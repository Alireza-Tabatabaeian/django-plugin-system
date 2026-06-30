from __future__ import annotations

import uuid
from typing import ClassVar, List, Type, Self

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import UniqueConstraint, Index, Q
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from encrypted_fields.fields import EncryptedJSONField

from .plugin_core import BasePluginType, BasePluginItem
from .register import load_plugin_item, load_plugin_type


class PluginStatus(models.TextChoices):
    ACTIVE = 'active'
    RESERVED = 'reserve'  # used if no active plugin is available
    DISABLED = 'disable'


class PluginType(models.Model):
    # CacheKey
    CACHE_KEY_PLUGIN_TYPE_SINGLE: ClassVar[str] = 'plugin-single-item-type-{}'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    manager = models.CharField(max_length=100)  # module providing the plugin type
    parent = models.ForeignKey('self', on_delete=models.SET_NULL,null=True, blank=True,related_name='parent_type')
    description = models.TextField()

    class Meta:
        constraints = [
            UniqueConstraint(fields=["name", "manager"], name="unique_plugin_type_name_manager"),
        ]
        indexes = [
            Index(fields=["name"]),
            Index(fields=["manager"]),
        ]

    def __str__(self):
        return f"Plugin type {self.name}"

    @staticmethod
    def get_plugin_type_by_class(plugin_type_class: Type[BasePluginType]) -> PluginType | None:
        try:
            return PluginType.objects.get(name=plugin_type_class.name, manager=plugin_type_class.__module__)
        except PluginType.DoesNotExist:
            return None

    @staticmethod
    def get_plugin_type_by_info(name: str, manager: str) -> PluginType | None:
        try:
            return PluginType.objects.get(name=name, manager=manager)
        except PluginType.DoesNotExist:
            return None

    def get_active_plugins(self) -> List[PluginInstance]:
        return PluginInstance.get_available_plugins(self)

    def get_reserve_plugins(self) -> List[PluginInstance]:
        return PluginInstance.get_reserved_plugins(self)

    def get_single_plugin(self, *args, **kwargs) -> PluginInstance | None:
        try:
            plugin_type = load_plugin_type(self.name, self.manager)
            get_plugin = plugin_type.get('get_plugin')
            if get_plugin:
                return get_plugin(self, *args, **kwargs)
        except KeyError:
            return None
        return PluginInstance.default_get_single_plugin(self)

    def get_plugin_by_id(self, instance_id: str, prevent_disabled: bool = False) -> PluginInstance | None:
        """
        returns a related plugin instance by id,
        will return None if id doesn't exist, instance is unrelated to plugin type or
        instance is disabled and prevent_disabled is set to True
        """
        try:
            plugin_instance = PluginInstance.objects.select_related("item", "item__plugin_type").get(id=instance_id)
            unrelated = plugin_instance.item.plugin_type != self
            disable = plugin_instance.status == PluginStatus.DISABLED and prevent_disabled
            return None if unrelated or disable else plugin_instance
        except PluginInstance.DoesNotExist:
            return None


class PluginItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plugin_type = models.ForeignKey(PluginType, on_delete=models.CASCADE, editable=False)
    module = models.CharField(max_length=100, editable=False)  # module providing the plugin item
    name = models.CharField(max_length=100, db_index=True, editable=False)
    configurable = models.BooleanField(default=False, editable=False)

    priority = models.SmallIntegerField(default=0)
    """
    since version 2.0.0 the priority of the instance is the parameter for selecting an instance, yet the priority of PluginItem acts as default value for instance (can be modified through admin panel).
    """
    description = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["name", "module", "plugin_type"],
                name="unique_plugin_item_name_module_type",
            )
        ]
        indexes = [
            Index(fields=["plugin_type"]),
            Index(fields=["module"])
        ]

    def __str__(self):
        return f"Plugin {self.name} for {self.plugin_type} provided by {self.module}."

    def load_plugin_class(self) -> Type[BasePluginItem] | Type | None:
        try:
            plugin_item = load_plugin_item(self.name, self.module, self.plugin_type.name, self.plugin_type.manager)
            return plugin_item['plugin_class']
        except KeyError:
            return None

    def load_class(self) -> Type[BasePluginItem] | Type | None:
        return self.load_plugin_class()

    def load_instance(self) -> Type[BasePluginItem] | Type | None:
        plugin_item_cls = self.load_plugin_class()
        return None if plugin_item_cls is None else plugin_item_cls()


