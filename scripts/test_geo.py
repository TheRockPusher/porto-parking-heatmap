"""Offline unit tests for porto_data.geo."""

from __future__ import annotations

import math
import struct
import unittest

from porto_data.geo import (
    EARTH_RADIUS_M,
    HEX_AREA_M2,
    HEX_CIRCUMRADIUS_M,
    ORIGIN,
    densify_line,
    from_local,
    haversine_m,
    hex_center_local,
    hex_of_lonlat,
    hex_of_local,
    hex_polygon_lonlat,
    lattice_points_in_polygon,
    line_length_m,
    parse_gpkg_geometry,
    point_in_polygon,
    point_in_ring,
    polygon_bbox,
    polygon_centroid,
    tm06_to_wgs84,
    to_local,
    wgs84_to_tm06,
)

LON0_TM06 = -(8 + 7 / 60 + 59.19 / 3600)
LAT0_TM06 = 39 + 40 / 60 + 5.73 / 3600

A = 6378137.0
F = 1 / 298.257222101
E2 = F * (2 - F)


def snyder_forward_tm(lon: float, lat: float) -> tuple[float, float]:
    """Independent forward Transverse Mercator (Snyder, USGS PP1395 eq. 8-9..8-13)."""
    ep2 = E2 / (1 - E2)

    def meridian(phi: float) -> float:
        return A * (
            (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256) * phi
            - (3 * E2 / 8 + 3 * E2**2 / 32 + 45 * E2**3 / 1024) * math.sin(2 * phi)
            + (15 * E2**2 / 256 + 45 * E2**3 / 1024) * math.sin(4 * phi)
            - (35 * E2**3 / 3072) * math.sin(6 * phi)
        )

    phi = math.radians(lat)
    n = A / math.sqrt(1 - E2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    a = math.radians(lon - LON0_TM06) * math.cos(phi)
    x = n * (
        a
        + (1 - t + c) * a**3 / 6
        + (5 - 18 * t + t**2 + 72 * c - 58 * ep2) * a**5 / 120
    )
    y = meridian(phi) - meridian(math.radians(LAT0_TM06)) + n * math.tan(phi) * (
        a**2 / 2
        + (5 - t + 9 * c + 4 * c**2) * a**4 / 24
        + (61 - 58 * t + t**2 + 600 * c - 330 * ep2) * a**6 / 720
    )
    return x, y


def shoelace(ring: list) -> float:
    return 0.5 * abs(
        sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))
    )


class Tm06Tests(unittest.TestCase):
    def test_projection_origin(self) -> None:
        lon, lat = tm06_to_wgs84(0.0, 0.0)
        self.assertAlmostEqual(lon, -8.133108333, delta=1e-7)
        self.assertAlmostEqual(lat, 39.668258333, delta=1e-7)

    def test_forward_of_origin_is_zero(self) -> None:
        x, y = wgs84_to_tm06(LON0_TM06, LAT0_TM06)
        self.assertAlmostEqual(x, 0.0, delta=1e-6)
        self.assertAlmostEqual(y, 0.0, delta=1e-6)

    def test_porto_points_match_independent_snyder_forward(self) -> None:
        places = [
            (-8.6110, 41.1496),  # Aliados
            (-8.6291, 41.1579),  # Palácio de Cristal area
            (-8.5853, 41.1620),  # Campanhã area
            (-8.6763, 41.1560),  # Foz
            (-8.7000, 41.1900),  # NW edge
            (-8.5500, 41.1300),  # SE edge
        ]
        for lon, lat in places:
            with self.subTest(lon=lon, lat=lat):
                x, y = snyder_forward_tm(lon, lat)
                # Porto is ~40-50 km west and ~165 km north of the TM06 origin.
                self.assertTrue(-60_000 < x < -30_000, x)
                self.assertTrue(150_000 < y < 190_000, y)
                got_lon, got_lat = tm06_to_wgs84(x, y)
                # 1 cm on the ground.
                self.assertLess(haversine_m(lon, lat, got_lon, got_lat), 0.01)

    def test_round_trip_is_sub_millimetre(self) -> None:
        for lon in (-8.75, -8.65, -8.55, -8.2):
            for lat in (41.05, 41.15, 41.25):
                x, y = wgs84_to_tm06(lon, lat)
                back_lon, back_lat = tm06_to_wgs84(x, y)
                self.assertLess(haversine_m(lon, lat, back_lon, back_lat), 1e-3)

    def test_forward_agrees_with_snyder_within_a_centimetre(self) -> None:
        for lon, lat in [(-8.611, 41.1496), (-9.14, 38.72), (-7.9, 37.0)]:
            fx, fy = wgs84_to_tm06(lon, lat)
            sx, sy = snyder_forward_tm(lon, lat)
            self.assertLess(math.hypot(fx - sx, fy - sy), 0.01)

    def test_east_of_central_meridian_is_positive_x(self) -> None:
        lon, _ = tm06_to_wgs84(10_000.0, 0.0)
        self.assertGreater(lon, LON0_TM06)
        lon, _ = tm06_to_wgs84(-10_000.0, 0.0)
        self.assertLess(lon, LON0_TM06)


