from __future__ import annotations

import warnings
from typing import Type

from .plugin_core import BasePluginType, BasePluginItem


def get_plugin_instance(
        plugin_type: str | Type[BasePluginType],
        manager: str = ""
) -> BasePluginItem | object | None:
    from .models import PluginType
    is_plugin_class = (
            isinstance(plugin_type, type)
            and issubclass(plugin_type, BasePluginType)
    )
    pt = PluginType.get_plugin_type_by_class(plugin_type) if is_plugin_class else PluginType.get_plugin_type_by_info(
        plugin_type, manager)
    if pt is None:
        return None
    instance = pt.get_single_plugin()
    if not instance:
        return None
    return instance.load_instance()


def get_plugin_instance_by_id(
        plugin_type: Type[BasePluginType],
        instance_id: str,
        prevent_disable: bool = False
) -> BasePluginItem | None:
    """
    :param plugin_type: Type[BasePluginType]
    :param instance_id: str. The Plugin instance id
    :param prevent_disable: bool. If True, the disabled instance won't be loaded.(default False)
    :return:
    """
    from .models import PluginType
    pt = PluginType.get_plugin_type_by_class(plugin_type)
    if pt is None:
        return None
    instance = pt.get_plugin_by_id(instance_id, prevent_disable)
    if not instance:
        return None
    return instance.load_instance()


def get_plugin_instance_by_id_name_manager(
        type_name: str,
        type_manager: str,
        instance_id: str,
        prevent_disable=False
) -> BasePluginItem | None:
    """
    deprecated since 2.0.0
    will be removed in 3.0.0, use get_plugin_instance_by_id instead.
    Use only if plugin type is not a subclass of BasePluginType.
    """

    from .models import PluginType

    warnings.warn(
        "get_plugin_instance_by_id_name_manager is deprecated."
        "will be removed in 3.0.0, use get_plugin_instance_by_id instead."
        "Use only if plugin type is not a subclass of BasePluginType.",
        DeprecationWarning,
        stacklevel=2
    )
    pt = PluginType.get_plugin_type_by_info(type_name, type_manager)
    if pt is None:
        return None
    instance = pt.get_plugin_by_id(instance_id, prevent_disable)
    if not instance:
        return None
    return instance.load_instance()


def get_active_plugins(plugin_type: Type[BasePluginType]):
    """
    :param plugin_type: Type[BasePluginType]
    :return: List[PluginInstance]

    Note that PluginInstance doesn't load the Type[BasePluginItem]. So in order to execute the methods it needs to get the instance with `.load_instance() method, then methods can be run.
    An example:
    payment_gateways: List[PluginInstance] = get_active_plugins(PaymentGateway)
    first_gateway : Type[BasePluginItem] = payment_gateways[0].load_instance()
    first_gateway.create_payment(1000)
    """
    from .models import PluginType

    pt: PluginType = PluginType.get_plugin_type_by_class(plugin_type)
    if pt is None:
        return []
    return pt.get_active_plugins()


def get_reserve_plugins(plugin_type: Type[BasePluginType]):
    """
    :param plugin_type: Type[BasePluginType]
    :return: List[PluginInstance]

    Note that PluginInstance doesn't load the Type[BasePluginItem]. So in order to execute the methods it needs to get the instance with `.load_instance() method, then methods can be run.
    An example:
    payment_gateways: List[PluginInstance] = get_reserve_plugins(PaymentGateway)
    first_gateway : Type[BasePluginItem] = payment_gateways[0].load_instance()
    first_gateway.create_payment(1000)
    """
    from .models import PluginType

    pt: PluginType = PluginType.get_plugin_type_by_class(plugin_type)
    if pt is None:
        return []
    return pt.get_reserve_plugins()
