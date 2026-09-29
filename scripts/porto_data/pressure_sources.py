"""Fetch and normalize the inputs of the parking pressure index.

Every ``fetch_*`` function takes a ``Fetcher`` and returns ``(records, source_record)``.
Only the minimum fields needed for aggregation are kept in memory.
"""

from __future__ import annotations

import io
import json
import math
import os
import sqlite3
import tempfile
import unicodedata
import urllib.parse
import zipfile
from datetime import datetime, timezone
from typing import Any

from . import geo
from .common import DataError, utc_now

PORTO_ENVELOPE = (-8.72, 41.12, -8.54, 41.20)  # min lon, min lat, max lon, max lat

CENSUS_URL = "https://mapas.ine.pt/download/filesGPG/2021/municipios/BGRI2021_1312.zip"
CENSUS_MEMBER = "BGRI2021_1312.gpkg"
CENSUS_METADATA_URL = "https://mapas.ine.pt/download/metadados/bgri.html"
CENSUS_REFERENCE_DATE = "2021-04-19"
CENSUS_HOUSEHOLDS_FIELD = "N_ALOJAMENTOS_FAM_CLASS_RHABITUAL"
CENSUS_PARKING_FIELD = "N_RHABITUAL_COM_ESTACIONAMENTO"

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OSM_AREA_ID = 3603372453
OSM_ROAD_CLASSES = ("primary", "secondary", "tertiary", "unclassified", "residential", "living_street")
OSM_METADATA_URL = "https://www.openstreetmap.org/relation/3372453"

CKAN_BASE = "https://dadosabertos.cm-porto.pt"
PRIVATE_ORIGIN = "http://192.168.221.240:8443"
RESTRICTIONS_SLUG = "condicionamentos-de-transito"
RESTRICTIONS_RESOURCE_ID = "a8d825c7-8057-4e61-b5f5-66691ef4c816"
RESTRICTIONS_URL = (
    f"{CKAN_BASE}/dataset/538f30de-9e19-11f1-84ed-6abdb6d5cf34/resource/{RESTRICTIONS_RESOURCE_ID}"
    "/download/ext-condicionamentos-de-transito-geojson.geojson"
)
RESTRICTIONS_METADATA_URL = f"{CKAN_BASE}/api/3/action/package_show?id={RESTRICTIONS_SLUG}"
MAX_RESTRICTION_DAYS = 366

COMPLAINTS_URL = "https://reportaporto.cm-porto.pt/o/apd/Occurrences"
COMPLAINT_CODES = ("C060901GO", "C060802GO", "C061701GO", "C061100GO")

PDM_URL = "https://pdm.cm-porto.pt/documents/63/71_PDMP_ECD_Sist_Mob_Transp.pdf"
PDM_ON_STREET_TOTAL = 64680


def _source(id_, name, url, metadata_url, license_, reference_date, count, caveat):
    return {
        "id": id_,
        "group": "pressure",
        "name": name,
        "url": url,
        "metadataUrl": metadata_url,
        "license": license_,
        "referenceDate": reference_date,
        "retrievedAt": utc_now(),
        "recordCount": count,
        "caveat": caveat,
    }


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# ----------------------------------------------------------------------------- census


def _census_int(value: Any, field: str) -> int:
    if value is None:
        raise DataError(f"Census field {field} is missing")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"Census field {field} must be an integer, got {value!r}")
    if not math.isfinite(value) or value != int(value):
        raise DataError(f"Census field {field} must be an integer, got {value!r}")
    if value < 0:
        raise DataError(f"Census field {field} must not be negative, got {value!r}")
    return int(value)


def _polygons_of(geometry: dict) -> list:
    kind = geometry.get("type")
    if kind == "GeometryCollection" and not geometry.get("geometries"):
        raise DataError("Census subsection has an empty geometry (GeoPackage empty flag set)")
    if kind == "Polygon":
        polygons = [geometry["coordinates"]]
    elif kind == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        raise DataError(f"Census geometry must be a polygon, got {kind!r}")
    return [[[(float(p[0]), float(p[1])) for p in ring] for ring in polygon] for polygon in polygons]


