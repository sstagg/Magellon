import os
from typing import Optional

from models.pydantic_models_settings import AppSettings

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
# Initialize AppSettings instance with default values or fallback settings

app_settings: AppSettings = None

if os.environ.get('APP_ENV', "development") == 'production':
    app_settings = AppSettings.load_settings("./configs/app_settings_prod.yaml")
else:
    app_settings = AppSettings.load_settings("./configs/app_settings_dev.yaml")


def _env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return None


def _env_bool(*names: str) -> Optional[bool]:
    value = _env(*names)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(*names: str) -> Optional[int]:
    value = _env(*names)
    if value is None:
        return None
    return int(value)


def _override_attr(obj, attr: str, value) -> None:
    if obj is not None and value is not None:
        setattr(obj, attr, value)


def _apply_environment_overrides(settings: AppSettings) -> AppSettings:
    """Let deployment secrets and endpoints come from the process env.

    Checked-in YAML remains the local/dev baseline, but production
    containers should inject credentials through environment variables
    or a secret manager. Keep the aliases broad so existing compose
    files such as ``RABBITMQ_HOST`` continue to work.
    """
    _override_attr(settings, "SLACK_TOKEN", _env("SLACK_TOKEN", "MAGELLON_SLACK_TOKEN"))
    _override_attr(settings, "DOCKER_URL", _env("DOCKER_URL", "MAGELLON_DOCKER_URL"))
    _override_attr(settings, "DOCKER_REPOSITORY", _env("DOCKER_REPOSITORY", "MAGELLON_DOCKER_REPOSITORY"))
    _override_attr(settings, "DOCKER_USERNAME", _env("DOCKER_USERNAME", "MAGELLON_DOCKER_USERNAME"))
    _override_attr(settings, "DOCKER_PASSWORD", _env("DOCKER_PASSWORD", "MAGELLON_DOCKER_PASSWORD"))

    db = settings.database_settings
    _override_attr(db, "DB_Driver", _env("DB_DRIVER", "MAGELLON_DB_DRIVER"))
    _override_attr(db, "DB_HOST", _env("DB_HOST", "MAGELLON_DB_HOST"))
    _override_attr(db, "DB_NAME", _env("DB_NAME", "MAGELLON_DB_NAME"))
    _override_attr(db, "DB_PASSWORD", _env("DB_PASSWORD", "MAGELLON_DB_PASSWORD", "MYSQL_PASSWORD"))
    _override_attr(db, "DB_Port", _env_int("DB_PORT", "MAGELLON_DB_PORT", "MYSQL_PORT"))
    _override_attr(db, "DB_USER", _env("DB_USER", "MAGELLON_DB_USER", "MYSQL_USER"))

    leginon = settings.leginon_db_settings
    _override_attr(leginon, "ENABLED", _env_bool("LEGINON_DB_ENABLED", "MAGELLON_LEGINON_DB_ENABLED"))
    _override_attr(leginon, "HOST", _env("LEGINON_DB_HOST", "MAGELLON_LEGINON_DB_HOST"))
    _override_attr(leginon, "PORT", _env_int("LEGINON_DB_PORT", "MAGELLON_LEGINON_DB_PORT"))
    _override_attr(leginon, "USER", _env("LEGINON_DB_USER", "MAGELLON_LEGINON_DB_USER"))
    _override_attr(leginon, "PASSWORD", _env("LEGINON_DB_PASSWORD", "MAGELLON_LEGINON_DB_PASSWORD"))
    _override_attr(leginon, "DATABASE", _env("LEGINON_DB_NAME", "MAGELLON_LEGINON_DB_NAME"))

    docs = settings.api_docs_settings
    _override_attr(docs, "ENABLED", _env_bool("API_DOCS_ENABLED", "MAGELLON_API_DOCS_ENABLED"))
    _override_attr(docs, "USERNAME", _env("API_DOCS_USERNAME", "MAGELLON_API_DOCS_USERNAME"))
    _override_attr(docs, "PASSWORD", _env("API_DOCS_PASSWORD", "MAGELLON_API_DOCS_PASSWORD"))

    setup = settings.security_setup_settings
    _override_attr(setup, "ENABLED", _env_bool("SECURITY_SETUP_ENABLED", "MAGELLON_SECURITY_SETUP_ENABLED"))
    _override_attr(setup, "SETUP_TOKEN", _env("SECURITY_SETUP_TOKEN", "MAGELLON_SECURITY_SETUP_TOKEN"))
    _override_attr(
        setup,
        "AUTO_DISABLE",
        _env_bool("SECURITY_SETUP_AUTO_DISABLE", "MAGELLON_SECURITY_SETUP_AUTO_DISABLE"),
    )

    rmq = settings.rabbitmq_settings
    _override_attr(rmq, "HOST_NAME", _env("RABBITMQ_HOST", "RABBITMQ_HOST_NAME", "MAGELLON_RABBITMQ_HOST"))
    _override_attr(rmq, "PORT", _env_int("RABBITMQ_PORT", "MAGELLON_RABBITMQ_PORT"))
    _override_attr(rmq, "USER_NAME", _env("RABBITMQ_USER", "RABBITMQ_USER_NAME", "MAGELLON_RABBITMQ_USER"))
    _override_attr(
        rmq,
        "PASSWORD",
        _env("RABBITMQ_PASSWORD", "RABBITMQ_PASS", "RABBITMQ_DEFAULT_PASS", "MAGELLON_RABBITMQ_PASSWORD"),
    )
    _override_attr(rmq, "VIRTUAL_HOST", _env("RABBITMQ_VIRTUAL_HOST", "MAGELLON_RABBITMQ_VIRTUAL_HOST"))
    _override_attr(rmq, "SSL_ENABLED", _env_bool("RABBITMQ_SSL_ENABLED", "MAGELLON_RABBITMQ_SSL_ENABLED"))
    _override_attr(
        rmq,
        "CONNECTION_TIMEOUT",
        _env_int("RABBITMQ_CONNECTION_TIMEOUT", "MAGELLON_RABBITMQ_CONNECTION_TIMEOUT"),
    )
    _override_attr(rmq, "PREFETCH_COUNT", _env_int("RABBITMQ_PREFETCH_COUNT", "MAGELLON_RABBITMQ_PREFETCH_COUNT"))
    return settings


