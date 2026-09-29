import type { Feature, FeatureCollection, Geometry } from "geojson";

export type LayerKind = "streets" | "zones" | "spaces" | "garages";
export type MapLayer = LayerKind | "pressure";
export type DatasetName = LayerKind | "pressure";
export type SpaceStatus = "active" | "inactive" | "unknown";
export type PressurePeriod = "daytime" | "overnight";

interface BaseProperties {
  id: string;
  name: string | null;
}

export interface StreetProperties extends BaseProperties {
  kind: "streets";
}

export interface ZoneProperties extends BaseProperties {
  kind: "zones";
  zone: string | null;
  hourlyRate: number | null;
}

export interface SpaceProperties extends BaseProperties {
  kind: "spaces";
  status: SpaceStatus;
  residentZone: string | null;
}

export interface GarageProperties extends BaseProperties {
  kind: "garages";
  address: string | null;
  operator: string | null;
  openingHours: string | null;
  lightVehicleCapacity: number | null;
}

export type ParkingProperties =
  | StreetProperties
  | ZoneProperties
  | SpaceProperties
  | GarageProperties;
export type ParkingFeature = Feature<Geometry, ParkingProperties>;

export interface ParkingCollections {
  streets: FeatureCollection<Geometry, StreetProperties>;
  zones: FeatureCollection<Geometry, ZoneProperties>;
  spaces: FeatureCollection<Geometry, SpaceProperties>;
  garages: FeatureCollection<Geometry, GarageProperties>;
}

/** Raw source attributes, loaded lazily per inventory layer and keyed by feature id. */
export type AttributeTable = Record<string, Record<string, unknown>>;

export type SourceId = LayerKind | "census" | "osm" | "restrictions" | "complaints" | "calibration";

export interface SourceRecord {
  id: SourceId;
  group: "inventory" | "pressure";
  name: string;
  url: string;
  metadataUrl: string | null;
  license: string;
  referenceDate: string | null;
  retrievedAt: string;
  recordCount: number;
  caveat: string;
}

export interface InventoryDatasetEntry {
  path: string;
  attributesPath: string;
  bytes: number;
  featureCount: number;
}

export interface PressureDatasetEntry {
  path: string;
  bytes: number;
  cellCount: number;
}

export interface DataManifest {
  schemaVersion: 2;
  generatedAt: string;
  datasets: Record<LayerKind, InventoryDatasetEntry> & { pressure: PressureDatasetEntry };
  sources: SourceRecord[];
}

export interface PressureGridSpec {
  type: "hex-axial-pointy";
  circumradiusM: number;
  origin: [number, number];
  earthRadiusM: number;
  projection: "equirectangular-local";
}

export interface PressureMethod {
  onStreetTotalCalibration: number;
  roadClasses: string[];
  poiWeights: Record<string, number>;
  minSupplyForIndex: number;
  complaintServiceCodes: string[];
  complaintWindow: [string, string] | null;
  restrictionsWindow: [string, string] | null;
  notes: string;
}

export interface PressureColumns {
  q: number[];
  r: number[];
  coverage: number[];
  zone: (string | null)[];
  households: number[];
  householdsWithParking: number[];
  residentDemand: number[];
  roadLengthM: number[];
  onStreetEstimate: number[];
  offStreetPublic: number[];
  westernActiveSpaces: number[];
  attraction: number[];
  complaints: number[];
  restrictionDays: number[];
  overnightRatio: (number | null)[];
  daytimeRatio: (number | null)[];
  overnightIndex: (number | null)[];
  daytimeIndex: (number | null)[];
}

export interface PressureData {
  schemaVersion: 2;
  grid: PressureGridSpec;
  periods: PressurePeriod[];
  method: PressureMethod;
  cells: PressureColumns;
}

/** One row of PressureColumns plus its feature id ("pressure:q_r"). */
export type PressureCellProperties = {
  [K in keyof PressureColumns]: PressureColumns[K][number];
} & { id: string; kind: "pressure" };

export type DatasetStatus = "idle" | "loading" | "ready" | "error";

export interface ExplorerState {
  layers: MapLayer[];
  statuses: SpaceStatus[];
  period: PressurePeriod;
  selectedId: string | null;
}
