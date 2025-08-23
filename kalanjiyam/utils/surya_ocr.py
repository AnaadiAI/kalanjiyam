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

    # Check if file exists and is readable
    if not file_path.exists():
        raise RuntimeError(f"Image file does not exist: {file_path}")
    
    if not file_path.is_file():
        raise RuntimeError(f"Path is not a file: {file_path}")
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise RuntimeError(f"Image file is empty: {file_path}")
    
    logging.info(f"Processing image file: {file_path}, size: {file_size} bytes")

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
        try:
            foundation_predictor = FoundationPredictor()
            detection_predictor = DetectionPredictor(foundation_predictor)
            recognition_predictor = RecognitionPredictor(foundation_predictor)
        except Exception as e:
            logging.error(f"Surya model initialization failed: {e}")
            logging.warning("Falling back to Google OCR due to Surya model failure")
            
            # Fallback to Google OCR first, then Tesseract
            try:
                from kalanjiyam.utils import google_ocr
                return google_ocr.run(file_path, language=language)
            except Exception as google_error:
                logging.warning(f"Google OCR fallback failed: {google_error}")
                logging.warning("Falling back to Tesseract OCR")
                
                try:
                    from kalanjiyam.utils import tesseract_ocr
                    # Convert language code from Google format to Tesseract format
                    tesseract_lang = language
                    if language == 'sa':
                        tesseract_lang = 'san'
                    elif language == 'en':
                        tesseract_lang = 'eng'
                    elif language == 'hi':
                        tesseract_lang = 'hin'
                    elif language == 'te':
                        tesseract_lang = 'tel'
                    elif language == 'mr':
                        tesseract_lang = 'mar'
                    elif language == 'bn':
                        tesseract_lang = 'ben'
                    elif language == 'gu':
                        tesseract_lang = 'guj'
                    elif language == 'kn':
                        tesseract_lang = 'kan'
                    elif language == 'ml':
                        tesseract_lang = 'mal'
                    elif language == 'ta':
                        tesseract_lang = 'tam'
                    elif language == 'pa':
                        tesseract_lang = 'pan'
                    elif language == 'or':
                        tesseract_lang = 'ori'
                    elif language == 'ur':
                        tesseract_lang = 'urd'
                    
                    return tesseract_ocr.run(file_path, language=tesseract_lang)
                except Exception as tesseract_error:
                    logging.error(f"Tesseract OCR fallback also failed: {tesseract_error}")
                    raise RuntimeError(
                        f"Surya model initialization failed: {e}. "
                        f"Google OCR fallback failed: {google_error}. "
                        f"Tesseract OCR fallback failed: {tesseract_error}"
                    )
        
        # Load and process the image
        from PIL import Image
        import numpy as np
        
        try:
            image = Image.open(file_path)
            
            # Convert to RGB if necessary (Surya expects RGB images)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Ensure the image is properly loaded
            if image.size[0] == 0 or image.size[1] == 0:
                raise ValueError("Image has zero dimensions")
            
            logging.info(f"Loaded image: {image.size}, mode: {image.mode}")
            
        except Exception as e:
            logging.error(f"Failed to load image {file_path}: {e}")
            raise RuntimeError(f"Failed to load image: {e}")
        
        # Run OCR using Surya's Python API
        # Note: Surya automatically detects languages, so we don't need to specify language
        try:
            ocr_results = recognition_predictor(
                [image],
                task_names=['recognition'],
                det_predictor=detection_predictor,
                return_words=True
            )
        except Exception as e:
            logging.error(f"Surya OCR processing failed: {e}")
            logging.warning("Falling back to Google OCR due to Surya failure")
            
            # Fallback to Google OCR
            try:
                from kalanjiyam.utils import google_ocr
                return google_ocr.run(file_path, language=language)
            except Exception as fallback_error:
                logging.error(f"Google OCR fallback also failed: {fallback_error}")
                raise RuntimeError(f"Surya OCR failed: {e}. Google OCR fallback also failed: {fallback_error}")
        
        # Extract text content and bounding boxes
        text_content = ""
        bounding_boxes = []
        
        if ocr_results and len(ocr_results) > 0:
            ocr_result = ocr_results[0]  # Get the first result
            
            # Extract text content
            if hasattr(ocr_result, 'text') and ocr_result.text:
                text_content = ocr_result.text
                text_content = post_process(text_content)
                logging.info(f"Extracted text content: {len(text_content)} characters")
            
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
                
                logging.info(f"Extracted {len(bounding_boxes)} bounding boxes")
        else:
            logging.warning("No OCR results returned from Surya")
        
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
