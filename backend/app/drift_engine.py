"""
drift_engine.py — physics-based particle advection (SACD.md component #3).

Pure NumPy, no ML. A static current+wind vector is a deliberate
simplification for a 10h build (see SACD.md §4 / DRD.md §2) — the *method*
(particle advection, run backward for hindcasting and forward for
forecasting) is the same one the reference architecture describes; only the
data source behind the vector field is simplified.

Backward run: start N particles at the detected spill centroid, at
DETECTION_TS, and step them backward in time against the (reversed) drift
vector plus small random diffusion per particle. The cloud's centroid after
HINDCAST_HOURS is the probable origin; its spread is the uncertainty radius.

Forward run (S1, optional): same idea, stepped forward from the centroid.
"""
from dataclasses import dataclass
from datetime import timedelta

import numpy as np

from app import config
from app.geo_utils import haversine_km, km_to_deg_lat, km_to_deg_lon

RNG = np.random.default_rng(3)


@dataclass
class DriftResult:
    center: tuple            # (lat, lon) of the particle cloud's centroid
    radius_km: float         # 90th-percentile particle distance from center
    confidence: float        # 0-1, tighter cloud -> higher confidence
    particle_cloud_geojson: dict
    path_geojson: dict       # centroid's path over time, for animating the drift


def _forcing_sampler(scenario_id, reverse):
    """Return f(step_index) -> (u_kmh, v_kmh), the drift vector to apply.

    With real forcing this walks the hourly Open-Meteo series (current + 3%
    windage) for that event. Without it, it returns the constant vector from
    config, so nothing breaks when data/ocean_forcing.json has not been built.
    `reverse` flips the vector, which is what makes the backward run a genuine
    inversion of the same data the slick position was derived from.
    """
    sign = -1.0 if reverse else 1.0
    series = None
    if scenario_id is not None:
        entry = config.forcing_for(scenario_id)
        series = entry.get("series") if entry else None

    if series is None:
        rad = np.radians(config.DRIFT_BEARING_DEG)
        u = config.DRIFT_SPEED_KMH * np.sin(rad)
        v = config.DRIFT_SPEED_KMH * np.cos(rad)
        return lambda _step: (sign * u, sign * v)

    sc = config.scenario(scenario_id)
    times, us, vs = series["time"], series["u_kmh"], series["v_kmh"]

    def at(step_index, start_ts=sc["detection_ts"], step_hours=config.STEP_HOURS):
        ts = start_ts + timedelta(hours=sign * step_index * step_hours)
        key = ts.strftime("%Y-%m-%dT%H:%M")
        if key <= times[0]:
            i = 0
        elif key >= times[-1]:
            i = len(times) - 1
        else:
            i = max(j for j, t in enumerate(times) if t <= key)
        return sign * us[i], sign * vs[i]

    return at


def _advect(start_lat, start_lon, hours, n_particles, diffusion_km_per_hour,
            step_hours, forcing):
    """Advect n_particles from a single start point for `hours` under `forcing`,
    with independent random-walk diffusion per particle. Returns
    (final_lats, final_lons, path_centroid_per_step)."""
    n_steps = max(1, int(hours / step_hours))
    lats = np.full(n_particles, start_lat, dtype=float)
    lons = np.full(n_particles, start_lon, dtype=float)
    path_centroids = [(start_lat, start_lon)]

    for step in range(n_steps):
        # deterministic advection component (same for every particle)
        u_kmh, v_kmh = forcing(step)
        dlat = km_to_deg_lat(v_kmh * step_hours)
        dlon_per_particle = np.array([km_to_deg_lon(u_kmh * step_hours, lat)
                                       for lat in lats])
        lats = lats + dlat
        lons = lons + dlon_per_particle

        # random diffusion component (independent per particle) — this is
        # what turns a single point into a probability cloud
        sigma_km = diffusion_km_per_hour * step_hours
        jitter_bearing = RNG.uniform(0, 2 * np.pi, n_particles)
        jitter_dist = RNG.normal(0, sigma_km, n_particles)
        lats = lats + np.array([km_to_deg_lat(d * np.cos(b))
                                 for d, b in zip(jitter_dist, jitter_bearing)])
        lons = lons + np.array([km_to_deg_lon(d * np.sin(b), lat)
                                 for d, b, lat in zip(jitter_dist, jitter_bearing, lats)])

        path_centroids.append((float(np.mean(lats)), float(np.mean(lons))))

    return lats, lons, path_centroids


def _cloud_to_result(lats, lons, path_centroids) -> DriftResult:
    center_lat, center_lon = float(np.mean(lats)), float(np.mean(lons))
    dists = np.array([haversine_km(center_lat, center_lon, la, lo)
                       for la, lo in zip(lats, lons)])
    radius_km = float(np.percentile(dists, 90))
    # tighter cloud (small radius) -> higher confidence; deliberately simple
    confidence = float(np.clip(1 - radius_km / 25, 0.15, 0.95))

    points_geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lo, la]},
             "properties": {}}
            for la, lo in zip(lats, lons)
        ],
    }
    path_geojson = {
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[lo, la] for la, lo in path_centroids]},
        "properties": {},
    }
    return DriftResult(center=(round(center_lat, 5), round(center_lon, 5)),
                        radius_km=round(radius_km, 2),
                        confidence=round(confidence, 3),
                        particle_cloud_geojson=points_geojson,
                        path_geojson=path_geojson)


