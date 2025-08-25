#!/usr/bin/env python3

from config import create_config_only_app
from kalanjiyam.utils.translation_engine import translate_text, TranslationEngineFactory

app = create_config_only_app('development')

with app.app_context():
    # Test text
    test_text = "Hello, this is a test message."
    
    print("Testing translation engine...")
    print(f"Original text: {test_text}")
    
    try:
        # Test Google Translate
        print("\n--- Testing Google Translate ---")
        result = translate_text(test_text, 'en', 'te', 'google')
        print(f"Translated text: {result.translated_text}")
        print(f"Source: {result.source_language}")
        print(f"Target: {result.target_language}")
        print(f"Engine: {result.engine}")
        
        # Test with a different language pair
        print("\n--- Testing English to Hindi ---")
        result2 = translate_text(test_text, 'en', 'hi', 'google')
        print(f"Translated text: {result2.translated_text}")
        
        # Test with Sanskrit to English
        print("\n--- Testing Sanskrit to English ---")
        sanskrit_text = "नमस्ते"
        result3 = translate_text(sanskrit_text, 'sa', 'en', 'google')
        print(f"Original: {sanskrit_text}")
        print(f"Translated: {result3.translated_text}")
        
    except Exception as e:
        print(f"Translation failed: {e}")
        import traceback
        traceback.print_exc()
