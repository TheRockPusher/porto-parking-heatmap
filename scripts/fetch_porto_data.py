#!/usr/bin/env python3
"""Fetch Porto's public CC0 parking inventory, never occupancy or availability.

Python 3.10+, standard library only. Run from any directory:
    python3 scripts/fetch_porto_data.py [--output PATH]

Known public resource URLs come from HANDOFF.md. Each refresh verifies CKAN's
license and resource reference date, validates all four layers, then atomically
replaces the snapshot. Retrieval dates are not observation/reference dates.
"""

import argparse
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request


BASE_URL = "https://dadosabertos.cm-porto.pt"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "public/data/porto-parking.json"
# A generous Porto-area sanity envelope, NOT a municipal-boundary spatial join.
PORTO_BOUNDS = (-8.72, 41.12, -8.54, 41.20)
SOURCES = (
    {
        "id": "streets",
        "name": "Paid streets — Eixos Tarifados",
        "slug": "eixos-tarifados",
        "dataset": "564ca386-9e19-11f1-84ed-6abdb6d5cf34",
        "resource": "3a72d8f7-a5a6-4d35-b58f-0bbe5a3b9999",
        "filename": "ext-eixos-tarifados-geojson.geojson",
        "caveat": "Paid-street geometry, not bay capacity, meter locations, live availability or occupancy.",
    },
    {
        "id": "zones",
        "name": "Limited-duration tariff zones — ZEDL",
        "slug": "zonas-de-estacionamento-de-duracao-limitada-zedl",
        "dataset": "67480551-9e19-11f1-84ed-6abdb6d5cf34",
        "resource": "982e8ba5-340d-4dc5-be03-1ba1521cbe56",
        "filename": "ext-zonas-de-estacionamento-de-duracao-limitada-zedl-geojson.geojson",
        "caveat": "Tariff polygons, not individual spaces. Rates are one-hour EUR references matching municipal guidance, not a linear duration calculator. Check current signage; not live availability or occupancy.",
    },
    {
        "id": "spaces",
        "name": "Individual paid spaces — western area",
        "slug": "lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental",
        "dataset": "5c04defd-9e19-11f1-84ed-6abdb6d5cf34",
        "resource": "ed32ec82-efbd-4921-8c4d-3fa4ac1597b0",
        "filename": "ext-lugares-de-estacionamento-zonas-de-estacionamento-pago-zona-ocidental-geojson.geojson",
        "caveat": "Western-area inventory only; active, inactive and unknown source statuses are preserved. Status is not current availability or occupancy; counts are not citywide capacity. Resident zones are not tariff classes.",
    },
    {
        "id": "garages",
        "name": "Municipal parking facilities",
        "slug": "parques-de-estacionamento-municipais",
        "dataset": "5ea79d81-9e19-11f1-84ed-6abdb6d5cf34",
        "resource": "7364670a-1fa0-4189-9729-5d314f8701f1",
        "filename": "ext-parques-de-estacionamento-municipais-geojson.geojson",
        "caveat": "Historical municipal facility inventory. Light-vehicle capacity is one source category, not total capacity or free spaces; other categories and missing values remain in attributes. Operators and hours may have changed. No live availability or occupancy.",
    },
)
GEOMETRY_TYPES = {
    "streets": {"LineString", "MultiLineString"},
    "zones": {"Polygon", "MultiPolygon"},
    "spaces": {"Point"},
    "garages": {"Point"},
}


