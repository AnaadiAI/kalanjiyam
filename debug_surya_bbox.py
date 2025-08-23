#!/usr/bin/env python3
"""Debug script to understand Surya OCR output structure."""

import sys
from PIL import Image, ImageDraw, ImageFont

def debug_surya_output():
    """Debug the Surya OCR output structure."""
    try:
        from surya.foundation import FoundationPredictor
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor
        from surya.common.surya.schema import TaskNames
        
        # Create a simple test image
        test_image = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(test_image)
        font = ImageFont.load_default()
        draw.text((10, 10), 'Hello World', fill='black', font=font)
        
        print("Initializing Surya predictors...")
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
        
        print("Running OCR...")
        predictions = rec_predictor(
            [test_image],
            task_names=[TaskNames.ocr_with_boxes],
            det_predictor=det_predictor,
            highres_images=[test_image],
            math_mode=True
        )
        
        prediction = predictions[0]
        print(f"Prediction type: {type(prediction)}")
        print(f"Text lines type: {type(prediction.text_lines)}")
        print(f"Number of text lines: {len(prediction.text_lines)}")
        
        if prediction.text_lines:
            line = prediction.text_lines[0]
            print(f"Line type: {type(line)}")
            print(f"Line attributes: {dir(line)}")
            print(f"Has bbox attribute: {hasattr(line, 'bbox')}")
            
            if hasattr(line, 'bbox'):
                print(f"Bbox type: {type(line.bbox)}")
                print(f"Bbox value: {line.bbox}")
                
                # Check if bbox is a list/tuple or something else
                if hasattr(line.bbox, '__iter__') and not isinstance(line.bbox, (str, bytes)):
                    print(f"Bbox is iterable with length: {len(line.bbox)}")
                    if len(line.bbox) > 0:
                        print(f"First element type: {type(line.bbox[0])}")
                        print(f"First element: {line.bbox[0]}")
                else:
                    print("Bbox is not iterable or is a string/bytes")
            
            # Check for other possible bounding box attributes
            for attr in dir(line):
                if 'bbox' in attr.lower() or 'box' in attr.lower() or 'coord' in attr.lower():
                    try:
                        value = getattr(line, attr)
                        print(f"Attribute {attr}: {type(value)} = {value}")
                    except Exception as e:
                        print(f"Attribute {attr}: Error accessing - {e}")
        
        return True
        
    except Exception as e:
        print(f"Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_surya_output()
    sys.exit(0 if success else 1)
