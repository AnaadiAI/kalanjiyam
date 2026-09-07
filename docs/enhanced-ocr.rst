Enhanced OCR & Manuscript Line Segmentation
=============================================

Kalanjiyam includes an advanced **Enhanced OCR Pipeline** designed specifically for difficult historical manuscripts, palm-leaf records, and degraded archival documents.

The pipeline sits directly between the raw image storage and the OCR microservice: it applies image enhancement profiles, optionally segments tightly written or overlapping text lines, optionally performs high-quality image upscaling, and reconstructs the result into a clean synthetic image for **exactly one** OCR API invocation.

.. code-block:: text

   Raw Manuscript Page Scan
              │
              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                  Enhanced OCR Preprocessing                  │
   ├──────────────────────────────────────────────────────────────┤
   │ 1. Profile Preprocessing (document_cleanup, bg_clahe, etc.) │
   │ 2. Closely Written Line Segmentation & Valley Partitioning  │
   │ 3. Synthetic Single-Page Image Reconstruction                │
   │ 4. Optional Image Upscaling (1x, 2x, 3x, 4x)                │
   └──────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                   POST /v1/ocr (Exactly 1 API Call)
                                  │
                                  ▼
                   Kalanjiyam Proofing Editor
              (Version Track stamped with :segmented)

Overview of Capabilities
------------------------

1. **Targeted Enhancement Profiles**: Cleans backgrounds, evens out non-uniform illumination, sharpens faint character strokes, and eliminates ink bleed-through.
2. **Devanagari & Indic Line Segmentation**: Overcomes the common failure mode where tightly packed or touching lines in historical manuscripts are merged into single illegible blocks by standard OCR engines.
3. **Single OCR Invocation Guarantee**: Regardless of how many lines are segmented or padded, they are assembled into **one** synthetic page image before calling the OCR microservice. This prevents API quota exhaustion and keeps latency predictable.
4. **Coordinate & Document Preservation**: OCR bounding boxes and layout blocks returned from the OCR microservice map back to the editor cleanly.
5. **Storage & Version Isolation**: Enhanced OCR runs create distinct version tracks (e.g. ``ocr:enhanced:dots_ocr:document_cleanup:segmented``) and dedicated storage keys so original engine transcriptions are never overwritten.

Supported Enhancement Profiles
------------------------------

Preprocessing profiles are defined in ``kalanjiyam.utils.image_preprocessing``:

+--------------------------+-----------------------+--------------------------------------------------------------------------+
| Profile Name             | Aliases               | Description                                                              |
+==========================+=======================+==========================================================================+
| ``document_cleanup``     | default               | Illumination normalization, background stain removal, and CLAHE.         |
|                          |                       | Recommended general-purpose profile for aged paper and parchment.       |
+--------------------------+-----------------------+--------------------------------------------------------------------------+
| ``bg_clahe``             | ``clahe``,            | Gaussian background estimation followed by Contrast Limited Adaptive     |
|                          | ``background_clahe``  | Histogram Equalization. Good for uneven lighting and shadows.            |
+--------------------------+-----------------------+--------------------------------------------------------------------------+
| ``sharpen``              | —                     | Controlled unsharp masking (USM) with edge thresholding to sharpen soft  |
|                          |                       | character boundaries without amplifying paper grain noise.               |
+--------------------------+-----------------------+--------------------------------------------------------------------------+
| ``text_enhancement``     | —                     | Tone-curve adjustment (gamma 0.70) and stroke enhancement. Restores      |
|                          |                       | faded ink, faint pencil, and low-contrast writing.                       |
+--------------------------+-----------------------+--------------------------------------------------------------------------+
| ``hybrid_binarization``  | ``historical_hybrid``,| Multi-stage adaptive binarization for severely degraded historical      |
|                          | ``binarize``          | manuscripts, bleed-through, and water-damaged folios.                    |
+--------------------------+-----------------------+--------------------------------------------------------------------------+

