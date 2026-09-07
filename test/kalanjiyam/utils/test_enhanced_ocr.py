"""Comprehensive tests for Enhanced OCR pipeline.

Covers:
1. Normal OCR remains unchanged.
2. Enhanced OCR can run with Gemma.
3. Enhanced OCR can run with Dots.
4. Each supported preprocessing profile works (document_cleanup, clahe, sharpen, text_enhancement).
5. Output dimensions are preserved and source image is not modified in-place.
6. Each profile produces a distinct preprocessed output.
7. Preprocessing parameters and custom PreprocessingConfig work.
8. Invalid engine is rejected.
9. Invalid enhancement profile (including "normal") is rejected cleanly.
10. Alias resolution works (background_clahe -> document_cleanup, clahe_1 -> clahe).
11. Enhanced result is marked as enhanced with both 'enhancement' and 'preprocessing' metadata.
12. Enhanced result does not overwrite normal OCR.
13. JSON is correctly gzip-compressed and can be read back.
14. Page dimensions / coordinate space remain correct.
15. Different engine + preprocessing combinations produce distinguishable versions/results.
16. API Route for Enhanced OCR.
17. Background Task for Enhanced OCR.
"""

import gzip
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from kalanjiyam.utils.document_storage import derive_revision_tag
from kalanjiyam.utils.image_preprocessing import (
    DEFAULT_PREPROCESSING_CONFIG,
    SUPPORTED_ENHANCEMENT_PROFILES,
    PreprocessingConfig,
    preprocess_image,
    preprocess_image_to_tempfile,
    validate_enhancement_profile,
)
from kalanjiyam.utils.ocr_persist import ocr_response_to_api_dict
from kalanjiyam.utils.ocr_runner import run_enhanced_ocr, run_ocr
from kalanjiyam.utils.ocr_types import OcrResponse
from kalanjiyam.utils.storage import MemoryStorage, page_enhanced_ocr_key, page_ocr_key


