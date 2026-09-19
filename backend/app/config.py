"""
config.py — single source of truth for the demo scenario.

Change these constants and every module (detection, drift, AIS) stays in
sync, because they all import from here rather than hardcoding values.

Kept in sync with scripts/generate_ais.py's ORIGIN_LAT/LON and spill window
— if you change one, change the other (see the comment there).
"""
from datetime import datetime, timedelta, timezone

from app import geo_utils

# ---------------------------------------------------------------------------
# Scenario ground truth (only "known" during generation — the pipeline is
# supposed to *recover* this from the image + AIS data, not read it directly)
# ---------------------------------------------------------------------------
# Offshore of Paradip Port, Odisha, in the Bay of Bengal. These have to be
# genuinely at sea: an earlier draft used coordinates ~15 km inland, which a
# 36 km-wide synthetic tile hid but a 2.5 km real Sentinel-1 tile renders as a
# slick sitting on top of the town. Checked against ETOPO1 bathymetry —
# every bearing from 10° to 250° stays at sea out to 90 km, which is what
# SEAWARD_BEARING_DEG in generate_ais.py encodes.
REGION_CENTER = (20.05, 86.95)                 # Bay of Bengal, off Paradip

# The ocean is the same everywhere in the region, so the drift vector is global.
# A static vector is a deliberate simplification — see SACD.md §4 / DRD.md §2.
DRIFT_BEARING_DEG = 100          # compass bearing the slick drifts along
DRIFT_SPEED_KMH = 2.5            # ~1.35 knots, a plausible current+wind drift
SPILL_WINDOW_HOURS = 4           # +/- 2h around the implied spill time
HINDCAST_HOURS = 4.0             # assumed lag between spill and satellite pass

# ---------------------------------------------------------------------------
# Spill events in the region.
#
# There are four, not one, and this matters more than it looks. With a single
# scenario every sample tile was anchored to the same point, so every image
# produced the same origin, the same funnel and the same culprit — which is
# indistinguishable from a hardcoded answer no matter how honest the code is.
# Each tile now belongs to a different event, so changing the image genuinely
# changes where the drift lands and who gets caught.
#
# Constraints when editing:
#   * every origin AND its detected point must be at sea (ETOPO1 checked;
#     these sit in 28-1335 m of water)
#   * origins must be >= 35 km apart, comfortably beyond SPATIAL_RADIUS_KM, so
#     one event's vessels never leak into another's funnel
#   * spill times must sit well inside the AIS track window (TRACK_HOURS in
#     generate_ais.py, centred on TRACK_ANCHOR below)
# ---------------------------------------------------------------------------
TRACK_ANCHOR = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)


def _scenario(sid, label, origin, spill_time, guilty):
    """Derive the observable facts from the ground-truth ones. `detected` is
    where the slick has drifted to by the time the satellite sees it — that is
    what the sample tile gets anchored on, and what detector.py is expected to
    rediscover from pixels."""
    lat, lon = origin
    det_lat, det_lon = geo_utils.project(
        lat, lon, DRIFT_BEARING_DEG, DRIFT_SPEED_KMH * HINDCAST_HOURS)
    return {
        "id": sid,
        "label": label,
        "origin_lat": lat,
        "origin_lon": lon,
        "spill_time": spill_time,
        "detection_ts": spill_time + timedelta(hours=HINDCAST_HOURS),
        "detected_lat": det_lat,
        "detected_lon": det_lon,
        "guilty": guilty,
    }


SCENARIOS = [
    _scenario("sc_01", "Paradip approach",
              (20.15, 86.82), datetime(2026, 9, 9, 16, 0, tzinfo=timezone.utc),
              "BAY VOYAGER"),
    _scenario("sc_02", "Outer anchorage",
              (20.28, 87.18), datetime(2026, 9, 10, 4, 0, tzinfo=timezone.utc),
              "MV KALINGA PRIDE"),
    _scenario("sc_03", "Southern lane",
              (19.72, 86.78), datetime(2026, 9, 10, 16, 0, tzinfo=timezone.utc),
              "ORIENT MARINER"),
    _scenario("sc_04", "Deep-water crossing",
              (19.80, 87.15), datetime(2026, 9, 11, 4, 0, tzinfo=timezone.utc),
              "MV SILVER TIDE"),
]
SCENARIOS_BY_ID = {sc["id"]: sc for sc in SCENARIOS}
DEFAULT_SCENARIO_ID = SCENARIOS[0]["id"]


