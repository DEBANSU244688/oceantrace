# NEXT STEPS — OceanTrace

**Written after diffing the scaffold in this repo against `PRD.md` / `BL.md` / `PP.md`.**
Ordered by "what loses us marks if it's missing on the day", not by effort.

## Where the build actually stands

| Item | Doc ref | Status |
|---|---|---|
| M1 detection + characterisation | `BL.md` MUST 1 | Built (`detector.py`, `characterize.py`) |
| M2 drift + attribution chain | `BL.md` MUST 2 | Built (`drift_engine.py`, `attribution.py`) |
| M3 FastAPI ↔ React end-to-end | `BL.md` MUST 3 | Built, CORS configured, all 6 endpoints live |
| Real Zenodo SAR imagery | `PRD.md` §5 | Built (`fetch_sar_tiles.py`, 3 Sentinel-1 tiles) |
| S1 forecast path | `BL.md` SHOULD | Built (`drift_engine.forecast`, dashed line on map) |
| S3 "why flagged" reasons | `BL.md` SHOULD | Built (`reasons[]` → `VesselDetail.jsx`) |
| S2 spill age estimate | `BL.md` SHOULD | **Not built** |
| S4 look-alike confidence note | `BL.md` SHOULD | **Not built** |

All three MUSTs are done, and the pipeline now runs on real Sentinel-1 imagery rather than
the synthetic stand-in. What's left is the two remaining SHOULDs and the gaps below — some
of which the docs imply, and two of which only became visible once real tiles zoomed the
map in far enough to see them.

---

## P0 — Blocks a stated success criterion

### 0. ~~Every image produced the same origin, funnel and culprit~~ — FIXED
The most damaging problem in the build, and it was self-inflicted. To make real
imagery compose with the synthetic AIS, `bbox_anchored_at` anchored *every* tile so its
detected slick landed on the same `DETECTED_LAT/LON`. Same centroid → same hindcast → same
origin → same ranked list. Changing the image changed the pixels and nothing else.

It does not matter how honest the code is if the observable behaviour is identical to a
hardcoded answer. This was the direct counter-evidence to the one question the demo most
needs to survive.

- [x] `config.SCENARIOS` — four spill events in the region, each with its own origin,
      spill time and guilty vessel
- [x] Each sample tile bound to an event in `SAMPLE_IMAGES`; `fetch_sar_tiles.py` anchors
      on that event's detected point
- [x] `generate_ais.py` builds one roster covering all four events — each gets a guilty
      vessel, a near-miss and a false positive, so every event's funnel is interesting
- [x] Origins ≥ 35 km apart and bathymetry-checked; vessel homes drawn around the region
      centre rather than any one origin
- [x] Uploads rotate through the events and the response names which one it used, since an
      uploaded tile has no geocoding and the placement is a choice, not a finding
- [x] Smoke test asserts four tiles give four distinct origins and four distinct culprits
- [x] Spill window now shows the date — two events shared a time of day and looked like a
      stuck value
- [ ] Note the deviation from `BL.md`'s WON'T list when presenting (already annotated there)

### 1. ~~Swap in a real Zenodo SAR image~~ — DONE
`PRD.md` §5 requires "at least one detection result on a *real* Zenodo SAR sample (not a
synthetic image)". Right now `SAMPLE_IMAGES` has exactly one entry and it is synthetic
(`generate_sample_image.py`). Needs internet, so it is a pre-round task, not a
clock-running task — `DRD.md` §4 says the same.

- [x] `scripts/fetch_sar_tiles.py` pulls three Sentinel-1 tiles from Zenodo record 15298010
      (CC-BY-4.0) using HTTP range requests, so it never downloads the 1.1 GB archive
- [x] All three registered in `SAMPLE_IMAGES`, real ones first so the app auto-loads real
      imagery; the synthetic tile stays as an offline fallback
- [x] `scripts/validate_detector.py` scores the detector against the dataset's own masks:
      mean IoU 0.43, median 0.41, 27/70 tiles above 0.5
- [x] Full flow re-run against all four tiles — each recovers the origin and ranks
      BAY VOYAGER first at 0.94
- [x] Tile selector in the UI, so a judge asking "does it only work on that one image?"
      gets an answer rather than a story

**Fallout worth knowing about:** real tiles are 256 px at 10 m/px = 2.5 km across, versus
the synthetic tile's 36 km. That exposed a scenario bug — see #2 below — and forced the map
to fit its data rather than sit at a fixed zoom.

### 2. ~~The demo scenario was on land~~ — FIXED
`REGION_CENTER`, `ORIGIN_LAT/LON` and everything derived from them sat 2–3 m *above* sea
level, roughly 15 km inland of Paradip. The 36 km synthetic tile hid it; the first real
2.5 km tile drew an oil slick on top of the town.

- [x] Scenario moved to 20.05 N, 86.95 E — ~255 m of water, checked against ETOPO1
- [x] `SEAWARD_BEARING_DEG` added to `generate_ais.py`: vessel homes now come from the
      10°–250° arc, which is open water out to 90 km. Without it about a sixth of the
      roster spawned on dry land
