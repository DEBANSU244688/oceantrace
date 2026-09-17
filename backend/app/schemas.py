"""Pydantic models — these are the API contract from SACD.md §3, typed.
Frontend devs can read this file (or hit /docs) instead of asking backend
devs to describe the shape verbally."""
from typing import Optional

from pydantic import BaseModel


class DetectRequest(BaseModel):
    image_id: str


class DetectResponse(BaseModel):
    spill_id: str
    polygon_geojson: dict
    area_km2: float
    perimeter_km: float
    centroid: list  # [lat, lon]
    confidence: float


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


class DriftResponse(BaseModel):
    origin_zone: OriginZone
    spill_window: SpillWindow
    forecast_path_geojson: Optional[dict] = None


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
