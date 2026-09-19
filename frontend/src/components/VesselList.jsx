function riskClass(score) {
  if (score >= 0.6) return "risk-high";
  if (score >= 0.3) return "risk-med";
  return "risk-low";
}

export default function VesselList({ vessels, selectedId, onSelect }) {
  if (!vessels) return <p className="empty-hint">Run AIS analysis to see ranked vessels.</p>;

  return (
    <div className="vessel-list">
      {vessels.slice(0, 8).map((v, i) => (
        <div
          key={v.vessel_id}
          className={`vessel-row ${v.vessel_id === selectedId ? "selected" : ""}`}
          onClick={() => onSelect(v.vessel_id)}
        >
          <span className="vessel-rank">{i + 1}</span>
          <span className="vessel-name">{v.name}</span>
          <span className={`vessel-score ${riskClass(v.score)}`}>
            {(v.score * 100).toFixed(0)}
          </span>
        </div>
      ))}
    </div>
  );
}