class DataError(ValueError):
    """An upstream source cannot safely become a published snapshot."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def source_urls(spec):
    return (
        f"{BASE_URL}/dataset/{spec['dataset']}/resource/{spec['resource']}/download/{spec['filename']}",
        f"{BASE_URL}/api/3/action/package_show?id={spec['slug']}",
    )


def reject_constant(value):
    raise DataError(f"Non-finite JSON number: {value}")


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "porto-parking-inventory/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8-sig"), parse_constant=reject_constant)
    except (urllib.error.URLError, OSError, UnicodeError, ValueError) as exc:
        raise DataError(f"Cannot retrieve valid JSON from {url}: {exc}") from exc


def reference_date(metadata, spec):
    if not isinstance(metadata, dict) or metadata.get("success") is not True:
        raise DataError("CKAN metadata did not report success")
    result = metadata.get("result")
    if not isinstance(result, dict) or result.get("id") != spec["dataset"]:
        raise DataError("CKAN metadata dataset ID does not match the requested source")
    if result.get("license_id") != "cc-zero":
        raise DataError(f"CC0 not verified: license_id={result.get('license_id')!r}")
    resources = result.get("resources")
    if not isinstance(resources, list):
        raise DataError("CKAN metadata resources must be a list")
    matches = [r for r in resources if isinstance(r, dict) and r.get("id") == spec["resource"]]
    if len(matches) != 1 or str(matches[0].get("format", "")).lower() != "geojson":
        raise DataError("Expected GeoJSON resource missing or ambiguous in CKAN metadata")
    value = matches[0].get("reference_date")
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError("expected YYYY-MM-DD")
    except ValueError as exc:
        raise DataError(f"Invalid or missing resource reference_date: {value!r}") from exc
    return value


def nullable_text(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise DataError(f"{field} must be text or null")
    return value.strip() or None


def nonnegative_number(value, field, integer=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DataError(f"{field} must be a finite number or null")
    if value < 0 or (integer and value != int(value)):
        raise DataError(f"{field} must be a nonnegative {'integer' if integer else 'number'}")
    return int(value) if integer else value


def validate_geometry(geometry, kind):
    if not isinstance(geometry, dict) or geometry.get("type") not in GEOMETRY_TYPES[kind]:
        raise DataError(f"{kind} geometry must be one of {sorted(GEOMETRY_TYPES[kind])}")

    def position(value):
        if not isinstance(value, list) or len(value) not in (2, 3):
            raise DataError("A coordinate must contain longitude, latitude and optional altitude")
        if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in value):
            raise DataError("Coordinates must be finite WGS84 numbers")
        west, south, east, north = PORTO_BOUNDS
        if not west <= value[0] <= east or not south <= value[1] <= north:
            raise DataError(f"Coordinate outside Porto-area WGS84 bounds: {value}")

    def sequence(value, minimum, validator):
        if not isinstance(value, list) or len(value) < minimum:
            raise DataError(f"Geometry coordinate sequence needs at least {minimum} entries")
        for item in value:
            validator(item)

    def line(value):
        sequence(value, 2, position)

    def ring(value):
        sequence(value, 4, position)
        if value[0] != value[-1]:
            raise DataError("Polygon ring must be closed")
        if len({tuple(p[:2]) for p in value[:-1]}) < 3:
            raise DataError("Polygon ring needs at least three distinct positions")

    def polygon(value):
        sequence(value, 1, ring)

    coordinates = geometry.get("coordinates")
    geometry_type = geometry["type"]
    if geometry_type == "Point":
        position(coordinates)
    elif geometry_type == "LineString":
        line(coordinates)
    elif geometry_type == "MultiLineString":
        sequence(coordinates, 1, line)
    elif geometry_type == "Polygon":
        polygon(coordinates)
    else:
        sequence(coordinates, 1, polygon)


def normalize_feature(feature, kind):
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise DataError("Expected a GeoJSON Feature")
    attrs = feature.get("properties")
    if not isinstance(attrs, dict):
        raise DataError("Feature properties must be an object")
    object_id = attrs.get("objectid")
    if type(object_id) is not int or object_id <= 0:
        raise DataError(f"objectid must be a positive integer, got {object_id!r}")
    identifier = f"{kind}:{object_id}"
    geometry = feature.get("geometry")
    validate_geometry(geometry, kind)
    props = {"id": identifier, "kind": kind, "sourceId": kind, "attributes": attrs}
    if kind in ("streets", "spaces"):
        props["name"] = nullable_text(attrs.get("toponimo"), "toponimo")
    if kind == "streets":
        if attrs.get("tarifado") != "Sim":
            raise DataError(f"Paid-street tarifado must be 'Sim', got {attrs.get('tarifado')!r}")
    elif kind == "zones":
        zone = nullable_text(attrs.get("zona"), "zona")
        if zone is not None and zone not in {"I", "II", "III", "IV"}:
            raise DataError(f"Unsupported tariff zone category: {zone!r}")
        props.update(name=f"Zone {zone}" if zone else None, zone=zone,
                     hourlyRate=nonnegative_number(attrs.get("valor_taxa"), "valor_taxa"))
    elif kind == "spaces":
        status = nullable_text(attrs.get("estado"), "estado")
        statuses = {"Ativo": "active", "Inativo": "inactive", None: "unknown"}
        if status not in statuses:
            raise DataError(f"Unsupported inventory status: {status!r}")
        resident_zone = attrs.get("num_zona")
        if resident_zone is not None:
            if type(resident_zone) is not int or resident_zone <= 0:
                raise DataError("num_zona must be a positive integer or null")
            resident_zone = str(resident_zone)
        props.update(status=statuses[status], residentZone=resident_zone)
    else:
        # Never add these categories: the source does not establish total semantics.
        for field, value in attrs.items():
            if field.startswith("nº_lugares_"):
                nonnegative_number(value, field, integer=True)
        props.update(
            name=nullable_text(attrs.get("designacao"), "designacao"),
            address=nullable_text(attrs.get("toponimo"), "toponimo"),
            operator=nullable_text(attrs.get("entid_gest"), "entid_gest"),
            openingHours=nullable_text(attrs.get("horario_funcionamento"), "horario_funcionamento"),
            lightVehicleCapacity=nonnegative_number(attrs.get("nº_lugares_ligeiros"), "nº_lugares_ligeiros", integer=True),
        )
    return {"type": "Feature", "id": identifier, "geometry": geometry, "properties": props}


def normalize_collection(payload, kind):
    if kind not in GEOMETRY_TYPES:
        raise DataError(f"Unknown layer: {kind!r}")
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise DataError("Expected a GeoJSON FeatureCollection")
    crs = payload.get("crs")
    if crs is not None:
        allowed = {"urn:ogc:def:crs:OGC:1.3:CRS84", "urn:ogc:def:crs:EPSG::4326", "EPSG:4326"}
        if not isinstance(crs, dict) or crs.get("type") != "name" or not isinstance(crs.get("properties"), dict) or crs["properties"].get("name") not in allowed:
            raise DataError("Source CRS must be WGS84 longitude/latitude")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise DataError("Source features must be a nonempty list; refusing an empty replacement")
    normalized = []
    seen = set()
    for index, feature in enumerate(features):
        try:
            item = normalize_feature(feature, kind)
            if item["id"] in seen:
                raise DataError(f"Duplicate objectid: {item['id']}")
            seen.add(item["id"])
            normalized.append(item)
        except DataError as exc:
            raise DataError(f"{kind} feature #{index + 1}: {exc}") from exc
    normalized.sort(key=lambda item: item["properties"]["attributes"]["objectid"])
    return {"type": "FeatureCollection", "features": normalized}


def build_snapshot(fetch=fetch_json):
    collections = {}
    sources = []
    for spec in SOURCES:
        url, metadata_url = source_urls(spec)
        try:
            reference = reference_date(fetch(metadata_url), spec)
            collection = normalize_collection(fetch(url), spec["id"])
        except DataError as exc:
            raise DataError(f"{spec['id']}: {exc}") from exc
        collections[spec["id"]] = collection
        sources.append({
            "id": spec["id"], "name": spec["name"], "url": url,
            "metadataUrl": metadata_url, "license": "CC0-1.0", "referenceDate": reference,
            "retrievedAt": utc_now(), "featureCount": len(collection["features"]),
            "caveat": spec["caveat"],
        })
    return {"schemaVersion": 1, "generatedAt": utc_now(), "sources": sources, "collections": collections}


def write_snapshot(snapshot, output):
    """Complete serialization before atomic replacement, including on disk errors."""
    output = Path(output)
    encoded = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def refresh(output, fetch=fetch_json):
    snapshot = build_snapshot(fetch)
    write_snapshot(snapshot, output)
    return snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path (default: public/data/porto-parking.json)")
    args = parser.parse_args(argv)
    try:
        snapshot = refresh(args.output)
    except (DataError, OSError, ValueError) as exc:
        print(f"Porto data refresh failed; previous snapshot was not replaced: {exc}", file=sys.stderr)
        return 1
    counts = ", ".join(f"{source['id']}={source['featureCount']}" for source in snapshot["sources"])
    print(f"Wrote {args.output}: {counts}. Inventory/tariffs only; not live availability or occupancy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
