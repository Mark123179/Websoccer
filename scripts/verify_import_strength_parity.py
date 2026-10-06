"""T1 parity on synthetic, identical inputs; never imports package or ORM rows."""
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class Query(list):
    def all(self):
        return self

    def filter(self, **kwargs):
        return self

    def order_by(self, *args):
        return self


def measure():
    import django
    django.setup()
    from game.strength_service import compute_strength_for_player, OUTFIELD_ATTR_COLS, GK_ATTR_COLS
    outputs = []
    for position in ("TW", "IV", "ZM", "ST"):
        for ratings in ((75, 80), (None, 80), (75, None), (None, None)):
            for potential in (None, 90):
                for freshness in (0, 65, 100):
                    rows = Query()
                    for source, rating in zip(("FM", "CMTRACKER"), ratings):
                        if rating is not None:
                            values = dict(source=source, rating=rating, potential=potential)
                            values.update({key: 35 + i % 40 for i, key in enumerate(
                                OUTFIELD_ATTR_COLS + GK_ATTR_COLS)})
                            rows.append(SimpleNamespace(**values))
                    player = SimpleNamespace(
                        source_ratings=rows, position=position,
                        main_positions=[position], secondary_positions=["DM"],
                        strength_profile=SimpleNamespace(freshness=freshness),
                        form_snapshots=Query([SimpleNamespace(rating=7.1, minutes_played=90)]),
                    )
                    outputs.append(compute_strength_for_player(player))
    encoded = json.dumps(outputs, default=str, sort_keys=True)
    return {
        "cases": len(outputs),
        "outputs_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "code": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                 for p in ("game/strength_service.py", "game/strength_engine.py")},
    }


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    result = measure()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
