"""Unified OCR engine interface for proofing projects."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from kalanjiyam.utils import google_ocr, tesseract_ocr


# Use the OcrResponse from google_ocr as the common interface
OcrResponse = google_ocr.OcrResponse


class OcrEngine(ABC):
    """Abstract base class for OCR engines."""
    
    @abstractmethod
    def run(self, file_path: Path, **kwargs) -> OcrResponse:
        """Run OCR on the given image file."""
        pass
    
    @abstractmethod
    def run_with_selection(self, file_path: Path, selection: Dict[str, int], **kwargs) -> OcrResponse:
        """Run OCR on a specific selection of the image."""
        pass


class GoogleOcrEngine(OcrEngine):
    """Google Cloud Vision OCR engine."""
    
    def run(self, file_path: Path, **kwargs) -> OcrResponse:
        """Run Google OCR on the given image file."""
        return google_ocr.run(file_path)
    
    def run_with_selection(self, file_path: Path, selection: Dict[str, int], **kwargs) -> OcrResponse:
        """Run Google OCR on a specific selection of the image."""
        # Google OCR doesn't have built-in selection support, so we'll crop the image
        from PIL import Image
        image = Image.open(file_path)
        left, top, width, height = selection['left'], selection['top'], selection['width'], selection['height']
        selection_image = image.crop((left, top, left + width, top + height))
        
        # Save the cropped image temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            selection_image.save(tmp_file.name, 'JPEG')
            tmp_path = Path(tmp_file.name)
        
        try:
            return google_ocr.run(tmp_path)
        finally:
            # Clean up temporary file
            tmp_path.unlink(missing_ok=True)


class TesseractOcrEngine(OcrEngine):
    """Tesseract OCR engine."""
    
    def run(self, file_path: Path, **kwargs) -> OcrResponse:
        """Run Tesseract OCR on the given image file."""
        language = kwargs.get('language', 'eng')
        return tesseract_ocr.run(file_path, language=language)
    
    def run_with_selection(self, file_path: Path, selection: Dict[str, int], **kwargs) -> OcrResponse:
        """Run Tesseract OCR on a specific selection of the image."""
        language = kwargs.get('language', 'eng')
        return tesseract_ocr.run_with_selection(file_path, selection, language=language)


class OcrEngineFactory:
    """Factory for creating OCR engines."""
    
    _engines = {
        'google': GoogleOcrEngine,
        'tesseract': TesseractOcrEngine,
    }
    
    @classmethod
    def create(cls, engine_name: str) -> OcrEngine:
        """Create an OCR engine instance.
        
        :param engine_name: Name of the engine ('google' or 'tesseract')
        :return: OCR engine instance
        :raises: ValueError if engine name is not supported
        """
        if engine_name not in cls._engines:
            raise ValueError(f"Unsupported OCR engine: {engine_name}. Supported engines: {list(cls._engines.keys())}")
        
        return cls._engines[engine_name]()
    
    @classmethod
    def get_supported_engines(cls) -> List[str]:
        """Get list of supported OCR engines."""
        return list(cls._engines.keys())


def run_ocr(file_path: Path, engine_name: str = 'google', **kwargs) -> OcrResponse:
    """Run OCR using the specified engine.
    
    :param file_path: Path to the image file
    :param engine_name: Name of the OCR engine ('google' or 'tesseract')
    :param kwargs: Additional arguments for the OCR engine
    :return: OCR response
    """
    engine = OcrEngineFactory.create(engine_name)
    return engine.run(file_path, **kwargs)


def run_ocr_with_selection(file_path: Path, selection: Dict[str, int], engine_name: str = 'google', **kwargs) -> OcrResponse:
    """Run OCR on a selection using the specified engine.
    
    :param file_path: Path to the image file
    :param selection: Selection dictionary with 'left', 'top', 'width', 'height' keys
    :param engine_name: Name of the OCR engine ('google' or 'tesseract')
    :param kwargs: Additional arguments for the OCR engine
    :return: OCR response
    """
    engine = OcrEngineFactory.create(engine_name)
    return engine.run_with_selection(file_path, selection, **kwargs) 