def hindcast(centroid_lat, centroid_lon, hours=None, scenario_id=None) -> DriftResult:
    """Run the drift backward from the detected centroid to estimate the origin.

    With real forcing this integrates the hourly Open-Meteo series backward from
    the satellite overpass — the same data, reversed, that carried the slick
    there in the first place. `hours` defaults to config.HINDCAST_HOURS (the
    assumed detection lag); see S2 for estimating it from the slick instead.
    """
    hours = hours or config.HINDCAST_HOURS
    lats, lons, path = _advect(
        centroid_lat, centroid_lon, hours,
        n_particles=config.N_PARTICLES,
        diffusion_km_per_hour=config.DIFFUSION_KM_PER_HOUR,
        step_hours=config.STEP_HOURS,
        forcing=_forcing_sampler(scenario_id, reverse=True),
    )
    return _cloud_to_result(lats, lons, path)


def forecast(centroid_lat, centroid_lon, hours=None, scenario_id=None) -> DriftResult:
    """Run the drift forward from the detected centroid — S1 (SHOULD)."""
    hours = hours or config.FORECAST_HOURS
    lats, lons, path = _advect(
        centroid_lat, centroid_lon, hours,
        n_particles=config.N_PARTICLES,
        diffusion_km_per_hour=config.DIFFUSION_KM_PER_HOUR,
        step_hours=config.STEP_HOURS,
        forcing=_forcing_sampler(scenario_id, reverse=False),
    )
    return _cloud_to_result(lats, lons, path)


def estimate_spill_age(polygon_geojson, scenario_id=None):
    """S2 — estimate how long the slick has been drifting, from its own shape.

    A spill from an effectively point-like source that has been advected for T
    hours gets smeared into a streak along the drift axis roughly v*T long. So
    measuring the slick's extent *along the drift bearing* and dividing by the
    drift speed gives an age estimate that comes from the image, independent of
    config.HINDCAST_HOURS (which is an assumed satellite-pass lag, not a
    measurement). Showing both is the point: two independent routes to the same
    number is a much better answer than one assumption restated twice.

    Confidence comes from elongation. A long thin streak is strong evidence of
    directional drift; a blob that is as wide as it is long carries almost no
    temporal information, and we say so rather than quoting a firm number.
    """
    coords = polygon_geojson.get("coordinates") or []
    if not coords or not coords[0]:
        return None
    ring = coords[0]                       # GeoJSON Polygon: [[[lon, lat], ...]]
    lons = np.array([c[0] for c in ring], dtype=float)
    lats = np.array([c[1] for c in ring], dtype=float)
    mean_lat = float(np.mean(lats))

    # local flat projection to km (east, north), same approximation as elsewhere
    x_km = (lons - float(np.mean(lons))) * 111.320 * np.cos(np.radians(mean_lat))
    y_km = (lats - mean_lat) * 110.574

    # Measure along the drift axis this event actually experienced, not a global
    # constant — with real forcing the four events drift on different bearings.
    entry = config.forcing_for(scenario_id) if scenario_id else None
    bearing = entry["mean_bearing_deg"] if entry else config.DRIFT_BEARING_DEG
    drift_speed = entry["mean_drift_kmh"] if entry else config.DRIFT_SPEED_KMH
    rad = np.radians(bearing)
    along = x_km * np.sin(rad) + y_km * np.cos(rad)
    across = x_km * np.cos(rad) - y_km * np.sin(rad)

    length_km = float(along.max() - along.min())
    width_km = float(across.max() - across.min())
    if drift_speed <= 0:
        return None

    age_hours = length_km / drift_speed
    elongation = length_km / max(width_km, 1e-6)
    # elongation 1.0 (round blob) -> ~0.15, elongation 3+ -> ~0.9
    confidence = float(np.clip((elongation - 1.0) / 2.0, 0.0, 1.0) * 0.75 + 0.15)

    return {
        "estimated_age_hours": round(age_hours, 1),
        "confidence": round(confidence, 3),
        "along_drift_km": round(length_km, 2),
        "across_drift_km": round(width_km, 2),
        "method": ("slick extent along the drift axis divided by drift speed; "
                    "independent of the assumed satellite-pass lag"),
    }


def estimate_spill_window(detection_ts, hindcast_hours=None):
    """+/- 2h uncertainty band around the hindcast-implied spill time.

    `detection_ts` is when the satellite acquired the tile, which is a property
    of the image, not a global — each sample tile belongs to a different spill
    event with its own overpass time (see config.SCENARIOS)."""
    hindcast_hours = hindcast_hours or config.HINDCAST_HOURS
    implied_spill_time = detection_ts - timedelta(hours=hindcast_hours)
    half = timedelta(hours=config.SPILL_WINDOW_HOURS / 2)
    return implied_spill_time - half, implied_spill_time + half