- [x] AIS regenerated, synthetic tile regenerated, all four tiles re-verified
- [ ] **If anyone moves the scenario again, re-measure that bearing arc.** It is specific
      to this origin, and nothing checks it at runtime

### 0b. ~~A tile with no oil in it still got attributed to a vessel~~ — FIXED
Uploading `06_no_oil_lookalikes_only.png` — a tile the dataset labels as containing no oil
— produced a polygon, a traced origin, and a named suspect at 92%. The system was
confidently accusing a real vessel of a spill that never happened. In an NTRO context that
is the worst failure mode available, and it is much worse than missing a detection.

- [x] `detector.attribution_gate()` — confidence >= 0.40 and lookalike_risk <= 0.60
- [x] `/api/drift` and `/api/attribution` return **409** for anything that fails it,
      enforced server-side rather than only in the UI
- [x] UI disables both steps and shows the reason in red
- [x] Thresholds measured against the dataset's labels, not guessed:
      `validate_detector.py --gate` → blocks 60/60 no-oil tiles, 12/60 (20%) of real slicks
- [x] Smoke test asserts both no-oil tiles are refused at both endpoints

Worth knowing: the detector *already* refused outright on 28 of 60 no-oil tiles (no region
above the size threshold at all). The gate catches the remaining 32.

### 3. ~~The demo needs internet, but `PRD.md` says it must not~~ — FIXED
`PRD.md` §5: "Runs fully offline/local — no dependency on a live internet connection".
`MapView.jsx` loads CARTO raster tiles over HTTPS and warns if `VITE_CARTO_BASEMAPS_API_KEY`
is missing. Venue Wi-Fi failing means the map renders blank under the data layers.
`PP.md` Phase D flags this as a test; it is really a code fix.

Neither of the options originally listed here was right. Caching raster tiles violates
both CARTO's and OSM's usage policies, and only covers the zooms and area you thought to
fetch. A blank fallback rectangle tells the viewer nothing.

- [x] `scripts/fetch_coastline.py` pulls **public-domain Natural Earth** land polygons,
      clips them to the region and writes a 35 KB GeoJSON
- [x] Served at `GET /api/basemap/land`, drawn in a pane at z-index 150 — below Leaflet's
      tile pane (200), so CARTO covers it when online and it remains when offline. No
      fallback logic needed
- [x] Attribution credits Natural Earth alongside CARTO/OSM, since either can be what is
      actually on screen
- [x] Verified with CARTO blocked at the network layer: coastline, SAR tile, origin
      cloud, vessel track all render; the map says "basemap offline"

**Two bugs found while testing this**, both of which would have shown up live:
- `fitBounds` animates by default, and Leaflet drops one issued while a previous zoom is
  still animating — so clicking Detect then Trace origin quickly left the origin zone
  off-screen. Now `animate: false`.
- The offline notice never fired: `tileerror` is emitted by the TileLayer, not the map, so
  `useMapEvents` never saw it. Moved onto the layer's `eventHandlers`.

### 4. ~~The SAR image is never shown on the map~~ — DONE
`PRD.md` §4 step 2: "spill polygon overlaid on **the image**". Today the polygon floats on
a basemap — the judge never sees the SAR pixels the detection came from. This is the single
most convincing visual in the whole demo and it is currently missing.

- [x] `GET /api/images/{image_id}` serves the tile (`main.py`)
- [x] `/api/detect` now returns `image_id`, `image_bbox`, `image_url` (contract updated in
      `SACD.md` §3)
- [x] `MapView.jsx` draws it as an `<ImageOverlay>` in a dedicated pane at z-index 250 —
      above the basemap, below every vector layer
- [x] Opacity slider bottom-left of the map. Fading the tile mid-demo is the cheapest proof
      that the polygon traces the real slick rather than being drawn from an answer key

---

## P1 — The two remaining SHOULD items (`PP.md` Phase B)

### 5. ~~S2 — estimated spill age~~ — DONE
Owner R2. `config.HINDCAST_HOURS` and the hindcast particle spread already contain
everything needed; nothing new needs simulating.

- Return `estimated_age_hours` + a confidence on `/api/drift` (extend `DriftResponse`)
- Derive confidence from the particle-cloud radius: tighter cloud → tighter age estimate
- Show it in `SpillCard.jsx` next to the spill window

### 6. ~~S4 — look-alike confidence note~~ — DONE
Owner R1. `detector.py` already finds every above-threshold contour and scores them by
`area × compactness`, then discards the losers — the decoy count exists and is thrown away.

- Return `candidate_regions` and `rejected_as_lookalike` from `detect()`
- Surface in the UI as "3 candidate regions found, 2 rejected as likely look-alikes"
- No new detection logic. `BL.md` S4 explicitly does not want a real classifier here

---

### 13. ~~The drift engine's best visuals are computed and then discarded~~ — DONE
`drift_engine.py` already produces a 150-particle probability cloud and the centroid's
path over time. The API returns the cloud but the map never draws it, and the backward
path is dropped in `main.py` entirely (only the forecast path survives).

