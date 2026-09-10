import tempfile

import fitz
from PIL import Image

import kalanjiyam.queries as q
import kalanjiyam.tasks.projects as projects
import kalanjiyam.tasks.utils
from kalanjiyam.utils.storage import (
    get_storage,
    page_image_key,
    pdf_key,
    project_raw_image_key,
)


def _create_sample_pdf(output_path: str, num_pages: int):
    """Create a toy PDF with 10 pages."""
    doc = fitz.open()
    for i in range(1, num_pages + 1):
        page = doc.new_page()
        where = fitz.Point(50, 50)
        page.insert_text(where, f"This is page {i}", fontsize=30)
    doc.save(output_path)


def test_create_project_inner(flask_app):
    with flask_app.app_context():
        project = q.project("cool-project")
        assert project is None

        f = tempfile.NamedTemporaryFile()
        _create_sample_pdf(f.name, num_pages=10)

        source_pdf_key = pdf_key("cool-project")
        get_storage().save(source_pdf_key, f.name)

        projects.create_project_inner(
            display_title="Cool project",
            pdf_key=source_pdf_key,
            app_environment=flask_app.config["KALANJIYAM_ENVIRONMENT"],
            creator_id=1,
            task_status=kalanjiyam.tasks.utils.LocalTaskStatus(),
        )

        project = q.project("cool-project")
        assert project
        assert len(project.pages) == 10
        # Page images land in storage under the project's key prefix.
        storage = get_storage()
        assert storage.exists(page_image_key("cool-project", "1"))
        assert storage.exists(page_image_key("cool-project", "10"))
        # Source PDF is deleted after page extraction to save space, and its size is saved in DB
        assert not storage.exists(source_pdf_key)
        assert project.extracted_metadata is not None
        assert project.extracted_metadata["source_file"]["size_bytes"] > 0
        assert project.extracted_metadata["source_file"]["deleted_after_extraction"] is True


def test_create_project_inner_with_images(flask_app):
    with flask_app.app_context():
        project = q.project("images-project")
        assert project is None

        storage = get_storage()
        image_keys = []
        for i in range(1, 4):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                im = Image.new("RGB", (100, 100), color="blue")
                im.save(tmp.name, "JPEG")
                raw_key = project_raw_image_key("images-project", f"{i}.jpg")
                storage.save(raw_key, tmp.name)
                image_keys.append(raw_key)

        projects.create_project_inner(
            display_title="Images project",
            image_keys=image_keys,
            app_environment=flask_app.config["KALANJIYAM_ENVIRONMENT"],
            creator_id=1,
            task_status=kalanjiyam.tasks.utils.LocalTaskStatus(),
        )

        project = q.project("images-project")
        assert project
        assert len(project.pages) == 3
        # Page images exist
        assert storage.exists(page_image_key("images-project", "1"))
        assert storage.exists(page_image_key("images-project", "2"))
        assert storage.exists(page_image_key("images-project", "3"))
        # Raw staging images were deleted
        for raw_key in image_keys:
            assert not storage.exists(raw_key)
        assert project.extracted_metadata is not None
        assert project.extracted_metadata["source_file"]["type"] == "images"
        assert project.extracted_metadata["source_file"]["num_images"] == 3
        assert project.extracted_metadata["source_file"]["deleted_after_extraction"] is True

        # Verify output image has 200 DPI metadata
        page1_path = storage.local_copy(page_image_key("images-project", "1"))
        with Image.open(page1_path) as saved_im:
            assert saved_im.info.get("dpi") == (200, 200)


def test_process_page_image_for_storage_high_dpi():
    """Verify 300 DPI scan is resampled down to 200 DPI."""
    from kalanjiyam.tasks.projects import process_page_image_for_storage

    im = Image.new("RGB", (3000, 3000), color="white")
    im.info["dpi"] = (300, 300)
    processed = process_page_image_for_storage(im)
    assert processed.size == (2000, 2000)


def test_process_page_image_for_storage_phone_camera():
    """Verify high-res phone camera photo is resampled to 200 DPI standard document height (max edge 2400)."""
    from kalanjiyam.tasks.projects import process_page_image_for_storage

    im = Image.new("RGB", (3000, 4000), color="white")
    im.info["dpi"] = (72, 72)
    processed = process_page_image_for_storage(im)
    assert processed.size == (1800, 2400)


def test_process_page_image_for_storage_never_upscales():
    """Verify lower resolution images are never upscaled."""
    from kalanjiyam.tasks.projects import process_page_image_for_storage

    im = Image.new("RGB", (800, 1200), color="white")
    im.info["dpi"] = (150, 150)
    processed = process_page_image_for_storage(im)
    assert processed.size == (800, 1200)


def test_create_batch_image_projects_inner(flask_app):
    with flask_app.app_context():
        storage = get_storage()
        projects_data = []

        for name in ["batch-proj-1", "batch-proj-2"]:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                im = Image.new("RGB", (100, 100), color="green")
                im.save(tmp.name, "JPEG")
                raw_key = project_raw_image_key(name, "1.jpg")
                storage.save(raw_key, tmp.name)
                projects_data.append({
                    "display_title": name.replace("-", " ").title(),
                    "image_keys": [raw_key],
                })

        res = projects.create_batch_image_projects_inner(
            projects_data=projects_data,
            app_environment=flask_app.config["KALANJIYAM_ENVIRONMENT"],
            creator_id=1,
            task_status=kalanjiyam.tasks.utils.LocalTaskStatus(),
        )

        assert res["total"] == 2
        assert res["current"] == 2
        assert res["doc_type"] == "batch_images"
        assert len(res["created_slugs"]) == 2

        p1 = q.project("batch-proj-1")
        p2 = q.project("batch-proj-2")
        assert p1 is not None
        assert p2 is not None
        assert len(p1.pages) == 1
        assert len(p2.pages) == 1
        assert storage.exists(page_image_key("batch-proj-1", "1"))
        assert storage.exists(page_image_key("batch-proj-2", "1"))


def test_create_batch_pdf_projects_inner(flask_app):
    with flask_app.app_context():
        storage = get_storage()
        projects_data = []

        for name, page_count in [("batch-pdf-1", 2), ("batch-pdf-2", 3)]:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                _create_sample_pdf(tmp.name, num_pages=page_count)
                source_key = pdf_key(name)
                storage.save(source_key, tmp.name)
                projects_data.append({
                    "display_title": name.replace("-", " ").title(),
                    "pdf_key": source_key,
                })

        res = projects.create_batch_pdf_projects_inner(
            projects_data=projects_data,
            app_environment=flask_app.config["KALANJIYAM_ENVIRONMENT"],
            creator_id=1,
            task_status=kalanjiyam.tasks.utils.LocalTaskStatus(),
        )

        assert res["total"] == 2
        assert res["current"] == 2
        assert res["doc_type"] == "batch_pdfs"
        assert len(res["created_slugs"]) == 2

        p1 = q.project("batch-pdf-1")
        p2 = q.project("batch-pdf-2")
        assert p1 is not None
        assert p2 is not None
        assert len(p1.pages) == 2
        assert len(p2.pages) == 3

        # Page images exist
        assert storage.exists(page_image_key("batch-pdf-1", "1"))
        assert storage.exists(page_image_key("batch-pdf-1", "2"))
        assert storage.exists(page_image_key("batch-pdf-2", "1"))
        assert storage.exists(page_image_key("batch-pdf-2", "3"))

        # Staged PDFs should have been cleaned up after page extraction
        for item in projects_data:
            assert not storage.exists(item["pdf_key"])