class LocalPlaneTests(unittest.TestCase):
    def test_origin_maps_to_zero(self) -> None:
        x, y = to_local(*ORIGIN)
        self.assertEqual((x, y), (0.0, 0.0))

    def test_round_trip(self) -> None:
        for lon, lat in [(-8.63, 41.16), (-8.7, 41.1), (-8.5, 41.25), (-9.0, 41.0)]:
            x, y = to_local(lon, lat)
            back = from_local(x, y)
            self.assertAlmostEqual(back[0], lon, delta=1e-12)
            self.assertAlmostEqual(back[1], lat, delta=1e-12)

    def test_axes_and_scale(self) -> None:
        x, y = to_local(ORIGIN[0], ORIGIN[1] + 0.01)
        self.assertEqual(x, 0.0)
        self.assertAlmostEqual(y, EARTH_RADIUS_M * math.radians(0.01), places=6)
        x, y = to_local(ORIGIN[0] + 0.01, ORIGIN[1])
        self.assertGreater(x, 0)
        self.assertEqual(y, 0.0)
        # East-west degrees are shorter than north-south ones at 41°N.
        self.assertLess(x, EARTH_RADIUS_M * math.radians(0.01))


class HexTests(unittest.TestCase):
    def test_origin_hex_is_zero(self) -> None:
        self.assertEqual(hex_of_local(0.0, 0.0), (0, 0))
        self.assertEqual(hex_of_lonlat(*ORIGIN), (0, 0))
        self.assertEqual(hex_center_local(0, 0), (0.0, 0.0))

    def test_center_round_trip(self) -> None:
        for q in range(-30, 31):
            for r in range(-30, 31):
                cx, cy = hex_center_local(q, r)
                self.assertEqual(hex_of_local(cx, cy), (q, r))

    def test_points_just_inside_each_edge_map_to_hex(self) -> None:
        apothem = HEX_CIRCUMRADIUS_M * math.sqrt(3) / 2
        for q, r in [(0, 0), (3, -2), (-5, 7), (-12, -9), (20, 4)]:
            cx, cy = hex_center_local(q, r)
            for k in range(6):
                angle = math.radians(60 * k)
                ux, uy = math.cos(angle), math.sin(angle)
                inside = hex_of_local(cx + (apothem - 0.01) * ux, cy + (apothem - 0.01) * uy)
                self.assertEqual(inside, (q, r), (q, r, k))
                outside = hex_of_local(cx + (apothem + 0.01) * ux, cy + (apothem + 0.01) * uy)
                self.assertNotEqual(outside, (q, r), (q, r, k))

    def test_points_near_vertices_map_to_hex(self) -> None:
        for q, r in [(0, 0), (-4, 6)]:
            cx, cy = hex_center_local(q, r)
            for k in range(6):
                angle = math.radians(30 + 60 * k)
                d = HEX_CIRCUMRADIUS_M - 0.05
                self.assertEqual(
                    hex_of_local(cx + d * math.cos(angle), cy + d * math.sin(angle)), (q, r)
                )

    def test_neighbours_are_adjacent(self) -> None:
        cx, cy = hex_center_local(0, 0)
        nx, ny = hex_center_local(1, 0)
        self.assertAlmostEqual(math.hypot(nx - cx, ny - cy), HEX_CIRCUMRADIUS_M * math.sqrt(3))
        self.assertAlmostEqual(ny, 0.0)

    def test_hex_polygon_shape_and_area(self) -> None:
        for q, r in [(0, 0), (5, -3), (-8, 11)]:
            ring = hex_polygon_lonlat(q, r)
            self.assertEqual(len(ring), 7)
            self.assertEqual(ring[0], ring[-1])
            local = [to_local(lon, lat) for lon, lat in ring]
            self.assertAlmostEqual(shoelace(local) / HEX_AREA_M2, 1.0, delta=1e-3)
            cx, cy = hex_center_local(q, r)
            for x, y in local[:-1]:
                self.assertAlmostEqual(math.hypot(x - cx, y - cy), HEX_CIRCUMRADIUS_M, places=6)
            # Pointy-top: first vertex at 30 degrees.
            self.assertAlmostEqual(
                math.degrees(math.atan2(local[0][1] - cy, local[0][0] - cx)), 30.0, places=6
            )
            self.assertEqual(hex_of_local(cx, cy), (q, r))

    def test_hex_area_constant(self) -> None:
        self.assertAlmostEqual(HEX_AREA_M2, 3 * math.sqrt(3) / 2 * 150.0**2)


