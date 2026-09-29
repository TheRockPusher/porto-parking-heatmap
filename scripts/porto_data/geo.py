"""Geometry helpers for the Porto parking data pipeline (standard library only).

Coordinate conventions used throughout:

* ``lon``/``lat`` are decimal degrees (WGS84; ETRS89 is treated as identical).
* "local" coordinates ``(x, y)`` are metres in an equirectangular plane about
  :data:`ORIGIN` (east, north). The hex grid lives in this plane.
* TM06 coordinates ``(x, y)`` are metres in EPSG:3763 (ETRS89 / Portugal TM06).
* Distances are metres, areas are square metres (of whichever planar unit the
  caller supplies for the planar helpers).
"""

from __future__ import annotations

import math
import struct
from typing import Any, Sequence

EARTH_RADIUS_M = 6371008.8
ORIGIN = (-8.63, 41.16)  # (lon, lat) of the local plane origin and hex (0, 0) centre
HEX_CIRCUMRADIUS_M = 150.0
HEX_AREA_M2 = 3 * math.sqrt(3) / 2 * HEX_CIRCUMRADIUS_M**2

_SQRT3 = math.sqrt(3.0)
_COS_LAT0 = math.cos(math.radians(ORIGIN[1]))

# --- EPSG:3763 (ETRS89 / Portugal TM06) -------------------------------------
_GRS80_A = 6378137.0
_GRS80_INV_F = 298.257222101
_GRS80_F = 1.0 / _GRS80_INV_F
_TM06_LAT0 = 39.0 + 40.0 / 60.0 + 5.73 / 3600.0  # 39°40'05.73" N
_TM06_LON0 = -(8.0 + 7.0 / 60.0 + 59.19 / 3600.0)  # 8°07'59.19" W
_TM06_K0 = 1.0
_TM06_FE = 0.0
_TM06_FN = 0.0


def _kruger_constants() -> tuple[float, float, tuple[float, ...], tuple[float, ...], float]:
    """Krüger n-series coefficients (4th order, sub-millimetre inside Portugal)."""
    f = _GRS80_F
    n = f / (2.0 - f)
    e = math.sqrt(f * (2.0 - f))
    n2, n3, n4 = n * n, n**3, n**4
    rect = _GRS80_A / (1.0 + n) * (1.0 + n2 / 4.0 + n4 / 64.0)
    alpha = (
        n / 2.0 - 2.0 * n2 / 3.0 + 5.0 * n3 / 16.0 + 41.0 * n4 / 180.0,
        13.0 * n2 / 48.0 - 3.0 * n3 / 5.0 + 557.0 * n4 / 1440.0,
        61.0 * n3 / 240.0 - 103.0 * n4 / 140.0,
        49561.0 * n4 / 161280.0,
    )
    beta = (
        n / 2.0 - 2.0 * n2 / 3.0 + 37.0 * n3 / 96.0 - n4 / 360.0,
        n2 / 48.0 + n3 / 15.0 - 437.0 * n4 / 1440.0,
        17.0 * n3 / 480.0 - 37.0 * n4 / 840.0,
        4397.0 * n4 / 161280.0,
    )
    return rect, e, alpha, beta, n


_RECT_A, _ECC, _ALPHA, _BETA, _N = _kruger_constants()
_DELTA = (
    2.0 * _N - 2.0 * _N**2 / 3.0 - 2.0 * _N**3 + 116.0 * _N**4 / 45.0,
    7.0 * _N**2 / 3.0 - 8.0 * _N**3 / 5.0 - 227.0 * _N**4 / 45.0,
    56.0 * _N**3 / 15.0 - 136.0 * _N**4 / 35.0,
    4279.0 * _N**4 / 630.0,
)


def _conformal_latitude(lat_rad: float) -> float:
    sin_lat = math.sin(lat_rad)
    return math.atan(math.sinh(math.atanh(sin_lat) - _ECC * math.atanh(_ECC * sin_lat)))


def _xi0() -> float:
    chi = _conformal_latitude(math.radians(_TM06_LAT0))
    return chi + sum(a * math.sin(2 * (j + 1) * chi) for j, a in enumerate(_ALPHA))


_XI0 = _xi0()


def wgs84_to_tm06(lon: float, lat: float) -> tuple[float, float]:
    """Forward EPSG:3763: WGS84 degrees -> TM06 metres ``(easting, northing)``.

    Provided mainly so the inverse can be round-trip tested.
    """
    dlon = math.radians(lon - _TM06_LON0)
    chi = _conformal_latitude(math.radians(lat))
    xi_p = math.atan2(math.tan(chi), math.cos(dlon))
    eta_p = math.atanh(math.cos(chi) * math.sin(dlon))
    xi = xi_p
    eta = eta_p
    for j, a in enumerate(_ALPHA, start=1):
        xi += a * math.sin(2 * j * xi_p) * math.cosh(2 * j * eta_p)
        eta += a * math.cos(2 * j * xi_p) * math.sinh(2 * j * eta_p)
    x = _TM06_FE + _TM06_K0 * _RECT_A * eta
    y = _TM06_FN + _TM06_K0 * _RECT_A * (xi - _XI0)
    return x, y


