export default function SpillCard({ spill, driftWindow }) {
  if (!spill) return <p className="empty-hint">Run detection to see spill stats here.</p>;

  return (
    <div>
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
          <span className="stat-value">
            {new Date(driftWindow.start).toUTCString().slice(17, 22)}–
            {new Date(driftWindow.end).toUTCString().slice(17, 22)} UTC
          </span>
        </div>
      )}
    </div>
  );
}
