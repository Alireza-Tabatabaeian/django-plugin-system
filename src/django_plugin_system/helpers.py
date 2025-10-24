from typing import Type, TypeVar, Optional

from .models import PluginType

T = TypeVar("T")


def get_plugin_instance(type_name: str, manager: str) -> Optional[object]:
    try:
        pt = PluginType.objects.get(name=type_name, manager=manager)
    except PluginType.DoesNotExist:
        return None
    item = pt.get_single_plugin()
    if not item:
        return None
    cls = item.load_class()
    return cls() if cls else None


def get_plugin_class(type_name: str, manager: str) -> Optional[Type[T]]:
    try:
        pt = PluginType.objects.get(name=type_name, manager=manager)
    except PluginType.DoesNotExist:
        return None
    item = pt.get_single_plugin()
    if not item:
        return None
    return item.load_class()
