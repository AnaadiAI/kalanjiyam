# Memory Optimization for Surya OCR

This document explains the memory optimization changes made to prevent high memory usage when running Surya OCR with GPU acceleration.

## Problem

The original configuration was causing excessive memory usage:
- **50+ Celery worker processes** running simultaneously
- Each worker consuming **900MB-1GB** of memory
- Total memory usage of **50+ GB** for background tasks
- Process 3450003 showing **482 MiB** memory usage

## Root Cause

1. **Default Celery concurrency**: Celery was creating worker processes equal to the number of CPU cores (50+ on your system)
2. **No memory limits**: Workers could grow indefinitely in memory
3. **Surya OCR memory usage**: Each Surya OCR process loads large ML models into GPU memory
4. **No cleanup**: Memory wasn't being properly released after tasks

## Solution

### 1. Conservative Celery Configuration

**File**: `kalanjiyam/tasks/__init__.py`

```python
app.conf.update(
    # Conservative worker configuration to prevent memory issues
    worker_concurrency=2,  # Limit to 2 worker processes instead of default (CPU cores)
    worker_prefetch_multiplier=1,  # Don't prefetch too many tasks
    task_acks_late=True,  # Only acknowledge tasks after completion
    worker_max_tasks_per_child=50,  # Restart workers after 50 tasks to prevent memory leaks
    worker_max_memory_per_child=200000,  # Restart workers if they exceed 200MB memory
)
```

### 2. Surya OCR Memory Optimization

**File**: `kalanjiyam/utils/surya_ocr.py`

```python
# Set conservative environment variables for Surya OCR
os.environ.setdefault('COMPILE_DETECTOR', 'false')  # Disable compilation to save memory
os.environ.setdefault('COMPILE_LAYOUT', 'false')    # Disable compilation to save memory
os.environ.setdefault('COMPILE_TABLE_REC', 'false') # Disable compilation to save memory

# Resize large images to prevent memory issues (max 2048px on longest side)
max_size = 2048
if max(image.size) > max_size:
    ratio = max_size / max(image.size)
    new_size = tuple(int(dim * ratio) for dim in image.size)
    image = image.resize(new_size, Image.Resampling.LANCZOS)

# Disable math recognition to save memory
math_mode=False,  # Disable math recognition to save memory

# Clean up memory after processing
del predictions_by_image, prediction, foundation_predictor, det_predictor, rec_predictor
gc.collect()
```

### 3. GPU Configuration Support

**File**: `config/surya_gpu_config.py`

New GPU configuration system that allows you to specify:
- Which GPU to use (`cuda:0`, `cuda:1`, etc.)
- Memory fraction to use (0.0-1.0)
- Memory limits in MB
- Growth policies

**Environment Variables**:
```bash
# GPU device selection
export SURYA_GPU_DEVICE=cuda:0          # Use specific GPU
export SURYA_GPU_DEVICE=auto            # Auto-detect (default)
export SURYA_GPU_DEVICE=cpu             # Force CPU mode

# Memory management
export SURYA_GPU_MEMORY_FRACTION=0.8    # Use 80% of GPU memory
export SURYA_GPU_MAX_MEMORY_MB=4096     # Max 4GB GPU memory
export SURYA_GPU_ALLOW_GROWTH=true      # Allow memory growth

# Performance settings
export SURYA_MAX_IMAGE_SIZE=2048        # Max image dimension
export SURYA_MATH_MODE=false            # Disable math recognition
```

**Example Configurations**:
```python
# Conservative (low memory usage)
config = {
    'device': 'cuda:0',
    'memory_fraction': 0.5,  # Use only 50% of GPU memory
    'max_memory_mb': 4096,   # Max 4GB
    'allow_growth': False,
}

# Balanced (default)
config = {
    'device': 'cuda:0',
    'memory_fraction': 0.8,  # Use 80% of GPU memory
    'max_memory_mb': 0,      # No limit
    'allow_growth': True,
}

# Performance (high memory usage)
config = {
    'device': 'cuda:0',
    'memory_fraction': 1.0,  # Use all GPU memory
    'max_memory_mb': 0,      # No limit
    'allow_growth': True,
}
```

### 4. Updated Startup Scripts

**Files**: 
- `scripts/start_celery.sh`
- `Makefile`
- `deploy/local/docker-compose.yml`
- `deploy/staging/docker-compose.yml`

All now use conservative settings:
```bash
celery -A kalanjiyam.tasks worker --loglevel=INFO --concurrency=2 --prefetch-multiplier=1
```

### 5. Memory Monitoring

**File**: `scripts/monitor_memory.py`

A monitoring script that:
- Tracks Celery worker processes and their memory usage
- Identifies high memory processes
- Provides recommendations for memory management
- Can stop all workers if needed

### 6. GPU Testing Tools

**File**: `scripts/test_surya_gpu.py`

A testing script that:
- Lists available GPUs
- Tests different GPU configurations
- Measures performance and memory usage
- Validates configuration settings

## Results