class PluginInstance(models.Model):
    """
    A configured instance of a PluginItem (implementation).
    Multiple instances of the same item can exist with different configs.
    """
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    item = models.ForeignKey(PluginItem, on_delete=models.CASCADE, related_name="instances")
    name = models.CharField(max_length=100)  # human-friendly instance name
    config = EncryptedJSONField(null=True)
    status = models.CharField(
        max_length=10, choices=PluginStatus.choices, default=PluginStatus.ACTIVE, db_index=True
    )
    priority = models.SmallIntegerField(default=0)  # lower is better
    description = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["item", "name"], name="unique_plugin_instance_item_name"),
        ]
        indexes = [
            models.Index(fields=["item", "status", "priority"]),
        ]

    def __str__(self):
        return f"{self.item.module}.{self.item.name}::{self.name}"

    def get_plugin_class(self) -> Type[BasePluginItem] | Type | None:
        return self.item.load_class()

    @staticmethod
    def default_get_single_plugin(plugin_type: PluginType) -> PluginInstance | None:
        key = PluginType.CACHE_KEY_PLUGIN_TYPE_SINGLE.format(plugin_type.id)
        use_cache = getattr(settings, 'DJANGO_PLUGIN_SYSTEM_USE_CACHE', False)
        if use_cache:
            CACHE_MISS = "__django_plugin_system_cache_miss__"

            plugin = cache.get(key, CACHE_MISS)

            if plugin != CACHE_MISS:
                return plugin
        qs = (
            PluginInstance.objects
            .select_related("item", "item__plugin_type", "item__plugin_type__parent")
            .filter(Q(item__plugin_type=plugin_type ) | Q(item__plugin_type__parent=plugin_type))
            .exclude(status=PluginStatus.DISABLED)  # only prevent disabled instances
            .order_by('priority', "id")
        )
        # qs returns a list of active and reserved plugin instances sorted by priority
        selected_instance = qs.first()
        for instance in qs:
            if instance.status == PluginStatus.ACTIVE:
                selected_instance = instance  # first active instance should be selected
                break
        if use_cache:
            cache.set(key, selected_instance)  # selected_instance may be None
        return selected_instance

    @staticmethod
    def get_available_plugins(plugin_type: PluginType) -> List[PluginInstance]:
        return list(
            PluginInstance.objects
            .select_related("item", "item__plugin_type", "item__plugin_type__parent")
            .filter(Q(item__plugin_type=plugin_type) | Q(item__plugin_type__parent=plugin_type), Q(status=PluginStatus.ACTIVE))
            .order_by('priority')
        )

    @staticmethod
    def get_reserved_plugins(plugin_type: PluginType) -> List[PluginInstance]:
        return list(
            PluginInstance.objects
            .select_related("item", "item__plugin_type", "item__plugin_type__parent")
            .filter(Q(item__plugin_type=plugin_type) | Q(item__plugin_type__parent=plugin_type), Q(status=PluginStatus.RESERVED))
            .order_by('priority')
        )

    def load_instance(self):
        """
        deprecated since 2.0.2
        will be removed in 3.0.0, use load_implementation instead.
        """
        return self.load_implementation()

    def load_implementation(self):
        class_imp = self.item.load_plugin_class()
        return None if class_imp is None else class_imp(self)

# Cache invalidation when items change
@receiver(post_save, sender=PluginInstance)
@receiver(post_delete, sender=PluginInstance)
def _clear_single_plugin_cache(sender, instance: PluginInstance, **kwargs):
    key = PluginType.CACHE_KEY_PLUGIN_TYPE_SINGLE.format(instance.item.plugin_type.id)
    cache.delete(key)
