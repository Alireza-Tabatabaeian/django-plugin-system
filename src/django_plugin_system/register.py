import logging
from abc import ABC

from .storage import (
    _registry_plugin_items,
    _registry_plugin_types,
    PluginTypeRegistry,
    PluginItemRegistry,
    PLUGIN_TYPE_PLACEHOLDER,
    PLUGIN_ITEM_PLACEHOLDER,
)

logger = logging.getLogger(__name__)


def register_plugin_type(plugin_type: PluginTypeRegistry):
    if not issubclass(plugin_type['interface'], ABC):
        raise TypeError("Interface must be a subclass of ABC")
    if not getattr(plugin_type['interface'], '__abstractmethods__', None):
        raise TypeError("Interface must have at least one abstractmethod")

    name = PLUGIN_TYPE_PLACEHOLDER.format(plugin_type['name'], plugin_type['manager'])
    _registry_plugin_types[name] = plugin_type


def load_plugin_type(type_name: str, manager: str) -> PluginTypeRegistry:
    name = PLUGIN_TYPE_PLACEHOLDER.format(type_name, manager)
    if name in _registry_plugin_types:
        return _registry_plugin_types[name]
    raise KeyError(f"Plugin type '{name}' not found")


def register_plugin_item(plugin_item: PluginItemRegistry):
    plugin_type: PluginTypeRegistry = load_plugin_type(plugin_item['type_name'], plugin_item['manager_name'])
    if not issubclass(plugin_item['plugin_class'], plugin_type['interface']):
        raise TypeError(
            f"Plugin '{plugin_item['name']}' does not implement interface {plugin_type['interface'].__name__}")
    name = PLUGIN_ITEM_PLACEHOLDER.format(plugin_item['name'], plugin_item['module'], plugin_item['type_name'])
    _registry_plugin_items[name] = plugin_item
    logger.debug("Registered plugin item %s", name)


def load_plugin_item(plugin_name: str, module_name: str, type_name: str) -> PluginItemRegistry:
    name = PLUGIN_ITEM_PLACEHOLDER.format(plugin_name, module_name, type_name)
    if name in _registry_plugin_items:
        return _registry_plugin_items[name]
    raise KeyError(f"Plugin item '{name}' not found")
