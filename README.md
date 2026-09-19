# OceanTrace — Round 2 scaffold (FastAPI + React)

FastAPI backend + React (Vite) frontend, built and verified against
`docs/PRD.md` / `SACD.md` / `BL.md` / `PP.md` / `DB.md` / `DRD.md` /
`TASKS.md` / `MASTER_REFERENCE_INDEX.md`. This is a real, tested starting
point for the 10-hour build — not a stub.

**Verified end-to-end**: detection runs on **real Sentinel-1 SAR tiles**
downloaded from Zenodo and recovers the slick; hindcast recovers the
ground-truth origin to within ~50 m and the spill window exactly;
attribution ranks the "guilty" vessel (0.94) far above near-miss and
false-positive vessels (0.2–0.5) and clean background traffic, each with
plain-language "why flagged" reasons.

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
Open the URL Vite prints (default http://localhost:5173). Pick a SAR tile
from the selector top-right, then click **Detect spill -> Trace origin ->
Analyse AIS**, and click a vessel in the ranked list to see its trajectory
and why it was flagged.

> Vite falls back to port **5174** if 5173 is busy, and the backend's CORS
> allowlist only covers 5173/3000 — so every API call then fails with no
> obvious cause. If the app loads but nothing works, check which port Vite
> actually printed.

The map uses CARTO raster basemaps. Put your key in `frontend/.env.local`:

```bash
VITE_CARTO_BASEMAPS_API_KEY=your_carto_basemaps_key
```

Vite reads `.env.local` only when the dev server starts, so restart
`npm run dev` after changing the key. Keep CARTO/OpenStreetMap attribution
visible per CARTO's basemap terms.

## The SAR imagery is real

`backend/data/sample_images/` ships three real Sentinel-1 tiles plus one
synthetic fallback, all already generated/downloaded so the app runs
immediately. To re-pull or change the real tiles:

```bash
cd backend
python scripts/fetch_sar_tiles.py      # needs internet; the demo itself does not
```

Source: **Refined Deep-SAR Oil Spill (SOS) dataset**, Zenodo record
[15298010](https://doi.org/10.5281/zenodo.15298010), CC-BY-4.0 — the refined
release of the Deep-SAR SOS dataset (Zhu et al., *IEEE TGRS*, 2021). Its
`images.zip` is 1.1 GB, so the script does not download it: it uses HTTP
range requests to read the zip's central directory and pull only the three
member files it needs, a few hundred KB in total.

**Georeferencing — say this out loud if a judge asks.** The SOS tiles are
crops shipped without any geocoding, so there is no true lat/lon to recover.
`fetch_sar_tiles.py` places each tile so the slick `detector.py` finds in it
lands on the scenario's `DETECTED_LAT/LON`, at 10 m/px (Sentinel-1 IW GRD
nominal spacing, set in `TILE_METRES_PER_PX`). The *pixels* are real
Sentinel-1 backscatter; the *position* is the demo scenario's. That is what
lets real imagery compose with the synthetic AIS roster, which `DRD.md` §3
notes the PS explicitly permits.

### It runs with no internet

`PRD.md` §5 requires the demo to work offline, but the CARTO basemap needs the
network. Pre-caching raster tiles is the wrong fix — both CARTO's and OSM's
usage policies prohibit bulk tile downloading, and a cache only covers the area
and zooms you thought to fetch.

Instead the map draws **public-domain Natural Earth land polygons** underneath
the raster tiles, in a pane below Leaflet's tile pane. Online, CARTO's opaque
tiles cover them and nothing changes. Offline, they're what remains — a
readable coastline at any zoom, from a 35 KB file, with no API key and no tile
policy to worry about. The map also says "basemap offline" rather than leaving
you guessing.

```bash
cd backend
python scripts/fetch_coastline.py     # needs internet once; the demo never does
```

### It refuses to accuse when it isn't sure

Otsu thresholding always returns the darkest region in a frame, so a tile with
no oil in it still produces a polygon. Left alone, the pipeline would hindcast
that non-existent slick and name a real vessel as responsible for it.

So detections must clear a gate — confidence ≥ 40% and look-alike risk ≤ 60% —
before `/api/drift` or `/api/attribution` will touch them. Both return **409**
otherwise, and the UI disables the steps and explains why. Enforced server-side
on purpose: a rule that only lives in the frontend is not a rule.

The thresholds are measured against the dataset's own labels:

```bash
python scripts/validate_detector.py --gate
```

**Blocks 60/60 tiles with no oil, at the cost of 12/60 (20%) of genuine
slicks.** That asymmetry is deliberate — declining to attribute a real spill
costs an analyst a second look; attributing one that never happened costs a
ship operator their reputation.

### How good is the detector, really?

The same Zenodo record ships ground-truth masks, so this is measurable
rather than asserted:

```bash
python scripts/validate_detector.py --sample 70
```

Scoring `detector.py` against the dataset's own labels over 70 random
Sentinel-1 validation tiles: **mean IoU 0.43, median 0.41, 27/70 above 0.5**
— for classical CV (Otsu + morphology + contour selection) with no training
at all, which is the trade `BL.md` deliberately makes. Worth having a real
number for in the Q&A.

## Images to hand an evaluator

`backend/data/demo_uploads/` holds seven real SAR tiles for the **upload**
button — none of them registered in `SAMPLE_IMAGES`, so the app has genuinely
never processed them. That is the answer to "does it only work on the images
you picked?" Two of them contain **no oil at all**, deliberately: see that
folder's `README.md` for how to use them and what to say.

Re-pull with `python scripts/fetch_demo_uploads.py`.

## Check it still works

```bash
cd backend
uvicorn app.main:app --port 8000        # in another terminal
python scripts/smoke_test.py
```

78 checks over the live HTTP API — every sample tile, the upload path and
the refusal gate,
asserting the hindcast recovers the known origin, the spill window brackets the
known spill time, and the guilty vessel ranks first with a clear gap. Run it
after any change, and once on a cold start before the demo (`PP.md` Phase D).

## Demo scenario

Bay of Bengal, **offshore of Paradip Port, Odisha**. The region carries **four
separate spill events**, each with its own origin, its own spill window and its
own guilty vessel, and each sample tile is bound to one of them:

| Tile | Event | Origin | Culprit |
|---|---|---|---|
| `s1_371` | Paradip approach | 20.15, 86.82 | BAY VOYAGER |
| `s1_485` | Outer anchorage | 20.28, 87.18 | MV KALINGA PRIDE |
| `s1_473` | Southern lane | 19.72, 86.78 | ORIENT MARINER |
| `sar_001` | Deep-water crossing | 19.80, 87.15 | MV SILVER TIDE |

**This is the difference between a demo and a magic trick.** An earlier version
anchored every tile to a single origin, so changing the image changed the
pixels and nothing else — same origin, same funnel, same culprit every time,
which looks exactly like a hardcoded answer no matter how honest the code is.
Switching tiles now changes where the drift lands and who gets caught.

Origins are ≥ 35 km apart (well beyond `SPATIAL_RADIUS_KM`, so one event's
vessels never leak into another's funnel) and all verified at sea against
ETOPO1 bathymetry. Everything keys off `backend/app/config.py`; change it there
and re-run both generator scripts plus `fetch_sar_tiles.py`.

An earlier draft put the scenario ~15 km inland. A 36 km-wide synthetic tile
hid that; a 2.5 km real Sentinel-1 tile renders it as a slick sitting on top
of the town. The coordinates and the AIS generator's seaward bearing arc are
now both checked against ETOPO1 bathymetry — see the comments in
`app/config.py` and `scripts/generate_ais.py`. **If you move the scenario,
re-measure that arc**, or a sixth of the vessel roster ends up on dry land.

## Before the actual round
- [x] ~~Swap the synthetic image for real Zenodo SAR tiles~~ — done, see above
- [ ] Everyone reads `docs/SACD.md` §3 (the API contract) once, out loud, per
      `PP.md` Phase 1
- [ ] Confirm `pip install` / `npm install` both run clean on every
      teammate's laptop *before* the clock starts
- [ ] **Reconcile with the other in-progress build** — there's a second,
      plain HTML/JS + Leaflet implementation of this same project underway
      elsewhere. Pick one before hackathon day.
- [ ] Work `docs/next_steps.md` — it has the current gap list, ranked
- [ ] Read `docs/evaluator_brief.md` — what to say, and the questions to expect

## What's real vs. what's synthetic
- **Real**: the Sentinel-1 SAR imagery (Zenodo, CC-BY-4.0) and the detector's
  measured accuracy against that dataset's ground-truth masks.
- **Real, working logic**: classical CV detection (thresholding + morphology
  + contour selection), particle-based drift hindcast/forecast, the AIS
  funnel + weighted attribution scoring, the full FastAPI<->React wiring —
  all tested against ground truth, not mocked.
- **Synthetic by design**: the AIS roster (`DRD.md` §3 — the PS permits this
  explicitly), the current/wind field driving the drift engine (`DRD.md` §2),
  and each tile's geographic placement (see above).

## Project layout
```
backend/    FastAPI app — see backend/README.md
frontend/   React (Vite) app
docs/       PRD, architecture + API contract, backlog, plan, next steps
```
