#!/usr/bin/env python3
"""Minimal test to check Surya OCR with the problematic image."""

import sys
from pathlib import Path

def test_image_file():
    """Test if the image file can be processed."""
    image_path = Path("data/file-uploads/projects/myabstract/pages/1.jpg")
    
    print(f"Testing image file: {image_path}")
    print(f"File exists: {image_path.exists()}")
    print(f"File size: {image_path.stat().st_size if image_path.exists() else 'N/A'} bytes")
    
    if not image_path.exists():
        print("❌ Image file does not exist")
        return False
    
    # Test PIL
    try:
        from PIL import Image
        img = Image.open(image_path)
        print(f"✓ PIL can open image: {img.size}, mode: {img.mode}")
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
            print(f"✓ Converted to RGB: {img.size}, mode: {img.mode}")
        
        return True
    except Exception as e:
        print(f"❌ PIL failed to open image: {e}")
        return False

def test_surya_basic():
    """Test basic Surya functionality."""
    try:
        from surya.recognition import RecognitionPredictor
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        print("✓ Surya modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Surya import failed: {e}")
        return False

def test_surya_with_image():
    """Test Surya with the actual image."""
    image_path = Path("data/file-uploads/projects/myabstract/pages/1.jpg")
    
    if not image_path.exists():
        print("❌ Image file not found")
        return False
    
    try:
        from PIL import Image
        from surya.recognition import RecognitionPredictor
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        
        print("Loading image...")
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        print("Initializing Surya predictors...")
        foundation_predictor = FoundationPredictor()
        detection_predictor = DetectionPredictor(foundation_predictor)
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        
        print("Running OCR...")
        ocr_results = recognition_predictor(
            [image],
            task_names=['recognition'],
            det_predictor=detection_predictor,
            return_words=True
        )
        
        print(f"✓ Surya OCR completed successfully")
        print(f"Results: {len(ocr_results) if ocr_results else 0} result(s)")
        
        if ocr_results and len(ocr_results) > 0:
            result = ocr_results[0]
            if hasattr(result, 'text') and result.text:
                print(f"Text length: {len(result.text)} characters")
                print(f"First 100 chars: {result.text[:100]}...")
            else:
                print("No text extracted")
        
        return True
        
    except Exception as e:
        print(f"❌ Surya OCR failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Minimal Surya OCR Test")
    print("=" * 30)
    
    tests = [
        test_image_file,
        test_surya_basic,
        test_surya_with_image,
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
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
