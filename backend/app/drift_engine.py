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


def _advect(start_lat, start_lon, hours, bearing_deg, speed_kmh, n_particles,
            diffusion_km_per_hour, step_hours):
    """Advect n_particles from a single start point for `hours`, along
    `bearing_deg` at `speed_kmh`, with independent random-walk diffusion per
    particle. Returns (final_lats, final_lons, path_centroid_per_step)."""
    n_steps = max(1, int(hours / step_hours))
    lats = np.full(n_particles, start_lat, dtype=float)
    lons = np.full(n_particles, start_lon, dtype=float)
    path_centroids = [(start_lat, start_lon)]

    bearing_rad = np.radians(bearing_deg)
    step_dist_km = speed_kmh * step_hours

    for _ in range(n_steps):
        # deterministic advection component (same for every particle)
        dlat = km_to_deg_lat(step_dist_km * np.cos(bearing_rad))
        dlon_per_particle = np.array([km_to_deg_lon(step_dist_km * np.sin(bearing_rad), lat)
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


def hindcast(centroid_lat, centroid_lon, hours=None) -> DriftResult:
    """Run the drift backward from the detected centroid to estimate the
    origin. `hours` defaults to config.HINDCAST_HOURS (the assumed detection
    lag) — see BL.md's S2 (age estimate) for how a real system would
    estimate this instead of assuming it."""
    hours = hours or config.HINDCAST_HOURS
    # backward = reverse the drift vector's direction
    lats, lons, path = _advect(
        centroid_lat, centroid_lon, hours,
        bearing_deg=(config.DRIFT_BEARING_DEG + 180) % 360,
        speed_kmh=config.DRIFT_SPEED_KMH,
        n_particles=config.N_PARTICLES,
        diffusion_km_per_hour=config.DIFFUSION_KM_PER_HOUR,
        step_hours=config.STEP_HOURS,
    )
    return _cloud_to_result(lats, lons, path)


def forecast(centroid_lat, centroid_lon, hours=None) -> DriftResult:
    """Run the drift forward from the detected centroid — S1 (SHOULD)."""
    hours = hours or config.FORECAST_HOURS
    lats, lons, path = _advect(
        centroid_lat, centroid_lon, hours,
        bearing_deg=config.DRIFT_BEARING_DEG,
        speed_kmh=config.DRIFT_SPEED_KMH,
        n_particles=config.N_PARTICLES,
        diffusion_km_per_hour=config.DIFFUSION_KM_PER_HOUR,
        step_hours=config.STEP_HOURS,
    )
    return _cloud_to_result(lats, lons, path)


def estimate_spill_age(polygon_geojson):
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

    # unit vector along the drift bearing (0 = north, 90 = east)
    rad = np.radians(config.DRIFT_BEARING_DEG)
    along = x_km * np.sin(rad) + y_km * np.cos(rad)
    across = x_km * np.cos(rad) - y_km * np.sin(rad)

    length_km = float(along.max() - along.min())
    width_km = float(across.max() - across.min())
    if config.DRIFT_SPEED_KMH <= 0:
        return None

    age_hours = length_km / config.DRIFT_SPEED_KMH
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