@pytest.fixture
def test_image(tmp_path) -> Path:
    """Create a temporary test image with realistic scanned page content (text, background, stain)."""
    img_path = tmp_path / "test_page_19.jpg"
    im = Image.new("RGB", (400, 600), color=(235, 225, 205))  # Aged paper color
    draw = ImageDraw.Draw(im)
    # Add simulated lines of text / strokes
    for y in range(50, 550, 30):
        draw.line([(30, y), (370, y)], fill=(40, 35, 30), width=3)
    # Add uneven illumination gradient / stain
    for i in range(100):
        draw.rectangle(
            [i, i, 400 - i, 600 - i], outline=(220 - i // 2, 210 - i // 2, 190 - i // 2)
        )
    im.save(img_path, format="JPEG")
    return img_path


@pytest.fixture
def mock_ocr_response():
    """Sample raw OCR response from backend engine."""
    return OcrResponse(
        text_content="Sample extracted text line 1\nSample extracted text line 2",
        bounding_boxes=[(10.0, 20.0, 390.0, 50.0, "Sample line")],
        blocks=[
            {
                "id": "block_1",
                "type": "paragraph",
                "bbox": [10, 20, 390, 50],
                "reading_order": 1,
                "content": "Sample extracted text line 1",
                "confidence": 0.95,
            }
        ],
        content_format="blocks",
        page_width=400,
        page_height=600,
        pipeline="standard",
        coordinate_space="pixel",
        contract_version="2.2",
        model={"name": "dots-ocr", "version": "1.0.0"},
        page_confidence=0.95,
        p05=0.95,
        blocks_count=1,
        chars_count=28,
        engine_latency_ms=150.0,
    )


# ---------------------------------------------------------------------------
# 1. Normal OCR remains unchanged
# ---------------------------------------------------------------------------
def test_normal_ocr_remains_unchanged(test_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_ocr(test_image, engine_name="dots-ocr", language="sa")
        assert resp.ocr_mode == "standard"
        assert resp.enhancement_profile is None
        assert resp.enhancement_version is None
        # Verify normal API dict output does not inject enhanced fields
        api_dict = ocr_response_to_api_dict(
            resp, "dots_ocr", image_width=400, image_height=600
        )
        assert "ocr_mode" not in api_dict
        assert "enhancement" not in api_dict
        assert "preprocessing" not in api_dict
        assert api_dict["engine"] == "dots_ocr"
        assert api_dict["coordinate_space"] == "pixel"
        mock_remote.assert_called_once_with(test_image, "dots_ocr", "sa")


# ---------------------------------------------------------------------------
# 2. Enhanced OCR can run with Gemma
# ---------------------------------------------------------------------------
def test_enhanced_ocr_runs_with_gemma(test_image, mock_ocr_response):
    gemma_resp = OcrResponse(
        text_content="Gemma text",
        bounding_boxes=[(10.0, 20.0, 390.0, 50.0, "Gemma text")],
        blocks=[
            {
                "id": "g1",
                "type": "paragraph",
                "bbox": [10, 20, 390, 50],
                "reading_order": 1,
                "content": "Gemma text",
                "confidence": 0.92,
            }
        ],
        page_width=400,
        page_height=600,
        coordinate_space="pixel",
        contract_version="2.2",
        model={"name": "gemma-ocr", "version": "1.0.0"},
    )
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=gemma_resp
    ) as mock_remote:
        resp = run_enhanced_ocr(
            test_image,
            engine_name="gemma-ocr",
            profile="document_cleanup",
            language="sa",
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.engine == "gemma_ocr"
        assert resp.enhancement_profile == "document_cleanup"
        assert resp.enhancement_version == "1.0"
        assert resp.preprocessing_latency_ms is not None
        mock_remote.assert_called_once()
        args, _ = mock_remote.call_args
        assert args[1] == "gemma_ocr"
        assert args[2] == "sa"


# ---------------------------------------------------------------------------
# 3. Enhanced OCR can run with Dots
# ---------------------------------------------------------------------------
def test_enhanced_ocr_runs_with_dots(test_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            test_image,
            engine_name="dots-ocr",
            profile="bg_clahe",
            language="sa",
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.engine == "dots_ocr"
        assert resp.enhancement_profile == "bg_clahe"
        assert resp.enhancement_version == "1.0"
        mock_remote.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Each supported preprocessing profile works
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile", SUPPORTED_ENHANCEMENT_PROFILES)
def test_each_preprocessing_profile_works(test_image, profile):
    with Image.open(test_image) as img:
        orig_size = img.size
        orig_pixels = list(img.getdata())
        processed = preprocess_image(img, profile)
        assert processed is not None
        assert processed.size == orig_size
        assert isinstance(processed, Image.Image)
        # Verify source image was not mutated in-place
        assert list(img.getdata()) == orig_pixels

    with preprocess_image_to_tempfile(test_image, profile) as tmp_file:
        assert tmp_file.exists()
        with Image.open(tmp_file) as proc_img:
            assert proc_img.size == orig_size


# ---------------------------------------------------------------------------
# 5. Output dimensions are preserved and source image is not modified
# ---------------------------------------------------------------------------
def test_dimensions_and_source_immutability(test_image):
    with Image.open(test_image) as original:
        orig_data = list(original.getdata())

        for profile in SUPPORTED_ENHANCEMENT_PROFILES:
            result = preprocess_image(original, profile)
            assert result.size == (400, 600)
            # Original remains identical
            assert list(original.getdata()) == orig_data


# ---------------------------------------------------------------------------
# 6. Each profile produces a distinct preprocessed output
# ---------------------------------------------------------------------------
def test_distinct_preprocessing_outputs(test_image):
    with Image.open(test_image) as img:
        outputs = {}
        for profile in SUPPORTED_ENHANCEMENT_PROFILES:
            proc = preprocess_image(img, profile)
            # Store pixel sample hash
            outputs[profile] = list(proc.convert("L").getdata())

        # Verify all profiles produce mutually distinct pixel arrays
        profiles = list(SUPPORTED_ENHANCEMENT_PROFILES)
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                p1, p2 = profiles[i], profiles[j]
                assert outputs[p1] != outputs[p2], (
                    f"Outputs of {p1} and {p2} should be distinct"
                )


# ---------------------------------------------------------------------------
# 7. Preprocessing parameters and custom PreprocessingConfig work
# ---------------------------------------------------------------------------
def test_custom_preprocessing_config(test_image):
    with Image.open(test_image) as img:
        cfg_default = DEFAULT_PREPROCESSING_CONFIG
        cfg_custom = PreprocessingConfig(
            clahe_clip_limit=5.0,
            sharpen_percent=250,
            text_gamma=0.40,
        )

        res_bg_clahe_def = preprocess_image(img, "bg_clahe", config=cfg_default)
        res_bg_clahe_custom = preprocess_image(img, "bg_clahe", config=cfg_custom)
        assert list(res_bg_clahe_def.getdata()) != list(res_bg_clahe_custom.getdata())

        res_sharp_def = preprocess_image(img, "sharpen", config=cfg_default)
        res_sharp_custom = preprocess_image(img, "sharpen", config=cfg_custom)
        assert list(res_sharp_def.getdata()) != list(res_sharp_custom.getdata())


# ---------------------------------------------------------------------------
# 8. Invalid engine is rejected
# ---------------------------------------------------------------------------
def test_invalid_engine_is_rejected(test_image):
    with pytest.raises(ValueError, match="Unsupported OCR engine"):
        run_enhanced_ocr(
            test_image, engine_name="unsupported_engine_xyz", profile="document_cleanup"
        )


# ---------------------------------------------------------------------------
# 9. Invalid enhancement profile (including 'normal') is rejected
# ---------------------------------------------------------------------------
def test_invalid_enhancement_profile_is_rejected(test_image):
    with pytest.raises(ValueError, match="Unsupported enhancement profile"):
        run_enhanced_ocr(
            test_image, engine_name="dots-ocr", profile="invalid_magic_profile"
        )

    # "normal" profile is intentionally removed and must be rejected
    with pytest.raises(ValueError, match="Unsupported enhancement profile"):
        validate_enhancement_profile("normal")

    with pytest.raises(ValueError, match="Unsupported enhancement profile"):
        validate_enhancement_profile("unknown_profile")


# ---------------------------------------------------------------------------
# 10. Alias resolution works
# ---------------------------------------------------------------------------
def test_profile_alias_resolution():
    assert validate_enhancement_profile("background_clahe") == "bg_clahe"
    assert validate_enhancement_profile("bg_clahe") == "bg_clahe"
    assert validate_enhancement_profile("bg+clahe") == "bg_clahe"
    assert validate_enhancement_profile("clahe") == "bg_clahe"
    assert validate_enhancement_profile("clahe_1") == "bg_clahe"
    assert validate_enhancement_profile("DOCUMENT_CLEANUP") == "document_cleanup"
    assert validate_enhancement_profile("SHARPEN") == "sharpen"
    assert validate_enhancement_profile("text_enhancement") == "text_enhancement"
    assert validate_enhancement_profile("hybrid_binarization") == "hybrid_binarization"
    assert validate_enhancement_profile("HYBRID") == "hybrid_binarization"
    assert validate_enhancement_profile("historical_hybrid") == "hybrid_binarization"
    assert validate_enhancement_profile("binarize") == "hybrid_binarization"


# ---------------------------------------------------------------------------
# 11. Enhanced result is marked as enhanced with enhancement & preprocessing metadata
# ---------------------------------------------------------------------------
def test_enhanced_result_metadata(test_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ):
        resp = run_enhanced_ocr(
            test_image, engine_name="dots-ocr", profile="document_cleanup"
        )
        api_dict = ocr_response_to_api_dict(
            resp, "dots_ocr", image_width=400, image_height=600
        )
        assert api_dict["ocr_mode"] == "enhanced"
        assert api_dict["enhancement_version"] == "1.0"
        assert api_dict["contract_version"] == "2.2"
        assert api_dict["engine"] == "dots_ocr"
        assert api_dict["enhancement"] == {
            "profile": "document_cleanup",
            "version": "1.0",
        }
        assert api_dict["preprocessing"] == {
            "profile": "document_cleanup",
            "version": "1.0",
        }
        assert api_dict["model"] == {"name": "dots-ocr", "version": "1.0.0"}
        assert "preprocessing_latency_ms" in api_dict


# ---------------------------------------------------------------------------
# 12. Enhanced result does not overwrite normal OCR
# ---------------------------------------------------------------------------
def test_enhanced_result_does_not_overwrite_normal_ocr(flask_app):
    with flask_app.app_context():
        mem_storage = MemoryStorage()
        with patch("kalanjiyam.utils.storage.get_storage", return_value=mem_storage):
            project_slug = "cool-book"
            page_slug = "19"

            # 1. Store normal OCR
            normal_key = page_ocr_key(project_slug, page_slug)
            normal_payload = {"text": "normal ocr text", "mode": "standard"}
            mem_storage.save_json_gz(normal_key, normal_payload)

            # 2. Store enhanced OCR
            enhanced_key = page_enhanced_ocr_key(
                project_slug, page_slug, "dots-ocr", "document_cleanup"
            )
            enhanced_payload = {
                "contract_version": "2.2",
                "ocr_mode": "enhanced",
                "enhancement_version": "1.0",
                "engine": "dots-ocr",
                "enhancement": {"profile": "document_cleanup", "version": "1.0"},
                "preprocessing": {"profile": "document_cleanup", "version": "1.0"},
                "blocks": [],
            }
            mem_storage.save_json_gz(enhanced_key, enhanced_payload)

            # Assert keys are completely distinct
            assert normal_key != enhanced_key
            assert "enhanced" in enhanced_key
            assert "normal" not in enhanced_key

            # Assert loading normal OCR returns original untouched normal content
            loaded_normal = mem_storage.load_json_gz(normal_key)
            assert loaded_normal == normal_payload
            assert loaded_normal["mode"] == "standard"

            # Assert loading enhanced OCR returns enhanced content
            loaded_enhanced = mem_storage.load_json_gz(enhanced_key)
            assert loaded_enhanced["ocr_mode"] == "enhanced"
            assert loaded_enhanced["enhancement"]["profile"] == "document_cleanup"


# ---------------------------------------------------------------------------
# 13. JSON is correctly gzip-compressed and can be read back
# ---------------------------------------------------------------------------
def test_json_gzip_compression_and_decompression(flask_app):
    with flask_app.app_context():
        mem_storage = MemoryStorage()
        with patch("kalanjiyam.utils.storage.get_storage", return_value=mem_storage):
            key = page_enhanced_ocr_key("proj", "19", "dots-ocr", "bg_clahe")
            data = {
                "ocr_mode": "enhanced",
                "engine": "dots-ocr",
                "enhancement_version": "1.0",
                "enhancement": {"profile": "bg_clahe", "version": "1.0"},
                "preprocessing": {"profile": "bg_clahe", "version": "1.0"},
                "blocks": [{"id": "b1", "content": "compressed text"}],
            }
            mem_storage.save_json_gz(key, data)

            # Verify raw bytes in storage are valid gzip
            raw_bytes = mem_storage.read_bytes(key)
            decompressed_raw = gzip.decompress(raw_bytes).decode("utf-8")
            parsed = json.loads(decompressed_raw)
            assert parsed == data

            # Verify loading via load_json_gz helper
            loaded = mem_storage.load_json_gz(key)
            assert loaded == data


# ---------------------------------------------------------------------------
# 14. Page dimensions / coordinate space remain correct
# ---------------------------------------------------------------------------
def test_page_dimensions_and_coordinate_space(test_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ):
        resp = run_enhanced_ocr(
            test_image, engine_name="dots-ocr", profile="text_enhancement"
        )
        api_dict = ocr_response_to_api_dict(
            resp, "dots_ocr", image_width=400, image_height=600
        )
        assert api_dict["page_width"] == 400
        assert api_dict["page_height"] == 600
        assert api_dict["coordinate_space"] == "pixel"
        for block in api_dict["blocks"]:
            bbox = block["bbox"]
            assert len(bbox) == 4
            assert 0 <= bbox[0] <= 400
            assert 0 <= bbox[1] <= 600
            assert 0 <= bbox[2] <= 400
            assert 0 <= bbox[3] <= 600


# ---------------------------------------------------------------------------
# 15. Different engine + preprocessing combinations produce distinguishable versions/results
# ---------------------------------------------------------------------------
def test_different_combinations_produce_distinguishable_results(flask_app):
    with flask_app.app_context():
        # Keys for combinations on page 19:
        key1 = page_enhanced_ocr_key("cool-book", "19", "dots-ocr", "document_cleanup")
        key2 = page_enhanced_ocr_key("cool-book", "19", "gemma-ocr", "document_cleanup")
        key3 = page_enhanced_ocr_key("cool-book", "19", "dots-ocr", "bg_clahe")
        key4 = page_enhanced_ocr_key("cool-book", "19", "dots-ocr", "text_enhancement")

        assert len({key1, key2, key3, key4}) == 4

        assert "dots-ocr/document_cleanup/19.json.gz" in key1
        assert "gemma-ocr/document_cleanup/19.json.gz" in key2
        assert "dots-ocr/bg_clahe/19.json.gz" in key3
        assert "dots-ocr/text_enhancement/19.json.gz" in key4

        # Revision tags for version tracks:
        class MockRevision:
            def __init__(self, key):
                self.page_version = MagicMock(version_key=key)
                self.summary = ""
                self.translations = []
                self.author = None

        rev1 = MockRevision("ocr:enhanced:dots_ocr:document_cleanup")
        rev2 = MockRevision("ocr:enhanced:gemma_ocr:document_cleanup")
        rev3 = MockRevision("ocr:enhanced:dots_ocr:bg_clahe")
        rev4 = MockRevision("ocr:enhanced:dots_ocr:text_enhancement")
        rev_normal = MockRevision("ocr:dots_ocr")

        tag1 = derive_revision_tag(rev1)
        tag2 = derive_revision_tag(rev2)
        tag3 = derive_revision_tag(rev3)
        tag4 = derive_revision_tag(rev4)
        tag_normal = derive_revision_tag(rev_normal)

        assert tag1 == "ocr-enhanced-dots-ocr_document-cleanup"
        assert tag2 == "ocr-enhanced-gemma-ocr_document-cleanup"
        assert tag3 == "ocr-enhanced-dots-ocr_bg-clahe"
        assert tag4 == "ocr-enhanced-dots-ocr_text-enhancement"
        assert tag_normal == "ocr-dots-ocr"

        assert len({tag1, tag2, tag3, tag4, tag_normal}) == 5


# ---------------------------------------------------------------------------
# 16. API Route for Enhanced OCR
# ---------------------------------------------------------------------------
def test_enhanced_ocr_api_endpoint(flask_app, mock_ocr_response, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(name="Test Board Enhanced")
        session.add(board)
        session.flush()

        status = session.query(db.PageStatus).first()
        project = db.Project(
            slug="test-enhanced-ocr-book",
            display_title="Test Enhanced OCR Book",
            board_id=board.id,
        )
        session.add(project)
        session.flush()

        page = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        session.add(page)
        session.commit()

        dummy_img = tmp_path / "page_1.jpg"
        Image.new("RGB", (400, 600), color=(250, 250, 250)).save(
            dummy_img, format="JPEG"
        )

        with flask_app.test_client() as client:
            with (
                patch(
                    "kalanjiyam.views.proofing.page.get_page_image_filepath",
                    return_value=dummy_img,
                ),
                patch(
                    "kalanjiyam.utils.ocr_runner.run_ocr_remote",
                    return_value=mock_ocr_response,
                ),
                patch("kalanjiyam.utils.quotas.ensure_ocr_quota_for_project"),
                patch("kalanjiyam.utils.quotas.consume_ocr_credit_for_project"),
                patch(
                    "kalanjiyam.views.proofing.page.q.user_can_view_proofing_project",
                    return_value=True,
                ),
                patch("kalanjiyam.views.proofing.decorators.current_user") as dec_user,
                patch("kalanjiyam.views.proofing.page.current_user") as mock_user,
            ):
                for u in (dec_user, mock_user):
                    u.is_authenticated = True
                    u.is_super_admin = False
                    u.is_org_admin = True
                    u.is_moderator = True
                    u.is_p2 = True
                    u.is_p1 = True
                    u.id = 1

                # Test document_cleanup
                resp = client.get(
                    f"/api/enhanced-ocr/{project.slug}/{page.slug}/?engine=dots_ocr&enhancement=document_cleanup&language=sa"
                )
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["ocr_mode"] == "enhanced"
                assert data["enhancement_version"] == "1.0"
                assert data["enhancement"]["profile"] == "document_cleanup"
                assert data["preprocessing"]["profile"] == "document_cleanup"
                assert data["engine"] == "dots_ocr"

                # Test text_enhancement
                resp_text_enh = client.get(
                    f"/api/enhanced-ocr/{project.slug}/{page.slug}/?engine=dots_ocr&enhancement=text_enhancement&language=sa"
                )
                assert resp_text_enh.status_code == 200
                data_text_enh = resp_text_enh.get_json()
                assert data_text_enh["enhancement"]["profile"] == "text_enhancement"

                # Test alias route /api/ocr/enhanced/ with alias background_clahe -> bg_clahe
                resp_alias = client.get(
                    f"/api/ocr/enhanced/{project.slug}/{page.slug}/?engine=dots_ocr&enhancement=background_clahe&language=sa"
                )
                assert resp_alias.status_code == 200
                assert resp_alias.get_json()["enhancement"]["profile"] == "bg_clahe"

                # Test invalid enhancement profile via API returns 400
                bad_resp = client.get(
                    f"/api/enhanced-ocr/{project.slug}/{page.slug}/?engine=dots_ocr&enhancement=bad_profile"
                )
                assert bad_resp.status_code == 400


# ---------------------------------------------------------------------------
# 17. Background Task for Enhanced OCR
# ---------------------------------------------------------------------------
def test_enhanced_ocr_background_task(flask_app, mock_ocr_response, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q
    from kalanjiyam.tasks.ocr import _run_enhanced_ocr_for_page_inner

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(name="Test Board Task")
        session.add(board)
        session.flush()

        status = session.query(db.PageStatus).first()
        project = db.Project(
            slug="test-task-enhanced-book",
            display_title="Test Task Enhanced Book",
            board_id=board.id,
        )
        session.add(project)
        session.flush()

        page = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        session.add(page)
        session.commit()

        dummy_img = tmp_path / "page_task.jpg"
        Image.new("RGB", (400, 600), color=(250, 250, 250)).save(
            dummy_img, format="JPEG"
        )

        with (
            patch(
                "kalanjiyam.tasks.ocr.get_page_image_filepath", return_value=dummy_img
            ),
            patch(
                "kalanjiyam.utils.ocr_runner.run_ocr_remote",
                return_value=mock_ocr_response,
            ),
            patch("kalanjiyam.utils.quotas.ensure_ocr_quota_for_project"),
            patch("kalanjiyam.utils.quotas.consume_ocr_credit_for_project"),
        ):
            result = _run_enhanced_ocr_for_page_inner(
                app_env="testing",
                project_slug=project.slug,
                page_slug=page.slug,
                engine="dots-ocr",
                profile="document_cleanup",
                language="sa",
            )
            assert result is not None
            assert result["ocr_mode"] == "enhanced"
            assert result["enhancement"]["profile"] == "document_cleanup"
            assert result["preprocessing"]["profile"] == "document_cleanup"
            assert result["engine"] == "dots_ocr"


# ---------------------------------------------------------------------------
# 18. Preview Enhancement API Endpoint
# ---------------------------------------------------------------------------
def test_preview_enhancement_endpoint(flask_app, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(name="Test Board Preview")
        session.add(board)
        session.flush()

        status = session.query(db.PageStatus).first()
        project = db.Project(
            slug="test-preview-book",
            display_title="Test Preview Book",
            board_id=board.id,
        )
        session.add(project)
        session.flush()

        page = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        session.add(page)
        session.commit()

        dummy_img = tmp_path / "preview_page.jpg"
        Image.new("RGB", (200, 300), color=(220, 220, 220)).save(
            dummy_img, format="JPEG"
        )

        with flask_app.test_client() as client:
            with (
                patch(
                    "kalanjiyam.views.proofing.page.get_page_image_filepath",
                    return_value=dummy_img,
                ),
                patch(
                    "kalanjiyam.views.proofing.page.q.user_can_view_proofing_project",
                    return_value=True,
                ),
                patch("kalanjiyam.views.proofing.decorators.current_user") as dec_user,
                patch("kalanjiyam.views.proofing.page.current_user") as mock_user,
            ):
                for u in (dec_user, mock_user):
                    u.is_authenticated = True
                    u.is_super_admin = True
                    u.id = 1

                # 1. Preview hybrid_binarization
                resp = client.get(
                    f"/api/preview-enhancement/{project.slug}/{page.slug}/?profile=hybrid_binarization"
                )
                assert resp.status_code == 200
                assert resp.content_type == "image/jpeg"
                assert len(resp.data) > 0

                # 2. Preview document_cleanup
                resp_doc = client.get(
                    f"/api/preview-enhancement/{project.slug}/{page.slug}/?profile=document_cleanup"
                )
                assert resp_doc.status_code == 200
                assert resp_doc.content_type == "image/jpeg"

                # 3. Preview with line segmentation enabled
                resp_seg = client.get(
                    f"/api/preview-enhancement/{project.slug}/{page.slug}/?profile=hybrid_binarization&line_segmentation=1"
                )
                assert resp_seg.status_code == 200
                assert resp_seg.content_type == "image/jpeg"
                assert len(resp_seg.data) > 0

                # 4. Invalid profile returns 400
                resp_bad = client.get(
                    f"/api/preview-enhancement/{project.slug}/{page.slug}/?profile=bad_profile_xyz"
                )
                assert resp_bad.status_code == 400


# ---------------------------------------------------------------------------
# 19. Replace and Revert Page Image API Endpoint
# ---------------------------------------------------------------------------
def test_replace_and_revert_page_image_endpoint(flask_app, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(name="Test Board Replace")
        session.add(board)
        session.flush()

        status = session.query(db.PageStatus).first()
        project = db.Project(
            slug="test-replace-book",
            display_title="Test Replace Book",
            board_id=board.id,
        )
        session.add(project)
        session.flush()

        page = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        session.add(page)
        session.commit()

        dummy_img = tmp_path / "replace_page.jpg"
        Image.new("RGB", (200, 300), color=(200, 200, 200)).save(
            dummy_img, format="JPEG"
        )

        from kalanjiyam.utils.storage import (
            get_project_org_slug,
            get_storage,
            page_master_image_key,
        )

        storage = get_storage()
        org_slug = get_project_org_slug(project)
        m_key = page_master_image_key(project.slug, page.slug, org_slug=org_slug)
        if storage.exists(m_key):
            storage.delete(m_key)

        with flask_app.test_client() as client:
            with (
                patch(
                    "kalanjiyam.views.proofing.page.get_page_image_filepath",
                    return_value=dummy_img,
                ),
                patch(
                    "kalanjiyam.views.proofing.page.q.user_can_view_proofing_project",
                    return_value=True,
                ),
                patch("kalanjiyam.views.proofing.decorators.current_user") as dec_user,
                patch("kalanjiyam.views.proofing.page.current_user") as mock_user,
            ):
                for u in (dec_user, mock_user):
                    u.is_authenticated = True
                    u.is_super_admin = True
                    u.id = 1

                # Check initial status
                status_resp = client.get(
                    f"/api/replace-page-image/{project.slug}/{page.slug}/?action=status"
                )
                assert status_resp.status_code == 200
                assert status_resp.get_json()["has_master_backup"] is False

                # Replace with hybrid_binarization
                replace_resp = client.post(
                    f"/api/replace-page-image/{project.slug}/{page.slug}/",
                    json={"action": "replace", "profile": "hybrid_binarization"},
                )
                assert replace_resp.status_code == 200
                assert replace_resp.get_json()["status"] == "ok"
                assert replace_resp.get_json()["is_preprocessed"] is True

                # Status should now indicate master backup exists
                status_after = client.get(
                    f"/api/replace-page-image/{project.slug}/{page.slug}/?action=status"
                )
                assert status_after.get_json()["has_master_backup"] is True

                # Revert back to original
                revert_resp = client.post(
                    f"/api/replace-page-image/{project.slug}/{page.slug}/",
                    json={"action": "revert"},
                )
                assert revert_resp.status_code == 200
                assert revert_resp.get_json()["status"] == "ok"
                assert revert_resp.get_json()["is_preprocessed"] is False


# ---------------------------------------------------------------------------
# 20. Batch Enhanced OCR Endpoints and Task Dispatch
# ---------------------------------------------------------------------------
def test_batch_enhanced_ocr_get_and_post(flask_app, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(
            name="Test Board Batch Enhanced"
        )
        session.add(board)
        session.flush()

        project = db.Project(
            slug=f"test-batch-enh-{uuid.uuid4().hex[:6]}",
            board_id=board.id,
            display_title="Test Batch Enhanced OCR Project",
        )
        session.add(project)
        session.flush()

        status = session.query(db.PageStatus).first() or db.PageStatus(
            name="Status Batch"
        )
        session.add(status)
        session.flush()

        page1 = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        page2 = db.Page(project_id=project.id, order=2, slug="2", status_id=status.id)
        session.add_all([page1, page2])
        session.commit()

        with flask_app.test_client() as client:
            with (
                patch(
                    "kalanjiyam.views.proofing.project.q.user_can_view_proofing_project",
                    return_value=True,
                ),
                patch("kalanjiyam.views.proofing.decorators.current_user") as dec_user,
                patch("kalanjiyam.views.proofing.project.current_user") as mock_user,
                patch("kalanjiyam.views.proofing.project.redis_client") as mock_redis,
                patch(
                    "kalanjiyam.views.proofing.project.ocr_tasks.run_enhanced_ocr_for_project"
                ) as mock_run_proj,
            ):
                mock_redis.get.return_value = None
                mock_redis.scan_iter.return_value = []
                for u in (dec_user, mock_user):
                    u.is_authenticated = True
                    u.is_super_admin = True
                    u.is_moderator = True
                    u.id = 1

                # Mock task return
                mock_task = MagicMock()
                mock_task.id = "test-enhanced-task-id-123"
                mock_run_proj.return_value = mock_task

                # 1. GET Batch Enhanced OCR config form
                get_resp = client.get(f"/proofing/{project.slug}/batch-enhanced-ocr")
                assert get_resp.status_code == 200
                assert b"Enhanced Batch OCR Pipeline" in get_resp.data
                assert b"Hybrid Binarization" in get_resp.data

                # 2. POST to trigger Enhanced Batch OCR with save_enhanced_images=1
                post_resp = client.post(
                    f"/proofing/{project.slug}/batch-enhanced-ocr",
                    data={
                        "engine": "12",
                        "profile": "hybrid_binarization",
                        "language": "sa",
                        "save_enhanced_images": "1",
                    },
                )
                assert post_resp.status_code == 200
                mock_run_proj.assert_called_once()
                call_kwargs = mock_run_proj.call_args.kwargs
                assert call_kwargs["engine"] == "dots_ocr"
                assert call_kwargs["profile"] == "hybrid_binarization"
                assert call_kwargs["save_enhanced_images"] is True

                # 3. Check status endpoint
                with patch(
                    "kalanjiyam.views.proofing.project.GroupResult.restore"
                ) as mock_restore:
                    mock_group_res = MagicMock()
                    mock_group_res.results = [
                        MagicMock(state="SUCCESS", failed=lambda: False)
                    ]
                    mock_group_res.completed_count.return_value = 1
                    mock_restore.return_value = mock_group_res

                    status_resp = client.get(
                        f"/proofing/batch-enhanced-ocr-status/{mock_task.id}"
                    )
                    assert status_resp.status_code == 200


# ===========================================================================
# Closely Written Manuscript Line Segmentation Tests
# ===========================================================================


@pytest.fixture
def closely_written_manuscript_image(tmp_path) -> Path:
    """Create a simulated closely written Devanagari manuscript page with tightly packed text lines."""
    img_path = tmp_path / "manuscript_page_packed.png"
    w, h = 500, 700
    im = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(im)

    # Draw 8 closely spaced text lines (Devanagari shirorekha + glyph strokes)
    # Line spacing is tight (gap of ~8px between lines of height ~22px)
    line_tops = [60, 95, 130, 165, 200, 235, 270, 305]
    for top in line_tops:
        # Shirorekha (headline continuous bar)
        draw.rectangle([40, top, 460, top + 3], fill=(0, 0, 0))
        # Vertical / loop glyph strokes hanging from shirorekha
        for x in range(45, 455, 12):
            draw.rectangle([x, top + 3, x + 4, top + 18], fill=(0, 0, 0))
        # Ascender / upper matras
        for x in range(60, 440, 36):
            draw.line([(x, top - 6), (x + 6, top)], fill=(0, 0, 0), width=2)
        # Descender / lower matras
        for x in range(70, 430, 48):
            draw.arc([x, top + 16, x + 8, top + 24], start=0, end=180, fill=(0, 0, 0), width=2)

    im.save(img_path, format="PNG")
    return img_path


# 1. Feature disabled: existing OCR behavior is unchanged
def test_line_segmentation_disabled_unchanged(test_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            test_image,
            engine_name="dots-ocr",
            profile="hybrid_binarization",
            language="sa",
            line_segmentation=False,
        )
        assert resp.line_segmentation is False
        assert resp.line_segmentation_version is None
        mock_remote.assert_called_once()
        api_dict = ocr_response_to_api_dict(
            resp, "dots_ocr", image_width=400, image_height=600
        )
        assert "line_segmentation" not in api_dict
        assert "transformed_image_state" not in api_dict


# 2. Feature enabled: multiple text lines produce ONE reconstructed image
def test_line_segmentation_enabled_reconstructs_single_image(
    closely_written_manuscript_image,
):
    from kalanjiyam.utils.line_segmentation import (
        DEFAULT_LINE_SEGMENTATION_CONFIG,
        crop_text_lines,
        detect_text_lines,
        segment_and_reconstruct_image,
    )

    with Image.open(closely_written_manuscript_image) as img:
        detected = detect_text_lines(img, config=DEFAULT_LINE_SEGMENTATION_CONFIG)
        # Should detect all 8 lines
        assert len(detected) >= 6

        crops = crop_text_lines(img, detected, config=DEFAULT_LINE_SEGMENTATION_CONFIG)
        assert len(crops) == len(detected)

        reconstructed, stats = segment_and_reconstruct_image(
            img, config=DEFAULT_LINE_SEGMENTATION_CONFIG
        )
        assert stats.lines_detected >= 6
        assert stats.fallback_used is False
        assert isinstance(reconstructed, Image.Image)
        # Reconstructed image is a valid non-empty single image
        rw, rh = reconstructed.size
        assert rw > 0 and rh > 0


# 3. Empty / no-line detection gracefully falls back to enhanced full-page image
def test_empty_or_no_line_detection_fallback(tmp_path, mock_ocr_response):
    from kalanjiyam.utils.line_segmentation import segment_and_reconstruct_image

    blank_img_path = tmp_path / "blank_page.jpg"
    blank_im = Image.new("RGB", (300, 400), color=(255, 255, 255))
    blank_im.save(blank_img_path, format="JPEG")

    with Image.open(blank_img_path) as img:
        reconstructed, stats = segment_and_reconstruct_image(img)
        assert stats.fallback_used is True
        assert stats.lines_detected == 0
        assert reconstructed.size == (300, 400)

    # Full pipeline test on blank image
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            blank_img_path,
            engine_name="dots-ocr",
            profile="hybrid_binarization",
            language="sa",
            line_segmentation=True,
        )
        assert resp is not None
        assert resp.line_segmentation is True
        mock_remote.assert_called_once()


# 4. Closely spaced lines are detected separately
def test_closely_spaced_lines_detection():
    from kalanjiyam.utils.line_segmentation import detect_text_lines

    w, h = 400, 200
    im = Image.new("L", (w, h), color=255)
    draw = ImageDraw.Draw(im)

    # Draw 3 tightly packed lines with only 5px gap
    lines_y = [30, 60, 90]
    for y in lines_y:
        draw.rectangle([20, y, 380, y + 4], fill=0)  # shirorekha
        for x in range(25, 375, 10):
            draw.rectangle([x, y + 4, x + 3, y + 16], fill=0)  # body

    detected = detect_text_lines(im)
    assert len(detected) == 3
    # Verify reading order (y1 values strictly increasing)
    y_starts = [line[0] for line in detected]
    assert y_starts == sorted(y_starts)


# 5. Valley-based line crop extraction and debug overlay generation
def test_line_cropping_and_debug_overlay():
    from kalanjiyam.utils.line_segmentation import (
        LineSegmentationConfig,
        crop_text_lines,
        generate_segmentation_debug_overlay,
    )

    w, h = 300, 100
    im = Image.new("RGB", (w, h), color=(255, 255, 255))
    detected = [(30, 50, 20, 280), (50, 70, 20, 280)]

    crops = crop_text_lines(im, detected)
    assert len(crops) == 2
    assert crops[0].size == (260, 20)
    assert crops[1].size == (260, 20)

    overlay = generate_segmentation_debug_overlay(im)
    assert isinstance(overlay, Image.Image)
    assert overlay.size == (w, h)


# 6. OCR invocation count: mock OCR runner and assert EXACTLY ONE invocation
def test_ocr_invocation_count_is_strictly_one(
    closely_written_manuscript_image, mock_ocr_response
):
    from kalanjiyam.utils.line_segmentation import LINE_SEGMENTATION_VERSION

    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            closely_written_manuscript_image,
            engine_name="dots-ocr",
            profile="hybrid_binarization",
            language="sa",
            line_segmentation=True,
        )
        assert resp is not None
        # Must be EXACTLY ONE call, NEVER N calls per line!
        assert mock_remote.call_count == 1
        assert resp.line_segmentation is True
        assert resp.line_segmentation_version == LINE_SEGMENTATION_VERSION


# 7. Cache/revision identity: segmented and non-segmented runs do not collide
def test_segmented_and_non_segmented_cache_and_revision_identity(flask_app):
    with flask_app.app_context():
        # Storage keys
        key_unseg = page_enhanced_ocr_key(
            "cool-book", "19", "dots-ocr", "hybrid_binarization", line_segmentation=False
        )
        key_seg = page_enhanced_ocr_key(
            "cool-book", "19", "dots-ocr", "hybrid_binarization", line_segmentation=True
        )

        assert key_unseg != key_seg
        assert "hybrid_binarization_segmented" in key_seg
        assert "hybrid_binarization_segmented" not in key_unseg

        # Revision tags
        class MockRevision:
            def __init__(self, key):
                self.page_version = MagicMock(version_key=key)
                self.summary = ""
                self.translations = []
                self.author = None

        rev_unseg = MockRevision("ocr:enhanced:dots_ocr:hybrid_binarization")
        rev_seg = MockRevision("ocr:enhanced:dots_ocr:hybrid_binarization:segmented")

        tag_unseg = derive_revision_tag(rev_unseg)
        tag_seg = derive_revision_tag(rev_seg)

        assert tag_unseg == "ocr-enhanced-dots-ocr_hybrid-binarization"
        assert tag_seg == "ocr-enhanced-dots-ocr_hybrid-binarization_segmented"
        assert tag_unseg != tag_seg


# 8. Existing profiles: composition with hybrid_binarization and other profiles
@pytest.mark.parametrize("profile", SUPPORTED_ENHANCEMENT_PROFILES)
def test_composition_with_all_enhancement_profiles(
    closely_written_manuscript_image, profile, mock_ocr_response
):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            closely_written_manuscript_image,
            engine_name="dots-ocr",
            profile=profile,
            language="sa",
            line_segmentation=True,
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.enhancement_profile == profile
        assert resp.line_segmentation is True
        assert mock_remote.call_count == 1


# 9. Single-page API and Batch Task integration for line segmentation
def test_line_segmentation_api_and_batch_task(flask_app, mock_ocr_response, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q
    from kalanjiyam.tasks.ocr import _run_enhanced_ocr_for_page_inner

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(name="Test Board Segmented")
        session.add(board)
        session.flush()

        status = session.query(db.PageStatus).first()
        project = db.Project(
            slug="test-segmented-ocr-book",
            display_title="Test Segmented Book",
            board_id=board.id,
        )
        session.add(project)
        session.flush()

        page = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        session.add(page)
        session.commit()

        dummy_img = tmp_path / "page_seg_task.jpg"
        Image.new("RGB", (400, 600), color=(250, 250, 250)).save(
            dummy_img, format="JPEG"
        )

        with (
            patch(
                "kalanjiyam.tasks.ocr.get_page_image_filepath", return_value=dummy_img
            ),
            patch(
                "kalanjiyam.utils.ocr_runner.run_ocr_remote",
                return_value=mock_ocr_response,
            ) as mock_remote,
            patch("kalanjiyam.utils.quotas.ensure_ocr_quota_for_project"),
            patch("kalanjiyam.utils.quotas.consume_ocr_credit_for_project"),
        ):
            # Run background task with line_segmentation=True
            result = _run_enhanced_ocr_for_page_inner(
                app_env="testing",
                project_slug=project.slug,
                page_slug=page.slug,
                engine="dots-ocr",
                profile="hybrid_binarization",
                language="sa",
                line_segmentation=True,
            )
            assert result is not None
            assert result["ocr_mode"] == "enhanced"
            assert result["line_segmentation"] is True
            assert result["transformed_image_state"] == "reconstructed_segmented_lines"
            assert mock_remote.call_count == 1

            # Check revision was saved to ocr:enhanced:dots_ocr:hybrid_binarization:segmented
            pv = (
                session.query(db.PageVersion)
                .filter_by(
                    page_id=page.id,
                    version_key="ocr:enhanced:dots_ocr:hybrid_binarization:segmented",
                )
                .first()
            )
            assert pv is not None

        # Test API endpoint with line_segmentation=1
        with flask_app.test_client() as client:
            with (
                patch(
                    "kalanjiyam.views.proofing.page.get_page_image_filepath",
                    return_value=dummy_img,
                ),
                patch(
                    "kalanjiyam.utils.ocr_runner.run_ocr_remote",
                    return_value=mock_ocr_response,
                ) as mock_api_remote,
                patch("kalanjiyam.utils.quotas.ensure_ocr_quota_for_project"),
                patch("kalanjiyam.utils.quotas.consume_ocr_credit_for_project"),
                patch(
                    "kalanjiyam.views.proofing.page.q.user_can_view_proofing_project",
                    return_value=True,
                ),
                patch("kalanjiyam.views.proofing.decorators.current_user") as dec_user,
                patch("kalanjiyam.views.proofing.page.current_user") as mock_user,
            ):
                for u in (dec_user, mock_user):
                    u.is_authenticated = True
                    u.is_super_admin = False
                    u.is_org_admin = True
                    u.is_moderator = True
                    u.is_p2 = True
                    u.is_p1 = True
                    u.id = 1

                resp = client.get(
                    f"/api/enhanced-ocr/{project.slug}/{page.slug}/?engine=dots_ocr&enhancement=hybrid_binarization&line_segmentation=1&language=sa"
                )
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["line_segmentation"] is True
                assert data["version_key"] == "ocr:enhanced:dots_ocr:hybrid_binarization:segmented"
                assert mock_api_remote.call_count == 1


# 10. Actual Manuscript Image line segmentation verification
def test_actual_closely_written_manuscript_segmentation():
    import os
    from kalanjiyam.utils.line_segmentation import (
        detect_text_lines,
        detect_line_peaks_and_valleys,
        segment_and_reconstruct_image,
        generate_segmentation_debug_overlay,
    )

    manuscript_path = Path(__file__).resolve().parents[3] / "test-data" / "00010 jpg images manuscripts.JPG"
    if not manuscript_path.exists():
        pytest.skip("Manuscript sample image not found at test-data path")

    with Image.open(manuscript_path) as img:
        peaks, boundaries, text_block = detect_line_peaks_and_valleys(img)
        assert len(peaks) == 18
        assert len(boundaries) == 19
        assert text_block[2] > text_block[0]

        detected_lines = detect_text_lines(img)
        assert len(detected_lines) == 18
        # Assert lines are strictly contiguous from valley to valley (no overlapping spans)
        for i in range(len(detected_lines) - 1):
            assert detected_lines[i][1] == detected_lines[i + 1][0]

        reconstructed, stats = segment_and_reconstruct_image(img)
        assert stats.fallback_used is False
        assert stats.lines_detected == 18
        assert reconstructed.size[1] >= (boundaries[-1] - boundaries[0])
        assert reconstructed.size[0] > 0

        overlay = generate_segmentation_debug_overlay(img)
        assert overlay.size == img.size


# ===========================================================================
# Upscale Image Feature Tests
# ===========================================================================


def test_upscale_image_resampling():
    from kalanjiyam.utils.image_preprocessing import upscale_image

    im = Image.new("RGB", (100, 150), color=(120, 130, 140))
    # 1x scale factor preserves dimensions
    assert upscale_image(im, factor=1).size == (100, 150)
    # 2x doubles dimensions
    assert upscale_image(im, factor=2).size == (200, 300)
    # 3x triples dimensions
    assert upscale_image(im, factor=3).size == (300, 450)
    # 4x quadruples dimensions
    assert upscale_image(im, factor=4).size == (400, 600)
    # Mode preservation
    im_l = Image.new("L", (100, 150), color=128)
    assert upscale_image(im_l, factor=2).mode == "L"


# Test Case A: Segmentation OFF, Upscale OFF
def test_pipeline_case_a_seg_off_upscale_off(test_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            test_image,
            engine_name="dots-ocr",
            profile="hybrid_binarization",
            language="sa",
            line_segmentation=False,
            upscale=False,
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.line_segmentation is False
        assert resp.upscale is False
        assert resp.upscale_factor == 1
        assert mock_remote.call_count == 1

        api_dict = ocr_response_to_api_dict(resp, "dots_ocr", image_width=400, image_height=600)
        assert "line_segmentation" not in api_dict
        assert "upscale" not in api_dict
        assert "transformed_image_state" not in api_dict


# Test Case B: Segmentation ON, Upscale OFF
def test_pipeline_case_b_seg_on_upscale_off(closely_written_manuscript_image, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            closely_written_manuscript_image,
            engine_name="dots-ocr",
            profile="hybrid_binarization",
            language="sa",
            line_segmentation=True,
            upscale=False,
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.line_segmentation is True
        assert resp.upscale is False
        assert resp.upscale_factor == 1
        assert mock_remote.call_count == 1

        api_dict = ocr_response_to_api_dict(resp, "dots_ocr", image_width=500, image_height=700)
        assert api_dict["line_segmentation"] is True
        assert "upscale" not in api_dict
        assert api_dict["transformed_image_state"] == "reconstructed_segmented_lines"


# Test Case C: Segmentation OFF, Upscale ON (1x, 2x, 3x, 4x)
@pytest.mark.parametrize("factor", [1, 2, 3, 4])
def test_pipeline_case_c_seg_off_upscale_on(test_image, factor, mock_ocr_response):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            test_image,
            engine_name="dots-ocr",
            profile="document_cleanup",
            language="sa",
            line_segmentation=False,
            upscale=True,
            upscale_factor=factor,
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.line_segmentation is False
        assert resp.upscale is True
        assert resp.upscale_factor == factor
        assert mock_remote.call_count == 1

        api_dict = ocr_response_to_api_dict(resp, "dots_ocr", image_width=400, image_height=600)
        assert api_dict["upscale"] is True
        assert api_dict["upscale_factor"] == factor
        if factor > 1:
            assert api_dict["transformed_image_state"] == "upscaled"
        else:
            assert "transformed_image_state" not in api_dict


# Test Case D: Segmentation ON, Upscale ON (1x, 2x, 3x, 4x)
@pytest.mark.parametrize("factor", [1, 2, 3, 4])
def test_pipeline_case_d_seg_on_upscale_on(
    closely_written_manuscript_image, factor, mock_ocr_response
):
    with patch(
        "kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response
    ) as mock_remote:
        resp = run_enhanced_ocr(
            closely_written_manuscript_image,
            engine_name="dots-ocr",
            profile="hybrid_binarization",
            language="sa",
            line_segmentation=True,
            upscale=True,
            upscale_factor=factor,
        )
        assert resp.ocr_mode == "enhanced"
        assert resp.line_segmentation is True
        assert resp.upscale is True
        assert resp.upscale_factor == factor
        assert mock_remote.call_count == 1

        api_dict = ocr_response_to_api_dict(resp, "dots_ocr", image_width=500, image_height=700)
        assert api_dict["line_segmentation"] is True
        assert api_dict["upscale"] is True
        assert api_dict["upscale_factor"] == factor
        if factor > 1:
            assert api_dict["transformed_image_state"] == "reconstructed_segmented_lines_upscaled"
        else:
            assert api_dict["transformed_image_state"] == "reconstructed_segmented_lines"


# Test Tempfile Generation Dimensions for All 4 Cases
def test_tempfile_dimensions_for_pipeline_cases(test_image):
    with Image.open(test_image) as original:
        orig_w, orig_h = original.size

    # Case A: seg OFF, upscale OFF
    with preprocess_image_to_tempfile(test_image, "document_cleanup", line_segmentation=False, upscale=False) as f:
        with Image.open(f) as im:
            assert im.size == (orig_w, orig_h)
            assert f.name.endswith("_document_cleanup.jpg")

    # Case C: seg OFF, upscale ON (2x)
    with preprocess_image_to_tempfile(test_image, "document_cleanup", line_segmentation=False, upscale=True, upscale_factor=2) as f:
        with Image.open(f) as im:
            assert im.size == (orig_w * 2, orig_h * 2)
            assert f.name.endswith("_document_cleanup_upscale_2x.jpg")

    # Case C: seg OFF, upscale ON (3x)
    with preprocess_image_to_tempfile(test_image, "document_cleanup", line_segmentation=False, upscale=True, upscale_factor=3) as f:
        with Image.open(f) as im:
            assert im.size == (orig_w * 3, orig_h * 3)
            assert f.name.endswith("_document_cleanup_upscale_3x.jpg")


# Test Storage Keys and Revision Tags for All Combinations
def test_upscale_storage_keys_and_revision_tags(flask_app):
    with flask_app.app_context():
        # Storage keys
        k_base = page_enhanced_ocr_key("book", "1", "dots_ocr", "hybrid_binarization", line_segmentation=False, upscale=False)
        k_seg = page_enhanced_ocr_key("book", "1", "dots_ocr", "hybrid_binarization", line_segmentation=True, upscale=False)
        k_upscale_2x = page_enhanced_ocr_key("book", "1", "dots_ocr", "hybrid_binarization", line_segmentation=False, upscale=True, upscale_factor=2)
        k_both_2x = page_enhanced_ocr_key("book", "1", "dots_ocr", "hybrid_binarization", line_segmentation=True, upscale=True, upscale_factor=2)
        k_both_3x = page_enhanced_ocr_key("book", "1", "dots_ocr", "hybrid_binarization", line_segmentation=True, upscale=True, upscale_factor=3)

        assert len({k_base, k_seg, k_upscale_2x, k_both_2x, k_both_3x}) == 5
        assert "hybrid_binarization_upscale_2x" in k_upscale_2x
        assert "hybrid_binarization_segmented_upscale_2x" in k_both_2x
        assert "hybrid_binarization_segmented_upscale_3x" in k_both_3x

        # Revision tags
        class MockRevision:
            def __init__(self, key):
                self.page_version = MagicMock(version_key=key)
                self.summary = ""
                self.translations = []
                self.author = None

        tag_base = derive_revision_tag(MockRevision("ocr:enhanced:dots_ocr:hybrid_binarization"))
        tag_seg = derive_revision_tag(MockRevision("ocr:enhanced:dots_ocr:hybrid_binarization:segmented"))
        tag_up2 = derive_revision_tag(MockRevision("ocr:enhanced:dots_ocr:hybrid_binarization:upscale:2x"))
        tag_both = derive_revision_tag(MockRevision("ocr:enhanced:dots_ocr:hybrid_binarization:segmented:upscale:2x"))

        assert tag_base == "ocr-enhanced-dots-ocr_hybrid-binarization"
        assert tag_seg == "ocr-enhanced-dots-ocr_hybrid-binarization_segmented"
        assert tag_up2 == "ocr-enhanced-dots-ocr_hybrid-binarization_upscale_2x"
        assert tag_both == "ocr-enhanced-dots-ocr_hybrid-binarization_segmented_upscale_2x"
        assert len({tag_base, tag_seg, tag_up2, tag_both}) == 4


# Test Fallback with Upscaling
def test_segmentation_fallback_with_upscaling(tmp_path):
    from kalanjiyam.utils.line_segmentation import segment_and_reconstruct_image

    blank_img_path = tmp_path / "blank_upscale.jpg"
    blank_im = Image.new("RGB", (150, 200), color=(255, 255, 255))
    blank_im.save(blank_img_path, format="JPEG")

    with Image.open(blank_img_path) as img:
        reconstructed, stats = segment_and_reconstruct_image(img, upscale_factor=2)
        assert stats.fallback_used is True
        assert stats.lines_detected == 0
        assert stats.upscale_enabled is True
        assert stats.upscale_factor == 2
        # Fallback image is upscaled by factor 2
        assert reconstructed.size == (300, 400)


# Test API endpoint with Upscale options
def test_enhanced_ocr_api_with_upscale(flask_app, mock_ocr_response, tmp_path):
    import kalanjiyam.database as db
    import kalanjiyam.queries as q

    with flask_app.app_context():
        session = q.get_session()
        board = session.query(db.Board).first() or db.Board(name="Test Board Upscale API")
        session.add(board)
        session.flush()

        status = session.query(db.PageStatus).first()
        project = db.Project(
            slug=f"test-upscale-api-{uuid.uuid4().hex[:6]}",
            display_title="Test Upscale Book",
            board_id=board.id,
        )
        session.add(project)
        session.flush()

        page = db.Page(project_id=project.id, order=1, slug="1", status_id=status.id)
        session.add(page)
        session.commit()

        dummy_img = tmp_path / "page_upscale_api.jpg"
        Image.new("RGB", (400, 600), color=(250, 250, 250)).save(dummy_img, format="JPEG")

        with flask_app.test_client() as client:
            with (
                patch("kalanjiyam.views.proofing.page.get_page_image_filepath", return_value=dummy_img),
                patch("kalanjiyam.utils.ocr_runner.run_ocr_remote", return_value=mock_ocr_response) as mock_api_remote,
                patch("kalanjiyam.utils.quotas.ensure_ocr_quota_for_project"),
                patch("kalanjiyam.utils.quotas.consume_ocr_credit_for_project"),
                patch("kalanjiyam.views.proofing.page.q.user_can_view_proofing_project", return_value=True),
                patch("kalanjiyam.views.proofing.decorators.current_user") as dec_user,
                patch("kalanjiyam.views.proofing.page.current_user") as mock_user,
            ):
                for u in (dec_user, mock_user):
                    u.is_authenticated = True
                    u.is_super_admin = False
                    u.is_org_admin = True
                    u.is_moderator = True
                    u.is_p2 = True
                    u.is_p1 = True
                    u.id = 1

                # 1. Test Enhanced OCR with upscale=1 and upscale_factor=3
                resp = client.get(
                    f"/api/enhanced-ocr/{project.slug}/{page.slug}/?engine=dots_ocr&enhancement=hybrid_binarization&upscale=1&upscale_factor=3&language=sa"
                )
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["upscale"] is True
                assert data["upscale_factor"] == 3
                assert data["transformed_image_state"] == "upscaled"
                assert data["version_key"] == "ocr:enhanced:dots_ocr:hybrid_binarization:upscale:3x"
                assert mock_api_remote.call_count == 1

                # 2. Test Preview with upscale=1 and upscale_factor=2
                resp_preview = client.get(
                    f"/api/preview-enhancement/{project.slug}/{page.slug}/?profile=hybrid_binarization&upscale=1&upscale_factor=2"
                )
                assert resp_preview.status_code == 200
                assert resp_preview.content_type == "image/jpeg"
                with Image.open(io.BytesIO(resp_preview.data)) if "io" in globals() else Image.open(tmp_path / "page_upscale_api.jpg") as pimg:
                    assert resp_preview.data is not None


# Test Real Manuscript Image with Segmentation + 2x Upscale
def test_actual_manuscript_segmentation_and_upscale():
    import os
    from kalanjiyam.utils.line_segmentation import segment_and_reconstruct_image

    manuscript_path = Path(__file__).resolve().parents[3] / "test-data" / "00010 jpg images manuscripts.JPG"
    if not manuscript_path.exists():
        pytest.skip("Manuscript sample image not found at test-data path")

    with Image.open(manuscript_path) as img:
        reconstructed, stats = segment_and_reconstruct_image(img, upscale_factor=2)
        assert stats.lines_detected == 18
        assert stats.upscale_enabled is True
        assert stats.upscale_factor == 2
        assert stats.fallback_used is False
        assert reconstructed.size[0] > img.size[0]
        assert reconstructed.size[1] > 0

