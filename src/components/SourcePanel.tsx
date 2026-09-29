import { useEffect, useRef } from "react";
import { ExternalLink, X } from "lucide-react";
import { formatDate } from "../lib/parking";
import type { DataManifest, PressureMethod, SourceId, SourceRecord } from "../types";

interface SourcePanelProps {
  manifest: DataManifest;
  method: PressureMethod | null;
  open: boolean;
  onClose: () => void;
}

const SOURCE_LABELS: Record<SourceId, string> = {
  zones: "Tariff zones",
  streets: "Paid streets",
  spaces: "Western paid spaces",
  garages: "Municipal garages",
  census: "Census 2021",
  osm: "OpenStreetMap",
  restrictions: "Traffic restrictions",
  complaints: "Complaints",
  calibration: "Calibration",
};

const GROUPS: { id: SourceRecord["group"]; title: string }[] = [
  { id: "inventory", title: "Parking inventory" },
  { id: "pressure", title: "Pressure index inputs" },
];

const DATASET_LABELS: Record<string, string> = { pressure: "Pressure cells", ...SOURCE_LABELS };

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const siteUrl = (path: string) => `${import.meta.env.BASE_URL}${path}`;

export function SourcePanel({ manifest, method, open, onClose }: SourcePanelProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  const downloads = Object.entries(manifest.datasets).flatMap(([name, entry]) => [
    { key: name, label: DATASET_LABELS[name] ?? name, path: entry.path, bytes: entry.bytes },
    ...("attributesPath" in entry ? [{ key: `${name}-attrs`, label: `${DATASET_LABELS[name] ?? name} · original attributes`, path: entry.attributesPath, bytes: null }] : []),
  ]);
  const poiWeights = method ? Object.entries(method.poiWeights).sort(([, a], [, b]) => b - a) : [];

  return (
    <dialog ref={dialog} className="source-dialog" aria-labelledby="sources-heading" onCancel={onClose}>
      <div className="dialog-heading">
        <div><span className="eyebrow">Municipal and open data</span><h2 id="sources-heading">Sources, dates & method</h2></div>
        <button className="icon-button" aria-label="Close sources" onClick={onClose}><X size={21} aria-hidden="true" /></button>
      </div>
      <p className="source-intro">This is a bundled snapshot, not a live feed. A recent retrieval or catalog update does not make the underlying records current.</p>
      <p className="snapshot-date">Snapshot assembled {formatDate(manifest.generatedAt)}. Reference dates below describe the source data, not an occupancy observation.</p>

      <section className="source-method" aria-labelledby="method-heading">
        <h3 id="method-heading">How the pressure index is estimated</h3>
        <p>Porto is divided into 150 m hexagons. For each cell we estimate demand and supply from open data, then rank the cells against each other from 0 (lowest) to 100 (highest).</p>
        <p>Overnight, demand is the number of households without their own parking (census 2021) and supply is the estimated public on-street spaces. Weekday daytime demand is a weighted score of nearby offices, schools, hospitals, shops and other activity from OpenStreetMap; supply adds public off-street capacity.</p>
        <p>On-street spaces are an estimate: the municipal total from the 2021 mobility diagnosis is distributed along eligible OpenStreetMap roads, adjusted for roads tagged without parking. Cells with too little estimated supply have no index rather than a value of zero.</p>
        <p>Complaint counts, parking restrictions and the western paid-space inventory are shown for context and do not change the ranking.</p>
        <p><strong>The index is a relative estimate of pressure — not occupancy, not availability and not a prediction.</strong></p>
        {method && (
          <dl className="method-constants">
            <div><dt>Municipal on-street total (calibration)</dt><dd>{method.onStreetTotalCalibration.toLocaleString("en-GB")} spaces</dd></div>
            <div><dt>Minimum supply for an index</dt><dd>{method.minSupplyForIndex.toLocaleString("en-GB")} spaces</dd></div>
            <div><dt>Road classes counted</dt><dd>{method.roadClasses.join(", ")}</dd></div>
            <div><dt>Complaint window</dt><dd>{method.complaintWindow ? `${formatDate(method.complaintWindow[0])} – ${formatDate(method.complaintWindow[1])}` : "Not provided"}</dd></div>
            <div><dt>Restriction window</dt><dd>{method.restrictionsWindow ? `${formatDate(method.restrictionsWindow[0])} – ${formatDate(method.restrictionsWindow[1])}` : "Not provided"}</dd></div>
          </dl>
        )}
        {method && poiWeights.length > 0 && (
          <details className="poi-weights">
            <summary>Daytime activity weights (documented assumptions)</summary>
            <ul>{poiWeights.map(([tag, weight]) => <li key={tag}><span>{tag}</span><strong>{weight}</strong></li>)}</ul>
            {method.notes && <p className="small-text">{method.notes}</p>}
          </details>
        )}
      </section>

      {GROUPS.map((group) => {
        const sources = manifest.sources.filter((source) => source.group === group.id);
        if (!sources.length) return null;
        return (
          <section key={group.id} className="source-group" aria-labelledby={`sources-${group.id}`}>
            <h3 id={`sources-${group.id}`} className="source-group-title">{group.title}</h3>
            <div className="source-cards">
              {sources.map((source) => (
                <section key={source.id} className="source-card">
                  <span className={`type-label type-${source.group === "inventory" ? source.id : "pressure"}`}>{SOURCE_LABELS[source.id]}</span>
                  <h4>{source.name}</h4>
                  <dl>
                    <div><dt>Records</dt><dd>{source.recordCount.toLocaleString("en-GB")}</dd></div>
                    <div><dt>Reference date</dt><dd>{source.referenceDate ? formatDate(source.referenceDate) : "Not provided"}</dd></div>
                    <div><dt>Retrieved</dt><dd>{formatDate(source.retrievedAt)}</dd></div>
                    <div><dt>License</dt><dd>{source.license}</dd></div>
                  </dl>
                  <p>{source.caveat}</p>
                  <div className="source-links">
                    {source.metadataUrl && <a href={source.metadataUrl} target="_blank" rel="noreferrer">Official metadata <ExternalLink size={13} aria-hidden="true" /></a>}
                    <a href={source.url} target="_blank" rel="noreferrer">Original source <ExternalLink size={13} aria-hidden="true" /></a>
                  </div>
                </section>
              ))}
            </div>
          </section>
        );
      })}

      <section className="source-limits">
        <h3>What this map cannot tell you</h3>
        <p>No verified public citywide street-payment history or block/hour occupancy feed is connected. Static road lines, polygons, bay records, garage capacities and estimated pressure cannot predict where you will find a space.</p>
        <p>Western space records are partial geographic coverage. Garage light-vehicle capacity is a category, not a reconciled total. Inventory status is not availability. Always check signs, restrictions and current operator information.</p>
      </section>

      <section className="source-downloads" aria-labelledby="downloads-heading">
        <h3 id="downloads-heading">Download the data</h3>
        <ul>
          <li><a href={siteUrl("data/manifest.json")} download>manifest.json</a><small>index of datasets and sources</small></li>
          {downloads.map((item) => (
            <li key={item.key}><a href={siteUrl(item.path)} download>{item.label}</a><small>{item.path.split("/").pop()}{item.bytes !== null ? ` · ${formatBytes(item.bytes)}` : ""}</small></li>
          ))}
        </ul>
      </section>
      <div className="source-footer">
        <span>Map tiles: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>. Pressure inputs include OpenStreetMap data under the ODbL.</span>
      </div>
    </dialog>
  );
}
