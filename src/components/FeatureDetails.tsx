import { useEffect, useRef } from "react";
import { ExternalLink, X } from "lucide-react";
import { FEATURE_LABELS, STATUS_LABELS, featureName, formatDate, formatRate } from "../lib/parking";
import type { ParkingFeature, ParkingSource } from "../types";

interface FeatureDetailsProps {
  feature: ParkingFeature;
  source: ParkingSource | undefined;
  onClose: () => void;
}

export function FeatureDetails({ feature, source, onClose }: FeatureDetailsProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const properties = feature.properties;

  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 760px)").matches) {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      heading.current?.scrollIntoView({ behavior: reducedMotion ? "instant" : "smooth", block: "start" });
    }
  }, [properties.id]);

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
          <div><dt>Source reference</dt><dd>{formatDate(source.referenceDate)}</dd></div>
          <div><dt>Retrieved</dt><dd>{formatDate(source.retrievedAt)}</dd></div>
          <div><dt>License</dt><dd>{source.license}</dd></div>
        </dl>
        <p className="small-text">{source.caveat}</p>
        <a href={source.metadataUrl} target="_blank" rel="noreferrer">Official metadata <ExternalLink size={13} aria-hidden="true" /></a>
        <a href={source.url} target="_blank" rel="noreferrer">Source GeoJSON <ExternalLink size={13} aria-hidden="true" /></a>
      </div>}
      <details className="raw-attributes">
        <summary>Original source attributes</summary>
        <dl>{Object.entries(properties.attributes).map(([key, value]) => (
          <div key={key}><dt>{key}</dt><dd>{value === null ? "Not provided" : typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>
        ))}</dl>
      </details>
    </section>
  );
}
