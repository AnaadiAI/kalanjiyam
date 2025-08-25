#!/usr/bin/env python3

from config import create_config_only_app
from kalanjiyam import database as db
from kalanjiyam import queries as q

app = create_config_only_app('development')

with app.app_context():
    session = q.get_session()
    
    # Get the project
    project = q.project('aryabhatiya-by-kripa-shankar-shukla')
    if not project:
        print("Project not found")
        exit(1)
    
    print(f"Project: {project.display_title}")
    print(f"Total pages: {len(project.pages)}")
    
    # Check each page
    pages_with_revisions = 0
    pages_with_translations = 0
    pages_without_translations = 0
    
    print("\nChecking translation coverage:")
    print("-" * 50)
    
    for page in project.pages:
        if page.revisions:
            pages_with_revisions += 1
            latest_revision = page.revisions[-1]
            
            # Check if this page has any translations
            translations = session.query(db.Translation).filter_by(
                page_id=page.id,
                revision_id=latest_revision.id
            ).all()
            
            if translations:
                pages_with_translations += 1
                print(f"Page {page.slug}: ✅ Has {len(translations)} translation(s)")
                for t in translations:
                    print(f"  - {t.source_language}->{t.target_language} ({t.translation_engine})")
            else:
                pages_without_translations += 1
                print(f"Page {page.slug}: ❌ No translations")
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Pages with revisions: {pages_with_revisions}")
    print(f"Pages with translations: {pages_with_translations}")
    print(f"Pages without translations: {pages_without_translations}")
    print(f"Translation coverage: {pages_with_translations}/{pages_with_revisions} ({pages_with_translations/pages_with_revisions*100:.1f}%)")
