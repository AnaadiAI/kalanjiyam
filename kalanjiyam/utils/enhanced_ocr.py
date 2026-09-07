"""Enhanced OCR runner — applies image enhancement profile before running OCR."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from kalanjiyam.utils.image_preprocessing import (
    SUPPORTED_ENHANCEMENT_PROFILES,
    preprocess_image_to_tempfile,
    validate_enhancement_profile,
)
from kalanjiyam.utils.ocr_runner import run_ocr
from kalanjiyam.utils.ocr_types import (
    SUPPORTED_ENGINES,
    OcrResponse,
    engine_for_service,
    normalize_engine,
)

logger = logging.getLogger(__name__)

ENHANCEMENT_VERSION = "1.0"

__all__ = [
    "ENHANCEMENT_VERSION",
    "SUPPORTED_ENHANCEMENT_PROFILES",
    "run_enhanced_ocr",
]


def run_enhanced_ocr(
    file_path: Path | str,
    engine_name: str,
    profile: str = "document_cleanup",
    language: str = "sa",
    gpu_config=None,
    line_segmentation: bool = False,
    segmentation_config=None,
    upscale: bool = False,
    upscale_factor: int = 2,
) -> OcrResponse:
    """Run Enhanced OCR pipeline on an input page image.

    1. Validates source image path, engine, and enhancement profile.
    2. Applies the requested preprocessing profile.
    3. If line_segmentation is enabled, segments tightly-packed text lines and
       reconstructs them into ONE synthetic page before OCR (with optional upscaling).
    4. If upscale is enabled (and line_segmentation is False), upscales the enhanced page.
    5. Executes OCR via run_ocr() with EXACTLY ONE API invocation.
    6. Stamps enhanced OCR metadata (ocr_mode, enhancement_profile, line_segmentation, upscale, upscale_factor).
    7. Preserves coordinate space and document structures.
    """
    del gpu_config

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Source image not found: {path}")

    # Validate enhancement profile
    valid_profile = validate_enhancement_profile(profile)

    # Validate engine
    normalized_engine = normalize_engine(engine_name)
    if normalized_engine not in SUPPORTED_ENGINES:
        raise ValueError(
            f"Unsupported OCR engine: {engine_name!r}. Supported engines: {SUPPORTED_ENGINES}"
        )

    t0_prep = time.time()
    logger.info(
        "Starting Enhanced OCR for %s: engine=%s, profile=%s, line_segmentation=%s, upscale=%s (factor=%sx), language=%s",
        path.name,
        normalized_engine,
        valid_profile,
        line_segmentation,
        upscale,
        upscale_factor,
        language,
    )

    with preprocess_image_to_tempfile(
        path,
        valid_profile,
        line_segmentation=line_segmentation,
        segmentation_config=segmentation_config,
        upscale=upscale,
        upscale_factor=upscale_factor,
    ) as preprocessed_path:
        prep_latency_ms = round((time.time() - t0_prep) * 1000, 2)

        # Execute OCR using the existing OCR infrastructure (EXACTLY ONE API CALL)
        ocr_response = run_ocr(
            preprocessed_path,
            engine_name=normalized_engine,
            language=language,
        )

    # Stamp enhanced OCR provenance and metadata
    ocr_response.ocr_mode = "enhanced"
    ocr_response.enhancement_version = ENHANCEMENT_VERSION
    ocr_response.enhancement_profile = valid_profile
    ocr_response.preprocessing_latency_ms = prep_latency_ms
    ocr_response.engine = normalized_engine
    ocr_response.line_segmentation = bool(line_segmentation)
    ocr_response.upscale = bool(upscale)
    ocr_response.upscale_factor = int(upscale_factor) if upscale else 1

    if line_segmentation:
        from kalanjiyam.utils.line_segmentation import LINE_SEGMENTATION_VERSION

        ocr_response.line_segmentation_version = LINE_SEGMENTATION_VERSION

    if not ocr_response.contract_version:
        ocr_response.contract_version = "2.2"

    if ocr_response.model is None:
        ocr_response.model = {
            "name": engine_for_service(normalized_engine),
            "version": "1.0.0",
        }

    logger.info(
        "Enhanced OCR completed for %s: engine=%s, profile=%s, line_segmentation=%s, upscale=%s (%dx), prep_latency=%.2fms, engine_latency=%.2fms",
        path.name,
        normalized_engine,
        valid_profile,
        line_segmentation,
        upscale,
        upscale_factor,
        prep_latency_ms,
        ocr_response.engine_latency_ms or 0.0,
    )

    return ocr_response
