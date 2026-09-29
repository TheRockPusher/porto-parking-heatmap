import json
import math
import unittest

from porto_data import geo
from porto_data import pressure as pr
from porto_data import pressure_sources as src

X0, Y0 = -41000.0, 165000.0  # TM06 metres, central Porto
SIZE = 900.0


def square(x, y, size):
    return [[(x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)]]


def census(households=1000, with_parking=400, x=X0, y=Y0, size=SIZE):
    return {"polygons": [square(x, y, size)], "households": households, "withParking": with_parking}


def lonlat(dx, dy):
    return geo.tm06_to_wgs84(X0 + dx, Y0 + dy)


def road(dy, tags=None, x_from=100.0, x_to=800.0):
    base = {"highway": "residential"}
    base.update(tags or {})
    return {"coords": [list(lonlat(x_from, dy)), list(lonlat(x_to, dy))], "tags": base}


def poi(dx, dy, tags):
    lon, lat = lonlat(dx, dy)
    return {"lon": lon, "lat": lat, "tags": tags}


def compute(osm=None, censuses=None, restrictions=(), complaints=(), inventory=None):
    osm = {"roads": [], "parking": [], "pois": [], **(osm or {})}
    return pr.compute_pressure(censuses or [census()], osm, list(restrictions), list(complaints), inventory or {})


def col(dataset, name):
    return dataset["cells"][name]


class PercentileTests(unittest.TestCase):
    def test_ties_use_average_ranks_and_none_is_preserved(self):
        self.assertEqual(pr.percentile_index([1.0, 2.0, 2.0, 3.0]), [0, 50, 50, 100])
        self.assertEqual(pr.percentile_index([5.0, None, 1.0]), [100, None, 0])

    def test_single_eligible_cell_is_fifty_and_all_equal_ties_middle(self):
        self.assertEqual(pr.percentile_index([None, 7.0]), [None, 50])
        self.assertEqual(pr.percentile_index([3.0, 3.0, 3.0]), [50, 50, 50])
        self.assertEqual(pr.percentile_index([None, None]), [None, None])


class SupplyTests(unittest.TestCase):
    def test_calibration_distributes_the_pdm_total_over_scope(self):
        data = compute({"roads": [road(300), road(600, {"highway": "tertiary"})]})
        total = sum(col(data, "onStreetEstimate"))
        self.assertAlmostEqual(total, 64680, delta=0.05 * len(col(data, "q")) + 0.1)

    def test_roads_outside_scope_and_ineligible_classes_are_ignored(self):
        base = compute({"roads": [road(300)]})
        far = {"coords": [list(lonlat(100 + 6000, 300)), list(lonlat(800 + 6000, 300))],
               "tags": {"highway": "residential"}}
        extra = [far, road(500, {"highway": "motorway"}), road(500, {"area": "yes"}),
                 road(500, {"tunnel": "yes"}), road(500, {"bridge": "viaduct"}), road(500, {"access": "private"})]
        self.assertEqual(compute({"roads": [road(300)] + extra})["cells"], base["cells"])

    def test_parking_side_tags_remove_supply(self):
        def length(*roads):
            return sum(col(compute({"roads": list(roads)}), "roadLengthM"))

        full = length(road(300))
        self.assertAlmostEqual(full, 700, delta=15)
        self.assertEqual(length(road(300), road(600, {"parking:both": "no"})), full)
        self.assertAlmostEqual(length(road(300, {"parking:left": "no"})), full / 2, delta=15)
        self.assertEqual(length(road(300, {"parking:left": "no", "parking:right": "no_stopping"})), 0)
        self.assertAlmostEqual(length(road(300, {"parking:both": "yes", "parking:left": "separate"})), full / 2, delta=15)

    def test_cells_without_enough_supply_have_null_ratio_and_index_never_zero(self):
        data = compute({"roads": [road(300)], "pois": [poi(450, 700, {"shop": "yes"})]})
        cells = data["cells"]
        eligible = 0
        for i, supply in enumerate(cells["onStreetEstimate"]):
            if supply < 5:
                self.assertIsNone(cells["overnightRatio"][i])
                self.assertIsNone(cells["overnightIndex"][i])
                if supply + cells["offStreetPublic"][i] < 5:
                    self.assertIsNone(cells["daytimeRatio"][i])
                    self.assertIsNone(cells["daytimeIndex"][i])
            else:
                eligible += 1
                self.assertIsNotNone(cells["overnightIndex"][i])
        self.assertGreater(eligible, 0)
        self.assertLess(eligible, len(cells["q"]))


