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

## Quick-reference: tech stack
**Backend**: Python 3.11+ · FastAPI + Uvicorn · OpenCV/scikit-image · Shapely · NumPy ·
Pandas · GeoPandas · in-memory state (no DB server).
**Frontend**: React (Vite) + react-leaflet, plain `useState`/`fetch`, no Redux/router.
No trained models, no live AIS feed, no PostGIS, no Docker, no auth, no production
frontend build — see `SACD.md` §4 for why. This matches the submitted PPT's Technical
Approach slide (FastAPI backend, Leaflet map, React as the app shell).

## Quick-reference: API contract (full detail in `SACD.md` §3)
```
GET  /api/scenario                 → sample images + region center
POST /api/detect      {image_id}   → spill polygon + area/perimeter/centroid/confidence
POST /api/drift       {spill_id}   → origin zone + spill window (+ forecast path)
POST /api/attribution {spill_id}   → funnel counts + ranked vessel list w/ score breakdown
GET  /api/vessels/{id}             → trajectory + full score breakdown + reasons
```

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

## Quick-reference: demo scenario defaults (swap freely)
- Location: Bay of Bengal, off Paradip Port, Odisha (~20.31°N, 86.61°E)
- Synthetic roster: ~20–30 vessels, one deliberately routed through the origin zone with a
  speed/course anomaly during the spill window (see `DRD.md` §3)

## Demo script (rehearse before code freeze)
1. **Hook (30s)**: "Marine oil spills usually go unattributed. We built a pipeline that
   turns one satellite image into a ranked list of suspect vessels."
2. **Live flow (2–3 min)**: load image → spill detected + characterised → click "Trace
   Origin" → backward drift animates → click "Analyse AIS" → funnel narrows (e.g. 27 → 9 →
   5 → 3) → ranked vessels appear → click top vessel → trajectory + "why flagged" reasons.
   Every click is a real call from the React app to the FastAPI backend.
3. **Deliberate cuts, say this out loud**: "We deliberately cut live AIS ingestion and
   custom model training this round to focus on proving the full attribution chain works
   end-to-end on a real API — that's the next sprint."
4. **Technical highlight (30s)**: pick one real story — e.g. the backward/forward particle
   drift model, the weighted/explainable attribution score, or the clean API contract that
   let backend and frontend build in parallel without blocking each other.

## Key decisions/assumptions made while drafting these docs (confirm or override)
- Project name: "OceanTrace" — finalised, matches the submitted idea PPT
- **Architecture: FastAPI backend + React (Vite) frontend with react-leaflet for mapping**
  — matches the PPT's Technical Approach slide; this replaces an earlier Streamlit-based
  draft of these docs, which is no longer in use
- MVP scope: classical CV detection (not trained deep learning), physics-based particle
  drift, rule-based (non-ML) AIS scoring — see `SACD.md` §4
- Assumed team size 4–6 for role split in `PP.md`/`TASKS.md` — merge roles if smaller, but
  keep R4 (frontend/integration) separate, it carries the most integration risk in this stack
- Demo scenario location defaulted to Paradip, Odisha — a placeholder for concreteness, swap
  freely

## Risk register (top 3)
| Risk | Mitigation |
|---|---|
| Frontend↔backend integration discovered broken late | CORS + a live health-check fetch is the Phase 1 checkpoint in `PP.md` — prove it in the first 75 minutes, before any pipeline feature work |
| Live demo breaks | Record a video backup during Phase 5 rehearsal; narrate calmly and switch to it if needed |
| Scope creep into WON'T items | `BL.md` is the contract — if it's not MUST/SHOULD, it doesn't exist until Phase 5 buffer, and even then, no |
