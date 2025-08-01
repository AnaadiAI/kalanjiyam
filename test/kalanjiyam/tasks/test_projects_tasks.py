import tempfile

import fitz

import kalanjiyam.queries as q
import kalanjiyam.tasks.projects as projects
import kalanjiyam.tasks.utils


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

        projects.create_project_inner(
            display_title="Cool project",
            pdf_path=f.name,
            output_dir=flask_app.config["UPLOAD_FOLDER"],
            app_environment=flask_app.config["KALANJIYAM_ENVIRONMENT"],
            creator_id=1,
            task_status=kalanjiyam.tasks.utils.LocalTaskStatus(),
        )

        project = q.project("cool-project")
        assert project
        assert len(project.pages) == 10
