#!/usr/bin/env python3

from config import create_config_only_app
from kalanjiyam import database as db
from kalanjiyam import queries as q

app = create_config_only_app('development')

with app.app_context():
    session = q.get_session()
    
    # Get all projects
    projects = session.query(db.Project).all()
    print(f"Total projects: {len(projects)}")
    
    for project in projects:
        print(f"Project: {project.display_title} (slug: {project.slug})")
        print(f"  Pages: {len(project.pages)}")
        if project.pages:
            page = project.pages[0]
            print(f"  First page: {page.slug} (ID: {page.id})")
            if page.revisions:
                print(f"  Latest revision: {page.revisions[-1].id}")
        print()
