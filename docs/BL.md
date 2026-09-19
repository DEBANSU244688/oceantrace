# BL — Backlog (MoSCoW)
**OceanTrace · Rule: without this, there is no demo. Max 3 MUSTs — be brutal.**

**Status: all 3 MUSTs and all 4 SHOULDs are built.** Verified by
`backend/scripts/smoke_test.py` — 78 assertions over the live HTTP API.

## MUST (build first, in this order)
1. **M1 — Detection & characterisation pipeline**: sample SAR image → mask → polygon +
   area/perimeter/centroid/confidence. *Non-negotiable — without it there's no spill to
   trace.*
2. **M2 — Drift + attribution chain**: backward particle sim → origin zone → synthetic AIS
   funnel (spatial → temporal → trajectory) → weighted risk score → ranked vessel list.
   *This is the actual differentiator the PS asks for — the whole "who did it" story.*
3. **M3 — FastAPI + React integration, end-to-end**: every step in `PRD.md` §4 is a real
   API call, not mock frontend data. *With a split frontend/backend, wiring them together is
   itself a MUST-level risk, not a polish step — see `PP.md`'s Phase 1 checkpoint.*

## SHOULD — all four built

- ✅ **S1 — Forecast path**: forward particle sim, drawn as a dashed line on the map.
- ✅ **S2 — Estimated spill age**: measured from the slick's own extent along the drift
  axis divided by the drift speed, with confidence from elongation. Deliberately
  *independent* of the assumed satellite-pass lag, so the two can be compared — on the
  synthetic tile it returns 3.7 h against an assumed 4.0 h.
- ✅ **S3 — "Why flagged" panel**: generated from the same numbers the score is built from,
  so there is no explanation layer that can disagree with the score.
- ✅ **S4 — Look-alike confidence note**: reported as *ambiguity* (how close the runner-up
  dark region scored) plus *faintness* (contrast against the scene mean). It lowers the
  reported confidence rather than sitting in a field nobody reads. No classifier, as
  specified.

## Built beyond the backlog

Not in the original MoSCoW, added because the build needed them:

- **Real Sentinel-1 imagery** (Zenodo, CC-BY-4.0) with accuracy measured against the
  dataset's own ground-truth masks — mean IoU 0.43.
- **Real ocean forcing** — hourly current + 3% windage from Open-Meteo, per event. This
  retires the simplification `DRD.md` §2 originally accepted.
- **Attribution gate** — refuses to trace or attribute a detection that does not clear
  confidence ≥ 40% and look-alike risk ≤ 60%. Without it, a tile containing no oil still
  produced a traced origin and a named suspect, which is a false accusation and a worse
  failure than a missed detection. Blocks 60/60 no-oil tiles.
- **Upload your own image** — a judge can hand over a file and watch the same pipeline run.
- **Offline basemap** — public-domain Natural Earth coastline, so `PRD.md` §5's offline
  requirement holds without violating any tile provider's usage policy.
- **Light + dark themes**, WCAG AA checked.
- **`smoke_test.py`** — 78 assertions over the live API, for the cold-start check
  `PP.md` Phase D asks for.

## WON'T (this round — say this explicitly in the pitch, don't hide it)
- Live/real-time AIS feed ingestion — *cut because real-time infra isn't buildable or
  demoable safely in 10h; synthetic data proves the algorithm works.*
- Deep learning model trained from scratch — *cut because training + validation eats the
  whole time budget for marginal demo benefit over classical CV.*
- ~~Multi-spill / multi-region generalisation~~ — **partially reversed, deliberately.**
  *The original cut assumed one scenario was enough to prove the chain. It is not: with a
  single origin, every sample tile was anchored to the same point and therefore produced the
  same origin, the same funnel and the same culprit. That is indistinguishable from a
  hardcoded answer to anyone watching, which undermines the entire demo. The region now
  carries four spill events and each tile is bound to one. Still one spill analysed at a
  time — no multi-spill UI, no simultaneous tracking — so the concurrency work this item was
  really about stays cut.*
- Auth, persistence across restarts, deployment pipeline — *cut, irrelevant to a
  single-scenario local demo.*
- Mobile app — *cut, out of scope for a dashboard-style deliverable.*
- **Production build of the React app** (`vite build`) — *cut, the dev server demos fine and
  a build step is one more thing that can break in the last hour.*
- **Any frontend state library (Redux/Zustand) or router** — *cut, the demo flow is one
  linear page; plain `useState` is enough.*

## Stub strategy — not used, and worth saying so

The plan allowed stubbing S1–S4 with precomputed results if they threatened the timeline.
**Nothing was stubbed.** Every value in the UI is computed at request time from the real
pipeline. If a judge asks whether anything on screen is canned, the answer is no, and the
Network tab backs it up.
