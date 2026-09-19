"""
validate_detector.py — score detector.py against real ground-truth labels.

The Zenodo SOS record ships a masks.zip (28 MB) alongside its 1.1 GB images.zip.
That gives us something the synthetic fixture never could: a way to say how good
the classical CV detector actually is on real Sentinel-1 backscatter, with a
number, rather than asserting it looks about right.

Downloads masks.zip once into a cache dir, range-fetches a random sample of the
matching validation images (see fetch_sar_tiles.py for how that works), and
reports per-tile and aggregate IoU / precision / recall.

This is the honest answer to "how well does it work?" in the demo Q&A — worth
having a real number for, especially since BL.md deliberately cuts training a
model. Run it once before the round; it needs the internet, the demo does not.

Usage:
    python scripts/validate_detector.py [--sample N]
"""
import argparse
import io
import json
import random
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, detector  # noqa: E402
from scripts.fetch_sar_tiles import extract, read_central_directory  # noqa: E402

MASKS_URL = "https://zenodo.org/api/records/15298010/files/masks.zip/content"
CACHE = Path(__file__).resolve().parent.parent / "data" / ".validation_cache"


def load_masks():
    CACHE.mkdir(parents=True, exist_ok=True)
    masks_zip = CACHE / "masks.zip"
    if not masks_zip.exists():
        print(f"downloading ground-truth masks (28 MB) -> {masks_zip}")
        urllib.request.urlretrieve(MASKS_URL, masks_zip)
    z = zipfile.ZipFile(masks_zip)
    return z, {Path(n).name: n for n in z.namelist()
               if "/val/" in n and n.endswith(".png") and "__MACOSX" not in n}


def run_gate_eval(args):
    """Measure the attribution gate against the dataset's own labels.

    The gate exists because Otsu always returns the darkest region in a frame,
    so a tile with no oil in it still yields a polygon — and without a gate the
    pipeline would hindcast that and name a real vessel for a spill that never
    happened. These are the numbers behind the thresholds in app/config.py.
    """
    z, mask_index = load_masks()
    entries = read_central_directory()

    empty, oily = [], []
    for name, member in mask_index.items():
        has_oil = (np.array(Image.open(io.BytesIO(z.read(member))).convert("L")) > 127).any()
        (oily if has_oil else empty).append(name)
    print(f"validation split: {len(empty)} tiles with NO oil, {len(oily)} with oil")

    random.seed(args.seed)
    n = min(args.sample, len(empty))
    groups = {"no oil": empty[:n], "has oil": random.sample(oily, n)}

    results = {}
    for label, names in groups.items():
        blocked = refused = total = 0
        for name in names:
            member = f"images/val/{name}"
            if member not in entries:
                continue
            total += 1
            gray = np.array(Image.open(io.BytesIO(extract(entries[member]))).convert("L"))
            try:
                det = detector.detect(gray)
            except ValueError:
                refused += 1      # no region above the size threshold at all
                blocked += 1
                continue
            ok, _reason = detector.attribution_gate(det.confidence, det.lookalike_risk)
            if not ok:
                blocked += 1
        results[label] = (blocked, refused, total)

    print(f"\ngate: confidence >= {config.MIN_ATTRIBUTION_CONFIDENCE:.2f} "
          f"and lookalike_risk <= {config.MAX_ATTRIBUTION_LOOKALIKE_RISK:.2f}\n")
    for label, (blocked, refused, total) in results.items():
        print(f"  {label:8}  blocked {blocked}/{total} ({blocked / max(total, 1):.0%})"
              f"   [{refused} refused outright by the detector]")

    no_oil_blocked = results["no oil"][0] / max(results["no oil"][2], 1)
    oil_blocked = results["has oil"][0] / max(results["has oil"][2], 1)
    print(f"\nBlocking {no_oil_blocked:.0%} of no-oil tiles costs us {oil_blocked:.0%} of")
    print("genuine slicks. That asymmetry is deliberate: declining to attribute a")
    print("real spill costs an analyst a second look, attributing one that never")
    print("happened costs a ship operator their reputation.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=70,
                    help="how many validation tiles to score (default 70)")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--gate", action="store_true",
                    help="instead of scoring IoU, measure the attribution gate: "
                         "how often it blocks tiles the dataset labels as "
                         "containing no oil, vs tiles that do contain oil")
    args = ap.parse_args()

    if args.gate:
        return run_gate_eval(args)

    z, mask_index = load_masks()
    entries = read_central_directory()
    candidates = [n for n in entries
                  if n.startswith("images/") and "/val/" in n
                  and Path(n).name.startswith("sentinel")
                  and Path(n).name in mask_index]
    random.seed(args.seed)
    sample = random.sample(candidates, min(args.sample, len(candidates)))
    print(f"scoring {len(sample)} real Sentinel-1 validation tiles\n")

    rows, skipped = [], 0
    for member in sample:
        name = Path(member).name
        gray = np.array(Image.open(io.BytesIO(extract(entries[member]))).convert("L"))
        gt = np.array(Image.open(io.BytesIO(z.read(mask_index[name]))).convert("L")) > 127
        try:
            pred = detector.detect(gray).mask.astype(bool)
        except ValueError:
            skipped += 1      # detector found nothing above the size threshold
            continue
        inter, union = int((pred & gt).sum()), int((pred | gt).sum())
        rows.append({
            "tile": name,
            "iou": inter / union if union else 0.0,
            "precision": inter / pred.sum() if pred.sum() else 0.0,
            "recall": inter / gt.sum() if gt.sum() else float("nan"),
        })

    ious = [r["iou"] for r in rows]
    print(f"{'IoU':>6} {'prec':>6} {'rec':>6}  tile")
    for r in sorted(rows, key=lambda r: -r["iou"]):
        print(f"{r['iou']:6.3f} {r['precision']:6.3f} {r['recall']:6.3f}  {r['tile']}")

    print(f"\nscored {len(rows)} tiles ({skipped} had no detection at all)")
    print(f"  mean IoU     {np.mean(ious):.3f}")
    print(f"  median IoU   {np.median(ious):.3f}")
    print(f"  IoU > 0.5    {sum(i > 0.5 for i in ious)}/{len(ious)}")
    print(f"  IoU > 0.3    {sum(i > 0.3 for i in ious)}/{len(ious)}")

    out = CACHE / "validation_report.json"
    out.write_text(json.dumps({
        "n_scored": len(rows), "n_no_detection": skipped,
        "mean_iou": float(np.mean(ious)), "median_iou": float(np.median(ious)),
        "tiles": rows,
    }, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
