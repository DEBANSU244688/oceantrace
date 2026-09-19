# SACD — System Architecture & Component Design
**OceanTrace · FastAPI + React, scoped to what's buildable in 10 hours**

## 1. Pipeline

```
Sample SAR image (Zenodo)
        │
        ▼
[1] DETECTION  ──────────  classical CV (thresholding + morphology on
        │                  backscatter) OR a small pretrained segmentation
        │                  model. NOT trained from scratch.
        ▼
[2] CHARACTERISATION ────  OpenCV/skimage contour + Shapely on the mask
        │                  → polygon, area, perimeter, centroid, confidence
        ▼
[3] DRIFT ENGINE ────────  physics-based particle model (pure NumPy).
        │                  Advect N particles from spill centroid using REAL
        │                  hourly ocean current + 3% windage (Open-Meteo),
        │                  cached per event by fetch_ocean_forcing.py.
        │                  Run backward (origin) and forward (forecast).
        ▼
[4] AIS FUNNEL ──────────  synthetic AIS roster (generated ahead of time,
        │                  see DRD.md) filtered: spatial → temporal →
        │                  trajectory-intersection
        ▼
[5] ATTRIBUTION SCORING ─  rule-based weighted formula (no ML model —
        │                  see formula in MASTER_REFERENCE_INDEX.md)
        ▼
[6] FASTAPI BACKEND ─────  wraps 1–5 behind a small REST API (see §3)
        │
        ▼
[7] REACT FRONTEND ──────  Vite + react-leaflet dashboard: map, spill
                           card, funnel counter, ranked vessel list,
                           "why flagged" detail panel
```

## 2. Component responsibilities

| # | Component | Responsibility | Input | Output |
|---|---|---|---|---|
| 1 | `detector.py` | Segment oil-like regions from a SAR image | image file | binary mask |
| 2 | `characterize.py` | Turn mask into geometry + stats | mask | polygon, area, perimeter, centroid, confidence |
| 3 | `drift_engine.py` | Backward/forward particle advection | centroid, current/wind field, N hours | origin zone (particle cloud), forecast path |
| 4 | `scripts/generate_ais.py` | Generate synthetic vessel roster + tracks across all four events | scenario config (see DRD.md) | vessel table + position time series |
| 5 | `attribution.py` | Filter candidates, compute risk scores | origin zone, spill window, AIS tracks | ranked vessel list with score breakdown |
| 6 | `api/main.py` (FastAPI) | Wire 1–5 behind REST endpoints, CORS | HTTP requests | JSON / GeoJSON |
| 7 | `frontend/src/` (React) | Call the API, render the map + panels | — | interactive demo in the browser |

**Data-prep scripts** (run ahead of time, never during the demo; all outputs committed):

| script | what it produces |
|---|---|
| `fetch_sar_tiles.py` | the real Sentinel-1 tiles + their bounding boxes |
| `fetch_demo_uploads.py` | unseen tiles for the upload button, incl. two with no oil |
| `fetch_ocean_forcing.py` | real hourly current + wind per event, and each event's detected position |
| `fetch_coastline.py` | public-domain land polygons — the offline basemap |
| `generate_ais.py` | the synthetic AIS roster and tracks |
| `generate_sample_image.py` | the synthetic fallback tile |
| `validate_detector.py` | detector IoU vs ground truth; `--gate` measures the refusal gate |
| `smoke_test.py` | 78 assertions over the live HTTP API |

Note: the sample imagery is served by component 6 too (`GET /api/images/{id}`),
so the SAR tile the judge sees is the same file `detector.py` ran on.

## 3. API contract (freeze this in the first 15 minutes — see `PP.md`)

Everyone builds against this. Backend owners (R1–R3) and the frontend owner (R4) should not
need to renegotiate shapes mid-build.

