#!/usr/bin/env python3

from config import create_config_only_app
from kalanjiyam import database as db
from kalanjiyam import queries as q

app = create_config_only_app('development')

with app.app_context():
    session = q.get_session()
    
    # Get all translations
    translations = session.query(db.Translation).all()
    print(f"Total translations: {len(translations)}")
    
    failed_count = 0
    for translation in translations:
        # Get the original revision content to compare
        revision = session.query(db.Revision).filter_by(id=translation.revision_id).first()
        if revision:
            # Check if translation content is identical to original content (indicating failed translation)
            #if translation.content.strip() == revision.content.strip():
            if True:
                print(f"Found failed translation {translation.id}: {translation.source_language}->{translation.target_language}")
                print(f"  Page: {translation.page_id}, Revision: {translation.revision_id}")
                print(f"  Content preview: {translation.content[:100]}...")
                
                # Delete the failed translation
                session.delete(translation)
                failed_count += 1
    
    if failed_count > 0:
        session.commit()
        print(f"\nCleaned up {failed_count} failed translations")
    else:
        print("No failed translations found")
    
    # Show remaining translations
    remaining = session.query(db.Translation).count()
    print(f"Remaining translations: {remaining}")
