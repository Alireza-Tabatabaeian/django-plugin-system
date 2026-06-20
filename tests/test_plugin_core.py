from abc import abstractmethod

import pytest
from django import forms

from django_plugin_system.plugin_core import BasePluginType, BasePluginItem, PluginConfiguration


def test_plugin_type_requires_name():
    with pytest.raises(TypeError):

        class MissingNameType(BasePluginType):
            @abstractmethod
            def run(self):
                pass


def test_plugin_type_requires_abstract_method():
    with pytest.raises(TypeError):

        class NoAbstractType(BasePluginType):
            name = "no_abstract"


def test_plugin_item_requires_name():
    class PaymentType(BasePluginType):
        name = "payment"

        @abstractmethod
        def pay(self):
            pass

    with pytest.raises(TypeError):

        class MissingNameItem(BasePluginItem):
            plugin_type = PaymentType

            def pay(self):
                return "ok"


def test_plugin_item_must_implement_plugin_type_methods():
    class PaymentType(BasePluginType):
        name = "payment"

        @abstractmethod
        def pay(self):
            pass

    with pytest.raises(AttributeError):

        class BrokenPaymentItem(BasePluginItem):
            name = "broken"
            plugin_type = PaymentType


def test_plugin_item_accepts_django_form_configuration():
    class PaymentType(BasePluginType):
        name = "payment"

        @abstractmethod
        def pay(self):
            pass

    class PaymentConfigForm(forms.Form):
        merchant_id = forms.CharField()

    class ConfigurationClass(PluginConfiguration):
        form_class = PaymentConfigForm

    class PaymentItem(BasePluginItem):
        name = "payment_item"
        plugin_type = PaymentType
        configuration = ConfigurationClass

        def pay(self):
            return "ok"

    assert PaymentItem.configuration is ConfigurationClass
    assert PaymentItem.configuration.form_class is PaymentConfigForm