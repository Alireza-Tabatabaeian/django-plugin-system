import uuid
from typing import ClassVar, List, Type, Dict

from django.core.cache import cache
from django.db import models
from django.db.models import UniqueConstraint, Index
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .register import load_plugin_item, load_plugin_type


class PluginStatus(models.TextChoices):
    ACTIVE = 'active'
    RESERVED = 'reserve'  # used if no active plugin is available
    DISABLED = 'disable'


class PluginType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    manager = models.CharField(max_length=100)  # app providing the plugin type
    description = models.TextField()

    class Meta:
        constraints = [
            UniqueConstraint(fields=["name", "manager"], name="uniq_plugin_type_name_manager"),
        ]
        indexes = [
            Index(fields=["name"]),
            Index(fields=["manager"]),
        ]

    def __str__(self):
        return f"Plugin type {self.name}"

    def get_all_plugins(self) -> Dict[str, List['PluginItem']]:
        return PluginItem.get_all_plugins(self)

    def get_active_plugins(self) -> 'List[PluginItem]':
        return PluginItem.get_available_plugins(self)

    def get_single_plugin(self,*args,**kwargs) -> 'PluginItem | None':
        try:
            plugin_type = load_plugin_type(self.name, self.manager)
            get_plugin = plugin_type.get('get_plugin')
            if get_plugin:
                return get_plugin(self, *args, **kwargs)
        except KeyError:
            return None
        return PluginItem.default_get_single_plugin(self)


class PluginItem(models.Model):
    # CacheKey
    CACHE_KEY_PLUGIN_TYPE_SINGLE: ClassVar[str] = 'plugin-single-item-type-{}'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plugin_type = models.ForeignKey(PluginType, on_delete=models.CASCADE)
    module = models.CharField(max_length=100)  # app providing the plugin item
    name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=10,
        choices=PluginStatus.choices,
        default=PluginStatus.ACTIVE,
        db_index=True,
    )
    priority = models.SmallIntegerField(default=0)  # lower is better
    description = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["name", "module", "plugin_type"],
                name="uniq_plugin_item_name_module_type",
            )
        ]
        indexes = [
            Index(fields=["plugin_type", "status", "priority"]),
            Index(fields=["module"]),
        ]

    def __str__(self):
        return f"Plugin {self.name} for {self.plugin_type} provided by {self.module}.({self.status})"

    def load_class(self) -> Type | None:
        try:
            plugin_item = load_plugin_item(self.name, self.module, self.plugin_type.name)
            return plugin_item['plugin_class']
        except Exception:
            return None

    @staticmethod
    def default_get_single_plugin(plugin_type: PluginType) -> 'PluginItem | None':
        key = PluginItem.CACHE_KEY_PLUGIN_TYPE_SINGLE.format(plugin_type.id)
        plugin = cache.get(key)
        if plugin:
            return plugin
        qs = PluginItem.objects.filter(plugin_type=plugin_type, status=PluginStatus.ACTIVE).order_by('priority')
        first = qs.first()
        if first:
            cache.set(key, first)
            return first
        qs = PluginItem.objects.filter(plugin_type=plugin_type, status=PluginStatus.RESERVED).order_by('priority')
        return qs.first()

    @staticmethod
    def get_all_plugins(plugin_type: PluginType) -> Dict[str, List['PluginItem']]:
        result = {}
        for plugin in PluginItem.objects.filter(plugin_type=plugin_type).order_by('priority'):
            result.setdefault(plugin.status, []).append(plugin)
        return result

    @staticmethod
    def get_available_plugins(plugin_type: PluginType) -> 'List[PluginItem]':
        return list(
            PluginItem.objects.filter(plugin_type=plugin_type, status=PluginStatus.ACTIVE).order_by('priority')
        )


# Cache invalidation when items change
@receiver(post_save, sender=PluginItem)
@receiver(post_delete, sender=PluginItem)
def _clear_single_plugin_cache(sender, instance: PluginItem, **kwargs):
    key = PluginItem.CACHE_KEY_PLUGIN_TYPE_SINGLE.format(instance.plugin_type.id)
    cache.delete(key)
