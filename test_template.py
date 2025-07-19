#!/usr/bin/env python3

from kalanjiyam import create_app

app = create_app('development')

with app.app_context():
    # Check if kalanjiyam_locales is available
    locales = app.jinja_env.globals.get('kalanjiyam_locales')
    print('kalanjiyam_locales available:', locales is not None)
    if locales:
        print('Number of locales:', len(locales))
        for locale in locales:
            print(f'  - {locale.code}: {locale.text}')
    
    # Try to render the index template with a request context
    try:
        from flask import render_template
        with app.test_request_context('/'):
            rendered = render_template('index.html')
            print('Template rendered successfully')
            print('Length of rendered content:', len(rendered))
            print('Contains "Explore the library":', 'Explore the library' in rendered)
            print('Contains "kalanjiyam_locales":', 'kalanjiyam_locales' in rendered)
            # Check if the language selector is rendered
            print('Contains "தமிழ்":', 'தமிழ்' in rendered)
            print('Contains "English":', 'English' in rendered)
    except Exception as e:
        print('Error rendering template:', e)
        import traceback
        traceback.print_exc() 