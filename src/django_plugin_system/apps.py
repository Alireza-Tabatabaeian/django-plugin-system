from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class PluginSystemConfig(AppConfig):
    name = 'django_plugin_system'
    verbose_name = 'Django Plugin System'

    def ready(self):
        from django.conf import settings

        required_settings = [
            "FIELD_ENCRYPTION_KEY",
            "SALT_KEY"
        ]

        for setting_name in required_settings:
            if not hasattr(settings, setting_name):
                raise ImproperlyConfigured(
                    f"{setting_name} must be configured to use django-plugin-system."
                )
