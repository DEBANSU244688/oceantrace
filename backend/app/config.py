"""
config.py — single source of truth for the demo scenario.

Change these constants and every module (detection, drift, AIS) stays in
sync, because they all import from here rather than hardcoding values.

Kept in sync with scripts/generate_ais.py's ORIGIN_LAT/LON and spill window
— if you change one, change the other (see the comment there).
"""
from datetime import datetime, timezone

from app import geo_utils

# ---------------------------------------------------------------------------
# Scenario ground truth (only "known" during generation — the pipeline is
# supposed to *recover* this from the image + AIS data, not read it directly)
# ---------------------------------------------------------------------------
REGION_CENTER = (20.31, 86.61)                 # Paradip Port, Odisha
ORIGIN_LAT, ORIGIN_LON = 20.28, 86.55          # where the spill actually started

SPILL_TIME = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)   # spill window midpoint
SPILL_WINDOW_HOURS = 4                                            # +/- 2h around SPILL_TIME
DETECTION_TS = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)  # satellite pass

# "Current + wind" drift vector carrying the slick away from the origin
# between the spill and the satellite pass. A static vector is a deliberate
# simplification for a 10h build — see SACD.md §4 / DRD.md §2.
DRIFT_BEARING_DEG = 100          # compass bearing the slick drifts along
DRIFT_SPEED_KMH = 2.5            # ~1.35 knots, a plausible combined current+wind drift

HINDCAST_HOURS = (DETECTION_TS - SPILL_TIME).total_seconds() / 3600  # = 4.0

# Where the slick actually is by the time the satellite sees it — this is
# the "ground truth" the sample image is generated around, and what
# detector.py is expected to (re)discover from pixels, not read from here.
DETECTED_LAT, DETECTED_LON = geo_utils.project(
    ORIGIN_LAT, ORIGIN_LON, DRIFT_BEARING_DEG, DRIFT_SPEED_KMH * HINDCAST_HOURS)

# ---------------------------------------------------------------------------
# Sample image geography (see scripts/generate_sample_image.py)
# ---------------------------------------------------------------------------
IMAGE_SIZE_PX = 512
IMAGE_HALF_WIDTH_KM = 18   # image covers +/- this many km around DETECTED_LAT/LON
SAMPLE_IMAGES_DIR = "data/sample_images"

SAMPLE_IMAGES = [
    {"id": "sar_001", "label": "Paradip slick — Sentinel-1 style (synthetic placeholder)",
     "file": "sar_001.png"},
]

# ---------------------------------------------------------------------------
# Detection tuning
# ---------------------------------------------------------------------------
MIN_BLOB_AREA_PX = 200          # ignore speckle smaller than this after thresholding

# ---------------------------------------------------------------------------
# Drift engine tuning
# ---------------------------------------------------------------------------
N_PARTICLES = 150
DIFFUSION_KM_PER_HOUR = 0.6     # small per-step random spread simulating uncertainty
STEP_HOURS = 0.5
FORECAST_HOURS = 6              # S1 — forward projection horizon

# ---------------------------------------------------------------------------
# Attribution scoring weights (must sum to 1.0 — see MASTER_REFERENCE_INDEX.md)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "spatial": 0.25,
    "temporal": 0.20,
    "trajectory": 0.20,
    "speed_anomaly": 0.10,
    "course_anomaly": 0.10,
    "loitering": 0.05,
    "ais_anomaly": 0.05,
    "vessel_type": 0.05,
}
SPATIAL_RADIUS_KM = 15          # distance beyond which spatial_score -> 0
TEMPORAL_DECAY_HOURS = 24       # how fast temporal_score decays with time offset
TRAJECTORY_RADIUS_KM = 15       # distance beyond which trajectory_score -> 0
