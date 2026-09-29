"""Porto's public CC0 parking inventory (streets, zones, spaces, garages).

Inventory and tariffs only, never occupancy or availability. Each source's CKAN
license and resource reference date are verified, every feature is validated,
then compact features (rendering/search properties) and lazily loaded raw
attribute tables are produced separately.
"""

from datetime import date
import math

from .common import DataError, Fetcher, round_coords, utc_now


BASE_URL = "https://dadosabertos.cm-porto.pt"
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
        "caveat": "Historical municipal facility inventory. Light-vehicle capacity is one source category, not total capacity or free spaces; other categories and missing values remain in the original attributes. Operators and hours may have changed. No live availability or occupancy.",
    },
)
GEOMETRY_TYPES = {
    "streets": {"LineString", "MultiLineString"},
    "zones": {"Polygon", "MultiPolygon"},
    "spaces": {"Point"},
    "garages": {"Point"},
}


def source_urls(spec):
    """(download URL, CKAN package_show URL)."""
    return (
        f"{BASE_URL}/dataset/{spec['dataset']}/resource/{spec['resource']}/download/{spec['filename']}",
        f"{BASE_URL}/api/3/action/package_show?id={spec['slug']}",
    )


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


# Geometry validation -------------------------------------------------------

def _position(value):
    if not isinstance(value, list) or len(value) not in (2, 3):
        raise DataError("A coordinate must contain longitude, latitude and optional altitude")
    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in value):
        raise DataError("Coordinates must be finite WGS84 numbers")
    west, south, east, north = PORTO_BOUNDS
    if not west <= value[0] <= east or not south <= value[1] <= north:
        raise DataError(f"Coordinate outside Porto-area WGS84 bounds: {value}")


def _sequence(value, minimum, validator):
    if not isinstance(value, list) or len(value) < minimum:
        raise DataError(f"Geometry coordinate sequence needs at least {minimum} entries")
    for item in value:
        validator(item)


def _line(value):
    _sequence(value, 2, _position)


def _ring(value):
    _sequence(value, 4, _position)
    if value[0] != value[-1]:
        raise DataError("Polygon ring must be closed")
    if len({tuple(p[:2]) for p in value[:-1]}) < 3:
        raise DataError("Polygon ring needs at least three distinct positions")


def _polygon(value):
    _sequence(value, 1, _ring)


def validate_geometry(geometry, kind):
    if not isinstance(geometry, dict) or geometry.get("type") not in GEOMETRY_TYPES[kind]:
        raise DataError(f"{kind} geometry must be one of {sorted(GEOMETRY_TYPES[kind])}")
    coordinates = geometry.get("coordinates")
    geometry_type = geometry["type"]
    if geometry_type == "Point":
        _position(coordinates)
    elif geometry_type == "LineString":
        _line(coordinates)
    elif geometry_type == "MultiLineString":
        _sequence(coordinates, 1, _line)
    elif geometry_type == "Polygon":
        _polygon(coordinates)
    else:
        _sequence(coordinates, 1, _polygon)


# Geometry compaction (post-validation) --------------------------------------

def _is_valid(validator, value):
    try:
        validator(value)
    except DataError:
        return False
    return True


def _dedupe(positions):
    result = []
    for position in positions:
        if not result or position != result[-1]:
            result.append(position)
    return result


def _compact_sequence(original, validator):
    """Round to 6 dp and drop consecutive duplicates, but only while the sequence stays valid.

    Falls back to rounded-only, then to the untouched source coordinates, so
    compaction can never turn a valid source geometry into an invalid one.
    """
    rounded = round_coords(original)
    for candidate in (_dedupe(rounded), rounded):
        if _is_valid(validator, candidate):
            return candidate
    return original


def compact_geometry(geometry):
    geometry_type = geometry["type"]
    coordinates = geometry["coordinates"]
    if geometry_type == "Point":
        compacted = round_coords(coordinates)
    elif geometry_type == "LineString":
        compacted = _compact_sequence(coordinates, _line)
    elif geometry_type == "MultiLineString":
        compacted = [_compact_sequence(line, _line) for line in coordinates]
    elif geometry_type == "Polygon":
        compacted = [_compact_sequence(ring, _ring) for ring in coordinates]
    else:
        compacted = [[_compact_sequence(ring, _ring) for ring in polygon] for polygon in coordinates]
    return {"type": geometry_type, "coordinates": compacted}


# Feature normalization ---------------------------------------------------------

def normalize_feature(feature, kind):
    """Return (compact Feature, original attributes) for one validated source feature."""
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
    props = {"id": identifier, "kind": kind}
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
    return {"type": "Feature", "geometry": compact_geometry(geometry), "properties": props}, attrs


def normalize_with_attributes(payload, kind):
    """Validate a source FeatureCollection; return (compact collection, {feature id: original attributes})."""
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
            item, attrs = normalize_feature(feature, kind)
            identifier = item["properties"]["id"]
            if identifier in seen:
                raise DataError(f"Duplicate objectid: {identifier}")
            seen.add(identifier)
            normalized.append((attrs["objectid"], item, attrs))
        except DataError as exc:
            raise DataError(f"{kind} feature #{index + 1}: {exc}") from exc
    normalized.sort(key=lambda entry: entry[0])
    collection = {"type": "FeatureCollection", "features": [item for _, item, _ in normalized]}
    attributes = {item["properties"]["id"]: attrs for _, item, attrs in normalized}
    return collection, attributes


def normalize_collection(payload, kind):
    """Compact FeatureCollection only (attributes are split off by normalize_with_attributes)."""
    return normalize_with_attributes(payload, kind)[0]


def build_inventory(fetcher: Fetcher):
    """Fetch and verify all four sources.

    Returns (collections by kind, attribute tables by kind keyed by feature id,
    SourceRecords with group "inventory").
    """
    collections = {}
    attributes = {}
    sources = []
    for spec in SOURCES:
        url, metadata_url = source_urls(spec)
        try:
            reference = reference_date(fetcher.get_json(metadata_url), spec)
            collection, attrs = normalize_with_attributes(fetcher.get_json(url), spec["id"])
        except DataError as exc:
            raise DataError(f"{spec['id']}: {exc}") from exc
        collections[spec["id"]] = collection
        attributes[spec["id"]] = attrs
        sources.append({
            "id": spec["id"], "group": "inventory", "name": spec["name"], "url": url,
            "metadataUrl": metadata_url, "license": "CC0-1.0", "referenceDate": reference,
            "retrievedAt": utc_now(), "recordCount": len(collection["features"]),
            "caveat": spec["caveat"],
        })
    return collections, attributes, sources
