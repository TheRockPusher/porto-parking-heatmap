import type { Feature, FeatureCollection, Geometry } from "geojson";

export type LayerKind = "streets" | "zones" | "spaces" | "garages";
export type SpaceStatus = "active" | "inactive" | "unknown";

interface BaseProperties {
  id: string;
  name: string | null;
  sourceId: LayerKind;
  attributes: Record<string, unknown>;
}

export interface StreetProperties extends BaseProperties {
  kind: "streets";
}

export interface ZoneProperties extends BaseProperties {
  kind: "zones";
  zone: string;
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

export interface ParkingSource {
  id: LayerKind;
  name: string;
  url: string;
  metadataUrl: string;
  license: string;
  referenceDate: string;
  retrievedAt: string;
  featureCount: number;
  caveat: string;
}

export interface ParkingData {
  schemaVersion: 1;
  generatedAt: string;
  sources: ParkingSource[];
  collections: {
    streets: FeatureCollection<Geometry, StreetProperties>;
    zones: FeatureCollection<Geometry, ZoneProperties>;
    spaces: FeatureCollection<Geometry, SpaceProperties>;
    garages: FeatureCollection<Geometry, GarageProperties>;
  };
}

export interface ExplorerState {
  layers: LayerKind[];
  statuses: SpaceStatus[];
  selectedId: string | null;
}
