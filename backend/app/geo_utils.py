"""Shared geo math — used by the drift engine, characterizer, AIS generator,
and the sample-image generator so every module agrees on the same projection."""
import math


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def km_to_deg_lat(km):
    return km / 110.574


def km_to_deg_lon(km, at_lat):
    return km / (111.320 * math.cos(math.radians(at_lat)))


def project(lat, lon, bearing_deg, distance_km):
    """Move `distance_km` from (lat, lon) along compass `bearing_deg`
    (0 = north, 90 = east). Flat-earth approximation — fine at this scale
    (a few tens of km)."""
    rad = math.radians(bearing_deg)
    dlat = km_to_deg_lat(distance_km * math.cos(rad))
    dlon = km_to_deg_lon(distance_km * math.sin(rad), lat)
    return lat + dlat, lon + dlon
