---
name: Manager Career History Table
description: Planned future table for manager career history; current OneToOneField approach is intentionally kept simple.
---

## Current approach (intentional, do not change without reason)

`Club.managed_by = OneToOneField(ManagerProfile, null=True)`

- DB-enforced: UNIQUE on `game_club.managed_by_id`
- Live pointer for fast queries and constraint enforcement
- `claim_club` uses `select_for_update()` on both ManagerProfile and Club rows inside `transaction.atomic()`

## Future: ManagerCareerEntry table

When career features are built (entlassungen, rücktritte, hall of fame, saisonhistorie):

```python
class ManagerCareerEntry(models.Model):
    manager    = ForeignKey(ManagerProfile, on_delete=CASCADE)
    club       = ForeignKey(Club, on_delete=CASCADE)
    started_at = DateField()
    ended_at   = DateField(null=True, blank=True)
    end_reason = CharField(max_length=32, choices=[
        ('resign', 'Rücktritt'),
        ('fired', 'Entlassung'),
        ('season_end', 'Saisonende'),
    ], null=True, blank=True)
    active     = BooleanField(default=True)
```

**Why:** `Club.managed_by` stays as the fast live-pointer; `ManagerCareerEntry` is the history layer added on top without breaking anything.

**How to apply:** On claim → create entry (active=True, started_at=today). On release/fire → set ended_at, active=False, club.managed_by=None. Migration is additive — no changes to existing Club model needed.
