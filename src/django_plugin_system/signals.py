from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .services.sync import sync_registered_plugins_to_db

APP_LABEL = "django_plugin_system"


@receiver(post_migrate)
def sync_registered_plugins_signal(sender, **kwargs):
    if getattr(sender, "name", None) != APP_LABEL:
        return
    # create-only; do not overwrite admin-edited fields
    sync_registered_plugins_to_db(mode="create", prune=True)
