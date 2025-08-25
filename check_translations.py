#!/usr/bin/env python3

from config import create_config_only_app
from kalanjiyam import database as db
from kalanjiyam import queries as q

app = create_config_only_app('development')

with app.app_context():
    session = q.get_session()
    translations = session.query(db.Translation).all()
    print(f'Total translations: {len(translations)}')
    
    if translations:
        for t in translations[:5]:
            print(f'Translation {t.id}: {t.source_language}->{t.target_language} for page {t.page_id}, revision {t.revision_id}')
            print(f'  Content preview: {t.content[:100]}...')
    else:
        print('No translations found in database')
