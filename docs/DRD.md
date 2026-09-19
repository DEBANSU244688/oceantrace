# DRD — Data Requirements Document
**OceanTrace · what data the demo needs, and where it comes from**

## 1. Satellite imagery (real data) — DONE
- **Source used**: *Refined Deep-SAR Oil Spill (SOS) dataset*, Zenodo record
  [15298010](https://doi.org/10.5281/zenodo.15298010), CC-BY-4.0. The PS names the
  Sentinel-1 SAR Oil Spill Dataset; that record is 40 GB, this one is the same family of
  imagery at a workable size and ships ground-truth masks too.
- **Fetched by** `scripts/fetch_sar_tiles.py`, which reads the zip's central directory over
  HTTP range requests and pulls only the members it needs — the 1.1 GB archive is never
  downloaded. Three tiles are registered; `fetch_demo_uploads.py` pulls seven more for the
  upload button, including two the dataset labels as containing **no oil**.
- **Accuracy is measured, not asserted**: `scripts/validate_detector.py` scores the
  detector against the dataset's own masks — mean IoU 0.43, median 0.41, 27/70 above 0.5.
- **Georeferencing**: the SOS tiles are crops shipped without geocoding, so each is anchored
  so its detected slick lands on its event's origin. Real pixels, our position — say this
  plainly if asked.
- **Optional secondary**: 1 optical/EO image, used only to illustrate the "secondary
  confirmation layer" concept in the demo narrative — not required for the pipeline to run.
- Serve these as static files the FastAPI backend can load by `image_id` (see `/api/scenario`
  in `SACD.md` §3) — no upload flow needed for the demo.

## 2. Ocean current + wind field (for the drift engine)
For a 10h build, do **not** integrate a live API (Copernicus Marine, NOAA, etc.) unless
someone on the team has already used one — auth/setup risk is too high for the time budget.
- ~~**Recommended**: a static or lightly-randomized synthetic vector field~~ —
  **superseded, we use real data.** `scripts/fetch_ocean_forcing.py` pulls the real hourly
  ocean current and 10 m wind over each spill event's own coordinates and dates from
  Open-Meteo (free, no API key, no registration) and caches them to disk, so the demo still
  runs offline. Drift is `current + 3% × wind`, the conventional windage for oil.
- The four events now drift at 0.64–2.19 km/h on bearings from 204° to 324° — genuinely
  different per event, where the old constant made them identical. The drift paths visibly
  curve on the map because the forcing varies hour to hour.
- The static vector in `app/config.py` survives only as a fallback for when
  `data/ocean_forcing.json` has not been built. The demo must not depend on a file that
  needs the internet to create.

## 3. AIS data — synthetic, by design
The official PS explicitly permits this: *"Real AIS if available may be used else synthetic
data can be prepared for the region of oil spill to demonstrate the functioning of the
algorithm."* Real historical AIS matched precisely to a chosen spill scenario is not
realistically obtainable in this window — build the generator instead.

**The demo scenario, as built:**
Bay of Bengal, **offshore** of Paradip Port, Odisha — region centre 20.05°N, 86.95°E, with
four spill events between 19.72–20.28°N and 86.78–87.18°E. Fits the NTRO/India context and
gives the team a coastline they can reason about while building.

Not a free-swap placeholder any more. An earlier draft used ~20.31°N, 86.61°E, which is
about 15 km *inland* — a 36 km-wide synthetic tile hid that, a 2.5 km real Sentinel-1 tile
draws a slick on top of the town. Every coordinate is now checked against ETOPO1
bathymetry, and `generate_ais.py`'s seaward bearing arc is measured for this specific
origin. **Moving the scenario means re-measuring both.**

**Synthetic roster spec (as built: 26 vessels across four events):**
- ~20–30 vessels in a bounding box around the scenario coordinates
- Track points every 15–30 min over a 48–72h window bracketing the estimated spill window
- **One vessel per event deliberately routed** through that origin during that spill
  window, with a speed drop and/or course deviation — four events, four different guilty
  vessels, so changing the image changes the answer
- Remaining vessels: a spread of near-misses (close but wrong time), false positives
  (right time, far away), and clean traffic (neither) — this is what makes the funnel
  animation in Step 4 of the demo (see `PRD.md` §4) actually demonstrate filtering, not just
  return one result
- Fields per position: `vessel_id, ts, lat, lon, speed_knots, course_deg, status` (see
  `DB.md` §4). The generator can run entirely standalone, before the round starts, and just
  gets loaded by the FastAPI backend at startup.

## 4. Pre-round prep checklist

- [x] Download Zenodo SAR sample images — `fetch_sar_tiles.py`, committed
- [x] Decide the fixed demo scenario — four events, in `app/config.py`, committed
- [x] Write and test the synthetic AIS generator — `generate_ais.py`, committed
- [x] Fetch the real ocean forcing — `fetch_ocean_forcing.py`, committed
- [ ] **Confirm `pip install -r requirements.txt` and `npm install` run clean on every
      laptop.** Still outstanding, and it already bit once: `python-multipart` was added for
      the upload endpoint, and an existing setup fails at import until it is re-installed.
      Use `python -m uvicorn ...` rather than bare `uvicorn` if a laptop has more than one
      Python — the shim can resolve to a different interpreter than your packages.
- [ ] Rehearse and record the backup video (`PP.md` Phase E) — not done

Real AIS was investigated and not used. Free sources are either registration-gated
(AISStream, BarentsWatch) or region-limited to waters we are not demonstrating in
(MarineCadastre is US-only). Nothing open covers the Bay of Bengal, and a US dataset would
contain no known spill to check attribution against. The PS permits synthetic AIS
explicitly — see §3.