class PolygonTests(unittest.TestCase):
    SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]

    def test_point_in_ring_open_and_closed(self) -> None:
        self.assertTrue(point_in_ring(5, 5, self.SQUARE))
        self.assertTrue(point_in_ring(5, 5, self.SQUARE[:-1]))
        self.assertFalse(point_in_ring(11, 5, self.SQUARE))
        self.assertFalse(point_in_ring(5, -1, self.SQUARE))
        self.assertFalse(point_in_ring(0, 0, []))

    def test_concave_ring(self) -> None:
        u_shape = [[0, 0], [9, 0], [9, 9], [6, 9], [6, 3], [3, 3], [3, 9], [0, 9]]
        self.assertTrue(point_in_ring(1, 8, u_shape))
        self.assertFalse(point_in_ring(4.5, 8, u_shape))
        self.assertTrue(point_in_ring(4.5, 1, u_shape))

    def test_point_in_polygon_with_hole(self) -> None:
        poly = [self.SQUARE, self.HOLE]
        self.assertTrue(point_in_polygon(1, 1, poly))
        self.assertFalse(point_in_polygon(5, 5, poly))
        self.assertFalse(point_in_polygon(20, 5, poly))
        self.assertTrue(point_in_polygon(5, 5, [self.SQUARE]))
        self.assertFalse(point_in_polygon(5, 5, []))

    def test_bbox(self) -> None:
        self.assertEqual(polygon_bbox([[[1, 2], [5, 2], [3, 9], [1, 2]]]), (1, 2, 5, 9))

    def test_centroid_of_square_and_shifted_square(self) -> None:
        self.assertEqual(polygon_centroid([self.SQUARE]), (5.0, 5.0))
        big = [[x + 1e6, y + 2e6] for x, y in self.SQUARE]
        cx, cy = polygon_centroid([big])
        self.assertAlmostEqual(cx, 1e6 + 5, places=6)
        self.assertAlmostEqual(cy, 2e6 + 5, places=6)

    def test_centroid_area_weighted_not_vertex_mean(self) -> None:
        # Right triangle with an extra collinear vertex biasing the vertex mean.
        tri = [[0, 0], [6, 0], [6.0001, 0], [0, 3], [0, 0]]
        cx, cy = polygon_centroid([tri])
        self.assertAlmostEqual(cx, 2.0, places=3)
        self.assertAlmostEqual(cy, 1.0, places=3)

    def test_centroid_orientation_independent(self) -> None:
        cw = list(reversed(self.SQUARE))
        self.assertEqual(polygon_centroid([cw]), (5.0, 5.0))

    def test_centroid_with_off_centre_hole(self) -> None:
        hole = [[1, 4], [3, 4], [3, 6], [1, 6], [1, 4]]
        cx, cy = polygon_centroid([self.SQUARE, hole])
        self.assertAlmostEqual(cy, 5.0)
        self.assertGreater(cx, 5.0)
        # (100*5 - 4*2) / 96
        self.assertAlmostEqual(cx, (100 * 5 - 4 * 2) / 96)

    def test_centroid_degenerate_falls_back_to_vertex_mean(self) -> None:
        line = [[0, 0], [4, 0], [8, 0], [0, 0]]
        self.assertEqual(polygon_centroid([line]), (4.0, 0.0))
        self.assertEqual(polygon_centroid([[[3, 3], [3, 3], [3, 3]]]), (3.0, 3.0))


