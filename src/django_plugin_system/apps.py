from django.apps import AppConfig


class PluginSystemConfig(AppConfig):
    name = 'django_plugin_system'
    verbose_name = 'Django Plugin System'

    def ready(self):
        from .signals import sync_registered_plugins_to_db
        from .models import _clear_single_plugin_cache
