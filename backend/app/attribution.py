"""
attribution.py — AIS funnel + weighted attribution scoring
(SACD.md components #4 and #5).

Rule-based, not ML (see BL.md's WON'T list) — every sub-score is a small,
explainable function of the AIS data, combined via the fixed weights in
MASTER_REFERENCE_INDEX.md. This is what powers both the ranked list and the
per-vessel "why flagged" panel (S3) — the reasons text is generated from the
exact same numbers the score is built from, so there's no gap between what's
scored and what's explained.
"""
import numpy as np
import pandas as pd

from app import config
from app.geo_utils import haversine_km

VESSEL_TYPE_SCORES = {
    "tanker": 0.9, "cargo": 0.6, "container": 0.6,
    "bulk carrier": 0.6, "fishing": 0.2,
}


def _clip01(x):
    return float(np.clip(x, 0.0, 1.0))


def _vessel_track_stats(track: pd.DataFrame, origin_lat, origin_lon,
                         window_start, window_end):
    """All the raw numbers the scoring below is built from, computed once
    per vessel so nothing gets recomputed inconsistently between scores and
    reasons text."""
    dists = track.apply(lambda r: haversine_km(r.lat, r.lon, origin_lat, origin_lon), axis=1)
    track = track.assign(dist_km=dists)

    in_window = track[(track.ts >= window_start) & (track.ts <= window_end)]
    min_dist_in_window = float(in_window.dist_km.min()) if len(in_window) else float("inf")

    global_min_idx = track.dist_km.idxmin()
    global_min_row = track.loc[global_min_idx]
    global_min_dist = float(global_min_row.dist_km)
    global_min_ts = global_min_row.ts

    if window_start <= global_min_ts <= window_end:
        time_offset_hours = 0.0
    else:
        time_offset_hours = min(abs((global_min_ts - window_start).total_seconds()),
                                 abs((global_min_ts - window_end).total_seconds())) / 3600

    near_closest = track[(track.ts >= global_min_ts - pd.Timedelta(hours=1))
                          & (track.ts <= global_min_ts + pd.Timedelta(hours=1))]
    had_speed_drop = bool((near_closest.status == "reduced speed").any()
                           or (near_closest.status == "stopped").any())
    had_stop = bool((near_closest.status == "stopped").any())
    course_std = float(near_closest.course_deg.diff().abs().fillna(0).clip(upper=180).mean()) \
        if len(near_closest) > 1 else 0.0

    typical_speed = float(track.speed_knots.median())
    min_speed_near_closest = float(near_closest.speed_knots.min()) if len(near_closest) else typical_speed

    # AIS transmission-gap check — flat in this synthetic dataset (uniform
    # sampling), but computed for real so it's a live signal on real AIS data
    gap_minutes = track.sort_values("ts").ts.diff().dt.total_seconds().dropna() / 60
    max_gap = float(gap_minutes.max()) if len(gap_minutes) else 0.0

    return {
        "min_dist_in_window_km": min_dist_in_window,
        "global_min_dist_km": global_min_dist,
        "global_min_ts": global_min_ts,
        "time_offset_hours": time_offset_hours,
        "had_speed_drop": had_speed_drop,
        "had_stop": had_stop,
        "course_std": course_std,
        "typical_speed": typical_speed,
        "min_speed_near_closest": min_speed_near_closest,
        "max_gap_minutes": max_gap,
    }


def score_vessel(stats, vessel_type):
    spatial = _clip01(1 - stats["min_dist_in_window_km"] / config.SPATIAL_RADIUS_KM)
    trajectory = _clip01(1 - stats["global_min_dist_km"] / config.TRAJECTORY_RADIUS_KM)
    temporal = _clip01(1 - stats["time_offset_hours"] / config.TEMPORAL_DECAY_HOURS)

    speed_drop_ratio = 1 - (stats["min_speed_near_closest"] / max(stats["typical_speed"], 1e-6))
    speed_anomaly = _clip01(speed_drop_ratio) if stats["had_speed_drop"] else 0.05

    course_anomaly = _clip01(stats["course_std"] / 60) if stats["had_speed_drop"] else 0.05
    loitering = 0.9 if stats["had_stop"] else 0.05
    ais_anomaly = _clip01((stats["max_gap_minutes"] - 20) / 60)  # flat near 0 on uniform demo data
    vessel_type_score = VESSEL_TYPE_SCORES.get(vessel_type, 0.4)

    breakdown = {
        "spatial": round(spatial, 3), "temporal": round(temporal, 3),
        "trajectory": round(trajectory, 3), "speed_anomaly": round(speed_anomaly, 3),
        "course_anomaly": round(course_anomaly, 3), "loitering": round(loitering, 3),
        "ais_anomaly": round(ais_anomaly, 3), "vessel_type": round(vessel_type_score, 3),
    }
    total = sum(config.WEIGHTS[k] * v for k, v in breakdown.items())
    return round(_clip01(total), 3), breakdown


def build_reasons(stats, breakdown):
    reasons = []
    if stats["min_dist_in_window_km"] < config.SPATIAL_RADIUS_KM:
        reasons.append(f"{stats['min_dist_in_window_km']:.1f} km from origin during the spill window")
    if breakdown["temporal"] > 0.6:
        reasons.append("present during the estimated spill window")
    if breakdown["trajectory"] > 0.6:
        reasons.append("trajectory intersects the origin zone")
    if stats["had_stop"]:
        reasons.append("came to a stop near the origin around the estimated spill time")
    elif stats["had_speed_drop"]:
        reasons.append("unusual speed reduction near the origin")
    if breakdown["course_anomaly"] > 0.4:
        reasons.append("course deviation detected near the origin")
    if not reasons:
        far = stats["min_dist_in_window_km"]
        reasons.append(f"no strong correlation — closest approach during the window was "
                        f"{'unavailable' if far == float('inf') else f'{far:.0f} km'}")
    return reasons


def run_attribution(spill_id, origin_lat, origin_lon, window_start, window_end,
                     vessels_df, positions_df):
    results = []
    for _, vessel in vessels_df.iterrows():
        track = positions_df[positions_df.vessel_id == vessel.vessel_id]
        if track.empty:
            continue
        stats = _vessel_track_stats(track, origin_lat, origin_lon, window_start, window_end)
        score, breakdown = score_vessel(stats, vessel.type)
        reasons = build_reasons(stats, breakdown)
        results.append({
            "vessel_id": vessel.vessel_id, "name": vessel["name"], "type": vessel.type,
            "score": score, "breakdown": breakdown, "reasons": reasons,
            "_stats": stats,  # kept for the funnel counts below, stripped before the API response
        })

    results.sort(key=lambda r: r["score"], reverse=True)

    spatial_candidates = sum(1 for r in results if r["breakdown"]["spatial"] > 0.05)
    temporal_candidates = sum(1 for r in results
                               if r["breakdown"]["spatial"] > 0.05 and r["breakdown"]["temporal"] > 0.5)
    trajectory_candidates = sum(1 for r in results
                                 if r["breakdown"]["spatial"] > 0.05 and r["breakdown"]["temporal"] > 0.5
                                 and r["breakdown"]["trajectory"] > 0.5)

    funnel = {"total": len(results), "spatial": spatial_candidates,
              "temporal": temporal_candidates, "trajectory": trajectory_candidates}

    for r in results:
        r.pop("_stats")

    return funnel, results
