#!/usr/bin/env python3
"""Test script for the fixed Surya OCR implementation."""

import sys
import os
from pathlib import Path

def test_surya_imports():
    """Test if all required Surya modules can be imported."""
    try:
        from surya.detection import DetectionPredictor
        from surya.layout import LayoutPredictor
        from surya.recognition import RecognitionPredictor
        from surya.table_rec import TableRecPredictor
        from surya.foundation import FoundationPredictor
        from surya.common.surya.schema import TaskNames
        print("✓ All Surya modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Surya import failed: {e}")
        return False

def test_surya_initialization():
    """Test if Surya predictors can be initialized."""
    try:
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        from surya.layout import LayoutPredictor
        from surya.recognition import RecognitionPredictor
        from surya.table_rec import TableRecPredictor
        
        print("Initializing Surya predictors...")
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        layout_predictor = LayoutPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        table_rec_predictor = TableRecPredictor()
        
        print("✓ All Surya predictors initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Surya initialization failed: {e}")
        return False

def test_surya_ocr_simple():
    """Test simple OCR functionality."""
    try:
        from PIL import Image
        import numpy as np
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor
        from surya.common.surya.schema import TaskNames
        
        # Create a simple test image with text
        test_image = Image.new('RGB', (400, 100), color='white')
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(test_image)
        
        # Try to use a default font, fallback to basic if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        draw.text((10, 10), "Hello World", fill='black', font=font)
        
        print("Running simple OCR test...")
        
        # Initialize predictors
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        
        # Run OCR
        predictions = rec_predictor(
            [test_image],
            task_names=[TaskNames.ocr_with_boxes],
            det_predictor=det_predictor,
            highres_images=[test_image],
            math_mode=True
        )
        
        if predictions and len(predictions) > 0:
            prediction = predictions[0]
            print(f"✓ OCR completed successfully")
            print(f"Number of text lines detected: {len(prediction.text_lines) if hasattr(prediction, 'text_lines') else 0}")
            return True
        else:
            print("❌ No OCR results generated")
            return False
            
    except Exception as e:
        print(f"❌ Simple OCR test failed: {e}")
        return False

def test_surya_ocr_with_real_image():
    """Test OCR with a real image if available."""
    image_path = Path("data/file-uploads/projects/myabstract/pages/1.jpg")
    
    if not image_path.exists():
        print(f"⚠️  Test image not found: {image_path}")
        print("Skipping real image test")
        return True
    
    try:
        from PIL import Image
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor
        from surya.common.surya.schema import TaskNames
        
        print(f"Testing with real image: {image_path}")
        
        # Load image
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Initialize predictors
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        
        # Run OCR
        predictions = rec_predictor(
            [image],
            task_names=[TaskNames.ocr_with_boxes],
            det_predictor=det_predictor,
            highres_images=[image],
            math_mode=True
        )
        
        if predictions and len(predictions) > 0:
            prediction = predictions[0]
            print(f"✓ Real image OCR completed successfully")
            print(f"Number of text lines detected: {len(prediction.text_lines) if hasattr(prediction, 'text_lines') else 0}")
            
            # Print first few text lines if available
            if hasattr(prediction, 'text_lines') and prediction.text_lines:
                print("First few text lines:")
                for i, line in enumerate(prediction.text_lines[:3]):
                    print(f"  {i+1}: {line.text[:50]}...")
            
            return True
        else:
            print("❌ No OCR results generated for real image")
            return False
            
    except Exception as e:
        print(f"❌ Real image OCR test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Surya OCR Fixed Implementation Test")
    print("=" * 40)
    
    tests = [
        test_surya_imports,
        test_surya_initialization,
        test_surya_ocr_simple,
        test_surya_ocr_with_real_image,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if test():
            passed += 1
        print()
    
    print("=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Surya OCR is working correctly.")
    else:
        print("❌ Some tests failed. Please check the error messages above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
