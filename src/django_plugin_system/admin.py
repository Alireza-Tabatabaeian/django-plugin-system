from django.contrib import admin
from django.contrib import messages
from django.db.models import F
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse
from django.utils.safestring import mark_safe

from .forms import PluginInstanceMetaForm
from .models import PluginItem, PluginInstance, PluginType, PluginStatus


@admin.register(PluginType)
class PluginTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "manager", "description", "active_count", "reserved_count", "disabled_count")
    list_filter = ("manager",)
    search_fields = ("name", "manager", "description")
    ordering = ("name", "manager")

    def _count_with_status(self, obj, status):
        return PluginInstance.objects.select_related("item", "item__plugin_type").filter(item__plugin_type=obj,
                                                                                         status=status).count()

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


@admin.register(PluginInstance)
class PluginInstanceAdmin(admin.ModelAdmin):
    list_display = ("name", "item_name", "plugin_type", "status", "priority", "loaded_ok", "edit")
    list_filter = ("status", "item__module", "item__plugin_type__name", "item__plugin_type__manager")
    search_fields = ("name", "item__module", "description", "item__plugin_type__name")
    ordering = ("item__name", "item__plugin_type__name", "priority", "name")
    list_editable = ("status", "priority")
    actions = [mark_active, mark_reserved, mark_disabled, increase_priority, decrease_priority]

    def add_view(self, request, form_url="", extra_context=None):
        return redirect("admin:django_plugin_system_plugininstance_create")

    @admin.display(ordering="item__name", description="Item")
    def item_name(self, obj):
        return obj.item.name

    @admin.display(ordering="item__plugin_type__name", description="Plugin Type")
    def plugin_type(self, obj):
        return obj.item.plugin_type.name

    @admin.display(boolean=True, description="Class loads")
    def loaded_ok(self, obj: PluginInstance):
        return obj.load_instance() is not None

    @admin.display(description="Edit")
    def edit(self, obj: PluginInstance):
        edit_url = reverse("admin:django_plugin_system_plugininstance_configure", args=[obj.id])
        return mark_safe('<a href="%s">edit</a>' % edit_url)

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "create/",
                self.admin_site.admin_view(self.create_step_item),
                name="django_plugin_system_plugininstance_create",
            ),
            path(
                "create/<uuid:item_id>/",
                self.admin_site.admin_view(self.create_step_config),
                name="django_plugin_system_plugininstance_create_config",
            ),
            path(
                "<uuid:instance_id>/configure/",
                self.admin_site.admin_view(self.edit_config),
                name="django_plugin_system_plugininstance_configure",
            ),
        ]

        return custom_urls + urls

    def create_step_item(self, request):

        items = PluginItem.objects.filter(configurable=True).select_related("plugin_type")

        return render(
            request,
            "admin/django_plugin_system/plugininstance/select_item.html",
            {
                **self.admin_site.each_context(request),
                "title": "Select plugin item",
                "items": items,
            },
        )

    def create_step_config(self, request, item_id):
        item = get_object_or_404(PluginItem, id=item_id, configurable=True)

        plugin_item_class = item.load_plugin_class()
        configuration_class = plugin_item_class.configuration
        configuration = configuration_class(plugin_item=item)

        config_form = configuration.get_form(
            data=request.POST or None,
            files=request.FILES or None,
            prefix="config"
        )

        meta_form = PluginInstanceMetaForm(
            data=request.POST or None,
            initial={
                "name": item.name,
                "priority": item.priority,
            },
            prefix="meta"
        )

        if request.method == "POST":
            if config_form.is_valid() and meta_form.is_valid():
                PluginInstance.objects.create(
                    item=item,
                    name=meta_form.cleaned_data["name"],
                    description=meta_form.cleaned_data.get("description", ""),
                    priority=meta_form.cleaned_data["priority"],
                    status=meta_form.cleaned_data["status"],
                    config=configuration.clean_config(config_form),
                )

                messages.success(request, "Plugin instance created successfully.")
                return redirect("admin:django_plugin_system_plugininstance_changelist")

        return render(
            request,
            "admin/django_plugin_system/plugininstance/configure.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Configure {item.name}",
                "item": item,
                "config_form": config_form,
                "meta_form": meta_form,
            },
        )

    def edit_config(self, request, instance_id):
        instance = get_object_or_404(
            PluginInstance.objects.select_related("item"),
            id=instance_id,
        )

        item: PluginItem = instance.item
        if item.configurable:
            plugin_item_class = item.load_plugin_class()
            configuration_class = plugin_item_class.configuration
            configuration = configuration_class(
                plugin_item=item,
                plugin_instance=instance,
            )

            config_form = configuration.get_form(
                data=request.POST or None,
                files=request.FILES or None,
                prefix="config"
            )
        else:
            config_form = None
            configuration = None

        meta_form = PluginInstanceMetaForm(
            data=request.POST or None,
            instance=instance,
            prefix="meta"
        )

        if request.method == "POST":
            if meta_form.is_valid() and (config_form is None or config_form.is_valid()):
                instance = meta_form.save(commit=False)
                if config_form is not None:
                    instance.config = configuration.clean_config(config_form)
                instance.save()

                messages.success(request, "Plugin instance updated successfully.")
                return redirect("admin:django_plugin_system_plugininstance_changelist")

        return render(
            request,
            "admin/django_plugin_system/plugininstance/configure.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Configure {instance.name}",
                "item": item,
                "instance": instance,
                "config_form": config_form,
                "meta_form": meta_form,
            },
        )