def tm06_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Inverse EPSG:3763: TM06 metres ``(easting, northing)`` -> ``(lon, lat)`` degrees.

    Krüger n-series on GRS80; error is well below 1 mm within Portugal. ETRS89 is
    treated as WGS84 (sub-metre difference).
    """
    xi = (y - _TM06_FN) / (_TM06_K0 * _RECT_A) + _XI0
    eta = (x - _TM06_FE) / (_TM06_K0 * _RECT_A)
    xi_p = xi
    eta_p = eta
    for j, b in enumerate(_BETA, start=1):
        xi_p -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta_p -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    chi = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    lat = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, start=1))
    lon = math.atan2(math.sinh(eta_p), math.cos(xi_p))
    return _TM06_LON0 + math.degrees(lon), math.degrees(lat)


# --- Local equirectangular plane ---------------------------------------------
def to_local(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 degrees -> local metres ``(x east, y north)`` about :data:`ORIGIN`."""
    x = EARTH_RADIUS_M * math.radians(lon - ORIGIN[0]) * _COS_LAT0
    y = EARTH_RADIUS_M * math.radians(lat - ORIGIN[1])
    return x, y


def from_local(x: float, y: float) -> tuple[float, float]:
    """Local metres -> WGS84 ``(lon, lat)`` degrees; exact inverse of :func:`to_local`."""
    lon = ORIGIN[0] + math.degrees(x / (EARTH_RADIUS_M * _COS_LAT0))
    lat = ORIGIN[1] + math.degrees(y / EARTH_RADIUS_M)
    return lon, lat


# --- Distances ------------------------------------------------------------------
def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two WGS84 points (degrees)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def line_length_m(coords: Sequence[Sequence[float]]) -> float:
    """Length in metres of a ``[[lon, lat], ...]`` polyline (haversine per segment)."""
    total = 0.0
    for i in range(1, len(coords)):
        total += haversine_m(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
    return total


def densify_line(
    coords: Sequence[Sequence[float]], step_m: float = 10.0
) -> list[tuple[float, float, float]]:
    """Midpoint samples along a ``[[lon, lat], ...]`` polyline.

    Each segment of length ``L`` metres is cut into ``ceil(L / step_m)`` equal pieces
    and one ``(lon, lat, weight_m)`` sample is emitted at the middle of each piece,
    with ``weight_m`` the piece length. The weights sum to :func:`line_length_m`.
    Zero-length segments produce no samples.
    """
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    samples: list[tuple[float, float, float]] = []
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1][0], coords[i - 1][1]
        lon2, lat2 = coords[i][0], coords[i][1]
        length = haversine_m(lon1, lat1, lon2, lat2)
        if length <= 0.0:
            continue
        pieces = max(1, math.ceil(length / step_m))
        weight = length / pieces
        for k in range(pieces):
            t = (k + 0.5) / pieces
            samples.append((lon1 + (lon2 - lon1) * t, lat1 + (lat2 - lat1) * t, weight))
    return samples


# --- Hex grid (pointy-top axial) ------------------------------------------------
def hex_of_local(x: float, y: float) -> tuple[int, int]:
    """Axial ``(q, r)`` of the hex containing local point ``(x, y)`` metres (cube rounding)."""
    size = HEX_CIRCUMRADIUS_M
    fq = (_SQRT3 / 3.0 * x - y / 3.0) / size
    fr = (2.0 / 3.0 * y) / size
    fs = -fq - fr
    rq, rr, rs = round(fq), round(fr), round(fs)
    dq, dr, ds = abs(rq - fq), abs(rr - fr), abs(rs - fs)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


def hex_of_lonlat(lon: float, lat: float) -> tuple[int, int]:
    """Axial ``(q, r)`` of the hex containing a WGS84 point (degrees)."""
    x, y = to_local(lon, lat)
    return hex_of_local(x, y)


def hex_center_local(q: int, r: int) -> tuple[float, float]:
    """Centre of hex ``(q, r)`` in local metres."""
    size = HEX_CIRCUMRADIUS_M
    return size * _SQRT3 * (q + r / 2.0), size * 1.5 * r


