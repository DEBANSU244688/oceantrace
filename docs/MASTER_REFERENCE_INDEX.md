# MASTER_REFERENCE_INDEX
**OceanTrace · SIH 2026 · PS 26143 (NTRO) · Round-2, 10h build**
**Team: The HackerPunk · Team ID: [TBD]**

## Elevator pitch
"Oil spills at sea usually go unattributed. OceanTrace turns a single satellite image into
a ranked list of suspect vessels — detecting the slick, tracing it backward to where and
when it started, and cross-referencing that against ship traffic to score who's responsible."

## Document index
| File | What's in it |
|---|---|
| `PRD.md` | Problem, scope, judge-facing flow, success criteria |
| `SACD.md` | Pipeline architecture, component responsibilities, **API contract**, tech stack |
| `DB.md` | Data storage schema (spills, origin_zones, vessels, ais_positions, vessel_scores) |
| `DRD.md` | Datasets, synthetic AIS generation spec, pre-round prep checklist |
| `BL.md` | MoSCoW backlog — MUST/SHOULD/WON'T |
| `PP.md` | Hour-by-hour timeline + role split |
| `TASKS.md` | Granular per-role checklist |
| `evaluator_brief.md` | What's built, the numbers, the deliberate cuts |
| `JUDGE_QA_PREP.md` | Anticipated judge questions, readiness, what to say |
| `next_steps.md` | Ranked list of what's still open |
| `MASTER_REFERENCE_INDEX.md` | This file |

## Build status — as of the current branch

All three MUSTs and **all four SHOULDs** are built, plus work that was not in the
original backlog. `python backend/scripts/smoke_test.py` asserts it: **78 checks**.

| | |
|---|---|
| Imagery | **Real Sentinel-1** (Zenodo SOS, CC-BY-4.0), 3 tiles + 1 synthetic fallback |
| Detector accuracy | mean IoU **0.43** vs the dataset's own masks (`validate_detector.py`) |
| Ocean forcing | **Real** hourly current + 3% windage (Open-Meteo), per event, cached |
| Scenario | **Four** spill events, each with its own origin, window and guilty vessel |
| Origin recovery | **22–91 m** from ground truth |
| Refusal gate | blocks **60/60** no-oil tiles (`validate_detector.py --gate`) |
| Offline | Natural Earth land layer; the demo needs no internet |
| Full flow | ~0.5 s (`PRD.md` allows 60) |

## Quick-reference: tech stack
**Backend**: Python 3.11+ · FastAPI + Uvicorn · python-multipart (uploads) ·
OpenCV/scikit-image · Shapely · NumPy · Pandas · GeoPandas · in-memory state (no DB server).
**Frontend**: React (Vite) + react-leaflet, plain `useState`/`fetch`, no Redux/router,
light + dark themes.
**External data, all free and keyless**: Zenodo record 15298010 (SAR tiles + ground-truth
masks), Open-Meteo marine + forecast (ocean current and wind), Natural Earth (coastline).
CARTO basemap tiles need a key but the demo runs without them.
No trained models, no live AIS feed, no PostGIS, no Docker, no auth, no production
frontend build — see `SACD.md` §4 for why. This matches the submitted PPT's Technical
Approach slide (FastAPI backend, Leaflet map, React as the app shell).

## Quick-reference: API contract (full detail in `SACD.md` §3)
```
GET  /health                       → liveness, used as the Phase 1 CORS checkpoint
GET  /api/scenario                 → sample images + region center
GET  /api/images/{image_id}        → the SAR tile itself, for the map overlay
GET  /api/basemap/land             → public-domain coastline, the offline basemap
POST /api/detect      {image_id}   → spill polygon + stats + look-alike risk + event id
POST /api/detect/upload  (file)    → same, for a judge-supplied image
POST /api/drift       {spill_id}   → origin zone + window + forecast + hindcast + age
POST /api/attribution {spill_id}   → funnel counts + ranked vessel list w/ score breakdown
GET  /api/vessels/{id}?spill_id=   → trajectory + full score breakdown + reasons
```
`/api/drift` and `/api/attribution` return **409** when the detection did not clear the
attribution gate — the system will not name a vessel for a spill it is not confident
happened.

## Quick-reference: attribution scoring formula
```
Risk Score =
    0.25 × Spatial Score          (proximity to origin)
  + 0.20 × Temporal Score         (present during spill window)
  + 0.20 × Trajectory Score       (path intersects origin zone)
  + 0.10 × Speed Anomaly Score
  + 0.10 × Course Anomaly Score
  + 0.05 × Loitering Score
  + 0.05 × AIS Transmission Anomaly Score
  + 0.05 × Vessel Type/Context Score
```
Each sub-score is 0–1; weights sum to 1.00. Full field definitions in `DB.md` §5.

