#!/usr/bin/env python3

from config import create_config_only_app
from kalanjiyam import database as db
from kalanjiyam import queries as q

app = create_config_only_app('development')

with app.app_context():
    session = q.get_session()
    
    # Get a specific project and page
    project = q.project('aryabhatiya-by-kripa-shankar-shukla')
    if project:
        print(f"Project: {project.display_title}")
        
        # Get first page
        if project.pages:
            page = project.pages[0]
            print(f"Page: {page.slug}")
            print(f"Page ID: {page.id}")
            
            if page.revisions:
                latest_revision = page.revisions[-1]
                print(f"Latest revision ID: {latest_revision.id}")
                
                # Check for translations
                translation = session.query(db.Translation).filter_by(
                    page_id=page.id,
                    revision_id=latest_revision.id
                ).first()
                
                if translation:
                    print(f"Found translation: {translation.id}")
                    print(f"Source: {translation.source_language} -> Target: {translation.target_language}")
                    print(f"Engine: {translation.translation_engine}")
                    print(f"Content preview: {translation.content[:200]}...")
                else:
                    print("No translation found for this page/revision")
                    
                    # Check if there are any translations for this page
                    all_translations = session.query(db.Translation).filter_by(page_id=page.id).all()
                    print(f"Total translations for this page: {len(all_translations)}")
                    for t in all_translations:
                        print(f"  Translation {t.id}: rev {t.revision_id}, {t.source_language}->{t.target_language}")
            else:
                print("No revisions found for this page")
        else:
            print("No pages found for this project")
    else:
        print("Project not found")