def hex_polygon_lonlat(q: int, r: int) -> list[list[float]]:
    """Closed ring (7 ``[lon, lat]`` points, first == last) of hex ``(q, r)``.

    Vertices sit at angles 30° + 60°·i from the centre (pointy-top), counter-clockwise.
    """
    cx, cy = hex_center_local(q, r)
    ring: list[list[float]] = []
    for i in range(6):
        angle = math.radians(30.0 + 60.0 * i)
        lon, lat = from_local(
            cx + HEX_CIRCUMRADIUS_M * math.cos(angle), cy + HEX_CIRCUMRADIUS_M * math.sin(angle)
        )
        ring.append([lon, lat])
    ring.append(list(ring[0]))
    return ring


# --- Planar polygon helpers (any planar unit) -----------------------------------
Ring = Sequence[Sequence[float]]
Polygon = Sequence[Ring]


def point_in_ring(x: float, y: float, ring: Ring) -> bool:
    """Even-odd point-in-ring test; the ring may be open or explicitly closed."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    xj, yj = ring[n - 1][0], ring[n - 1][1]
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        xj, yj = xi, yi
    return inside


def point_in_polygon(x: float, y: float, polygon: Polygon) -> bool:
    """``polygon = [outer, *holes]``; True when inside the outer ring and outside all holes."""
    if not polygon or not point_in_ring(x, y, polygon[0]):
        return False
    return not any(point_in_ring(x, y, hole) for hole in polygon[1:])


def polygon_bbox(polygon: Polygon) -> tuple[float, float, float, float]:
    """``(minx, miny, maxx, maxy)`` of the outer ring."""
    outer = polygon[0]
    if not outer:
        raise ValueError("polygon has an empty outer ring")
    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    return min(xs), min(ys), max(xs), max(ys)


def _ring_area_centroid(ring: Ring) -> tuple[float, float, float]:
    """Signed shoelace area and area centroid of a ring (0, 0, 0 for degenerate rings)."""
    n = len(ring)
    if n < 3:
        return 0.0, 0.0, 0.0
    # Shift to the first vertex for numerical stability with large coordinates.
    ox, oy = ring[0][0], ring[0][1]
    a2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x0, y0 = ring[i][0] - ox, ring[i][1] - oy
        x1, y1 = ring[(i + 1) % n][0] - ox, ring[(i + 1) % n][1] - oy
        cross = x0 * y1 - x1 * y0
        a2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if a2 == 0.0:
        return 0.0, 0.0, 0.0
    return a2 / 2.0, ox + cx / (3.0 * a2), oy + cy / (3.0 * a2)


def polygon_centroid(polygon: Polygon) -> tuple[float, float]:
    """Area-weighted centroid (holes subtracted); vertex mean of the outer ring if area ≈ 0."""
    outer = polygon[0]
    if not outer:
        raise ValueError("polygon has an empty outer ring")
    minx, miny, maxx, maxy = polygon_bbox(polygon)
    scale = max(maxx - minx, maxy - miny)
    area, cx, cy = _ring_area_centroid(outer)
    total = abs(area)
    wx = abs(area) * cx
    wy = abs(area) * cy
    for hole in polygon[1:]:
        h_area, hx, hy = _ring_area_centroid(hole)
        total -= abs(h_area)
        wx -= abs(h_area) * hx
        wy -= abs(h_area) * hy
    if total > 1e-12 * scale * scale and total > 0.0:
        return wx / total, wy / total
    pts = outer[:-1] if len(outer) > 1 and outer[0][0] == outer[-1][0] and outer[0][1] == outer[-1][1] else outer
    return (
        sum(p[0] for p in pts) / len(pts),
        sum(p[1] for p in pts) / len(pts),
    )


def lattice_points_in_polygon(polygon: Polygon, step: float) -> list[tuple[float, float]]:
    """Points ``(i*step, j*step)`` inside ``polygon = [outer, *holes]`` (holes excluded).

    Works in the polygon's own planar units (``step`` in the same units). Uses even-odd
    scanline crossings per lattice row, so cost is O(rows * edges) instead of a
    point-in-polygon test per lattice point. Output is ordered by row (y), then x.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    if not polygon or len(polygon[0]) < 3:
        return []
    _, miny, _, maxy = polygon_bbox(polygon)
    edges: list[tuple[float, float, float, float]] = []
    for ring in polygon:
        n = len(ring)
        if n < 3:
            continue
        for i in range(n):
            x0, y0 = ring[i - 1][0], ring[i - 1][1]
            x1, y1 = ring[i][0], ring[i][1]
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
    points: list[tuple[float, float]] = []
    row = math.ceil(miny / step)
    last_row = math.floor(maxy / step)
    while row <= last_row:
        y = row * step
        crossings: list[float] = []
        for x0, y0, x1, y1 in edges:
            if (y0 > y) != (y1 > y):
                crossings.append((x1 - x0) * (y - y0) / (y1 - y0) + x0)
        crossings.sort()
        for k in range(0, len(crossings) - 1, 2):
            # Same half-open convention as point_in_ring: x is inside for c0 <= x < c1.
            first = math.ceil(crossings[k] / step)
            last = math.ceil(crossings[k + 1] / step) - 1
            for col in range(first, last + 1):
                points.append((col * step, y))
        row += 1
    return points


