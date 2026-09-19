const utc = (iso) => new Date(iso).toUTCString();

function riskWord(risk) {
  if (risk >= 0.5) return "elevated";
  if (risk >= 0.25) return "moderate";
  return "low";
}

export default function SpillCard({ spill, driftWindow, ageEstimate }) {
  if (!spill) return <p className="empty-hint">Run detection to see spill stats here.</p>;

  return (
    <div>
      {spill.source === "upload" && (
        <div className="tag">uploaded · placed at {spill.scenario_label}</div>
      )}

      {/* Each sample tile is an observation of a different spill event, so the
          origin, the window and the vessel that gets caught all change with
          the image. Naming the event makes that visible rather than implied. */}
      {spill.scenario_label && spill.source !== "upload" && (
        <div className="stat-row">
          <span className="stat-label">Event</span>
          <span className="stat-value">{spill.scenario_label}</span>
        </div>
      )}

      <div className="stat-row">
        <span className="stat-label">Area</span>
        <span className="stat-value">{spill.area_km2} km²</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Perimeter</span>
        <span className="stat-value">{spill.perimeter_km} km</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Centroid</span>
        <span className="stat-value">
          {spill.centroid[0].toFixed(3)}, {spill.centroid[1].toFixed(3)}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Confidence</span>
        <span className="stat-value">{(spill.confidence * 100).toFixed(0)}%</span>
      </div>

      {driftWindow && (
        <div className="stat-row">
          <span className="stat-label">Est. spill window</span>
          {/* include the date: two events can share a time of day, and a
              window reading "14:00-18:00" on both looks like a stuck value */}
          <span className="stat-value">
            {utc(driftWindow.start).slice(5, 11)}{" "}
            {utc(driftWindow.start).slice(17, 22)}–
            {utc(driftWindow.end).slice(17, 22)} UTC
          </span>
        </div>
      )}

      {/* S2 — derived from the slick's shape, so it is an independent check on
          the assumed satellite-pass lag rather than a restatement of it. */}
      {ageEstimate && (
        <div className="stat-row">
          <span className="stat-label">Est. slick age</span>
          <span className="stat-value">
            {ageEstimate.estimated_age_hours} h
            <span className="stat-qualifier">
              {(ageEstimate.confidence * 100).toFixed(0)}% conf
            </span>
          </span>
        </div>
      )}

      {/* The gate. Otsu always returns the darkest region, so a tile with no
          oil in it still produces a polygon — this is what stops the pipeline
          hindcasting it and naming a vessel for a spill that never happened. */}
      {!spill.attributable && (
        <div className="note note-blocked">
          <span className="note-label">Not attributable</span>
          {spill.attribution_block_reason}
        </div>
      )}

      {/* S4 — look-alikes are the real failure mode of SAR oil detection, so
          say how contested this particular detection was. */}
      {spill.lookalike_note && (
        <div className={`note ${spill.lookalike_risk >= 0.5 ? "note-warn" : ""}`}>
          <span className="note-label">
            Look-alike risk {riskWord(spill.lookalike_risk)}
          </span>
          {spill.lookalike_note}
        </div>
      )}
    </div>
  );
}
