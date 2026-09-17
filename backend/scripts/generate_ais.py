"""
generate_ais.py — OceanTrace synthetic AIS generator (DRD.md §3)

Standalone script. No dependency on the detection/drift/attribution code —
can be run and iterated on before the hackathon clock starts.

Produces two files under backend/data/:
  vessels.json         — the static vessel roster (DB.md §3)
  ais_positions.csv    — the position time series (DB.md §4)

Design (matches DRD.md §3's four categories exactly):
  - 1 "guilty" vessel:      passes through the origin zone DURING the spill
                             window, with a speed/status anomaly there.
  - 3 "near-miss" vessels:  pass close to the origin zone, but at a time well
                             outside the spill window (right place, wrong time).
  - 3 "false-positive"      are near the origin zone's general vicinity during
    vessels:                 the spill window, but too far away to be the
                             source (right time, wrong place).
  - the rest:                clean background traffic — a bounded random walk
                             with no special routing at all.

Every vessel's track is a bounded random walk (so it stays on a sane map
viewport for a full 60h), with a short, verifiable "detour" blended in for
the three routed categories above. Run this file directly to see a printed
verification table confirming each vessel lands where its category promises.

Usage:
    python scripts/generate_ais.py
"""
import json
import math
import random
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402  (import after sys.path fix, deliberate)

# ---------------------------------------------------------------------------
# Scenario constants — sourced from app/config.py so the AIS data, the
# detection sample image, and the drift engine can never drift out of sync.
# ---------------------------------------------------------------------------
SEED = 7
ORIGIN_LAT, ORIGIN_LON = config.ORIGIN_LAT, config.ORIGIN_LON
SPILL_WINDOW_MID = config.SPILL_TIME
SPILL_WINDOW_START = SPILL_WINDOW_MID - timedelta(hours=config.SPILL_WINDOW_HOURS / 2)
SPILL_WINDOW_END = SPILL_WINDOW_MID + timedelta(hours=config.SPILL_WINDOW_HOURS / 2)

HOME_MIN_KM = 25                    # every vessel's home is at least this far
HOME_MAX_KM = 90                    # ...and at most this far from the origin,
                                     # so proximity to the origin only ever
                                     # comes from a deliberate warp, never chance
PER_VESSEL_WANDER_KM = 14           # how far a vessel roams from its own home

TRACK_HOURS = 60
STEP_MINUTES = 20
N_CLEAN_VESSELS = 19  # + 1 guilty + 3 near-miss + 3 false-positive = 26 total

VESSEL_TYPES = ["tanker", "cargo", "fishing", "container", "bulk carrier"]
NAME_POOL = [
    "MV OCEAN STAR", "SEA TRADER", "BLUE MERIDIAN", "MV KALINGA PRIDE",
    "COASTAL VENTURE", "MV NAVIGATOR", "PARADIP DAWN", "MV SAGAR RATNA",
    "GULF CARRIER", "MV EASTERN WAVE", "BAY VOYAGER", "MV SILVER TIDE",
    "ORIENT MARINER", "MV DEEP HORIZON II", "COROMANDEL STAR",
    "MV SWIFT CURRENT", "HARBOUR QUEEN", "MV TRUE NORTH", "SANDPIPER",
    "MV LONG REACH", "TIDEWATER EXPRESS", "MV FAR HORIZON", "CAPE RUNNER",
    "MV NORTHERN LIGHT", "ODISHA PIONEER", "MV STORM PETREL",
]

random.seed(SEED)


from app.geo_utils import haversine_km, km_to_deg_lat, km_to_deg_lon  # noqa: E402


def random_point_within_radius(center_lat, center_lon, radius_km, min_radius_km=0):
    r_km = min_radius_km + (radius_km - min_radius_km) * math.sqrt(random.random())
    theta = random.uniform(0, 2 * math.pi)
    dlat = km_to_deg_lat(r_km * math.cos(theta))
    dlon = km_to_deg_lon(r_km * math.sin(theta), center_lat)
    return center_lat + dlat, center_lon + dlon


