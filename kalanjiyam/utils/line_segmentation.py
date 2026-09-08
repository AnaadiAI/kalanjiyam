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

# Disable PIL decompression bomb limits for legitimate high-resolution/upscaled historical manuscripts
Image.MAX_IMAGE_PIXELS = None

logger = logging.getLogger(__name__)

LINE_SEGMENTATION_VERSION = "2.0"


@dataclass
class BoundaryDecision:
    """Record of a content-aware boundary placement decision."""

    boundary_index: int
    initial_boundary: int
    final_boundary: int
    ink_density_at_boundary: int
    whitespace_window_score: int
    moved: bool
    movement_distance: int
    reason: str


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

    # Content-aware boundary parameters
    padding_px: int = 4
    safety_window_k: int = 2
    min_component_area: int = 4
    max_above_ratio: float = 0.55
    max_below_ratio: float = 0.85
    noise_pixel_threshold: int = 0
    tight_crops: bool = False
    debug_mode: bool = False


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
    boundary_decisions: list[BoundaryDecision] = field(default_factory=list)
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

    # Lightly smoothed HPP for initial candidate valley search
    hpp_valley = cv2.GaussianBlur(hpp[:, None], (1, 9), 1.5).flatten()

    safe_boundaries, initial_valleys, decisions = find_safe_boundaries(
        bin_img, peaks, block_x0, block_x1, hpp_valley, med_spacing, config=config
    )

    block_y0 = safe_boundaries[0] if safe_boundaries else 0
    block_y1 = safe_boundaries[-1] if safe_boundaries else h

    return peaks, safe_boundaries, initial_valleys, (block_x0, block_y0, block_x1, block_y1), decisions