class OffStreetTests(unittest.TestCase):
    def parking(self, dx, dy, **tags):
        item = poi(dx, dy, {"amenity": "parking", **tags})
        return item

    def test_private_permit_and_uncapacitated_parking_are_excluded_customers_included(self):
        parking = [
            self.parking(200, 200, capacity="100"),
            self.parking(300, 200, capacity="50", access="customers"),
            self.parking(400, 200, capacity="40", access="private"),
            self.parking(500, 200, capacity="30", access="permit"),
            self.parking(600, 200, capacity="20", access="no"),
            self.parking(700, 200, capacity="20", parking="garage_boxes"),
            self.parking(700, 300, capacity="0"),
            self.parking(700, 400, capacity="many"),
            self.parking(700, 500),
        ]
        data = compute({"parking": parking})
        self.assertEqual(sum(col(data, "offStreetPublic")), 150)

    def test_municipal_garage_counts_only_when_no_osm_car_park_within_100m(self):
        osm_lot = self.parking(300, 300, capacity="80")
        near = lonlat(300 + 60, 300)
        far = lonlat(700, 700)
        garages = {"features": [
            {"geometry": {"type": "Point", "coordinates": list(near)}, "properties": {"lightVehicleCapacity": 30}},
            {"geometry": {"type": "Point", "coordinates": list(far)}, "properties": {"lightVehicleCapacity": 45}},
            {"geometry": {"type": "Point", "coordinates": list(far)}, "properties": {"lightVehicleCapacity": None}},
        ]}
        data = compute({"parking": [osm_lot]}, inventory={"garages": garages})
        self.assertEqual(sum(col(data, "offStreetPublic")), 80 + 45)
        # a private OSM car park does not shadow the garage
        private = self.parking(300, 300, capacity="80", access="private")
        data = compute({"parking": [private]}, inventory={"garages": {"features": garages["features"][:1]}})
        self.assertEqual(sum(col(data, "offStreetPublic")), 30)


class AttractionTests(unittest.TestCase):
    def test_feature_counts_once_with_highest_weight(self):
        tags = {"amenity": "hospital", "office": "yes", "shop": "medical"}
        self.assertEqual(pr.poi_weight(tags), 10.0)
        self.assertEqual(pr.poi_weight({"shop": "x", "amenity": "cafe"}), 1.0)
        self.assertEqual(pr.poi_weight({"amenity": "bench"}), 0.0)
        data = compute({"pois": [poi(300, 300, tags), poi(300, 300, {"office": "it"}),
                                 poi(300, 300, {"amenity": "bench"})]})
        self.assertEqual(sum(col(data, "attraction")), 13.0)


