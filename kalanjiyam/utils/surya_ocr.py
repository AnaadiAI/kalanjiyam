"""Surya OCR utilities for proofing projects."""

import logging
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Any

from PIL import Image

from kalanjiyam.utils import google_ocr

# Use the OcrResponse from google_ocr as the common interface
OcrResponse = google_ocr.OcrResponse


def post_process(text: str) -> str:
    """Post process OCR text."""
    return (
        text
        # Danda and double danda
        .replace("||", "॥")
        .replace("|", "।")
        .replace("।।", "॥")
        # Remove curly quotes
        .replace("'", "'")
        .replace("'", "'")
        .replace(""", '"')
        .replace(""", '"')
    )


def serialize_bounding_boxes(boxes: List[Tuple[int, int, int, int, str]]) -> str:
    """Serialize bounding boxes to string format."""
    return "\n".join("\t".join(str(x) for x in row) for row in boxes)


def run(file_path: Path, language: str = 'sa') -> OcrResponse:
    """Run Surya OCR over the given image.

    :param file_path: path to the image we'll process with OCR.
    :param language: language code for OCR (default: 'sa' for Sanskrit).
    :return: an OCR response containing the image's text content and
        bounding boxes.
    """
    logging.debug(f"Starting Surya OCR: {file_path} with language {language}")

    try:
        # Try to import Surya OCR
        try:
            from surya.recognition import RecognitionPredictor
            from surya.foundation import FoundationPredictor
            from surya.detection import DetectionPredictor
            import sys
            logging.info(f"Surya OCR imported successfully. Python executable: {sys.executable}")
        except ImportError as e:
            import sys
            logging.error(f"Failed to import Surya OCR. Python executable: {sys.executable}")
            logging.error(f"Import error: {e}")
            raise RuntimeError(
                f"Surya OCR is not installed in the current Python environment.\n"
                f"Python executable: {sys.executable}\n"
                f"Please install it with: pip install surya-ocr\n"
                f"For more information, see: https://github.com/datalab-to/surya"
            )
        
        # Initialize Surya predictors
        foundation_predictor = FoundationPredictor()
        detection_predictor = DetectionPredictor(foundation_predictor)
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        
        # Load and process the image
        from PIL import Image
        image = Image.open(file_path)
        
        # Run OCR using Surya's Python API
        # Note: Surya automatically detects languages, so we don't need to specify language
        ocr_results = recognition_predictor(
            [image],
            task_names=['recognition'],
            det_predictor=detection_predictor,
            return_words=True
        )
        
        # Extract text content and bounding boxes
        text_content = ""
        bounding_boxes = []
        
        if ocr_results and len(ocr_results) > 0:
            ocr_result = ocr_results[0]  # Get the first result
            
            # Extract text content
            if hasattr(ocr_result, 'text') and ocr_result.text:
                text_content = ocr_result.text
                text_content = post_process(text_content)
            
            # Extract bounding boxes from words
            if hasattr(ocr_result, 'words') and ocr_result.words:
                for word in ocr_result.words:
                    if hasattr(word, 'bbox') and hasattr(word, 'text'):
                        bbox = word.bbox
                        text = word.text
                        # Convert bbox format to our format (x1, y1, x2, y2)
                        if len(bbox) >= 4:
                            x1, y1, x2, y2 = bbox[:4]
                            bounding_boxes.append((x1, y1, x2, y2, text))
        
        return OcrResponse(text_content=text_content, bounding_boxes=bounding_boxes)
        
    except RuntimeError:
        # Re-raise RuntimeError (installation error)
        raise
    except Exception as e:
        logging.error(f"Surya OCR failed with unexpected error: {e}")
        raise RuntimeError(f"Surya OCR failed: {e}")


def run_with_selection(file_path: Path, selection: dict, language: str = 'sa') -> OcrResponse:
    """Run Surya OCR on a specific selection of the image.

    :param file_path: path to the image we'll process with OCR.
    :param selection: dictionary with 'left', 'top', 'width', 'height' keys.
    :param language: language code for OCR (default: 'sa' for Sanskrit).
    :return: an OCR response containing the image's text content and
        bounding boxes.
    """
    logging.debug(f"Starting Surya OCR on selection: {file_path} with language {language}")
    
    # Crop the image to the selection
    image = Image.open(file_path)
    left, top, width, height = selection['left'], selection['top'], selection['width'], selection['height']
    selection_image = image.crop((left, top, left + width, top + height))
    
    # Save the cropped image temporarily
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
        selection_image.save(tmp_file.name, 'JPEG')
        tmp_path = Path(tmp_file.name)
    
    try:
        return run(tmp_path, language=language)
    finally:
        # Clean up temporary file
        tmp_path.unlink(missing_ok=True)
