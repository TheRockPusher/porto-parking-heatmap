import { useEffect, useRef, useState } from "react";
import { ExternalLink, X } from "lucide-react";
import { FEATURE_LABELS, STATUS_LABELS, featureName, formatDate, formatRate } from "../lib/parking";
import type { AttributeTable, LayerKind, ParkingFeature, SourceRecord } from "../types";

interface FeatureDetailsProps {
  feature: ParkingFeature;
  source: SourceRecord | undefined;
  loadAttributes: (kind: LayerKind) => Promise<AttributeTable>;
  onClose: () => void;
}

interface AttributeResult {
  kind: LayerKind;
  attempt: number;
  table: AttributeTable | null;
  message: string | null;
}

export function FeatureDetails({ feature, source, loadAttributes, onClose }: FeatureDetailsProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const properties = feature.properties;
  const kind = properties.kind;
  const [attributesOpen, setAttributesOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<AttributeResult | null>(null);

  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 760px)").matches) {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      heading.current?.scrollIntoView({ behavior: reducedMotion ? "instant" : "smooth", block: "start" });
    }
  }, [properties.id]);

  useEffect(() => {
    if (!attributesOpen) return;
    let current = true;
    loadAttributes(kind).then(
      (table) => { if (current) setResult({ kind, attempt, table, message: null }); },
      (reason: unknown) => { if (current) setResult({ kind, attempt, table: null, message: reason instanceof Error ? reason.message : "Unknown error" }); },
    );
    return () => { current = false; };
  }, [attributesOpen, kind, attempt, loadAttributes]);

  const settled = result && result.kind === kind && result.attempt === attempt ? result : null;
  const rawAttributes = settled?.table?.[properties.id];

  return (
    <section className="feature-details" aria-labelledby="feature-heading">
      <div className="section-heading">
        <span className={`type-label type-${properties.kind}`}>{FEATURE_LABELS[properties.kind]}</span>
        <button className="icon-button" aria-label="Close feature details" onClick={onClose}><X size={18} aria-hidden="true" /></button>
      </div>
      <h2 id="feature-heading" ref={heading} tabIndex={-1}>{featureName(feature)}</h2>
      <p className="record-id">Record {properties.id}</p>
      <dl className="feature-facts">
        {properties.kind === "zones" && <>
          <div><dt>Tariff class</dt><dd>Zone {properties.zone}</dd></div>
          <div><dt>One-hour reference</dt><dd>{formatRate(properties.hourlyRate)}</dd></div>
        </>}
        {properties.kind === "spaces" && <>
          <div><dt>Inventory status</dt><dd>{STATUS_LABELS[properties.status]}</dd></div>
          <div><dt>Resident-zone identifier</dt><dd>{properties.residentZone ?? "Not provided"}</dd></div>
        </>}
        {properties.kind === "garages" && <>
          <div><dt>Address</dt><dd>{properties.address ?? "Not provided"}</dd></div>
          <div><dt>Operator in snapshot</dt><dd>{properties.operator ?? "Not provided"}</dd></div>
          <div><dt>Recorded opening hours</dt><dd>{properties.openingHours ?? "Not provided"}</dd></div>
          <div><dt>Light-vehicle category capacity</dt><dd>{properties.lightVehicleCapacity?.toLocaleString("en-GB") ?? "Not provided"}</dd></div>
        </>}
      </dl>
      {properties.kind === "zones" && <p className="detail-caveat">A one-hour reference, not a duration calculator. Longer-stay tariffs are not necessarily linear. Check current signage and the official tariff.</p>}
      {properties.kind === "streets" && <p className="detail-caveat">A paid-street geometry, not a meter or bay count. This record does not assign a tariff class, capacity or enforcement schedule to the street.</p>}
      {properties.kind === "spaces" && <p className="detail-caveat">“{STATUS_LABELS[properties.status]}” is a historical inventory status, not whether this space is free or occupied. Western coverage only; resident-zone identifiers are not tariff classes I–IV.</p>}
      {properties.kind === "garages" && <p className="detail-caveat">Capacity is the source’s light-vehicle category only, not total capacity or free spaces. Other categories may be listed separately; opening hours and operators may have changed.</p>}
      {source && <div className="feature-provenance">
        <h3>Record provenance</h3>
        <p>{source.name}</p>
        <dl>
          <div><dt>Source reference</dt><dd>{source.referenceDate ? formatDate(source.referenceDate) : "Not provided"}</dd></div>
          <div><dt>Retrieved</dt><dd>{formatDate(source.retrievedAt)}</dd></div>
          <div><dt>License</dt><dd>{source.license}</dd></div>
        </dl>
        <p className="small-text">{source.caveat}</p>
        {source.metadataUrl && <a href={source.metadataUrl} target="_blank" rel="noreferrer">Official metadata <ExternalLink size={13} aria-hidden="true" /></a>}
        <a href={source.url} target="_blank" rel="noreferrer">Source GeoJSON <ExternalLink size={13} aria-hidden="true" /></a>
      </div>}
      <details className="raw-attributes" onToggle={(event) => setAttributesOpen(event.currentTarget.open)}>
        <summary>Original source attributes</summary>
        {attributesOpen && !settled && <p className="attributes-status" role="status">Loading original attributes…</p>}
        {settled?.message && (
          <p className="attributes-status attributes-error" role="alert">
            Original attributes could not load ({settled.message}).{" "}
            <button onClick={() => setAttempt((value) => value + 1)}>Retry</button>
          </p>
        )}
        {settled?.table && (rawAttributes
          ? <dl>{Object.entries(rawAttributes).map(([key, value]) => (
            <div key={key}><dt>{key}</dt><dd>{value === null ? "Not provided" : typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>
          ))}</dl>
          : <p className="attributes-status">No original attributes are stored for this record.</p>)}
      </details>
    </section>
  );
}
