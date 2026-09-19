# TASKS — Granular Checklist
**OceanTrace · check off as you go**

**Status: the build is done.** All MUSTs, all SHOULDs, plus work that was not in the
original plan. What remains is one team decision and one rehearsal — jump to
[What's actually left](#whats-actually-left).

Verify the whole thing in one command:

```bash
cd backend && python scripts/smoke_test.py     # 78 assertions over the live API
```

---

## Pre-round
- [x] Download Zenodo SAR sample images — `fetch_sar_tiles.py`
- [x] Fix the demo scenario: location, spill times, guilty vessels — `app/config.py`
- [x] Draft + test the synthetic AIS generator — `generate_ais.py`
- [ ] **Confirm `pip install -r requirements.txt` and `npm install` run clean on every
      laptop.** Not done, and it has already bitten once — see the note at the bottom.

## R0 — Everyone, first 20 minutes
- [x] Read the API contract in `SACD.md` §3 as a team
- [ ] Re-read it — the contract has grown: uploads, the look-alike fields, the age
      estimate, the 409 refusal, and `?spill_id=` on `/api/vessels/{id}`

## R1 — Detection & CV (`/api/detect`)
- [x] Load sample SAR image, denoise/normalise
- [x] Otsu threshold + morphological cleanup → binary mask
- [x] Contour extraction → polygon (Shapely)
- [x] Area, perimeter, centroid, bounding box
- [x] Confidence heuristic (size + compactness + contrast)
- [x] **S4 look-alike flag** — ambiguity + faintness, lowers the reported confidence
- [x] **Attribution gate** — refuse to trace or attribute a detection below the bar.
      Thresholds measured against the dataset's labels, not guessed
- [x] Accuracy measured against ground truth — `validate_detector.py`, mean IoU 0.43
- [x] `POST /api/detect` and `POST /api/detect/upload`

## R2 — Drift & Oceanography (`/api/drift`)
- [x] ~~Define a synthetic current + wind field~~ → **replaced with real data.**
      `fetch_ocean_forcing.py` pulls hourly current + 10 m wind per event from Open-Meteo;
      drift is `current + 3% × wind`
- [x] Particle advection step function
- [x] Backward run → particle cloud → origin + uncertainty radius. Recovers ground truth
      to 22–91 m across the four events
- [x] Spill time window from the hindcast
- [x] **S1 forward run** → forecast path
- [x] **S2 age estimate** — from the slick's extent along the drift axis, independent of
      the assumed satellite-pass lag
- [x] Hindcast path returned so the map can animate the backward drift
- [x] `POST /api/drift`

## R3 — AIS & Attribution (`/api/attribution`)
- [x] Vessel roster (26) covering **four** spill events
- [x] Position time series; each event gets a guilty vessel, a near-miss and a false positive
- [x] Vessel homes constrained to a seaward bearing arc — without it a sixth of the roster
      spawned on dry land
- [x] Spatial → temporal → trajectory filters
- [x] Weighted risk score, 8 sub-scores, weights sum to 1.00
- [x] Ranking + score breakdown
- [x] **S3 plain-language "why flagged" reasons**, generated from the same numbers as the
      score
- [x] `POST /api/attribution`, `GET /api/vessels/{id}?spill_id=`

## R4 — React Frontend & Integration
- [x] Vite + React, `/health` fetch proving CORS
- [x] react-leaflet map, centred on the region
- [x] Spill card + polygon layer
- [x] **SAR tile rendered under the polygon** with an opacity slider
- [x] Origin zone + particle cloud + animated backward drift + forecast path
- [x] Funnel counter, ranked vessel list, why-flagged panel
- [x] Tile selector and upload control
- [x] Loading and error states; refused detections disable the downstream steps
- [x] Map fits its data instead of a fixed zoom
- [x] **Light + dark themes**, OS-following with a persisted override, WCAG AA checked
- [x] Offline basemap — Natural Earth coastline under the raster tiles

## R5 — Data prep & presentation
- [x] Own the pre-round data scripts
- [x] Realistic vessel names
- [x] Demo-upload set, including two tiles with no oil, for showing the refusal
- [x] Demo script written — `MASTER_REFERENCE_INDEX.md`, with `evaluator_brief.md` and
      `JUDGE_QA_PREP.md` for the Q&A
- [ ] **Rehearse it, timed**
- [ ] **Record the backup video**
- [ ] Call the code freeze

---

## What's actually left

1. **Decide the parallel-build question.** There is a second plain HTML/JS + Leaflet
   implementation of this project underway elsewhere. Pick one. Not a code task, and it
   invalidates everything else if it goes the other way.
2. **Rehearse and record.** `PRD.md`'s 60-second target is verified by script (~0.5 s) but
   never by a human driving and talking at the same time. No backup video exists, which is
   the mitigation the risk register names for "live demo breaks".
3. **Every laptop runs it.** `python-multipart` was added for uploads; an existing setup
   fails at import until `pip install -r requirements.txt` is re-run. If a laptop has more
   than one Python, use `python -m uvicorn ...` rather than bare `uvicorn` — the shim can
   resolve to a different interpreter than your packages.
4. **Cold-start test on the presenting laptop**, including venue wifi. The map degrades
   gracefully with no internet now, but nobody has tried it at the venue.

Ranked detail in `next_steps.md`.