def find_safe_boundaries(
    bin_img: np.ndarray,
    peaks: list[int],
    block_x0: int,
    block_x1: int,
    hpp_valley: np.ndarray,
    med_spacing: float,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> tuple[list[int], list[int], list[BoundaryDecision]]:
    """Determine content-aware safe boundaries between lines.

    Analyzes connected component bounding boxes, row foreground occupancy, and local window ink
    around initial projection valleys to navigate around vertically extending Devanagari matras,
    modifiers, and conjuncts, placing boundaries squarely in genuine whitespace bands.

    Returns:
        (safe_boundaries, initial_valleys, boundary_decisions)
    """
    h, w = bin_img.shape
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        bin_img, connectivity=8
    )

    # Extract connected components with area >= min_component_area overlapping the horizontal text block
    components: list[tuple[int, int, int, int, int]] = []
    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area < config.min_component_area:
            continue
        cx = int(stats[lbl, cv2.CC_STAT_LEFT])
        cw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        cy = int(stats[lbl, cv2.CC_STAT_TOP])
        ch = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        if (cx + cw) < block_x0 or cx > block_x1:
            continue
        components.append((cy, cy + ch, cx, cw, area))

    # Row-wise foreground ink count inside text block
    row_ink = np.sum(bin_img[:, block_x0:block_x1] == 255, axis=1).astype(np.int32)

    # Number of connected components whose body is strictly sliced by each row y
    components_cut = np.zeros(h, dtype=np.int32)
    for cy_min, cy_max, _, _, _ in components:
        if cy_max - cy_min > 1:
            components_cut[cy_min + 1 : cy_max] += 1

    # Local window ink occupancy around row y: [y - k, y + k]
    k = max(1, config.safety_window_k)
    window_ink = np.zeros(h, dtype=np.int32)
    for y in range(h):
        y_lo = max(0, y - k)
        y_hi = min(h, y + k + 1)
        window_ink[y] = int(np.sum(row_ink[y_lo:y_hi]))

    safe_boundaries: list[int] = []
    initial_valleys: list[int] = []
    boundary_decisions: list[BoundaryDecision] = []

    # 1. Top Boundary B_0 (above first line peak)
    p0 = peaks[0]
    top_search_limit = max(0, p0 - int(med_spacing * 1.5))
    top_slice = hpp_valley[top_search_limit:p0]
    if len(top_slice) > 0:
        y_init_0 = top_search_limit + int(np.argmin(top_slice))
    else:
        y_init_0 = max(0, p0 - int(med_spacing * 0.5))
    initial_valleys.append(int(y_init_0))

    # Topmost foreground ink of line 0 within search limit
    ink_above = np.where(
        (row_ink[:p0] > config.noise_pixel_threshold) & (np.arange(p0) >= top_search_limit)
    )[0]
    if len(ink_above) > 0:
        ink_top_0 = int(ink_above[0])
    else:
        ink_top_0 = p0

    b0_candidate = max(0, ink_top_0 - config.padding_px)
    while b0_candidate > 0 and (
        row_ink[b0_candidate] > config.noise_pixel_threshold
        or components_cut[b0_candidate] > 0
    ):
        b0_candidate -= 1
    safe_boundaries.append(int(b0_candidate))

    top_moved = bool(b0_candidate != y_init_0)
    top_dist = int(b0_candidate - y_init_0)
    top_reason = "preserved_valley"
    if top_moved:
        top_reason = (
            "moved_up_to_clear_upper_matras"
            if top_dist < 0
            else "moved_down_to_safe_whitespace"
        )

    boundary_decisions.append(
        BoundaryDecision(
            boundary_index=0,
            initial_boundary=int(y_init_0),
            final_boundary=int(b0_candidate),
            ink_density_at_boundary=int(row_ink[b0_candidate]),
            whitespace_window_score=int(window_ink[b0_candidate]),
            moved=top_moved,
            movement_distance=top_dist,
            reason=top_reason,
        )
    )

    # 2. Inter-Line Boundaries B_1 .. B_{N-1}
    for i in range(len(peaks) - 1):
        p_curr = peaks[i]
        p_next = peaks[i + 1]
        gap = p_next - p_curr

        inter_slice = hpp_valley[p_curr:p_next]
        y_init = p_curr + int(np.argmin(inter_slice))
        initial_valleys.append(int(y_init))

        y_start = p_curr + max(3, int(gap * 0.15))
        y_end = p_next - max(2, int(gap * 0.08))
        if y_start >= y_end:
            y_start = p_curr + 1
            y_end = p_next

        # Detect contiguous clean whitespace bands
        clean_bands: list[tuple[int, int]] = []
        band_start: int | None = None
        for y in range(y_start, y_end):
            if components_cut[y] == 0 and row_ink[y] <= config.noise_pixel_threshold:
                if band_start is None:
                    band_start = y
            else:
                if band_start is not None:
                    clean_bands.append((band_start, y - 1))
                    band_start = None
        if band_start is not None:
            clean_bands.append((band_start, y_end - 1))

        if clean_bands:
            # Score each clean band: prefer wide bands with low window ink, closest to y_init
            best_band = clean_bands[0]
            best_score = -float("inf")
            for b_s, b_e in clean_bands:
                b_mid = (b_s + b_e) // 2
                width = b_e - b_s + 1
                w_ink = window_ink[b_mid]
                dist = abs(b_mid - y_init)
                score = (width * 10.0) - (w_ink * 2.0) - (dist * 0.5)
                if score > best_score:
                    best_score = score
                    best_band = (b_s, b_e)
            y_safe = (best_band[0] + best_band[1]) // 2
            reason = "whitespace_band_center"
        else:
            # Fallback if no 100% zero-ink row exists (e.g. tightly packed touching lines)
            best_y = y_init
            min_cost = float("inf")
            for y in range(y_start, y_end):
                cost = (
                    components_cut[y] * 1000.0
                    + row_ink[y] * 10.0
                    + window_ink[y] * 2.0
                    + abs(y - y_init) * 0.1
                )
                if cost < min_cost:
                    min_cost = cost
                    best_y = y
            y_safe = best_y
            reason = "minimal_cut_cost_fallback"

        moved = bool(y_safe != y_init)
        move_dist = int(y_safe - y_init)
        if moved:
            if row_ink[y_init] > config.noise_pixel_threshold or components_cut[y_init] > 0:
                reason = f"avoided_glyph_ink_at_initial_valley_{y_init}"
            elif move_dist > 0:
                reason = "moved_down_to_safe_whitespace"
            else:
                reason = "moved_up_to_safe_whitespace"
        else:
            reason = "preserved_valley"

        boundary_decisions.append(
            BoundaryDecision(
                boundary_index=i + 1,
                initial_boundary=int(y_init),
                final_boundary=int(y_safe),
                ink_density_at_boundary=int(row_ink[y_safe]),
                whitespace_window_score=int(window_ink[y_safe]),
                moved=moved,
                movement_distance=move_dist,
                reason=reason,
            )
        )
        safe_boundaries.append(int(y_safe))

    # 3. Bottom Boundary B_N (below final line peak)
    plast = peaks[-1]
    bot_search_limit = min(h, plast + int(med_spacing * 1.5))
    bot_slice = hpp_valley[plast:bot_search_limit]
    if len(bot_slice) > 0:
        y_init_last = plast + int(np.argmin(bot_slice))
    else:
        y_init_last = min(h, plast + int(med_spacing * 0.5))
    initial_valleys.append(int(y_init_last))

    # Lowermost foreground ink of final line
    ink_below = np.where(row_ink[plast:bot_search_limit] > config.noise_pixel_threshold)[0]
    if len(ink_below) > 0:
        ink_bot_last = plast + int(ink_below[-1])
    else:
        ink_bot_last = plast

    bn_candidate = min(h, ink_bot_last + config.padding_px + 1)
    while bn_candidate < h and (
        row_ink[bn_candidate] > config.noise_pixel_threshold
        or components_cut[bn_candidate] > 0
    ):
        bn_candidate += 1
    safe_boundaries.append(int(bn_candidate))

    bot_moved = bool(bn_candidate != y_init_last)
    bot_dist = int(bn_candidate - y_init_last)
    bot_reason = "preserved_valley"
    if bot_moved:
        bot_reason = (
            "moved_down_to_clear_lower_matras"
            if bot_dist > 0
            else "moved_up_to_safe_whitespace"
        )

    boundary_decisions.append(
        BoundaryDecision(
            boundary_index=len(peaks),
            initial_boundary=int(y_init_last),
            final_boundary=int(bn_candidate),
            ink_density_at_boundary=int(row_ink[bn_candidate]),
            whitespace_window_score=int(window_ink[bn_candidate]),
            moved=bot_moved,
            movement_distance=bot_dist,
            reason=bot_reason,
        )
    )

    return safe_boundaries, initial_valleys, boundary_decisions


