# Surya OCR Setup Guide

This guide explains how to set up and use Surya OCR as an additional OCR option in Kalanjiyam.

## What is Surya OCR?

[Surya](https://github.com/datalab-to/surya) is a lightweight document OCR and analysis toolkit that supports 90+ languages. It provides:

- Text detection and recognition
- Layout analysis
- Reading order detection
- Table recognition
- LaTeX OCR

## Installation

### Prerequisites

- Python 3.10+
- PyTorch (CPU or GPU version)
- Access to install Python packages (may require virtual environment)

### Install Surya OCR

1. **Option 1: Install in a virtual environment (Recommended)**
   ```bash
   # Create and activate a virtual environment
   python3 -m venv surya_env
   source surya_env/bin/activate  # On Windows: surya_env\Scripts\activate
   
   # Install Surya OCR
   pip install surya-ocr
   ```

2. **Option 2: Install system-wide (if you have permission)**
   ```bash
   pip install surya-ocr
   ```

3. **Option 3: Install with pipx (isolated installation)**
   ```bash
   pipx install surya-ocr
   ```

4. The model weights will automatically download the first time you run Surya.

### Verify Installation

After installation, you can verify Surya OCR is working:

```bash
python3 -c "import surya; print('Surya OCR installed successfully')"
```

### Environment Variables (Optional)

You can configure Surya OCR behavior using environment variables:

- `TORCH_DEVICE`: Set to `cuda` for GPU acceleration or `cpu` for CPU-only
- `COMPILE_DETECTOR=true`: Enable compilation for detection model (faster inference)
- `COMPILE_LAYOUT=true`: Enable compilation for layout model
- `COMPILE_TABLE_REC=true`: Enable compilation for table recognition model

### Language Support

Surya OCR automatically detects languages in the document, so you don't need to specify the language manually. The language parameter in the interface is kept for consistency with other OCR engines but is not used by Surya.

## Usage in Kalanjiyam

Once installed, Surya OCR will be available as an option in:

1. **Page Editor**: Select "Surya OCR" from the OCR engine dropdown
2. **Batch OCR**: Choose "Surya OCR" when running OCR on multiple pages

### Supported Languages

Surya OCR supports 90+ languages, including:

- **Indian Languages**: Sanskrit (sa), Hindi (hi), Telugu (te), Marathi (mr), Bengali (bn), Gujarati (gu), Kannada (kn), Malayalam (ml), Tamil (ta), Punjabi (pa), Odia (or), Urdu (ur)
- **International Languages**: English (en), Arabic (ar), Persian (fa), Thai (th), Korean (ko), Japanese (ja), Chinese (zh), Russian (ru), Spanish (es), French (fr), German (de), Italian (it), Portuguese (pt), Dutch (nl), Polish (pl), Turkish (tr), Vietnamese (vi), Indonesian (id), Malay (ms)

## Performance

- **Text Detection**: ~0.13 seconds per image on GPU (A10)
- **Text Recognition**: Varies by language and image complexity
- **Layout Analysis**: ~0.13 seconds per image on GPU (A10)
- **Table Recognition**: ~0.3 seconds per image on GPU (A10)

## Troubleshooting

### Common Issues

1. **"Surya OCR is not installed" error**: 
   - This means the `surya-ocr` package is not installed in your Python environment
   - Follow the installation instructions above
   - If you're using a virtual environment, make sure it's activated
   - If you get permission errors, try using a virtual environment

2. **"externally-managed-environment" error**:
   - This means your system Python is managed by the OS
   - Use a virtual environment: `python3 -m venv myenv && source myenv/bin/activate`
   - Or use pipx: `pipx install surya-ocr`

3. **Model download fails**: Check your internet connection and try again
4. **CUDA out of memory**: Reduce batch size or use CPU mode
5. **Slow performance**: Enable compilation with environment variables

### Error Messages

- **"No such file or directory: 'surya'"**: Surya OCR is not installed
- **"ModuleNotFoundError: No module named 'surya'"**: Surya OCR is not installed
- **"Surya OCR is not installed"**: Follow the installation instructions above

### Getting Help

- [Surya GitHub Repository](https://github.com/datalab-to/surya)
- [Surya Documentation](https://github.com/datalab-to/surya#readme)
- [Datalab Support](https://www.datalab.to)

## License

Surya OCR is licensed under GPL-3.0. The model weights are licensed under CC-BY-NC-SA-4.0 with commercial usage restrictions. See the [Surya repository](https://github.com/datalab-to/surya) for full license details.
