---
name: game/tests Package-Falle
description: game/tests/ ist ein Package das game/tests.py überlagert; neue Tests müssen in game/tests/test_*.py angelegt werden.
---

## Regel

Neue Tests IMMER in `game/tests/test_*.py` anlegen — **nicht** in `game/tests.py`.

## Warum

`game/tests/` ist ein Python-Package mit `__init__.py`. Python bevorzugt das Package über die gleichnamige `.py`-Datei. `game/tests.py` existiert noch (historisch), wird aber von Django's Test-Runner und von `import game.tests` vollständig ignoriert. Edits an `game/tests.py` gehen ins Leere.

## Aktueller Stand (Stand 2026-06-15)

```
game/tests/
├── __init__.py          (leer)
├── test_cup_service.py  (43 Tests)
├── test_default_tactic_v1.py  (13 Tests)
├── test_ko_match.py     (27 Tests)
└── test_matchday_xi.py  (26 Tests)
```

Gesamt: 109 Tests.

## Import-Stil in Package-Dateien

Absoluter Import (nicht relativ):
```python
from game.models import Club, League, Player
from game.match_engine import simulate_match
```

## Wie man eine neue Testdatei anlegt

1. Datei `game/tests/test_<feature>.py` erstellen
2. `from django.test import TestCase` für DB-Tests
3. `from game.models import ...` für Modell-Imports
4. Für ORM-freie Tests: minimaler Django-Setup wie in `test_ko_match.py`
