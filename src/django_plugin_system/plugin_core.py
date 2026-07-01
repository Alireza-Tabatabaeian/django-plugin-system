from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar, Type, TYPE_CHECKING

from django.forms import Form

if TYPE_CHECKING:
    from .models import PluginInstance

def required_plugin_item_method(func):
    func.__required_plugin_item_method__ = True
    return func

class PluginConfiguration:
    form_class: ClassVar[Type[Form]]

    def __init__(self, plugin_item=None, plugin_instance=None):
        self.plugin_item = plugin_item
        self.plugin_instance = plugin_instance

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        config_form = getattr(cls, "form_class", None)

        if config_form is None or not issubclass(config_form, Form):
            raise TypeError("form_class must be a subclass of Form")

    def get_initial(self) -> dict[str, Any]:
        if self.plugin_instance:
            return self.plugin_instance.config or {}
        return {}

    def get_form(self, data=None, files=None, prefix=None) -> Form:
        return self.form_class(
            data=data,
            files=files,
            initial=self.get_initial(),
            prefix=prefix
        )

    def clean_config(self, form: Form) -> dict[str, Any]:
        return dict(form.cleaned_data)


class BasePluginType(ABC):
    name: ClassVar[str]
    """
    a name for the plugin type (required)
    """
    description: ClassVar[str] = ""
    """
    description about the plugin type (optional), defaults to empty string
    """
    _plugin_item: BasePluginItem

    @property
    def plugin_item(self) -> BasePluginItem:
        return self._plugin_item

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls is BasePluginType:
            return

        # first check if class provides an abstract method or not, as it should
        has_abstract = any(
            getattr(value, "__isabstractmethod__", False) or getattr(value, "__required_plugin_item_method__", False)
            for value in cls.__dict__.values()
        )

        # raise an error if it doesn't
        if not has_abstract:
            raise TypeError("Plugin type class must have at least one abstract or required plugin item method")

        # the class should also provide a name for plugin type
        if not hasattr(cls, 'name'):
            raise TypeError("Plugin type class must have name")

    def __init__(self, plugin_item: BasePluginItem):
        self._plugin_item = plugin_item

    @classmethod
    def __plugin_item_validator__(cls, plugin_item_cls: Type[BasePluginItem]):
        if getattr(cls, "__plugin_item_validator__", False):
            cls.__plugin_item_validator__(plugin_item_cls)


class BasePluginItem:
    name: ClassVar[str]
    """
    a name for the plugin item (required)
    """
    description: ClassVar[str] = ""
    """
    description about the plugin item (optional)
    """
    plugin_type: ClassVar[Type[BasePluginType]]
    """
    defines which plugin type, is this plugin item related to (required)
    """
    configuration: ClassVar[Type[PluginConfiguration] | None] = None
    """
    the configuration class if the plugin item can be configured (optional but if provides one, it should be a subclass of PluginConfiguration)
    """
    _instance: PluginInstance | None

    def __init__(self, instance: PluginInstance | None = None) -> None:
        self._instance = instance

    @property
    def config(self):
        return self._instance.config

    @property
    def plugin_instance(self):
        return self._instance

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is BasePluginItem:
            return
        # check requirements (name and related plugin type)
        if 'name' not in cls.__dict__:
            raise TypeError("Plugin item must have name")
        if not hasattr(cls, 'plugin_type'):
            raise TypeError("Plugin item must have plugin type")
        # check if plugin type is suitable and then if the class do implement all the abstract methods of plugin type
        plugin_type = cls.plugin_type
        if not issubclass(plugin_type, BasePluginType):
            raise TypeError("Plugin items must point to a correct type of plugin type through `plugin_type` property")
        else:
            for attr_name, prop in plugin_type.__dict__.items():
                if getattr(prop,"__isabstractmethod__", False) or getattr(prop, "__required_plugin_item_method__", False):
                    item_method = cls.__dict__.get(attr_name)

                    if item_method is None or not callable(item_method):
                        raise TypeError(
                            f"{cls.__name__} must implement `{attr_name}` "
                            f"required by plugin type `{plugin_type.name}`"
                        )
            plugin_type.__plugin_item_validator__(cls)
        # check if class provides a configuration form and then if the form is of correct type
        configuration = getattr(cls, "configuration", None)
        if isinstance(configuration, type) and not issubclass(configuration, PluginConfiguration):
            raise TypeError("configuration must be a subclass of PluginConfiguration")

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)

        plugin_type_method = self.plugin_type.__dict__.get(item)

        if plugin_type_method is None:
            raise AttributeError(item)

        if not callable(plugin_type_method):
            raise AttributeError(item)

        if getattr(plugin_type_method, "__isabstractmethod__", False):
            raise AttributeError(item)

        def delegated_method(*args, **kwargs):
            plugin_type_instance = self.plugin_type(self)
            method = getattr(plugin_type_instance, item)
            return method(*args, **kwargs)

        return delegated_method