class ComplaintTests(unittest.TestCase):
    def occurrence(self, code, lon=-8.61, lat=41.15, extra=None):
        return {"service_type": {"service_code": code, "name": "text"},
                "location": {"geographic": {"coordinates": [lon, lat]}, "address": "Rua X"},
                "timeline": {"requested_datetime": "2026-01-02T10:00:00+00:00"},
                "photos": ["p.jpg"], "description": "secret", "id": 99, **(extra or {})}

    def test_only_listed_codes_are_kept_and_no_other_fields_survive(self):
        payload = {"Total": 3, "Occurrences": [
            self.occurrence("C060901GO"), self.occurrence("C000000GO"), self.occurrence("C061100GO")]}
        records, dropped = src.parse_complaints(payload)
        self.assertEqual([r["code"] for r in records], ["C060901GO", "C061100GO"])
        self.assertEqual(dropped, 0)
        for record in records:
            self.assertEqual(set(record), {"code", "lon", "lat", "requested"})
        self.assertEqual(records[0]["requested"], "2026-01-02T10:00:00Z")

    def test_coordinates_outside_porto_are_dropped_and_counted(self):
        payload = {"Occurrences": [self.occurrence("C060802GO", lon=-9.14, lat=38.72),
                                   self.occurrence("C060802GO", lon=-8.61, lat=41.15)]}
        records, dropped = src.parse_complaints(payload)
        self.assertEqual((len(records), dropped), (1, 1))

    def test_complaints_are_counted_per_cell_with_window(self):
        lon, lat = lonlat(300, 300)
        records = [{"code": "C060901GO", "lon": lon, "lat": lat, "requested": "2026-03-01T00:00:00Z"},
                   {"code": "C060802GO", "lon": lon, "lat": lat, "requested": "2025-09-01T00:00:00Z"},
                   {"code": "OTHER", "lon": lon, "lat": lat, "requested": "2020-01-01T00:00:00Z"}]
        data = compute(complaints=records)
        self.assertEqual(sum(col(data, "complaints")), 2)
        self.assertEqual(data["method"]["complaintWindow"], ["2025-09-01T00:00:00Z", "2026-03-01T00:00:00Z"])
        self.assertIsNone(compute()["method"]["complaintWindow"])


class RestrictionTests(unittest.TestCase):
    def feature(self, kind="Estacionamento", start=1_600_000_000_000, days=10.0, lon=-8.61, lat=41.15):
        props = {"tipo_de_condicionamento": kind, "data_de_inicio": start,
                 "data_de_fim": None if days is None else start + int(days * 86_400_000)}
        return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [lon, lat]}}

    def test_durations_are_capped_and_invalid_entries_skipped(self):
        payload = {"features": [
            self.feature(days=10),
            self.feature(days=1000),
            self.feature(days=None),
            self.feature(days=-5),
            self.feature(kind="Obras"),
            self.feature(kind="ESTACIONAMENTO", days=2),
            self.feature(kind="Estacionamento", days=1, lon=-9.14, lat=38.72),
        ]}
        records = src.parse_restrictions(payload)
        self.assertEqual([round(r["days"], 3) for r in records], [10.0, 366.0, 2.0])

    def test_accented_type_matches_after_folding(self):
        payload = {"features": [self.feature(kind="  Estacionamento ")]}
        self.assertEqual(len(src.parse_restrictions(payload)), 1)

    def test_restriction_days_are_summed_per_cell_with_window(self):
        lon, lat = lonlat(300, 300)
        rows = [{"lon": lon, "lat": lat, "days": 4.0, "start": "2020-01-01", "end": "2020-01-05"},
                {"lon": lon, "lat": lat, "days": 6.5, "start": "2019-03-21", "end": "2024-09-24"}]
        data = compute(restrictions=rows)
        self.assertEqual(sum(col(data, "restrictionDays")), 10.5)
        self.assertEqual(data["method"]["restrictionsWindow"], ["2019-03-21", "2024-09-24"])


class CensusTests(unittest.TestCase):
    def test_households_are_conserved_when_apportioned_across_lattice_points(self):
        subsections = [census(1000, 400, X0, Y0, 700), census(333, 111, X0 + 400, Y0 + 400, 500)]
        points, households, with_parking = pr.census_cells(subsections)
        self.assertAlmostEqual(sum(households.values()), 1333, places=6)
        self.assertAlmostEqual(sum(with_parking.values()), 511, places=6)
        self.assertTrue(all(n > 0 for n in points.values()))

    def test_tiny_subsection_without_lattice_point_falls_back_to_centroid(self):
        tiny = {"polygons": [square(X0 + 3.0, Y0 + 3.0, 2.0)], "households": 7, "withParking": 2}
        points, households, _ = pr.census_cells([tiny])
        self.assertEqual(sum(points.values()), 1)
        self.assertAlmostEqual(sum(households.values()), 7)

    def test_resident_demand_never_negative(self):
        data = compute(censuses=[census(households=10, with_parking=25)])
        self.assertTrue(all(v == 0 for v in col(data, "residentDemand")))