Closely Written Manuscript Line Segmentation
--------------------------------------------

Historical Indian manuscripts frequently have lines written extremely close to each other, with ascenders, descenders, and Devanagari *shirorekha* (headlines) touching adjacent lines. Standard OCR models frequently fail to isolate lines or read across multiple lines simultaneously.

The line segmentation module (``kalanjiyam.utils.line_segmentation``) solves this via:

1. **Devanagari Headline & Text Region Isolation**: Identifies text regions using vertical and horizontal projection profiles (HPP).
2. **Valley-Based Boundary Partitioning**: Uses SciPy peak and valley detection on projection profiles to place clean partition boundaries precisely in the whitespace valleys between adjacent lines.
3. **Synthetic Reconstruction**: Individual lines are cropped and repacked vertically onto a clean white canvas with standardized inter-line spacing and margins.
4. **Synthetic Metadata**: The resulting ``OcrResponse`` records ``line_segmentation=True``, the segmentation algorithm version (``LINE_SEGMENTATION_VERSION = "2.0"``), and transformed image state.

Image Upscaling
---------------

Historical manuscripts scanned at lower resolutions (e.g. 100–150 DPI) often lack the stroke clarity needed for modern vision-language OCR models.

* Enhanced OCR supports optional image upscaling with factors of **1x**, **2x**, **3x**, or **4x**.
* Upscaling can run either standalone (on the enhanced full page) or downstream of the synthetic line reconstruction.
* PIL decompression limits (``MAX_IMAGE_PIXELS``) are automatically bypassed for high-resolution upscaled canvases.

Interactive Editor Experience
-----------------------------

In the single-page proofing editor (Replica Mode):

1. Click **Tools → Enhanced OCR** to open the enhancement modal.
2. Select your desired OCR engine (e.g. Dots OCR, Google, Gemma).
3. Choose the enhancement profile and toggle **Closely Written Manuscripts** or **Upscale**.
4. Use the **Live Preview** toggle to visually inspect the filtered scan and segmented bounding lines in real time before committing GPU credits.
5. Click **Run Enhanced OCR**. The editor receives live updates upon task completion without requiring a full page refresh.

Command-Line Interface (CLI)
----------------------------

Run Enhanced OCR from the command line using ``python cli.py enhanced-ocr``:

.. code-block:: bash

   # Basic run with document cleanup
   docker exec -it kalanjiyam-web python scripts/cli.py enhanced-ocr \
     --project "sample-manuscript" --page "1" \
     --engine "dots_ocr" --enhancement "document_cleanup"

   # Enable line segmentation for closely written manuscripts
   docker exec -it kalanjiyam-web python scripts/cli.py enhanced-ocr \
     --project "sample-manuscript" --page "1" \
     --engine "dots_ocr" --enhancement "document_cleanup" \
     --line-segmentation

   # Enable both line segmentation and 2x upscaling
   docker exec -it kalanjiyam-web python scripts/cli.py enhanced-ocr \
     --project "sample-manuscript" --page "1" \
     --engine "dots_ocr" --enhancement "document_cleanup" \
     --line-segmentation --upscale --upscale-factor 2

Options:
* ``--project TEXT``: Project URL slug (required).
* ``--page TEXT``: Page slug (e.g. ``1``, ``15``) (required).
* ``--engine TEXT``: Target OCR engine (default: ``dots_ocr``).
* ``--enhancement, --profile TEXT``: Enhancement profile: ``document_cleanup`` (default), ``bg_clahe``, ``sharpen``, ``text_enhancement``, ``hybrid_binarization``.
* ``--line-segmentation / --no-line-segmentation``: Enable manuscript line segmentation.
* ``--upscale / --no-upscale``: Enable image upscaling before OCR.
* ``--upscale-factor [1|2|3|4]``: Scale factor (default: ``2``).
* ``--lang TEXT``: Language code (default: ``sa``).
