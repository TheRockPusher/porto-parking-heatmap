import type { ExplorerState, LayerKind, ParkingFeature, SpaceStatus } from "../types";

export const LAYER_KINDS: LayerKind[] = ["zones", "streets", "spaces", "garages"];
export const SPACE_STATUSES: SpaceStatus[] = ["active", "inactive", "unknown"];
export const DEFAULT_STATE: ExplorerState = {
  layers: ["zones", "streets", "garages"],
  statuses: ["active"],
  selectedId: null,
};
export const LAYER_LABELS: Record<LayerKind, string> = {
  zones: "Tariff zones",
  streets: "Paid streets",
  spaces: "Western paid spaces",
  garages: "Municipal garages",
};
export const FEATURE_LABELS: Record<LayerKind, string> = {
  zones: "Tariff zone",
  streets: "Paid street",
  spaces: "Western paid space",
  garages: "Municipal garage",
};
export const STATUS_LABELS: Record<SpaceStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  unknown: "Unknown",
};
export const ZONE_COLORS: Record<string, string> = {
  I: "#2765b0",
  II: "#087f83",
  III: "#b67810",
  IV: "#8355b6",
};

const currency = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
const date = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export function formatRate(value: number | null): string {
  return value === null ? "Not provided" : currency.format(value);
}

export function formatDate(value: string): string {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? value || "Not provided" : date.format(timestamp);
}

export function featureName(feature: ParkingFeature): string {
  return feature.properties.name || `Unnamed ${FEATURE_LABELS[feature.properties.kind].toLowerCase()}`;
}

export function normalizeSearch(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("pt-PT").trim();
}
