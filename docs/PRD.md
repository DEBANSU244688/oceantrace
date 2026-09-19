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
- **MUST** ✅ *all built*: detection+characterisation, drift+attribution pipeline, FastAPI
  backend serving it, React dashboard consuming it end-to-end
- **SHOULD** ✅ *all four built*: S1 forecast path, S2 age estimate, S3 explainability
  panel, S4 look-alike confidence note
- **WON'T** (this round): live AIS feeds, trained-from-scratch deep models, auth, mobile
  app, production deploy/build of the React app, satellite tasking. Multi-region was
  partially reversed on purpose — see `BL.md`.

## 4. Judge-facing user flow
1. Judge picks a tile from the selector — or **uploads their own image**
2. App shows: the SAR tile itself on the map, the detected polygon over it, plus
   area/perimeter/centroid/confidence and a look-alike risk note. An opacity slider fades
   the tile so the polygon can be seen tracking the real slick
3. Judge clicks **"Trace origin"** → backward drift animates, then resolves into a
   150-particle probability cloud and an uncertainty circle, with the estimated slick age
4. Judge clicks **"Analyse AIS"** → funnel narrows from 26 (how far depends on the event)
5. Ranked vessel list appears with risk scores; clicking a vessel shows its trajectory +
   a plain-language "why flagged" panel
6. **Switching to a different tile gives a different origin, window and culprit** — each
   tile is an observation of a different spill event

If a detection does not clear the attribution gate, steps 3–5 are refused and the panel
says why. Each of steps 2–5 is a real REST call — see `SACD.md` §3. No step is
frontend-only mock data at demo time.

## 5. Success criteria — current status
- ✅ Full flow completes in under 60 seconds live — measured at **~0.5 s**
- ✅ At least one detection on a *real* Zenodo SAR sample — **three** real Sentinel-1 tiles,
  scored against the dataset's own masks at mean IoU 0.43
- ✅ Vessel ranking driven by the actual scoring formula, not hardcoded — and demonstrably
  so: four tiles give four different culprits
- ✅ Two local processes, one documented command each; CORS covers Vite's 5173–5176 range
- ✅ Runs fully offline — Natural Earth coastline replaces the networked basemap, and all
  imagery, AIS and ocean forcing are cached on disk
- ⬜ **Untested: the 60-second target with a human driving and talking.** Verified by
  script only. `PP.md` Phase E rehearsal has not happened.

## 6. Non-functional requirements (deliberately minimal)
- Single machine, two local processes (`uvicorn` + Vite dev server) — no cloud deploy needed
- No auth, no multi-user support, no persistence required across restarts
- Inference/response time: under ~5s per API call is fine for a live demo (actual: the
  whole four-call flow runs in ~0.5s)
- No production build of the React app required — the Vite dev server is fine to demo from

## 7. Team & roles
See `PP.md` / `TASKS.md`. Assumes 4–6 people; merge roles if the team is smaller.

## 8. Related documents
`SACD.md` (architecture + API contract) · `DB.md` (data storage) · `DRD.md` (datasets) ·
`BL.md` (backlog) · `PP.md` (timeline) · `TASKS.md` (checklist) ·
`MASTER_REFERENCE_INDEX.md` (index)
