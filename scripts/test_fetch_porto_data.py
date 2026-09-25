"""Offline regression coverage for inventory meaning and publication boundaries."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fetch_porto_data import (
    DataError,
    SOURCES,
    normalize_collection,
    reference_date,
    refresh,
    source_urls,
    write_snapshot,
)


POINT = {"type": "Point", "coordinates": [-8.61, 41.15]}
RING = [[-8.62, 41.15], [-8.61, 41.15], [-8.61, 41.16], [-8.62, 41.15]]


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


class NormalizationTests(unittest.TestCase):
    def test_missing_space_status_is_unknown_not_active_and_resident_zone_is_not_tariff(self):
        payload = collection({"toponimo": None, "estado": None, "num_zona": 66})
        props = normalized_properties(payload, "spaces")
        self.assertEqual(props["status"], "unknown")
        self.assertEqual(props["residentZone"], "66")
        self.assertIsNone(props["name"])
        self.assertIsNone(props["attributes"]["estado"])
        self.assertNotIn("zone", props)

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
        props = normalized_properties(collection(attrs), "garages")
        self.assertEqual(props["lightVehicleCapacity"], 292)
        self.assertEqual(props["attributes"]["nº_lugares_veiculos_eletricos"], 45)
        self.assertNotIn("totalCapacity", props)
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
        geometry = {"type": "Polygon", "coordinates": [RING]}
        for rate in (-0.4, float("inf"), "0.40", True):
            with self.subTest(rate=rate), self.assertRaises(DataError):
                normalize_collection(collection({"zona": "IV", "valor_taxa": rate}, geometry), "zones")
        self.assertEqual(normalized_properties(collection({"zona": "I", "valor_taxa": 1.2}, geometry), "zones")["hourlyRate"], 1.2)
        with self.assertRaisesRegex(DataError, "Unsupported tariff zone"):
            normalize_collection(collection({"zona": "66", "valor_taxa": 0.4}, geometry), "zones")

    def test_paid_street_must_still_be_tariffed(self):
        geometry = {"type": "LineString", "coordinates": RING[:2]}
        with self.assertRaisesRegex(DataError, "tarifado"):
            normalize_collection(collection({"tarifado": "Não"}, geometry), "streets")

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


class PublicationTests(unittest.TestCase):
    def test_license_and_reference_date_are_verified_not_assumed(self):
        spec = SOURCES[-1]
        with self.assertRaisesRegex(DataError, "CC0 not verified"):
            reference_date(metadata(spec, "other-open"), spec)
        payload = metadata(spec)
        payload["result"]["resources"][0]["reference_date"] = "2022-02-30"
        with self.assertRaisesRegex(DataError, "reference_date"):
            reference_date(payload, spec)

    def test_late_source_failure_keeps_good_snapshot_byte_for_byte(self):
        # The first three sources succeed; a changed fourth-source license aborts
        # the entire publication, rather than mixing generations or partial data.
        payloads = {}
        geometries = [
            {"type": "LineString", "coordinates": RING[:2]},
            {"type": "Polygon", "coordinates": [RING]}, POINT,
        ]
        properties = [{"tarifado": "Sim"}, {"zona": "IV", "valor_taxa": 0.4}, {"estado": None}]
        for spec, geometry, attrs in zip(SOURCES, geometries, properties):
            url, metadata_url = source_urls(spec)
            payloads[metadata_url] = metadata(spec)
            payloads[url] = collection(attrs, geometry)
        payloads[source_urls(SOURCES[-1])[1]] = metadata(SOURCES[-1], "restricted")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot.json"
            original = b'{"last":"known good"}\n'
            output.write_bytes(original)
            with self.assertRaisesRegex(DataError, "garages.*CC0"):
                refresh(output, fetch=payloads.__getitem__)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_serialization_and_replace_failures_preserve_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot.json"
            output.write_text('{"previous":true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                write_snapshot({"bad": float("nan")}, output)
            self.assertEqual(json.loads(output.read_text()), {"previous": True})
            with patch("fetch_porto_data.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    write_snapshot({"next": True}, output)
            self.assertEqual(json.loads(output.read_text()), {"previous": True})
            self.assertEqual(list(output.parent.iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
