"""
fetch_ocean_forcing.py — replace the invented drift vector with real ocean data.

Until now the drift engine advected particles along a single made-up vector
(DRIFT_BEARING_DEG / DRIFT_SPEED_KMH). The *method* was right — particle
advection is what a production system does — but the forcing was a guess, and
`DRD.md` §2 was explicit that this was the simplification we were accepting.

This removes that simplification. It pulls the real hourly ocean current and
10 m wind over each spill event's own location and dates from Open-Meteo (free,
no API key, no registration) and writes them to disk, so the demo itself still
runs fully offline.

Drift physics
-------------
Oil on water moves with the current plus a fraction of the wind — the slick sits
partly proud of the surface, so it catches air. That fraction ("windage") is
conventionally 2-4% for oil; we use 3%.

    drift = current + 0.03 × wind

Direction conventions differ between the two, which is the easiest thing in this
whole file to get backwards:
  * **wind** direction is meteorological — the direction the wind blows *from*,
    so the vector points at bearing + 180°.
  * **ocean current** direction is oceanographic — the direction the water flows
    *towards*, used as-is.

Scenario consistency
--------------------
Each event's ground truth is its origin. Where the slick *is* when the satellite
sees it is then a consequence of the real drift, not a constant — so this script
forward-advects each origin through the real forcing over HINDCAST_HOURS and
records the resulting detected position. `fetch_sar_tiles.py` anchors that
event's tile there, and the drift engine integrates backward through the same
series to recover the origin. Same data in both directions, so the recovery is a
real inversion rather than an arithmetic identity.

Writes:
  data/ocean_forcing.json

Usage:
    python scripts/fetch_ocean_forcing.py
"""
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, geo_utils  # noqa: E402

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WINDAGE = 0.03          # fraction of wind speed imparted to the slick
PAD_HOURS = 18          # fetch either side of the window we actually integrate

OUT = Path(__file__).resolve().parent.parent / "data" / "ocean_forcing.json"


def _get(url, params, attempts=4):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(f"{url}?{query}", timeout=60) as r:
                payload = json.load(r)
            if "error" in payload:
                raise RuntimeError(payload.get("reason", "unknown API error"))
            return payload
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == attempts:
                raise
            print(f"    retry {attempt} after {type(e).__name__}: {e}")


def to_uv(speed, direction_deg, coming_from):
    """Polar to (east, north) components in the same unit as `speed`."""
    if speed is None or direction_deg is None:
        return 0.0, 0.0
    bearing = direction_deg + 180 if coming_from else direction_deg
    rad = math.radians(bearing)
    return speed * math.sin(rad), speed * math.cos(rad)


def fetch_series(sc):
    """Hourly drift vector (u, v) in km/h over this event's window."""
    start = (sc["spill_time"] - timedelta(hours=PAD_HOURS)).date().isoformat()
    end = (sc["detection_ts"] + timedelta(hours=config.FORECAST_HOURS + PAD_HOURS)
           ).date().isoformat()
    common = {"latitude": sc["origin_lat"], "longitude": sc["origin_lon"],
              "start_date": start, "end_date": end, "timezone": "UTC"}

    marine = _get(MARINE_URL, {**common,
                               "hourly": "ocean_current_velocity,ocean_current_direction"})
    weather = _get(WEATHER_URL, {**common, "hourly": "wind_speed_10m,wind_direction_10m"})

    mh, wh = marine["hourly"], weather["hourly"]
    wind_at = dict(zip(wh["time"], zip(wh["wind_speed_10m"], wh["wind_direction_10m"])))

    times, us, vs = [], [], []
    for i, t in enumerate(mh["time"]):
        cu, cv = to_uv(mh["ocean_current_velocity"][i],
                       mh["ocean_current_direction"][i], coming_from=False)
        ws, wd = wind_at.get(t, (0.0, 0.0))
        wu, wv = to_uv(ws, wd, coming_from=True)
        times.append(t)
        us.append(round(cu + WINDAGE * wu, 4))
        vs.append(round(cv + WINDAGE * wv, 4))
    return {"time": times, "u_kmh": us, "v_kmh": vs}


def sample(series, ts):
    """Linearly interpolate the drift vector at an arbitrary timestamp."""
    key = ts.strftime("%Y-%m-%dT%H:%M")
    times = series["time"]
    if key <= times[0]:
        return series["u_kmh"][0], series["v_kmh"][0]
    if key >= times[-1]:
        return series["u_kmh"][-1], series["v_kmh"][-1]
    lo = 0
    for i, t in enumerate(times):
        if t <= key:
            lo = i
        else:
            break
    hi = min(lo + 1, len(times) - 1)
    span = 60.0  # hourly data
    minutes = (ts - ts.replace(minute=0, second=0, microsecond=0)).total_seconds() / 60
    w = minutes / span
    return (series["u_kmh"][lo] * (1 - w) + series["u_kmh"][hi] * w,
            series["v_kmh"][lo] * (1 - w) + series["v_kmh"][hi] * w)


def advect_point(series, lat, lon, start_ts, hours, step_hours=0.25):
    """Integrate one point through the real forcing. Positive `hours` moves
    forward in time, which is how a spill becomes the slick the satellite sees."""
    steps = max(1, int(abs(hours) / step_hours))
    sign = 1 if hours >= 0 else -1
    ts = start_ts
    for _ in range(steps):
        u, v = sample(series, ts)
        lat += geo_utils.km_to_deg_lat(sign * v * step_hours)
        lon += geo_utils.km_to_deg_lon(sign * u * step_hours, lat)
        ts += timedelta(hours=sign * step_hours)
    return lat, lon


def main():
    out = {"windage": WINDAGE,
           "source": "Open-Meteo marine + forecast APIs (free, no API key)",
           "scenarios": {}}

    for sc in config.SCENARIOS:
        print(f"{sc['id']}  {sc['label']}  ({sc['origin_lat']}, {sc['origin_lon']})")
        series = fetch_series(sc)

        det_lat, det_lon = advect_point(series, sc["origin_lat"], sc["origin_lon"],
                                        sc["spill_time"], config.HINDCAST_HOURS)
        drift_km = geo_utils.haversine_km(sc["origin_lat"], sc["origin_lon"],
                                          det_lat, det_lon)

        # mean vector over the drift window, for the S2 age estimate which needs
        # a single axis to measure the slick's elongation against
        n = max(1, int(config.HINDCAST_HOURS))
        sampled = [sample(series, sc["spill_time"] + timedelta(hours=h)) for h in range(n)]
        mu = sum(s[0] for s in sampled) / len(sampled)
        mv = sum(s[1] for s in sampled) / len(sampled)
        mean_speed = math.hypot(mu, mv)
        mean_bearing = (math.degrees(math.atan2(mu, mv)) + 360) % 360

        print(f"    {len(series['time'])} hourly samples · mean drift "
              f"{mean_speed:.2f} km/h towards {mean_bearing:.0f}°")
        print(f"    slick travels {drift_km:.2f} km in {config.HINDCAST_HOURS:g} h "
              f"-> detected at {det_lat:.4f}, {det_lon:.4f}")

        out["scenarios"][sc["id"]] = {
            "series": series,
            "detected_lat": det_lat,
            "detected_lon": det_lon,
            "mean_drift_kmh": round(mean_speed, 4),
            "mean_bearing_deg": round(mean_bearing, 2),
            "drift_km": round(drift_km, 3),
        }

    OUT.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Re-run scripts/fetch_sar_tiles.py and generate_sample_image.py so the "
          "tiles are anchored on the new detected positions.")


if __name__ == "__main__":
    main()
