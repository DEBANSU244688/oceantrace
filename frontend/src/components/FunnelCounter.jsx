import { Fragment } from "react";

export default function FunnelCounter({ funnel }) {
  if (!funnel) return <p className="empty-hint">Run AIS analysis to see the candidate funnel.</p>;

  const stages = [
    { label: "AIS traffic", value: funnel.total },
    { label: "near origin", value: funnel.spatial },
    { label: "right time", value: funnel.temporal },
    { label: "trajectory", value: funnel.trajectory },
  ];

  return (
    <div className="funnel-flow">
      {stages.map((s, i) => (
        <Fragment key={s.label}>
          {i > 0 && <span className="arrow">&rarr;</span>}
          <div className="funnel-stage">
            <div className="funnel-value">{s.value}</div>
            <div className="funnel-label">{s.label}</div>
          </div>
        </Fragment>
      ))}
    </div>
  );
}
