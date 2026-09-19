"""
main.py — FastAPI app (SACD.md component #6). Wires detector -> characterize
-> drift_engine -> attribution behind the REST API contract frozen in
SACD.md §3. Every endpoint here should match that doc exactly — if you need
to change a shape, change it there first so the frontend team sees it too.
"""
import io
import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError
from shapely.geometry import Polygon

from app import (attribution, characterize, config, detector, drift_engine,
                 geo_utils, store)
from app.schemas import (AttributionRequest, AttributionResponse, DetectRequest,
                          DetectResponse, DriftRequest, DriftResponse, VesselDetailResponse)

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="OceanTrace API")

# CORS — the Phase 1 checkpoint in PP.md. Vite's default dev port is 5173, but
# when that port is busy Vite prints one line and quietly serves on 5174/5175
# instead; every API call then fails CORS with no obvious cause, which is a
# miserable thing to debug in front of judges. So allow the whole fallback
# range, plus 3000 in case someone's tooling defaults there.
_DEV_PORTS = [5173, 5174, 5175, 5176, 3000]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{host}:{port}"
                   for port in _DEV_PORTS
                   for host in ("localhost", "127.0.0.1")],
    allow_methods=["*"],
    allow_headers=["*"],
)

_latest_attribution_spill_id = None


@app.on_event("startup")
def on_startup():
    store.load_ais_data()


def _require_attributable(spill):
    """Refuse to trace or attribute a detection that did not clear the gate.

    Enforced here rather than only in the UI: the whole point is that the
    system will not name a vessel for a spill it is not confident happened, and
    a rule that only lives in the frontend is not a rule.
    """
    if not spill.get("attributable", True):
        raise HTTPException(409, spill.get("attribution_block_reason")
                            or "Detection did not meet the attribution threshold")


def _sample_image(image_id: str):
    """Resolve an image_id to (metadata, image path, bbox path), 404/500ing the
    same way for every endpoint that serves the sample imagery."""
    meta = next((s for s in config.SAMPLE_IMAGES if s["id"] == image_id), None)
    if meta is None:
        raise HTTPException(404, f"Unknown image_id: {image_id}")

    image_path = BASE_DIR / config.SAMPLE_IMAGES_DIR / meta["file"]
    bbox_path = BASE_DIR / config.SAMPLE_IMAGES_DIR / f"{meta['id']}_meta.json"
    if not image_path.exists() or not bbox_path.exists():
        raise HTTPException(500, f"Sample image assets missing for {image_id} — "
                                 f"run scripts/generate_sample_image.py")
    return meta, image_path, bbox_path


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenario")
def scenario():
    return {
        "sample_images": [{"id": s["id"], "label": s["label"]} for s in config.SAMPLE_IMAGES],
        "region_center": list(config.REGION_CENTER),
    }


@app.get("/api/images/{image_id}")
def sample_image(image_id: str):
    """Serve the raw sample tile so react-leaflet can draw it as an
    <ImageOverlay>. Served through the API rather than a StaticFiles mount so
    unknown ids give the same 404 shape as every other endpoint."""
    uploaded = store.get_upload(image_id)
    if uploaded is not None:
        data, media_type = uploaded
        return Response(content=data, media_type=media_type)
    _meta, image_path, _bbox_path = _sample_image(image_id)
    return FileResponse(image_path, media_type="image/png")


@app.get("/api/basemap/land")
def basemap_land():
    """Public-domain land polygons for the scenario region (Natural Earth),
    clipped and simplified by scripts/fetch_coastline.py.

    This is the offline basemap. PRD.md §5 requires the demo to run with no
    internet, but the CARTO raster basemap needs the network — so the frontend
    draws this underneath it. Online, CARTO's opaque tiles cover it and nothing
    changes; offline, this is what keeps the map from being a black void. No
    API key, and no tile-usage policy to worry about."""
    path = BASE_DIR / "data" / "coastline.geojson"
    if not path.exists():
        raise HTTPException(503, "Coastline not built — run scripts/fetch_coastline.py")
    return FileResponse(path, media_type="application/geo+json")


