from abc import ABC
from typing import Any, ClassVar, Type
from typing import Dict

from django.forms import Form


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

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls is BasePluginType:
            return

        # first check if class provides an abstract method or not, as it should
        has_abstract = any(
            getattr(value, "__isabstractmethod__", False)
            for value in cls.__dict__.values()
        )

        # raise an error if it doesn't
        if not has_abstract:
            raise TypeError("Plugin type class must have at least one abstractmethod")

        # the class should also provide a name for plugin type
        if not hasattr(cls, 'name'):
            raise TypeError("Plugin type class must have name")


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
    _config: Dict
    """
    the config of instance
    """

    def __init__(self, config: Dict | None = None):
        self._config = config

    @property
    def config(self):
        return self._config

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
                if getattr(prop, "__isabstractmethod__", False):
                    if not hasattr(cls, attr_name):
                        raise AttributeError(f"Plugin item for {plugin_type.name} must implement {attr_name}")
        # check if class provides a configuration form and then if the form is of correct type
        configuration = getattr(cls, "configuration", None)
        if configuration is not None and not issubclass(configuration, PluginConfiguration):
            raise TypeError("configuration must be a subclass of PluginConfiguration")
