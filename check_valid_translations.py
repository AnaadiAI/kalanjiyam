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
    
    # Group by language pairs
    language_pairs = {}
    for translation in translations:
        pair = f"{translation.source_language}->{translation.target_language}"
        if pair not in language_pairs:
            language_pairs[pair] = 0
        language_pairs[pair] += 1
    
    print("\nTranslations by language pair:")
    for pair, count in language_pairs.items():
        print(f"  {pair}: {count}")
    
    # Show a few examples of valid translations
    print("\nSample valid translations:")
    for translation in translations[:5]:
        revision = session.query(db.Revision).filter_by(id=translation.revision_id).first()
        if revision:
            # Check if this is a valid translation (not identical to original)
            if translation.content.strip() != revision.content.strip():
                print(f"  Translation {translation.id}: {translation.source_language}->{translation.target_language}")
                print(f"    Page: {translation.page_id}, Revision: {translation.revision_id}")
                print(f"    Original preview: {revision.content[:50]}...")
                print(f"    Translated preview: {translation.content[:50]}...")
                print()
