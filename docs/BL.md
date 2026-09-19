# BL — Backlog (MoSCoW)
**OceanTrace · Rule: without this, there is no demo. Max 3 MUSTs — be brutal.**

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

## SHOULD (only after all 3 MUSTs work end-to-end)
- **S1 — Forecast path**: forward particle sim showing predicted future slick movement
- **S2 — Estimated spill age**: temporal-comparison estimate with a confidence value
  (PS marks this "if feasible" — genuinely optional)
- **S3 — "Why flagged" explainability panel**: per-vessel plain-language reasons
  (distance, temporal overlap, trajectory, anomalies) — strong demo value for low effort
  since the score breakdown already exists in the `/api/attribution` response (see `SACD.md`)
- **S4 — Look-alike confidence note**: a short flag in the UI when detection confidence is
  lowered by look-alike risk (low wind areas, biogenic slicks etc.) — shows judges the team
  understands the real failure mode, doesn't need a real classifier behind it

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

## Stub strategy for SHOULD items that touch the critical path
If S1–S4 threaten the timeline: stub with a hardcoded/precomputed result that *looks* real
in the demo (e.g. a precomputed forecast path for the one demo image) rather than cutting
the visual entirely — judges respond to what they see moving on the map. A stub still goes
through the real API endpoint (return a fixed JSON payload from `/api/drift`'s
`forecast_path_geojson` field) so the frontend code doesn't need a special case.
