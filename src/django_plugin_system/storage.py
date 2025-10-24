from abc import ABC
from typing import TypedDict, Callable, Type, Dict, NotRequired

PLUGIN_TYPE_PLACEHOLDER = 'plugin-type-{}-by-{}'
PLUGIN_ITEM_PLACEHOLDER = 'plugin-item-{}-by-{}-for-{}'


class PluginTypeRegistry(TypedDict):
    name: str
    interface: type[ABC]
    manager: str
    get_plugin: NotRequired[Callable | None]
    description: NotRequired[str | None]


class PluginItemRegistry(TypedDict):
    name: str
    type_name: str
    manager_name: str
    plugin_class: Type
    module: str
    description: NotRequired[str | None]
    priority: NotRequired[int | None]


_registry_plugin_types: Dict[str, PluginTypeRegistry] = {}
_registry_plugin_items: Dict[str, PluginItemRegistry] = {}
