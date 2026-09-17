import { useEffect, useState } from "react";
import MapView from "./components/MapView";
import SpillCard from "./components/SpillCard";
import FunnelCounter from "./components/FunnelCounter";
import VesselList from "./components/VesselList";
import VesselDetail from "./components/VesselDetail";
import { api } from "./api";

export default function App() {
  const [backendStatus, setBackendStatus] = useState("checking"); // checking | ok | error
  const [scenario, setScenario] = useState(null);

  const [spill, setSpill] = useState(null);
  const [drift, setDrift] = useState(null);
  const [attribution, setAttribution] = useState(null);
  const [selectedVesselId, setSelectedVesselId] = useState(null);
  const [vesselDetail, setVesselDetail] = useState(null);

  const [loading, setLoading] = useState({});
  const [errors, setErrors] = useState({});

  // Phase 1 checkpoint (PP.md): prove the frontend can actually reach the
  // backend before anything else in the flow is attempted.
  useEffect(() => {
    api
      .health()
      .then(() => setBackendStatus("ok"))
      .catch(() => setBackendStatus("error"));
    api
      .scenario()
      .then(setScenario)
      .catch((e) => setErrors((p) => ({ ...p, scenario: e.message })));
  }, []);

  async function runStep(key, fn) {
    setLoading((p) => ({ ...p, [key]: true }));
    setErrors((p) => ({ ...p, [key]: null }));
    try {
      return await fn();
    } catch (e) {
      setErrors((p) => ({ ...p, [key]: e.message }));
      return null;
    } finally {
      setLoading((p) => ({ ...p, [key]: false }));
    }
  }

  async function handleDetect() {
    const imageId = scenario?.sample_images?.[0]?.id;
    if (!imageId) return;
    const result = await runStep("detect", () => api.detect(imageId));
    if (result) {
      setSpill(result);
      setDrift(null);
      setAttribution(null);
      setSelectedVesselId(null);
      setVesselDetail(null);
    }
  }

  async function handleDrift() {
    if (!spill) return;
    const result = await runStep("drift", () => api.drift(spill.spill_id));
    if (result) setDrift(result);
  }

  async function handleAttribution() {
    if (!spill) return;
    const result = await runStep("attribution", () => api.attribution(spill.spill_id));
    if (result) setAttribution(result);
  }

  async function handleSelectVessel(vesselId) {
    setSelectedVesselId(vesselId);
    const result = await runStep("vessel", () => api.vessel(vesselId));
    if (result) setVesselDetail(result);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          Ocean<span>Trace</span>
        </div>
        <div className="app-subtitle">Satellite spill detection &amp; AIS vessel attribution</div>
        <div className={`status-pill ${backendStatus}`}>
          {backendStatus === "checking" && "checking backend…"}
          {backendStatus === "ok" && "backend connected"}
          {backendStatus === "error" && "backend unreachable"}
        </div>
      </header>

      <div className="step-bar">
        <button className="step-btn" disabled={backendStatus !== "ok" || loading.detect} onClick={handleDetect}>
          <span className="step-num">1</span>
          {loading.detect ? <span className="spinner" /> : null}
          Detect Spill
        </button>
        <button
          className={`step-btn ${drift ? "done" : ""}`}
          disabled={!spill || loading.drift}
          onClick={handleDrift}
        >
          <span className="step-num">2</span>
          {loading.drift ? <span className="spinner" /> : null}
          Trace Origin
        </button>
        <button
          className={`step-btn ${attribution ? "done" : ""}`}
          disabled={!drift || loading.attribution}
          onClick={handleAttribution}
        >
          <span className="step-num">3</span>
          {loading.attribution ? <span className="spinner" /> : null}
          Analyse AIS
        </button>
      </div>

      {(errors.detect || errors.drift || errors.attribution) && (
        <div style={{ padding: "0 24px", marginTop: 12 }}>
          <div className="error-banner">
            {errors.detect || errors.drift || errors.attribution}
          </div>
        </div>
      )}

      <div className="main-area">
        <div className="map-pane">
          <MapView
            regionCenter={scenario?.region_center}
            spill={spill}
            drift={drift}
            vesselDetail={vesselDetail}
          />
        </div>

        <div className="sidebar">
          <div className="panel accent-teal">
            <p className="panel-title">SPILL DETECTION</p>
            <SpillCard spill={spill} driftWindow={drift?.spill_window} />
          </div>

          <div className="panel accent-amber">
            <p className="panel-title">AIS CANDIDATE FUNNEL</p>
            <FunnelCounter funnel={attribution?.funnel} />
          </div>

          <div className="panel">
            <p className="panel-title">RANKED SUSPECT VESSELS</p>
            <VesselList
              vessels={attribution?.ranked_vessels}
              selectedId={selectedVesselId}
              onSelect={handleSelectVessel}
            />
          </div>

          <div className="panel">
            <p className="panel-title">WHY FLAGGED</p>
            <VesselDetail vessel={vesselDetail} loading={loading.vessel} error={errors.vessel} />
          </div>
        </div>
      </div>
    </div>
  );
}
