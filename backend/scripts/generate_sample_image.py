"""
generate_sample_image.py — builds a synthetic, SAR-style grayscale demo image
with a dark "slick" blob placed at the scenario's known DETECTED_LAT/LON
(app/config.py), plus speckle noise and a couple of decoy dark patches
(look-alikes: low-wind areas, etc.) so detector.py has to do real work
rather than just finding the only dark thing in the frame.

This is a stand-in for a real downloaded Zenodo Sentinel-1 SAR tile (see
DRD.md §1 / §4's pre-round checklist) — swap in a real image + update its
bounding box in app/config.py before the actual round if time allows. The
detection pipeline (detector.py) doesn't care which one it's given, as long
as the image + its geographic bounding box are both provided.

Writes:
  data/sample_images/sar_001.png
  data/sample_images/sar_001_meta.json   (geographic bounding box)

Usage:
    python scripts/generate_sample_image.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, geo_utils  # noqa: E402

RNG = np.random.default_rng(11)


def make_image():
    size = config.IMAGE_SIZE_PX
    half_km = config.IMAGE_HALF_WIDTH_KM

    # geographic bounding box of the image
    lat_top, _ = geo_utils.project(config.DETECTED_LAT, config.DETECTED_LON, 0, half_km)
    lat_bottom, _ = geo_utils.project(config.DETECTED_LAT, config.DETECTED_LON, 180, half_km)
    _, lon_right = geo_utils.project(config.DETECTED_LAT, config.DETECTED_LON, 90, half_km)
    _, lon_left = geo_utils.project(config.DETECTED_LAT, config.DETECTED_LON, 270, half_km)
    bbox = {"lat_top": lat_top, "lat_bottom": lat_bottom,
            "lon_left": lon_left, "lon_right": lon_right}

    def latlon_to_px(lat, lon):
        x = (lon - bbox["lon_left"]) / (bbox["lon_right"] - bbox["lon_left"]) * size
        y = (bbox["lat_top"] - lat) / (bbox["lat_top"] - bbox["lat_bottom"]) * size
        return x, y

    # background: SAR-like speckle (bright, noisy sea surface)
    base = RNG.normal(150, 18, (size, size))

    yy, xx = np.mgrid[0:size, 0:size]

    def add_dark_blob(cx, cy, rx, ry, angle_deg, darkness, edge_softness=6):
        angle = np.radians(angle_deg)
        xr = (xx - cx) * np.cos(angle) + (yy - cy) * np.sin(angle)
        yr = -(xx - cx) * np.sin(angle) + (yy - cy) * np.cos(angle)
        dist = np.sqrt((xr / rx) ** 2 + (yr / ry) ** 2)
        mask = 1 / (1 + np.exp((dist - 1) * edge_softness))  # smooth falloff
        return mask * darkness

    img = base.copy()

    # the actual slick, centered on the ground-truth DETECTED_LAT/LON
    cx, cy = latlon_to_px(config.DETECTED_LAT, config.DETECTED_LON)
    img -= add_dark_blob(cx, cy, rx=55, ry=32, angle_deg=35, darkness=95)

    # two look-alike decoys (low-wind patch + a biogenic-style slick) —
    # smaller / fainter / more irregular than the real spill
    img -= add_dark_blob(cx - 140, cy + 90, rx=22, ry=14, angle_deg=-10, darkness=45)
    img -= add_dark_blob(cx + 160, cy - 120, rx=18, ry=30, angle_deg=60, darkness=35)

    img = np.clip(img, 0, 255).astype(np.uint8)

    out_dir = Path(__file__).resolve().parent.parent / config.SAMPLE_IMAGES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, mode="L").save(out_dir / "sar_001.png")
    (out_dir / "sar_001_meta.json").write_text(json.dumps(bbox, indent=2))

    print(f"Wrote {out_dir/'sar_001.png'} ({size}x{size})")
    print(f"Bounding box: {bbox}")
    print(f"Ground-truth slick center (px): ({cx:.1f}, {cy:.1f}) "
          f"-> lat/lon ({config.DETECTED_LAT:.5f}, {config.DETECTED_LON:.5f})")


if __name__ == "__main__":
    make_image()
