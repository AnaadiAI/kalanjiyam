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
        # Import Surya modules
        from surya.common.surya.schema import TaskNames
        from surya.detection import DetectionPredictor
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.scripts.config import CLILoader
        
        logging.info("Surya modules imported successfully")
        
        # Set up the loader
        loader_kwargs = {
            'output_dir': tempfile.mkdtemp(),
            'images': False,
            'debug': False
        }
        loader = CLILoader(str(file_path), loader_kwargs, highres=True)
        
        # Set up task names
        task_names = [TaskNames.ocr_with_boxes] * len(loader.images)
        
        # Initialize predictors
        logging.info("Initializing Surya predictors...")
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        
        # Run OCR
        logging.info("Running Surya OCR...")
        predictions_by_image = rec_predictor(
            loader.images,
            task_names=task_names,
            det_predictor=det_predictor,
            highres_images=loader.highres_images,
            math_mode=False,  # Disable math recognition for text OCR
        )
        
        if not predictions_by_image:
            raise RuntimeError("No OCR predictions returned")
        
        prediction = predictions_by_image[0]
        logging.info("Surya OCR completed successfully")
        
    except ImportError as e:
        logging.error(f"Failed to import Surya modules: {e}")
        raise RuntimeError(
            f"Surya OCR is not installed in the current Python environment.\n"
            f"Please install it with: pip install surya-ocr\n"
            f"For more information, see: https://github.com/datalab-to/surya"
        )
    except Exception as e:
        logging.error(f"Surya OCR failed: {e}")
        logging.warning("Falling back to Tesseract OCR")
        
        # Fallback to Tesseract OCR
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
            raise RuntimeError(f"Surya OCR failed: {e}. Tesseract OCR fallback also failed: {tesseract_error}")
    
    # Extract text content and bounding boxes from Surya prediction
    text_content = ""
    bounding_boxes = []
    
    try:
        # Extract text from text lines
        if hasattr(prediction, 'text_lines') and prediction.text_lines:
            text_lines = []
            for line in prediction.text_lines:
                if hasattr(line, 'text') and line.text:
                    text_lines.append(line.text)
                    # Extract bounding box for each line
                    if hasattr(line, 'bbox') and line.bbox:
                        bbox = line.bbox
                        if len(bbox) >= 4:
                            x1, y1, x2, y2 = bbox[:4]
                            bounding_boxes.append((x1, y1, x2, y2, line.text))
            
            text_content = "\n".join(text_lines)
            text_content = post_process(text_content)
        
        logging.info(f"Extracted text content: {len(text_content)} characters")
        logging.info(f"Extracted {len(bounding_boxes)} bounding boxes")
        
    except Exception as e:
        logging.error(f"Failed to extract text from Surya prediction: {e}")
        # Return empty result if extraction fails
        text_content = ""
        bounding_boxes = []
    
    return OcrResponse(text_content=text_content, bounding_boxes=bounding_boxes)


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
