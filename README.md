# OceanTrace — Round 2 scaffold (FastAPI + React)

FastAPI backend + React (Vite) frontend, built and verified against
`PRD.md` / `SACD.md` / `BL.md` / `PP.md` / `DB.md` / `DRD.md` / `TASKS.md` /
`MASTER_REFERENCE_INDEX.md` (in your project outputs). This is a real,
tested starting point for the 10-hour build — not a stub.

**Verified end-to-end already**: detection recovers the ground-truth spill
location from the sample image to within meters; hindcast recovers the
ground-truth origin and spill window exactly; attribution correctly ranks
the "guilty" vessel (score 0.94) far above near-miss/false-positive vessels
(0.2-0.45) and clean background traffic (<0.1), each with plain-language
"why flagged" reasons.

## Run it (two terminals)

**Terminal 1 - backend**
```bash
cd backend
pip install -r requirements.txt
python scripts/generate_ais.py            # only needed once, or after changing app/config.py
python scripts/generate_sample_image.py   # only needed once, or after changing app/config.py
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - frontend**
```bash
cd frontend
npm install
cp .env.example .env.local   # then add your CARTO Basemaps API key
npm run dev
```
Open the URL Vite prints (default http://localhost:5173). Click **Detect
Spill -> Trace Origin -> Analyse AIS**, then click a vessel in the ranked
list to see its trajectory and why it was flagged.

The map uses CARTO raster basemaps. Put your key in `frontend/.env.local`:

```bash
VITE_CARTO_BASEMAPS_API_KEY=your_carto_basemaps_key
```

Vite reads `.env.local` only when the dev server starts, so restart
`npm run dev` after changing the key. Keep CARTO/OpenStreetMap attribution
visible per CARTO's basemap terms.

`backend/data/vessels.json`, `backend/data/ais_positions.csv`, and
`backend/data/sample_images/` are already generated and included so the app
runs immediately - the two scripts above only need to be re-run if you
change the scenario constants in `backend/app/config.py`.

## Before the actual round
- [ ] Swap `backend/data/sample_images/sar_001.png` for a real downloaded
      Zenodo SAR tile (see `DRD.md` S1) - update its bounding box and add
      it to `SAMPLE_IMAGES` in `backend/app/config.py`. `detector.py`
      itself doesn't need to change.
- [ ] Everyone reads `SACD.md` S3 (the API contract) once, out loud, per
      `PP.md` Phase 1.
- [ ] Confirm `pip install` / `npm install` both run clean on every
      teammate's laptop *before* the clock starts.
- [ ] **Reconcile with the other in-progress build** — see the note your
      teammate got about this; there's a second, plain HTML/JS + Leaflet
      implementation of this same project already underway elsewhere. Pick
      one before hackathon day.

## What's real vs. what's a placeholder
- **Real, working logic**: classical CV detection (thresholding + morphology
  + contour selection), particle-based drift hindcast/forecast, the AIS
  funnel + weighted attribution scoring, the full FastAPI<->React wiring -
  all tested against ground truth, not mocked.
- **Placeholder, swap before presenting if you can**: the SAR image itself
  is synthetically generated, since Zenodo wasn't reachable from the
  environment this was built in - see the checklist above.

## Project layout
```
backend/    FastAPI app - see backend/README.md
frontend/   React (Vite) app
```
