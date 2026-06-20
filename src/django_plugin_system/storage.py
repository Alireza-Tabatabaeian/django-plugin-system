from abc import ABC
from typing import TypedDict, Callable, Type, Dict, NotRequired

from .plugin_core import BasePluginType, BasePluginItem

PLUGIN_TYPE_PLACEHOLDER = 'plugin-type-{}-by-{}'
PLUGIN_ITEM_PLACEHOLDER = 'plugin-item-{}-by-{}-for-{}-{}'


class PluginTypeRegistry(TypedDict):
    interface: Type[BasePluginType] | Type[ABC]
    """
    version 3 and above will only accept subclasses of BasePluginType 
    """
    get_plugin: NotRequired[Callable | None]
    """
    a callable that should return an object of class PluginInstance
    used for customizing plugin instance selection logic when calling `get_single_plugin` method of plugin type
    if doesn't provided then the instance with the highest priority will be selected as default (minimum id if priority is the same)
    """
    name: NotRequired[str]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by interface.name
    """
    manager: NotRequired[str]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by interface.__module__ attribute
    """
    description: NotRequired[str | None]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by interface.description
    """


class PluginItemRegistry(TypedDict):
    plugin_class: Type[BasePluginItem] | Type
    """
    version 3 and above will only accept subclasses of BasePluginItem
    """
    name: NotRequired[str]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by plugin_class.name attribute
    """
    type_name: NotRequired[str]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by plugin_class.plugin_type.name attribute
    """
    manager_name: NotRequired[str]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by the plugin_class.interface.__module__ attribute
    """
    module: NotRequired[str]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by plugin_class.__module__ attribute
    """
    description: NotRequired[str | None]
    """
    deprecated since 2.0.0
    will be removed in 3.0.0 and replaced by plugin_class.description attribute
    """
    priority: NotRequired[int | None]


_registry_plugin_types: Dict[str, PluginTypeRegistry] = {}
_registry_plugin_items: Dict[str, PluginItemRegistry] = {}
