"""Config management for the Kalanjiyam Flask app.

All of Kalanjiyam's interesting config values are defined in the project's `.env`
file. Here, we parse that file and map its values to specific config objects,
which we then load into Flask.

Most config values are documented on :class:`BaseConfig`, from which all other
classes inherit. Production-specific config values, which are mainly replated
to deployment, are defined on :class:`ProductionConfig`.

It's considered a best practice to keep this module outside the application
package: From the Flask docs (emphasis added):

    Configuration becomes more useful if you can store it in a separate file,
    *ideally located outside the actual application package*.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

# Load dotenv early so that `_env` will work in the class definitions below.
load_dotenv()

#: The test environment. For unit tests only.
TESTING = "testing"
#: The development environment. For local development.
DEVELOPMENT = "development"
#: The build environment. For build on github.
BUILD = "build"
#: The staging environment. For testing on staging.
STAGING = "staging"
#: The production environment. For production serving.
PRODUCTION = "production"


def _make_path(path: Path):
    """Create a path if it doesn't exist already.

    If possible, avoid using this function so that our config code has fewer
    side effects. Currently, we use this function only to set up unit tests.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env(key: str, default=None) -> str | None:
    """Fetch a value from the local environment.

    :param key: the environment variable to fetch
    :return: a value, or ``None`` if the variable is undefined.
    """
    return os.environ.get(key, default)


class BaseConfig:
    """Base settings for all configs."""

    # Core settings
    # -------------

    #: The Flask app environment ("production", "development", etc.). We set
    #: this explicitly so that Celery can have access to it and load an
    #: appropriate application context.
    KALANJIYAM_ENVIRONMENT = "development"

    #: Internal secret key for encrypting sensitive data.
    SECRET_KEY = _env("SECRET_KEY")

    #: URI for the Kalanjiyam database. This URI (also called a URL in some docs)
    #: has the following basic format:
    #:
    #:     dialect+driver://username:password@host:port/database
    #:
    #: For more information, see:
    #:
    #: https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls
    SQLALCHEMY_DATABASE_URI = _env("SQLALCHEMY_DATABASE_URI")

    #: Where to store user uploads (PDFs, images, etc.).
    UPLOAD_FOLDER = _env("FLASK_UPLOAD_FOLDER")

    #: Logger setup
    LOG_LEVEL = logging.ERROR

    # Extensions
    # ----------

    # Flask-Babel

    #: Default locale. This is "en" by default, but declare it here to be
    #: explicit.
    BABEL_DEFAULT_LOCALE = "en"

    # Flask-Mail

    #: URL for mail server.
    MAIL_SERVER = _env("MAIL_SERVER")
    #: Port for mail server.
    MAIL_PORT = _env("MAIL_PORT")
    #: If ``True``, use TLS for email encryption.
    MAIL_USE_TLS = True
    #: Username for mail server.
    MAIL_USERNAME = _env("MAIL_USERNAME")
    #: Password for mail server.
    MAIL_PASSWORD = _env("MAIL_PASSWORD")
    #: Default sender for site emails.
    MAIL_DEFAULT_SENDER = _env("MAIL_DEFAULT_SENDER")

    # Flask-WTF

    #: If True, enable cross-site request forgery (CSRF) protection.
    #: This must be True in production.
    WTF_CSRF_ENABLED = True

    # Services
    # --------

    #: ReCAPTCHA public key.
    RECAPTCHA_PUBLIC_KEY = _env("RECAPTCHA_PUBLIC_KEY")

    #: ReCAPTCHA private key.
    RECAPTCHA_PRIVATE_KEY = _env("RECAPTCHA_PRIVATE_KEY")

    #: Sentry data source name (DSN).
    #: We use Sentry to get notifications about server errors.
    SENTRY_DSN = _env("SENTRY_DSN")

    # Test-only
    # ---------

    #: If ``True``, enable the Flask debugger.
    DEBUG = False

    #: If ``True``, enable testing mode.
    TESTING = False

    # Environment variables
    # ---------------------

    # KALANJIYAM_BOT_PASSWORD is the password we use for the "kalanjiyam-bot" account.
    # We set this account as an envvar because we need to create this user as
    # part of database seeding.

    # GOOGLE_APPLICATION_CREDENTIALS contains credentials for the Google Vision
    # API, but these credentials are fetched by the Google API implicitly,
    # so we don't need to define it on the Config object here.


