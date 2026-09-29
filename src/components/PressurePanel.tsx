import { Gauge } from "lucide-react";
import { PERIODS } from "../lib/parking";
import { NO_DATA_COLOR, PERIOD_LABELS, PRESSURE_STOPS, pressureClass } from "../lib/pressure";
import type { DatasetStatus, PressurePeriod } from "../types";

interface PressurePanelProps {
  period: PressurePeriod;
  status: DatasetStatus;
  cellCount: number | null;
  visible: boolean;
  onPeriod: (period: PressurePeriod) => void;
  onShow: () => void;
  onOpenMethod: () => void;
}

const PERIOD_HINTS: Record<PressurePeriod, string> = {
  daytime: "Activity near offices, schools, shops and hospitals versus public supply",
  overnight: "Households without own parking versus on-street supply",
};

export function PressurePanel({ period, status, cellCount, visible, onPeriod, onShow, onOpenMethod }: PressurePanelProps) {
  const classes = PRESSURE_STOPS.map(([start], position) => {
    const next = PRESSURE_STOPS[position + 1]?.[0];
    return { start, range: `${start}–${next === undefined ? 100 : next - 1}`, ...pressureClass(start) };
  });

  return (
    <section className="pressure-section" aria-labelledby="pressure-section-heading">
      <div className="section-heading">
        <h2 id="pressure-section-heading"><Gauge size={17} aria-hidden="true" /> Parking pressure (estimated)</h2>
        <span className="quiet-label">{status === "loading" || status === "idle" ? "Loading…" : status === "error" ? "Unavailable" : `${cellCount?.toLocaleString("en-GB") ?? "—"} cells`}</span>
      </div>
      <fieldset className="segmented" disabled={status !== "ready"} aria-describedby="pressure-period-hint">
        <legend className="segmented-legend">Time of day</legend>
        <div className="segmented-options">
          {PERIODS.map((value) => (
            <label key={value} className={period === value ? "segment selected" : "segment"}>
              <input type="radio" name="pressure-period" value={value} checked={period === value} onChange={() => onPeriod(value)} />
              <span>{PERIOD_LABELS[value]}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <p className="helper-text" id="pressure-period-hint">{PERIOD_HINTS[period]}.</p>
      {!visible && status === "ready" && <p className="helper-text pressure-hidden">The pressure layer is hidden. <button onClick={onShow}>Show it on the map</button></p>}
      <div className="pressure-legend" role="group" aria-label="Pressure index legend, relative to other cells in Porto">
        <ul>
          {classes.map((item) => (
            <li key={item.start}><span className="pressure-swatch" style={{ backgroundColor: item.color }} aria-hidden="true" /><span>{item.label}</span><small>{item.range}</small></li>
          ))}
          <li><span className="pressure-swatch pressure-swatch-empty" style={{ backgroundColor: NO_DATA_COLOR }} aria-hidden="true" /><span>{pressureClass(null).label}</span><small>no index</small></li>
        </ul>
      </div>
      <p className="helper-text">
        Method: 150 m hexagons compare estimated demand (households without own parking, or weekday activity) with estimated
        public supply, then rank cells from 0 to 100. <button onClick={onOpenMethod}>Read the methodology</button>.
      </p>
      <p className="pressure-caveat"><strong>Estimate, not occupancy.</strong> A relative ranking within Porto — not live availability and not a prediction.</p>
    </section>
  );
}