### Before Optimization
- **50+ Celery workers** consuming **50+ GB** total memory
- Each worker: **900MB-1GB**
- System memory pressure and potential crashes

### After Optimization
- **4 Celery workers** consuming **389MB** total memory
- Each worker: **~100MB**
- **99% reduction** in memory usage for background tasks

## Usage

### Start Celery with Conservative Settings
```bash
make celery
```

### Monitor Memory Usage
```bash
make memory-monitor
```

### Stop All Workers (if needed)
```bash
make celery-stop
```

### Test GPU Configuration
```bash
# List available GPUs
make list-gpus

# Test default configuration
make test-surya-gpu

# Test specific configuration
python scripts/test_surya_gpu.py --config conservative --device cuda:0 --memory-fraction 0.5
```

## Configuration Options

### Environment Variables for Surya OCR

You can customize Surya OCR behavior with environment variables:

```bash
# Device selection
export SURYA_GPU_DEVICE=cuda:0          # Use specific GPU
export SURYA_GPU_DEVICE=auto            # Auto-detect (default)
export SURYA_GPU_DEVICE=cpu             # Force CPU mode

# Memory optimization (recommended)
export SURYA_GPU_MEMORY_FRACTION=0.8    # Use 80% of GPU memory
export SURYA_GPU_MAX_MEMORY_MB=4096     # Max 4GB GPU memory
export SURYA_GPU_ALLOW_GROWTH=true      # Allow memory growth
export COMPILE_DETECTOR=false           # Disable compilation
export COMPILE_LAYOUT=false             # Disable compilation
export COMPILE_TABLE_REC=false          # Disable compilation

# Performance vs Memory trade-off
export SURYA_MAX_IMAGE_SIZE=2048        # Max image dimension
export SURYA_MATH_MODE=false            # Disable math recognition
```

### Celery Configuration

You can adjust Celery settings in `kalanjiyam/tasks/__init__.py`:

```python
# For more memory-constrained systems
worker_concurrency=1              # Single worker
worker_max_memory_per_child=100000  # 100MB limit

# For systems with more memory
worker_concurrency=4              # 4 workers
worker_max_memory_per_child=500000  # 500MB limit
```

### GPU Configuration Examples

```python
# Conservative setup (low memory usage)
from config.surya_gpu_config import EXAMPLE_CONFIGS
config = EXAMPLE_CONFIGS['conservative']

# Balanced setup (default)
config = EXAMPLE_CONFIGS['balanced']

# Performance setup (high memory usage)
config = EXAMPLE_CONFIGS['performance']

# Multi-GPU setup
from config.surya_gpu_config import get_multi_gpu_config
config = get_multi_gpu_config([0, 1], memory_fraction=0.6)

# CPU-only setup
from config.surya_gpu_config import get_cpu_config
config = get_cpu_config()
```

## Troubleshooting

### High Memory Usage
1. Run `make memory-monitor` to check current usage
2. If workers are using too much memory, restart: `make celery-stop && make celery`
3. Check for memory leaks in Surya OCR processes
4. Reduce GPU memory fraction: `export SURYA_GPU_MEMORY_FRACTION=0.5`

### Slow Performance
1. Increase `worker_concurrency` if you have more memory available
2. Enable compilation for faster inference (but higher memory usage):
   ```bash
   export COMPILE_DETECTOR=true
   export COMPILE_LAYOUT=true
   ```
3. Increase GPU memory fraction: `export SURYA_GPU_MEMORY_FRACTION=1.0`

### GPU Memory Issues
1. Use CPU mode: `export SURYA_GPU_DEVICE=cpu`
2. Reduce image size: `export SURYA_MAX_IMAGE_SIZE=1024`
3. Disable math recognition: `export SURYA_MATH_MODE=false`
4. Set memory limits: `export SURYA_GPU_MAX_MEMORY_MB=2048`

### GPU Selection Issues
1. List available GPUs: `make list-gpus`
2. Test specific GPU: `python scripts/test_surya_gpu.py --device cuda:1`
3. Check GPU memory: `nvidia-smi`
4. Use auto-detection: `export SURYA_GPU_DEVICE=auto`

## Best Practices

1. **Monitor regularly**: Use `make memory-monitor` to track usage
2. **Restart workers**: Restart Celery workers periodically to prevent memory leaks
3. **Scale appropriately**: Adjust concurrency based on available memory
4. **Use conservative defaults**: The current settings are optimized for stability over speed
5. **Test GPU configurations**: Use `make test-surya-gpu` to validate settings
6. **Set memory limits**: Use `SURYA_GPU_MAX_MEMORY_MB` to prevent GPU OOM errors

## Future Improvements

1. **Dynamic scaling**: Automatically adjust worker count based on system resources
2. **Memory profiling**: Add detailed memory profiling for Surya OCR processes
3. **GPU memory management**: Better GPU memory allocation and cleanup
4. **Task prioritization**: Prioritize OCR tasks based on user needs
5. **Multi-GPU load balancing**: Distribute tasks across multiple GPUs
6. **GPU monitoring**: Real-time GPU memory and utilization monitoring
