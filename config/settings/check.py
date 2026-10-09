"""
Temporary check settings — SQLite only, used to verify Python/template
layer before PostgreSQL is installed. Not used at runtime.
"""
from .base import *  # noqa

SECRET_KEY = "check-only-not-for-runtime"
DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_check.sqlite3",
    }
}
