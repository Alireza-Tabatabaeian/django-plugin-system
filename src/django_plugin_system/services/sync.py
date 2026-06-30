from typing import Literal

from django.db import transaction

from ..models import PluginType, PluginItem, PluginInstance, PluginStatus
from ..plugin_core import BasePluginType, BasePluginItem
from ..storage import _registry_plugin_types, _registry_plugin_items

Mode = Literal["create", "update"]


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
    result = {
        "types_created": 0,
        "types_found": 0,
        "items_created": 0,
        "items_found": 0,
        "instances_created": 0,
        "instances_found": 0,
        "pruned_types": 0,
        "pruned_items": 0,
        "pruned_instances": 0
    }

    valid_plugin_types = list()
    valid_plugin_items = list()

    # TYPES
    for _, pt in _registry_plugin_types.items():
        interface = pt["interface"]
        is_base_plugin_type = issubclass(interface, BasePluginType)
        interface_base : type = interface.__base__
        is_sub_base_plugin_type = is_base_plugin_type and interface_base.__base__ == BasePluginType
        pt_name = interface.name if is_base_plugin_type else pt["name"]
        pt_description = interface.description if is_base_plugin_type else pt.get("description", "")
        defaults = {"description": pt_description}
        if mode == "update":
            obj, created = PluginType.objects.update_or_create(
                name=pt_name, manager=interface.__module__, defaults=defaults
            )
        else:
            obj, created = PluginType.objects.get_or_create(
                name=pt_name, manager=interface.__module__, defaults=defaults
            )
        if is_sub_base_plugin_type:
            parent_obj = PluginType.get_plugin_type_by_class(interface_base)
            if parent_obj:
                obj.parent = parent_obj
            else:
                parent_defaults = {"description": interface.__base__.description}
                obj.parent = PluginType.objects.create(name=interface.__base__, manager=interface.__base__.__module__,defaults=parent_defaults)
                result['types_created'] += 1
            obj.save()
        valid_plugin_types.append(obj.id)
        if created:
            result["types_created"] += 1
        else:
            result["types_found"] += 1

    # ITEMS and INSTANCES
    for _, pi in _registry_plugin_items.items():
        pi_class = pi["plugin_class"]
        is_base_plugin_item = issubclass(pi_class, BasePluginItem)
        pi_name = pi_class.name if is_base_plugin_item else pi["name"]
        pi_description = pi_class.description if is_base_plugin_item else pi["description"] or ""

        pt_obj = PluginType.get_plugin_type_by_class(
            pi_class.plugin_type) if is_base_plugin_item else PluginType.get_plugin_type_by_info(pi["type_name"],
                                                                                                 pi["manager_name"])
        if pt_obj is None:
            # Type isn't synced (or missing) — skip
            continue

        is_configurable = is_base_plugin_item and getattr(pi_class, "configuration", None) is not None

        defaults = {
            "description": pi_description,
            # prefer registry priority on first creation; won’t override in "create" mode
            "priority": pi.get("priority") or 0,
            "configurable": is_configurable
        }

        lookup = {"name": pi_name, "module": pi_class.__module__, "plugin_type": pt_obj}
        if mode == "update":
            obj, created = PluginItem.objects.update_or_create(defaults=defaults, **lookup)
        else:
            obj, created = PluginItem.objects.get_or_create(defaults=defaults, **lookup)
        valid_plugin_items.append(obj.id)
        if is_configurable and not obj.configurable:  # plugin item has changed to configurable
            obj.configurable = True
            obj.save()  # apply the update
            try:  # remove the previous default instance
                PluginInstance.objects.get(item=obj).delete()
                result["pruned_instances"] += 1
            except PluginInstance.DoesNotExist:
                continue

        instance_defaults = {
            "name": obj.name,
            "description": obj.description,
            # use same priority as plugin item
            "priority": obj.priority,
            # first-time status ACTIVE; admin changes later will stick
            "status": PluginStatus.ACTIVE,
        }

        # if a plugin item is not configurable, then a default plugin instance should be created automatically with no config
        # this provides backward compatibility as in version 1 there were no instances, now this default instance acts as the single plugin item
        if not is_configurable:
            instance_lookup = {"item": obj}
            instance_obj, instance_created = PluginInstance.objects.get_or_create(defaults=instance_defaults,
                                                                                  **instance_lookup)

            if instance_created:
                result["instances_created"] += 1
            else:
                result["instances_found"] += 1

        if created:
            result["items_created"] += 1
        else:
            result["items_found"] += 1

    # Prune invalid plugin types if needed
    if prune:
        invalid_plugin_types = PluginType.objects.exclude(id__in=valid_plugin_types)
        for invalid_plugin_type in invalid_plugin_types:
            invalid_plugin_items = PluginItem.objects.filter(plugin_type=invalid_plugin_type)
            for invalid_plugin_item in invalid_plugin_items:
                result["pruned_instances"] += PluginInstance.objects.filter(item=invalid_plugin_item).delete()[0]
                invalid_plugin_item.delete()
                result["pruned_items"] += 1
            invalid_plugin_type.delete()
            result["pruned_types"] += 1
        # some PluginItems might be invalid even if its related PluginType exist
        invalid_plugin_items = PluginItem.objects.exclude(id__in=valid_plugin_items)
        for invalid_plugin_item in invalid_plugin_items:
            result["pruned_instances"] += PluginInstance.objects.filter(item=invalid_plugin_item).delete()[0]
            invalid_plugin_item.delete()
            result["pruned_items"] += 1

    return result