So `PRD.md` §4 step 3 — *"map animates backward drift"* — is currently a static amber
circle. The physics is done; only the rendering is missing. This is the cheapest
remaining upgrade to how the demo *looks*, and it is the step judges are told to watch.

- Return `hindcast_path_geojson` alongside `forecast_path_geojson`
- Draw the particle cloud as small low-opacity dots inside the origin zone
- Animate the path with a simple index-over-time `setInterval`, no animation library

## P2 — Robustness before rehearsal

### 7. ~~`/api/vessels/{id}` depends on hidden global state~~ — FIXED
`main.py` keeps `_latest_attribution_spill_id` at module level and 400s if it is unset.
A judge who reloads the browser mid-demo, or opens `/docs` and calls the endpoint directly,
gets an error. Take `spill_id` as a query param with the global as fallback.

### 8. ~~CORS only allows port 5173, but Vite silently moves off it~~ — FIXED
Hit this live: with 5173 already in use, Vite prints "Port 5173 is in use, trying another
one..." and serves on **5174** — which `main.py`'s `allow_origins` does not include. Every
API call then fails CORS and the app looks broken for a reason nobody will diagnose calmly
at a demo table. `PP.md` names CORS the #1 first-hour failure mode; this is the version of
it that survives into hour 10.

Fix: either add 5174–5176 to `allow_origins`, or pin the port with `--strictPort` in the
`dev` script so a clash fails loudly instead of quietly relocating.

### 9. ~~No automated cold-start check~~ — DONE
`README.md` claims the pipeline is verified against ground truth, but there is no test file
in the repo. `PP.md` Phase D and the `TASKS.md` shared-final-hour block both call for a cold
start run. Write `backend/scripts/smoke_test.py` that walks
detect → drift → attribution → vessel and asserts the guilty vessel ranks first. One command,
run it after every change.

### 10. Commit `docs/`
`git status` shows `docs/` untracked — the whole planning set (`PRD`, `SACD`, `BL`, `PP`,
`DB`, `DRD`, `TASKS`, `MASTER_REFERENCE_INDEX`, this file) is outside version control. If
teammates clone the repo they get code with no contract to build against.

---

## P3 — Team decision, not code

### 14. ~~Decide on an "upload your own image" feature~~ — BUILT
Worth doing, with guardrails — see the reasoning below. `DRD.md` §1 says no upload flow
is needed, so this is a deliberate deviation, not an oversight.

Scope it as: accept an upload, place it at the scenario location exactly as
`fetch_sar_tiles.py` already does, run the full chain. **Do not ship it before #6 (S4)** —
Otsu always finds *something* dark, so without a look-alike guard, a judge uploading a
non-SAR image gets a confident-looking false detection on the projector.

### 11. Reconcile with the parallel build
`README.md` notes a second plain HTML/JS + Leaflet implementation of this project underway
elsewhere. `SACD.md` §4 and the submitted PPT both commit to React + FastAPI. Pick one
before the clock starts — two half-finished builds is the worst outcome available.

### 12. Demo script rehearsal
`MASTER_REFERENCE_INDEX.md` has the script written. `PP.md` Phase E wants it timed and a
backup video recorded. Neither has happened yet. `PRD.md` §5 requires the full flow in
under 60 seconds — that number is untested.

---

## Suggested order — what is actually left

1. **#11 Decide the parallel-build question.** Still the only thing that can
   invalidate everything else. Not a code task.
2. **#10 Commit `docs/`.** The whole planning set is still untracked.
3. **#12 Rehearse, time it, record the backup video.** `PP.md` Phase E.
   Nobody has done this yet, and `PRD.md`'s 60-second target is still untested
   with a human driving instead of a script. This is now the highest-value hour
   the team can spend.

Everything else on this list is built. Run `python scripts/smoke_test.py`
against a live backend to confirm — 78 checks, covering the upload path and the
attribution gate.

## Already done

**Data and scenario**
- #1 real Sentinel-1 tiles from Zenodo, with measured detector accuracy
- #2 scenario moved offshore (it was on land, 2–3 m above sea level)

**Features**
- #4 SAR tile rendered under the spill polygon, with an opacity slider
- #5 S2 slick age estimate, derived from slick geometry rather than restating
  the assumed satellite-pass lag
- #6 S4 look-alike risk — ambiguity + faintness, lowers reported confidence
- #13 particle cloud drawn, backward drift animated
- #14 upload your own image, same pipeline, same anchoring as the Zenodo tiles

**Robustness**
- #3 offline basemap — public-domain Natural Earth coastline under the raster tiles
- #7 `/api/vessels/{id}` takes `?spill_id=`, survives a browser reload
- #8 CORS covers Vite's 5173–5176 fallback range
- #9 `scripts/smoke_test.py` — 78 checks over the live HTTP API
- Basemap failure now announces itself instead of rendering a silent black void

**Design**
- Minimalist UI pass: no panel boxes, one accent, hairline rules, tile selector,
  map fits its data, vessel tracks trimmed to the spill window
