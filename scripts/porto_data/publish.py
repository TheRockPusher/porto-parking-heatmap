"""Publish content-hashed immutable dataset files plus one small mutable manifest.

Order: validate everything and serialize in memory, write all hashed files
atomically, write manifest.json atomically, then prune stale hashed files and
the legacy monolithic bundle. A failure before the manifest replacement leaves
the previous manifest (and every file it references) untouched.
"""

from pathlib import Path
import re

from .common import DataError, atomic_write_bytes, content_hash, dumps_compact


SCHEMA_VERSION = 2
INVENTORY_KINDS = ("zones", "streets", "spaces", "garages")
# Everything this module may ever delete; nothing else in the directory is touched.
HASHED_FILE = re.compile(r"^(zones|streets|spaces|garages|pressure)(\.attrs)?\.[0-9a-f]{10}\.json$")
LEGACY_BUNDLE = "porto-parking.json"
MANIFEST_NAME = "manifest.json"
# Manifest paths are relative to the site base URL, which serves public/ as root.
PATH_PREFIX = "data/"


def _validate(collections, attributes, pressure, sources):
    for kind in INVENTORY_KINDS:
        collection = collections.get(kind) if isinstance(collections, dict) else None
        if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
            raise DataError(f"Missing or invalid {kind} collection")
        features = collection.get("features")
        if not isinstance(features, list) or not features:
            raise DataError(f"{kind} collection has no features")
        table = attributes.get(kind) if isinstance(attributes, dict) else None
        if not isinstance(table, dict):
            raise DataError(f"Missing {kind} attribute table")
        ids = {feature.get("properties", {}).get("id") for feature in features}
        if ids != set(table):
            raise DataError(f"{kind} attribute table does not match its features")
    cells = pressure.get("cells") if isinstance(pressure, dict) else None
    if not isinstance(cells, dict) or not isinstance(cells.get("q"), list):
        raise DataError("Pressure dataset must contain columnar cells")
    if not isinstance(sources, list) or not sources:
        raise DataError("At least one source record is required")


def publish(output_dir: Path, *, generated_at: str, collections, attributes, pressure, sources) -> dict:
    """Write datasets + manifest into output_dir and return the manifest."""
    output_dir = Path(output_dir)
    _validate(collections, attributes, pressure, sources)

    # Serialize everything up front: NaN or unserializable values fail before any write.
    files = {}  # file name -> bytes
    datasets = {}
    for kind in INVENTORY_KINDS:
        body = dumps_compact(collections[kind])
        attrs_body = dumps_compact(attributes[kind])
        name = f"{kind}.{content_hash(body)}.json"
        attrs_name = f"{kind}.attrs.{content_hash(attrs_body)}.json"
        files[name] = body
        files[attrs_name] = attrs_body
        datasets[kind] = {
            "path": PATH_PREFIX + name, "attributesPath": PATH_PREFIX + attrs_name,
            "bytes": len(body), "featureCount": len(collections[kind]["features"]),
        }
    pressure_body = dumps_compact(pressure)
    pressure_name = f"pressure.{content_hash(pressure_body)}.json"
    files[pressure_name] = pressure_body
    datasets["pressure"] = {
        "path": PATH_PREFIX + pressure_name, "bytes": len(pressure_body),
        "cellCount": len(pressure["cells"]["q"]),
    }
    manifest = {"schemaVersion": SCHEMA_VERSION, "generatedAt": generated_at,
                "datasets": datasets, "sources": sources}
    manifest_body = dumps_compact(manifest)

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        atomic_write_bytes(output_dir / name, body)
    atomic_write_bytes(output_dir / MANIFEST_NAME, manifest_body)

    for entry in output_dir.iterdir():
        if entry.name == LEGACY_BUNDLE or (HASHED_FILE.fullmatch(entry.name) and entry.name not in files):
            if entry.is_file() or entry.is_symlink():
                entry.unlink(missing_ok=True)
    return manifest
