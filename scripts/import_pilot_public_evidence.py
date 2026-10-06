"""Read-only local public fingerprints. Never exports row values or credentials."""
import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.copy_import_pilot_protected import source_state


def capture():
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with conn.cursor() as cur:
            cur.execute("SELECT inet_server_addr() IS NULL OR inet_server_addr() "
                        "IN ('127.0.0.1'::inet,'::1'::inet)")
            if not cur.fetchone()[0]:
                raise RuntimeError("Non-local source forbidden.")
            state = source_state(cur)
            state["metadata"] = {key: hashlib.sha256(
                json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()
                for key, value in state["metadata"].items()}
            return state


if __name__ == "__main__":
    result = capture()
    destination = Path(sys.argv[1])
    if "--compare" in sys.argv:
        before = json.loads(destination.read_text())
        current = json.loads(json.dumps(result, default=str))
        if before != current:
            changed = [key for key in current if current[key] != before.get(key)]
            raise RuntimeError("Public comparison failed in: " + ", ".join(changed))
        print(json.dumps({"public_unchanged": True, "tables": len(result["tables"]),
                          "sequences": len(result["sequences"]), "metadata": "equal"}))
    else:
        destination.write_text(json.dumps(result, default=str, indent=2) + "\n")
        print(json.dumps({"public_baseline": True, "tables": len(result["tables"])}))