class OutputTests(unittest.TestCase):
    def test_columns_are_aligned_sorted_finite_and_serializable(self):
        zones = {"features": [{"geometry": {"type": "Polygon", "coordinates": [[
            list(lonlat(-50, -50)), list(lonlat(450, -50)), list(lonlat(450, 950)),
            list(lonlat(-50, 950)), list(lonlat(-50, -50))]]}, "properties": {"zone": "II"}}]}
        spaces = {"features": [
            {"geometry": {"type": "Point", "coordinates": list(lonlat(200, 200))}, "properties": {"status": "active"}},
            {"geometry": {"type": "Point", "coordinates": list(lonlat(200, 200))}, "properties": {"status": "inactive"}},
        ]}
        data = compute({"roads": [road(300), road(600)], "pois": [poi(300, 300, {"shop": "y"})]},
                       inventory={"zones": zones, "spaces": spaces})
        cells = data["cells"]
        self.assertEqual(len({len(v) for v in cells.values()}), 1)
        order = list(zip(cells["r"], cells["q"]))
        self.assertEqual(order, sorted(order))
        self.assertEqual(sum(cells["westernActiveSpaces"]), 1)
        self.assertIn("II", cells["zone"])
        self.assertIn(None, cells["zone"])
        json.dumps(data, allow_nan=False)
        for name in ("overnightIndex", "daytimeIndex"):
            self.assertTrue(all(v is None or 0 <= v <= 100 for v in cells[name]))
        self.assertTrue(all(0 < c <= 1 for c in cells["coverage"]))

    def test_validation_rejects_nan_and_unsorted_cells(self):
        data = compute({"roads": [road(300)]})
        bad = json.loads(json.dumps(data))
        bad["cells"]["attraction"][0] = float("nan")
        with self.assertRaises(src.DataError):
            pr.validate_pressure(bad)
        bad = json.loads(json.dumps(data))
        for values in bad["cells"].values():
            values.reverse()
        with self.assertRaises(src.DataError):
            pr.validate_pressure(bad)


class OverpassTests(unittest.TestCase):
    def test_zero_roads_is_an_error_and_shape_is_validated(self):
        with self.assertRaises(src.DataError):
            src.parse_overpass({"elements": [{"type": "node", "lon": -8.6, "lat": 41.15,
                                              "tags": {"amenity": "parking"}}]})
        with self.assertRaises(src.DataError):
            src.parse_overpass({"nope": []})

    def test_elements_are_classified_and_reference_timestamp_read(self):
        payload = {"osm3s": {"timestamp_osm_base": "2026-09-28T10:00:00Z"}, "elements": [
            {"type": "way", "tags": {"highway": "residential"},
             "geometry": [{"lat": 41.15, "lon": -8.61}, {"lat": 41.151, "lon": -8.61}]},
            {"type": "way", "tags": {"amenity": "parking", "capacity": "10"}, "center": {"lat": 41.15, "lon": -8.6}},
            {"type": "node", "lat": 41.15, "lon": -8.62, "tags": {"shop": "bakery"}},
            {"type": "relation", "tags": {"shop": "mall"}},
        ]}
        osm, timestamp = src.parse_overpass(payload)
        self.assertEqual((len(osm["roads"]), len(osm["parking"]), len(osm["pois"])), (1, 1, 1))
        self.assertEqual(timestamp, "2026-09-28T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
