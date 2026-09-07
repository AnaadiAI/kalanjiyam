"""Line segmentation and page reconstruction for closely written manuscripts.

Detects text lines in preprocessed historical manuscript images (exploiting Devanagari
shirorekha/headline features, text-region isolation, and horizontal projection profiles),
places crop boundaries precisely in the whitespace valleys between adjacent lines,
and reconstructs them into a single clean synthetic OCR image without overlapping crops.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from PIL import Image
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)

LINE_SEGMENTATION_VERSION = "2.0"


@dataclass(frozen=True)
class LineSegmentationConfig:
    """Configuration parameters for manuscript line segmentation and reconstruction."""

    # Detection parameters
    min_line_height: int = 10
    noise_density_threshold: float = 0.05
    peak_prominence_ratio: float = 0.03
    peak_height_ratio: float = 0.08
    margin_filter_ratio: float = 0.02
    vpp_threshold_ratio: float = 0.08

    # Reconstruction parameters
    line_spacing: int = 24
    horizontal_margin: int = 30
    vertical_margin: int = 30
    background_color: int = 255
    preserve_paragraph_gaps: bool = True
    paragraph_gap_multiplier: float = 1.35


DEFAULT_LINE_SEGMENTATION_CONFIG = LineSegmentationConfig()


@dataclass
class LineDetectionStats:
    """Statistics for line detection and reconstruction."""

    lines_detected: int = 0
    original_size: tuple[int, int] = (0, 0)
    reconstructed_size: tuple[int, int] = (0, 0)
    line_heights: list[int] = field(default_factory=list)
    line_peaks: list[int] = field(default_factory=list)
    line_boundaries: list[int] = field(default_factory=list)
    text_block: tuple[int, int, int, int] = (0, 0, 0, 0)
    segmentation_latency_ms: float = 0.0
    fallback_used: bool = False
    upscale_enabled: bool = False
    upscale_factor: int = 1


def _extract_foreground_mask(img: Image.Image | np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    """Extract a binary ink mask (255 = ink / text, 0 = background) and optional color image array.

    Suppresses red border / marginal ink from corrupting text detection when input is RGB.
    """
    if isinstance(img, Image.Image):
        raw_arr = np.array(img)
    else:
        raw_arr = img.copy()

    if raw_arr.ndim == 3 and raw_arr.shape[2] >= 3:
        gray = cv2.cvtColor(raw_arr, cv2.COLOR_RGB2GRAY)
        # Identify saturated red ink/borders: R > 120, R - G > 30, R - B > 30
        r, g, b = (
            raw_arr[:, :, 0].astype(int),
            raw_arr[:, :, 1].astype(int),
            raw_arr[:, :, 2].astype(int),
        )
        red_mask = (r > 120) & (r - g > 30) & (r - b > 30)
    else:
        gray = raw_arr.copy() if raw_arr.ndim == 2 else raw_arr[:, :, 0]
        red_mask = None

    # Check if already binarized
    unique_vals = np.unique(gray)
    if len(unique_vals) <= 4:
        binary = np.where(gray < 128, 255, 0).astype(np.uint8)
    else:
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

    # Exclude red border pixels from text foreground if detected
    if red_mask is not None and np.any(red_mask):
        binary[red_mask] = 0

    return binary, raw_arr


def _detect_text_block_horizontal_range(
    bin_img: np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> tuple[int, int]:
    """Determine common left (x_start) and right (x_end) bounds of the central text block."""
    h, w = bin_img.shape

    # Focus on central 80% vertical region to exclude top/bottom margin annotations
    y_start = int(0.10 * h)
    y_end = max(y_start + 1, int(0.90 * h))
    core_slice = bin_img[y_start:y_end, :]

    vpp = np.sum(core_slice == 255, axis=0).astype(np.float32)
    if np.max(vpp) == 0:
        return 0, w

    smooth_k = max(21, int(w * 0.02)) | 1
    vpp_smooth = cv2.GaussianBlur(
        vpp[:, None], (smooth_k, 1), smooth_k / 4.0
    ).flatten()

    vpp_thresh = np.max(vpp_smooth) * config.vpp_threshold_ratio
    active_cols = np.where(vpp_smooth > vpp_thresh)[0]

    if len(active_cols) == 0:
        return 0, w

    x0 = int(active_cols[0])
    x1 = int(active_cols[-1]) + 1

    # Safety margin: expand slightly (1.5% width) without crossing page boundaries
    safety_pad = int(0.015 * w)
    x0 = max(0, x0 - safety_pad)
    x1 = min(w, x1 + safety_pad)

    return x0, x1


def detect_line_peaks_and_valleys(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> tuple[list[int], list[int], tuple[int, int, int, int]]:
    """Detect candidate text-line centers (peaks) and inter-line whitespace valleys.

    Returns:
        (peaks, boundaries, (block_x0, block_y0, block_x1, block_y1))
    """
    bin_img, _ = _extract_foreground_mask(img)
    h, w = bin_img.shape

    if h < config.min_line_height or w < 20:
        return [], [], (0, 0, w, h)

    # Exclude extreme outer margins to prevent border/scanner noise
    margin_y = max(2, int(h * config.margin_filter_ratio))
    margin_x = max(2, int(w * config.margin_filter_ratio))
    masked_bin = bin_img.copy()
    masked_bin[:margin_y, :] = 0
    masked_bin[h - margin_y :, :] = 0
    masked_bin[:, :margin_x] = 0
    masked_bin[:, w - margin_x :] = 0

    block_x0, block_x1 = _detect_text_block_horizontal_range(masked_bin, config)

    # Compute horizontal projection profile inside core text block
    text_bin = masked_bin[:, block_x0:block_x1]
    hpp = np.sum(text_bin == 255, axis=1).astype(np.float32)

    if np.max(hpp) == 0:
        return [], [], (block_x0, 0, block_x1, h)

    # Pass 1: Scale-adaptive coarse smoothing
    sigma1 = max(3.0, h / 350.0)
    ksize1 = int(sigma1 * 6) | 1
    hpp_s1 = cv2.GaussianBlur(hpp[:, None], (1, ksize1), sigma1).flatten()

    min_dist1 = max(8, int(h / 70.0))
    max_h1 = float(np.max(hpp_s1))
    peaks1, _ = find_peaks(
        hpp_s1,
        height=max_h1 * config.peak_height_ratio,
        distance=min_dist1,
        prominence=max_h1 * config.peak_prominence_ratio,
    )

    if len(peaks1) == 0:
        return [], [], (block_x0, 0, block_x1, h)

    if len(peaks1) >= 2:
        med_spacing = float(np.median(np.diff(peaks1)))
    else:
        med_spacing = max(16.0, h / 25.0)

    # Pass 2: Fine-tuned smoothing based on detected median spacing
    sigma2 = max(2.0, med_spacing / 12.0)
    ksize2 = int(sigma2 * 6) | 1
    hpp_s2 = cv2.GaussianBlur(hpp[:, None], (1, ksize2), sigma2).flatten()

    min_dist2 = max(8, int(med_spacing * 0.45))
    max_h2 = float(np.max(hpp_s2))
    peaks2, _ = find_peaks(
        hpp_s2,
        height=max_h2 * config.peak_height_ratio,
        distance=min_dist2,
        prominence=max_h2 * config.peak_prominence_ratio,
    )

    peaks = [int(p) for p in (peaks2 if len(peaks2) > 0 else peaks1)]

    # Valley detection between adjacent peaks using lightly smoothed HPP
    hpp_valley = cv2.GaussianBlur(hpp[:, None], (1, 9), 1.5).flatten()

    boundaries: list[int] = []

    # 1. Top boundary above first peak
    p0 = peaks[0]
    top_search_limit = max(0, p0 - int(med_spacing * 1.2))
    top_slice = hpp_valley[top_search_limit:p0]
    if len(top_slice) > 0:
        b0 = top_search_limit + int(np.argmin(top_slice))
    else:
        b0 = max(0, p0 - int(med_spacing * 0.5))
    boundaries.append(int(b0))

    # 2. Valley between every adjacent pair of line peaks
    for i in range(len(peaks) - 1):
        p_curr = peaks[i]
        p_next = peaks[i + 1]
        inter_slice = hpp_valley[p_curr:p_next]
        v = p_curr + int(np.argmin(inter_slice))
        boundaries.append(int(v))

    # 3. Bottom boundary below final peak
    plast = peaks[-1]
    bot_search_limit = min(h, plast + int(med_spacing * 1.2))
    bot_slice = hpp_valley[plast:bot_search_limit]
    if len(bot_slice) > 0:
        blast = plast + int(np.argmin(bot_slice))
    else:
        blast = min(h, plast + int(med_spacing * 0.5))
    boundaries.append(int(blast))

    block_y0 = boundaries[0]
    block_y1 = boundaries[-1]

    return peaks, boundaries, (block_x0, block_y0, block_x1, block_y1)


def detect_text_lines(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> list[tuple[int, int, int, int]]:
    """Detect contiguous, valley-to-valley text lines in a manuscript image.

    Returns:
        List of (y_start, y_end, x_start, x_end) line bounds in top-to-bottom reading order.
        Adjacent line slices share valley boundaries so there is NO overlap between crops.
    """
    peaks, boundaries, (block_x0, _, block_x1, _) = detect_line_peaks_and_valleys(
        img, config
    )

    if not peaks or len(boundaries) < 2:
        return []

    lines: list[tuple[int, int, int, int]] = []
    for i in range(len(boundaries) - 1):
        y0 = boundaries[i]
        y1 = boundaries[i + 1]
        if y1 > y0:
            lines.append((y0, y1, block_x0, block_x1))

    return lines


def crop_text_lines(
    img: Image.Image,
    detected_lines: list[tuple[int, int, int, int]],
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> list[Image.Image]:
    """Crop detected text lines from the image using the valley-bounded text region."""
    if not detected_lines:
        return []

    w, h = img.size
    line_crops: list[Image.Image] = []

    for y0, y1, x0, x1 in detected_lines:
        safe_x0 = max(0, min(w, x0))
        safe_x1 = max(safe_x0 + 1, min(w, x1))
        safe_y0 = max(0, min(h, y0))
        safe_y1 = max(safe_y0 + 1, min(h, y1))

        crop = img.crop((safe_x0, safe_y0, safe_x1, safe_y1))
        line_crops.append(crop)

    return line_crops


def build_segmented_ocr_page(
    line_crops: list[Image.Image],
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
    mode: str = "RGB",
    line_peaks: list[int] | None = None,
    scale_factor: int = 1,
) -> Image.Image:
    """Reconstruct line crops into ONE single clean synthetic OCR image.

    Preserves top-to-bottom reading order, controlled inter-line gaps,
    and natural paragraph gaps, scaling canvas layout when line crops are upscaled.
    """
    if not line_crops:
        raise ValueError("Cannot build synthetic OCR page from empty line crops.")

    max_line_w = max(crop.size[0] for crop in line_crops)
    n_lines = len(line_crops)
    scale = max(1, scale_factor)

    base_gap = int(config.line_spacing * scale)
    margin_h = int(config.horizontal_margin * scale)
    margin_v = int(config.vertical_margin * scale)

    # Compute inter-line gaps, preserving detected paragraph breaks
    line_gaps: list[int] = []
    if line_peaks and len(line_peaks) >= 2 and config.preserve_paragraph_gaps:
        peak_diffs = np.diff(line_peaks)
        med_dist = float(np.median(peak_diffs))
        for d in peak_diffs:
            if d > config.paragraph_gap_multiplier * med_dist:
                extra_gap = int((d - med_dist) * scale)
                line_gaps.append(base_gap + extra_gap)
            else:
                line_gaps.append(base_gap)
    else:
        line_gaps = [base_gap] * max(0, n_lines - 1)

    total_lines_h = sum(crop.size[1] for crop in line_crops)
    total_gaps_h = sum(line_gaps)

    canvas_w = max_line_w + (2 * margin_h)
    canvas_h = (2 * margin_v) + total_lines_h + total_gaps_h

    bg_color = (
        (config.background_color, config.background_color, config.background_color)
        if mode == "RGB"
        else config.background_color
    )
    canvas = Image.new(mode, (canvas_w, canvas_h), color=bg_color)

    cur_y = margin_v
    for i, crop in enumerate(line_crops):
        cw, ch = crop.size
        canvas.paste(crop, (margin_h, cur_y))
        cur_y += ch
        if i < len(line_gaps):
            cur_y += line_gaps[i]

    return canvas


def generate_segmentation_debug_overlay(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> Image.Image:
    """Generate a visual debugging image showing detected text block, line centers, and valley boundaries."""
    if isinstance(img, Image.Image):
        raw_arr = np.array(img.convert("RGB"))
    else:
        raw_arr = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

    h, w = raw_arr.shape[:2]
    peaks, boundaries, (bx0, by0, bx1, by1) = detect_line_peaks_and_valleys(
        img, config
    )

    overlay = raw_arr.copy()

    # 1. Draw text block boundary in orange
    cv2.rectangle(overlay, (bx0, by0), (bx1, by1), (255, 140, 0), 2)

    # 2. Draw line center peaks in green (shirorekha headline centers)
    for idx, p in enumerate(peaks):
        cv2.line(overlay, (bx0, p), (bx1, p), (0, 180, 0), 2)
        label = f"L{idx+1} (Y={p})"
        cv2.putText(
            overlay,
            label,
            (bx0 + 15, max(15, p - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 140, 0),
            2,
        )

    # 3. Draw valley crop boundaries in red
    for idx, b in enumerate(boundaries):
        cv2.line(overlay, (0, b), (w, b), (220, 30, 30), 2)
        label = f"B{idx} (Y={b})"
        cv2.putText(
            overlay,
            label,
            (max(10, w - 180), max(15, b - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (200, 20, 20),
            2,
        )

    return Image.fromarray(overlay)


def segment_and_reconstruct_image(
    img: Image.Image,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
    upscale_factor: int = 1,
) -> tuple[Image.Image, LineDetectionStats]:
    """Complete end-to-end pipeline: detect line peaks, find valleys, crop lines, and build ONE synthetic page.

    When upscale_factor > 1, upscales each line crop individually before synthetic page reconstruction.
    If 0 lines are detected or detection fails, gracefully returns the original (optionally upscaled) image.
    """
    stats = LineDetectionStats(original_size=img.size)
    stats.upscale_enabled = bool(upscale_factor > 1)
    stats.upscale_factor = max(1, upscale_factor)
    t0 = time.perf_counter()

    try:
        peaks, boundaries, text_block = detect_line_peaks_and_valleys(img, config=config)
        stats.line_peaks = peaks
        stats.line_boundaries = boundaries
        stats.text_block = text_block
        stats.lines_detected = len(peaks)

        if not peaks or len(boundaries) < 2:
            logger.info("No text lines detected; falling back to full enhanced image.")
            stats.fallback_used = True
            if upscale_factor > 1:
                from kalanjiyam.utils.image_preprocessing import upscale_image

                fallback_img = upscale_image(img, factor=upscale_factor)
            else:
                fallback_img = img
            stats.reconstructed_size = fallback_img.size
            stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
            return fallback_img, stats

        detected_lines: list[tuple[int, int, int, int]] = []
        bx0, _, bx1, _ = text_block
        for i in range(len(boundaries) - 1):
            y0 = boundaries[i]
            y1 = boundaries[i + 1]
            if y1 > y0:
                detected_lines.append((y0, y1, bx0, bx1))

        stats.line_heights = [y1 - y0 for y0, y1, _, _ in detected_lines]
        crops = crop_text_lines(img, detected_lines, config=config)

        if not crops:
            stats.fallback_used = True
            if upscale_factor > 1:
                from kalanjiyam.utils.image_preprocessing import upscale_image

                fallback_img = upscale_image(img, factor=upscale_factor)
            else:
                fallback_img = img
            stats.reconstructed_size = fallback_img.size
            stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
            return fallback_img, stats

        if upscale_factor > 1:
            from kalanjiyam.utils.image_preprocessing import upscale_image

            crops = [upscale_image(c, factor=upscale_factor) for c in crops]

        reconstructed = build_segmented_ocr_page(
            crops,
            config=config,
            mode=img.mode,
            line_peaks=peaks,
            scale_factor=upscale_factor,
        )
        stats.reconstructed_size = reconstructed.size
        stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0

        logger.info(
            "Line segmentation complete: %d lines detected (upscale=%dx), original=%s, reconstructed=%s in %.2fms",
            stats.lines_detected,
            upscale_factor,
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
        if upscale_factor > 1:
            from kalanjiyam.utils.image_preprocessing import upscale_image

            fallback_img = upscale_image(img, factor=upscale_factor)
        else:
            fallback_img = img
        stats.reconstructed_size = fallback_img.size
        stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
        return fallback_img, stats
