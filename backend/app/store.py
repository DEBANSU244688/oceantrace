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
