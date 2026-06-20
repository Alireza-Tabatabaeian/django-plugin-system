from django import forms

from .models import PluginInstance


class PluginInstanceMetaForm(forms.ModelForm):
    class Meta:
        model = PluginInstance
        fields = [
            "name",
            "description",
            "priority",
            "status",
        ]