def random_walk_track(home_lat, home_lon, start_ts, hours, step_minutes,
                       base_speed_knots, max_radius_km):
    """A bounded random walk, computed in a local flat (east, north) km frame
    centered on `home` (a fine approximation over ~50 km). Heading wanders
    freely (no angle-wrapping arithmetic — we only ever add a delta or call
    atan2 fresh, never blend two raw angles). If a step would take the vessel
    outside max_radius_km, it's clamped onto that boundary and the heading is
    reset to point back toward home — a hard, reliable bound with no drift-off
    failure mode.
    """
    n_steps = int(hours * 60 / step_minutes)
    x, y = 0.0, 0.0  # km offset from home: x = east, y = north
    heading = random.uniform(0, 360)
    ts = start_ts
    rows = []
    for _ in range(n_steps):
        heading = heading + random.uniform(-20, 20)
        speed = max(2.0, base_speed_knots + random.uniform(-2, 2))
        step_km = speed * (step_minutes / 60) * 1.852
        rad = math.radians(heading)
        new_x = x + step_km * math.sin(rad)
        new_y = y + step_km * math.cos(rad)

        dist = math.hypot(new_x, new_y)
        if dist > max_radius_km:
            scale = max_radius_km / dist
            new_x, new_y = new_x * scale, new_y * scale
            heading = math.degrees(math.atan2(-new_x, -new_y))  # aim back at home

        x, y = new_x, new_y
        lat = home_lat + km_to_deg_lat(y)
        lon = home_lon + km_to_deg_lon(x, home_lat)

        rows.append({"ts": ts, "lat": lat, "lon": lon,
                     "speed_knots": round(speed, 1),
                     "course_deg": round(heading % 360, 1), "status": "underway"})
        ts += timedelta(minutes=step_minutes)
    return rows


def warp_through_point(rows, target_ts, target_lat, target_lon, blend_hours, step_minutes):
    """Blend the track so it passes through (target_lat, target_lon) at the
    row closest to target_ts, fading back to the original path over
    `blend_hours` on either side. Returns the index of the snapped row."""
    idx = min(range(len(rows)), key=lambda i: abs((rows[i]["ts"] - target_ts).total_seconds()))
    blend_steps = max(1, int(blend_hours * 60 / step_minutes))
    for offset in range(-blend_steps, blend_steps + 1):
        i = idx + offset
        if 0 <= i < len(rows):
            weight = 1 - abs(offset) / blend_steps  # 1.0 at idx, 0.0 at the edges
            rows[i]["lat"] = rows[i]["lat"] * (1 - weight) + target_lat * weight
            rows[i]["lon"] = rows[i]["lon"] * (1 - weight) + target_lon * weight
    rows[idx]["lat"], rows[idx]["lon"] = target_lat, target_lon
    return idx


def apply_anomaly(rows, idx, half_window_steps=2):
    """Speed drop / course deviation right around the snapped index — the
    'guilty vessel' behavioural signature."""
    for i in range(max(0, idx - half_window_steps), min(len(rows), idx + half_window_steps + 1)):
        rows[i]["speed_knots"] = round(random.uniform(0.5, 2.5), 1)
        rows[i]["course_deg"] = round((rows[i]["course_deg"] + random.choice([-40, 40])) % 360, 1)
        rows[i]["status"] = "stopped" if rows[i]["speed_knots"] < 1.5 else "reduced speed"


def build_roster():
    names = random.sample(NAME_POOL, 1 + 3 + 3 + N_CLEAN_VESSELS)
    roles = (["guilty"] + ["near_miss"] * 3 + ["false_positive"] * 3
             + ["clean"] * N_CLEAN_VESSELS)
    vessels = []
    for i, (name, role) in enumerate(zip(names, roles)):
        vessels.append({
            "vessel_id": f"V{i+1:03d}",
            "name": name,
            "type": random.choice(VESSEL_TYPES),
            "_role": role,  # internal only, not written to vessels.json
        })
    return vessels


