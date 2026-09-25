import { useMemo, useState } from "react";
import { Database, ExternalLink, Info, Layers, MapPin, RotateCcw, Search, X } from "lucide-react";
import { ParkingMap } from "./components/ParkingMap";
import { FeatureDetails } from "./components/FeatureDetails";
import { SourcePanel } from "./components/SourcePanel";
import { useParkingData } from "./hooks/useParkingData";
import { useUrlState } from "./hooks/useUrlState";
import {
  DEFAULT_STATE, FEATURE_LABELS, LAYER_KINDS, LAYER_LABELS, SPACE_STATUSES,
  STATUS_LABELS, ZONE_COLORS, featureName, formatDate, formatRate, normalizeSearch,
} from "./lib/parking";
import type { LayerKind, ParkingFeature, SpaceStatus } from "./types";

const RULES_URL = "https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/estacionamento-1";
const TARIFF_URL = "https://mobilidade.cm-porto.pt/estacionamento-na-via-publica/pagamento-das-taxas-e-informacoes";

function App() {
  const { data, loading, error, retry } = useParkingData();
  const [state, setState] = useUrlState();
  const [query, setQuery] = useState("");
  const [searchKind, setSearchKind] = useState<LayerKind | "all">("all");
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [resetKey, setResetKey] = useState(0);

  const features = useMemo(() => {
    const records: ParkingFeature[] = [];
    if (data) for (const kind of LAYER_KINDS) records.push(...data.collections[kind].features);
    return records;
  }, [data]);
  const featureIndex = useMemo(() => new Map(features.map((feature) => [feature.properties.id, feature])), [features]);
  const searchIndex = useMemo(() => features.map((feature) => ({
    feature,
    text: normalizeSearch([
      feature.properties.name,
      FEATURE_LABELS[feature.properties.kind],
      feature.properties.id,
      feature.properties.kind === "garages" ? feature.properties.address : "",
    ].filter(Boolean).join(" ")),
  })), [features]);
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
  const selected = state.selectedId ? featureIndex.get(state.selectedId) ?? null : null;
  const selectedVisible = selected && state.layers.includes(selected.properties.kind) &&
    (selected.properties.kind !== "spaces" || state.statuses.includes(selected.properties.status));
  const statusCounts = useMemo(() => {
    const counts: Record<SpaceStatus, number> = { active: 0, inactive: 0, unknown: 0 };
    data?.collections.spaces.features.forEach((feature) => { counts[feature.properties.status] += 1; });
    return counts;
  }, [data]);
  const tariffs = useMemo(() => {
    const rates = new Map<string, number | null>();
    data?.collections.zones.features.forEach((feature) => rates.set(feature.properties.zone, feature.properties.hourlyRate));
    const order = ["I", "II", "III", "IV"];
    return Array.from(rates).sort(([a], [b]) => order.indexOf(a) - order.indexOf(b));
  }, [data]);

  function selectFeature(id: string) {
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

  function toggleLayer(kind: LayerKind) {
    setState((previous) => ({
      ...previous,
      layers: previous.layers.includes(kind) ? previous.layers.filter((layer) => layer !== kind) : [...previous.layers, kind],
    }));
  }

  function reset() {
    setState(DEFAULT_STATE);
    setQuery("");
    setSearchKind("all");
    setResetKey((value) => value + 1);
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#explorer">Skip to parking explorer</a>
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><MapPin size={26} /></div>
          <div><span className="eyebrow">Porto · Portugal</span><h1>Parking atlas</h1></div>
        </div>
        <p className="header-description">A map of supply & tariffs.<br /><span>Explore the records, not a prediction.</span></p>
        <div className="header-actions">
          <button className="button" aria-label="Reset view" onClick={reset}><RotateCcw size={16} aria-hidden="true" /><span>Reset view</span></button>
          <button className="button button-primary" disabled={!data} onClick={() => setSourcesOpen(true)}><Database size={16} aria-hidden="true" /><span>Sources & dates</span></button>
        </div>
      </header>
      <div className="availability-notice">
        <Info size={18} aria-hidden="true" />
        <p><strong>Not live availability or occupancy.</strong> Historical inventory and tariff references — no free-space counts, demand estimates or “best time to park”.</p>
      </div>
      <main className="workspace">
        <aside className="explorer" id="explorer" aria-label="Parking explorer" tabIndex={-1}>
          <section className="search-section" aria-labelledby="search-heading">
            <span className="eyebrow">Explore the city</span>
            <h2 id="search-heading">Find a place to understand</h2>
            <div className="search-input">
              <Search size={18} aria-hidden="true" />
              <label className="sr-only" htmlFor="parking-search">Search parking records</label>
              <input id="parking-search" type="search" value={query} disabled={!data} placeholder="Try Trindade or Boavista" onChange={(event) => setQuery(event.target.value)} aria-describedby="search-help" />
              {query && <button className="icon-button" onClick={() => setQuery("")} aria-label="Clear search"><X size={16} aria-hidden="true" /></button>}
            </div>
            <div className="search-scope">
              <label htmlFor="search-kind">Browse</label>
              <select id="search-kind" value={searchKind} disabled={!data} onChange={(event) => setSearchKind(event.target.value as LayerKind | "all")}>
                <option value="all">All record types</option>
                {LAYER_KINDS.map((kind) => <option key={kind} value={kind}>{LAYER_LABELS[kind]}</option>)}
              </select>
            </div>
            <p id="search-help" className="helper-text">Local records, with or without accents. Search includes hidden layers and statuses; selecting a result reveals it.</p>
            {browsing && data && <div className="search-results">
              <p className="result-count" role="status">{results.length.toLocaleString("en-GB")} matching {results.length === 1 ? "record" : "records"}{results.length > 30 ? " · first 30 shown" : ""}</p>
              {results.length === 0 ? <p className="empty-search">No matching records. Try a street or garage name, or change the record type. This is not an address geocoder.</p> :
                <ul aria-label="Parking search results">{results.slice(0, 30).map((feature) => (
                  <li key={feature.properties.id}>
                    <button className={selected?.properties.id === feature.properties.id ? "result-button selected" : "result-button"} onClick={() => selectFeature(feature.properties.id)} aria-pressed={selected?.properties.id === feature.properties.id}>
                      <span className={`result-dot dot-${feature.properties.kind}`} aria-hidden="true" />
                      <span><strong>{featureName(feature)}</strong><small>{FEATURE_LABELS[feature.properties.kind]} · {feature.properties.id}{feature.properties.kind === "spaces" ? ` · ${STATUS_LABELS[feature.properties.status]}` : ""}</small></span>
                    </button>
                  </li>
                ))}</ul>}
              {results.length > 30 && <p className="helper-text">Refine your search to find other records.</p>}
            </div>}
          </section>

          {selected && <>
            {!selectedVisible && <p className="hidden-selection">This record is hidden by a map filter. <button onClick={() => selectFeature(selected.properties.id)}>Show it on the map</button></p>}
            <FeatureDetails feature={selected} source={data?.sources.find((source) => source.id === selected.properties.sourceId)} onClose={() => setState((previous) => ({ ...previous, selectedId: null }))} />
          </>}
          {data && state.selectedId && !selected && <p className="hidden-selection">The shared record is not in this snapshot. <button onClick={() => setState((previous) => ({ ...previous, selectedId: null }))}>Clear selection</button></p>}

          <section className="layers-section" aria-labelledby="layers-heading">
            <div className="section-heading"><h2 id="layers-heading"><Layers size={17} aria-hidden="true" /> Map layers</h2><span className="quiet-label">Snapshot records</span></div>
            <fieldset className="layer-controls" disabled={!data}>
              <legend className="sr-only">Visible map layers</legend>
              {LAYER_KINDS.map((kind) => (
                <label className="layer-option" key={kind}>
                  <input type="checkbox" checked={state.layers.includes(kind)} onChange={() => toggleLayer(kind)} />
                  <span className={`layer-symbol symbol-${kind}`} aria-hidden="true" />
                  <span>{LAYER_LABELS[kind]}<small>{kind === "spaces" ? "Western area only" : kind === "streets" ? "Paid road segments, not capacity" : kind === "garages" ? "Facilities, not free-space counts" : "One-hour price references"}</small></span>
                  <span className="layer-count">{data?.collections[kind].features.length.toLocaleString("en-GB") ?? "—"}</span>
                </label>
              ))}
            </fieldset>
            <fieldset className="status-controls" disabled={!data}>
              <legend>Western space inventory status</legend>
              <div className="status-options">{SPACE_STATUSES.map((status) => (
                <label key={status}>
                  <input type="checkbox" checked={state.statuses.includes(status)} onChange={() => setState((previous) => ({ ...previous, statuses: previous.statuses.includes(status) ? previous.statuses.filter((item) => item !== status) : [...previous.statuses, status] }))} />
                  <span className={`status-dot status-${status}`} aria-hidden="true" />
                  <span>{STATUS_LABELS[status]}<small>{data ? statusCounts[status].toLocaleString("en-GB") : "—"}</small></span>
                </label>
              ))}</div>
              <p className="helper-text">“Active” does not mean vacant. {state.layers.includes("spaces") ? `${state.statuses.reduce((sum, status) => sum + statusCounts[status], 0).toLocaleString("en-GB")} space records shown.` : "Enable Western paid spaces to see these records."}</p>
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
            <p>Municipal open data, carefully separated from live conditions.</p>
            {data && <p>Snapshot assembled {formatDate(data.generatedAt)}. <button onClick={() => setSourcesOpen(true)}>See source reference dates</button>.</p>}
          </footer>
        </aside>

        <section className="map-panel" aria-label="Porto parking map">
          <div className="map-heading"><span className="map-location"><MapPin size={15} aria-hidden="true" /> Porto</span><span>Supply & tariff geography</span></div>
          {data && <ParkingMap data={data} layers={state.layers} statuses={state.statuses} selected={selectedVisible ? selected : null} resetKey={resetKey} onSelect={selectFeature} />}
          {loading && <div className="map-message" role="status"><span className="loading-spinner" /><h2>Loading Porto’s parking records</h2><p>Opening the bundled municipal snapshot. No live availability is requested.</p></div>}
          {error && <div className="map-message error-message" role="alert"><Database size={32} aria-hidden="true" /><h2>Parking data could not load</h2><p>{error}</p><p>Check your connection and retry. If this persists, the site’s bundled snapshot may be missing or invalid.</p><button className="button button-primary" onClick={retry}><RotateCcw size={16} aria-hidden="true" /> Retry parking data</button></div>}
          {data && !state.layers.length && <p className="map-empty-notice">All parking layers are hidden. Enable a layer in the explorer.</p>}
          {data && <div className="map-caption"><span>Click a feature to inspect its record</span><strong>Inventory ≠ availability</strong></div>}
        </section>
      </main>
      {data && <SourcePanel data={data} open={sourcesOpen} onClose={() => setSourcesOpen(false)} />}
    </div>
  );
}

export default App;
