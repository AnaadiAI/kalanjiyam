Proofing Editor & OCR Editing Mechanics
========================================

The Kalanjiyam proofing page editor provides an interactive, multi-modal environment designed for transcribing, correcting, and verifying historical manuscripts and printed texts.

Editing View Modes
------------------

Replica Mode (Default)
~~~~~~~~~~~~~~~~~~~~~~
- **Layout**: Displays the original scanned document image with bounding box overlays on the left pane and a spatial-scaled page replica on the right pane.
- **In-Place Editing**: Proofreaders can click directly on any text block on the page to edit text directly within the spatial canvas.
- **Structure Preservation**: Keeps columns, running headers, tables, figures, and footnotes in their true physical layout coordinates.

Flow Mode
~~~~~~~~~
- **Layout**: A continuous rich-text editor (using TipTap) on one side paired with an image viewer on the other.
- **Syncing**: OCR output executed in Replica mode automatically parses, structure-clusters, and syncs to Flow mode.
- **Continuous Flow**: Best suited for long-form prose and proofreading without strict spatial block boundaries.

Handsfree Voice Mode (Voice Editing)
------------------------------------

Kalanjiyam supports real-time, handsfree voice editing in the proofing editor (controlled by the ``VOICE_EDIT_ENABLED`` environment flag).

- **Workflow**: Pick an input language, open the microphone, and speak corrections (e.g. *"in line two change Rama to Lakshmana"*).
- **Architecture**: Audio is forwarded over HTTP to the Yojaka AI service at ``POST /v1/voice-edit``. The service parses speech and page reading order, returning block-anchored edit operations:
  
  .. code-block:: json

     {
       "op": "replace",
       "block_id": "b1a2c3d4",
       "find": "Rama",
       "replace": "Lakshmana"
     }

- **Client-Side Verification**: Before applying any edit, the browser verifies that ``find`` matches the live block text verbatim. If text has shifted or was already edited, failures surface clearly in the console log rather than corrupting text silently.
- **Visual Diff Log**: Spoken utterances appear in the docked bottom console, displaying what was said (slate), previous text (rose with strikethrough), and replacement text (emerald).
- **Dedicated Undo Stack**: Voice mode brings an independent undo stack allowing quick rollbacks of voice turns.
- **Audio Privacy**: Audio streams are processed in-flight and never stored on disk or S3, ensuring zero quota impact and full privacy.
- See :doc:`voice-edit-service-contract` for the full technical service specification.

Enhanced OCR & Live Enhancement Preview
---------------------------------------

For degraded, faded, or tightly-packed historical manuscripts:

1. Choose **Tools → Enhanced OCR** in the editor toolbar.
2. Select an image enhancement profile (e.g. ``document_cleanup``, ``bg_clahe``, ``sharpen``, ``text_enhancement``, ``hybrid_binarization``).
3. Optionally enable **Closely Written Manuscripts** (line segmentation) and **Upscaling** (1x to 4x).
4. Toggle **Live Preview** to visually compare the processed scan and segmented lines directly in the modal before running OCR.
5. See :doc:`enhanced-ocr` for full algorithm details and pipeline architecture.

Real-Time Updates & Version Branching
-------------------------------------

- **Live Updates Without Refresh**: When an OCR or background enhancement task finishes, the editor dynamically receives the new blocks and canvas layers via background polling/events without requiring a full browser reload.
- **Full Version Branch Visibility**: The editor version dropdown displays complete version identifiers (e.g. user branches, ``main`` branch, ``ocr:google``, ``ocr:enhanced:dots_ocr:document_cleanup:segmented``) without text truncation.
- **Optimistic Locking**: Every edit tracks the target ``version_key``. Concurrent conflicts trigger the Git-style Conflict Resolver modal, allowing users to visually inspect diffs and resolve conflicts safely.

Exports
-------

From the project **Download** page:

- **Plain Text** and **TEI XML** (annotated with structural tags).
- **PageDocument JSON Bundle** (gzipped spatial coordinates and word-level confidence).
- **Layout HTML Replica Export** (standalone self-rendering replica of the book).

See :doc:`ocr-api` for the OCR service API contract and :doc:`enhanced-ocr` for enhancement pipelines.
