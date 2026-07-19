---
name: ManagerProfile auto-create signal
description: Every new auth.User automatically gets a ManagerProfile via post_save signal — tests must not create one manually.
---

Ein `post_save`-Signal auf `auth.User` (`create_manager_profile_on_user_create` in game/signals.py) legt für JEDEN neu erstellten User automatisch ein `ManagerProfile` an (name=username).

**Why:** Test-Setup mit `ManagerProfile.objects.create(user=...)` nach `create_user()` schlägt mit UniqueViolation auf `user_id` fehl — kostete einen Testlauf beim Notizen-Tablet-Task.

**How to apply:**
- In Tests nach `create_user()` das Profil per `ManagerProfile.objects.get(user=...)` holen, nie neu anlegen.
- Für den "User ohne Managerprofil"-Randfall das auto-erstellte Profil explizit löschen.
- `getattr(user, 'manager_profile', None)` ist als Guard sicher: `RelatedObjectDoesNotExist` erbt von `AttributeError`; im Template ist `{% if user.manager_profile %}` dank `silent_variable_failure` ebenfalls sicher falsy.