def build_positions(vessels):
    track_start = SPILL_WINDOW_MID - timedelta(hours=TRACK_HOURS / 2)
    all_rows = []
    verification = []

    for vessel in vessels:
        role = vessel["_role"]

        # every vessel's home is drawn from a ring around the ORIGIN itself
        # (not the port) so proximity to the origin is never accidental —
        # it only happens via the deliberate warp below.
        home_lat, home_lon = random_point_within_radius(
            ORIGIN_LAT, ORIGIN_LON, HOME_MAX_KM, min_radius_km=HOME_MIN_KM)

        base_speed = random.uniform(9, 15)
        rows = random_walk_track(home_lat, home_lon, track_start, TRACK_HOURS,
                                  STEP_MINUTES, base_speed, max_radius_km=PER_VESSEL_WANDER_KM)

        if role == "guilty":
            idx = warp_through_point(rows, SPILL_WINDOW_MID, ORIGIN_LAT, ORIGIN_LON,
                                      blend_hours=2, step_minutes=STEP_MINUTES)
            apply_anomaly(rows, idx)
        elif role == "near_miss":
            off_ts = SPILL_WINDOW_MID - timedelta(hours=random.choice([28, 32, 36]))
            jitter_lat, jitter_lon = random_point_within_radius(ORIGIN_LAT, ORIGIN_LON, 3)
            warp_through_point(rows, off_ts, jitter_lat, jitter_lon,
                                blend_hours=2, step_minutes=STEP_MINUTES)
        elif role == "false_positive":
            far_lat, far_lon = random_point_within_radius(ORIGIN_LAT, ORIGIN_LON, 28, min_radius_km=20)
            warp_through_point(rows, SPILL_WINDOW_MID, far_lat, far_lon,
                                blend_hours=2, step_minutes=STEP_MINUTES)
        # "clean" vessels: no warp at all

        for r in rows:
            all_rows.append({"vessel_id": vessel["vessel_id"], "ts": r["ts"].isoformat(),
                              "lat": round(r["lat"], 5), "lon": round(r["lon"], 5),
                              "speed_knots": r["speed_knots"], "course_deg": r["course_deg"],
                              "status": r["status"]})

        in_window = [r for r in rows if SPILL_WINDOW_START <= r["ts"] <= SPILL_WINDOW_END]
        min_in_window = min((haversine_km(r["lat"], r["lon"], ORIGIN_LAT, ORIGIN_LON)
                              for r in in_window), default=float("nan"))
        global_min_row = min(rows, key=lambda r: haversine_km(r["lat"], r["lon"], ORIGIN_LAT, ORIGIN_LON))
        global_min_dist = haversine_km(global_min_row["lat"], global_min_row["lon"], ORIGIN_LAT, ORIGIN_LON)
        verification.append({
            "vessel_id": vessel["vessel_id"], "name": vessel["name"], "role": role,
            "min_dist_in_window_km": round(min_in_window, 1),
            "global_min_dist_km": round(global_min_dist, 1),
            "global_min_dist_ts": global_min_row["ts"].isoformat(),
        })

    return all_rows, verification


def main():
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(exist_ok=True)

    vessels = build_roster()
    positions, verification = build_positions(vessels)

    roster_out = [{"vessel_id": v["vessel_id"], "name": v["name"], "type": v["type"]}
                  for v in vessels]
    (out_dir / "vessels.json").write_text(json.dumps(roster_out, indent=2))

    df = pd.DataFrame(positions)
    df.to_csv(out_dir / "ais_positions.csv", index=False)

    print(f"Wrote {len(roster_out)} vessels -> {out_dir/'vessels.json'}")
    print(f"Wrote {len(df)} position rows -> {out_dir/'ais_positions.csv'}")
    print(f"Spill window: {SPILL_WINDOW_START.isoformat()} .. {SPILL_WINDOW_END.isoformat()}")
    print(f"Origin zone: {ORIGIN_LAT}, {ORIGIN_LON}\n")

    print(f"{'vessel':<10}{'name':<20}{'role':<16}{'min_dist_in_window':>20}{'global_min_dist':>18}")
    for v in verification:
        print(f"{v['vessel_id']:<10}{v['name']:<20}{v['role']:<16}"
              f"{v['min_dist_in_window_km']:>17.1f} km{v['global_min_dist_km']:>15.1f} km")


if __name__ == "__main__":
    main()
