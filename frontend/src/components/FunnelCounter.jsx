export default function FunnelCounter({ funnel }) {
  if (!funnel) return <p className="empty-hint">Run AIS analysis to see the candidate funnel.</p>;

  const stages = [
    { label: "AIS traffic", value: funnel.total },
    { label: "near origin", value: funnel.spatial },
    { label: "+ right time", value: funnel.temporal },
    { label: "+ trajectory match", value: funnel.trajectory },
  ];

  return (
    <div className="funnel-flow">
      {stages.map((s, i) => (
        <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {i > 0 && <span className="arrow">&rarr;</span>}
          <span>
            {s.value}
            <span className="stage-label">{s.label}</span>
          </span>
        </span>
      ))}
    </div>
  );
}
