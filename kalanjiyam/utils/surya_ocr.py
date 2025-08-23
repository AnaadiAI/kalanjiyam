"""Surya OCR utilities for proofing projects."""
import logging
import subprocess
import tempfile
import json
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image

from kalanjiyam.utils import google_ocr
OcrResponse = google_ocr.OcrResponse


def post_process(text: str) -> str:
    """Post-process OCR text."""
    if not text:
        return ""
    
    # Clean up common OCR artifacts
    text = text.strip()
    # Remove excessive whitespace
    text = ' '.join(text.split())
    return text


def serialize_bounding_boxes(boxes: List[Tuple[int, int, int, int, str]]) -> str:
    """Serialize bounding boxes to JSON string."""
    return json.dumps([{
        'x1': box[0], 'y1': box[1], 'x2': box[2], 'y2': box[3], 'text': box[4]
    } for box in boxes])


def run(file_path: Path, language: str = 'sa', additional_languages: Optional[List[str]] = None) -> OcrResponse:
    """
    Run Surya OCR on the given image file.
    
    Args:
        file_path: Path to the image file
        language: Primary language code (e.g., 'sa', 'en', 'hi')
        additional_languages: Optional list of additional language codes for bilingual/multilingual OCR
    
    Returns:
        OcrResponse with text content and bounding boxes
    """
    logging.debug(f"Starting Surya OCR: {file_path} with language {language}")
    
    if not file_path.exists():
        raise RuntimeError(f"File does not exist: {file_path}")
    
    if not file_path.is_file():
        raise RuntimeError(f"Path is not a file: {file_path}")
    
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise RuntimeError(f"File is empty: {file_path}")
    
    logging.info(f"Processing image file: {file_path}, size: {file_size} bytes")
    
    try:
        # Import Surya modules
        from surya.common.surya.schema import TaskNames
        from surya.detection import DetectionPredictor
        from surya.debug.text import draw_text_on_image
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.scripts.config import CLILoader
        
        # Load image
        image = Image.open(file_path)
        image = image.convert('RGB')
        
        # Set up the loader
        loader_kwargs = {
            'output_dir': tempfile.mkdtemp(),
            'images': False,
            'debug': False
        }
        loader = CLILoader(str(file_path), loader_kwargs, highres=True)
        
        # Initialize predictors
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        
        # Set task names for OCR with bounding boxes
        task_names = [TaskNames.ocr_with_boxes] * len(loader.images)
        
        # Run OCR
        logging.info("Running Surya OCR with automatic language detection")
        predictions_by_image = rec_predictor(
            loader.images,
            task_names=task_names,
            det_predictor=det_predictor,
            highres_images=loader.highres_images,
            math_mode=True,  # Enable math recognition
        )
        
        # Extract text and bounding boxes from the first image result
        if not predictions_by_image:
            raise RuntimeError("No OCR results generated")
        
        prediction = predictions_by_image[0]
        text_content = ""
        bounding_boxes = []
        
        # Extract text lines and their bounding boxes
        for line in prediction.text_lines:
            line_text = post_process(line.text)
            if line_text:
                text_content += line_text + "\n"
                
                # Convert polygon to bounding box format (x1, y1, x2, y2)
                if hasattr(line, 'bbox') and line.bbox:
                    bbox = line.bbox
                    if len(bbox) >= 4:
                        # Convert from polygon format to bounding box
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        x1, x2 = min(x_coords), max(x_coords)
                        y1, y2 = min(y_coords), max(y_coords)
                        bounding_boxes.append((x1, y1, x2, y2, line_text))
        
        text_content = text_content.strip()
        logging.info(f"Surya OCR completed successfully. Extracted {len(bounding_boxes)} text lines")
        
    except ImportError as e:
        import sys
        raise RuntimeError(
            f"Surya OCR is not installed in the current Python environment.\n"
            f"Python executable: {sys.executable}\n"
            f"Please install it with: pip install surya-ocr\n"
            f"For more information, see: https://github.com/datalab-to/surya\n"
            f"Import error: {e}"
        )
    except Exception as e:
        logging.error(f"Surya OCR failed: {e}")
        logging.warning("Falling back to Tesseract OCR")
        
        # Fallback to Tesseract OCR
        try:
            from kalanjiyam.utils import tesseract_ocr
            return tesseract_ocr.run(file_path, language=language)
        except Exception as fallback_error:
            logging.error(f"Tesseract fallback also failed: {fallback_error}")
            raise RuntimeError(f"Surya OCR failed: {e}. Fallback to Tesseract also failed: {fallback_error}")
    
    return OcrResponse(text_content=text_content, bounding_boxes=bounding_boxes)


def run_with_selection(file_path: Path, selection: dict, language: str = 'sa', additional_languages: Optional[List[str]] = None) -> OcrResponse:
    """
    Run Surya OCR on a specific selection of the image.
    
    Args:
        file_path: Path to the image file
        selection: Dictionary with 'x1', 'y1', 'x2', 'y2' coordinates
        language: Primary language code
        additional_languages: Optional list of additional language codes
    
    Returns:
        OcrResponse with text content and bounding boxes
    """
    logging.debug(f"Starting Surya OCR with selection: {file_path}")
    
    if not file_path.exists():
        raise RuntimeError(f"File does not exist: {file_path}")
    
    try:
        # Load image and crop to selection
        image = Image.open(file_path)
        image = image.convert('RGB')
        
        # Crop to selection area
        x1 = selection.get('x1', 0)
        y1 = selection.get('y1', 0)
        x2 = selection.get('x2', image.width)
        y2 = selection.get('y2', image.height)
        
        cropped_image = image.crop((x1, y1, x2, y2))
        
        # Save cropped image to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            cropped_image.save(temp_file.name)
            temp_path = Path(temp_file.name)
        
        try:
            # Run OCR on cropped image
            result = run(temp_path, language=language, additional_languages=additional_languages)
            
            # Adjust bounding box coordinates back to original image
            adjusted_boxes = []
            for box in result.bounding_boxes:
                adjusted_boxes.append((
                    box[0] + x1,  # x1
                    box[1] + y1,  # y1
                    box[2] + x1,  # x2
                    box[3] + y1,  # y2
                    box[4]        # text
                ))
            
            return OcrResponse(text_content=result.text_content, bounding_boxes=adjusted_boxes)
            
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
                
    except Exception as e:
        logging.error(f"Surya OCR with selection failed: {e}")
        raise RuntimeError(f"Surya OCR with selection failed: {e}")


def get_supported_languages() -> List[str]:
    """Get supported language codes for Surya OCR."""
    # Surya supports 90+ languages automatically
    # Return common language codes that users might want to specify
    return [
        'sa', 'en', 'hi', 'te', 'mr', 'bn', 'gu', 'kn', 'ml', 'ta', 'pa', 'or', 'ur',
        'ar', 'fa', 'th', 'ko', 'ja', 'zh', 'ru', 'es', 'fr', 'de', 'it', 'pt', 'nl',
        'pl', 'tr', 'vi', 'id', 'ms'
    ]
