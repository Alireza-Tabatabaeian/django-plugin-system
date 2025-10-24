# Django Plugin System

A lightweight, batteries-included plugin registry for Django apps.  
Use it to expose **swappable implementations** (e.g., multiple OTP providers) behind a stable interface, select the active plugin in **Django Admin**, and keep the database in sync with in‑code registrations via a **management command**.

---

## ✨ Features

- **Simple interface-first design** — define an abstract base class (ABC), register implementations.
- **Registry → DB sync** — `pluginsync` management command (and optional `post_migrate` signal).
- **Admin UX** — filter/search, bulk enable/disable, and quick priority nudges.
- **Deterministic selection** — pick a single plugin by `status` and `priority`, with caching.
- **Safe defaults** — `get_or_create` syncing preserves admin-edited fields.
- **Uniqueness guarantees** — unique constraints for types and items.

---

## 📦 Installation

```bash
pip install django-plugin-system
```

Add the app to `INSTALLED_APPS`:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_plugin_system",
]
```

> The app creates two models: `PluginType` and `PluginItem`.

---

## 🔌 Core Concepts

### 1) Define an **interface** (ABC)

```python
# apps/otp/interfaces.py
from abc import ABC, abstractmethod

class AbstractOTP(ABC):
    @abstractmethod
    def send_otp(self, number: str, code: str) -> None: ...
```

### 2) Register a **plugin type**

```python
# apps/otp/apps.py (or any module imported at startup)
from django.apps import AppConfig
from django_plugin_system.register import register_plugin_type

class OtpConfig(AppConfig):
    name = "apps.otp"
    def ready(self):
        register_plugin_type({
            "name": "otp",
            "manager": self.name,  # the app providing the type
            "interface": AbstractOTP,
            "description": "One-time password (OTP) delivery channel",
        })
```

### 3) Implement and register **plugin items**

```python
# apps/otp_sms/plugins.py
from django_plugin_system.register import register_plugin_item
from .interfaces import AbstractOTP

class SmsIrOTP(AbstractOTP):
    def send_otp(self, number: str, code: str) -> None:
        # call provider api...
        pass

# Register this implementation
register_plugin_item({
    "name": "sms_ir",
    "module": "apps.otp_sms",     # the app providing the item
    "type_name": "otp",
    "manager_name": "apps.otp",   # the app providing the type
    "plugin_class": SmsIrOTP,
    "priority": 10,
    "description": "Send OTP using Sms.ir provider",
})
```

> You can register multiple items with different priorities. Lower number means **higher** priority.

---

## 🗄️ Database Models

```python
# django_plugin_system.models
class PluginType(models.Model):
    id          = UUID PK
    name        = CharField
    manager     = CharField   # the app that defines the interface
    description = TextField

class PluginItem(models.Model):
    id          = UUID PK
    plugin_type = FK -> PluginType
    module      = CharField   # the app that provides the implementation
    name        = CharField
    status      = TextChoices('active', 'reserve', 'disable')
    priority    = SmallIntegerField  # lower is better
    description = TextField
```

### Uniqueness

- `PluginType(name, manager)` is unique.  
- `PluginItem(name, module, plugin_type)` is unique.

---

## 🧠 Selection Logic

- **Active first:** pick the lowest-priority `active` item.
- **Fallback:** if no `active`, pick the lowest-priority `reserve` item.
- **Cache:** the chosen item is cached per `PluginType` and auto‑invalidated on save/delete.

### Helper

```python
from django_plugin_system.helpers import get_plugin_instance

otp = get_plugin_instance("otp", "apps.otp")
if otp:
    otp.send_otp("+31123456789", "123456")
```

> Or call `PluginType.get_single_plugin()` then `.load_class()` to instantiate manually.

---

## 🛠️ Syncing the Registry

You have **two** ways to keep the DB aligned with the in‑memory registry:

1) **Automatically after migrations** (default)
   - The `post_migrate` signal syncs in *create-only* mode (preserves admin edits).

2) **Manually via command**
   ```bash
   python manage.py pluginsync
   # or to refresh defaults from registry (overwrites description/priority on conflicts):
   python manage.py pluginsync --mode update
   # skip pruning of stale rows:
   python manage.py pluginsync --no-prune
   ```

**Modes:**

- `create` → uses `get_or_create` (safe: won’t overwrite `status`/`priority` changed in Admin)
- `update` → uses `update_or_create` (refresh `description`/`priority` from code)

---

## 🧭 Admin Panel

- **PluginType** list shows counts per status.
- **PluginItem** list lets you:
  - quick-edit `status` and `priority`,
  - bulk mark **ACTIVE/RESERVED/DISABLED**,
  - **Increase/Decrease priority** in-place,
  - view a “Class loads” boolean to catch broken registrations.

> Changing status/priority automatically clears the single‑plugin selection cache.

---

## 🔄 Overriding selection

You can override the selection logic per type by providing a `get_plugin` callable in the type registry entry:

```python
def my_selector(plugin_type_model_obj):
    # your custom logic (possibly data-driven)
    return plugin_type_model_obj.get_active_plugins()[0]

