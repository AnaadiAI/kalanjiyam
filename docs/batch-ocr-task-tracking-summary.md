# Batch OCR Task Tracking - Quick Reference

## Overview
Redis-based task tracking system for batch OCR operations that allows users to navigate away and return to see progress.

## Key Components

### 1. Redis Storage
- **Key Format**: `ocr_task:{project_slug}`
- **Value**: JSON with `task_id`, `engine`, `started_at`, `project_slug`
- **Expiration**: 24 hours (86400 seconds)

### 2. Main Functions

#### `batch_ocr(slug)` - Route Handler
- Checks Redis for ongoing tasks
- Shows progress page if active task found
- Stores new task info in Redis when starting OCR

#### `batch_ocr_status(task_id)` - Progress Endpoint
- Returns current progress
- Automatically cleans up completed tasks

#### `_clear_ocr_task_from_redis(task_id)` - Helper
- Scans Redis keys to find and remove completed tasks

### 3. User Experience Flow
1. User clicks "Run OCR" → Task stored in Redis → Progress page shown
2. User navigates away → Task continues in background
3. User returns → System detects task → Shows progress page
4. Task completes → Automatically removed from Redis

## Configuration

### Environment Variables
```bash
REDIS_URL=redis://localhost:6379/0  # Default
```

### Dependencies
- Redis server running
- Celery worker running (`make celery`)
- Redis Python client (already in requirements)

## Monitoring

### Redis Commands
```bash
# List all OCR tasks
redis-cli keys "ocr_task:*"

# Get task details
redis-cli get "ocr_task:my-project"

# Check memory usage
redis-cli info memory
```

### Logging
- Task storage: Debug level
- Task detection: Info level  
- Task cleanup: Debug level
- Errors: Warning level

## Error Handling

### Graceful Fallbacks
- Redis connection issues → Fall back to normal behavior
- Invalid task data → Remove and continue
- Task not found → Remove from Redis
- Server restart → Clean slate (users can restart)

## Benefits
- ✅ Better UX (persistent progress tracking)
- ✅ Stateless design (no DB changes)
- ✅ Automatic cleanup
- ✅ Error resilient
- ✅ Server restart friendly
- ✅ Uses existing infrastructure

## Limitations
- Requires Redis running
- Temporary storage (lost on Redis restart)
- Memory usage for active tasks
- Network dependency

## Files Modified
- `kalanjiyam/views/proofing/project.py` - Main implementation
- `docs/batch-ocr-task-tracking.rst` - Detailed documentation
- `docs/index.rst` - Added to documentation index
- `docs/background-tasks-with-celery.rst` - Added reference

## Future Enhancements
- Database persistence for longer-term tracking
- Task history and audit logs
- User notifications on completion
- Task cancellation support
- Progress time estimates
- Multiple concurrent tasks per user 