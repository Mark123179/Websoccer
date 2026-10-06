"""T1 checks in rollback-only transactions; not a package/import simulation."""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
import django
django.setup()
from django.apps import apps
from django.db import connection, transaction, IntegrityError
from django.test import Client
from django.db.migrations.loader import MigrationLoader
from psycopg2 import sql
from game import models as gm
from game.import_schema import POST_START_FIELDS
from scripts.copy_import_pilot_protected import TABLES, fingerprint, rows


def check():
    result = {}
    columns = {}
    for model in apps.get_models():
        columns.setdefault(model._meta.db_table, set()).update(
            f.column for f in model._meta.concrete_fields)
    for filename in ("feldliste-n27.md", "feldliste-n27-paketfelder.md"):
        checked = 0
        for line in (ROOT / "docs/import-pilot" / filename).read_text().splitlines():
            if not line.startswith("| "):
                continue
            cell = line.split("|")[1 if filename == "feldliste-n27.md" else 2].strip()
            cell = cell.split("#")[0]
            if not re.fullmatch(r"game_\w+\.\w+", cell):
                continue
            if cell.startswith("game_playerapplication."):
                continue  # Explicit deferred youth proposal, not T1.
            table, column = cell.split(".")
            assert column in columns.get(table, set()), "Missing field-list target: " + cell
            checked += 1
        result[filename] = {"checked_sql_targets": checked, "missing": 0}
    assert gm.Player._meta.get_field("real_life_club").null
    assert not any(f.name.startswith("real_loan_") for f in gm.Player._meta.fields)
    assert gm.Club._meta.get_field("league").null is False
    assert "nur_verweis" not in dict(gm.Club._meta.get_field("import_state").choices)
    assert all(not any("position" in name for name in fields)
               for fields in POST_START_FIELDS.values())
    result["n29_n30_n31"] = True

    with transaction.atomic():
        league = gm.League(id=-100, name="T1 rollback fixture")
        gm.League.objects.bulk_create([league])
        club = gm.Club(id=-100, name="T1 rollback fixture", league=league,
                       founded_year=2000, budget=0)
        gm.Club.objects.bulk_create([club])
        player = gm.Player(id=-100, first_name="T1", last_name="Rollback", age=20,
                           club=None, market_value=None)
        gm.Player.objects.bulk_create([player])
        original = gm.Player.objects.filter(pk=player.pk).values(
            "market_value", "salary_per_match").get()
        source = gm.DataSource.objects.filter(code="FM").first()
        assert source is not None, "Protected FM catalog entry missing."
        for i in range(12):
            gm.PlayerMarketValueSnapshot(
                id=-1000-i, player=player, recorded_at=date(2025, 1, 1),
                value_eur=i*1000, source=source, origin="real", source_row_key="t1-" + str(i),
                update_current=True).save()
            gm.PlayerSourceRatingSnapshot(
                id=-1000-i, player=player, source=source,
                recorded_at=date(2025, 1, 1), rating=60+i, potential=80,
                source_version="t1-" + str(i), payload_hash=format(i, "064x"),
                update_current=True).save()
        assert gm.PlayerMarketValueSnapshot.objects.filter(player=player).count() == 12
        assert gm.PlayerSourceRatingSnapshot.objects.filter(player=player).count() == 12
        assert gm.Player.objects.filter(pk=player.pk).values(
            "market_value", "salary_per_match").get() == original
        assert not gm.PlayerSourceRating.objects.filter(player=player).exists()
        player.owner_club = club
        player.owner_club_tm_id = 17
        player.loan_club_tm_id = 18
        assert player.is_in_loan_pool
        assert player.import_lock
        stadium = gm.Stadium(club=club)
        assert stadium.capacity_total is None
        for side in ("nord", "ost", "sued", "west"):
            for kind in ("standing", "seating", "vip"):
                setattr(stadium, side + "_" + kind, 0)
        assert stadium.capacity_total == 0
        coach = gm.HistoricCoach(id=-100, name="T1 rollback person", person_kind="trainer")
        gm.HistoricCoach.objects.bulk_create([coach])
        external_source = (source if gm.PlayerExternalId._meta.get_field("source").is_relation
                           else source.code)
        gm.PlayerExternalId.objects.bulk_create([
            gm.PlayerExternalId(id=-100, player=player, source=external_source,
                external_id="123", identity_kind="spieler", status="gefunden"),
            gm.PlayerExternalId(id=-101, person=coach, source=external_source,
                external_id="123", identity_kind="trainer", status="gefunden"),
        ])
        try:
            with transaction.atomic():
                gm.PlayerExternalId.objects.bulk_create([
                    gm.PlayerExternalId(id=-102, source=external_source, external_id="124")])
        except IntegrityError as error:
            assert error.__cause__.diag.constraint_name == "external_id_exactly_one_owner"
        else:
            raise AssertionError("Owner XOR not enforced.")
        transaction.set_rollback(True)
    result["rollback_snapshot_checks"] = {
        "mw_history_rows": 12, "rating_history_rows": 12,
        "same_day_versions_preserved": True, "implicit_writes": 0,
        "loan_pool_property": True, "default_import_lock": True,
        "unknown_capacity_none_and_known_zero_distinct": True,
        "typed_external_identity_spaces": True, "owner_xor_constraint": True,
    }
    client = Client(HTTP_HOST="localhost")
    assert client.get("/health/").status_code == 200
    assert client.post("/health/").status_code == 403
    result["http_health_and_t1_mutation_block"] = True

    evidence = json.loads((ROOT / "docs/import-pilot/t1-schema-evidence.json").read_text())
    with connection.cursor() as cur:
        live_tables = [r[0] for r in rows(cur,
            "SELECT tablename FROM pg_tables WHERE schemaname='import_pilot' "
            "AND tablename NOT LIKE 't1_saved_%%' "
            "AND tablename NOT IN ('django_migrations','django_session')")]
        for table in live_tables:
            if table not in TABLES:
                assert rows(cur, 'SELECT count(*) FROM "import_pilot"."%s"' % table)[0][0] == 0
        result["business_tables_zero"] = len([t for t in live_tables if t not in TABLES])
        for table in TABLES:
            record = evidence["protected"][table]
            assert fingerprint(cur, sql.SQL(
                "SELECT {} FROM {} a JOIN {} b ON a.id=b.id").format(
                    sql.SQL(",").join(
                        sql.Identifier("a", col)
                        for col in record["columns"]),
                    sql.Identifier("import_pilot", table),
                    sql.Identifier("import_pilot", "t1_saved_" + table))) == (
                        record["before_rows"], record["before_fingerprint"])
        result["protected_fingerprints_equal_after_checks"] = len(TABLES)
    loader = MigrationLoader(connection)
    from django.db.migrations.executor import MigrationExecutor
    assert not MigrationExecutor(connection).migration_plan(loader.graph.leaf_nodes())
    result["unapplied_migrations"] = 0
    before = json.loads((ROOT / "docs/import-pilot/t1-strength-before.json").read_text())
    after = json.loads((ROOT / "docs/import-pilot/t1-strength-after.json").read_text())
    assert before == after
    result["strength_parity"] = before
    return result


if __name__ == "__main__":
    result = check()
    (ROOT / "docs/import-pilot/t1-checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