```
GET  /api/scenario
  → { "sample_images": [{"id": "sar_001", "label": "Paradip slick A"}, ...],
      "region_center": [20.05, 86.95] }

POST /api/detect            body: { "image_id": "sar_001" }
  → { "spill_id": "SP-001", "polygon_geojson": <GeoJSON Polygon>,
      "area_km2": 18.6, "perimeter_km": 42.3, "centroid": [lat, lon],
      "confidence": 0.94,
      "image_id": "sar_001",
      "image_bbox": { "lat_top": 20.427, "lat_bottom": 20.101,
                      "lon_left": 86.472, "lon_right": 86.817 },
      "image_url": "/api/images/sar_001",   // path on this API, not absolute
      "candidate_regions": 3,               // S4 — dark regions that survived
      "rejected_lookalikes": 2,             //      thresholding, and how many lost
      "lookalike_risk": 0.05,               //      0-1; also lowers `confidence`
      "lookalike_note": "2 other dark regions found and rejected as look-alikes",
      "source": "sample",                   // "sample" | "upload"
      "scenario_id": "sc_01",               // which spill event this tile is an
      "scenario_label": "Paradip approach", //   observation of — differs per tile
      "attributable": true,                 // did it clear the attribution gate?
      "attribution_block_reason": null }    // if not, why — shown to the user

  /api/drift and /api/attribution both return 409 for a spill whose detection
  did not clear the gate (confidence >= MIN_ATTRIBUTION_CONFIDENCE and
  lookalike_risk <= MAX_ATTRIBUTION_LOOKALIKE_RISK, app/config.py). Otsu always
  returns the darkest region in a frame, so a tile with no oil in it still
  yields a polygon — without the gate the pipeline would hindcast that and name
  a real vessel for a spill that never happened. Enforced server-side, not just
  in the UI: a rule that only lives in the frontend is not a rule.

POST /api/detect/upload     multipart form-data, field name "file"
  → identical shape to /api/detect, with "source": "upload". The upload carries
    no geocoding, so it is anchored at the scenario location exactly the way
    scripts/fetch_sar_tiles.py anchors the downloaded Zenodo tiles — which keeps
    /api/drift and /api/attribution meaningful instead of dead-ending.
    415 on a non-image, 422 when no slick-like region is found, 413 over 12 MB.

GET  /api/images/{image_id}
  → the raw sample tile (image/png). The frontend draws it as a react-leaflet
    <ImageOverlay> at image_bbox, under the spill polygon — PRD.md §4 step 2
    wants the polygon overlaid on the image, not floating on a bare basemap.

POST /api/drift              body: { "spill_id": "SP-001" }
  → { "origin_zone": { "center": [lat, lon], "radius_km": 6.2,
        "particle_cloud_geojson": <GeoJSON>, "confidence": 0.81 },
      "spill_window": { "start": "<ISO ts>", "end": "<ISO ts>" },
      "forecast_path_geojson": <GeoJSON | null>,    // S1 — forward run
      "hindcast_path_geojson": <GeoJSON | null>,    // backward run's centroid
                                                     // track, for the animation
      "age_estimate": {                              // S2
        "estimated_age_hours": 3.1, "confidence": 0.29,
        "along_drift_km": 7.77, "across_drift_km": 5.67,
        "method": "slick extent along the drift axis / drift speed" } }

POST /api/attribution        body: { "spill_id": "SP-001" }
  → { "funnel": { "total": 27, "spatial": 9, "temporal": 5, "trajectory": 3 },
      "ranked_vessels": [
        { "vessel_id": "V001", "name": "MV OCEAN STAR", "score": 0.91,
          "breakdown": { "spatial": 0.95, "temporal": 0.9, "trajectory": 0.95,
                         "speed_anomaly": 0.8, "course_anomaly": 0.7,
                         "loitering": 0.4, "ais_anomaly": 0.2, "vessel_type": 0.5 },
          "reasons": ["2.8 km from origin", "present during spill window",
                       "trajectory intersects origin zone", "unusual speed drop"] },
        ... ] }

GET  /api/vessels/{vessel_id}?spill_id=SP-001     // spill_id optional;
                                                   // defaults to the latest run
  → { "vessel_id": "V001", "name": "MV OCEAN STAR",
      "trajectory_geojson": <GeoJSON LineString>,   // trimmed to the spill
                                                     // window +/- TRACK_WINDOW_PAD_HOURS
      "score_breakdown": {...}, "reasons": [...] }
```