class LatticeTests(unittest.TestCase):
    def test_square_count_matches_area(self) -> None:
        square = [[3.0, 5.0], [253.0, 5.0], [253.0, 255.0], [3.0, 255.0], [3.0, 5.0]]
        points = lattice_points_in_polygon([square], 25.0)
        self.assertEqual(len(points), 10 * 10)
        self.assertLess(abs(len(points) - 250.0 * 250.0 / 625.0), 25)
        for x, y in points:
            self.assertEqual(x % 25.0, 0.0)
            self.assertEqual(y % 25.0, 0.0)
            self.assertTrue(point_in_polygon(x, y, [square]))

    def test_matches_brute_force_point_in_polygon(self) -> None:
        outer = [[3, 2], [98, -7], [110, 61], [70, 90], [12, 77], [3, 2]]
        hole = [[40, 20], [70, 25], [60, 50], [38, 45], [40, 20]]
        poly = [outer, hole]
        step = 7.0
        expected = set()
        for i in range(-3, 20):
            for j in range(-3, 20):
                if point_in_polygon(i * step, j * step, poly):
                    expected.add((i * step, j * step))
        got = lattice_points_in_polygon(poly, step)
        self.assertEqual(len(got), len(set(got)))
        self.assertEqual(set(got), expected)

    def test_holes_are_excluded(self) -> None:
        square = [[0.5, 0.5], [100.5, 0.5], [100.5, 100.5], [0.5, 100.5], [0.5, 0.5]]
        hole = [[25.5, 25.5], [75.5, 25.5], [75.5, 75.5], [25.5, 75.5], [25.5, 25.5]]
        full = lattice_points_in_polygon([square], 10.0)
        holed = lattice_points_in_polygon([square, hole], 10.0)
        self.assertEqual(len(full), 100)
        self.assertEqual(len(holed), 100 - 25)
        for x, y in holed:
            self.assertFalse(25.5 < x < 75.5 and 25.5 < y < 75.5)

    def test_tiny_polygon_between_lattice_lines_has_no_points(self) -> None:
        tiny = [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]
        self.assertEqual(lattice_points_in_polygon([tiny], 25.0), [])

    def test_negative_coordinates(self) -> None:
        square = [[-49, -49], [-1, -49], [-1, -1], [-49, -1], [-49, -49]]
        points = lattice_points_in_polygon([square], 25.0)
        self.assertEqual(sorted(points), [(-25.0, -25.0)])

    def test_many_polygons_are_fast_enough(self) -> None:
        # 1,700 polygons of ~25,000 m² with a few dozen vertices each.
        total = 0
        for k in range(1700):
            cx = 1000.0 * (k % 40) + 7.3
            cy = 1000.0 * (k // 40) + 3.1
            ring = [
                [cx + 90 * math.cos(t * math.tau / 40) * (1 + 0.1 * math.sin(5 * t)),
                 cy + 90 * math.sin(t * math.tau / 40) * (1 + 0.1 * math.sin(5 * t))]
                for t in range(40)
            ]
            ring.append(ring[0])
            total += len(lattice_points_in_polygon([ring], 25.0))
        self.assertGreater(total, 1700 * 20)

    def test_invalid_step_raises(self) -> None:
        with self.assertRaises(ValueError):
            lattice_points_in_polygon([[[0, 0], [1, 0], [1, 1], [0, 0]]], 0)


class LineTests(unittest.TestCase):
    def test_haversine_known_distances(self) -> None:
        self.assertEqual(haversine_m(-8.6, 41.1, -8.6, 41.1), 0.0)
        one_degree = math.radians(1) * EARTH_RADIUS_M
        self.assertAlmostEqual(haversine_m(0, 0, 0, 1), one_degree, places=3)
        self.assertAlmostEqual(haversine_m(0, 0, 1, 0), one_degree, places=3)
        self.assertAlmostEqual(haversine_m(10, 20, 30, 40), haversine_m(30, 40, 10, 20))
        # Antipodal points: half the circumference.
        self.assertAlmostEqual(haversine_m(0, 0, 180, 0), math.pi * EARTH_RADIUS_M, places=3)

    def test_haversine_agrees_with_local_plane_at_city_scale(self) -> None:
        lon1, lat1, lon2, lat2 = -8.62, 41.15, -8.60, 41.16
        x1, y1 = to_local(lon1, lat1)
        x2, y2 = to_local(lon2, lat2)
        self.assertAlmostEqual(
            haversine_m(lon1, lat1, lon2, lat2) / math.hypot(x2 - x1, y2 - y1), 1.0, delta=2e-3
        )

    def test_line_length_sums_segments(self) -> None:
        coords = [[-8.62, 41.15], [-8.61, 41.15], [-8.61, 41.16]]
        expected = haversine_m(-8.62, 41.15, -8.61, 41.15) + haversine_m(-8.61, 41.15, -8.61, 41.16)
        self.assertAlmostEqual(line_length_m(coords), expected)
        self.assertEqual(line_length_m([[-8.6, 41.1]]), 0.0)
        self.assertEqual(line_length_m([]), 0.0)

    def test_densify_weights_sum_to_length(self) -> None:
        coords = [[-8.62, 41.15], [-8.6188, 41.1507], [-8.6171, 41.1502], [-8.6171, 41.1502],
                  [-8.61, 41.16]]
        samples = densify_line(coords, 10.0)
        length = line_length_m(coords)
        self.assertAlmostEqual(sum(w for _, _, w in samples) / length, 1.0, delta=1e-9)
        for _, _, w in samples:
            self.assertGreater(w, 0.0)
            self.assertLessEqual(w, 10.0 + 1e-9)

    def test_densify_samples_lie_on_segments_at_midpoints(self) -> None:
        coords = [[-8.62, 41.15], [-8.61, 41.15]]
        length = haversine_m(-8.62, 41.15, -8.61, 41.15)
        samples = densify_line(coords, 10.0)
        pieces = math.ceil(length / 10.0)
        self.assertEqual(len(samples), pieces)
        self.assertAlmostEqual(samples[0][0], -8.62 + 0.01 * 0.5 / pieces)
        self.assertAlmostEqual(samples[-1][0], -8.61 - 0.01 * 0.5 / pieces)
        for lon, lat, _ in samples:
            self.assertEqual(lat, 41.15)
            self.assertTrue(-8.62 < lon < -8.61)

    def test_densify_short_segment_yields_one_sample_with_full_weight(self) -> None:
        coords = [[-8.62, 41.15], [-8.61995, 41.15]]
        samples = densify_line(coords, 10.0)
        self.assertEqual(len(samples), 1)
        self.assertAlmostEqual(samples[0][2], line_length_m(coords))

    def test_densify_degenerate_inputs(self) -> None:
        self.assertEqual(densify_line([]), [])
        self.assertEqual(densify_line([[-8.6, 41.1]]), [])
        self.assertEqual(densify_line([[-8.6, 41.1], [-8.6, 41.1]]), [])
        with self.assertRaises(ValueError):
            densify_line([[0, 0], [1, 1]], 0)


# --- GeoPackage blob builders -------------------------------------------------------
def wkb_header(kind: int, little: bool = True, srid: int | None = None) -> bytes:
    order = "<" if little else ">"
    raw = kind | (0x20000000 if srid is not None and kind < 1000 else 0)
    out = struct.pack("B", 1 if little else 0) + struct.pack(order + "I", raw)
    if srid is not None:
        out += struct.pack(order + "I", srid)
    return out


def wkb_coords(points: list[tuple[float, ...]], little: bool = True) -> bytes:
    order = "<" if little else ">"
    out = struct.pack(order + "I", len(points))
    for p in points:
        out += struct.pack(f"{order}{len(p)}d", *p)
    return out


def wkb_polygon(rings: list[list[tuple[float, ...]]], kind: int = 3, little: bool = True) -> bytes:
    order = "<" if little else ">"
    out = wkb_header(kind, little) + struct.pack(order + "I", len(rings))
    for ring in rings:
        out += wkb_coords(ring, little)
    return out


def gpkg(wkb: bytes, *, envelope: int = 0, little: bool = True, empty: bool = False,
         magic: bytes = b"GP") -> bytes:
    flags = (1 if little else 0) | (envelope << 1) | (0x10 if empty else 0)
    order = "<" if little else ">"
    env_len = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[envelope]
    return magic + bytes([0, flags]) + struct.pack(order + "i", 3763) + b"\xab" * env_len + wkb


SQ = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0)]
SQ_HOLE = [(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0), (1.0, 1.0)]