# --- GeoPackage / WKB -----------------------------------------------------------
_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
_EWKB_Z = 0x80000000
_EWKB_M = 0x40000000
_EWKB_SRID = 0x20000000
_GEOJSON_TYPES = {
    1: "Point",
    2: "LineString",
    3: "Polygon",
    4: "MultiPoint",
    5: "MultiLineString",
    6: "MultiPolygon",
}


class _WkbReader:
    def __init__(self, buf: bytes, offset: int) -> None:
        self.buf = buf
        self.pos = offset

    def _unpack(self, fmt: str) -> tuple:
        size = struct.calcsize(fmt)
        if self.pos + size > len(self.buf):
            raise ValueError("truncated WKB geometry")
        values = struct.unpack_from(fmt, self.buf, self.pos)
        self.pos += size
        return values

    def _count(self, order: str, min_item_bytes: int) -> int:
        (count,) = self._unpack(order + "I")
        if count * min_item_bytes > len(self.buf) - self.pos:
            raise ValueError("truncated WKB geometry")
        return count

    def _coords(self, order: str, dims: int) -> list[list[float]]:
        count = self._count(order, dims * 8)
        values = self._unpack(f"{order}{count * dims}d")
        return [[values[i], values[i + 1]] for i in range(0, count * dims, dims)]

    def geometry(self) -> tuple[str, Any]:
        (byte_order,) = self._unpack("B")
        if byte_order not in (0, 1):
            raise ValueError(f"invalid WKB byte order marker {byte_order}")
        order = "<" if byte_order == 1 else ">"
        (raw_type,) = self._unpack(order + "I")
        has_z = bool(raw_type & _EWKB_Z)
        has_m = bool(raw_type & _EWKB_M)
        has_srid = bool(raw_type & _EWKB_SRID)
        code = raw_type & 0x0FFFFFFF
        iso_dim, code = divmod(code, 1000)
        if iso_dim > 3:
            raise ValueError(f"unsupported WKB geometry type {raw_type}")
        has_z = has_z or iso_dim in (1, 3)
        has_m = has_m or iso_dim in (2, 3)
        if has_srid:
            self._unpack(order + "I")
        gtype = _GEOJSON_TYPES.get(code)
        if gtype is None:
            raise ValueError(f"unsupported WKB geometry type {raw_type}")
        dims = 2 + int(has_z) + int(has_m)
        if code == 1:
            values = self._unpack(f"{order}{dims}d")
            return gtype, [values[0], values[1]]
        if code == 2:
            return gtype, self._coords(order, dims)
        if code == 3:
            rings = self._count(order, 4)
            return gtype, [self._coords(order, dims) for _ in range(rings)]
        # Multi geometries: each member carries its own header.
        member_type = {4: "Point", 5: "LineString", 6: "Polygon"}[code]
        members = self._count(order, 5)
        out: list[Any] = []
        for _ in range(members):
            sub_type, coords = self.geometry()
            if sub_type != member_type:
                raise ValueError(f"{gtype} contains a {sub_type}")
            out.append(coords)
        return gtype, out


def parse_gpkg_geometry(blob: bytes) -> dict:
    """Decode a GeoPackage geometry BLOB to ``{"type": ..., "coordinates": ...}``.

    Supports the GeoPackage binary header (magic ``GP``, envelope codes 0-4, either
    header byte order) followed by standard WKB in either byte order for Point,
    LineString, Polygon, MultiPoint, MultiLineString and MultiPolygon, including ISO
    (+1000/+2000/+3000) and EWKB (Z/M/SRID flag) variants. Z and M values are dropped.
    Coordinates are returned exactly as stored (the caller knows the CRS).

    Geometries flagged empty in the header return
    ``{"type": "GeometryCollection", "geometries": []}``.
    Raises ``ValueError`` on bad magic, bad envelope code, truncation or unsupported types.
    """
    if len(blob) < 8 or blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry blob (bad magic)")
    flags = blob[3]
    envelope_code = (flags >> 1) & 0x07
    if envelope_code not in _ENVELOPE_BYTES:
        raise ValueError(f"invalid GeoPackage envelope indicator {envelope_code}")
    if (flags >> 4) & 1:
        return {"type": "GeometryCollection", "geometries": []}
    offset = 8 + _ENVELOPE_BYTES[envelope_code]
    reader = _WkbReader(bytes(blob), offset)
    gtype, coords = reader.geometry()
    return {"type": gtype, "coordinates": coords}