register_plugin_type({
    "name": "otp",
    "manager": "apps.otp",
    "interface": AbstractOTP,
    "description": "OTP delivery",
    "get_plugin": my_selector,  # <- override
})
```

---

## 🧪 Testing tips

- Ensure your registry code paths are imported in test settings (e.g., via `AppConfig.ready`).
- Use `pluginsync --mode create` in test setup to materialize rows.
- Toggle item `status` in tests to verify fallback and cache invalidation.

---

## 📐 Design Notes & Guarantees

- Registry data lives in memory at import time; DB represents a **materialized view** used by Admin and runtime selection.
- Syncing is **idempotent** and safe to run many times.
- Items are validated to **implement the declared interface**.
- Errors on registration are not swallowed — mis-registrations fail early and loudly.

---

## 🤔 Why Use Django Plugin System?

When you build extensible Django apps — like payment gateways, OTP senders, or notification systems — you often need pluggable backends that can be swapped or prioritized without touching your core logic.

This library lets you define interfaces, register multiple implementations, and let users (or admins) pick which ones are active — all without breaking code, and with database-level configurability.

---

### 🧩 Example: Notification System

Imagine you have multiple ways to notify users:

- Email

- SMS

- Push notification

Each of these is handled by a different piece of code — maybe even from different apps.

### 🚫 **Without** Django Plugin System

- You hardcode your imports and logic:

```python
# notifications/core.py
from notifications.email_sender import send_email
from notifications.sms_sender import send_sms
from notifications.push_sender import send_push

def notify_user(user, message):
    if user.prefers_email:
        send_email(user.email, message)
    elif user.prefers_sms:
        send_sms(user.phone, message)
    elif user.prefers_push:
        send_push(user.device_token, message)
```
- Every time you add a new provider, you must:
  - Write new import statements
  - Modify your logic
  - Re-deploy your code
  - Possibly break something that used to work

And there’s no way for an admin to change behavior dynamically — everything is baked into code.

---
### ✅ **With** Django Plugin System

1. You define one interface:

```python
from abc import ABC, abstractmethod

class AbstractNotifier(ABC):
    @abstractmethod
    def send(self, user, message): ...
```

2. You register it as a plugin type:

```python
from django_plugin_system.register import register_plugin_type

register_plugin_type({
    "name": "notifier",
    "manager": "apps.notifications",
    "interface": AbstractNotifier,
    "description": "Notification channels for users",
})
```

3. You implement as many plugin items as you want (completely independent of the rest of the code):

```python
from django_plugin_system.register import register_plugin_item
from .interfaces import AbstractNotifier

class EmailNotifier(AbstractNotifier):
    def send(self, user, message):
        print(f"Sending email to {user.email}: {message}")

register_plugin_item({
    "name": "email",
    "module": "apps.notifications.email",
    "type_name": "notifier",
    "manager_name": "apps.notifications",
    "plugin_class": EmailNotifier,
    "priority": 5,
    "description": "Send notification via Email",
})
```

4. You can now dynamically select from Admin which notifiers are active, in reserve, or disabled — even reorder them by priority.
5. Your code doesn’t change at all:

```python
from django_plugin_system.helpers import get_plugin_instance

notifier = get_plugin_instance("notifier", "apps.notifications")
notifier.send(user, "Your OTP is 1234")
```

💡 You can even expose multiple active notifiers and let users subscribe to their favorites — Email + Push for one user, Push only for another — all configurable through database records instead of code edits.

```python
# models.py
from typing import List

from django.db import models
from django.contrib.auth.models import User

from django_plugin_system.models import PluginItem


class UserNotifyPref(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    favourite_plugins = models.ManyToManyField(PluginItem)

    @staticmethod
    def get_user_plugins(user: User) -> List[PluginItem]:
        try:
            return list(UserNotifyPref.objects.get(user=user).favourite_plugins.all())
        except UserNotifyPref.DoesNotExist:
            return []
```

Now the following code will notify user through all selected plugins:
```python
from myapp.models import UserNotifyPref

...

favourite_plugins = UserNotifyPref.get_user_plugins(user)
for plugin in favourite_plugins:
    plugin_service = plugin.load_class()
    plugin_service.send(user, message)

...

```
just as simple as you see, **with** django-plugin-system, you can let users decide which plugin they prefer to use.

---

### ⚖️ Summary — With vs Without

| Aspect                    | **Without Plugin System**     | **With Plugin System**       |
| :------------------------ | :---------------------------- | :--------------------------- |
| Adding a new provider     | Requires code change + deploy | Just register plugin class   |
| Selecting active provider | Hardcoded logic               | Done in Django Admin         |
| Prioritization / fallback | Manual if-else chain          | Automatic by `priority`      |
| Runtime swapping          | Not possible                  | Fully supported              |
| Testing new providers     | Requires staging deployment   | Just toggle “active/reserve” |
| Extensibility             | Rigid                         | Clean, modular, and safe     |
| Dev vs Ops                | Devs control behavior         | Ops/Admins control behavior  |

---

## 📄 License

MIT [Alireza Tabatabaeian](https://github.com/Alireza-Tabatabaeian)