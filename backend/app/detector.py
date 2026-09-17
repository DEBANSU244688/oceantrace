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

    best = max(contours, key=score)
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

    single_mask = np.zeros_like(mask)
    cv2.drawContours(single_mask, [best], -1, 255, thickness=cv2.FILLED)

    return DetectionResult(
        mask=single_mask,
        contour_px=best.reshape(-1, 2),
        confidence=round(confidence, 3),
    )