def as_lists(ring: list[tuple[float, ...]]) -> list[list[float]]:
    return [[p[0], p[1]] for p in ring]


class GpkgTests(unittest.TestCase):
    def test_polygon_with_hole_little_and_big_endian(self) -> None:
        for little in (True, False):
            blob = gpkg(wkb_polygon([SQ, SQ_HOLE], little=little), little=little)
            geom = parse_gpkg_geometry(blob)
            self.assertEqual(geom["type"], "Polygon")
            self.assertEqual(geom["coordinates"], [as_lists(SQ), as_lists(SQ_HOLE)])

    def test_mixed_header_and_wkb_byte_orders(self) -> None:
        blob = gpkg(wkb_polygon([SQ], little=False), little=True)
        self.assertEqual(parse_gpkg_geometry(blob)["coordinates"], [as_lists(SQ)])
        blob = gpkg(wkb_polygon([SQ], little=True), little=False)
        self.assertEqual(parse_gpkg_geometry(blob)["coordinates"], [as_lists(SQ)])

    def test_all_envelope_indicators(self) -> None:
        for envelope in range(5):
            blob = gpkg(wkb_polygon([SQ]), envelope=envelope)
            geom = parse_gpkg_geometry(blob)
            self.assertEqual(geom["coordinates"], [as_lists(SQ)], envelope)

    def test_invalid_envelope_indicator_raises(self) -> None:
        blob = bytearray(gpkg(wkb_polygon([SQ])))
        blob[3] |= 5 << 1
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(bytes(blob))

    def test_multipolygon(self) -> None:
        second = [(10.0, 10.0), (12.0, 10.0), (12.0, 12.0), (10.0, 10.0)]
        for little in (True, False):
            order = "<" if little else ">"
            wkb = (
                wkb_header(6, little)
                + struct.pack(order + "I", 2)
                + wkb_polygon([SQ, SQ_HOLE], little=little)
                + wkb_polygon([second], little=little)
            )
            geom = parse_gpkg_geometry(gpkg(wkb, envelope=1, little=little))
            self.assertEqual(geom["type"], "MultiPolygon")
            self.assertEqual(
                geom["coordinates"],
                [[as_lists(SQ), as_lists(SQ_HOLE)], [as_lists(second)]],
            )

    def test_multipolygon_with_mixed_member_byte_order(self) -> None:
        wkb = (
            wkb_header(6, True)
            + struct.pack("<I", 2)
            + wkb_polygon([SQ], little=False)
            + wkb_polygon([SQ_HOLE], little=True)
        )
        geom = parse_gpkg_geometry(gpkg(wkb))
        self.assertEqual(geom["coordinates"], [[as_lists(SQ)], [as_lists(SQ_HOLE)]])

    def test_z_variants_drop_z(self) -> None:
        sq_z = [(x, y, 99.0) for x, y in SQ]
        # ISO Z polygon (type 1003).
        geom = parse_gpkg_geometry(gpkg(wkb_polygon([sq_z], kind=1003)))
        self.assertEqual(geom["coordinates"], [as_lists(SQ)])
        # ISO M (2003) and ZM (3003).
        sq_m = [(x, y, 7.0) for x, y in SQ]
        self.assertEqual(
            parse_gpkg_geometry(gpkg(wkb_polygon([sq_m], kind=2003)))["coordinates"],
            [as_lists(SQ)],
        )
        sq_zm = [(x, y, 1.0, 2.0) for x, y in SQ]
        self.assertEqual(
            parse_gpkg_geometry(gpkg(wkb_polygon([sq_zm], kind=3003)))["coordinates"],
            [as_lists(SQ)],
        )
        # EWKB Z flag.
        geom = parse_gpkg_geometry(gpkg(wkb_polygon([sq_z], kind=3 | 0x80000000)))
        self.assertEqual(geom["coordinates"], [as_lists(SQ)])

    def test_ewkb_srid_flag_is_skipped(self) -> None:
        wkb = wkb_header(3, srid=4326) + struct.pack("<I", 1) + wkb_coords(SQ)
        geom = parse_gpkg_geometry(gpkg(wkb))
        self.assertEqual(geom["coordinates"], [as_lists(SQ)])

    def test_multipolygon_z_variant(self) -> None:
        sq_z = [(x, y, 5.0) for x, y in SQ]
        wkb = (
            wkb_header(1006)
            + struct.pack("<I", 1)
            + wkb_polygon([sq_z], kind=1003)
        )
        geom = parse_gpkg_geometry(gpkg(wkb))
        self.assertEqual(geom, {"type": "MultiPolygon", "coordinates": [[as_lists(SQ)]]})

    def test_point_linestring_and_other_multis(self) -> None:
        point = wkb_header(1) + struct.pack("<2d", 1.5, -2.5)
        self.assertEqual(
            parse_gpkg_geometry(gpkg(point)), {"type": "Point", "coordinates": [1.5, -2.5]}
        )
        point_z = wkb_header(1001) + struct.pack("<3d", 1.5, -2.5, 9.0)
        self.assertEqual(parse_gpkg_geometry(gpkg(point_z))["coordinates"], [1.5, -2.5])
        line = wkb_header(2) + wkb_coords([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
        self.assertEqual(
            parse_gpkg_geometry(gpkg(line)),
            {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]]},
        )
        multi_line = (
            wkb_header(5) + struct.pack("<I", 2)
            + wkb_header(2) + wkb_coords([(0.0, 0.0), (1.0, 0.0)])
            + wkb_header(2) + wkb_coords([(5.0, 5.0), (6.0, 6.0)])
        )
        self.assertEqual(
            parse_gpkg_geometry(gpkg(multi_line)),
            {"type": "MultiLineString",
             "coordinates": [[[0.0, 0.0], [1.0, 0.0]], [[5.0, 5.0], [6.0, 6.0]]]},
        )
        multi_point = (
            wkb_header(4) + struct.pack("<I", 2)
            + wkb_header(1) + struct.pack("<2d", 1.0, 2.0)
            + wkb_header(1) + struct.pack("<2d", 3.0, 4.0)
        )
        self.assertEqual(
            parse_gpkg_geometry(gpkg(multi_point)),
            {"type": "MultiPoint", "coordinates": [[1.0, 2.0], [3.0, 4.0]]},
        )

    def test_empty_flag_returns_empty_collection(self) -> None:
        blob = gpkg(wkb_header(1) + struct.pack("<2d", math.nan, math.nan), empty=True)
        self.assertEqual(parse_gpkg_geometry(blob), {"type": "GeometryCollection", "geometries": []})

    def test_bad_magic_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(gpkg(wkb_polygon([SQ]), magic=b"XX"))
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(b"")
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(b"GP")

    def test_unsupported_type_raises(self) -> None:
        collection = wkb_header(7) + struct.pack("<I", 0)
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(gpkg(collection))
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(gpkg(wkb_header(17) + struct.pack("<I", 0)))
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(gpkg(wkb_header(4003) + struct.pack("<I", 0)))

    def test_bad_wkb_byte_order_marker_raises(self) -> None:
        blob = gpkg(b"\x05" + struct.pack("<I", 3))
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(blob)

    def test_truncated_or_inflated_counts_raise(self) -> None:
        good = gpkg(wkb_polygon([SQ]))
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(good[:-5])
        inflated = gpkg(wkb_header(3) + struct.pack("<I", 1) + struct.pack("<I", 4_000_000_000))
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(inflated)

    def test_wrong_member_type_in_multi_raises(self) -> None:
        wkb = wkb_header(6) + struct.pack("<I", 1) + wkb_header(2) + wkb_coords([(0.0, 0.0), (1.0, 1.0)])
        with self.assertRaises(ValueError):
            parse_gpkg_geometry(gpkg(wkb))

    def test_parsed_polygon_feeds_geometry_helpers(self) -> None:
        geom = parse_gpkg_geometry(gpkg(wkb_polygon([SQ, SQ_HOLE])))
        poly = geom["coordinates"]
        self.assertTrue(point_in_polygon(3, 3, poly))
        self.assertFalse(point_in_polygon(1.5, 1.5, poly))
        self.assertEqual(polygon_bbox(poly), (0.0, 0.0, 4.0, 4.0))


if __name__ == "__main__":
    unittest.main()
