from abc import abstractmethod

import pytest
from django import forms

from django_plugin_system.models import (
    PluginType,
    PluginItem,
    PluginInstance,
    PluginStatus,
)
from django_plugin_system.plugin_core import BasePluginType, BasePluginItem, PluginConfiguration
from django_plugin_system.register import (
    register_plugin_type,
    register_plugin_item,
    load_plugin_type,
    load_plugin_item,
)
from django_plugin_system.services.sync import sync_registered_plugins_to_db


class PaymentType(BasePluginType):
    name = "payment"
    description = "Payment gateway type"

    @abstractmethod
    def pay(self):
        pass


class SimplePaymentGateway(BasePluginItem):
    name = "simple_gateway"
    description = "Simple gateway"
    plugin_type = PaymentType

    def pay(self):
        return "paid"


class ConfigForm(forms.Form):
    merchant_id = forms.CharField()

class ConfigurationClass(PluginConfiguration):
    form_class = ConfigForm


class ConfigurablePaymentGateway(BasePluginItem):
    name = "configurable_gateway"
    description = "Configurable gateway"
    plugin_type = PaymentType
    configuration = ConfigurationClass

    def pay(self):
        who_paid = self.config
        if who_paid:
            return f"{self.config["hello"]} paid for you"
        return "I paid for you"


@pytest.mark.django_db
def test_register_and_load_plugin_type():
    register_plugin_type({"interface": PaymentType})

    loaded = load_plugin_type("payment", PaymentType.__module__)

    assert loaded["interface"] is PaymentType


@pytest.mark.django_db
def test_register_and_load_plugin_item():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": SimplePaymentGateway})

    loaded = load_plugin_item(
        "simple_gateway",
        SimplePaymentGateway.__module__,
        "payment",
        PaymentType.__module__
    )

    assert loaded["plugin_class"] is SimplePaymentGateway


@pytest.mark.django_db
def test_sync_creates_plugin_type_item_and_default_instance_for_non_configurable_item():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": SimplePaymentGateway})

    result = sync_registered_plugins_to_db(mode="create", prune=False)

    assert result["types_created"] == 1
    assert result["items_created"] == 1
    assert result["instances_created"] == 1

    plugin_type = PluginType.objects.get(name="payment")
    plugin_item = PluginItem.objects.get(name="simple_gateway")
    plugin_instance = PluginInstance.objects.get(item=plugin_item)

    assert plugin_type.manager == PaymentType.__module__
    assert plugin_item.module == SimplePaymentGateway.__module__
    assert plugin_item.configurable is False
    assert plugin_instance.name == "simple_gateway"
    assert plugin_instance.status == PluginStatus.ACTIVE


@pytest.mark.django_db
def test_sync_does_not_create_default_instance_for_configurable_item():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": ConfigurablePaymentGateway})

    result = sync_registered_plugins_to_db(mode="create", prune=False)

    assert result["types_created"] == 1
    assert result["items_created"] == 1
    assert result["instances_created"] == 0

    plugin_item = PluginItem.objects.get(name="configurable_gateway")

    assert plugin_item.configurable is True
    assert PluginInstance.objects.filter(item=plugin_item).count() == 0


@pytest.mark.django_db
def test_default_get_single_plugin_prefers_active_over_reserved_even_if_reserved_has_better_priority():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": SimplePaymentGateway})
    sync_registered_plugins_to_db(mode="create", prune=False)
    # one default plugin instance should be created
    # remove it
    deleted_count = PluginInstance.objects.all().delete()[0]
    assert deleted_count == 1

    plugin_type = PluginType.objects.get(name="payment")
    item = PluginItem.objects.get(name="simple_gateway")

    reserved = PluginInstance.objects.create(
        item=item,
        name="reserved",
        priority=-10,
        status=PluginStatus.RESERVED,
    )
    active = PluginInstance.objects.create(
        item=item,
        name="active",
        priority=10,
        status=PluginStatus.ACTIVE,
    )

    selected = plugin_type.get_single_plugin()

    assert selected == active
    assert selected != reserved


@pytest.mark.django_db
def test_plugin_instance_load_instance_passes_config_to_plugin_class():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": SimplePaymentGateway})
    sync_registered_plugins_to_db(mode="create", prune=False)

    instance = PluginInstance.objects.get()
    instance.config = {"hello": "world"}
    instance.save()

    loaded = instance.load_instance()

    assert isinstance(loaded, SimplePaymentGateway)
    assert loaded.config == {"hello": "world"}


@pytest.mark.django_db
def test_prune_removes_unregistered_items_after_sync():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": SimplePaymentGateway})
    sync_registered_plugins_to_db(mode="create", prune=False)

    assert PluginItem.objects.filter(name="simple_gateway").exists()

    # Clear registry, then sync with prune.
    from django_plugin_system.storage import _registry_plugin_types, _registry_plugin_items

    _registry_plugin_types.clear()
    _registry_plugin_items.clear()

    result = sync_registered_plugins_to_db(mode="create", prune=True)

    assert result["pruned_items"] >= 1
    assert result["pruned_types"] >= 1
    assert PluginItem.objects.count() == 0
    assert PluginType.objects.count() == 0
    assert PluginInstance.objects.count() == 0


@pytest.mark.django_db
def test_use_plugin_instance():
    register_plugin_type({"interface": PaymentType})
    register_plugin_item({"plugin_class": ConfigurablePaymentGateway})
    sync_registered_plugins_to_db(mode="create", prune=False)

    plugin_item = PluginItem.objects.get(name="configurable_gateway")
    created_instance = PluginInstance.objects.create(item=plugin_item, name="say_who_paid")
    created_instance.config = {"hello": "world"}
    created_instance.save()

    payment_type = PluginType.objects.get(name="payment")
    plugin_instance = payment_type.get_single_plugin()
    assert plugin_instance == created_instance

    plugin = plugin_instance.load_instance()
    assert isinstance(plugin, ConfigurablePaymentGateway)

    who_paid = plugin.pay()
    assert who_paid == "world paid for you"