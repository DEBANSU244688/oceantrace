"""
main.py — FastAPI app (SACD.md component #6). Wires detector -> characterize
-> drift_engine -> attribution behind the REST API contract frozen in
SACD.md §3. Every endpoint here should match that doc exactly — if you need
to change a shape, change it there first so the frontend team sees it too.
"""
import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from app import attribution, characterize, config, detector, drift_engine, store
from app.schemas import (AttributionRequest, AttributionResponse, DetectRequest,
                          DetectResponse, DriftRequest, DriftResponse, VesselDetailResponse)

app = FastAPI(title="OceanTrace API")

# CORS — the Phase 1 checkpoint in PP.md. Vite's default dev port is 5173;
# 3000 is included too in case someone's frontend tooling defaults there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_latest_attribution_spill_id = None


@app.on_event("startup")
def on_startup():
    store.load_ais_data()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenario")
def scenario():
    return {
        "sample_images": [{"id": s["id"], "label": s["label"]} for s in config.SAMPLE_IMAGES],
        "region_center": list(config.REGION_CENTER),
    }


@app.post("/api/detect", response_model=DetectResponse)
def detect(req: DetectRequest):
    matching = [s for s in config.SAMPLE_IMAGES if s["id"] == req.image_id]
    if not matching:
        raise HTTPException(404, f"Unknown image_id: {req.image_id}")
    meta = matching[0]

    base_dir = Path(__file__).resolve().parent.parent
    image_path = base_dir / config.SAMPLE_IMAGES_DIR / meta["file"]
    bbox_path = base_dir / config.SAMPLE_IMAGES_DIR / f"{meta['id']}_meta.json"
    if not image_path.exists() or not bbox_path.exists():
        raise HTTPException(500, f"Sample image assets missing for {req.image_id} — "
                                  f"run scripts/generate_sample_image.py")

    image = np.array(Image.open(image_path).convert("L"))
    bbox = json.loads(bbox_path.read_text())

    try:
        det = detector.detect(image)
        geom = characterize.characterize(det.contour_px, config.IMAGE_SIZE_PX, bbox)
    except ValueError as e:
        raise HTTPException(422, str(e))

    spill_id = store.new_spill_id()
    result = {
        "spill_id": spill_id,
        "polygon_geojson": geom.polygon_geojson,
        "area_km2": geom.area_km2,
        "perimeter_km": geom.perimeter_km,
        "centroid": list(geom.centroid),
        "confidence": det.confidence,
    }
    store.save_spill(spill_id, result)
    return result


@app.post("/api/drift", response_model=DriftResponse)
def drift(req: DriftRequest):
    spill = store.get_spill(req.spill_id)
    if spill is None:
        raise HTTPException(404, f"Unknown spill_id: {req.spill_id}")

    lat, lon = spill["centroid"]
    hc = drift_engine.hindcast(lat, lon)
    fc = drift_engine.forecast(lat, lon)
    window_start, window_end = drift_engine.estimate_spill_window()

    result = {
        "origin_zone": {
            "center": list(hc.center), "radius_km": hc.radius_km,
            "particle_cloud_geojson": hc.particle_cloud_geojson,
            "confidence": hc.confidence,
        },
        "spill_window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "forecast_path_geojson": fc.path_geojson,
    }
    store.save_drift(req.spill_id, result)
    return result


@app.post("/api/attribution", response_model=AttributionResponse)
def attribution_endpoint(req: AttributionRequest):
    global _latest_attribution_spill_id
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
def vessel_detail(vessel_id: str):
    if _latest_attribution_spill_id is None:
        raise HTTPException(400, "Run /api/attribution first")

    attribution_result = store.get_attribution(_latest_attribution_spill_id)
    match = next((v for v in attribution_result["ranked_vessels"]
                  if v["vessel_id"] == vessel_id), None)
    if match is None:
        raise HTTPException(404, f"Unknown vessel_id: {vessel_id}")

    track = store.positions_df()
    track = track[track.vessel_id == vessel_id].sort_values("ts")
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
