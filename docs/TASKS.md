# TASKS — Granular Checklist
**OceanTrace · check off as you go; each task ~15–45 min unless noted**

## Pre-round (before the clock starts — do not skip, see DRD.md §4)
- [ ] Download 2–3 Zenodo SAR sample images
- [ ] Fix the demo scenario: location, spill time, guilty vessel name/route
- [ ] Draft + test the synthetic AIS generator script
- [ ] Confirm `/backend` (`pip install -r requirements.txt`) and `/frontend`
      (`npm install`) both run clean on every laptop

## R0 — Everyone, first 20 minutes
- [ ] Read the API contract in `SACD.md` §3 out loud as a team — no one starts coding
      against a guessed shape

## R1 — Detection & CV (owns M1, `/api/detect`)
- [ ] Load sample SAR image, basic preprocessing (denoise/normalize)
- [ ] Thresholding + morphological cleanup → binary mask
- [ ] Connected components → polygon extraction (Shapely)
- [ ] Compute area, perimeter, centroid, bounding box
- [ ] Assign a confidence value (simple heuristic is fine — e.g. based on mask compactness)
- [ ] (SHOULD) Look-alike confidence flag — S4
- [ ] (SHOULD) Age estimate stub/heuristic — S2
- [ ] Expose as `POST /api/detect` returning the exact shape in `SACD.md` §3

## R2 — Drift & Oceanography (owns M2a, `/api/drift`, S1)
- [ ] Define synthetic/static current + wind vector field for the demo region
- [ ] Particle advection step function (position update per timestep)
- [ ] Run backward N steps from spill centroid → particle cloud → origin point + radius
- [ ] Estimate spill time window from backward run duration
- [ ] (SHOULD) Run forward N steps → forecast path — S1
- [ ] Expose as `POST /api/drift` returning the exact shape in `SACD.md` §3

## R3 — AIS & Attribution (owns AIS generator, M2b, `/api/attribution`, S3, S4)
- [ ] Generate vessel roster (~20–30 vessels) per DRD.md spec
- [ ] Generate position time series, one vessel deliberately routed through origin/window
- [ ] Spatial filter (distance from origin ≤ radius)
- [ ] Temporal filter (present during spill window)
- [ ] Trajectory filter (does path intersect origin zone)
- [ ] Implement weighted risk score (formula in MASTER_REFERENCE_INDEX.md)
- [ ] Rank vessels, attach score breakdown
- [ ] (SHOULD) Generate plain-language "why flagged" reason strings — S3
- [ ] Expose as `POST /api/attribution` and `GET /api/vessels/{id}` per `SACD.md` §3

## R4 — React Frontend & Integration (owns M3)
- [ ] Vite + React scaffold, `fetch('/health')` proving CORS works — do this before anything
      else (Phase 1 checkpoint in `PP.md`)
- [ ] react-leaflet map shell, base layer, centered on the demo region
- [ ] Spill card + polygon layer wired to `/api/detect`
- [ ] Origin zone layer (+ forecast path if ready) wired to `/api/drift`
- [ ] Funnel counter UI + ranked vessel list wired to `/api/attribution`
- [ ] Vessel detail panel ("why flagged") wired to `/api/vessels/{id}`
- [ ] One button per demo step (`PRD.md` §4), sequential, no routing library needed
- [ ] Loading state + visible error state on failed fetches (no silent blank screens)

## R5 — Data prep & presentation
- [ ] Own the pre-round checklist above
- [ ] Write the demo script (see MASTER_REFERENCE_INDEX.md) and rehearse timing
- [ ] Seed realistic vessel names/labels (not "vessel1", "test")
- [ ] Own Phase 5 rehearsal — call the code freeze
- [ ] Record backup video/screenshots of a full working run

## Shared — last hour, everyone
- [ ] Full rehearsal run-through on a cold start (kill and restart both servers once)
- [ ] Fix only what breaks
- [ ] Confirm backup recording exists
