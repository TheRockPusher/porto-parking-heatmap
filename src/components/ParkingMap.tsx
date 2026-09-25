import { Component, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Map, Source, Layer, NavigationControl, ScaleControl } from "react-map-gl/maplibre";
import type { MapRef } from "react-map-gl/maplibre";
import type { ExpressionSpecification, StyleSpecification } from "maplibre-gl";
import type { Geometry } from "geojson";
import { RotateCcw } from "lucide-react";
import { ZONE_COLORS } from "../lib/parking";
import type { LayerKind, ParkingData, ParkingFeature, SpaceStatus } from "../types";
import "maplibre-gl/dist/maplibre-gl.css";

const PORTO_VIEW = { longitude: -8.635, latitude: 41.157, zoom: 12.7, bearing: 0, pitch: 0 };
const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    basemap: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#e8eee9" } },
    { id: "basemap", type: "raster", source: "basemap", paint: { "raster-saturation": -0.5, "raster-opacity": 0.85 } },
  ],
};
const ZONE_COLOR: ExpressionSpecification = [
  "match", ["get", "zone"],
  "I", ZONE_COLORS.I, "II", ZONE_COLORS.II,
  "III", ZONE_COLORS.III, "IV", ZONE_COLORS.IV, "#667085",
];
const INTERACTIVE_LAYERS: Record<LayerKind, string> = {
  zones: "tariff-zones", streets: "paid-streets", spaces: "paid-spaces", garages: "municipal-garages",
};

function geometryBounds(geometry: Geometry): [[number, number], [number, number]] {
  const bounds: [[number, number], [number, number]] = [[Infinity, Infinity], [-Infinity, -Infinity]];
  function visitCoordinates(value: unknown) {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === "number" && typeof value[1] === "number") {
      bounds[0][0] = Math.min(bounds[0][0], value[0]);
      bounds[0][1] = Math.min(bounds[0][1], value[1]);
      bounds[1][0] = Math.max(bounds[1][0], value[0]);
      bounds[1][1] = Math.max(bounds[1][1], value[1]);
    } else {
      value.forEach(visitCoordinates);
    }
  }
  function visitGeometry(value: Geometry) {
    if (value.type === "GeometryCollection") value.geometries.forEach(visitGeometry);
    else visitCoordinates(value.coordinates);
  }
  visitGeometry(geometry);
  return bounds;
}

interface ParkingMapProps {
  data: ParkingData;
  layers: LayerKind[];
  statuses: SpaceStatus[];
  selected: ParkingFeature | null;
  resetKey: number;
  onSelect: (id: string) => void;
}

class MapBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="map-fallback" role="status">
          <h2>The map could not start</h2>
          <p>WebGL may be unavailable in this browser. All parking records, search results and source details are still available in the explorer.</p>
          <button className="button" onClick={() => this.setState({ failed: false })}>Try the map again</button>
        </div>
      );
    }
    return this.props.children;
  }
}

