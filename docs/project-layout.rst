Project Layout
=============

This document provides a high-level overview of Kalanjiyam's codebase structure.

Directory Structure
------------------

The main directories in the Kalanjiyam repository are:

- `kalanjiyam` contains the main server code.
- `docs` contains this documentation.
- `migrations` contains database migration files.
- `scripts` contains utility scripts for development and deployment.
- `test` contains our test suite.
- `deploy` contains deployment configuration files.

The `kalanjiyam` Directory
-------------------------

`kalanjiyam` contains the main server code, and this is where you will spend most
of your time when working on Kalanjiyam.

Key files:

- `__init__.py` is the main entrypoint to Kalanjiyam. It creates the app, sets up
  extensions, and registers blueprints.

- `config.py` contains configuration management code.

- `database.py` contains database connection and session management code.

- `models/` contains SQLAlchemy model definitions for our database tables.

- `views/` contains Flask view functions and blueprints.

- `templates/` contains Jinja2 templates for our HTML pages.

- `static/` contains CSS, JavaScript, and other static assets.

- `utils/` contains utility functions and helper modules.

- `seed/` contains scripts that prepare text and parse data for the data repos that Kalanjiyam depends on.

- `tasks/` contains Celery task definitions for background jobs.

- `views` contains Kalanjiyam's view logic, which combines most of the above to
  create the actual web pages that users see.

The `views` Directory
--------------------

The `views` directory contains all of Kalanjiyam's view logic. Views are organized
by feature:

- `about.py` contains basic pages about Kalanjiyam: our mission, values, etc.

- `auth.py` contains authentication-related views (login, logout, etc.).

- `dictionaries.py` contains dictionary lookup functionality.

- `proofing/` contains the proofreading interface that Kalanjiyam uses.

- `reader/` contains the text reading interface.

- `site.py` contains basic site pages like the homepage.

The `models` Directory
---------------------

The `models` directory contains SQLAlchemy model definitions. These models define
the structure of our database tables and provide an object-oriented interface
for working with our data.

Key models include:

- `User` represents users of the platform
- `Text` represents texts in our collection
- `Project` represents proofreading projects
- `Dictionary` represents dictionary entries

The `seed` Directory
-------------------

The `seed` directory contains scripts that prepare and load data into Kalanjiyam's
database. This includes:

- Text data from various sources
- Dictionary data from traditional dictionaries
- Parse data for grammatical analysis
- User and project data for development

The `static` Directory
---------------------

The `static` directory contains all of Kalanjiyam's static assets:

- `css/` contains stylesheets
- `js/` contains JavaScript files
- `images/` contains images and icons
- `fonts/` contains custom fonts

The `templates` Directory
------------------------

The `templates` directory contains Jinja2 templates for all of Kalanjiyam's HTML
pages. Templates are organized by feature, similar to the views directory.

Key template files:

- `base.html` is the base template that all other templates extend
- `about/` contains templates for about pages
- `proofing/` contains templates for the proofreading interface
- `reader/` contains templates for the text reading interface
