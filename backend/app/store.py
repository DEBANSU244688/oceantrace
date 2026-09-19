"""
store.py — DB.md's "skip a real database" recommendation in code. FastAPI is
a long-running process, so a couple of module-level dicts/DataFrames persist
naturally across requests with zero extra infrastructure.
"""
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_vessels_df = None
_positions_df = None
_spills = {}       # spill_id -> dict (detection + characterization result)
_drift = {}        # spill_id -> dict (hindcast/forecast result)
_attribution = {}  # spill_id -> dict (funnel + ranked vessels)
_next_spill_num = 1
_uploads = {}      # image_id -> (bytes, media_type) for judge-supplied tiles
_next_upload_num = 1
_upload_scenario_cursor = 0


def load_ais_data():
    """Call once at FastAPI startup."""
    global _vessels_df, _positions_df
    vessels = json.loads((DATA_DIR / "vessels.json").read_text())
    _vessels_df = pd.DataFrame(vessels)
    _positions_df = pd.read_csv(DATA_DIR / "ais_positions.csv", parse_dates=["ts"])
    if _positions_df["ts"].dt.tz is None:
        _positions_df["ts"] = _positions_df["ts"].dt.tz_localize("UTC")


def vessels_df():
    if _vessels_df is None:
        load_ais_data()
    return _vessels_df


def positions_df():
    if _positions_df is None:
        load_ais_data()
    return _positions_df


def new_spill_id():
    global _next_spill_num
    sid = f"SP-{_next_spill_num:03d}"
    _next_spill_num += 1
    return sid


def save_spill(spill_id, data):
    _spills[spill_id] = data


def get_spill(spill_id):
    return _spills.get(spill_id)


def save_drift(spill_id, data):
    _drift[spill_id] = data


def get_drift(spill_id):
    return _drift.get(spill_id)


def save_attribution(spill_id, data):
    _attribution[spill_id] = data


def get_attribution(spill_id):
    return _attribution.get(spill_id)


def save_upload(data: bytes, media_type: str) -> str:
    """Keep an uploaded tile in memory so /api/images/{id} can serve it back to
    the map. In-memory on purpose — DB.md's "no database server", and an
    uploaded demo image has no reason to outlive the process."""
    global _next_upload_num
    image_id = f"upload_{_next_upload_num:03d}"
    _next_upload_num += 1
    _uploads[image_id] = (data, media_type)
    return image_id


def get_upload(image_id):
    return _uploads.get(image_id)


def next_upload_scenario():
    """Rotate through the region's spill events for successive uploads.

    An uploaded tile has no geocoding, so there is nothing in it that says
    which event it belongs to — the choice is arbitrary either way. Rotating
    at least means two uploads in a row do not produce identical attribution,
    which would look like a hardcoded answer. The response names the event it
    picked, so the UI can be explicit that this was a placement, not a finding.
    """
    global _upload_scenario_cursor
    from app import config
    sc = config.SCENARIOS[_upload_scenario_cursor % len(config.SCENARIOS)]
    _upload_scenario_cursor += 1
    return sc