if app_settings is not None:
    app_settings = _apply_environment_overrides(app_settings)

IMAGE_ROOT_URL = app_settings.directory_settings.IMAGE_ROOT_URL

ORIGINAL_IMAGES_SUB_URL = app_settings.directory_settings.ORIGINAL_IMAGES_SUB_URL
IMAGE_SUB_URL = app_settings.directory_settings.IMAGE_SUB_URL
FRAMES_SUB_URL = app_settings.directory_settings.FRAMES_SUB_URL
THUMBNAILS_SUB_URL = app_settings.directory_settings.THUMBNAILS_SUB_URL
ATLAS_SUB_URL = app_settings.directory_settings.ATLAS_SUB_URL
CTF_SUB_URL = app_settings.directory_settings.CTF_SUB_URL
FAO_SUB_URL = app_settings.directory_settings.FAO_SUB_URL
GAINS_SUB_URL = app_settings.directory_settings.GAIN_SUB_URL
DEFECTS_SUB_URL = app_settings.directory_settings.DEFECTS_SUB_URL
FFT_SUB_URL = app_settings.directory_settings.FFT_SUB_URL
JOBS_PROCESSING_SUB_URL = app_settings.directory_settings.JOBS_PROCESSING_SUB_URL

THUMBNAILS_SUFFIX = app_settings.directory_settings.THUMBNAILS_SUFFIX
FRAMES_SUFFIX = app_settings.directory_settings.FRAMES_SUFFIX
FFT_SUFFIX = app_settings.directory_settings.FFT_SUFFIX
ATLAS_SUFFIX = app_settings.directory_settings.ATLAS_SUFFIX

# my_config_value = os.environ.get('MY_CONFIG_VALUE')
MAGELLON_HOME_DIR = app_settings.directory_settings.MAGELLON_HOME_DIR or os.getenv('DATA_DIR', '/app/data')
MAGELLON_JOBS_DIR = app_settings.directory_settings.JOBS_DIR or os.getenv('MAGELLON_JOBS_PATH', '/jobs')
MAGELLON_GPFS_DIR = app_settings.directory_settings.MAGELLON_GPFS_PATH or os.getenv('MAGELLON_GPFS_PATH', '/gpfs')
IMAGES_DIR = f"{MAGELLON_HOME_DIR}/{IMAGE_SUB_URL}"
FFT_DIR = f"{MAGELLON_HOME_DIR}/{FFT_SUB_URL}"
THUMBNAILS_DIR = f"{MAGELLON_HOME_DIR}/{THUMBNAILS_SUB_URL}"
JOBS_DIR = f"{MAGELLON_HOME_DIR}/{JOBS_PROCESSING_SUB_URL}"


DOCKER_URL = app_settings.DOCKER_URL
DOCKER_USERNAME = app_settings.DOCKER_USERNAME
DOCKER_PASSWORD = app_settings.DOCKER_PASSWORD


def fetch_image_root_dir():
    """Image root directory path.

    Was Consul-KV-backed; now reads from the same env var the
    container start-up uses, with the configured MAGELLON_HOME_DIR as
    the fallback. Dynamic config pushes (P7) handle the case where the
    operator wants to retarget at runtime — they re-publish to the
    plugins.config broadcast subject and the fleet picks it up."""
    return os.getenv('DATA_DIR', MAGELLON_HOME_DIR)


def get_db_connection():
    return f'{app_settings.database_settings.DB_Driver}://{app_settings.database_settings.DB_USER}:{app_settings.database_settings.DB_PASSWORD}@{app_settings.database_settings.DB_HOST}:{app_settings.database_settings.DB_Port}/{app_settings.database_settings.DB_NAME}'
