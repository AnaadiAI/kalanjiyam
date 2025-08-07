# Kalanjiyam Documentation

This directory contains the technical documentation for Kalanjiyam, a breakthrough Siddha Knowledge Systems library.

## Recent Updates

### Background Task Services (2024)

New Makefile commands have been added for easier management of background task services:

- `make redis` - Start Redis server for Celery backend and broker
- `make celery` - Start Celery worker for background task processing

These commands are essential for features like project uploads, OCR processing, and batch operations.

### Batch OCR Task Tracking (2024)

A new Redis-based task tracking system has been implemented for batch OCR operations. This feature allows users to:

- Start a batch OCR operation
- Navigate away from the progress page
- Return later to see the current progress
- Resume monitoring without losing track of the operation

**Key Features:**
- Persistent task tracking using Redis
- Automatic cleanup of completed tasks
- 24-hour task expiration
- Error resilience and graceful fallbacks
- No database schema changes required

**Documentation:**
- See `batch-ocr-task-tracking.rst` for detailed implementation guide
- See `background-tasks-with-celery.rst` for general Celery setup

**Implementation Files:**
- `kalanjiyam/views/proofing/project.py` - Main implementation
- Uses existing Redis infrastructure
- Compatible with existing Celery setup

## Building Documentation

To build the documentation:

```bash
cd docs
make html
```

## Documentation Structure

- `index.rst` - Main documentation index
- `quickstart.rst` - Quick start guide
- `installation.rst` - Installation instructions
- `architecture.rst` - System architecture overview
- `background-tasks-with-celery.rst` - Celery background tasks
- `batch-ocr-task-tracking.rst` - Batch OCR task tracking system
- `running-in-production.rst` - Production deployment
- And more...

## Contributing

When adding new features, please:

1. Update the relevant documentation files
2. Add new documentation files if needed
3. Update `index.rst` to include new documentation
4. Test that documentation builds correctly
5. Include code examples and usage instructions
