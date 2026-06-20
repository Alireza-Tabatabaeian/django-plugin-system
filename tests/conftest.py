import pytest

from django_plugin_system.storage import (
    _registry_plugin_types,
    _registry_plugin_items,
)


@pytest.fixture(autouse=True)
def clear_plugin_registry():
    _registry_plugin_types.clear()
    _registry_plugin_items.clear()
    yield
    _registry_plugin_types.clear()
    _registry_plugin_items.clear()