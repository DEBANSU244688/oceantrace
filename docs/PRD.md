# PRD — OceanTrace
**SIH 2026 · Problem Statement 26143 (NTRO) · Team: The HackerPunk · Round-2 build, 10-hour window**

## 1. Problem (verbatim scope, from official PS)
Detect oil spills at sea from satellite imagery (SAR/EO), trace each spill backward to its
probable origin point/time and forward to its future path using ocean/weather data, then
attribute the spill to a specific vessel using historic AIS data — filtering irrelevant
traffic and scoring suspects on proximity, trajectory, and behavioural anomalies. Deliver
a visual interface.

## 2. Goal for this round
Not a production system — a **credible, working, click-through demo** on a real
frontend/backend split (FastAPI + React), proving the full pipeline (image → spill →
origin → vessel ranking) runs end-to-end on real logic served over an actual API, matching
what's already on the submitted PPT's Technical Approach slide. Judges should be able to
change the input image or watch the AIS funnel narrow in real time and get a believable,
explainable answer — and the team should be able to open the Network tab and show a real
request/response if asked.

## 3. Scope (MoSCoW — full detail in `BL.md`)
- **MUST**: detection+characterisation, drift+attribution pipeline, FastAPI backend serving
  it, React dashboard consuming it end-to-end
- **SHOULD**: forecast path, age estimate, explainability panel
- **WON'T** (this round): live AIS feeds, trained-from-scratch deep models, multi-spill
  support, auth, mobile app, production deploy/build of the React app

## 4. Judge-facing user flow
1. Judge picks (or the app auto-loads) a sample SAR image
2. App shows: spill polygon overlaid on the image + area/perimeter/centroid/confidence
3. Judge clicks **"Trace Origin"** → map animates backward drift → origin probability zone
4. Judge clicks **"Analyse AIS"** → funnel counter animates (e.g. 27 → 9 → 5 → 3 candidates)
5. Ranked vessel list appears with risk scores; clicking a vessel shows its trajectory +
   a plain-language "why flagged" reasoning panel

Each of steps 2–5 is a real REST call from the React app to the FastAPI backend — see the
API contract in `SACD.md` §3. No step is frontend-only mock data at demo time.

## 5. Success criteria
- Full flow (step 1→5) completes in under 60 seconds live, no manual restarts
- At least one detection result is on a *real* Zenodo SAR sample (not a synthetic image)
- Vessel ranking is driven by the actual scoring formula on generated data, not hardcoded
- React frontend and FastAPI backend run as two local processes, started with one documented
  command each; CORS confirmed working before any feature work begins (see `PP.md` Phase 1)
- Runs fully offline/local — no dependency on a live internet connection during the demo

## 6. Non-functional requirements (deliberately minimal)
- Single machine, two local processes (`uvicorn` + Vite dev server) — no cloud deploy needed
- No auth, no multi-user support, no persistence required across restarts
- Inference/response time: under ~5s per API call is fine for a live demo
- No production build of the React app required — the Vite dev server is fine to demo from

## 7. Team & roles
See `PP.md` / `TASKS.md`. Assumes 4–6 people; merge roles if the team is smaller.

## 8. Related documents
`SACD.md` (architecture + API contract) · `DB.md` (data storage) · `DRD.md` (datasets) ·
`BL.md` (backlog) · `PP.md` (timeline) · `TASKS.md` (checklist) ·
`MASTER_REFERENCE_INDEX.md` (index)