def detect_line_peaks_and_safe_boundaries(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> tuple[
    list[int],
    list[int],
    list[int],
    tuple[int, int, int, int],
    list[BoundaryDecision],
]:
    """Detect candidate text-line centers (peaks) and content-aware safe whitespace boundaries.

    Returns:
        (peaks, safe_boundaries, initial_valleys, (block_x0, block_y0, block_x1, block_y1), decisions)
    """
    bin_img, _ = _extract_foreground_mask(img)
    h, w = bin_img.shape

    if h < config.min_line_height or w < 20:
        return [], [], [], (0, 0, w, h), []

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
        return [], [], [], (block_x0, 0, block_x1, h), []

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
        return [], [], [], (block_x0, 0, block_x1, h), []

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

    # Lightly smoothed HPP for initial candidate valley search
    hpp_valley = cv2.GaussianBlur(hpp[:, None], (1, 9), 1.5).flatten()

    safe_boundaries, initial_valleys, decisions = find_safe_boundaries(
        bin_img, peaks, block_x0, block_x1, hpp_valley, med_spacing, config=config
    )

    block_y0 = safe_boundaries[0] if safe_boundaries else 0
    block_y1 = safe_boundaries[-1] if safe_boundaries else h

    return peaks, safe_boundaries, initial_valleys, (block_x0, block_y0, block_x1, block_y1), decisions


def detect_line_peaks_and_valleys(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> tuple[list[int], list[int], tuple[int, int, int, int]]:
    """Detect candidate text-line centers (peaks) and inter-line whitespace boundaries.

    Returns:
        (peaks, boundaries, (block_x0, block_y0, block_x1, block_y1))
    """
    peaks, boundaries, _, text_block, _ = detect_line_peaks_and_safe_boundaries(
        img, config=config
    )
    return peaks, boundaries, text_block


def detect_text_lines(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> list[tuple[int, int, int, int]]:
    """Detect contiguous, content-aware safe text lines in a manuscript image.

    Returns:
        List of (y_start, y_end, x_start, x_end) line bounds in top-to-bottom reading order.
        Adjacent line slices share safe boundaries so there is NO overlap between crops.
    """
    peaks, boundaries, (block_x0, _, block_x1, _) = detect_line_peaks_and_valleys(
        img, config
    )

    if not peaks or len(boundaries) < 2:
        return []

    lines: list[tuple[int, int, int, int]] = []
    if config.tight_crops:
        bin_img, _ = _extract_foreground_mask(img)
        row_ink = np.sum(bin_img[:, block_x0:block_x1] == 255, axis=1).astype(np.int32)
        for i in range(len(boundaries) - 1):
            b0 = boundaries[i]
            b1 = boundaries[i + 1]
            if b1 <= b0:
                continue
            active = np.where(row_ink[b0:b1] > config.noise_pixel_threshold)[0]
            if len(active) > 0:
                ink_top = b0 + int(active[0])
                ink_bot = b0 + int(active[-1])
                safe_y0 = max(b0, ink_top - config.padding_px)
                safe_y1 = min(b1, ink_bot + config.padding_px + 1)
            else:
                safe_y0, safe_y1 = b0, b1
            lines.append((safe_y0, safe_y1, block_x0, block_x1))
    else:
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
    scale = max(1, int(scale_factor) if scale_factor else 1)

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

    assert canvas_w > 0, f"Invalid canvas width calculated: {canvas_w}"
    assert canvas_h > 0, f"Invalid canvas height calculated: {canvas_h}"

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

    assert canvas.width == canvas_w, f"Canvas width mismatch: {canvas.width} != {canvas_w}"
    assert canvas.height == canvas_h, f"Canvas height mismatch: {canvas.height} != {canvas_h}"
    return canvas


def generate_segmentation_debug_overlay(
    img: Image.Image | np.ndarray,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
) -> Image.Image:
    """Generate a visual debugging image showing detected text block, line centers, initial valleys, safe boundaries, and crops."""
    if isinstance(img, Image.Image):
        raw_arr = np.array(img.convert("RGB"))
    else:
        raw_arr = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

    h, w = raw_arr.shape[:2]
    peaks, safe_boundaries, initial_valleys, (bx0, by0, bx1, by1), decisions = (
        detect_line_peaks_and_safe_boundaries(img, config)
    )

    overlay = raw_arr.copy()

    # 1. Draw text block boundary in orange
    cv2.rectangle(overlay, (bx0, by0), (bx1, by1), (255, 140, 0), 2)

    # 2. Draw initial candidate valleys in gold / yellow
    for idx, v in enumerate(initial_valleys):
        cv2.line(overlay, (bx0, v), (bx1, v), (0, 215, 255), 1)
        lbl = f"Init B{idx} (Y={v})"
        cv2.putText(
            overlay,
            lbl,
            (bx0 + 5, max(12, v - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (0, 180, 220),
            1,
        )

    # 3. Draw line center peaks in green (shirorekha headline centers)
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

    # 4. Draw final safe boundaries in red
    for idx, b in enumerate(safe_boundaries):
        cv2.line(overlay, (0, b), (w, b), (220, 30, 30), 2)
        dec = decisions[idx] if idx < len(decisions) else None
        if dec and dec.moved:
            label = f"Safe B{idx} (Y={b}, moved {dec.movement_distance:+d}px)"
        else:
            label = f"Safe B{idx} (Y={b})"
        cv2.putText(
            overlay,
            label,
            (max(10, w - 240), max(15, b - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (200, 20, 20),
            2,
        )

    # 5. Draw final line crop bounding boxes in cyan
    detected_lines = detect_text_lines(img, config=config)
    for idx, (y0, y1, lx0, lx1) in enumerate(detected_lines):
        cv2.rectangle(overlay, (lx0, y0), (lx1, y1), (200, 160, 0), 1)

    return Image.fromarray(overlay)


def segment_and_reconstruct_image(
    img: Image.Image,
    config: LineSegmentationConfig = DEFAULT_LINE_SEGMENTATION_CONFIG,
    upscale_factor: int = 1,
) -> tuple[Image.Image, LineDetectionStats]:
    """Complete end-to-end pipeline: detect line peaks, find safe boundaries, crop lines, and build ONE synthetic page.

    When upscale_factor > 1, upscales each line crop individually before synthetic page reconstruction.
    If 0 lines are detected or detection fails, gracefully returns the original (optionally upscaled) image.
    """
    scale_int = int(upscale_factor) if upscale_factor else 1
    stats = LineDetectionStats(original_size=img.size)
    stats.upscale_enabled = bool(scale_int > 1)
    stats.upscale_factor = max(1, scale_int)
    t0 = time.perf_counter()

    try:
        peaks, boundaries, initial_valleys, text_block, decisions = (
            detect_line_peaks_and_safe_boundaries(img, config=config)
        )
        stats.line_peaks = peaks
        stats.line_boundaries = boundaries
        stats.boundary_decisions = decisions
        stats.text_block = text_block
        stats.lines_detected = len(peaks)

        if not peaks or len(boundaries) < 2:
            logger.info("No text lines detected; falling back to full enhanced image.")
            stats.fallback_used = True
            if scale_int > 1:
                from kalanjiyam.utils.image_preprocessing import upscale_image

                fallback_img = upscale_image(img, factor=scale_int)
            else:
                fallback_img = img
            stats.reconstructed_size = fallback_img.size
            stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
            return fallback_img, stats

        # Log boundary movements and metrics
        for dec in decisions:
            if dec.moved or config.debug_mode:
                logger.info(
                    "Boundary %d: initial=%d, final=%d, moved=%s (%+dpx), reason=%s, ink_density=%d, window_score=%d",
                    dec.boundary_index,
                    dec.initial_boundary,
                    dec.final_boundary,
                    dec.moved,
                    dec.movement_distance,
                    dec.reason,
                    dec.ink_density_at_boundary,
                    dec.whitespace_window_score,
                )

        detected_lines = detect_text_lines(img, config=config)
        stats.line_heights = [y1 - y0 for y0, y1, _, _ in detected_lines]
        crops = crop_text_lines(img, detected_lines, config=config)

        if not crops:
            stats.fallback_used = True
            if scale_int > 1:
                from kalanjiyam.utils.image_preprocessing import upscale_image

                fallback_img = upscale_image(img, factor=scale_int)
            else:
                fallback_img = img
            stats.reconstructed_size = fallback_img.size
            stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
            return fallback_img, stats

        if scale_int > 1:
            from kalanjiyam.utils.image_preprocessing import upscale_image

            crops = [upscale_image(c, factor=scale_int) for c in crops]

        for idx, c in enumerate(crops):
            assert c.width > 0, f"Line crop {idx+1} width must be > 0"
            assert c.height > 0, f"Line crop {idx+1} height must be > 0"

        reconstructed = build_segmented_ocr_page(
            crops,
            config=config,
            mode=img.mode,
            line_peaks=peaks,
            scale_factor=scale_int,
        )
        assert reconstructed.width > 0, f"Reconstructed image width must be > 0 (got {reconstructed.width})"
        assert reconstructed.height > 0, f"Reconstructed image height must be > 0 (got {reconstructed.height})"

        stats.reconstructed_size = reconstructed.size
        stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0

        logger.info(
            "Line segmentation complete: %d lines detected (upscale=%dx), original=%s, reconstructed=%s in %.2fms",
            stats.lines_detected,
            scale_int,
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
        if scale_int > 1:
            from kalanjiyam.utils.image_preprocessing import upscale_image

            fallback_img = upscale_image(img, factor=scale_int)
        else:
            fallback_img = img
        stats.reconstructed_size = fallback_img.size
        stats.segmentation_latency_ms = (time.perf_counter() - t0) * 1000.0
        return fallback_img, stats
