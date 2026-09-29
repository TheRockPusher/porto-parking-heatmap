import { useCallback, useEffect, useReducer, useRef } from "react";
import type { FeatureCollection, Polygon } from "geojson";
import { pressureToGeoJSON } from "../lib/pressure";
import type {
  AttributeTable,
  DataManifest,
  DatasetName,
  DatasetStatus,
  LayerKind,
  ParkingCollections,
  PressureCellProperties,
  PressureColumns,
  PressureData,
} from "../types";

type PressureGeoJSON = FeatureCollection<Polygon, PressureCellProperties>;

/** Fetch order: the pressure grid is the default visible layer, then inventory layers by size. */
const DATASET_ORDER: DatasetName[] = ["pressure", "zones", "streets", "garages", "spaces"];
const COLUMN_KEYS: Record<keyof PressureColumns, true> = {
  q: true, r: true, coverage: true, zone: true, households: true, householdsWithParking: true,
  residentDemand: true, roadLengthM: true, onStreetEstimate: true, offStreetPublic: true,
  westernActiveSpaces: true, attraction: true, complaints: true, restrictionDays: true,
  overnightRatio: true, daytimeRatio: true, overnightIndex: true, daytimeIndex: true,
};

interface State {
  manifest: DataManifest | null;
  collections: Partial<ParkingCollections>;
  pressure: PressureData | null;
  pressureGeoJSON: PressureGeoJSON | null;
  status: Record<DatasetName, DatasetStatus>;
  error: string | null;
}

type Action =
  | { type: "reset" }
  | { type: "manifest"; manifest: DataManifest }
  | { type: "manifestFailed"; message: string }
  | { type: "collection"; kind: LayerKind; collection: ParkingCollections[LayerKind] }
  | { type: "pressure"; pressure: PressureData; geojson: PressureGeoJSON }
  | { type: "datasetFailed"; name: DatasetName; message: string };

const INITIAL_STATE: State = {
  manifest: null,
  collections: {},
  pressure: null,
  pressureGeoJSON: null,
  status: { pressure: "loading", zones: "loading", streets: "loading", garages: "loading", spaces: "loading" },
  error: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "reset":
      return INITIAL_STATE;
    case "manifest":
      return { ...state, manifest: action.manifest };
    case "manifestFailed":
      return {
        ...state,
        status: { pressure: "error", zones: "error", streets: "error", garages: "error", spaces: "error" },
        error: action.message,
      };
    case "collection":
      return {
        ...state,
        collections: { ...state.collections, [action.kind]: action.collection } as Partial<ParkingCollections>,
        status: { ...state.status, [action.kind]: "ready" },
      };
    case "pressure":
      return {
        ...state,
        pressure: action.pressure,
        pressureGeoJSON: action.geojson,
        status: { ...state.status, pressure: "ready" },
      };
    case "datasetFailed":
      return {
        ...state,
        status: { ...state.status, [action.name]: "error" },
        error: state.error ?? action.message,
      };
  }
}

async function fetchJson(path: string, label: string, signal: AbortSignal, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`${import.meta.env.BASE_URL}${path}`, { ...init, signal });
  if (!response.ok) throw new Error(`${label} request returned HTTP ${response.status}.`);
  try {
    return await response.json();
  } catch {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    throw new Error(`${label} is not valid JSON.`);
  }
}

function validPath(value: unknown): value is string {
  // Paths are relative to the site base URL; never follow absolute or protocol-relative URLs.
  return typeof value === "string" && value.length > 0 && !/^([a-z][a-z0-9+.-]*:|\/\/)/i.test(value);
}

function validateManifest(value: unknown): DataManifest {
  const bad = () => new Error("The parking data manifest has an unsupported format.");
  const manifest = value as Partial<DataManifest> | null;
  const datasets = manifest?.datasets as Partial<Record<DatasetName, { path?: unknown; attributesPath?: unknown }>> | undefined;
  if (manifest?.schemaVersion !== 2 || typeof datasets !== "object" || datasets === null || !Array.isArray(manifest.sources)) {
    throw bad();
  }
  for (const name of DATASET_ORDER) {
    const entry = datasets[name];
    if (!validPath(entry?.path)) throw bad();
    if (name !== "pressure" && !validPath(entry?.attributesPath)) throw bad();
  }
  return manifest as DataManifest;
}

function validateCollection(value: unknown, kind: LayerKind): ParkingCollections[LayerKind] {
  const collection = value as Partial<FeatureCollection> | null;
  if (collection?.type !== "FeatureCollection" || !Array.isArray(collection.features)) {
    throw new Error(`The ${kind} dataset has an unsupported format.`);
  }
  return collection as ParkingCollections[LayerKind];
}

