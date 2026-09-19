"""
fetch_coastline.py — build the offline basemap.

`PRD.md` §5 says the demo must run with no internet. The map's CARTO basemap
breaks that: on venue wifi the tiles simply never arrive and every data layer
floats on black with no context.

The obvious fix — pre-caching raster tiles — is the wrong one. Both CARTO's and
OpenStreetMap's usage policies prohibit bulk tile downloading, and a cache only
covers the zoom levels and area you thought to fetch, so panning one screen over
puts you back on black.

This does it with vectors instead. Natural Earth is **public domain**, so there
is no policy question, and a clipped coastline renders at any zoom from a file
small enough to sit in the repo. For an offshore scenario that is also simply
the better basemap: the only feature that matters over open water is where the
land is.

The layer sits in a pane *below* Leaflet's tile pane, so when CARTO is reachable
its opaque tiles cover this and nothing changes. When CARTO fails, this is what
remains — no fallback logic, no blank map.

Writes:
  data/coastline.geojson    land polygons clipped to the scenario region

Usage:
    python scripts/fetch_coastline.py
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

# Natural Earth 1:10m land polygons — public domain, no attribution required
# (attribution is still nice; the frontend keeps the CARTO/OSM credit for when
# the raster basemap is the one actually being shown).
LAND_URL = "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip"

# Generous clip around the scenario region: the four spill origins span roughly
# half a degree, vessels roam 90 km from the centre, and a judge will pan. This
# covers the Odisha/Andhra coast and a good stretch of the Bay of Bengal.
PAD_DEG = 2.5
SIMPLIFY_DEG = 0.0005      # ~55 m — far finer than anything visible at demo zooms

OUT = Path(__file__).resolve().parent.parent / "data" / "coastline.geojson"


def main():
    lat, lon = config.REGION_CENTER
    clip = box(lon - PAD_DEG, lat - PAD_DEG, lon + PAD_DEG, lat + PAD_DEG)
    print(f"region {lat},{lon}  clip {clip.bounds}")

    print(f"downloading {LAND_URL}")
    with urllib.request.urlopen(LAND_URL, timeout=180) as r:
        payload = r.read()
    print(f"  {len(payload) / 1e6:.1f} MB")

    # geopandas reads straight out of the zip via pyogrio, no extraction needed
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        shp = next(n for n in z.namelist() if n.endswith(".shp"))
        tmp = OUT.parent / "_ne_land_tmp"
        tmp.mkdir(exist_ok=True)
        z.extractall(tmp)
    land = gpd.read_file(tmp / shp)
    print(f"  {len(land)} land features worldwide")

    clipped = gpd.clip(land, clip)
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()]
    clipped["geometry"] = clipped.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    print(f"  {len(clipped)} features after clipping to the region")

    clipped[["geometry"]].to_file(OUT, driver="GeoJSON")

    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()

    print(f"\nwrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Served at GET /api/basemap/land — no API key, no network, no tile policy.")


if __name__ == "__main__":
    main()
