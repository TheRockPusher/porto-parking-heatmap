import type { Feature, FeatureCollection, Polygon } from "geojson";
import type { PressureCellProperties, PressureData, PressureGridSpec, PressurePeriod } from "../types";

/** Defaults only; the runtime grid block published with the dataset always wins. */
export const HEX = {
  circumradiusM: 150,
  origin: [-8.63, 41.16] as [number, number],
  earthRadiusM: 6371008.8,
};

export const PERIOD_LABELS: Record<PressurePeriod, string> = {
  daytime: "Weekday daytime",
  overnight: "Overnight (residents)",
};

export function periodIndexProperty(period: PressurePeriod): "daytimeIndex" | "overnightIndex" {
  return period === "daytime" ? "daytimeIndex" : "overnightIndex";
}

/**
 * 5-class sequential ramp (low to high), magma-like: lightness falls monotonically so the
 * order survives colour-vision deficiencies and greyscale; the darkest classes stay legible
 * over the light OpenStreetMap basemap. Each entry is [lowest index in class, colour].
 */
export const PRESSURE_STOPS: [number, string][] = [
  [0, "#fbe08a"],
  [20, "#f4a259"],
  [40, "#d9574a"],
  [60, "#9c2a6b"],
  [80, "#4b1470"],
];

/** Neutral grey for cells without enough estimated supply; pair with a hatch/outline in the UI. */
export const NO_DATA_COLOR = "#9aa0a6";

const CLASS_LABELS = ["Low", "Below average", "Average", "Above average", "High"] as const;
export const NO_DATA_LABEL = "Insufficient supply data";

export function pressureClass(index: number | null): { label: string; color: string } {
  if (index === null || !Number.isFinite(index)) return { label: NO_DATA_LABEL, color: NO_DATA_COLOR };
  let step = 0;
  for (let i = PRESSURE_STOPS.length - 1; i > 0; i -= 1) {
    if (index >= PRESSURE_STOPS[i][0]) {
      step = i;
      break;
    }
  }
  return { label: CLASS_LABELS[step], color: PRESSURE_STOPS[step][1] };
}

export function pressureId(q: number, r: number): string {
  return `pressure:${q}_${r}`;
}

export function parsePressureId(id: string): { q: number; r: number } | null {
  const match = /^pressure:(-?\d+)_(-?\d+)$/.exec(id);
  return match ? { q: Number(match[1]), r: Number(match[2]) } : null;
}

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const SQRT3 = Math.sqrt(3);

function round6(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

/** Closed 7-point [lon, lat] ring; identical math to geo.py `hex_polygon_lonlat`. */
export function hexPolygon(q: number, r: number, grid: PressureGridSpec): [number, number][] {
  const size = grid.circumradiusM;
  const [lon0, lat0] = grid.origin;
  const metresPerLon = grid.earthRadiusM * Math.cos(lat0 * RAD);
  const centreX = size * SQRT3 * (q + r / 2);
  const centreY = size * 1.5 * r;
  const ring: [number, number][] = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (30 + 60 * i) * RAD;
    const x = centreX + size * Math.cos(angle);
    const y = centreY + size * Math.sin(angle);
    ring.push([round6(lon0 + (x / metresPerLon) * DEG), round6(lat0 + (y / grid.earthRadiusM) * DEG)]);
  }
  ring.push([ring[0][0], ring[0][1]]);
  return ring;
}

export function pressureToGeoJSON(
  data: PressureData,
): FeatureCollection<Polygon, PressureCellProperties> {
  const c = data.cells;
  const features: Feature<Polygon, PressureCellProperties>[] = new Array(c.q.length);
  for (let i = 0; i < c.q.length; i += 1) {
    features[i] = {
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [hexPolygon(c.q[i], c.r[i], data.grid)] },
      properties: {
        id: pressureId(c.q[i], c.r[i]),
        kind: "pressure",
        q: c.q[i],
        r: c.r[i],
        coverage: c.coverage[i],
        zone: c.zone[i],
        households: c.households[i],
        householdsWithParking: c.householdsWithParking[i],
        residentDemand: c.residentDemand[i],
        roadLengthM: c.roadLengthM[i],
        onStreetEstimate: c.onStreetEstimate[i],
        offStreetPublic: c.offStreetPublic[i],
        westernActiveSpaces: c.westernActiveSpaces[i],
        attraction: c.attraction[i],
        complaints: c.complaints[i],
        restrictionDays: c.restrictionDays[i],
        overnightRatio: c.overnightRatio[i],
        daytimeRatio: c.daytimeRatio[i],
        overnightIndex: c.overnightIndex[i],
        daytimeIndex: c.daytimeIndex[i],
      },
    };
  }
  return { type: "FeatureCollection", features };
}
