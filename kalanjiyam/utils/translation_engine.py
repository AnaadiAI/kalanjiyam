"""Unified translation engine interface for proofing projects."""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path

# Translation response data structure
@dataclass
class TranslationResponse:
    """Response from a translation engine."""
    #: The translated text content.
    translated_text: str
    #: Source language code.
    source_language: str
    #: Target language code.
    target_language: str
    #: Translation engine used.
    engine: str
    #: Additional metadata from the translation engine.
    metadata: Optional[Dict[str, Any]] = None


class TranslationEngine(ABC):
    """Abstract base class for translation engines."""
    
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str, **kwargs) -> TranslationResponse:
        """Translate the given text from source to target language."""
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass


class GoogleTranslateEngine(TranslationEngine):
    """Google Translate engine implementation."""
    
    def __init__(self):
        try:
            from googletrans import Translator
            self.translator = Translator()
            self._supported_languages = None
        except ImportError:
            raise ImportError("googletrans library is required for Google Translate. Install with: pip install googletrans==4.0.0rc1")
    
    def translate(self, text: str, source_lang: str, target_lang: str, **kwargs) -> TranslationResponse:
        """Translate text using Google Translate."""
        try:
            # Clean and segment text
            segments = self._segment_text(text)
            translated_segments = []
            
            for segment in segments:
                if segment.strip():
                    result = self.translator.translate(
                        segment, 
                        src=source_lang, 
                        dest=target_lang
                    )
                    translated_segments.append(result.text)
                else:
                    translated_segments.append(segment)
            
            translated_text = '\n'.join(translated_segments)
            
            return TranslationResponse(
                translated_text=translated_text,
                source_language=source_lang,
                target_language=target_lang,
                engine='google',
                metadata={'confidence': getattr(result, 'confidence', None)}
            )
        except Exception as e:
            logging.error(f"Google Translate failed: {e}")
            raise
    
    def get_supported_languages(self) -> List[str]:
        """Get supported language codes."""
        if self._supported_languages is None:
            try:
                self._supported_languages = list(self.translator.get_supported_languages().keys())
            except:
                # Fallback to common languages
                self._supported_languages = ['en', 'hi', 'sa', 'te', 'mr', 'fr', 'de', 'es']
        return self._supported_languages
    
    def _segment_text(self, text: str) -> List[str]:
        """Segment text into sentences or paragraphs for translation."""
        # Split by double newlines (paragraphs)
        paragraphs = text.split('\n\n')
        segments = []
        
        for paragraph in paragraphs:
            if paragraph.strip():
                # Split by single newlines and punctuation
                sentences = re.split(r'(?<=[.!?।॥])\s+', paragraph)
                segments.extend(sentences)
            else:
                segments.append(paragraph)
        
        return segments


class OpenAITranslateEngine(TranslationEngine):
    """OpenAI GPT-based translation engine."""
    
    def __init__(self, api_key: Optional[str] = None):
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai library is required. Install with: pip install openai")
    
    def translate(self, text: str, source_lang: str, target_lang: str, **kwargs) -> TranslationResponse:
        """Translate text using OpenAI GPT."""
        try:
            # Create a prompt for translation
            prompt = f"""Translate the following text from {source_lang} to {target_lang}. 
            Maintain the original formatting, line breaks, and structure.
            Only provide the translation, no explanations.
            
            Text to translate:
            {text}"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Provide accurate translations while preserving formatting."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            translated_text = response.choices[0].message.content.strip()
            
            return TranslationResponse(
                translated_text=translated_text,
                source_language=source_lang,
                target_language=target_lang,
                engine='openai',
                metadata={'model': 'gpt-3.5-turbo', 'usage': response.usage}
            )
        except Exception as e:
            logging.error(f"OpenAI translation failed: {e}")
            raise
    
    def get_supported_languages(self) -> List[str]:
        """Get supported language codes."""
        return ['en', 'hi', 'sa', 'te', 'mr', 'fr', 'de', 'es', 'ja', 'ko', 'zh']


class TranslationEngineFactory:
    """Factory for creating translation engines."""
    
    _engines = {
        'google': GoogleTranslateEngine,
        'openai': OpenAITranslateEngine,
    }
    
    @classmethod
    def create(cls, engine_name: str, **kwargs) -> TranslationEngine:
        """Create a translation engine instance.
        
        :param engine_name: Name of the engine ('google' or 'openai')
        :param kwargs: Additional arguments for the engine
        :return: Translation engine instance
        :raises: ValueError if engine name is not supported
        """
        if engine_name not in cls._engines:
            raise ValueError(f"Unsupported translation engine: {engine_name}. Supported engines: {list(cls._engines.keys())}")
        
        return cls._engines[engine_name](**kwargs)
    
    @classmethod
    def get_supported_engines(cls) -> List[str]:
        """Get list of supported translation engines."""
        return list(cls._engines.keys())


def translate_text(text: str, source_lang: str, target_lang: str, engine_name: str = 'google', **kwargs) -> TranslationResponse:
    """Convenience function to translate text using the specified engine.
    
    :param text: Text to translate
    :param source_lang: Source language code
    :param target_lang: Target language code
    :param engine_name: Translation engine to use
    :param kwargs: Additional arguments for the engine
    :return: Translation response
    """
    engine = TranslationEngineFactory.create(engine_name, **kwargs)
    return engine.translate(text, source_lang, target_lang, **kwargs)


def segment_text_for_translation(text: str, max_length: int = 1000) -> List[str]:
    """Segment text into chunks suitable for translation.
    
    :param text: Text to segment
    :param max_length: Maximum length of each segment
    :return: List of text segments
    """
    if len(text) <= max_length:
        return [text]
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    segments = []
    current_segment = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed max_length, start a new segment
        if len(current_segment) + len(paragraph) + 2 > max_length:  # +2 for '\n\n'
            if current_segment:
                segments.append(current_segment.strip())
                current_segment = ""
            
            # If a single paragraph is too long, split it by sentences
            if len(paragraph) > max_length:
                sentences = re.split(r'(?<=[.!?।॥])\s+', paragraph)
                for sentence in sentences:
                    if len(current_segment) + len(sentence) > max_length:
                        if current_segment:
                            segments.append(current_segment.strip())
                            current_segment = ""
                        # If a single sentence is too long, split it by words
                        if len(sentence) > max_length:
                            words = sentence.split()
                            for word in words:
                                if len(current_segment) + len(word) + 1 > max_length:
                                    if current_segment:
                                        segments.append(current_segment.strip())
                                        current_segment = ""
                                current_segment += word + " "
                        else:
                            current_segment += sentence + " "
                    else:
                        current_segment += sentence + " "
            else:
                current_segment = paragraph + '\n\n'
        else:
            current_segment += paragraph + '\n\n'
    
    if current_segment:
        segments.append(current_segment.strip())
    
    return segments 