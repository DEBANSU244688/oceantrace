"""
fetch_sar_tiles.py — pull real Sentinel-1 SAR tiles from Zenodo and wire them
into the demo scenario (DRD.md §1, and the pre-round checklist in §4).

Source: "Refined Deep-SAR Oil Spill (SOS) dataset", Zenodo record 15298010,
CC-BY-4.0 (doi:10.5281/zenodo.15298010), the refined release of the Deep-SAR
SOS dataset from Zhu et al., IEEE TGRS 2021. Its `images.zip` is 1.1 GB, so
this script does NOT download it — it uses HTTP range requests to read the
zip's central directory and then pull only the handful of member files we
actually want, a few hundred KB in total. That keeps the pre-round checklist
runnable on venue wifi.

Georeferencing, stated plainly because a judge may well ask: the SOS tiles are
crops shipped without any geocoding, so there is no true lat/lon to recover.
This script places each tile so that the slick detector.py finds in it lands on
the scenario's DETECTED_LAT/LON (app/config.py), at the pixel spacing in
TILE_METRES_PER_PX. The *pixels* are real Sentinel-1 backscatter; the *position*
is the demo scenario's. That is what makes the real imagery composable with the
synthetic AIS roster, which is itself generated around the same scenario — see
DRD.md §3, where the PS explicitly permits synthetic AIS.

Writes, for each tile:
  data/sample_images/<id>.png          grayscale SAR tile
  data/sample_images/<id>_meta.json    its geographic bounding box

Then add the ids it prints to SAMPLE_IMAGES in app/config.py.

Usage:
    python scripts/fetch_sar_tiles.py
"""
import http.client
import io
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, detector, geo_utils  # noqa: E402

ZIP_URL = "https://zenodo.org/api/records/15298010/files/images.zip/content"

# Chosen by running detector.py across a random sample of the dataset's
# validation split and scoring each result against the dataset's own
# ground-truth masks — see scripts/validate_detector.py, which reproduces the
# numbers. These three are the ones where the detection is both accurate and
# legible to someone looking at the screen for the first time.
# Which dataset member backs each registered sample image. The geographic
# placement comes from that image's scenario binding in app/config.py, so each
# tile lands on a different spill event.
TILES = [
    ("s1_371", "images/val/sentinel_371.png"),
    ("s1_485", "images/val/sentinel_485.png"),
    ("s1_473", "images/val/sentinel_473.png"),
]

OUT_DIR = Path(__file__).resolve().parent.parent / config.SAMPLE_IMAGES_DIR


def _get(byte_range, attempts=4):
    """One ranged GET. Zenodo sits behind a CDN whose nodes occasionally serve a
    bad TLS cert or drop the connection, which is exactly the kind of thing that
    eats twenty minutes on venue wifi — so retry rather than fail the run."""
    req = urllib.request.Request(ZIP_URL, headers={"Range": f"bytes={byte_range}"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, OSError,
                http.client.HTTPException) as e:
            # http.client.IncompleteRead is an HTTPException, not an OSError —
            # Zenodo's CDN truncates a response often enough that leaving it out
            # means the script dies partway through for no good reason.
            if attempt == attempts:
                raise
            print(f"    retry {attempt}/{attempts - 1} after {type(e).__name__}: {e}")
            time.sleep(2 * attempt)


def read_central_directory():
    """Locate and parse the zip's central directory over HTTP, so we can find
    each member's byte offset without downloading the 1.1 GB archive."""
    tail = _get("-65536")
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd == -1:
        raise RuntimeError("No zip end-of-central-directory found — did the URL change?")
    cd_size = struct.unpack("<I", tail[eocd + 12:eocd + 16])[0]
    cd_off = struct.unpack("<I", tail[eocd + 16:eocd + 20])[0]

    cd = _get(f"{cd_off}-{cd_off + cd_size - 1}")
    entries, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method = struct.unpack("<H", cd[p + 10:p + 12])[0]
        csize = struct.unpack("<I", cd[p + 20:p + 24])[0]
        nlen, elen, clen = struct.unpack("<HHH", cd[p + 28:p + 34])
        local_off = struct.unpack("<I", cd[p + 42:p + 46])[0]
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        entries[name] = {"method": method, "csize": csize, "local_off": local_off}
        p += 46 + nlen + elen + clen
    return entries


def extract(entry):
    """Range-fetch and inflate a single zip member."""
    start = entry["local_off"]
    # 30-byte local header + name/extra fields (bounded by 512) + the data
    blob = _get(f"{start}-{start + 30 + 512 + entry['csize']}")
    if blob[:4] != b"PK\x03\x04":
        raise RuntimeError("Expected a zip local file header — archive layout changed?")
    nlen, elen = struct.unpack("<HH", blob[26:30])
    data = blob[30 + nlen + elen:30 + nlen + elen + entry["csize"]]
    return zlib.decompress(data, -15) if entry["method"] == 8 else data


def bbox_for(image_gray, sc):
    """Build the tile's bounding box so the slick detector.py finds sits on the
    scenario's DETECTED_LAT/LON. Everything downstream — hindcast, spill window,
    the AIS funnel — keys off that centroid, so pinning it is what lets a real
    image drop into the existing scenario without regenerating the AIS roster."""
    height_px, width_px = image_gray.shape
    det = detector.detect(image_gray)
    # The pixel->lat/lon mapping is affine, so the polygon centroid taken in
    # pixel space maps exactly onto the geographic centroid characterize.py
    # will report. Using the contour's arithmetic mean instead lands ~150 m off.
    anchor_px = Polygon(det.contour_px).centroid.coords[0]
    bbox = geo_utils.bbox_anchored_at(
        width_px, height_px, anchor_px,
        sc["detected_lat"], sc["detected_lon"], config.TILE_METRES_PER_PX)
    return bbox, det


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"reading zip index over HTTP range requests: {ZIP_URL}")
    entries = read_central_directory()
    print(f"  {len(entries)} members indexed\n")

    registered = {img["id"]: img for img in config.SAMPLE_IMAGES}
    for image_id, member in TILES:
        if member not in entries:
            print(f"  !! {member} not in the archive — skipping")
            continue
        meta = registered.get(image_id)
        if meta is None:
            print(f"  !! {image_id} is not in SAMPLE_IMAGES — skipping")
            continue
        sc = config.scenario(meta.get("scenario"))

        raw = extract(entries[member])
        gray = Image.open(io.BytesIO(raw)).convert("L")
        arr = np.array(gray)

        bbox, det = bbox_for(arr, sc)
        gray.save(OUT_DIR / f"{image_id}.png")
        (OUT_DIR / f"{image_id}_meta.json").write_text(json.dumps(bbox, indent=2))

        km = arr.shape[1] * config.TILE_METRES_PER_PX / 1000.0
        print(f"  {image_id}: {member}  {arr.shape[1]}x{arr.shape[0]}px "
              f"({km:.2f} km across)  confidence={det.confidence}")
        print(f"      -> {sc['id']} {sc['label']} @ "
              f"{sc['detected_lat']:.4f},{sc['detected_lon']:.4f}  "
              f"(guilty: {sc['guilty']})")


if __name__ == "__main__":
    main()
