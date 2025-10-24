from django.contrib import admin
from django.db.models import F
from .models import PluginType, PluginItem, PluginStatus


@admin.register(PluginType)
class PluginTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "manager", "description", "active_count", "reserved_count", "disabled_count")
    list_filter = ("manager",)
    search_fields = ("name", "manager", "description")
    ordering = ("name", "manager")

    def _count_with_status(self, obj, status):
        return PluginItem.objects.filter(plugin_type=obj, status=status).count()

    def active_count(self, obj): return self._count_with_status(obj, PluginStatus.ACTIVE)

    def reserved_count(self, obj): return self._count_with_status(obj, PluginStatus.RESERVED)

    def disabled_count(self, obj): return self._count_with_status(obj, PluginStatus.DISABLED)

    active_count.short_description = "Active"
    reserved_count.short_description = "Reserved"
    disabled_count.short_description = "Disabled"


@admin.action(description="Mark selected as ACTIVE")
def mark_active(modeladmin, request, queryset):
    queryset.update(status=PluginStatus.ACTIVE)


@admin.action(description="Mark selected as RESERVED")
def mark_reserved(modeladmin, request, queryset):
    queryset.update(status=PluginStatus.RESERVED)


@admin.action(description="Mark selected as DISABLED")
def mark_disabled(modeladmin, request, queryset):
    queryset.update(status=PluginStatus.DISABLED)


@admin.action(description="Increase priority (lower number)")
def increase_priority(modeladmin, request, queryset):
    # Lower number => higher priority
    queryset.update(priority=F('priority') - 1)


@admin.action(description="Decrease priority (higher number)")
def decrease_priority(modeladmin, request, queryset):
    queryset.update(priority=F('priority') + 1)


@admin.register(PluginItem)
class PluginItemAdmin(admin.ModelAdmin):
    list_display = ("name", "plugin_type", "module", "status", "priority", "loaded_ok")
    list_filter = ("status", "module", "plugin_type__name", "plugin_type__manager")
    search_fields = ("name", "module", "description", "plugin_type__name")
    ordering = ("plugin_type__name", "priority", "name")
    list_editable = ("status", "priority")
    actions = [mark_active, mark_reserved, mark_disabled, increase_priority, decrease_priority]

    @admin.display(boolean=True, description="Class loads")
    def loaded_ok(self, obj: PluginItem):
        return obj.load_class() is not None
