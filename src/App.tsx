import { useMemo, useState } from "react";
import type { FeatureCollection, Geometry } from "geojson";
import { Database, ExternalLink, Info, Layers, MapPin, RotateCcw, Search, X } from "lucide-react";
import { ParkingMap } from "./components/ParkingMap";
import { FeatureDetails } from "./components/FeatureDetails";
import { PressureDetails } from "./components/PressureDetails";
import { PressurePanel } from "./components/PressurePanel";
import { SourcePanel } from "./components/SourcePanel";
import { useParkingData } from "./hooks/useParkingData";
import { useUrlState } from "./hooks/useUrlState";
import {
  DEFAULT_STATE, FEATURE_LABELS, LAYER_KINDS, LAYER_LABELS, MAP_LAYERS, MAP_LAYER_LABELS, SPACE_STATUSES,
  STATUS_LABELS, ZONE_COLORS, featureName, formatDate, formatRate, normalizeSearch,
} from "./lib/parking";
import type { DatasetName, LayerKind, MapLayer, ParkingFeature, ParkingProperties, PressurePeriod, SpaceStatus } from "./types";

const RULES_URL = "https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/estacionamento-1";
const TARIFF_URL = "https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/pagamento-das-taxas-e-informacoes";

const LAYER_HINTS: Record<MapLayer, string> = {
  pressure: "Estimated relative pressure, not occupancy",
  zones: "One-hour price references",
  streets: "Paid road segments, not capacity",
  spaces: "Western area only",
  garages: "Facilities, not free-space counts",
};

function indexCollection(collection: FeatureCollection<Geometry, ParkingProperties> | undefined) {
  return (collection?.features ?? []).map((feature) => ({
    feature: feature as ParkingFeature,
    text: normalizeSearch([
      feature.properties.name,
      FEATURE_LABELS[feature.properties.kind],
      feature.properties.id,
      feature.properties.kind === "garages" ? feature.properties.address : "",
    ].filter(Boolean).join(" ")),
  }));
}

