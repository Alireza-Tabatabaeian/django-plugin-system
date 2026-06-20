SECRET_KEY = "test-secret-key"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django_plugin_system"
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:"
    }
}

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MIGRATION_MODULES = {
    "django_plugin_system": None
}

DJANGO_PLUGIN_SYSTEM_USE_CACHE = False

# Needed for encrypting config field.
DJANGO_ENCRYPTED_FIELD_KEY = "test-field-encryption-key-32bytes!!"
SALT_KEY = "test-salt-key"