All responses are plain JSON; GeoJSON fields are just JSON objects react-leaflet can render
directly via `<GeoJSON data={...} />`. No protobuf, no websockets — plain REST is enough for
a click-driven demo flow.

## 4. Tech stack (recommended for speed of build)

| Layer | Choice | Why |
|---|---|---|
| Backend language | Python 3.11+ (tested on 3.13) | one language across the whole pipeline |
| API framework | **FastAPI + Uvicorn** | matches the submitted PPT; auto-generates OpenAPI docs at `/docs` for free, useful for R4 to explore the contract without asking R1–R3 |
| CORS | `fastapi.middleware.cors.CORSMiddleware`, allow the Vite dev origin | the #1 first-hour failure mode for a split frontend/backend — set it up before anyone builds a feature |
| Detection/CV | OpenCV + scikit-image | no training needed, thresholding + morphology is enough for a demo-quality mask |
| Geospatial analysis | GeoPandas | matches PPT; polygon/area/centroid math and any spatial joins for the AIS funnel |
| Drift sim | NumPy | plain vector math on lat/lon offsets, no GIS library needed here |
| AIS/attribution | Pandas + GeoPandas | tabular filtering + spatial joins for the funnel logic |
| State/storage | in-memory (module-level dict/DataFrame in the FastAPI process) | FastAPI is a long-running server, so state naturally persists between requests without a session-state workaround; see `DB.md` |
| Frontend | **React (Vite) + react-leaflet** | matches PPT ("Leaflet" is the map layer, React is the app shell); Vite gives near-instant hot reload, critical when the clock is running |
| Frontend state | plain `useState`/`useEffect`, `fetch` (or `axios`) | a single linear flow (PRD.md §4) doesn't need Redux/Zustand — one extra dependency is one extra thing to debug |
| Styling | plain CSS with custom properties | no component library needed; the same tokens drive light and dark themes |
| Ocean forcing | Open-Meteo marine + forecast APIs | free, keyless, and real — retires the static vector `DRD.md` §2 originally accepted |
| Offline basemap | Natural Earth land polygons | public domain, so no tile-usage policy to breach, and vector scales to any zoom |

**Explicitly skipped for this round**: trained anomaly-detection models, live AIS feeds,
PostGIS, Docker, auth, a production build (`vite build`) of the frontend — the dev server is
fine to demo from. All of these are good "next sprint" answers for the Feasibility slide,
not this build.

**Explicitly out of scope by design — satellite tasking.** OceanTrace does not acquire
imagery and is not trying to. That infrastructure already exists and this PS's own sponsor
can already invoke it: the International Charter "Space and Major Disasters" lets an
authorised national agency trigger coordinated multi-operator tasking over a disaster area
(ISRO is a member agency; NTRO is exactly the kind of authorised user), and ISRO/NRSC's
Disaster Management Support programme already routes SAR imagery to national disaster
bodies through NDEM for floods and cyclones. Copernicus EMS runs the same pattern in Europe.
OceanTrace's scope starts the moment an image lands: characterise the slick, trace the
origin, rank the vessels, in seconds rather than hours.

This is a boundary, not a gap — but it is the one an evaluator is most likely to probe, so
the reasoning and the supporting numbers live in `JUDGE_QA_PREP.md` Theme 3. Worth knowing:
the origin uncertainty our hindcast reports grows with the age of the image, from a ~3 km²
search area at a 3-hour lag to ~53 km² at 48 hours. That quantifies why acquisition latency
matters, and it is the strongest argument for this layer existing at all — there is no point
shortening image delivery if the analysis then queues for a day.

## 5. Data flow
Image → mask → polygon/stats → centroid feeds drift engine → origin zone (lat/lon +
uncertainty radius) + spill time window → AIS funnel queries synthetic roster against that
zone/window → scored, ranked list → FastAPI returns each stage's JSON → React renders it
onto the map/panels as each button is clicked, matching `PRD.md` §4 exactly.

## 6. Deployment
Local only, two processes on the presenting laptop:
```
# terminal 1
uvicorn api.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev        # Vite dev server, default port 5173
```
No cloud, no Docker, no production build — one less thing that can fail live. (A real
deployment pipeline is a Feasibility-slide "roadmap" item, not a round-2 deliverable.)
