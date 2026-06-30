import logging
import warnings
from abc import ABC

from .plugin_core import BasePluginType, BasePluginItem
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
    interface = plugin_type['interface']
    module = interface.__module__
    is_base_plugin_type = issubclass(interface, BasePluginType)
    if not is_base_plugin_type and not issubclass(interface, ABC):
        raise TypeError("Interface must be a subclass of BasePluginType or ABC")
    # first check if class provides an abstract method or not, as it should
    has_abstract = any(
        getattr(value, "__isabstractmethod__", False) or getattr(value, "__required_plugin_item_method__", False)
        for value in interface.__dict__.values()
    )
    if not has_abstract:
        raise TypeError("Interface must have at least one abstract or required plugin item method")
    if not is_base_plugin_type:
        warnings.warn(
            "The interface should be a subclass of BasePluginType in version 3.0+"
            "Interface should inherit BasePluginType",
            DeprecationWarning,
            stacklevel=2,
        )
    name = PLUGIN_TYPE_PLACEHOLDER.format(
        plugin_type['name'] if not is_base_plugin_type else interface.name,
        module
    )
    _registry_plugin_types[name] = plugin_type


def load_plugin_type(type_name: str, manager: str) -> PluginTypeRegistry:
    name = PLUGIN_TYPE_PLACEHOLDER.format(type_name, manager)
    if name in _registry_plugin_types:
        return _registry_plugin_types[name]
    raise KeyError(f"Plugin type '{name}' not found")


def register_plugin_item(plugin_item: PluginItemRegistry):
    plugin_class = plugin_item['plugin_class']
    is_base_plugin_item = issubclass(plugin_class, BasePluginItem)
    if is_base_plugin_item:
        plugin_type_name = plugin_class.plugin_type.name
        plugin_type_module = plugin_class.plugin_type.__module__
        plugin_item_name = plugin_class.name
    else:
        plugin_type_name = plugin_item['type_name']
        plugin_type_module = plugin_item['manager_name']
        plugin_item_name = plugin_item['name']
        warnings.warn(
            "The plugin_class should be a subclass of BasePluginItem in version 3.0+"
            "plugin_class should inherit BasePluginItem",
            DeprecationWarning,
            stacklevel=2,
        )
    plugin_item_module = plugin_class.__module__
    plugin_type: PluginTypeRegistry = load_plugin_type(plugin_type_name, plugin_type_module)
    if not is_base_plugin_item and not issubclass(plugin_item['plugin_class'], plugin_type['interface']):
        raise TypeError(
            f"Plugin '{plugin_item_name}' does not implement interface {plugin_type['interface'].__name__}"
        )
    name = PLUGIN_ITEM_PLACEHOLDER.format(plugin_item_name, plugin_item_module, plugin_type_name, plugin_type_module)
    _registry_plugin_items[name] = plugin_item
    logger.debug("Registered plugin item %s", name)


def load_plugin_item(plugin_name: str, module_name: str, type_name: str, type_module) -> PluginItemRegistry:
    name = PLUGIN_ITEM_PLACEHOLDER.format(plugin_name, module_name, type_name, type_module)
    if name in _registry_plugin_items:
        return _registry_plugin_items[name]
    raise KeyError(f"Plugin item '{name}' not found")
