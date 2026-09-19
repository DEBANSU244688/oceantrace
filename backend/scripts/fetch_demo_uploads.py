"""
fetch_demo_uploads.py — build a stash of real SAR tiles to hand an evaluator
for the "upload your own image" button.

None of these are wired into SAMPLE_IMAGES, so nothing here has been seen by
the app before you upload it. That is the point: when someone asks "does it
only work on the images you picked?", you want files the demo has genuinely
never processed.

The set is chosen to cover four different conversations, not just four pretty
pictures — see data/demo_uploads/README.md, which this script writes.

Same source and mechanism as fetch_sar_tiles.py: Zenodo record 15298010,
CC-BY-4.0, read via HTTP range requests so the 1.1 GB archive is never
downloaded.

Usage:
    python scripts/fetch_demo_uploads.py
"""
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fetch_sar_tiles import extract, read_central_directory  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_uploads"

# (output name, zip member, what it is for)
TILES = [
    ("01_sentinel1_strong_slick.png", "images/val/sentinel_165.png",
     "Clean Sentinel-1 detection. Best first upload — it just works."),
    ("02_sentinel1_clear_slick.png", "images/val/sentinel_212.png",
     "Second Sentinel-1 slick, different shape and sea state."),
    ("03_palsar_different_satellite.png", "images/val/palsar_119.png",
     "ALOS PALSAR, not Sentinel-1 — L-band instead of C-band, a different "
     "satellite entirely. Detector handles it unchanged."),
    ("04_palsar_large_slick.png", "images/val/palsar_593.png",
     "A slick covering ~40% of the frame. Shows the area figure scaling."),
    ("05_ambiguous_elevated_risk.png", "images/val/sentinel_500.png",
     "A real slick, but the scene has competing dark patches — look-alike "
     "risk climbs and the reported confidence drops accordingly."),
    ("06_no_oil_lookalikes_only.png", "images/val/sentinel_778.png",
     "NO OIL. The dataset labels this tile empty. The detector still outlines "
     "the darkest region — and flags high look-alike risk while doing it."),
    ("07_no_oil_faint.png", "images/val/sentinel_64.png",
     "NO OIL, and faint. Lowest confidence of the set."),
]

README = """# Demo upload set

Real SAR tiles for the **upload** button. None of these are registered in
`SAMPLE_IMAGES`, so the app has never processed them — which is the answer to
"does it only work on the images you chose?"

Source: Refined Deep-SAR Oil Spill (SOS) dataset, Zenodo record 15298010,
CC-BY-4.0 (Zhu et al., IEEE TGRS 2021). Re-pull with
`python scripts/fetch_demo_uploads.py`.

| File | What it demonstrates |
|---|---|
{table}

## How to use these in a demo

**Start with 01.** It is a clean detection and it builds confidence before you
show anything harder.

**Then 03.** Say: *"this one isn't even Sentinel-1 — it's ALOS PALSAR, L-band,
a different satellite. The detector doesn't need to know."*

**Finish with 06 if the evaluator is technical.** That tile has no oil in it at
all, and the pipeline will still draw a polygon around the darkest region —
because Otsu thresholding always finds something. Show them the look-alike risk
climbing and the confidence dropping, and say so plainly:

> *"This is the real failure mode of SAR oil detection — low-wind areas and
> biogenic slicks look exactly like oil to a threshold. We don't have a
> classifier for it, so instead of hiding it we report how contested the
> detection was. That's what this number is."*

Volunteering that is much stronger than being caught by it. It is also why the
look-alike work exists.

**To show input validation**, upload any non-image file — a `.txt`, a PDF,
anything. The API returns 415 rather than guessing.
"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("reading zip index over HTTP range requests")
    entries = read_central_directory()

    rows = []
    for out_name, member, purpose in TILES:
        if member not in entries:
            print(f"  !! {member} missing from the archive — skipping")
            continue
        raw = extract(entries[member])
        img = Image.open(io.BytesIO(raw)).convert("L")
        img.save(OUT_DIR / out_name)
        print(f"  {out_name}  <- {member}  {img.size[0]}x{img.size[1]}")
        rows.append(f"| `{out_name}` | {purpose} |")

    (OUT_DIR / "README.md").write_text(
        README.format(table="\n".join(rows)), encoding="utf-8")
    print(f"\n{len(rows)} tiles + README written to {OUT_DIR}")


if __name__ == "__main__":
    main()