def read_census_gpkg(path: str) -> list[dict]:
    """Read BGRI subsections from a GeoPackage file (EPSG:3763 metres)."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        try:
            table_row = connection.execute(
                "SELECT table_name FROM gpkg_contents WHERE data_type = 'features' ORDER BY table_name"
            ).fetchall()
            if len(table_row) < 1:
                raise DataError("Census GeoPackage has no feature table")
            table = table_row[0][0]
            geom = connection.execute(
                "SELECT column_name, srs_id FROM gpkg_geometry_columns WHERE table_name = ?", (table,)
            ).fetchone()
            if geom is None:
                raise DataError("Census GeoPackage has no geometry column metadata")
            geometry_column, srs_id = geom
            if srs_id != 3763:
                raise DataError(f"Census GeoPackage CRS must be EPSG:3763, got {srs_id!r}")
            quoted = '"' + str(table).replace('"', '""') + '"'
            cursor = connection.execute(f"SELECT * FROM {quoted}")
        except sqlite3.Error as exc:
            raise DataError(f"Cannot read census GeoPackage: {exc}") from exc
        names = {d[0].upper(): i for i, d in enumerate(cursor.description)}
        for needed in (geometry_column.upper(), CENSUS_HOUSEHOLDS_FIELD, CENSUS_PARKING_FIELD):
            if needed not in names:
                raise DataError(f"Census table lacks column {needed}")
        g_i, h_i, p_i = names[geometry_column.upper()], names[CENSUS_HOUSEHOLDS_FIELD], names[CENSUS_PARKING_FIELD]
        records = []
        for row in cursor:
            blob = row[g_i]
            if not isinstance(blob, (bytes, bytearray)):
                raise DataError("Census subsection without geometry")
            households = _census_int(row[h_i], CENSUS_HOUSEHOLDS_FIELD)
            with_parking = _census_int(row[p_i], CENSUS_PARKING_FIELD)
            polygons = _polygons_of(geo.parse_gpkg_geometry(bytes(blob)))
            records.append({"polygons": polygons, "households": households, "withParking": with_parking})
    finally:
        connection.close()
    if not records:
        raise DataError("Census GeoPackage contains no subsections")
    return records


def fetch_census(fetcher) -> tuple[list[dict], dict]:
    payload = fetcher.get_bytes(CENSUS_URL, timeout=600)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            try:
                gpkg = archive.read(CENSUS_MEMBER)
            except KeyError as exc:
                raise DataError(f"Census archive lacks {CENSUS_MEMBER}") from exc
    except zipfile.BadZipFile as exc:
        raise DataError(f"Census download is not a valid zip archive: {exc}") from exc
    handle, path = tempfile.mkstemp(suffix=".gpkg")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(gpkg)
        records = read_census_gpkg(path)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    source = _source(
        "census",
        "INE Census 2021 — statistical subsections (BGRI), Porto",
        CENSUS_URL,
        CENSUS_METADATA_URL,
        "INE — open access, no conditions (cite INE, Censos 2021)",
        CENSUS_REFERENCE_DATE,
        len(records),
        "Households in habitual residence and those with own parking, by census subsection, apportioned "
        "evenly across a 25 m lattice inside each subsection. Not a count of cars or of parking demand.",
    )
    return records, source


# ----------------------------------------------------------------------------- OSM

POI_AMENITIES = (
    "university|college|hospital|school|restaurant|cafe|bar|pub|fast_food|nightclub|clinic|doctors"
    "|dentist|pharmacy|cinema|theatre|arts_centre"
)
POI_TOURISM = "hotel|hostel|guest_house|apartment|attraction|museum|gallery"


def overpass_query() -> str:
    roads = "|".join(OSM_ROAD_CLASSES)
    area = f"area({OSM_AREA_ID})->.a;"
    return (
        "[out:json][timeout:300];\n"
        f"{area}\n"
        f'way(area.a)["highway"~"^({roads})$"];\n'
        "out tags geom;\n"
        "(\n"
        '  nwr(area.a)["amenity"="parking"];\n'
        '  nwr(area.a)["office"];\n'
        '  nwr(area.a)["shop"];\n'
        f'  nwr(area.a)["amenity"~"^({POI_AMENITIES})$"];\n'
        f'  nwr(area.a)["tourism"~"^({POI_TOURISM})$"];\n'
        '  nwr(area.a)["leisure"="stadium"];\n'
        ");\n"
        "out tags center;\n"
    )


def _osm_tags(element: dict) -> dict:
    tags = element.get("tags", {})
    if not isinstance(tags, dict):
        raise DataError("OSM element tags must be an object")
    return {str(k): str(v) for k, v in tags.items()}


def parse_overpass(payload: Any) -> tuple[dict, str | None]:
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise DataError("Overpass response lacks an elements list")
    roads, parking, pois = [], [], []
    for element in payload["elements"]:
        if not isinstance(element, dict):
            raise DataError("Overpass element must be an object")
        kind = element.get("type")
        tags = _osm_tags(element)
        if kind == "way" and "geometry" in element and "highway" in tags:
            geometry = element["geometry"]
            if not isinstance(geometry, list):
                raise DataError("Overpass way geometry must be a list")
            coords = []
            for point in geometry:
                if point is None:
                    continue  # nodes clipped by the query area
                if not isinstance(point, dict) or not _finite(point.get("lon")) or not _finite(point.get("lat")):
                    raise DataError("Overpass geometry point is invalid")
                coords.append([float(point["lon"]), float(point["lat"])])
            if len(coords) >= 2:
                roads.append({"coords": coords, "tags": tags})
            continue
        if kind == "node":
            location = element
        else:
            location = element.get("center")
        if not isinstance(location, dict) or not _finite(location.get("lon")) or not _finite(location.get("lat")):
            continue  # no usable position; cannot be placed in a cell
        item = {"lon": float(location["lon"]), "lat": float(location["lat"]), "tags": tags}
        if tags.get("amenity") == "parking":
            parking.append(item)
        else:
            pois.append(item)
    if not roads:
        raise DataError("Overpass response contains no roads")
    osm3s = payload.get("osm3s")
    timestamp = osm3s.get("timestamp_osm_base") if isinstance(osm3s, dict) else None
    return {"roads": roads, "parking": parking, "pois": pois}, timestamp if isinstance(timestamp, str) else None


def fetch_osm(fetcher) -> tuple[dict, dict]:
    body = urllib.parse.urlencode({"data": overpass_query()}).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    payload = None
    errors = []
    for url in OVERPASS_URLS:
        try:
            raw = fetcher.get_bytes(url, data=body, headers=headers, timeout=400)
            payload = json.loads(raw.decode("utf-8"))
            osm, timestamp = parse_overpass(payload)
            break
        except (DataError, OSError, ValueError) as exc:
            errors.append(f"{url}: {exc}")
            payload = None
    if payload is None:
        raise DataError("Overpass query failed on all endpoints: " + "; ".join(errors))
    reference = timestamp[:10] if timestamp else None
    source = _source(
        "osm",
        "OpenStreetMap — roads, car parks and points of interest (Overpass)",
        OVERPASS_URLS[0],
        OSM_METADATA_URL,
        "ODbL-1.0 (© OpenStreetMap contributors)",
        reference,
        len(osm["roads"]) + len(osm["parking"]) + len(osm["pois"]),
        "Volunteer-mapped; completeness varies. Road parking-side tags are rare, so on-street supply is "
        "a modelled estimate, and car parks without a capacity tag are ignored.",
    )
    return osm, source


# ----------------------------------------------------------------------------- restrictions


def _fold(text: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().casefold()


def _rewrite_private_origin(url: str) -> str:
    if url.startswith(PRIVATE_ORIGIN):
        return CKAN_BASE + url[len(PRIVATE_ORIGIN):]
    return url


def _epoch_ms(value: Any) -> float | None:
    if not _finite(value):
        return None
    return float(value) / 1000.0


def _iso_date(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()


def _geometry_point(geometry: Any) -> tuple[float, float] | None:
    if not isinstance(geometry, dict):
        return None
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    try:
        if kind == "Point":
            return float(coords[0]), float(coords[1])
        if kind == "Polygon":
            polygon = [[geo.to_local(p[0], p[1]) for p in ring] for ring in coords]
            return geo.from_local(*geo.polygon_centroid(polygon))
        if kind == "MultiPolygon":
            polygon = [[geo.to_local(p[0], p[1]) for p in ring] for ring in coords[0]]
            return geo.from_local(*geo.polygon_centroid(polygon))
        flat: list = []

        def walk(value):
            if value and isinstance(value[0], (int, float)):
                flat.append(value)
            else:
                for item in value:
                    walk(item)

        walk(coords)
        if flat:
            return (sum(p[0] for p in flat) / len(flat), sum(p[1] for p in flat) / len(flat))
    except (TypeError, IndexError, KeyError, ValueError):
        return None
    return None


def parse_restrictions(payload: Any) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise DataError("Restrictions payload must be a FeatureCollection")
    records = []
    for feature in payload["features"]:
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            raise DataError("Restrictions feature is malformed")
        props = feature["properties"]
        if _fold(props.get("tipo_de_condicionamento", "")) != "estacionamento":
            continue
        start, end = _epoch_ms(props.get("data_de_inicio")), _epoch_ms(props.get("data_de_fim"))
        if start is None or end is None or end < start:
            continue
        point = _geometry_point(feature.get("geometry"))
        if point is None or not (PORTO_ENVELOPE[0] <= point[0] <= PORTO_ENVELOPE[2]
                                 and PORTO_ENVELOPE[1] <= point[1] <= PORTO_ENVELOPE[3]):
            continue
        days = min(MAX_RESTRICTION_DAYS, (end - start) / 86400.0)
        records.append({"lon": point[0], "lat": point[1], "days": days,
                        "start": _iso_date(start), "end": _iso_date(end)})
    return records


def fetch_restrictions(fetcher) -> tuple[list[dict], dict]:
    metadata = fetcher.get_json(RESTRICTIONS_METADATA_URL)
    if not isinstance(metadata, dict) or metadata.get("success") is not True:
        raise DataError("CKAN metadata did not report success")
    result = metadata.get("result")
    if not isinstance(result, dict):
        raise DataError("CKAN metadata result missing")
    if result.get("license_id") != "cc-zero":
        raise DataError(f"CC0 not verified: license_id={result.get('license_id')!r}")
    url = RESTRICTIONS_URL
    for resource in result.get("resources") or []:
        if isinstance(resource, dict) and resource.get("id") == RESTRICTIONS_RESOURCE_ID:
            advertised = resource.get("url")
            if isinstance(advertised, str):
                rewritten = _rewrite_private_origin(advertised)
                if rewritten.startswith(CKAN_BASE + "/"):
                    url = rewritten
    payload = fetcher.get_json(url)
    records = parse_restrictions(payload)
    reference = None
    if records:
        reference = f"{min(r['start'] for r in records)}/{max(r['end'] for r in records)}"
    source = _source(
        "restrictions",
        "Traffic restrictions — parking conditions (CKAN)",
        url,
        RESTRICTIONS_METADATA_URL,
        "CC0-1.0",
        reference,
        len(records),
        "Only entries typed 'Estacionamento' with valid start and end dates; duration is capped at "
        f"{MAX_RESTRICTION_DAYS} days and placed at the geometry centroid. Historical, not current signage.",
    )
    return records, source


# ----------------------------------------------------------------------------- complaints


def _parse_time(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_complaints(payload: Any) -> tuple[list[dict], int]:
    """Return (kept records, number dropped for coordinates outside the Porto envelope)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("Occurrences"), list):
        raise DataError("ReportaPorto response lacks an Occurrences list")
    records, dropped = [], 0
    for item in payload["Occurrences"]:
        if not isinstance(item, dict):
            continue
        service = item.get("service_type")
        code = service.get("service_code") if isinstance(service, dict) else None
        if code not in COMPLAINT_CODES:
            continue
        location = item.get("location")
        geographic = location.get("geographic") if isinstance(location, dict) else None
        coords = geographic.get("coordinates") if isinstance(geographic, dict) else None
        if not isinstance(coords, list) or len(coords) < 2 or not _finite(coords[0]) or not _finite(coords[1]):
            dropped += 1
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if not (PORTO_ENVELOPE[0] <= lon <= PORTO_ENVELOPE[2] and PORTO_ENVELOPE[1] <= lat <= PORTO_ENVELOPE[3]):
            dropped += 1
            continue
        timeline = item.get("timeline")
        requested = _parse_time(timeline.get("requested_datetime")) if isinstance(timeline, dict) else None
        records.append({"code": code, "lon": lon, "lat": lat, "requested": requested})
    return records, dropped


