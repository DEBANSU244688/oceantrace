"""
characterize.py — turns a detected pixel-space contour into real-world
geometry and stats (SACD.md component #2): polygon, area, perimeter,
centroid. Pure geometry — no CV here, that's detector.py's job.
"""
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon, mapping


@dataclass
class SpillGeometry:
    polygon_geojson: dict
    area_km2: float
    perimeter_km: float
    centroid: tuple  # (lat, lon)


def _px_to_latlon(x, y, width_px, height_px, bbox):
    lon = bbox["lon_left"] + (x / width_px) * (bbox["lon_right"] - bbox["lon_left"])
    lat = bbox["lat_top"] - (y / height_px) * (bbox["lat_top"] - bbox["lat_bottom"])
    return lat, lon


def characterize(contour_px: np.ndarray, image_shape, bbox: dict) -> SpillGeometry:
    """`contour_px` is an Nx2 array of (x, y) pixel coordinates from detector.py.
    `image_shape` is the source image's (height, width) — taken from the image
    itself rather than a config constant, since real downloaded tiles come in
    whatever size the dataset shipped them at (the SOS tiles are 256x256, the
    synthetic one is 512x512) and need not be square."""
    height_px, width_px = image_shape[0], image_shape[1]
    latlon_ring = [_px_to_latlon(x, y, width_px, height_px, bbox) for x, y in contour_px]
    # shapely / GeoJSON both want (lon, lat) ordering
    lonlat_ring = [(lon, lat) for lat, lon in latlon_ring]
    if len(lonlat_ring) < 3:
        raise ValueError("Contour too small to form a polygon")

    poly = Polygon(lonlat_ring)
    if not poly.is_valid:
        poly = poly.buffer(0)  # cheap self-intersection fix, fine for a demo polygon

    centroid_lonlat = poly.centroid
    centroid = (centroid_lonlat.y, centroid_lonlat.x)  # back to (lat, lon)

    # Area/perimeter via a local equirectangular (lat/lon -> km) projection —
    # accurate enough at this scale (a few tens of km) without a full CRS lib.
    mean_lat = float(np.mean([lat for lat, _ in latlon_ring]))
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * np.cos(np.radians(mean_lat))
    xy_km = [(lon * km_per_deg_lon, lat * km_per_deg_lat) for lon, lat in lonlat_ring]
    poly_km = Polygon(xy_km)
    area_km2 = abs(poly_km.area)
    perimeter_km = poly_km.length

    return SpillGeometry(
        polygon_geojson=mapping(poly),
        area_km2=round(area_km2, 2),
        perimeter_km=round(perimeter_km, 2),
        centroid=(round(centroid[0], 5), round(centroid[1], 5)),
    )