def scenario(scenario_id=None):
    return SCENARIOS_BY_ID.get(scenario_id or DEFAULT_SCENARIO_ID, SCENARIOS[0])


# ---------------------------------------------------------------------------
# Sample image geography (see scripts/generate_sample_image.py)
# ---------------------------------------------------------------------------
IMAGE_SIZE_PX = 512
IMAGE_HALF_WIDTH_KM = 18   # image covers +/- this many km around DETECTED_LAT/LON
SAMPLE_IMAGES_DIR = "data/sample_images"

# Ground sample distance used to georeference the real Sentinel-1 tiles pulled
# by scripts/fetch_sar_tiles.py. 10 m/px is Sentinel-1 IW GRD nominal pixel
# spacing. The SOS dataset ships its crops without geocoding, so this is a
# stated assumption rather than a recovered value — see the script's docstring.
TILE_METRES_PER_PX = 10.0

# Real Sentinel-1 tiles first, so the app auto-loads real imagery rather than
# the synthetic stand-in (PRD.md §5 requires at least one detection on a real
# Zenodo sample). Pull them with scripts/fetch_sar_tiles.py; the synthetic one
# stays as an offline fallback and as the fixture the ground-truth check uses.
# Each tile is bound to a different spill event, so switching tiles changes the
# origin, the spill window and the vessel that gets caught — not just the
# pixels. Re-run scripts/fetch_sar_tiles.py after changing a binding.
SAMPLE_IMAGES = [
    {"id": "s1_371", "label": "Sentinel-1 — linear slick, Paradip approach",
     "file": "s1_371.png", "scenario": "sc_01"},
    {"id": "s1_485", "label": "Sentinel-1 — branching slick, outer anchorage",
     "file": "s1_485.png", "scenario": "sc_02"},
    {"id": "s1_473", "label": "Sentinel-1 — diffuse slick, southern lane",
     "file": "s1_473.png", "scenario": "sc_03"},
    {"id": "sar_001", "label": "Synthetic stand-in — deep-water crossing",
     "file": "sar_001.png", "scenario": "sc_04"},
]

# ---------------------------------------------------------------------------
# Detection tuning
# ---------------------------------------------------------------------------
MIN_BLOB_AREA_PX = 200          # ignore speckle smaller than this after thresholding

# ---------------------------------------------------------------------------
# Attribution gate — when is a detection good enough to accuse someone?
#
# Otsu always returns the darkest region in the frame, so feeding in a tile with
# no oil in it still yields a polygon. Without a gate the pipeline would then
# hindcast that non-existent slick and name a real vessel as responsible for it.
# That is a false accusation, and it is a far worse failure than staying quiet.
#
# Thresholds measured, not guessed — scripts/validate_detector.py --gate scores
# these against the dataset's own labels over 60 tiles with no oil and 60 with:
#
#     confidence >= 0.40 and lookalike_risk <= 0.60
#       blocks 60/60 (100%) of the no-oil tiles
#       blocks 11/60  (18%) of genuine slicks
#
# The asymmetry is deliberate. Declining to attribute a real spill costs an
# analyst a second look; attributing a spill that never happened costs a ship
# operator their reputation.
# ---------------------------------------------------------------------------
MIN_ATTRIBUTION_CONFIDENCE = 0.40
MAX_ATTRIBUTION_LOOKALIKE_RISK = 0.60

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
# /api/vessels returns the track trimmed to the spill window plus this much
# padding either side. The full roster track is 60 h of bounded random walk,
# which draws as an unreadable scribble and tells a judge nothing — the useful
# question is only ever "where was it around the time of the spill".
TRACK_WINDOW_PAD_HOURS = 6

SPATIAL_RADIUS_KM = 15          # distance beyond which spatial_score -> 0
TEMPORAL_DECAY_HOURS = 24       # how fast temporal_score decays with time offset
TRAJECTORY_RADIUS_KM = 15       # distance beyond which trajectory_score -> 0