@app.post("/api/detect", response_model=DetectResponse)
def detect(req: DetectRequest):
    _meta, image_path, bbox_path = _sample_image(req.image_id)
    image = np.array(Image.open(image_path).convert("L"))
    bbox = json.loads(bbox_path.read_text())

    try:
        det = detector.detect(image)
        geom = characterize.characterize(det.contour_px, image.shape, bbox)
    except ValueError as e:
        raise HTTPException(422, str(e))

    sc = config.scenario(_meta.get("scenario"))
    attributable, block_reason = detector.attribution_gate(
        det.confidence, det.lookalike_risk)
    spill_id = store.new_spill_id()
    result = {
        "spill_id": spill_id,
        "polygon_geojson": geom.polygon_geojson,
        "area_km2": geom.area_km2,
        "perimeter_km": geom.perimeter_km,
        "centroid": list(geom.centroid),
        "confidence": det.confidence,
        "scenario_id": sc["id"],
        "scenario_label": sc["label"],
        # The georeferenced footprint of the source tile + where to fetch it,
        # so the frontend can lay the actual SAR pixels under the polygon
        # (PRD.md §4 step 2) instead of floating it on a bare basemap.
        "image_id": req.image_id,
        "image_bbox": bbox,
        "image_url": f"/api/images/{req.image_id}",
        "candidate_regions": det.candidate_regions,
        "rejected_lookalikes": det.rejected_lookalikes,
        "lookalike_risk": det.lookalike_risk,
        "lookalike_note": det.lookalike_note,
        "attributable": attributable,
        "attribution_block_reason": block_reason,
        "source": "sample",
    }
    store.save_spill(spill_id, result)
    return result


