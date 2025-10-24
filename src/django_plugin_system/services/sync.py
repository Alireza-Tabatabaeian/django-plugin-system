from typing import Literal

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from ..models import PluginType, PluginItem, PluginStatus
from ..storage import _registry_plugin_types, _registry_plugin_items

Mode = Literal["create", "update"]


def _app_list() -> set[str]:
    return set(settings.INSTALLED_APPS)


@transaction.atomic
def sync_registered_plugins_to_db(
        *,
        mode: Mode = "create",
        prune: bool = True,
) -> dict:
    """
    Sync in-memory registry -> DB.

    Mode="create": uses get_or_create (won't overwrite admin-edited fields)
    mode="update": uses update_or_create (will refresh description/priority from registry)

    prune: remove DB rows for managers/modules that are no longer installed
    """
    result = {"types_created": 0, "types_found": 0, "items_created": 0, "items_found": 0, "pruned_types": 0,
              "pruned_items": 0}

    app_list = _app_list()

    if prune:
        # remove rows for uninstalled apps
        result["pruned_types"] = PluginType.objects.filter(~Q(manager__in=app_list)).delete()[0]
        result["pruned_items"] = PluginItem.objects.filter(~Q(module__in=app_list)).delete()[0]

    # TYPES
    for _, pt in _registry_plugin_types.items():
        defaults = {"description": pt.get("description") or ""}
        if mode == "update":
            obj, created = PluginType.objects.update_or_create(
                name=pt["name"], manager=pt["manager"], defaults=defaults
            )
        else:
            obj, created = PluginType.objects.get_or_create(
                name=pt["name"], manager=pt["manager"], defaults=defaults
            )
        if created:
            result["types_created"] += 1
        else:
            result["types_found"] += 1

    # ITEMS
    for _, pi in _registry_plugin_items.items():
        try:
            pt_obj = PluginType.objects.get(name=pi["type_name"], manager=pi["manager_name"])
        except PluginType.DoesNotExist:
            # Type isn't synced (or missing) — skip
            continue

        defaults = {
            "description": pi.get("description") or "",
            # prefer registry priority on first creation; won’t override in "create" mode
            "priority": pi.get("priority") or 0,
            # first-time status ACTIVE; admin changes later will stick
            "status": PluginStatus.ACTIVE,
        }

        lookup = {"name": pi["name"], "module": pi["module"], "plugin_type": pt_obj}
        if mode == "update":
            obj, created = PluginItem.objects.update_or_create(defaults=defaults, **lookup)
        else:
            obj, created = PluginItem.objects.get_or_create(defaults=defaults, **lookup)

        if created:
            result["items_created"] += 1
        else:
            result["items_found"] += 1

    return result
