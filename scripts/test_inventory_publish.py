"""Offline coverage for inventory meaning, the published file layout and the HTTP cache."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from porto_data.common import DataError, Fetcher, atomic_write_bytes, content_hash, dumps_compact, round_coords
from porto_data.inventory import (
    SOURCES,
    build_inventory,
    normalize_collection,
    normalize_with_attributes,
    reference_date,
    source_urls,
)
from porto_data.publish import HASHED_FILE, publish


POINT = {"type": "Point", "coordinates": [-8.61, 41.15]}
RING = [[-8.62, 41.15], [-8.61, 41.15], [-8.61, 41.16], [-8.62, 41.15]]
LINE = {"type": "LineString", "coordinates": RING[:2]}
POLYGON = {"type": "Polygon", "coordinates": [RING]}


def collection(properties, geometry=POINT):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"objectid": 1, **properties}, "geometry": deepcopy(geometry)},
    ]}


def metadata(spec, license_id="cc-zero"):
    return {"success": True, "result": {
        "id": spec["dataset"], "license_id": license_id,
        "resources": [{"id": spec["resource"], "format": "GeoJSON", "reference_date": "2022-12-16"}],
    }}


def normalized_properties(payload, kind):
    return normalize_collection(payload, kind)["features"][0]["properties"]


def source_payloads(extra_attrs=None, rate=0.4):
    """Valid upstream payloads for all four inventory sources, keyed by URL."""
    geometries = {"streets": LINE, "zones": POLYGON, "spaces": POINT, "garages": POINT}
    properties = {
        "streets": {"tarifado": "Sim", "toponimo": "Rua A"},
        "zones": {"zona": "IV", "valor_taxa": rate},
        "spaces": {"estado": None},
        "garages": {"designacao": "Trindade", "nº_lugares_ligeiros": 292},
    }
    payloads = {}
    for spec in SOURCES:
        url, metadata_url = source_urls(spec)
        payloads[metadata_url] = metadata(spec)
        attrs = {**properties[spec["id"]], **(extra_attrs or {}).get(spec["id"], {})}
        payloads[url] = collection(attrs, geometries[spec["id"]])
    return payloads


class FakeFetcher:
    def __init__(self, payloads):
        self.payloads = payloads

    def get_json(self, url, **kwargs):
        return self.payloads[url]


def built_inventory(**kwargs):
    collections, attributes, sources = build_inventory(FakeFetcher(source_payloads(**kwargs)))
    return collections, attributes, sources


PRESSURE = {"schemaVersion": 2, "cells": {"q": [0, 1], "r": [0, 0]}}


def publish_into(directory, pressure=PRESSURE, **kwargs):
    collections, attributes, sources = built_inventory(**kwargs)
    return publish(Path(directory), generated_at="2026-09-29T12:00:00Z", collections=collections,
                   attributes=attributes, pressure=pressure, sources=sources)


class NormalizationTests(unittest.TestCase):
    def test_missing_space_status_is_unknown_not_active_and_resident_zone_is_not_tariff(self):
        payload = collection({"toponimo": None, "estado": None, "num_zona": 66})
        props = normalized_properties(payload, "spaces")
        self.assertEqual(props["status"], "unknown")
        self.assertEqual(props["residentZone"], "66")
        self.assertIsNone(props["name"])
        self.assertNotIn("zone", props)
        _, attributes = normalize_with_attributes(payload, "spaces")
        self.assertIsNone(attributes["spaces:1"]["estado"])

    def test_inactive_space_is_preserved(self):
        props = normalized_properties(collection({"estado": "Inativo", "num_zona": None}), "spaces")
        self.assertEqual(props["status"], "inactive")
        self.assertIsNone(props["residentZone"])

    def test_unrecognized_status_cannot_silently_become_active(self):
        with self.assertRaisesRegex(DataError, "Unsupported inventory status"):
            normalize_collection(collection({"estado": "Ocupado"}), "spaces")

    def test_garage_category_is_not_total_and_missing_capacity_is_not_zero(self):
        attrs = {"designacao": "Trindade", "nº_lugares_ligeiros": 292,
                 "nº_lugares_veiculos_eletricos": 45, "nº_lugares_mobilidade_reduzida": 5}
        payload = collection(attrs)
        props = normalized_properties(payload, "garages")
        self.assertEqual(props["lightVehicleCapacity"], 292)
        self.assertNotIn("totalCapacity", props)
        self.assertNotIn("nº_lugares_veiculos_eletricos", props)
        _, attributes = normalize_with_attributes(payload, "garages")
        self.assertEqual(attributes["garages:1"]["nº_lugares_veiculos_eletricos"], 45)
        self.assertIsNone(normalized_properties(collection({}), "garages")["lightVehicleCapacity"])
        self.assertEqual(normalized_properties(collection({"nº_lugares_ligeiros": 0}), "garages")["lightVehicleCapacity"], 0)

    def test_invalid_category_counts_are_rejected_even_outside_light_vehicles(self):
        for value in (-1, 1.5, True, "45", float("nan")):
            with self.subTest(value=value), self.assertRaises(DataError):
                normalize_collection(collection({"nº_lugares_veiculos_eletricos": value}), "garages")

    def test_tariff_multipolygon_and_missing_rate_are_preserved(self):
        geometry = {"type": "MultiPolygon", "coordinates": [[RING], [RING]]}
        result = normalize_collection(collection({"zona": "IV", "valor_taxa": None}, geometry), "zones")
        self.assertEqual(result["features"][0]["geometry"], geometry)
        self.assertEqual(result["features"][0]["properties"]["name"], "Zone IV")
        self.assertIsNone(result["features"][0]["properties"]["hourlyRate"])

    def test_tariff_rate_rejects_negative_nonfinite_and_text_values(self):
        for rate in (-0.4, float("inf"), "0.40", True):
            with self.subTest(rate=rate), self.assertRaises(DataError):
                normalize_collection(collection({"zona": "IV", "valor_taxa": rate}, POLYGON), "zones")
        self.assertEqual(normalized_properties(collection({"zona": "I", "valor_taxa": 1.2}, POLYGON), "zones")["hourlyRate"], 1.2)
        with self.assertRaisesRegex(DataError, "Unsupported tariff zone"):
            normalize_collection(collection({"zona": "66", "valor_taxa": 0.4}, POLYGON), "zones")

    def test_paid_street_must_still_be_tariffed(self):
        with self.assertRaisesRegex(DataError, "tarifado"):
            normalize_collection(collection({"tarifado": "Não"}, LINE), "streets")

    def test_wrong_geometry_projected_swapped_and_nonfinite_coordinates_rejected(self):
        for coordinates in ([41.15, -8.61], [10000, 20000], [-8.61, float("nan")], [True, 41.15], [-9.14, 38.72]):
            with self.subTest(coordinates=coordinates), self.assertRaises(DataError):
                normalize_collection(collection({}, {"type": "Point", "coordinates": coordinates}), "garages")
        with self.assertRaisesRegex(DataError, "geometry"):
            normalize_collection(collection({}, {"type": "LineString", "coordinates": RING}), "garages")

    def test_unclosed_and_degenerate_polygon_rings_rejected(self):
        for ring in (RING[:-1], RING[:-1] + [[-8.63, 41.15]], [RING[0]] * 4):
            with self.subTest(ring=ring), self.assertRaises(DataError):
                normalize_collection(collection({"zona": "I"}, {"type": "Polygon", "coordinates": [ring]}), "zones")

    def test_explicit_projected_crs_is_rejected_even_with_plausible_coordinates(self):
        payload = collection({})
        payload["crs"] = {"type": "name", "properties": {"name": "EPSG:3763"}}
        with self.assertRaisesRegex(DataError, "CRS"):
            normalize_collection(payload, "garages")

    def test_missing_invalid_and_duplicate_ids_rejected(self):
        for value in (None, True, 0, -1, "1", 1.5):
            with self.subTest(value=value), self.assertRaisesRegex(DataError, "objectid"):
                normalize_collection(collection({"objectid": value}), "garages")
        payload = collection({})
        payload["features"].append(deepcopy(payload["features"][0]))
        with self.assertRaisesRegex(DataError, "Duplicate objectid"):
            normalize_collection(payload, "garages")

    def test_empty_collection_cannot_replace_inventory(self):
        with self.assertRaisesRegex(DataError, "empty replacement"):
            normalize_collection({"type": "FeatureCollection", "features": []}, "garages")

    def test_features_are_sorted_by_objectid(self):
        payload = collection({})
        payload["features"].append({"type": "Feature", "properties": {"objectid": 3}, "geometry": deepcopy(POINT)})
        payload["features"].append({"type": "Feature", "properties": {"objectid": 2}, "geometry": deepcopy(POINT)})
        result = normalize_collection(payload, "garages")
        self.assertEqual([f["properties"]["id"] for f in result["features"]], ["garages:1", "garages:2", "garages:3"])


class CompactShapeTests(unittest.TestCase):
    EXPECTED_KEYS = {
        "streets": {"id", "kind", "name"},
        "zones": {"id", "kind", "name", "zone", "hourlyRate"},
        "spaces": {"id", "kind", "name", "status", "residentZone"},
        "garages": {"id", "kind", "name", "address", "operator", "openingHours", "lightVehicleCapacity"},
    }

    def test_features_carry_only_render_properties_and_no_feature_id(self):
        collections, _, _ = built_inventory(extra_attrs={kind: {"secret_column": "x"} for kind in self.EXPECTED_KEYS})
        for kind, expected in self.EXPECTED_KEYS.items():
            feature = collections[kind]["features"][0]
            with self.subTest(kind=kind):
                self.assertNotIn("id", feature)
                self.assertEqual(set(feature["properties"]), expected)
                self.assertEqual(feature["properties"]["kind"], kind)

    def test_attribute_tables_are_keyed_by_feature_id_with_original_attributes(self):
        collections, attributes, _ = built_inventory(extra_attrs={"garages": {"nº_lugares_veiculos_eletricos": 45}})
        for kind, collection_ in collections.items():
            ids = [f["properties"]["id"] for f in collection_["features"]]
            self.assertEqual(sorted(attributes[kind]), sorted(ids))
        self.assertEqual(attributes["garages"]["garages:1"], {
            "objectid": 1, "designacao": "Trindade", "nº_lugares_ligeiros": 292, "nº_lugares_veiculos_eletricos": 45})

    def test_coordinates_are_rounded_to_six_decimals(self):
        point = {"type": "Point", "coordinates": [-8.610000123456, 41.150000987654]}
        geometry = normalize_collection(collection({}, point), "garages")["features"][0]["geometry"]
        self.assertEqual(geometry["coordinates"], [-8.610000, 41.150001])

    def test_consecutive_duplicates_after_rounding_are_removed_while_geometry_stays_valid(self):
        line = {"type": "LineString", "coordinates": [[-8.6100001, 41.15], [-8.6100002, 41.15], [-8.60, 41.15]]}
        coordinates = normalize_collection(collection({"tarifado": "Sim"}, line), "streets")["features"][0]["geometry"]["coordinates"]
        self.assertEqual(coordinates, [[-8.61, 41.15], [-8.60, 41.15]])
        ring = [[-8.62, 41.15], [-8.6100001, 41.15], [-8.6100002, 41.15], [-8.61, 41.16], [-8.62, 41.15]]
        geometry = {"type": "Polygon", "coordinates": [ring]}
        result = normalize_collection(collection({"zona": "I"}, geometry), "zones")["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(result, [[-8.62, 41.15], [-8.61, 41.15], [-8.61, 41.16], [-8.62, 41.15]])

    def test_dedupe_never_produces_an_invalid_geometry(self):
        # A line collapsing to a single rounded position must stay a 2-position line.
        line = {"type": "LineString", "coordinates": [[-8.6100001, 41.15], [-8.6100002, 41.15]]}
        coordinates = normalize_collection(collection({"tarifado": "Sim"}, line), "streets")["features"][0]["geometry"]["coordinates"]
        self.assertGreaterEqual(len(coordinates), 2)
        # A ring that would drop below three distinct positions keeps its source coordinates.
        ring = [[-8.62, 41.15], [-8.61, 41.15], [-8.6100001, 41.15], [-8.62, 41.15]]
        result = normalize_collection(collection({"zona": "I"}, {"type": "Polygon", "coordinates": [ring]}), "zones")
        self.assertEqual(result["features"][0]["geometry"]["coordinates"], [ring])


class VerificationTests(unittest.TestCase):
    def test_license_and_reference_date_are_verified_not_assumed(self):
        spec = SOURCES[-1]
        with self.assertRaisesRegex(DataError, "CC0 not verified"):
            reference_date(metadata(spec, "other-open"), spec)
        payload = metadata(spec)
        payload["result"]["resources"][0]["reference_date"] = "2022-02-30"
        with self.assertRaisesRegex(DataError, "reference_date"):
            reference_date(payload, spec)

    def test_source_records_use_record_count_and_inventory_group(self):
        _, _, sources = built_inventory()
        self.assertEqual([s["id"] for s in sources], [spec["id"] for spec in SOURCES])
        for record in sources:
            self.assertEqual(record["group"], "inventory")
            self.assertEqual(record["recordCount"], 1)
            self.assertEqual(record["referenceDate"], "2022-12-16")
            self.assertEqual(record["license"], "CC0-1.0")
            self.assertNotIn("featureCount", record)

    def test_late_source_failure_aborts_the_whole_inventory(self):
        payloads = source_payloads()
        payloads[source_urls(SOURCES[-1])[1]] = metadata(SOURCES[-1], "restricted")
        with self.assertRaisesRegex(DataError, "garages.*CC0"):
            build_inventory(FakeFetcher(payloads))


class PublishTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def names(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_manifest_references_existing_hashed_files_matching_their_content(self):
        manifest = publish_into(self.dir)
        self.assertEqual(json.loads((self.dir / "manifest.json").read_text()), manifest)
        self.assertEqual(manifest["schemaVersion"], 2)
        self.assertEqual(set(manifest["datasets"]), {"zones", "streets", "spaces", "garages", "pressure"})
        for name, info in manifest["datasets"].items():
            paths = [info["path"]] + ([info["attributesPath"]] if "attributesPath" in info else [])
            for path in paths:
                self.assertTrue(path.startswith("data/"))
                file = self.dir / path.removeprefix("data/")
                self.assertRegex(file.name, HASHED_FILE)
                self.assertEqual(file.stem.split(".")[-1], content_hash(file.read_bytes()))
            self.assertEqual((self.dir / info["path"].removeprefix("data/")).stat().st_size, info["bytes"])
        self.assertEqual(manifest["datasets"]["zones"]["featureCount"], 1)
        self.assertEqual(manifest["datasets"]["pressure"]["cellCount"], 2)
        # manifest + 4 datasets + 4 attribute tables + pressure
        self.assertEqual(len(self.names()), 10)

    def test_hashed_names_change_if_and_only_if_content_changes(self):
        first = publish_into(self.dir)
        again = publish_into(self.dir)
        self.assertEqual(first["datasets"], again["datasets"])

        # Only an original attribute changes: the compact collection keeps its name.
        attrs_only = publish_into(self.dir, extra_attrs={"zones": {"obs": "x"}})
        self.assertEqual(attrs_only["datasets"]["zones"]["path"], first["datasets"]["zones"]["path"])
        self.assertNotEqual(attrs_only["datasets"]["zones"]["attributesPath"], first["datasets"]["zones"]["attributesPath"])

        changed = publish_into(self.dir, rate=0.5)
        self.assertNotEqual(changed["datasets"]["zones"]["path"], first["datasets"]["zones"]["path"])
        for kind in ("streets", "spaces", "garages", "pressure"):
            self.assertEqual(changed["datasets"][kind]["path"], first["datasets"][kind]["path"])

    def test_stale_hashed_files_and_legacy_bundle_are_pruned_and_unrelated_files_kept(self):
        publish_into(self.dir)
        old = publish_into(self.dir, rate=0.5)
        stale = [
            "zones.0000000000.json", "pressure.attrs.ffffffffff.json", "porto-parking.json",
            old["datasets"]["zones"]["path"].removeprefix("data/"),
        ]
        for name in stale[:3]:
            (self.dir / name).write_text("{}")
        keep = ["notes.txt", "zones.json", "zones.abc.json", "zones.0123456789.json.bak",
                "other.0123456789.json", "zones.ABCDEF0123.json", "zones.attrs.attrs.0123456789.json"]
        for name in keep:
            (self.dir / name).write_text("keep")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "zones.0123456789.json").write_text("keep")

        new = publish_into(self.dir)
        referenced = {p.removeprefix("data/") for info in new["datasets"].values()
                      for p in (info["path"], info.get("attributesPath")) if p}
        for name in stale:
            if name not in referenced:
                self.assertFalse((self.dir / name).exists(), name)
        for name in keep:
            self.assertEqual((self.dir / name).read_text(), "keep", name)
        self.assertEqual((self.dir / "sub" / "zones.0123456789.json").read_text(), "keep")
        for name in referenced:
            self.assertTrue((self.dir / name).is_file())
        self.assertEqual(set(self.names()), referenced | {"manifest.json", "sub"} | set(keep))

    def test_failure_before_manifest_leaves_previous_manifest_and_its_files_intact(self):
        publish_into(self.dir)
        before = {name: (self.dir / name).read_bytes() for name in self.names()}
        real = atomic_write_bytes

        def fail_on_manifest(path, data):
            if Path(path).name == "manifest.json":
                raise OSError("disk full")
            real(path, data)

        with patch("porto_data.publish.atomic_write_bytes", side_effect=fail_on_manifest):
            with self.assertRaisesRegex(OSError, "disk full"):
                publish_into(self.dir, rate=0.9)
        self.assertEqual((self.dir / "manifest.json").read_bytes(), before["manifest.json"])
        for name, content in before.items():
            self.assertEqual((self.dir / name).read_bytes(), content)
        self.assertFalse([n for n in self.names() if n.endswith(".tmp")])

    def test_invalid_inputs_write_nothing(self):
        publish_into(self.dir)
        before = {name: (self.dir / name).read_bytes() for name in self.names()}
        collections, attributes, sources = built_inventory(rate=0.9)
        base = dict(generated_at="t", collections=collections, attributes=attributes, pressure=PRESSURE, sources=sources)
        missing_kind = {k: v for k, v in collections.items() if k != "garages"}
        empty_zones = {**collections, "zones": {"type": "FeatureCollection", "features": []}}
        mismatched = {**attributes, "spaces": {}}
        cases = {
            "missing kind": {**base, "collections": missing_kind},
            "empty collection": {**base, "collections": empty_zones},
            "attribute mismatch": {**base, "attributes": mismatched},
            "no cells": {**base, "pressure": {"schemaVersion": 2}},
            "no sources": {**base, "sources": []},
            "non-finite pressure": {**base, "pressure": {"cells": {"q": [0], "v": [float("nan")]}}},
        }
        for label, kwargs in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                publish(self.dir, **kwargs)
            self.assertEqual({name: (self.dir / name).read_bytes() for name in self.names()}, before, label)

    def test_validation_failure_does_not_create_the_output_directory(self):
        target = self.dir / "fresh"
        collections, attributes, sources = built_inventory()
        with self.assertRaises(DataError):
            publish(target, generated_at="t", collections=collections, attributes=attributes,
                    pressure={"schemaVersion": 2}, sources=sources)
        self.assertFalse(target.exists())


class SerializationTests(unittest.TestCase):
    def test_round_coords_rounds_nested_floats_only(self):
        self.assertEqual(round_coords([[1.23456789, 2], [[3.9999999, -0.0000004]]]), [[1.234568, 2], [[4.0, -0.0]]])

    def test_dumps_compact_is_compact_utf8_and_rejects_non_finite(self):
        self.assertEqual(dumps_compact({"a": [1, "nº"]}), '{"a":[1,"nº"]}\n'.encode("utf-8"))
        with self.assertRaises(ValueError):
            dumps_compact({"a": float("nan")})

    def test_atomic_write_replaces_and_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data.json"
            atomic_write_bytes(target, b"one")
            self.assertEqual(target.read_bytes(), b"one")
            self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            with patch("porto_data.common.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    atomic_write_bytes(target, b"two")
            self.assertEqual(target.read_bytes(), b"one")
            self.assertEqual(list(target.parent.iterdir()), [target])


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


class FakeOpener:
    """Replays a scripted list of results: bytes are responses, exceptions are raised."""

    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


def http_error(code):
    return urllib.error.HTTPError("https://example.test/x", code, "err", {}, None)


class FetcherTests(unittest.TestCase):
    URL = "https://example.test/data.json"

    def make(self, *results, **kwargs):
        self.sleeps = []
        self.opener = FakeOpener(*results)
        return Fetcher(opener=self.opener, sleep=self.sleeps.append, **kwargs)

    def test_transient_failures_are_retried_with_exponential_backoff_then_succeed(self):
        fetcher = self.make(urllib.error.URLError("down"), http_error(503), http_error(429), b'{"ok":true}')
        self.assertEqual(fetcher.get_json(self.URL), {"ok": True})
        self.assertEqual(self.sleeps, [2, 4, 8])
        self.assertEqual(len(self.opener.requests), 4)

    def test_timeouts_are_retried_and_exhaustion_raises_data_error(self):
        fetcher = self.make(*[TimeoutError("slow")] * 4)
        with self.assertRaisesRegex(DataError, "after 4 attempts"):
            fetcher.get_bytes(self.URL)
        self.assertEqual(self.sleeps, [2, 4, 8])

    def test_other_http_errors_fail_immediately(self):
        fetcher = self.make(http_error(404), b"unused")
        with self.assertRaisesRegex(DataError, "HTTP 404"):
            fetcher.get_bytes(self.URL)
        self.assertEqual(self.sleeps, [])
        self.assertEqual(len(self.opener.requests), 1)

    def test_body_selects_post_and_changes_cache_key(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher = self.make(b"get", b"post-a", b"post-b", cache_dir=Path(directory))
            fetcher.get_bytes(self.URL)
            fetcher.get_bytes(self.URL, data=b"query=a")
            fetcher.get_bytes(self.URL, data=b"query=b")
            self.assertEqual([r.get_method() for r in self.opener.requests], ["GET", "POST", "POST"])
            self.assertEqual(self.opener.requests[1].get_header("Content-type"), "application/x-www-form-urlencoded")
            self.assertEqual(len(list(Path(directory).glob("*.bin"))), 3)
            self.assertEqual(len(list(Path(directory).glob("*.url"))), 3)

    def test_offline_reads_cache_and_misses_raise(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make(b'{"cached":1}', cache_dir=Path(directory)).get_bytes(self.URL)
            offline = self.make(offline=True, cache_dir=Path(directory))
            self.assertEqual(offline.get_json(self.URL), {"cached": 1})
            with self.assertRaisesRegex(DataError, "Offline"):
                offline.get_bytes("https://example.test/other.json")
            with self.assertRaisesRegex(DataError, "Offline"):
                offline.get_bytes(self.URL, data=b"different body")
            self.assertEqual(self.opener.requests, [])
        with self.assertRaisesRegex(DataError, "Offline"):
            self.make(offline=True).get_bytes(self.URL)

    def test_online_fetch_does_not_reuse_cache_but_rewrites_it(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make(b"old", cache_dir=Path(directory)).get_bytes(self.URL)
            fresh = self.make(b"new", cache_dir=Path(directory))
            self.assertEqual(fresh.get_bytes(self.URL), b"new")
            self.assertEqual(len(self.opener.requests), 1)
            self.assertEqual(self.make(offline=True, cache_dir=Path(directory)).get_bytes(self.URL), b"new")

    def test_get_json_rejects_non_finite_and_invalid_json(self):
        for body in (b'{"a": NaN}', b'{"a": Infinity}', b'{"a": 1e999}', b"not json", b"\xff\xfe"):
            with self.subTest(body=body), self.assertRaises(DataError):
                self.make(body).get_json(self.URL)
        self.assertEqual(self.make(b'\xef\xbb\xbf{"a": 1.5}').get_json(self.URL), {"a": 1.5})


if __name__ == "__main__":
    unittest.main()
