#!/usr/bin/env python3
"""
Test script for Surya OCR GPU configuration.
This script helps you test different GPU configurations and verify they work correctly.
"""

import os
import sys
import argparse
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import time

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kalanjiyam.utils.surya_gpu_config import (
    get_default_gpu_config,
    get_gpu_config_from_env,
    get_multi_gpu_config,
    get_cpu_config,
    validate_gpu_config,
    print_gpu_config,
    EXAMPLE_CONFIGS
)
from kalanjiyam.utils.surya_ocr import get_gpu_config, setup_gpu_environment


def create_test_image(output_path: Path, text: str = "Test OCR Image") -> None:
    """Create a test image for OCR testing."""
    # Create a simple test image
    width, height = 800, 400
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Try to use a default font, fallback to basic if not available
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    # Draw text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=font)
    
    # Save the image
    image.save(output_path)
    print(f"Created test image: {output_path}")


def test_gpu_config(config: dict, test_image_path: Path) -> dict:
    """Test a GPU configuration with Surya OCR."""
    print(f"\n{'='*50}")
    print(f"Testing GPU Configuration:")
    print_gpu_config(config)
    print(f"{'='*50}")
    
    # Setup GPU environment
    setup_gpu_environment(config)
    
    # Test GPU detection
    try:
        import torch
        if torch.cuda.is_available():
            print(f"CUDA available: Yes")
            print(f"CUDA device count: {torch.cuda.device_count()}")
            if config['device'].startswith('cuda'):
                device_id = int(config['device'].split(':')[1]) if ':' in config['device'] else 0
                if device_id < torch.cuda.device_count():
                    print(f"Selected GPU: {torch.cuda.get_device_name(device_id)}")
                    print(f"GPU memory: {torch.cuda.get_device_properties(device_id).total_memory / 1024**3:.1f} GB")
                else:
                    print(f"Warning: GPU {device_id} not available")
        else:
            print(f"CUDA available: No")
    except ImportError:
        print("PyTorch not available")
    
    # Test Surya OCR
    try:
        from kalanjiyam.utils.surya_ocr import run
        
        start_time = time.time()
        result = run(test_image_path, language='en', gpu_config=config)
        end_time = time.time()
        
        print(f"\nOCR Results:")
        print(f"  Processing time: {end_time - start_time:.2f} seconds")
        print(f"  Extracted text: '{result.text_content.strip()}'")
        print(f"  Bounding boxes: {len(result.bounding_boxes)}")
        
        return {
            'success': True,
            'processing_time': end_time - start_time,
            'text_length': len(result.text_content),
            'bbox_count': len(result.bounding_boxes)
        }
        
    except Exception as e:
        print(f"OCR failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def list_available_gpus():
    """List available GPUs on the system."""
    try:
        import torch
        if torch.cuda.is_available():
            print(f"Available GPUs:")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"  GPU {i}: {props.name}")
                print(f"    Memory: {props.total_memory / 1024**3:.1f} GB")
                print(f"    Compute Capability: {props.major}.{props.minor}")
        else:
            print("No CUDA GPUs available")
    except ImportError:
        print("PyTorch not available - cannot detect GPUs")


def main():
    parser = argparse.ArgumentParser(description="Test Surya OCR GPU configuration")
    parser.add_argument('--config', choices=list(EXAMPLE_CONFIGS.keys()) + ['env', 'default', 'cpu'], 
                       default='default', help='GPU configuration to test')
    parser.add_argument('--device', help='Specific GPU device (e.g., cuda:0, cuda:1)')
    parser.add_argument('--memory-fraction', type=float, help='GPU memory fraction (0.0-1.0)')
    parser.add_argument('--list-gpus', action='store_true', help='List available GPUs')
    parser.add_argument('--test-image', type=Path, help='Path to test image (will create one if not provided)')
    
    args = parser.parse_args()
    
    if args.list_gpus:
        list_available_gpus()
        return
    
    # Create test image if not provided
    if args.test_image and args.test_image.exists():
        test_image_path = args.test_image
    else:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            test_image_path = Path(tmp_file.name)
            create_test_image(test_image_path)
    
    try:
        # Get configuration
        if args.config == 'env':
            config = get_gpu_config_from_env()
        elif args.config == 'default':
            config = get_default_gpu_config()
        elif args.config == 'cpu':
            config = get_cpu_config()
        else:
            config = EXAMPLE_CONFIGS[args.config].copy()
        
        # Override with command line arguments
        if args.device:
            config['device'] = args.device
        if args.memory_fraction is not None:
            config['memory_fraction'] = args.memory_fraction
        
        # Validate configuration
        if not validate_gpu_config(config):
            print("Error: Invalid GPU configuration")
            return 1
        
        # Test the configuration
        result = test_gpu_config(config, test_image_path)
        
        if result['success']:
            print(f"\n✅ Configuration test successful!")
            print(f"   Processing time: {result['processing_time']:.2f}s")
            print(f"   Text extracted: {result['text_length']} characters")
            print(f"   Bounding boxes: {result['bbox_count']}")
        else:
            print(f"\n❌ Configuration test failed!")
            print(f"   Error: {result['error']}")
            return 1
        
    finally:
        # Clean up test image if we created it
        if not args.test_image and test_image_path.exists():
            test_image_path.unlink()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