def fetch_complaints(fetcher) -> tuple[list[dict], dict]:
    payload = fetcher.get_json(COMPLAINTS_URL)
    records, dropped = parse_complaints(payload)
    times = sorted(r["requested"] for r in records if r["requested"])
    reference = f"{times[0][:10]}/{times[-1][:10]}" if times else None
    caveat = (
        "Citizen reports of irregular parking (sidewalk, double, cycle lane, abandoned vehicle); only code, "
        "position and request time are used, aggregated per cell. Reporting behaviour is uneven."
    )
    if dropped:
        caveat += f" {dropped} reports with missing or out-of-area coordinates were dropped."
    source = _source(
        "complaints",
        "ReportaPorto — parking-related occurrences",
        COMPLAINTS_URL,
        None,
        "No explicit licence; public web API (Lei 26/2016 art. 21.º(1)); aggregated counts only",
        reference,
        len(records),
        caveat,
    )
    return records, source


def calibration_source() -> dict:
    return _source(
        "calibration",
        "PDM Porto 2021 diagnosis — public on-street parking total",
        PDM_URL,
        None,
        "Municipal planning document, cited figure",
        None,
        1,
        f"The citywide total of {PDM_ON_STREET_TOTAL:,} public on-street spaces is distributed over the road "
        "network proportionally to eligible road length. Local supply is an estimate.",
    )
