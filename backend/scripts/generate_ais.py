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
REGION_LAT, REGION_LON = config.REGION_CENTER
SCENARIOS = config.SCENARIOS


def window_for(sc):
    half = timedelta(hours=config.SPILL_WINDOW_HOURS / 2)
    return sc["spill_time"] - half, sc["spill_time"] + half

HOME_MIN_KM = 25                    # every vessel's home is at least this far
HOME_MAX_KM = 90                    # ...and at most this far from the region
                                     # centre, so proximity to any spill origin
                                     # only ever comes from a deliberate warp,
                                     # never from chance

# Vessel homes are drawn from a seaward arc only. Without this, a ring around
# the origin puts roughly a sixth of the roster on dry land west of Paradip,
# which is the kind of thing a judge notices the moment they zoom out. The arc
# was measured against ETOPO1 bathymetry: from config.ORIGIN, bearings 10°-250°
# are open water all the way to HOME_MAX_KM, 260°-360° hit the coast. Re-measure
# this if you move the scenario (see the note in app/config.py).
SEAWARD_BEARING_DEG = (15, 245)
PER_VESSEL_WANDER_KM = 14           # how far a vessel roams from its own home

TRACK_HOURS = 60
STEP_MINUTES = 20
# Each of the four spill events gets its own guilty vessel, its own near-miss
# (right place, wrong time) and its own false positive (right time, wrong
# place), so every event's funnel is interesting on its own rather than one
# event carrying the whole demo.
N_CLEAN_VESSELS = 26 - 3 * len(SCENARIOS)   # 14

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


def random_point_within_radius(center_lat, center_lon, radius_km, min_radius_km=0,
                               bearing_range_deg=None):
    """Uniform-area sample from an annulus. `bearing_range_deg` narrows it to a
    compass arc (0 = north, 90 = east) — used to keep vessel homes offshore."""
    r_km = min_radius_km + (radius_km - min_radius_km) * math.sqrt(random.random())
    if bearing_range_deg is None:
        theta = random.uniform(0, 2 * math.pi)
    else:
        lo, hi = bearing_range_deg
        theta = math.radians(random.uniform(lo, hi))
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
    """One roster covering the whole region. The guilty vessels are named in
    app/config.py so the scenario, the sample image bound to it and the smoke
    test all agree on who did it."""
    guilty_names = [sc["guilty"] for sc in SCENARIOS]
    for name in guilty_names:
        assert name in NAME_POOL, f"{name} is not in NAME_POOL"

    remaining = [n for n in NAME_POOL if n not in guilty_names]
    needed = 2 * len(SCENARIOS) + N_CLEAN_VESSELS
    others = random.sample(remaining, needed)

    assignments = []
    for sc, name in zip(SCENARIOS, guilty_names):
        assignments.append((name, "guilty", sc["id"]))
    cursor = 0
    for sc in SCENARIOS:
        assignments.append((others[cursor], "near_miss", sc["id"]))
        assignments.append((others[cursor + 1], "false_positive", sc["id"]))
        cursor += 2
    for name in others[cursor:]:
        assignments.append((name, "clean", None))

    return [{
        "vessel_id": f"V{i+1:03d}",
        "name": name,
        "type": random.choice(VESSEL_TYPES),
        "_role": role,            # internal only, not written to vessels.json
        "_scenario": scenario_id,
    } for i, (name, role, scenario_id) in enumerate(assignments)]


