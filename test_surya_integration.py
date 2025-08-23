#!/usr/bin/env python3
"""Test script to verify Surya OCR integration with Kalanjiyam."""

import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def test_surya_ocr_engine():
    """Test Surya OCR through the Kalanjiyam OCR engine interface."""
    try:
        from kalanjiyam.utils.ocr_engine import OcrEngineFactory
        
        print("Testing Surya OCR engine creation...")
        surya_engine = OcrEngineFactory.create('surya')
        print("✓ Surya OCR engine created successfully")
        
        # Create a test image
        test_image = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(test_image)
        font = ImageFont.load_default()
        draw.text((10, 10), 'Hello World', fill='black', font=font)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            test_image.save(temp_file.name)
            temp_path = Path(temp_file.name)
        
        try:
            print("Testing Surya OCR on test image...")
            result = surya_engine.run(temp_path, language='en')
            
            print(f"✓ OCR completed successfully")
            print(f"Text content: {result.text_content}")
            print(f"Number of bounding boxes: {len(result.bounding_boxes)}")
            
            if result.bounding_boxes:
                print("First bounding box:", result.bounding_boxes[0])
            
            return True
            
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
                
    except Exception as e:
        print(f"❌ Surya OCR engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_surya_direct():
    """Test Surya OCR directly."""
    try:
        from kalanjiyam.utils import surya_ocr
        
        print("Testing Surya OCR directly...")
        
        # Create a test image
        test_image = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(test_image)
        font = ImageFont.load_default()
        draw.text((10, 10), 'Hello World', fill='black', font=font)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            test_image.save(temp_file.name)
            temp_path = Path(temp_file.name)
        
        try:
            result = surya_ocr.run(temp_path, language='en')
            
            print(f"✓ Direct OCR completed successfully")
            print(f"Text content: {result.text_content}")
            print(f"Number of bounding boxes: {len(result.bounding_boxes)}")
            
            if result.bounding_boxes:
                print("First bounding box:", result.bounding_boxes[0])
            
            return True
            
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
                
    except Exception as e:
        print(f"❌ Direct Surya OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all integration tests."""
    print("Surya OCR Integration Test")
    print("=" * 30)
    
    tests = [
        test_surya_ocr_engine,
        test_surya_direct,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if test():
            passed += 1
        print()
    
    print("=" * 30)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All integration tests passed! Surya OCR is working with Kalanjiyam.")
    else:
        print("❌ Some integration tests failed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