function App() {
  const { manifest, collections, pressure, pressureGeoJSON, status, complete, error, retry, loadAttributes } = useParkingData();
  const [state, setState] = useUrlState();
  const [query, setQuery] = useState("");
  const [searchKind, setSearchKind] = useState<LayerKind | "all">("all");
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [resetKey, setResetKey] = useState(0);

  const zoneEntries = useMemo(() => indexCollection(collections.zones), [collections.zones]);
  const streetEntries = useMemo(() => indexCollection(collections.streets), [collections.streets]);
  const spaceEntries = useMemo(() => indexCollection(collections.spaces), [collections.spaces]);
  const garageEntries = useMemo(() => indexCollection(collections.garages), [collections.garages]);
  const searchIndex = useMemo(
    () => [...zoneEntries, ...streetEntries, ...spaceEntries, ...garageEntries],
    [zoneEntries, streetEntries, spaceEntries, garageEntries],
  );
  const featureIndex = useMemo(() => new Map(searchIndex.map(({ feature }) => [feature.properties.id, feature])), [searchIndex]);
  const pressureIndex = useMemo(
    () => new Map((pressureGeoJSON?.features ?? []).map((feature) => [feature.properties.id, feature])),
    [pressureGeoJSON],
  );
  const searchTerm = normalizeSearch(query);
  const browsing = searchTerm.length > 0 || searchKind !== "all";
  const results = useMemo(() => {
    if (!browsing) return [];
    const words = searchTerm.split(/\s+/).filter(Boolean);
    return searchIndex.filter(({ feature, text }) =>
      (searchKind === "all" || feature.properties.kind === searchKind) && words.every((word) => text.includes(word)),
    ).map(({ feature }) => feature).sort((a, b) =>
      Number(b.properties.kind === "garages") - Number(a.properties.kind === "garages") ||
      featureName(a).localeCompare(featureName(b), "pt") || a.properties.id.localeCompare(b.properties.id),
    );
  }, [browsing, searchIndex, searchKind, searchTerm]);

  const selectedId = state.selectedId;
  const selectedInventory = selectedId ? featureIndex.get(selectedId) ?? null : null;
  const selectedPressure = selectedId ? pressureIndex.get(selectedId) ?? null : null;
  const selectedInventoryVisible = selectedInventory && state.layers.includes(selectedInventory.properties.kind) &&
    (selectedInventory.properties.kind !== "spaces" || state.statuses.includes(selectedInventory.properties.status));
  const selectedPressureVisible = selectedPressure && state.layers.includes("pressure");
  const selectedKind: MapLayer | null = selectedInventory?.properties.kind ?? (selectedPressure ? "pressure" : null);
  const selectedMapFeature = selectedInventoryVisible ? selectedInventory : selectedPressureVisible ? selectedPressure : null;
  const missingKind = selectedId?.split(":")[0] as DatasetName | undefined;
  const selectionMissing = Boolean(selectedId && !selectedKind && missingKind && status[missingKind] === "ready");

  const statusCounts = useMemo(() => {
    const counts: Record<SpaceStatus, number> = { active: 0, inactive: 0, unknown: 0 };
    collections.spaces?.features.forEach((feature) => { counts[feature.properties.status] += 1; });
    return counts;
  }, [collections.spaces]);
  const tariffs = useMemo(() => {
    const rates = new Map<string, number | null>();
    collections.zones?.features.forEach((feature) => {
      if (feature.properties.zone) rates.set(feature.properties.zone, feature.properties.hourlyRate);
    });
    const order = ["I", "II", "III", "IV"];
    return Array.from(rates).sort(([a], [b]) => order.indexOf(a) - order.indexOf(b));
  }, [collections.zones]);

  function selectFeature(id: string) {
    const cell = pressureIndex.get(id);
    if (cell) {
      setState((previous) => ({
        ...previous,
        selectedId: id,
        layers: previous.layers.includes("pressure") ? previous.layers : [...previous.layers, "pressure"],
      }));
      return;
    }
    const feature = featureIndex.get(id);
    if (!feature) return;
    const properties = feature.properties;
    setState((previous) => ({
      ...previous,
      selectedId: id,
      layers: previous.layers.includes(properties.kind) ? previous.layers : [...previous.layers, properties.kind],
      statuses: properties.kind === "spaces" && !previous.statuses.includes(properties.status)
        ? [...previous.statuses, properties.status] : previous.statuses,
    }));
  }

  function toggleLayer(layer: MapLayer) {
    setState((previous) => ({
      ...previous,
      layers: previous.layers.includes(layer) ? previous.layers.filter((item) => item !== layer) : [...previous.layers, layer],
    }));
  }

  function setPeriod(period: PressurePeriod) {
    setState((previous) => ({ ...previous, period }));
  }

  function reset() {
    setState(DEFAULT_STATE);
    setQuery("");
    setSearchKind("all");
    setResetKey((value) => value + 1);
  }

  const anyLoaded = searchIndex.length > 0 || LAYER_KINDS.some((kind) => collections[kind]);
  const loadingMessage = !manifest && !error;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#explorer">Skip to parking explorer</a>
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><MapPin size={26} /></div>
          <div><span className="eyebrow">Porto · Portugal</span><h1>Parking atlas</h1></div>
        </div>
        <p className="header-description">Estimated parking pressure & supply.<br /><span>Relative estimates, not availability.</span></p>
        <div className="header-actions">
          <button className="button" aria-label="Reset view" onClick={reset}><RotateCcw size={16} aria-hidden="true" /><span>Reset view</span></button>
          <button className="button button-primary" disabled={!manifest} onClick={() => setSourcesOpen(true)}><Database size={16} aria-hidden="true" /><span>Sources & method</span></button>
        </div>
      </header>
      <div className="availability-notice">
        <Info size={18} aria-hidden="true" />
        <p><strong>Estimated parking pressure — not live availability or occupancy.</strong> Hexagons rank estimated demand against estimated supply from open data; inventory and tariff records are historical references. No free-space counts and no “best time to park”.</p>
      </div>
      <main className="workspace">
        <aside className="explorer" id="explorer" aria-label="Parking explorer" tabIndex={-1}>
          <section className="search-section" aria-labelledby="search-heading">
            <span className="eyebrow">Explore the city</span>
            <h2 id="search-heading">Find a place to understand</h2>
            <div className="search-input">
              <Search size={18} aria-hidden="true" />
              <label className="sr-only" htmlFor="parking-search">Search parking records</label>
              <input id="parking-search" type="search" value={query} disabled={!anyLoaded} placeholder="Try Trindade or Boavista" onChange={(event) => setQuery(event.target.value)} aria-describedby="search-help" />
              {query && <button className="icon-button" onClick={() => setQuery("")} aria-label="Clear search"><X size={16} aria-hidden="true" /></button>}
            </div>
            <div className="search-scope">
              <label htmlFor="search-kind">Browse</label>
              <select id="search-kind" value={searchKind} disabled={!anyLoaded} onChange={(event) => setSearchKind(event.target.value as LayerKind | "all")}>
                <option value="all">All record types</option>
                {LAYER_KINDS.map((kind) => <option key={kind} value={kind}>{LAYER_LABELS[kind]}</option>)}
              </select>
            </div>
            <p id="search-help" className="helper-text">Local records, with or without accents. Search includes hidden layers and statuses; selecting a result reveals it. Pressure cells are selected on the map.</p>
            {browsing && anyLoaded && <div className="search-results">
              <p className="result-count" role="status">{results.length.toLocaleString("en-GB")} matching {results.length === 1 ? "record" : "records"}{results.length > 30 ? " · first 30 shown" : ""}</p>
              {!complete && !error && <p className="helper-text loading-note">Some records are still loading; results may be incomplete.</p>}
              {results.length === 0 ? <p className="empty-search">No matching records. Try a street or garage name, or change the record type. This is not an address geocoder.</p> :
                <ul aria-label="Parking search results">{results.slice(0, 30).map((feature) => (
                  <li key={feature.properties.id}>
                    <button className={selectedId === feature.properties.id ? "result-button selected" : "result-button"} onClick={() => selectFeature(feature.properties.id)} aria-pressed={selectedId === feature.properties.id}>
                      <span className={`result-dot dot-${feature.properties.kind}`} aria-hidden="true" />
                      <span><strong>{featureName(feature)}</strong><small>{FEATURE_LABELS[feature.properties.kind]} · {feature.properties.id}{feature.properties.kind === "spaces" ? ` · ${STATUS_LABELS[feature.properties.status]}` : ""}</small></span>
                    </button>
                  </li>
                ))}</ul>}
              {results.length > 30 && <p className="helper-text">Refine your search to find other records.</p>}
            </div>}
          </section>

          {selectedKind && <>
            {!(selectedInventoryVisible || selectedPressureVisible) && <p className="hidden-selection">This record is hidden by a map filter. <button onClick={() => selectFeature(selectedId!)}>Show it on the map</button></p>}
            {selectedInventory
              ? <FeatureDetails feature={selectedInventory} source={manifest?.sources.find((source) => source.id === selectedInventory.properties.kind)} loadAttributes={loadAttributes} onClose={() => setState((previous) => ({ ...previous, selectedId: null }))} />
              : selectedPressure && <PressureDetails cell={selectedPressure.properties} method={pressure?.method ?? null} onClose={() => setState((previous) => ({ ...previous, selectedId: null }))} />}
          </>}
          {selectionMissing && <p className="hidden-selection">The shared record is not in this snapshot. <button onClick={() => setState((previous) => ({ ...previous, selectedId: null }))}>Clear selection</button></p>}
          {selectedId && !selectedKind && !selectionMissing && !error && <p className="hidden-selection" role="status">Loading the shared record…</p>}

          <PressurePanel
            period={state.period}
            status={status.pressure}
            cellCount={manifest?.datasets.pressure.cellCount ?? null}
            visible={state.layers.includes("pressure")}
            onPeriod={setPeriod}
            onShow={() => toggleLayer("pressure")}
            onOpenMethod={() => setSourcesOpen(true)}
          />

          <section className="layers-section" aria-labelledby="layers-heading">
            <div className="section-heading"><h2 id="layers-heading"><Layers size={17} aria-hidden="true" /> Map layers</h2><span className="quiet-label">{complete ? "Snapshot records" : "Loading records…"}</span></div>
            {!complete && !error && <p className="helper-text loading-note" role="status">Some records are still loading. Layers appear on the map as they arrive.</p>}
            <fieldset className="layer-controls" disabled={!manifest}>
              <legend className="sr-only">Visible map layers</legend>
              {MAP_LAYERS.map((layer) => {
                const count = manifest ? (layer === "pressure" ? manifest.datasets.pressure.cellCount : manifest.datasets[layer].featureCount) : null;
                const layerStatus = status[layer];
                return (
                  <label className="layer-option" key={layer}>
                    <input type="checkbox" checked={state.layers.includes(layer)} onChange={() => toggleLayer(layer)} />
                    <span className={`layer-symbol symbol-${layer}`} aria-hidden="true" />
                    <span>{MAP_LAYER_LABELS[layer]}<small>{LAYER_HINTS[layer]}</small></span>
                    <span className="layer-count">{layerStatus === "error" ? "Failed" : layerStatus !== "ready" || count === null ? "Loading…" : count.toLocaleString("en-GB")}</span>
                  </label>
                );
              })}
            </fieldset>
            <fieldset className="status-controls" disabled={!collections.spaces}>
              <legend>Western space inventory status</legend>
              <div className="status-options">{SPACE_STATUSES.map((spaceStatus) => (
                <label key={spaceStatus}>
                  <input type="checkbox" checked={state.statuses.includes(spaceStatus)} onChange={() => setState((previous) => ({ ...previous, statuses: previous.statuses.includes(spaceStatus) ? previous.statuses.filter((item) => item !== spaceStatus) : [...previous.statuses, spaceStatus] }))} />
                  <span className={`status-dot status-${spaceStatus}`} aria-hidden="true" />
                  <span>{STATUS_LABELS[spaceStatus]}<small>{collections.spaces ? statusCounts[spaceStatus].toLocaleString("en-GB") : "—"}</small></span>
                </label>
              ))}</div>
              <p className="helper-text">“Active” does not mean vacant. {state.layers.includes("spaces") ? `${state.statuses.reduce((sum, item) => sum + statusCounts[item], 0).toLocaleString("en-GB")} space records shown.` : "Enable Western paid spaces to see these records."}</p>
            </fieldset>
          </section>

          <section className="tariff-legend" aria-labelledby="tariff-heading">
            <div className="section-heading"><h2 id="tariff-heading">Tariff classes</h2><span className="quiet-label">One hour · EUR</span></div>
            <div className="tariff-items">{tariffs.map(([zone, rate]) => (
              <div key={zone}><span className="zone-swatch" style={{ backgroundColor: ZONE_COLORS[zone] ?? "#667085" }} aria-hidden="true" /><span>Zone {zone}</span><strong>{formatRate(rate)}</strong></div>
            ))}</div>
            <p className="helper-text">Colors identify tariff classes, never demand or availability. Source references are historical; longer stays are not a simple hourly multiplication.</p>
          </section>

          <details className="rules-section">
            <summary>Parking rules & important exceptions</summary>
            <div className="rules-content">
              <h3>Check the signs before you park</h3>
              <p>Official municipal guidance lists paid hours for zones I–IV as weekdays 09:00–19:00; Zone I also Saturday 11:00–16:00. Public holidays are excluded.</p>
              <p>Maximum stays depend on signage (generally 2–10 hours). Longer-duration prices are not always linear: the published Zone II tariff includes €2.00 for four hours and €3.60 for a day.</p>
              <p>Resident permits apply only in the authorized area. Disability-badge exemptions and their conditions also matter. These records do not determine your eligibility.</p>
              <p>Movida restrictions apply on specified streets on Friday, Saturday and holiday eves, 20:00–08:00. Outside paid hours does not mean unrestricted parking.</p>
              <a href={RULES_URL} target="_blank" rel="noreferrer">Official hours & rules <ExternalLink size={13} aria-hidden="true" /></a>
              <a href={TARIFF_URL} target="_blank" rel="noreferrer">Official payment & tariff information <ExternalLink size={13} aria-hidden="true" /></a>
            </div>
          </details>
          <footer className="explorer-footer">
            <p>Municipal and open data, estimates clearly separated from live conditions.</p>
            {manifest && <p>Snapshot assembled {formatDate(manifest.generatedAt)}. <button onClick={() => setSourcesOpen(true)}>See sources, reference dates and method</button>.</p>}
          </footer>
        </aside>

        <section className="map-panel" aria-label="Porto parking map">
          <div className="map-heading"><span className="map-location"><MapPin size={15} aria-hidden="true" /> Porto</span><span>Estimated pressure & supply</span></div>
          {manifest && <ParkingMap collections={collections} pressureGeoJSON={pressureGeoJSON} period={state.period} layers={state.layers} statuses={state.statuses} selected={selectedMapFeature} resetKey={resetKey} onSelect={selectFeature} />}
          {loadingMessage && <div className="map-message" role="status"><span className="loading-spinner" /><h2>Loading Porto’s parking records</h2><p>Opening the bundled snapshot. No live availability is requested.</p></div>}
          {error && !manifest && <div className="map-message error-message" role="alert"><Database size={32} aria-hidden="true" /><h2>Parking data could not load</h2><p>{error}</p><p>Check your connection and retry. If this persists, the site’s bundled snapshot may be missing or invalid.</p><button className="button button-primary" onClick={retry}><RotateCcw size={16} aria-hidden="true" /> Retry parking data</button></div>}
          {error && manifest && <div className="map-resource-warning data-warning" role="alert"><span>Some parking data could not load: {error}</span><button onClick={retry}><RotateCcw size={14} aria-hidden="true" /> Retry parking data</button></div>}
          {manifest && !state.layers.length && <p className="map-empty-notice">All parking layers are hidden. Enable a layer in the explorer.</p>}
          {manifest && <div className="map-caption"><span>Click a cell or feature to inspect it</span><strong>Estimate ≠ availability</strong></div>}
        </section>
      </main>
      {manifest && <SourcePanel manifest={manifest} method={pressure?.method ?? null} open={sourcesOpen} onClose={() => setSourcesOpen(false)} />}
    </div>
  );
}

export default App;
