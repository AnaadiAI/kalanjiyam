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
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass


class GoogleOcrEngine(OcrEngine):
    """Google Cloud Vision OCR engine."""
    
    def run(self, file_path: Path, **kwargs) -> OcrResponse:
        """Run Google OCR on the given image file."""
        language = kwargs.get('language', 'sa')  # Default to Sanskrit
        return google_ocr.run(file_path, language=language)
    
    def run_with_selection(self, file_path: Path, selection: Dict[str, int], **kwargs) -> OcrResponse:
        """Run Google OCR on a specific selection of the image."""
        language = kwargs.get('language', 'sa')  # Default to Sanskrit
        return google_ocr.run_with_selection(file_path, selection, language=language)
    
    def get_supported_languages(self) -> List[str]:
        """Get supported language codes for Google OCR."""
        # Google Cloud Vision supports many languages, but we'll focus on the most relevant ones
        return ['sa', 'en', 'hi', 'te', 'mr', 'bn', 'gu', 'kn', 'ml', 'ta', 'pa', 'or', 'ur']


class TesseractOcrEngine(OcrEngine):
    """Tesseract OCR engine."""
    
    def run(self, file_path: Path, **kwargs) -> OcrResponse:
        """Run Tesseract OCR on the given image file."""
        language = kwargs.get('language', 'san')  # Default to Sanskrit
        return tesseract_ocr.run(file_path, language=language)
    
    def run_with_selection(self, file_path: Path, selection: Dict[str, int], **kwargs) -> OcrResponse:
        """Run Tesseract OCR on a specific selection of the image."""
        language = kwargs.get('language', 'san')  # Default to Sanskrit
        return tesseract_ocr.run_with_selection(file_path, selection, language=language)
    
    def get_supported_languages(self) -> List[str]:
        """Get supported language codes for Tesseract OCR."""
        # Tesseract language codes (these need to be installed)
        return ['san', 'eng', 'hin', 'tel', 'mar', 'ben', 'guj', 'kan', 'mal', 'tam', 'pan', 'ori', 'urd']


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
    
    @classmethod
    def get_supported_languages(cls, engine_name: str) -> List[str]:
        """Get supported languages for a specific engine."""
        if engine_name not in cls._engines:
            raise ValueError(f"Unsupported OCR engine: {engine_name}")
        
        engine = cls._engines[engine_name]()
        return engine.get_supported_languages()


def run_ocr(file_path: Path, engine_name: str = 'google', **kwargs) -> OcrResponse:
    """Run OCR on the given image file using the specified engine.
    
    :param file_path: Path to the image file
    :param engine_name: Name of the OCR engine ('google' or 'tesseract')
    :param kwargs: Additional arguments including 'language'
    :return: OCR response with text content and bounding boxes
    """
    engine = OcrEngineFactory.create(engine_name)
    return engine.run(file_path, **kwargs) 