def build_positions(vessels):
    track_start = config.TRACK_ANCHOR - timedelta(hours=TRACK_HOURS / 2)
    all_rows = []
    verification = []

    for vessel in vessels:
        role = vessel["_role"]
        sc = config.SCENARIOS_BY_ID.get(vessel["_scenario"])

        # Homes are drawn from a seaward arc around the region centre, not
        # around any one spill origin — otherwise every vessel would cluster on
        # whichever event happened to be first in the list.
        home_lat, home_lon = random_point_within_radius(
            REGION_LAT, REGION_LON, HOME_MAX_KM, min_radius_km=HOME_MIN_KM,
            bearing_range_deg=SEAWARD_BEARING_DEG)

        base_speed = random.uniform(9, 15)
        rows = random_walk_track(home_lat, home_lon, track_start, TRACK_HOURS,
                                  STEP_MINUTES, base_speed, max_radius_km=PER_VESSEL_WANDER_KM)

        if sc is not None:
            origin_lat, origin_lon = sc["origin_lat"], sc["origin_lon"]
            spill_mid = sc["spill_time"]

            if role == "guilty":
                idx = warp_through_point(rows, spill_mid, origin_lat, origin_lon,
                                          blend_hours=2, step_minutes=STEP_MINUTES)
                apply_anomaly(rows, idx)
            elif role == "near_miss":
                # right place, wrong time — well outside this event's window
                off_ts = spill_mid - timedelta(hours=random.choice([28, 32, 36]))
                jitter_lat, jitter_lon = random_point_within_radius(
                    origin_lat, origin_lon, 3)
                warp_through_point(rows, off_ts, jitter_lat, jitter_lon,
                                    blend_hours=2, step_minutes=STEP_MINUTES)
            elif role == "false_positive":
                # right time, wrong place — inside the window but too far out
                far_lat, far_lon = random_point_within_radius(
                    origin_lat, origin_lon, 28, min_radius_km=20)
                warp_through_point(rows, spill_mid, far_lat, far_lon,
                                    blend_hours=2, step_minutes=STEP_MINUTES)
        # "clean" vessels: no warp at all

        for r in rows:
            all_rows.append({"vessel_id": vessel["vessel_id"], "ts": r["ts"].isoformat(),
                              "lat": round(r["lat"], 5), "lon": round(r["lon"], 5),
                              "speed_knots": r["speed_knots"], "course_deg": r["course_deg"],
                              "status": r["status"]})

        # Verify against the event this vessel was built for; clean vessels are
        # checked against whichever origin they wandered closest to.
        check_scenarios = [sc] if sc is not None else SCENARIOS
        best = None
        for candidate in check_scenarios:
            w_start, w_end = window_for(candidate)
            o_lat, o_lon = candidate["origin_lat"], candidate["origin_lon"]
            in_window = [r for r in rows if w_start <= r["ts"] <= w_end]
            min_in_window = min((haversine_km(r["lat"], r["lon"], o_lat, o_lon)
                                  for r in in_window), default=float("nan"))
            closest = min(rows, key=lambda r: haversine_km(r["lat"], r["lon"], o_lat, o_lon))
            global_min = haversine_km(closest["lat"], closest["lon"], o_lat, o_lon)
            if best is None or global_min < best[1]:
                best = (candidate["id"], global_min, min_in_window)

        verification.append({
            "vessel_id": vessel["vessel_id"], "name": vessel["name"], "role": role,
            "scenario": best[0] if role != "clean" else f"~{best[0]}",
            "min_dist_in_window_km": round(best[2], 1),
            "global_min_dist_km": round(best[1], 1),
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
    track_start = config.TRACK_ANCHOR - timedelta(hours=TRACK_HOURS / 2)
    print(f"Track window: {track_start.isoformat()} .. "
          f"{(track_start + timedelta(hours=TRACK_HOURS)).isoformat()}\n")

    print("Spill events:")
    for sc in SCENARIOS:
        w_start, w_end = window_for(sc)
        print(f"  {sc['id']}  {sc['label']:22} origin {sc['origin_lat']},{sc['origin_lon']}"
              f"  window {w_start:%m-%d %H:%M}..{w_end:%H:%M}  guilty: {sc['guilty']}")
    print()

    print(f"{'vessel':<9}{'name':<20}{'role':<16}{'event':<9}"
          f"{'in-window':>12}{'closest':>11}")
    order = {"guilty": 0, "near_miss": 1, "false_positive": 2, "clean": 3}
    for v in sorted(verification, key=lambda v: (order[v["role"]], v["scenario"])):
        print(f"{v['vessel_id']:<9}{v['name']:<20}{v['role']:<16}{v['scenario']:<9}"
              f"{v['min_dist_in_window_km']:>9.1f} km{v['global_min_dist_km']:>8.1f} km")


if __name__ == "__main__":
    main()
