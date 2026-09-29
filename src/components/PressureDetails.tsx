import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { PERIODS, formatDate } from "../lib/parking";
import { PERIOD_LABELS, pressureClass } from "../lib/pressure";
import type { PressureCellProperties, PressureMethod, PressurePeriod } from "../types";

interface PressureDetailsProps {
  cell: PressureCellProperties;
  method: PressureMethod | null;
  onClose: () => void;
}

const number = (value: number, digits = 0) =>
  value.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function periodValues(cell: PressureCellProperties, period: PressurePeriod) {
  return period === "daytime"
    ? { index: cell.daytimeIndex, ratio: cell.daytimeRatio }
    : { index: cell.overnightIndex, ratio: cell.overnightRatio };
}

const RATIO_EXPLANATIONS: Record<PressurePeriod, string> = {
  daytime: "Weighted activity score per estimated public space",
  overnight: "Households without own parking per estimated on-street space",
};

export function PressureDetails({ cell, method, onClose }: PressureDetailsProps) {
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 760px)").matches) {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      heading.current?.scrollIntoView({ behavior: reducedMotion ? "instant" : "smooth", block: "start" });
    }
  }, [cell.id]);

  const complaintWindow = method?.complaintWindow;
  const restrictions = method?.restrictionsWindow;
  const complaintsNote = complaintWindow ? `${formatDate(complaintWindow[0])} – ${formatDate(complaintWindow[1])}` : "window not stated";

  return (
    <section className="feature-details pressure-details" aria-labelledby="pressure-heading">
      <div className="section-heading">
        <span className="type-label type-pressure">Estimate</span>
        <button className="icon-button" aria-label="Close pressure cell details" onClick={onClose}><X size={18} aria-hidden="true" /></button>
      </div>
      <h2 id="pressure-heading" ref={heading} tabIndex={-1}>Pressure cell</h2>
      <p className="record-id">{cell.zone ? `Tariff zone ${cell.zone}` : "Outside the paid tariff zones"} · {cell.id}</p>

      <ul className="pressure-periods" aria-label="Estimated pressure index by period">
        {PERIODS.map((period) => {
          const { index, ratio } = periodValues(cell, period);
          const cls = pressureClass(index);
          return (
            <li key={period}>
              <span className="pressure-period-name">{PERIOD_LABELS[period]}</span>
              <span className="pressure-index">
                <span className="pressure-swatch" style={{ backgroundColor: cls.color }} aria-hidden="true" />
                <strong>{index === null ? "—" : `${index}`}{index !== null && <small> / 100</small>}</strong>
                <span>{cls.label}</span>
              </span>
              <small className="pressure-ratio">
                {ratio === null ? "Ratio not computed: too little estimated supply in this cell." : `Ratio ${number(ratio, 2)} · ${RATIO_EXPLANATIONS[period]}`}
              </small>
            </li>
          );
        })}
      </ul>

      <table className="pressure-table">
        <caption>Components behind the estimate</caption>
        <thead><tr><th scope="col">Component</th><th scope="col">Value</th></tr></thead>
        <tbody>
          <tr>
            <th scope="row">Households without own parking<small>Census 2021, apportioned to the cell; {number(cell.households)} households, {number(cell.householdsWithParking)} with parking</small></th>
            <td>{number(cell.residentDemand, 1)} households</td>
          </tr>
          <tr>
            <th scope="row">Estimated on-street spaces<small>Estimate: OpenStreetMap road length scaled to the municipal total</small></th>
            <td>{number(cell.onStreetEstimate, 1)} spaces <em>estimate</em></td>
          </tr>
          <tr>
            <th scope="row">Public off-street capacity<small>OpenStreetMap car parks and municipal garages</small></th>
            <td>{number(cell.offStreetPublic)} spaces</td>
          </tr>
          <tr>
            <th scope="row">Western active paid spaces<small>Municipal inventory, partial coverage (western area only)</small></th>
            <td>{number(cell.westernActiveSpaces)} records <em>partial coverage</em></td>
          </tr>
          <tr>
            <th scope="row">Attraction score<small>Weighted daytime activity (offices, schools, shops, hospitals…)</small></th>
            <td>{number(cell.attraction, 1)} points</td>
          </tr>
          <tr>
            <th scope="row">Parking complaints<small>ReportaPorto counts, {complaintsNote}</small></th>
            <td>{number(cell.complaints)} complaints</td>
          </tr>
          <tr>
            <th scope="row">Parking restriction days<small>Municipal traffic restrictions{restrictions ? `, ${restrictions[0]} to ${restrictions[1]}` : ""}</small></th>
            <td>{number(cell.restrictionDays, 1)} days</td>
          </tr>
          <tr>
            <th scope="row">Cell coverage<small>Share of the hexagon inside the municipality</small></th>
            <td>{number(cell.coverage * 100)}%</td>
          </tr>
          <tr>
            <th scope="row">Tariff zone<small>Zone containing the cell centre</small></th>
            <td>{cell.zone ? `Zone ${cell.zone}` : "None"}</td>
          </tr>
        </tbody>
      </table>

      <p className="detail-caveat">
        The index is a relative ranking within Porto (0 = lowest, 100 = highest pressure), estimated from census 2021,
        OpenStreetMap, the municipal inventory and complaint counts. It is not occupancy, not availability and not a prediction.
        Complaints and restrictions are shown for context and do not change the index.
      </p>
    </section>
  );
}
