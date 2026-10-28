"""Local data-only oracle. No environment-selected or PostgreSQL database."""
from .package_test_settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "generated-artifacts" / "live-restart" / "verification.sqlite3",
    }
}
LIVE_RESTART_VERIFY_ONLY = True
