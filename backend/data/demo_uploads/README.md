# Demo upload set

Real SAR tiles for the **upload** button. None of these are registered in
`SAMPLE_IMAGES`, so the app has never processed them — which is the answer to
"does it only work on the images you chose?"

Source: Refined Deep-SAR Oil Spill (SOS) dataset, Zenodo record 15298010,
CC-BY-4.0 (Zhu et al., IEEE TGRS 2021). Re-pull with
`python scripts/fetch_demo_uploads.py`.

| File | What it demonstrates |
|---|---|
| `01_sentinel1_strong_slick.png` | Clean Sentinel-1 detection. Best first upload — it just works. |
| `02_sentinel1_clear_slick.png` | Second Sentinel-1 slick, different shape and sea state. |
| `03_palsar_different_satellite.png` | ALOS PALSAR, not Sentinel-1 — L-band instead of C-band, a different satellite entirely. Detector handles it unchanged. |
| `04_palsar_large_slick.png` | A slick covering ~40% of the frame. Shows the area figure scaling. |
| `05_ambiguous_elevated_risk.png` | A real slick, but the scene has competing dark patches — look-alike risk climbs and the reported confidence drops accordingly. |
| `06_no_oil_lookalikes_only.png` | NO OIL. The dataset labels this tile empty. The detector still outlines the darkest region — and flags high look-alike risk while doing it. |
| `07_no_oil_faint.png` | NO OIL, and faint. Lowest confidence of the set. |

## How to use these in a demo

**Start with 01.** It is a clean detection and it builds confidence before you
show anything harder.

**Then 03.** Say: *"this one isn't even Sentinel-1 — it's ALOS PALSAR, L-band,
a different satellite. The detector doesn't need to know."*

**Finish with 06.** That tile has no oil in it at all. The detector still
outlines the darkest region — Otsu always finds something — but the detection
scores 31% confidence against a 40% floor, so **Trace origin and Analyse AIS
are refused**. The panel says why, and the API returns 409 to anyone who tries
to skip the UI.

> *"This is the real failure mode of SAR oil detection — low-wind areas and
> biogenic slicks look exactly like oil to a threshold. So the system will not
> trace an origin or name a vessel unless the detection clears a bar. Declining
> to attribute a real spill costs an analyst a second look. Attributing one
> that never happened costs a ship operator their reputation."*

Those thresholds are measured, not guessed: `python scripts/validate_detector.py
--gate` scores them against the dataset's own labels — 100% of no-oil tiles
blocked, at the cost of 20% of genuine slicks.

**To show input validation**, upload any non-image file — a `.txt`, a PDF,
anything. The API returns 415 rather than guessing.
