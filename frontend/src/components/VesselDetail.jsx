export default function VesselDetail({ vessel, loading, error }) {
  if (loading) return <p className="empty-hint"><span className="spinner" />Loading vessel detail…</p>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!vessel) return <p className="empty-hint">Select a vessel above to see why it was flagged.</p>;

  return (
    <div>
      <div className="stat-row">
        <span className="stat-label">Vessel</span>
        <span className="stat-value">{vessel.name}</span>
      </div>
      <ul className="reasons-list">
        {vessel.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}
