import { useEffect, useRef } from "react";
import { ExternalLink, X } from "lucide-react";
import { formatDate, LAYER_LABELS } from "../lib/parking";
import type { ParkingData } from "../types";

interface SourcePanelProps {
  data: ParkingData;
  open: boolean;
  onClose: () => void;
}

export function SourcePanel({ data, open, onClose }: SourcePanelProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  return (
    <dialog ref={dialog} className="source-dialog" aria-labelledby="sources-heading" onCancel={onClose}>
      <div className="dialog-heading">
        <div><span className="eyebrow">Municipal open data</span><h2 id="sources-heading">Sources, dates & coverage</h2></div>
        <button className="icon-button" aria-label="Close sources" onClick={onClose}><X size={21} aria-hidden="true" /></button>
      </div>
      <p className="source-intro">This is a bundled geographic inventory, not a live feed. A recent retrieval or catalog update does not make the underlying records current.</p>
      <p className="snapshot-date">Snapshot assembled {formatDate(data.generatedAt)}. Reference dates below describe the source data, not an occupancy observation.</p>
      <div className="source-cards">
        {data.sources.map((source) => (
          <section key={source.id} className="source-card">
            <span className={`type-label type-${source.id}`}>{LAYER_LABELS[source.id]}</span>
            <h3>{source.name}</h3>
            <dl>
              <div><dt>Records</dt><dd>{source.featureCount.toLocaleString("en-GB")}</dd></div>
              <div><dt>Reference date</dt><dd>{formatDate(source.referenceDate)}</dd></div>
              <div><dt>Retrieved</dt><dd>{formatDate(source.retrievedAt)}</dd></div>
              <div><dt>License</dt><dd>{source.license}</dd></div>
            </dl>
            <p>{source.caveat}</p>
            <div className="source-links">
              <a href={source.metadataUrl} target="_blank" rel="noreferrer">Official metadata <ExternalLink size={13} aria-hidden="true" /></a>
              <a href={source.url} target="_blank" rel="noreferrer">Original GeoJSON <ExternalLink size={13} aria-hidden="true" /></a>
            </div>
          </section>
        ))}
      </div>
      <section className="source-limits">
        <h3>What this map cannot tell you</h3>
        <p>No verified public citywide street-payment history or block/hour occupancy feed is connected. Static road lines, polygons, bay records and garage capacities cannot predict where you will find a space.</p>
        <p>Western space records are partial geographic coverage. Garage light-vehicle capacity is a category, not a reconciled total. Inventory status is not availability. Always check signs, restrictions and current operator information.</p>
      </section>
      <div className="source-footer">
        <a href={`${import.meta.env.BASE_URL}data/porto-parking.json`} download>Download this normalized snapshot</a>
        <span>Map tiles: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a></span>
      </div>
    </dialog>
  );
}
