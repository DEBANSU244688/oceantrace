import { useEffect, useRef, useState } from "react";
import MapView from "./components/MapView";
import SpillCard from "./components/SpillCard";
import FunnelCounter from "./components/FunnelCounter";
import VesselList from "./components/VesselList";
import VesselDetail from "./components/VesselDetail";
import { api } from "./api";

export default function App() {
  const [backendStatus, setBackendStatus] = useState("checking"); // checking | ok | error
  const [scenario, setScenario] = useState(null);
  const [imageId, setImageId] = useState("");

  const [spill, setSpill] = useState(null);
  const [drift, setDrift] = useState(null);
  const [attribution, setAttribution] = useState(null);
  const [selectedVesselId, setSelectedVesselId] = useState(null);
  const [vesselDetail, setVesselDetail] = useState(null);

  const [loading, setLoading] = useState({});
  const [errors, setErrors] = useState({});
  const fileInput = useRef(null);

  // Phase 1 checkpoint (PP.md): prove the frontend can actually reach the
  // backend before anything else in the flow is attempted.
  useEffect(() => {
    api
      .health()
      .then(() => setBackendStatus("ok"))
      .catch(() => setBackendStatus("error"));
    api
      .scenario()
      .then((s) => {
        setScenario(s);
        setImageId(s.sample_images?.[0]?.id ?? "");
      })
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

  function resetDownstream() {
    setDrift(null);
    setAttribution(null);
    setSelectedVesselId(null);
    setVesselDetail(null);
  }

  async function handleDetect() {
    if (!imageId) return;
    const result = await runStep("detect", () => api.detect(imageId));
    if (result) {
      setSpill(result);
      resetDownstream();
    }
  }

  // Switching tiles mid-demo has to clear the old result, or the map shows one
  // image with the previous image's polygon on it.
  function handleSelectImage(nextId) {
    setImageId(nextId);
    setSpill(null);
    resetDownstream();
  }

  // #14 — judges ask "can I try my own image?". The upload runs the same
  // pipeline; it is placed at the scenario location exactly as the downloaded
  // Zenodo tiles are, so drift and AIS stay meaningful instead of dead-ending.
  async function handleUpload(e) {
    const file = e.target.files?.[0];
    e.target.value = "";          // so picking the same file twice still fires
    if (!file) return;
    const result = await runStep("detect", () => api.detectUpload(file));
    if (result) {
      setSpill(result);
      resetDownstream();
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

  const activeError = errors.detect || errors.drift || errors.attribution || errors.scenario;
  // A detection that did not clear the attribution gate must not lead anywhere:
  // tracing an origin for a slick we are not confident exists, and then naming
  // a real vessel for it, is the worst thing this system could do.
  const blocked = Boolean(spill && !spill.attributable);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          Ocean<span>Trace</span>
        </div>
        <div className="app-subtitle">Spill detection &amp; AIS vessel attribution</div>
        <div className={`status ${backendStatus}`}>
          {backendStatus === "checking" && "connecting"}
          {backendStatus === "ok" && "connected"}
          {backendStatus === "error" && "backend unreachable"}
        </div>
      </header>

      <div className="step-bar">
        <button className="step-btn" disabled={backendStatus !== "ok" || !imageId || loading.detect} onClick={handleDetect}>
          {loading.detect && <span className="spinner" />}
          Detect spill
        </button>
        <button
          className={`step-btn ${drift ? "done" : ""}`}
          disabled={!spill || blocked || loading.drift}
          onClick={handleDrift}
        >
          {loading.drift && <span className="spinner" />}
          Trace origin
        </button>
        <button
          className={`step-btn ${attribution ? "done" : ""}`}
          disabled={!drift || blocked || loading.attribution}
          onClick={handleAttribution}
        >
          {loading.attribution && <span className="spinner" />}
          Analyse AIS
        </button>

        <div className="source-controls">
          <select
            className="tile-select"
            value={spill?.source === "upload" ? "" : imageId}
            disabled={!scenario}
            onChange={(e) => handleSelectImage(e.target.value)}
          >
            {spill?.source === "upload" && <option value="">uploaded image</option>}
            {(scenario?.sample_images ?? []).map((img) => (
              <option key={img.id} value={img.id}>
                {img.label}
              </option>
            ))}
          </select>
          <button
            className="link-btn"
            disabled={backendStatus !== "ok" || loading.detect}
            onClick={() => fileInput.current?.click()}
          >
            upload
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            hidden
            onChange={handleUpload}
          />
        </div>
      </div>

      {activeError && (
        <div className="error-wrap">
          <div className="error-banner">{activeError}</div>
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
          <section className="block">
            <p className="block-title">Spill detection</p>
            <SpillCard
              spill={spill}
              driftWindow={drift?.spill_window}
              ageEstimate={drift?.age_estimate}
            />
          </section>

          <section className="block">
            <p className="block-title">AIS candidate funnel</p>
            <FunnelCounter funnel={attribution?.funnel} />
          </section>

          <section className="block">
            <p className="block-title">Ranked suspect vessels</p>
            <VesselList
              vessels={attribution?.ranked_vessels}
              selectedId={selectedVesselId}
              onSelect={handleSelectVessel}
            />
          </section>

          <section className="block">
            <p className="block-title">Why flagged</p>
            <VesselDetail vessel={vesselDetail} loading={loading.vessel} error={errors.vessel} />
          </section>
        </div>
      </div>
    </div>
  );
}