function validatePressure(value: unknown): PressureData {
  const bad = (detail: string) => new Error(`The pressure dataset has an unsupported format (${detail}).`);
  const data = value as Partial<PressureData> | null;
  if (data?.schemaVersion !== 2) throw bad("schema version");
  const grid = data.grid;
  if (
    grid?.type !== "hex-axial-pointy" ||
    typeof grid.circumradiusM !== "number" || !(grid.circumradiusM > 0) ||
    typeof grid.earthRadiusM !== "number" || !(grid.earthRadiusM > 0) ||
    !Array.isArray(grid.origin) || grid.origin.length !== 2 ||
    !grid.origin.every((n) => typeof n === "number" && Number.isFinite(n))
  ) {
    throw bad("grid");
  }
  if (!Array.isArray(data.periods) || typeof data.method !== "object" || data.method === null) throw bad("method");
  const cells = data.cells as Record<string, unknown> | undefined;
  if (typeof cells !== "object" || cells === null) throw bad("cells");
  let length = -1;
  for (const key of Object.keys(COLUMN_KEYS)) {
    const column = cells[key];
    if (!Array.isArray(column)) throw bad(`missing column ${key}`);
    if (length === -1) length = column.length;
    else if (column.length !== length) throw bad("columns differ in length");
  }
  return data as PressureData;
}

function validateAttributes(value: unknown, kind: LayerKind): AttributeTable {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`The ${kind} attribute table has an unsupported format.`);
  }
  return value as AttributeTable;
}

interface Session {
  controller: AbortController;
  manifest: Promise<DataManifest>;
  attributes: Map<LayerKind, Promise<AttributeTable>>;
}

export function useParkingData() {
  const [attempt, retryLoad] = useReducer((value: number) => value + 1, 0);
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const sessionRef = useRef<Session | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const manifest = fetchJson("data/manifest.json", "The data manifest", signal, { cache: "no-cache" })
      .then(validateManifest);
    // Failures are reported through the dispatch below and through loadAttributes callers.
    manifest.catch(() => undefined);
    const session: Session = { controller, manifest, attributes: new Map() };
    sessionRef.current = session;
    dispatch({ type: "reset" });

    async function loadDataset(name: DatasetName, entry: DataManifest["datasets"]) {
      try {
        const raw = await fetchJson(entry[name].path, `The ${name} dataset`, signal);
        if (name === "pressure") {
          const pressure = validatePressure(raw);
          const geojson = pressureToGeoJSON(pressure);
          if (!signal.aborted) dispatch({ type: "pressure", pressure, geojson });
        } else {
          const collection = validateCollection(raw, name);
          if (!signal.aborted) dispatch({ type: "collection", kind: name, collection });
        }
      } catch (error) {
        if (signal.aborted) return;
        dispatch({
          type: "datasetFailed",
          name,
          message: error instanceof Error ? error.message : `The ${name} dataset could not be read.`,
        });
      }
    }

    manifest.then(
      (loaded) => {
        if (signal.aborted) return;
        dispatch({ type: "manifest", manifest: loaded });
        for (const name of DATASET_ORDER) void loadDataset(name, loaded.datasets);
      },
      (error: unknown) => {
        if (signal.aborted) return;
        dispatch({
          type: "manifestFailed",
          message: error instanceof Error ? error.message : "The parking data manifest could not be read.",
        });
      },
    );

    return () => {
      controller.abort();
      if (sessionRef.current === session) sessionRef.current = null;
    };
  }, [attempt]);

  const loadAttributes = useCallback((kind: LayerKind): Promise<AttributeTable> => {
    const session = sessionRef.current;
    if (!session) return Promise.reject(new Error("Parking data is not available."));
    const cached = session.attributes.get(kind);
    if (cached) return cached;
    const promise = session.manifest.then(async (manifest) => {
      const raw = await fetchJson(manifest.datasets[kind].attributesPath, `The ${kind} attribute table`, session.controller.signal);
      return validateAttributes(raw, kind);
    });
    session.attributes.set(kind, promise);
    // Never cache a rejection: a failed load can be retried by calling loadAttributes again.
    promise.catch(() => {
      if (session.attributes.get(kind) === promise) session.attributes.delete(kind);
    });
    return promise;
  }, []);

  const complete = DATASET_ORDER.every((name) => state.status[name] === "ready");

  return {
    manifest: state.manifest,
    collections: state.collections,
    pressure: state.pressure,
    pressureGeoJSON: state.pressureGeoJSON,
    status: state.status,
    complete,
    error: state.error,
    retry: retryLoad,
    loadAttributes,
  };
}
