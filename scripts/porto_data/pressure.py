"""Hex-grid aggregation and the estimated parking pressure index.

The index is an ESTIMATE of relative demand versus supply. It is not occupancy or availability.
``compute_pressure`` is pure (no I/O); ``build_pressure`` fetches the inputs and calls it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from . import geo
from . import pressure_sources as sources

LATTICE_STEP_M = 25.0
MIN_SUPPLY_FOR_INDEX = 5
GARAGE_DEDUPE_M = 100.0
SCHEMA_VERSION = 2

BLOCKED_PARKING = frozenset({"no", "no_parking", "no_stopping", "separate"})
EXCLUDED_ROAD_ACCESS = frozenset({"private", "no"})
EXCLUDED_PARKING_ACCESS = frozenset({"private", "no", "permit"})
EXCLUDED_PARKING_TYPES = frozenset({"garage_boxes", "carports"})

# Documented assumptions, not measurements.
POI_KEY_WEIGHTS = {"office": 3.0, "shop": 1.0}
POI_VALUE_WEIGHTS = {
    ("amenity", "university"): 10.0,
    ("amenity", "college"): 10.0,
    ("amenity", "hospital"): 10.0,
    ("amenity", "school"): 3.0,
    ("amenity", "restaurant"): 1.0,
    ("amenity", "cafe"): 1.0,
    ("amenity", "bar"): 1.0,
    ("amenity", "pub"): 1.0,
    ("amenity", "fast_food"): 1.0,
    ("amenity", "nightclub"): 1.0,
    ("amenity", "clinic"): 1.0,
    ("amenity", "doctors"): 1.0,
    ("amenity", "dentist"): 1.0,
    ("amenity", "pharmacy"): 1.0,
    ("tourism", "hotel"): 1.0,
    ("tourism", "hostel"): 1.0,
    ("tourism", "guest_house"): 1.0,
    ("tourism", "apartment"): 1.0,
    ("tourism", "attraction"): 2.0,
    ("tourism", "museum"): 2.0,
    ("tourism", "gallery"): 2.0,
    ("amenity", "cinema"): 2.0,
    ("amenity", "theatre"): 2.0,
    ("amenity", "arts_centre"): 2.0,
    ("leisure", "stadium"): 10.0,
}
POI_WEIGHTS_DOC = {
    **{f"{key}=*": w for key, w in POI_KEY_WEIGHTS.items()},
    **{f"{key}={value}": w for (key, value), w in POI_VALUE_WEIGHTS.items()},
}

NOTES = (
    "Estimated relative parking pressure, not occupancy or availability. Overnight = households without "
    "own parking per estimated public on-street space; daytime = weighted points-of-interest score per "
    "estimated public parking space (on-street plus off-street). Indices are percentile ranks among "
    "cells with at least 5 estimated spaces. On-street supply distributes the PDM 2021 total of 64,680 "
    "spaces over OSM road length, so it is a model, not a survey. Weights are documented assumptions."
)


# ----------------------------------------------------------------------------- helpers


def cell_key(lon: float, lat: float) -> tuple[int, int]:
    return geo.hex_of_lonlat(lon, lat)


def poi_weight(tags: dict) -> float:
    """Highest applicable attraction weight of a feature (0 when none applies)."""
    best = 0.0
    for key, weight in POI_KEY_WEIGHTS.items():
        if key in tags:
            best = max(best, weight)
    for key in ("amenity", "tourism", "leisure"):
        best = max(best, POI_VALUE_WEIGHTS.get((key, tags.get(key)), 0.0))
    return best


def road_sides(tags: dict) -> int:
    """Number of kerbs (0-2) on which public parking is assumed possible."""
    if tags.get("parking:both") in BLOCKED_PARKING:
        return 0
    sides = 2
    for side in ("parking:left", "parking:right"):
        if tags.get(side) in BLOCKED_PARKING:
            sides -= 1
    return sides


def road_eligible(tags: dict) -> bool:
    if tags.get("highway") not in sources.OSM_ROAD_CLASSES:
        return False
    if tags.get("area") == "yes":
        return False
    for key in ("tunnel", "bridge"):
        if tags.get(key) not in (None, "no"):
            return False
    return tags.get("access") not in EXCLUDED_ROAD_ACCESS


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        try:
            number = int(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if number > 0 else None


def qualifying_parking(osm_parking: list[dict]) -> list[tuple[float, float, int]]:
    """(lon, lat, capacity) of public OSM car parks with a usable capacity tag."""
    result = []
    for item in osm_parking:
        tags = item["tags"]
        if tags.get("amenity") != "parking":
            continue
        capacity = _positive_int(tags.get("capacity"))
        if capacity is None:
            continue
        if tags.get("access") in EXCLUDED_PARKING_ACCESS or tags.get("parking") in EXCLUDED_PARKING_TYPES:
            continue
        result.append((item["lon"], item["lat"], capacity))
    return result


def census_cells(census: list[dict]) -> tuple[dict, dict, dict]:
    """Apportion subsections onto hex cells via a 25 m lattice.

    Returns (lattice points per cell, households per cell, households-with-parking per cell); the
    last two are unrounded floats whose sums equal the subsection totals.
    """
    points: dict[tuple[int, int], int] = defaultdict(int)
    households: dict[tuple[int, int], float] = defaultdict(float)
    with_parking: dict[tuple[int, int], float] = defaultdict(float)
    for subsection in census:
        lattice = []
        for polygon in subsection["polygons"]:
            lattice.extend(geo.lattice_points_in_polygon(polygon, LATTICE_STEP_M))
        if not lattice:
            polygons = subsection["polygons"]
            if not polygons:
                continue
            lattice = [geo.polygon_centroid(polygons[0])]
        share_h = subsection["households"] / len(lattice)
        share_p = subsection["withParking"] / len(lattice)
        for x, y in lattice:
            lon, lat = geo.tm06_to_wgs84(x, y)
            key = cell_key(lon, lat)
            points[key] += 1
            households[key] += share_h
            with_parking[key] += share_p
    return dict(points), dict(households), dict(with_parking)


def _zone_index(zones: dict | None) -> list[tuple[tuple, list, str | None]]:
    index = []
    for feature in (zones or {}).get("features", []):
        geometry = feature.get("geometry") or {}
        zone = (feature.get("properties") or {}).get("zone")
        if geometry.get("type") == "Polygon":
            polygons = [geometry["coordinates"]]
        elif geometry.get("type") == "MultiPolygon":
            polygons = geometry["coordinates"]
        else:
            continue
        for polygon in polygons:
            local = [[geo.to_local(p[0], p[1]) for p in ring] for ring in polygon]
            index.append((geo.polygon_bbox(local), local, zone))
    return index


def _zone_at(x: float, y: float, index: list) -> str | None:
    for (min_x, min_y, max_x, max_y), polygon, zone in index:
        if min_x <= x <= max_x and min_y <= y <= max_y and geo.point_in_polygon(x, y, polygon):
            return zone
    return None


def percentile_index(values: list[float | None]) -> list[int | None]:
    """0-100 percentile rank with average ranks for ties; None stays None; n == 1 -> 50."""
    eligible = sorted((v, i) for i, v in enumerate(values) if v is not None)
    result: list[int | None] = [None] * len(values)
    n = len(eligible)
    position = 0
    while position < n:
        end = position
        while end + 1 < n and eligible[end + 1][0] == eligible[position][0]:
            end += 1
        rank_avg = (position + end) / 2 + 1  # 1-based average rank
        pct = 0.5 if n == 1 else (rank_avg - 1) / (n - 1)
        score = int(math.floor(100 * pct + 0.5))
        for _, i in eligible[position:end + 1]:
            result[i] = score
        position = end + 1
    return result


def _window(values: list[str]) -> list[str] | None:
    return [min(values), max(values)] if values else None


# ----------------------------------------------------------------------------- computation


def compute_pressure(census: list[dict], osm: dict, restrictions: list[dict],
                     complaints: list[dict], inventory: dict) -> dict:
    points, households, with_parking = census_cells(census)
    if not points:
        raise sources.DataError("Census produced no cells in scope")
    scope = set(points)

    # Road supply
    road_len: dict[tuple[int, int], float] = defaultdict(float)
    for road in osm["roads"]:
        tags = road["tags"]
        if not road_eligible(tags):
            continue
        sides = road_sides(tags)
        if sides == 0:
            continue
        for lon, lat, weight in geo.densify_line(road["coords"], 10.0):
            key = cell_key(lon, lat)
            if key in scope:
                road_len[key] += weight * sides / 2
    total_len = sum(road_len.values())

    # Off-street public capacity
    off_street: dict[tuple[int, int], int] = defaultdict(int)
    osm_parking = qualifying_parking(osm["parking"])
    for lon, lat, capacity in osm_parking:
        key = cell_key(lon, lat)
        if key in scope:
            off_street[key] += capacity
    for feature in (inventory.get("garages") or {}).get("features", []):
        capacity = _positive_int((feature.get("properties") or {}).get("lightVehicleCapacity"))
        geometry = feature.get("geometry") or {}
        if capacity is None or geometry.get("type") != "Point":
            continue
        lon, lat = geometry["coordinates"][:2]
        key = cell_key(lon, lat)
        if key not in scope:
            continue
        if any(geo.haversine_m(lon, lat, plon, plat) <= GARAGE_DEDUPE_M for plon, plat, _ in osm_parking):
            continue
        off_street[key] += capacity

    # Western active paid spaces
    western: dict[tuple[int, int], int] = defaultdict(int)
    for feature in (inventory.get("spaces") or {}).get("features", []):
        geometry = feature.get("geometry") or {}
        if (feature.get("properties") or {}).get("status") != "active" or geometry.get("type") != "Point":
            continue
        lon, lat = geometry["coordinates"][:2]
        key = cell_key(lon, lat)
        if key in scope:
            western[key] += 1

    # Attraction
    attraction: dict[tuple[int, int], float] = defaultdict(float)
    for poi in osm["pois"]:
        weight = poi_weight(poi["tags"])
        if weight <= 0:
            continue
        key = cell_key(poi["lon"], poi["lat"])
        if key in scope:
            attraction[key] += weight

    # Complaints
    complaint_count: dict[tuple[int, int], int] = defaultdict(int)
    for record in complaints:
        if record["code"] not in sources.COMPLAINT_CODES:
            continue
        key = cell_key(record["lon"], record["lat"])
        if key in scope:
            complaint_count[key] += 1
    complaint_times = [r["requested"] for r in complaints
                       if r["code"] in sources.COMPLAINT_CODES and r.get("requested")]

    # Restrictions
    restriction_days: dict[tuple[int, int], float] = defaultdict(float)
    for record in restrictions:
        key = cell_key(record["lon"], record["lat"])
        if key in scope:
            restriction_days[key] += record["days"]
    restriction_starts = [r["start"] for r in restrictions if r.get("start")]
    restriction_ends = [r["end"] for r in restrictions if r.get("end")]
    restrictions_window = [min(restriction_starts), max(restriction_ends)] if restriction_starts else None

    zone_index = _zone_index(inventory.get("zones"))
    keys = sorted(scope, key=lambda k: (k[1], k[0]))
    columns: dict[str, list] = {name: [] for name in (
        "q", "r", "coverage", "zone", "households", "householdsWithParking", "residentDemand",
        "roadLengthM", "onStreetEstimate", "offStreetPublic", "westernActiveSpaces", "attraction",
        "complaints", "restrictionDays", "overnightRatio", "daytimeRatio", "overnightIndex", "daytimeIndex")}
    overnight: list[float | None] = []
    daytime: list[float | None] = []
    for key in keys:
        q, r = key
        hh = int(round(households.get(key, 0.0)))
        wp = int(round(with_parking.get(key, 0.0)))
        demand = max(0, hh - wp)
        length = road_len.get(key, 0.0)
        on_street = sources.PDM_ON_STREET_TOTAL * length / total_len if total_len > 0 else 0.0
        off = off_street.get(key, 0)
        attract = attraction.get(key, 0.0)
        cx, cy = geo.hex_center_local(q, r)
        over = demand / on_street if on_street >= MIN_SUPPLY_FOR_INDEX else None
        day = attract / (on_street + off) if on_street + off >= MIN_SUPPLY_FOR_INDEX else None
        overnight.append(over)
        daytime.append(day)
        columns["q"].append(q)
        columns["r"].append(r)
        columns["coverage"].append(round(min(1.0, points[key] * LATTICE_STEP_M ** 2 / geo.HEX_AREA_M2), 2))
        columns["zone"].append(_zone_at(cx, cy, zone_index))
        columns["households"].append(hh)
        columns["householdsWithParking"].append(wp)
        columns["residentDemand"].append(round(float(demand), 1))
        columns["roadLengthM"].append(int(round(length)))
        columns["onStreetEstimate"].append(round(on_street, 1))
        columns["offStreetPublic"].append(int(off))
        columns["westernActiveSpaces"].append(western.get(key, 0))
        columns["attraction"].append(round(attract, 1))
        columns["complaints"].append(complaint_count.get(key, 0))
        columns["restrictionDays"].append(round(restriction_days.get(key, 0.0), 1))
        columns["overnightRatio"].append(None if over is None else round(over, 3))
        columns["daytimeRatio"].append(None if day is None else round(day, 3))
    columns["overnightIndex"] = percentile_index(overnight)
    columns["daytimeIndex"] = percentile_index(daytime)

    dataset = {
        "schemaVersion": SCHEMA_VERSION,
        "grid": {
            "type": "hex-axial-pointy",
            "circumradiusM": 150,
            "origin": [geo.ORIGIN[0], geo.ORIGIN[1]],
            "earthRadiusM": geo.EARTH_RADIUS_M,
            "projection": "equirectangular-local",
        },
        "periods": ["daytime", "overnight"],
        "method": {
            "onStreetTotalCalibration": sources.PDM_ON_STREET_TOTAL,
            "roadClasses": list(sources.OSM_ROAD_CLASSES),
            "poiWeights": dict(POI_WEIGHTS_DOC),
            "minSupplyForIndex": MIN_SUPPLY_FOR_INDEX,
            "complaintServiceCodes": list(sources.COMPLAINT_CODES),
            "complaintWindow": _window(complaint_times),
            "restrictionsWindow": restrictions_window,
            "notes": NOTES,
        },
        "cells": columns,
    }
    validate_pressure(dataset)
    return dataset


def validate_pressure(dataset: dict) -> None:
    columns = dataset["cells"]
    lengths = {len(v) for v in columns.values()}
    if len(lengths) != 1 or lengths == {0}:
        raise sources.DataError("Pressure columns must be non-empty and of equal length")
    for name, values in columns.items():
        for value in values:
            if isinstance(value, float) and not math.isfinite(value):
                raise sources.DataError(f"Pressure column {name} contains a non-finite number")
    for name in ("overnightIndex", "daytimeIndex"):
        for value in columns[name]:
            if value is not None and not 0 <= value <= 100:
                raise sources.DataError(f"Pressure column {name} has an index outside 0-100")
    order = list(zip(columns["r"], columns["q"]))
    if order != sorted(order):
        raise sources.DataError("Pressure cells must be sorted by (r, q)")


def build_pressure(fetcher, inventory: dict[str, dict]) -> tuple[dict, list[dict]]:
    census, census_source = sources.fetch_census(fetcher)
    osm, osm_source = sources.fetch_osm(fetcher)
    restrictions, restrictions_source = sources.fetch_restrictions(fetcher)
    complaints, complaints_source = sources.fetch_complaints(fetcher)
    dataset = compute_pressure(census, osm, restrictions, complaints, inventory)
    records = [census_source, osm_source, restrictions_source, complaints_source, sources.calibration_source()]
    return dataset, records
