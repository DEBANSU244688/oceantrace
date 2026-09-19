"""Pydantic models — these are the API contract from SACD.md §3, typed.
Frontend devs can read this file (or hit /docs) instead of asking backend
devs to describe the shape verbally."""
from typing import Optional

from pydantic import BaseModel


class DetectRequest(BaseModel):
    image_id: str


class ImageBBox(BaseModel):
    """Geographic footprint of a sample tile, as written by
    scripts/generate_sample_image.py into <image_id>_meta.json."""
    lat_top: float
    lat_bottom: float
    lon_left: float
    lon_right: float


class DetectResponse(BaseModel):
    spill_id: str
    polygon_geojson: dict
    area_km2: float
    perimeter_km: float
    centroid: list  # [lat, lon]
    confidence: float
    image_id: str
    image_bbox: ImageBBox
    image_url: str  # path on this API, relative to its base URL
    # S4 — look-alike context (see detector.py)
    candidate_regions: int
    rejected_lookalikes: int
    lookalike_risk: float
    lookalike_note: str
    # Whether this detection clears the bar for tracing an origin and naming a
    # vessel. False means /api/drift and /api/attribution will refuse it.
    attributable: bool
    attribution_block_reason: Optional[str] = None
    source: str = "sample"  # "sample" | "upload"
    # which spill event this image is an observation of — different tiles are
    # bound to different events, so this changes with the image
    scenario_id: str
    scenario_label: str


class DriftRequest(BaseModel):
    spill_id: str


class OriginZone(BaseModel):
    center: list  # [lat, lon]
    radius_km: float
    particle_cloud_geojson: dict
    confidence: float


class SpillWindow(BaseModel):
    start: str
    end: str


class AgeEstimate(BaseModel):
    """S2 — derived from the slick's own geometry, not from the assumed lag."""
    estimated_age_hours: float
    confidence: float
    along_drift_km: float
    across_drift_km: float
    method: str


class DriftResponse(BaseModel):
    origin_zone: OriginZone
    spill_window: SpillWindow
    forecast_path_geojson: Optional[dict] = None
    # the backward run's centroid track, so the map can animate the hindcast
    hindcast_path_geojson: Optional[dict] = None
    age_estimate: Optional[AgeEstimate] = None


class AttributionRequest(BaseModel):
    spill_id: str


class RankedVessel(BaseModel):
    vessel_id: str
    name: str
    score: float
    breakdown: dict
    reasons: list


class Funnel(BaseModel):
    total: int
    spatial: int
    temporal: int
    trajectory: int


class AttributionResponse(BaseModel):
    funnel: Funnel
    ranked_vessels: list  # list[RankedVessel]


class VesselDetailResponse(BaseModel):
    vessel_id: str
    name: str
    trajectory_geojson: dict
    score_breakdown: dict
    reasons: list
