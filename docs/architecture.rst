Architecture
===========

This document provides a high-level overview of Kalanjiyam's technical architecture.

Overview
--------

Kalanjiyam is a web application built with Flask that provides access to Siddha Knowledge Systems
literature. The application consists of several key components:

- **Web server**: Flask application that serves HTML pages and API endpoints
- **Database**: SQLite database (development) or PostgreSQL (production) for storing data
- **Background tasks**: Celery for handling long-running tasks like OCR processing
- **Static assets**: CSS, JavaScript, and images served directly by the web server

Data Sources
------------

Kalanjiyam's data comes from several sources:

- **Text data**: Siddha texts from various manuscripts and published sources
- **Dictionary data**: Traditional Siddha and Tamil dictionaries
- **Parse data**: Grammatical analysis data from the Digital Corpus of Siddha
  in `kalanjiyam.seed.dcs`. (Our raw upstream parse data uses the CoNLL-U format, but
  we transform it into a more suitable format for our needs.)

Database
--------

We use SQLAlchemy as our ORM and SQLite for development. SQLite is fast and great for prototyping. Kalanjiyam is a read-heavy website, so
SQLite's performance characteristics work well for our use case.

For production, we use PostgreSQL for better concurrency and data integrity.

Key database tables:

- `users`: User accounts and authentication
- `texts`: Siddha texts and their metadata
- `projects`: Proofreading projects
- `dictionaries`: Dictionary entries and definitions
- `parses`: Grammatical analysis data

Frontend
--------

Our frontend is built with vanilla HTML, CSS, and JavaScript. We use:

- **Tailwind CSS** for styling
- **Vanilla JavaScript** for interactivity
- **HTMX** for dynamic content updates
- **Sanscript.js** for script transliteration

We avoid complex frontend frameworks to keep the codebase simple and maintainable.

Background Tasks
---------------

We use Celery for background tasks like:

- OCR processing of manuscript images
- Text parsing and analysis
- Data import and processing
- Email notifications

These tasks run asynchronously to avoid blocking the web interface.

Static Assets
-------------

We use a simple build process for our static assets:

- **Tailwind CSS** compiles our CSS from utility classes
- **esbuild** bundles our JavaScript
- **Asset hashing** for cache busting

The build process might seem overkill at first. But it keeps Kalanjiyam's CSS consistent, predictable, and fairly
maintainable.

Deployment
----------

Kalanjiyam is deployed using Docker containers:

- **Web container**: Flask application
- **Database container**: PostgreSQL
- **Redis container**: For Celery task queue
- **Nginx container**: For static file serving and load balancing

We use Docker Compose for local development and Kubernetes for production deployment.

Security
--------

We follow several security best practices:

- **HTTPS everywhere**: All traffic is encrypted
- **CSRF protection**: All forms are protected against CSRF attacks
- **Input validation**: All user input is validated and sanitized
- **SQL injection protection**: We use parameterized queries
- **XSS protection**: We escape all user-generated content

Monitoring
----------

We use several tools for monitoring:

- **Sentry**: Error tracking and performance monitoring
- **Logs**: Structured logging for debugging and analysis
- **Health checks**: Automated health checks for all services
- **Metrics**: Basic metrics collection for performance analysis