@app.post("/api/detect/upload", response_model=DetectResponse)
async def detect_upload(file: UploadFile = File(...)):
    """Run detection on a judge-supplied image.

    Same pipeline as /api/detect — the detector does not care where its
    pixels came from. The upload carries no geocoding, so it is placed
    exactly the way scripts/fetch_sar_tiles.py places the downloaded Zenodo
    tiles: anchored so the detected slick lands on the scenario's
    DETECTED_LAT/LON. That keeps the drift and AIS stages meaningful
    instead of dead-ending after detection.

    Be straight about this if a judge asks: an uploaded photo of anything
    will still produce *a* polygon, because Otsu always finds something
    darker than average. That is what lookalike_risk in the response is
    for — check it before believing the confidence number.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "Image too large — 12 MB limit")
    try:
        pil = Image.open(io.BytesIO(raw))
        pil.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Could not read that file as an image")

    gray = pil.convert("L")
    if min(gray.size) < 32:
        raise HTTPException(422, "Image too small to analyse")
    arr = np.array(gray)

    try:
        det = detector.detect(arr)
    except ValueError as e:
        raise HTTPException(422, str(e))

    # An upload carries no geocoding, so which event it belongs to is our
    # choice, not a measurement. Rotate through the events rather than always
    # picking the first, so uploading two images does not silently produce the
    # same origin and the same culprit twice — and name the event in the
    # response so the UI can say where it put it.
    sc = store.next_upload_scenario()
    anchor_px = Polygon(det.contour_px).centroid.coords[0]
    bbox = geo_utils.bbox_anchored_at(
        arr.shape[1], arr.shape[0], anchor_px,
        sc["detected_lat"], sc["detected_lon"], config.TILE_METRES_PER_PX)
    geom = characterize.characterize(det.contour_px, arr.shape, bbox)

    attributable, block_reason = detector.attribution_gate(
        det.confidence, det.lookalike_risk)

    # re-encode as PNG so the map gets something it can definitely render
    buf = io.BytesIO()
    gray.save(buf, format="PNG")
    image_id = store.save_upload(buf.getvalue(), "image/png")

    spill_id = store.new_spill_id()
    result = {
        "spill_id": spill_id,
        "polygon_geojson": geom.polygon_geojson,
        "area_km2": geom.area_km2,
        "perimeter_km": geom.perimeter_km,
        "centroid": list(geom.centroid),
        "confidence": det.confidence,
        "scenario_id": sc["id"],
        "scenario_label": sc["label"],
        "image_id": image_id,
        "image_bbox": bbox,
        "image_url": f"/api/images/{image_id}",
        "candidate_regions": det.candidate_regions,
        "rejected_lookalikes": det.rejected_lookalikes,
        "lookalike_risk": det.lookalike_risk,
        "lookalike_note": det.lookalike_note,
        "attributable": attributable,
        "attribution_block_reason": block_reason,
        "source": "upload",
    }
    store.save_spill(spill_id, result)
    return result


@app.post("/api/drift", response_model=DriftResponse)
def drift(req: DriftRequest):
    spill = store.get_spill(req.spill_id)
    if spill is None:
        raise HTTPException(404, f"Unknown spill_id: {req.spill_id}")
    _require_attributable(spill)

    lat, lon = spill["centroid"]
    sc = config.scenario(spill.get("scenario_id"))
    hc = drift_engine.hindcast(lat, lon)
    fc = drift_engine.forecast(lat, lon)
    window_start, window_end = drift_engine.estimate_spill_window(sc["detection_ts"])

    result = {
        "origin_zone": {
            "center": list(hc.center), "radius_km": hc.radius_km,
            "particle_cloud_geojson": hc.particle_cloud_geojson,
            "confidence": hc.confidence,
        },
        "spill_window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "forecast_path_geojson": fc.path_geojson,
        "hindcast_path_geojson": hc.path_geojson,
        "age_estimate": drift_engine.estimate_spill_age(spill["polygon_geojson"]),
    }
    store.save_drift(req.spill_id, result)
    return result


@app.post("/api/attribution", response_model=AttributionResponse)
def attribution_endpoint(req: AttributionRequest):
    global _latest_attribution_spill_id
    spill = store.get_spill(req.spill_id)
    if spill is not None:
        _require_attributable(spill)
    drift_result = store.get_drift(req.spill_id)
    if drift_result is None:
        raise HTTPException(400, f"Run /api/drift for {req.spill_id} before /api/attribution")

    origin_lat, origin_lon = drift_result["origin_zone"]["center"]
    window_start = drift_result["spill_window"]["start"]
    window_end = drift_result["spill_window"]["end"]

    import pandas as pd
    funnel, ranked = attribution.run_attribution(
        req.spill_id, origin_lat, origin_lon,
        pd.Timestamp(window_start), pd.Timestamp(window_end),
        store.vessels_df(), store.positions_df(),
    )
    result = {"funnel": funnel, "ranked_vessels": ranked}
    store.save_attribution(req.spill_id, result)
    _latest_attribution_spill_id = req.spill_id
    return result


@app.get("/api/vessels/{vessel_id}", response_model=VesselDetailResponse)
def vessel_detail(vessel_id: str, spill_id: str = Query(
        None, description="Which spill's attribution run to read. Defaults to "
                          "the most recent, so the demo flow needs no extra "
                          "plumbing — but pass it explicitly and the endpoint "
                          "survives a browser reload or a direct call from /docs.")):
    spill_id = spill_id or _latest_attribution_spill_id
    if spill_id is None:
        raise HTTPException(400, "Run /api/attribution first, or pass ?spill_id=")

    attribution_result = store.get_attribution(spill_id)
    if attribution_result is None:
        raise HTTPException(404, f"No attribution run stored for {spill_id}")
    match = next((v for v in attribution_result["ranked_vessels"]
                  if v["vessel_id"] == vessel_id), None)
    if match is None:
        raise HTTPException(404, f"Unknown vessel_id: {vessel_id}")

    track = store.positions_df()
    track = track[track.vessel_id == vessel_id].sort_values("ts")

    # Trim to the spill window +/- padding. Drawing all 60 h buries the part
    # that matters under the vessel's ordinary wandering.
    drift_result = store.get_drift(_latest_attribution_spill_id)
    if drift_result is not None:
        import pandas as pd
        pad = pd.Timedelta(hours=config.TRACK_WINDOW_PAD_HOURS)
        start = pd.Timestamp(drift_result["spill_window"]["start"]) - pad
        end = pd.Timestamp(drift_result["spill_window"]["end"]) + pad
        windowed = track[(track.ts >= start) & (track.ts <= end)]
        if len(windowed) >= 2:
            track = windowed

    trajectory_geojson = {
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[lon, lat] for lat, lon in zip(track.lat, track.lon)]},
        "properties": {},
    }

    return {
        "vessel_id": match["vessel_id"], "name": match["name"],
        "trajectory_geojson": trajectory_geojson,
        "score_breakdown": match["breakdown"], "reasons": match["reasons"],
    }
