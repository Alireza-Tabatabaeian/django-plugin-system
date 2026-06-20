# Django Plugin System

A flexible plugin framework for Django that allows applications to expose extension points through **Plugin Types**, implement them through **Plugin Items**, and configure multiple runtime **Plugin Instances** through Django Admin.

---

# Why use Django Plugin System?

As projects grow, it becomes increasingly common to support multiple implementations of the same functionality:

- Multiple payment gateways
- Different OTP providers
- Various notification channels
- AI providers from different vendors
- Storage backends
- Shipping providers
- Authentication mechanisms

Without a plugin system, these integrations are often hardcoded into the application, making them difficult to replace, configure, or extend.

Django Plugin System provides a structured way to:

- Define clear extension points through abstract interfaces
- Register multiple independent implementations
- Configure plugin instances directly from Django Admin
- Switch providers without changing application code
- Prioritize and enable/disable plugins at runtime
- Allow third-party Django apps to extend your system cleanly

Instead of writing large chains of conditional logic:

```python
if gateway == "zarinpal":
    ...
elif gateway == "stripe":
    ...
elif gateway == "paypal":
    ...
```

your application simply requests a plugin:

```python
gateway = get_plugin_instance(PaymentGatewayType)
gateway.create_payment(amount)
```

The selected implementation is determined by configuration, priority, and availability—not by hardcoded business logic.

This approach keeps applications modular, maintainable, and open for extension without requiring modifications to the core codebase.

> Django Plugin System helps you build extensible Django applications by separating **what a service should do** (Plugin Types) from **how it is implemented** (Plugin Items) and **how it is configured** (Plugin Instances).

---

## Features

- Interface-first plugin architecture
- Multiple implementations per plugin type
- Multiple configured instances per implementation
- Django Admin integration
- Configurable plugins using Django Forms
- Registry-to-database synchronization
- Automatic validation of plugin contracts
- Priority-based plugin selection
- Safe plugin discovery through AppConfig.ready()
- Runtime plugin loading helpers

---

## Installation

```bash
pip install django-plugin-system
```

Add the application:

```python
INSTALLED_APPS = [
    ...
    "django_plugin_system",
]
```

Run migrations:

```bash
python manage.py migrate
```

---

# Core Concepts

The system is built around three layers:

```text
Plugin Type
    ↓
Plugin Item
    ↓
Plugin Instance
```

## Plugin Type

Defines a contract (interface).

```python
from abc import abstractmethod
from django_plugin_system.plugin_core import BasePluginType


class PaymentGatewayType(BasePluginType):
    name = "payment_gateway"

    @abstractmethod
    def create_payment(self, amount):
        pass
```

## Plugin Item

Provides an implementation for a plugin type.

```python
from django_plugin_system.plugin_core import BasePluginItem


class ZarinpalGateway(BasePluginItem):
    name = "zarinpal"
    plugin_type = PaymentGatewayType

    def create_payment(self, amount):
        ...
```

## Plugin Instance

Represents a configured runtime instance of a plugin item.

Examples:

```text
Zarinpal Production
Zarinpal Sandbox
Zarinpal Backup
```

All may use the same plugin item but different configuration values.

---

# Typical Flow

Create Plugin Type > Create Plugin Item > Register Plugins > Run pluginsync > Create Plugin Instances > Load Plugin At Runtime

---

# Registering Plugins

Registration should usually happen inside `AppConfig.ready()`.

```python
from django.apps import AppConfig

from django_plugin_system.register import (
    register_plugin_type,
    register_plugin_item,
)


class PaymentsConfig(AppConfig):
    name = "payments"

    def ready(self):
        register_plugin_type({
            "interface": PaymentGatewayType,
        })

        register_plugin_item({
            "plugin_class": ZarinpalGateway,
        })
```

---

# Configurable Plugins

Plugins can expose configuration forms through a `PluginConfiguration` class.

```python
from django import forms

from django_plugin_system.plugin_core import (
    PluginConfiguration,
)


class ZarinpalConfigForm(forms.Form):
    merchant_id = forms.CharField()


class ZarinpalConfiguration(PluginConfiguration):
    form_class = ZarinpalConfigForm
```

Attach it to a plugin item:

```python
class ZarinpalGateway(BasePluginItem):
    name = "zarinpal"
    plugin_type = PaymentGatewayType
    configuration = ZarinpalConfiguration

    def create_payment(self, amount):
        merchant_id = self.config["merchant_id"]
        ...
```

Administrators can then create and manage configured plugin instances directly from Django Admin.

## Accessing Configuration Values
When a plugin instance is loaded, its configuration is automatically made available through the `config` property.

For example, suppose an administrator creates:

```text
Plugin Instance:
    Name: Zarinpal Production

Configuration:
    merchant_id = abc123
```

