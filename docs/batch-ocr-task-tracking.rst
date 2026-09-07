Background Task & Batch OCR Tracking
======================================

Kalanjiyam provides a centralized task tracking system that spans both interactive user-initiated background jobs (in Redis) and enterprise-scale bulk folder ingestions (in PostgreSQL).

This architecture allows users to start long-running tasks—such as batch OCR, enhanced OCR, machine translations, or multi-page PDF ingestions—navigate across the application, and monitor live progress from any page via the navigation bar task tray.

Architecture Overview
---------------------

Task tracking is split into two distinct tiers based on lifecycle and durability requirements:

1. **User Task Tracking (Redis)**: Tracks active and recent operations launched by individual users or guests. Powers the live navbar notification tray, task progress meters, and client polling endpoints.
2. **Archival Batch Tracking (PostgreSQL)**: Persists whole-corpus ingestions, per-item status, Celery chunk splits, OCR engine latencies, and bounding box summaries in the database.

.. code-block:: text

   ┌────────────────────────────────────────────────────────┐
   │                  User Triggered Action                 │
   │      (Batch OCR / Enhanced OCR / Translation)          │
   └───────────────────────────┬────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌───────────────────────────┐ ┌───────────────────────────┐
   │ Redis User Task Registry  │ │ PostgreSQL Relational Log │
   │ (user_tasks:{identifier}) │ │ (BatchJob / BatchItem)    │
   ├───────────────────────────┤ ├───────────────────────────┤
   │ • Fast in-memory state    │ │ • Permanent audit log     │
   │ • 7-day auto-expiration   │ │ • Chunk & page metrics    │
   │ • Per-user / guest scoped │ │ • Engine accuracy stats   │
   │ • Live navbar polling     │ │ • Failure retry recovery  │
   └───────────────────────────┘ └───────────────────────────┘

Redis User Task System (``kalanjiyam.utils.user_tasks``)
-------------------------------------------------------

User Identifier Resolution
~~~~~~~~~~~~~~~~~~~~~~~~~~

Every task is associated with an actor via ``get_user_identifier(user, request)``:

* **Authenticated Users**: ``user:<user_id>`` (e.g. ``user:42``).
* **Guest / Unregistered Users**: ``guest:<device_fingerprint>`` (tracked via a cryptographic browser cookie so guest uploads and OCR tasks survive navigation).

Storage & Hash Structure
~~~~~~~~~~~~~~~~~~~~~~~~

User tasks are stored in a Redis Hash at key:

.. code-block:: text

   user_tasks:{user_identifier}

Inside the hash, each field key is the Celery ``task_id``, and the value is a serialized JSON object:

.. code-block:: json

   {
     "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
     "type": "enhanced_ocr",
     "project_slug": "shiva-purana-vol-1",
     "project_title": "Shiva Purana Volume 1",
     "started_at": "2026-09-07T10:15:30.123456",
     "status": "in_progress",
     "progress": 45.0,
     "completed_count": 45,
     "total_count": 100,
     "extra_info": {
       "engine": "dots_ocr",
       "profile": "document_cleanup",
       "line_segmentation": true,
       "upscale": true,
       "upscale_factor": 2
     }
   }

Key Lifecycles & Retention
~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Expiration**: The Redis key TTL is set to **7 days** (604,800 seconds) on every task update.
* **Auto-Discovery**: When visiting a project's batch OCR or translation view, the frontend queries the task registry to detect if an operation is already underway and automatically restores the live progress bar.

Supported Task Types
~~~~~~~~~~~~~~~~~~~~

The centralized system monitors four primary task types:

1. ``batch_ocr``: Standard batch OCR across all or selected pages of a project.
2. ``enhanced_ocr``: Enhanced OCR tasks with preprocessing, line segmentation, and upscaling.
3. ``translation``: Asynchronous machine translation of project revisions.
4. ``project_create``: PDF splitting, DOCX extraction, and page rasterization.

Navbar Task Tray & Polling Endpoints
------------------------------------

The application layout header includes an asynchronous task indicator:

* ``GET /proofing/tasks/active``: Returns the count of currently running tasks for the active user/guest. If count > 0, an animated spinner appears in the top navigation bar.
* ``GET /proofing/tasks/user-tasks``: Returns the full list of recent and active tasks for the current user, displaying status badges, percent progress, and direct links to the relevant project.
* ``POST /proofing/tasks/clear``: Dismisses completed or failed tasks from the user's active view.

PostgreSQL Archival Batch Ingestion
-----------------------------------

For bulk operations initiated via the CLI (``python cli.py batch-ocr``), progress is additionally mapped to relational database models defined in ``kalanjiyam.models.batch``:

1. **``BatchJob``**:
   - High-level execution pass over an S3 bucket prefix or local folder.
   - Records ``target_uri``, ``status`` (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED), ``extract_metadata``, and total runtime duration.
2. **``BatchItem``**:
   - Document-level tracking (one per PDF file or image directory).
   - Records file size, MIME type, target project ID, engine, average confidence, and processed character count.
3. **``BatchOcrChunk``**:
   - Parallelized Celery worker units. Large PDFs are partitioned into discrete chunks processed concurrently across the worker pool.
4. **``BatchOcrPage``**:
   - Per-page execution audit tracking OCR engine processing latency, page quality metrics (``confidence``, ``p05``), and foreign key link to ``ProofPage``.

CLI Batch Inspection
--------------------

Administrators can monitor and manage bulk batch jobs from the CLI:

.. code-block:: bash

   # List recent batch jobs
   docker exec -it kalanjiyam-web python scripts/cli.py batch-list

   # Check detailed status and item failure traces
   docker exec -it kalanjiyam-web python scripts/cli.py batch-status --job-id 12

   # Cancel a running batch job
   docker exec -it kalanjiyam-web python scripts/cli.py batch-cancel --job-id 12

   # Retry failed or stuck items
   docker exec -it kalanjiyam-web python scripts/cli.py batch-retry --job-id 12 --org "udaan"