function PortoMap({ data, layers, statuses, selected, resetKey, onSelect }: ParkingMapProps) {
  const map = useRef<MapRef>(null);
  const [ready, setReady] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [hovering, setHovering] = useState(false);
  const [tileAttempt, setTileAttempt] = useState(0);
  const visibleSpaces = useMemo(() => ({
    ...data.collections.spaces,
    features: data.collections.spaces.features.filter((feature) => statuses.includes(feature.properties.status)),
  }), [data, statuses]);
  const selectedData = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: selected ? [selected] : [],
  }), [selected]);

  useEffect(() => {
    if (ready) map.current?.jumpTo(PORTO_VIEW);
  }, [resetKey, ready]);
  useEffect(() => {
    if (!ready || !selected || !map.current) return;
    const bounds = geometryBounds(selected.geometry);
    if (bounds.flat().every(Number.isFinite)) {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      map.current.fitBounds(bounds, { padding: 72, maxZoom: 17, duration: reducedMotion ? 0 : 650 });
    }
  }, [selected, ready]);


  return (
    <>
      <Map
        key={tileAttempt}
        ref={map}
        initialViewState={PORTO_VIEW}
        mapStyle={MAP_STYLE}
        minZoom={10}
        maxZoom={20}
        maxBounds={[[-8.85, 41.05], [-8.45, 41.27]]}
        dragRotate={false}
        touchPitch={false}
        attributionControl={{ compact: false }}
        interactiveLayerIds={layers.map((kind) => INTERACTIVE_LAYERS[kind])}
        cursor={hovering ? "pointer" : "grab"}
        onLoad={() => setReady(true)}
        onError={() => setMapError(true)}
        onMouseMove={(event) => setHovering(Boolean(event.features?.length))}
        onMouseLeave={() => setHovering(false)}
        onClick={(event) => {
          const feature = event.features?.[0];
          if (feature?.properties?.id) onSelect(String(feature.properties.id));
        }}
      >
        <NavigationControl position="top-right" showCompass={false} />
        <ScaleControl position="bottom-left" unit="metric" />
        <Source id="zones" type="geojson" data={data.collections.zones}>
          <Layer id="tariff-zones" type="fill" layout={{ visibility: layers.includes("zones") ? "visible" : "none" }} paint={{ "fill-color": ZONE_COLOR, "fill-opacity": 0.19 }} />
          <Layer id="tariff-outlines" type="line" layout={{ visibility: layers.includes("zones") ? "visible" : "none" }} paint={{ "line-color": ZONE_COLOR, "line-width": 1.6, "line-opacity": 0.7 }} />
        </Source>
        <Source id="streets" type="geojson" data={data.collections.streets}>
          <Layer id="paid-streets" type="line" layout={{ visibility: layers.includes("streets") ? "visible" : "none", "line-cap": "round" }} paint={{ "line-color": "#243f59", "line-width": ["interpolate", ["linear"], ["zoom"], 11, 2, 16, 5] }} />
        </Source>
        <Source id="spaces" type="geojson" data={visibleSpaces}>
          <Layer id="paid-spaces" type="circle" layout={{ visibility: layers.includes("spaces") ? "visible" : "none" }} paint={{
            "circle-color": ["match", ["get", "status"], "active", "#0b7272", "inactive", "#925629", "#727a84"],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 2.5, 16, 5],
            "circle-stroke-color": "#fff", "circle-stroke-width": 1,
          }} />
        </Source>
        <Source id="garages" type="geojson" data={data.collections.garages}>
          <Layer id="municipal-garages" type="circle" layout={{ visibility: layers.includes("garages") ? "visible" : "none" }} paint={{ "circle-color": "#cf652d", "circle-radius": 7, "circle-stroke-color": "#fff", "circle-stroke-width": 2.5 }} />
        </Source>
        <Source id="selection" type="geojson" data={selectedData}>
          <Layer id="selected-area" type="fill" filter={["==", ["geometry-type"], "Polygon"]} paint={{ "fill-color": "#132d46", "fill-opacity": 0.09 }} />
          <Layer id="selected-line" type="line" filter={["!=", ["geometry-type"], "Point"]} paint={{ "line-color": "#152c46", "line-width": 4, "line-dasharray": [2, 1] }} />
          <Layer id="selected-point" type="circle" filter={["==", ["geometry-type"], "Point"]} paint={{ "circle-color": "#fff", "circle-opacity": 0, "circle-radius": 12, "circle-stroke-color": "#132d46", "circle-stroke-width": 3 }} />
        </Source>
      </Map>
      {mapError && (
        <div className="map-resource-warning" role="status">
          <span>Some map resources could not load. Local parking search and details still work.</span>
          <button onClick={() => { setReady(false); setMapError(false); setTileAttempt((value) => value + 1); }}>
            <RotateCcw size={14} aria-hidden="true" /> Retry map
          </button>
        </div>
      )}
    </>
  );
}

export function ParkingMap(props: ParkingMapProps) {
  return <MapBoundary><PortoMap {...props} /></MapBoundary>;
}