Inside the plugin:

```python
def create_payment(self, amount):
    merchant_id = self.config["merchant_id"]

    print(merchant_id)
```

Output:

```text
abc123
```

self.config is a standard Python dictionary, so the following patterns are also valid:

```python
self.config["merchant_id"]
self.config.get("merchant_id")
self.config.get("sandbox", False)
```

## Encryption Configuration

Django Plugin System stores plugin instance configuration using encrypted database fields.

Before using configurable plugins, make sure the required encryption settings are configured.

```python
# settings.py

FIELD_ENCRYPTION_KEY = "your-field-encryption-key"
SALT_KEY = "your-salt-key"
```

For production environments, these values should be generated securely and stored outside source control (for example using environment variables).

```python
import os

FIELD_ENCRYPTION_KEY = os.environ["FIELD_ENCRYPTION_KEY"]
SALT_KEY = os.environ["SALT_KEY"]
```

For more information about key generation and encryption settings, please refer to the documentation of the underlying encryption package used by Django Plugin System.

---

# Synchronizing Plugins

After registering plugins, synchronize them into the database:

```bash
python manage.py pluginsync
```

Or:

```bash
python manage.py pluginsync --prune
```

The sync process:

- Creates missing plugin types
- Creates missing plugin items
- Creates default instances for non-configurable plugins
- Optionally removes stale records

---

# Loading Plugins

Retrieve the selected plugin instance:

```python
from django_plugin_system.helpers import get_plugin_instance

gateway = get_plugin_instance(
    PaymentGatewayType
)

gateway.create_payment(1000)
```

Load a specific instance:

```python
gateway = get_plugin_instance_by_id(
    PaymentGatewayType,
    plugin_id=instance_id,
)
```

## Load all active instances
In some scenarios you may want to present all available plugins to a user and let them choose which one to use, or maybe try instances on by one until the result is successful.

```python
instances : List[PluginInstance] = get_active_plugins(
    PaymentGatewayType
)

for instance in instances:
    print(instance.name)
```

Each returned object is a `PluginInstance`.

To load the actual plugin implementation:

```python
selected_instance = instances[0]

gateway = selected_instance.load_instance() # loads actual item with methods, like create_payment
gateway.create_payment(1000)
```

Reserve plugins can be retrieved using:

```python
reserve_instances = get_reserve_plugins(
    PaymentGatewayType
)
```

This can be useful when implementing custom fallback or failover logic.

---

# Plugin Selection

By default, each plugin type selects a single plugin instance according to:
1. Status
2. Priority

Selection order:

```text
ACTIVE
    ↓
RESERVED
    ↓
DISABLED
```

Within the same status, lower priority values are preferred.

For example:

| Instance          | Status   | Priority |
| ----------------- | -------- | -------- |
| Stripe Production | ACTIVE   | 10       |
| Stripe Backup     | ACTIVE   | 20       |
| Stripe Sandbox    | RESERVED | 1        |

The selected plugin would be: `Strip Production`

because ACTIVE instances are preferred over RESERVED instances regardless of priority.

## Customizing Plugin Selection

The default selection strategy works well for most applications, but some projects may require custom logic.

Examples:

- Selecting plugins based on geographic region
- Selecting plugins based on user preferences
- Load balancing between multiple providers
- Implementing A/B testing
- Selecting plugins according to business rules

Provide a custom get_plugin function when registering the plugin type.

```python
def custom_get_plugin(plugin_type):
    return(
            PluginInstance.objects
            .select_related("item", "item__plugin_type")
            .filter(item__plugin_type=plugin_type, status=PluginStatus.Active)
            .order_by('name')
            .first()
        )
```

Register the type:

```python
register_plugin_type({
    "interface": TestPluginType,
    "get_plugin": custom_get_plugin
})
```

The function must return either:
- a PluginInstance
- or None
---

# Django Admin

The admin interface allows:

- Creating plugin instances
- Editing plugin configuration
- Enabling/disabling instances
- Changing priorities
- Verifying plugin loading

For configurable plugins:

1. Select plugin item
2. Configure plugin-specific form
3. Set instance metadata
4. Save

---

# Validation

The framework validates registrations during startup.

Examples:

- Plugin types must define a name.
- Plugin types must contain abstract methods.
- Plugin items must implement required methods.
- Configuration classes must inherit from `PluginConfiguration`.
- Configuration forms must inherit from Django `Form`.

Invalid plugins fail fast during application startup.

---

# Legacy Support

Older registration APIs remain supported for backward compatibility, but new projects should use:

- `BasePluginType`
- `BasePluginItem`
- `PluginConfiguration`

---

# License

MIT License

Copyright (c) Alireza Tabatabaeian
