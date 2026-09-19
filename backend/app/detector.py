"""
detector.py — classical CV oil-spill detection (SACD.md component #1).

Deliberately NOT a trained model (see BL.md's WON'T list) — thresholding +
morphology + connected-component selection on the darkest, most compact
region in the frame. This is the same category of technique the reference
architecture calls for; it's the *training* we're skipping, not the concept.

Works on any grayscale image + a geographic bounding box (see
scripts/generate_sample_image.py for how the demo image was built) — swap in
a real Zenodo SAR tile and its bounding box and this code doesn't change.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from app import config


@dataclass
class DetectionResult:
    mask: np.ndarray            # binary mask, same size as input image
    contour_px: np.ndarray      # Nx2 array of (x, y) pixel coordinates
    confidence: float           # 0-1 heuristic confidence
    candidate_regions: int      # dark regions that survived thresholding
    rejected_lookalikes: int    # ...of which this many lost to the winner
    lookalike_risk: float       # 0-1, how ambiguous this detection is (S4)
    lookalike_note: str         # one plain sentence for the UI


def attribution_gate(confidence, lookalike_risk):
    """Is this detection solid enough to trace and attribute?

    Returns (attributable, reason). `reason` is None when the detection passes,
    and otherwise a sentence fit to show a user — this text is the whole point
    of the gate, so it has to explain itself rather than just saying "no".
    """
    if confidence < config.MIN_ATTRIBUTION_CONFIDENCE:
        return False, (
            f"Detection confidence {confidence:.0%} is below the "
            f"{config.MIN_ATTRIBUTION_CONFIDENCE:.0%} threshold required to trace an "
            f"origin or name a vessel. The darkest region in this scene is not "
            f"convincingly an oil slick.")
    if lookalike_risk > config.MAX_ATTRIBUTION_LOOKALIKE_RISK:
        return False, (
            f"Look-alike risk {lookalike_risk:.0%} exceeds the "
            f"{config.MAX_ATTRIBUTION_LOOKALIKE_RISK:.0%} ceiling. This scene has several "
            f"comparably dark regions, so the one selected cannot be attributed "
            f"to a vessel with any confidence.")
    return True, None


def _compactness(contour_px, area_px):
    """Isoperimetric ratio: 1.0 = perfect circle, lower = more irregular.
    Oil slicks tend to be smoother/more elongated-but-solid than speckle or
    broken look-alike patches — a cheap, explainable proxy, not a trained
    classifier."""
    perimeter_px = cv2.arcLength(contour_px, closed=True)
    if perimeter_px == 0:
        return 0.0
    return float(4 * np.pi * area_px / (perimeter_px ** 2))


def detect(image_gray: np.ndarray) -> DetectionResult:
    """
    Pipeline: denoise -> Otsu threshold (inverted, since a slick is DARKER
    than open water in SAR backscatter) -> morphological cleanup -> pick the
    largest sufficiently-compact connected component -> return its mask +
    contour + a confidence heuristic.
    """
    denoised = cv2.GaussianBlur(image_gray, (5, 5), 0)

    # Otsu picks a data-driven threshold rather than a hardcoded brightness
    # cutoff, which matters since sea-state brightness varies image to image.
    _, mask = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)   # drop speckle
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)  # fill small gaps

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= config.MIN_BLOB_AREA_PX]
    if not contours:
        raise ValueError("No spill-like region found above the minimum size threshold")

    # Score every remaining candidate by size * compactness, and take the
    # best one — this is what lets the two smaller/fainter decoy blobs in
    # the demo image lose to the real slick even though they also survive
    # thresholding.
    def score(c):
        area = cv2.contourArea(c)
        return area * (0.5 + 0.5 * _compactness(c, area))

    ranked = sorted(contours, key=score, reverse=True)
    best = ranked[0]
    best_area_px = cv2.contourArea(best)
    compactness = _compactness(best, best_area_px)

    # confidence heuristic: bigger + more compact + more clearly separated
    # from the image's mean brightness -> higher confidence. Deliberately
    # simple and explainable rather than a calibrated probability.
    contrast = float(np.mean(image_gray) - np.mean(image_gray[mask.astype(bool)]))
    confidence = float(np.clip(
        0.35 * min(1.0, best_area_px / 5000)
        + 0.35 * compactness
        + 0.30 * min(1.0, contrast / 60),
        0.05, 0.99,
    ))

    # ---- S4: look-alike risk -------------------------------------------
    # Oil is not the only thing that goes dark in SAR. Low-wind areas,
    # biogenic slicks, rain cells and current fronts all suppress backscatter
    # the same way, and they are the dominant false-positive source in real
    # operational use. We do not have a classifier for them (BL.md S4 says we
    # don't need one) — what we can honestly report is how *ambiguous* this
    # particular detection was, from two signals we already computed:
    #
    #   ambiguity — how close the runner-up region scored to the winner. A
    #               near-tie means the scene has several equally slick-like
    #               dark patches and our pick is weakly justified.
    #   faintness — low contrast against the scene mean. A genuine thick
    #               slick is much darker than the sea around it; a low-wind
    #               patch is only slightly darker.
    ambiguity = 0.0
    if len(ranked) > 1:
        best_score, runner_up = score(ranked[0]), score(ranked[1])
        if best_score > 0:
            ambiguity = float(np.clip(runner_up / best_score, 0.0, 1.0))
    faintness = float(np.clip(1 - contrast / 60, 0.0, 1.0))
    lookalike_risk = float(np.clip(0.55 * ambiguity + 0.45 * faintness, 0.0, 1.0))

    # Ambiguity lowers the confidence we report, rather than being a separate
    # number nobody looks at — BL.md S4 asks for exactly this.
    confidence = confidence * (1 - 0.25 * lookalike_risk)

    rejected = len(ranked) - 1
    if rejected and lookalike_risk > 0.5:
        note = (f"{rejected} other dark region{'s' if rejected != 1 else ''} in this scene "
                f"scored close to the one selected — treat as possible look-alikes "
                f"(low-wind area, biogenic slick, rain cell)")
    elif rejected:
        note = (f"{rejected} other dark region{'s' if rejected != 1 else ''} found and "
                f"rejected as look-alikes")
    elif lookalike_risk > 0.5:
        note = "only one candidate region, but it is faint — look-alike risk is elevated"
    else:
        note = "single clear candidate region, no significant look-alike competition"

    single_mask = np.zeros_like(mask)
    cv2.drawContours(single_mask, [best], -1, 255, thickness=cv2.FILLED)

    return DetectionResult(
        mask=single_mask,
        contour_px=best.reshape(-1, 2),
        confidence=round(float(np.clip(confidence, 0.05, 0.99)), 3),
        candidate_regions=len(ranked),
        rejected_lookalikes=rejected,
        lookalike_risk=round(lookalike_risk, 3),
        lookalike_note=note,
    )
