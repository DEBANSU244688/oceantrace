# DRD — Data Requirements Document
**OceanTrace · what data the demo needs, and where it comes from**

## 1. Satellite imagery (real data)
- **Source**: Sentinel-1 SAR Oil Spill Dataset on Zenodo (named directly in the official PS).
- **Action before the round starts**: download and pre-select 2–3 sample images with clear,
  demo-friendly slicks (visible dark region, not ambiguous). Do this ahead of time —
  dataset browsing/downloading during the 10h window is wasted build time.
- **Optional secondary**: 1 optical/EO image, used only to illustrate the "secondary
  confirmation layer" concept in the demo narrative — not required for the pipeline to run.
- Serve these as static files the FastAPI backend can load by `image_id` (see `/api/scenario`
  in `SACD.md` §3) — no upload flow needed for the demo.

## 2. Ocean current + wind field (for the drift engine)
For a 10h build, do **not** integrate a live API (Copernicus Marine, NOAA, etc.) unless
someone on the team has already used one — auth/setup risk is too high for the time budget.
- **Recommended**: a static or lightly-randomized synthetic vector field (e.g. a dominant
  current direction/speed + wind component + small random diffusion per particle). This is
  scientifically the same *method* the reference architecture describes (particle
  advection) — it's the *data source* that's simplified, not the physics.
- If someone wants to stretch: a single static download of a real current snapshot for the
  demo region is a good SHOULD item, not a MUST.

## 3. AIS data — synthetic, by design
The official PS explicitly permits this: *"Real AIS if available may be used else synthetic
data can be prepared for the region of oil spill to demonstrate the functioning of the
algorithm."* Real historical AIS matched precisely to a chosen spill scenario is not
realistically obtainable in this window — build the generator instead.

**Suggested demo scenario (placeholder — swap freely):**
Bay of Bengal, off Paradip Port, Odisha (~20.31°N, 86.61°E) — a real, recognisable shipping
lane, fits the NTRO/India context, and gives the team a coastline they can reason about
intuitively while building.

**Synthetic roster spec:**
- ~20–30 vessels in a bounding box around the scenario coordinates
- Track points every 15–30 min over a 48–72h window bracketing the estimated spill window
- **One vessel deliberately routed** through the origin zone during the spill window, with
  a speed drop and/or course deviation near that point — this is your "guilty" vessel and
  the one the demo narrative is built around
- Remaining vessels: a spread of near-misses (close but wrong time), false positives
  (right time, far away), and clean traffic (neither) — this is what makes the funnel
  animation in Step 4 of the demo (see `PRD.md` §4) actually demonstrate filtering, not just
  return one result
- Fields per position: `vessel_id, ts, lat, lon, speed_knots, course_deg, status` (see
  `DB.md` §4). The generator can run entirely standalone, before the round starts, and just
  gets loaded by the FastAPI backend at startup.

## 4. Pre-round prep checklist (do this BEFORE the clock starts)
- [ ] Download 2–3 Zenodo SAR sample images
- [ ] Decide the fixed demo scenario: location, spill time, "guilty" vessel identity/name
- [ ] Draft the synthetic AIS generator script (can be written and tested ahead of time —
      it has no dependency on anything built during the round)
- [ ] Scaffold both `/backend` and `/frontend` and confirm `npm install` / `pip install`
      work clean on every laptop — don't discover a missing dependency at hour 0
- [ ] Sample data reference for AIS *field format* only (not content): marinecadastre.gov
      AIS sample data, per the official PS dataset link