## Quick-reference: the demo scenario

Bay of Bengal, **offshore** of Paradip Port, Odisha. Region centre 20.05°N, 86.95°E.
(An earlier draft used ~20.31°N, 86.61°E — that is ~15 km *inland*, which a wide synthetic
tile hid and a 2.5 km real tile does not. All coordinates are now ETOPO1-checked.)

**Four spill events**, ≥35 km apart so one event's vessels never leak into another's funnel.
Each sample tile is an observation of one of them:

| Tile | Event | Origin | Guilty vessel | Real drift |
|---|---|---|---|---|
| `s1_371` | Paradip approach | 20.15, 86.82 | BAY VOYAGER | 0.64 km/h @ 204° |
| `s1_485` | Outer anchorage | 20.28, 87.18 | MV KALINGA PRIDE | 1.20 km/h @ 234° |
| `s1_473` | Southern lane | 19.72, 86.78 | ORIENT MARINER | 1.63 km/h @ 285° |
| `sar_001` | Deep-water crossing | 19.80, 87.15 | MV SILVER TIDE | 2.19 km/h @ 324° |

26-vessel synthetic roster covering all four events — each gets a guilty vessel, a
near-miss (right place, wrong time) and a false positive (right time, wrong place).
The drift figures are measured from real Open-Meteo data, not chosen.

## Demo script (rehearse before code freeze)
1. **Hook (30s)**: "Marine oil spills usually go unattributed. We built a pipeline that
   turns one satellite image into a ranked list of suspect vessels."
2. **Live flow (2–3 min)**: pick a tile → **Detect spill** → the real SAR tile appears
   under the detected polygon; *drag the opacity slider down* so they watch the polygon sit
   on the actual slick → **Trace origin** → backward drift animates, then resolves into 150
   particles and an uncertainty circle ("the origin is a probability cloud, not a point") →
   **Analyse AIS** → funnel narrows from 26 → click the top vessel → trajectory and
   plain-language reasons. Every click is a real call from React to FastAPI.
3. **Then switch tiles and run it again.** Different event, different origin, different
   culprit — and the previous culprit still in the list, scored down. This is the answer to
   "isn't it hardcoded?" and it is worth more than any explanation.
4. **Show it refuse.** Upload `06_no_oil_lookalikes_only.png` from
   `backend/data/demo_uploads/`. No oil in that tile, and the pipeline declines to trace or
   name anyone. *"Declining to attribute a real spill costs an analyst a second look.
   Attributing one that never happened costs a ship operator their reputation."*
5. **Deliberate cuts, say them before you are asked**: synthetic AIS (the PS permits it
   explicitly), classical CV rather than a trained model, and no satellite tasking — that
   infrastructure exists and NTRO can already invoke it. Full wording in
   `evaluator_brief.md`; likely questions in `JUDGE_QA_PREP.md`.
6. **Technical highlight (30s)**: pick one — the real ocean forcing driving the drift
   inversion, the explainable attribution score, the refusal gate, or the frozen API
   contract that let backend and frontend build in parallel.

## Key decisions/assumptions made while drafting these docs (confirm or override)
- Project name: "OceanTrace" — finalised, matches the submitted idea PPT
- **Architecture: FastAPI backend + React (Vite) frontend with react-leaflet for mapping**
  — matches the PPT's Technical Approach slide; this replaces an earlier Streamlit-based
  draft of these docs, which is no longer in use
- MVP scope: classical CV detection (not trained deep learning), physics-based particle
  drift, rule-based (non-ML) AIS scoring — see `SACD.md` §4
- Assumed team size 4–6 for role split in `PP.md`/`TASKS.md` — merge roles if smaller, but
  keep R4 (frontend/integration) separate, it carries the most integration risk in this stack
- Demo scenario location: offshore Paradip, Odisha. No longer a free-swap placeholder —
  the coordinates are bathymetry-checked and the AIS generator's seaward bearing arc is
  measured for this specific origin. Moving the scenario means re-measuring both.

## Risk register (top 3)
| Risk | Mitigation |
|---|---|
| Frontend↔backend integration discovered broken late | CORS + a live health-check fetch is the Phase 1 checkpoint in `PP.md` — prove it in the first 75 minutes, before any pipeline feature work |
| Live demo breaks | Record a video backup during Phase 5 rehearsal; narrate calmly and switch to it if needed |
| Scope creep into WON'T items | `BL.md` is the contract — if it's not MUST/SHOULD, it doesn't exist until Phase 5 buffer, and even then, no |
| Judge tries two images and gets the same answer | Fixed: four events, four culprits. Was the single most damaging problem in the build |
| Pipeline names a vessel for a spill that isn't there | Fixed: attribution gate, enforced server-side. See `evaluator_brief.md` |
