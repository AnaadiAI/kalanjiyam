"""Line segmentation and page reconstruction for closely written manuscripts.

Detects text lines in preprocessed historical manuscript images (exploiting Devanagari
shirorekha/headline features and horizontal projection profiles), crops detected lines
with vertical context padding, and reconstructs them into a single clean synthetic OCR image.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

LINE_SEGMENTATION_VERSION = "1.0"


@dataclass(frozen=True)
class LineSegmentationConfig:
    """Configuration parameters for manuscript line segmentation and reconstruction."""

    # Detection parameters
    min_line_height: int = 12
    max_line_height: int = 250
    profile_smooth_window: int = 9
    profile_smooth_sigma: float = 2.5
    noise_density_threshold: float = 0.015
    peak_prominence_ratio: float = 0.15
    valley_depth_ratio: float = 0.65
    margin_filter_ratio: float = 0.02

    # Cropping parameters
    top_padding_ratio: float = 0.20
    bottom_padding_ratio: float = 0.20
    min_padding_px: int = 4
    max_padding_px: int = 30

    # Reconstruction parameters
    line_spacing: int = 28
    horizontal_margin: int = 24
    background_color: int = 255


DEFAULT_LINE_SEGMENTATION_CONFIG = LineSegmentationConfig()


@dataclass
class LineDetectionStats:
    """Statistics for line detection and reconstruction."""

    lines_detected: int = 0
    original_size: tuple[int, int] = (0, 0)
    reconstructed_size: tuple[int, int] = (0, 0)
    line_heights: list[int] = field(default_factory=list)
    segmentation_latency_ms: float = 0.0
    fallback_used: bool = False


def _extract_foreground_mask(img: Image.Image | np.ndarray) -> np.ndarray:
    """Extract a binary ink mask (1 = ink / text, 0 = background) from PIL Image or ndarray."""
    if isinstance(img, Image.Image):
        gray = np.array(img.convert("L"))
    elif len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    # Check if already binarized (e.g. from hybrid_binarization)
    unique_vals = np.unique(gray)
    if len(unique_vals) <= 4:
        # Assumes background is white (>128) and ink is dark (<=128)
        return (gray < 128).astype(np.uint8)

    # Grayscale image: apply Otsu binarization
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return (binary > 0).astype(np.uint8)


def detect_text_lines(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> list[tuple[int, int, int, int]]:
    """Detect horizontal text-line bounding bands in a manuscript image.

    Exploits Devanagari shirorekha headlines and horizontal projection profiles
    to accurately separate tightly packed text lines.

    Returns:
        List of (y_start, y_end, x_start, x_end) line bounds in top-to-bottom reading order.
    """
    fg = _extract_foreground_mask(img)
    h, w = fg.shape

    if h < config.min_line_height or w < 20:
        return []

    # Exclude extreme outer margins to prevent border/stain noise from corrupting profile
    x_margin = int(w * config.margin_filter_ratio)
    y_margin = int(h * config.margin_filter_ratio)
    x_min, x_max = x_margin, max(w - x_margin, x_margin + 1)
    y_min, y_max = y_margin, max(h - y_margin, y_margin + 1)

    active_fg = fg[y_min:y_max, x_min:x_max]
    if active_fg.size == 0 or np.count_nonzero(active_fg) == 0:
        return []

    # 1. Compute horizontal ink projection profile across active text columns
    row_proj = np.sum(active_fg, axis=1).astype(np.float32)
    max_proj = np.max(row_proj)
    if max_proj == 0:
        return []

    # 2. Smooth projection profile with 1D Gaussian kernel to bridge intra-glyph gaps
    smooth_k = config.profile_smooth_window
    if smooth_k % 2 == 0:
        smooth_k += 1
    smoothed = cv2.GaussianBlur(
        row_proj.reshape(-1, 1),
        (1, smooth_k),
        sigmaX=0,
        sigmaY=config.profile_smooth_sigma,
    ).ravel()

    # 3. Determine active horizontal ink bands
    norm_profile = smoothed / max_proj
    active_mask = norm_profile > config.noise_density_threshold

    # Find contiguous active vertical spans
    diff = np.diff(active_mask.astype(np.int32))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1

    if active_mask[0]:
        starts = np.insert(starts, 0, 0)
    if active_mask[-1]:
        ends = np.append(ends, len(active_mask))

    candidate_bands: list[tuple[int, int]] = []
    for s, e in zip(starts, ends):
        band_h = e - s
        if band_h < config.min_line_height:
            # Check if this tiny band has enough ink to be a valid accent or is noise
            if np.mean(norm_profile[s:e]) < config.noise_density_threshold * 1.5:
                continue
        candidate_bands.append((int(s), int(e)))

    if not candidate_bands:
        return []

    # 4. Resolve merged lines in candidate bands (multi-line splitting via shirorekha peaks)
    final_bands: list[tuple[int, int]] = []
    for s, e in candidate_bands:
        band_profile = smoothed[s:e]
        band_h = e - s

        # If band height is large enough to contain multiple lines, search for internal valleys
        if band_h >= config.min_line_height * 2.0:
            # Find local peaks
            peaks = []
            for i in range(1, len(band_profile) - 1):
                if (
                    band_profile[i] > band_profile[i - 1]
                    and band_profile[i] >= band_profile[i + 1]
                ):
                    peaks.append(i)

            # Filter peaks by prominence
            prominent_peaks = []
            band_max = np.max(band_profile) if len(band_profile) > 0 else 1.0
            for p in peaks:
                if band_profile[p] >= band_max * config.peak_prominence_ratio:
                    prominent_peaks.append(p)

            # Check if multiple peaks are spaced like distinct lines
            split_points = []
            if len(prominent_peaks) >= 2:
                for idx in range(len(prominent_peaks) - 1):
                    p1 = prominent_peaks[idx]
                    p2 = prominent_peaks[idx + 1]
                    if (p2 - p1) >= config.min_line_height:
                        # Find deepest valley between p1 and p2
                        valley_slice = band_profile[p1:p2]
                        min_offset = int(np.argmin(valley_slice))
                        valley_idx = p1 + min_offset
                        valley_val = band_profile[valley_idx]
                        min_peak_val = min(band_profile[p1], band_profile[p2])
                        # Verify valley represents a real separation
                        if valley_val <= min_peak_val * config.valley_depth_ratio:
                            split_points.append(valley_idx)

            if split_points:
                cur_s = s
                for sp in split_points:
                    cut_y = s + sp
                    if (cut_y - cur_s) >= config.min_line_height:
                        final_bands.append((cur_s, cut_y))
                        cur_s = cut_y
                if (s + len(band_profile) - cur_s) >= config.min_line_height:
                    final_bands.append((cur_s, s + len(band_profile)))
                continue

        final_bands.append((s, e))

    if not final_bands:
        return []

    # 5. Calculate horizontal bounds for each line and convert coordinates back to page frame
    detected_lines: list[tuple[int, int, int, int]] = []
    for s, e in final_bands:
        abs_y1 = max(0, s + y_min)
        abs_y2 = min(h, e + y_min)

        # Find horizontal ink extents for this specific line band
        line_fg = fg[abs_y1:abs_y2, :]
        col_proj = np.sum(line_fg, axis=0)
        ink_cols = np.where(col_proj > 0)[0]
        if len(ink_cols) > 0:
            line_x1 = max(0, int(ink_cols[0]))
            line_x2 = min(w, int(ink_cols[-1]) + 1)
        else:
            line_x1 = x_min
            line_x2 = x_max

        detected_lines.append((abs_y1, abs_y2, line_x1, line_x2))

    return detected_lines


def crop_text_lines(
    img: Image.Image,
    detected_lines: list[tuple[int, int, int, int]],
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> list[Image.Image]:
    """Crop detected text lines from the image with proportional vertical context padding."""
    if not detected_lines:
        return []

    w, h = img.size
    line_crops: list[Image.Image] = []

    # Find overall text column width across lines for consistent crop width
    all_x1 = min(l[2] for l in detected_lines)
    all_x2 = max(l[3] for l in detected_lines)
    # Add small horizontal margin
    crop_x1 = max(0, all_x1 - config.horizontal_margin)
    crop_x2 = min(w, all_x2 + config.horizontal_margin)

    for y1, y2, _, _ in detected_lines:
        line_h = y2 - y1
        pad_top = max(
            config.min_padding_px,
            min(config.max_padding_px, int(line_h * config.top_padding_ratio)),
        )
        pad_bottom = max(
            config.min_padding_px,
            min(config.max_padding_px, int(line_h * config.bottom_padding_ratio)),
        )

        padded_y1 = max(0, y1 - pad_top)
        padded_y2 = min(h, y2 + pad_bottom)

        crop_box = (crop_x1, padded_y1, crop_x2, padded_y2)
        crop = img.crop(crop_box)
        line_crops.append(crop)

    return line_crops


def build_segmented_ocr_page(
    line_crops: list[Image.Image],
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
    mode: str = "RGB",
) -> Image.Image:
    """Reconstruct line crops into ONE single synthetic OCR image with controlled line spacing.

    Preserves top-to-bottom reading order while eliminating vertical line crowding.
    """
    if not line_crops:
        raise ValueError("Cannot build synthetic OCR page from empty line crops.")

    max_line_w = max(crop.size[0] for crop in line_crops)
    total_lines_h = sum(crop.size[1] for crop in line_crops)
    n_lines = len(line_crops)

    spacing = config.line_spacing
    margin = config.horizontal_margin

    canvas_w = max_line_w + (2 * margin)
    canvas_h = total_lines_h + ((n_lines + 1) * spacing)

    bg_color = (
        (config.background_color, config.background_color, config.background_color)
        if mode == "RGB"
        else config.background_color
    )
    canvas = Image.new(mode, (canvas_w, canvas_h), color=bg_color)

    cur_y = spacing
    for crop in line_crops:
        cw, ch = crop.size
        # Paste crop left-aligned with horizontal margin
        canvas.paste(crop, (margin, cur_y))
        cur_y += ch + spacing

    return canvas


def segment_and_reconstruct_image(
    img: Image.Image,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> tuple[Image.Image, LineDetectionStats]:
    """Complete end-to-end pipeline: detect lines, crop them, and build ONE reconstructed OCR page.

    If 0 lines are detected or detection fails, gracefully returns the original image.
    """
    stats = LineDetectionStats(original_size=img.size)
    t0 = time.perf_counter()

    try:
        detected = detect_text_lines(img, config=config)
        stats.lines_detected = len(detected)

        if not detected:
            logger.info("No text lines detected; falling back to full enhanced image.")
            stats.fallback_used = True
            stats.reconstructed_size = img.size
            stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
            return img, stats

        stats.line_heights = [y2 - y1 for y1, y2, _, _ in detected]
        crops = crop_text_lines(img, detected, config=config)

        if not crops:
            stats.fallback_used = True
            stats.reconstructed_size = img.size
            stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
            return img, stats

        reconstructed = build_segmented_ocr_page(crops, config=config, mode=img.mode)
        stats.reconstructed_size = reconstructed.size
        stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0

        logger.info(
            "Line segmentation complete: %d lines detected, original=%s, reconstructed=%s in %.2fms",
            stats.lines_detected,
            stats.original_size,
            stats.reconstructed_size,
            stats.segmentation_latency_ms,
        )
        return reconstructed, stats

    except Exception as err:
        logger.warning(
            "Line segmentation failed (%s); falling back to unsegmented enhanced image.",
            err,
        )
        stats.fallback_used = True
        stats.reconstructed_size = img.size
        stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
        return img, stats