class UnitTestConfig(BaseConfig):
    """For unit tests."""

    KALANJIYAM_ENVIRONMENT = TESTING
    TESTING = True
    SECRET_KEY = "insecure unit test secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = _make_path(Path(__file__).parent / "data" / "file-uploads")

    #: Logger setup
    LOG_LEVEL = logging.DEBUG

    #: Disable CSRF protection for unit tests, since the Flask test runner
    #: doesn't have good support for it.
    WTF_CSRF_ENABLED = False

    RECAPTCHA_PUBLIC_KEY = "re-public"
    RECAPTCHA_PRIVATE_KEY = "re-private"


class DevelopmentConfig(BaseConfig):
    """For local development."""

    KALANJIYAM_ENVIRONMENT = DEVELOPMENT
    DEBUG = True
    #: If set, automatically reload Flask templates (including imports) when
    #: they change on disk.
    TEMPLATES_AUTO_RELOAD = True

    #: Logger setup
    LOG_LEVEL = logging.INFO


class BuildConfig(BaseConfig):
    """For build on GitHub."""

    KALANJIYAM_ENVIRONMENT = BUILD
    DEBUG = True
    #: If set, automatically reload Flask templates (including imports) when
    #: they change on disk.
    TEMPLATES_AUTO_RELOAD = False

    #: Logger setup
    LOG_LEVEL = logging.INFO


class StagingConfig(BaseConfig):
    """For staging."""

    KALANJIYAM_ENVIRONMENT = STAGING
    DEBUG = True
    #: If set, automatically reload Flask templates (including imports) when
    #: they change on disk.
    TEMPLATES_AUTO_RELOAD = False

    #: Logger setup
    LOG_LEVEL = logging.INFO


class ProductionConfig(BaseConfig):
    """For production."""

    KALANJIYAM_ENVIRONMENT = PRODUCTION

    #: Logger setup
    LOG_LEVEL = logging.INFO

    # Deployment credentials
    # ----------------------

    #: Which directory to use on the production machine.
    SERVER_APP_DIRECTORY = _env("SERVER_APP_DIRECTORY")
    #: Server username.
    SERVER_USER = _env("SERVER_USER")
    #: Server host.
    SERVER_HOST = _env("SERVER_HOST")


def _validate_config(config: BaseConfig):
    """Examine the given config and fail if the config is malformed.

    :param config: the config to test
    """
    assert config.KALANJIYAM_ENVIRONMENT in {
        TESTING,
        DEVELOPMENT,
        BUILD,
        STAGING,
        PRODUCTION,
    }

    if not config.SQLALCHEMY_DATABASE_URI:
        raise ValueError("This config does not define SQLALCHEMY_DATABASE_URI")

    if not config.UPLOAD_FOLDER:
        raise ValueError("This config does not define UPLOAD_FOLDER.")

    if not Path(config.UPLOAD_FOLDER).is_absolute():
        raise ValueError("UPLOAD_FOLDER must be an absolute path.")

    if not config.SECRET_KEY:
        raise ValueError("This config does not define SECRET_KEY.")

    if config.KALANJIYAM_ENVIRONMENT == PRODUCTION:
        if not config.SENTRY_DSN:
            raise ValueError("Production config must define SENTRY_DSN.")


def load_config_object(name: str):
    """Load a config object by name.

    :param name: the name of the config to load
    :return: a config object
    """
    configs = {
        TESTING: UnitTestConfig,
        DEVELOPMENT: DevelopmentConfig,
        BUILD: BuildConfig,
        STAGING: StagingConfig,
        PRODUCTION: ProductionConfig,
    }

    if name not in configs:
        raise ValueError(f"Unknown config name: {name}")

    config = configs[name]()
    _validate_config(config)
    return config


def create_config_only_app(config_name: str):
    """Create a minimal Flask app that only loads config.

    This is useful for scripts that need to access config values but don't
    need the full application context.

    :param config_name: the name of the config to load
    :return: a minimal Flask app
    """
    app = Flask(__name__)
    app.config.from_object(load_config_object(config_name))
    return app
