"""T2 backend acceptance in rollback-only pilot transactions. No public writes."""
import copy
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
import django
django.setup()
from django.db import connection, transaction
from django.db.models import Q
from django.test import RequestFactory
from django.contrib import admin
from django.contrib.auth.models import User
from psycopg2 import sql
from game import models as m
from game.club_import.package_validation import read_package, PackageError
from game.club_import.package_service import apply_package
from game.club_import.runtime import assign_review_player, can_scout, scouting_condition, match_condition
from scripts.copy_import_pilot_protected import fingerprint, TABLES

PACKAGE = ROOT / "attached_assets/bvb_vereinspaket_2026-10-05_1_1791225377498.zip"
MANIFEST, DATA = read_package(PACKAGE)


def pack(data, manifest=None):
    manifest = copy.deepcopy(manifest or MANIFEST)
    for key in ("players", "persons", "records", "titles"):
        manifest["counts"][key] = len(data[key])
    for severity in ("blocking", "player_lock", "info"):
        manifest["counts"]["gaps_" + severity] = sum(
            g["severity"] == severity for g in data["gaps"])
    raw = json.dumps(data, ensure_ascii=False).encode()
    manifest["data_sha256"] = hashlib.sha256(raw).hexdigest()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("data.json", raw)
    return output.getvalue()


def state():
    with connection.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='import_pilot'")
        names = [r[0] for r in cur.fetchall()]
        return {name: fingerprint(cur, sql.SQL("SELECT * FROM {}").format(
                    sql.Identifier("import_pilot", name)))
                for name in names if not name.startswith("t1_saved_")}


def check():
    with connection.cursor() as c:
        c.execute("SELECT current_schema(),current_user")
        schema, role = c.fetchone()
        assert schema == "import_pilot" and role == "import_pilot_role", (schema, role)
    results = {}
    assert m.Player.objects.count() == m.Club.objects.count() == 0, (
        "This pre-import acceptance requires the empty pilot; do not clear an imported pilot.")
    before = state()
    with transaction.atomic():
        league = m.League.objects.create(name="T2 rollback Bundesliga", country="Deutschland")
        applied = apply_package(PACKAGE, league)
        club = m.Club.objects.get(pk=applied["club"])
        assert m.Player.objects.count() == 51
        assert m.Player.objects.filter(import_lock=True).count() == 2
        assert m.PlayerStrengthProfile.objects.count() == 35
        dynamic = m.Player.objects.filter(import_lock=False, strength_profile__isnull=True)
        assert dynamic.count() == 14
        assert all(p.potential is None for p in dynamic)
        assert m.Player.objects.filter(real_life_club__isnull=False).count() == 0
        assert m.Club.objects.count() == 1
        assert m.Player.objects.filter(club=club, squad_team="first").count() == 28
        assert m.Player.objects.filter(club=club, squad_team="u21").count() == 19
        assert sum(p.is_in_loan_pool for p in m.Player.objects.all()) == 4
        assert m.PlayerMarketValueSnapshot.objects.filter(is_start_value=True).count() == 6
        assert m.PlayerMarketValueSnapshot.objects.filter(origin="real").count() == sum(
            len(p["market_values"]) for p in DATA["players"])
        assert m.PlayerTransferHistory.objects.count() == sum(len(p["transfers"]) for p in DATA["players"])
        assert m.ClubRecord.objects.count() == 24
        assert m.ClubTrophyEntry.objects.count() == 30
        assert m.HistoricCoach.objects.count() == 11
        assert m.ImportIssue.objects.filter(severity="player_lock").count() == 2
        assert m.ImportIssue.objects.filter(severity="info").count() == 154
        for p in m.Player.objects.all():
            assert p.salary_per_match == p.market_value / 1_000_000 * 5000
        results["initial_counts_and_no_placeholder_clubs"] = True
        snap = state()
        assert apply_package(PACKAGE, league)["unchanged"]
        assert state() == snap
        results["identical_second_upload_all_table_fingerprints"] = True
        # Validation failure occurs before writes; identity conflict rolls back ALL writes.
        with transaction.atomic():
            bad = copy.deepcopy(DATA)
            bad["stadium"]["stands"]["N"]["seating"]["value"] += 1
            try:
                apply_package(pack(bad), league)
                raise AssertionError("Invalid sum was accepted")
            except PackageError:
                pass
            assert state() == snap
        with transaction.atomic():
            bad = copy.deepcopy(DATA)
            bad["players"][0]["ids"]["fmi"] = bad["players"][1]["ids"]["fmi"]
            try:
                apply_package(pack(bad), league)
                raise AssertionError("Split identity was accepted")
            except PackageError:
                pass
            assert state() == snap
        results["invalid_sum_and_identity_conflict_atomic"] = True
        # Omission preserves IDs, source ratings and histories; all three pools are disjoint.
        with transaction.atomic():
            reduced = copy.deepcopy(DATA)
            omitted = reduced["players"].pop(0)
            apply_package(pack(reduced), league)
            p = m.Player.objects.get(transfermarkt_id=omitted["ids"]["tm"]["value"])
            assert p.review_pool and p.club_id is None and not p.is_in_loan_pool and not can_scout(p)
            assert p.source_ratings.exists() and p.market_value_snapshots.exists() and p.external_ids.exists()
            assert not m.Player.objects.filter(scouting_condition(), pk=p.pk).exists()
            apply_package(PACKAGE, league)  # Earlier bytes are not skipped after an intervening package.
            p.refresh_from_db()
            assert not p.review_pool and p.club_id == club.pk
            assert m.ImportIssue.objects.filter(field="review_pool", resolution_status="resolved").exists()
            transaction.set_rollback(True)
        results["review_pool_omission_and_automatic_reassignment"] = True
        with transaction.atomic():
            p = m.Player.objects.get(transfermarkt_id=DATA["players"][0]["ids"]["tm"]["value"])
            p.club = None
            p.review_pool = True
            p.save()
            assign_review_player(p, club)
            p.refresh_from_db()
            assert not p.review_pool and p.club_id == club.pk
            transaction.set_rollback(True)
        results["controlled_review_assignment"] = True
        # Only N30 positive-list fields/IDs/records/titles may change after start.
        with transaction.atomic():
            m.LeagueSeasonState.objects.create(league=league, season=0, current_matchday=2)
            old_players = list(m.Player.objects.order_by("pk").values(
                "pk", "club_id", "owner_club_id", "owner_club_tm_id", "loan_club_tm_id",
                "squad_team", "import_lock", "review_pool", "position", "primary_position",
                "source_positions", "main_position_1", "potential", "market_value", "salary_per_match"))
            old_ratings = list(m.PlayerSourceRating.objects.order_by("pk").values())
            old_history = (m.PlayerMarketValueSnapshot.objects.count(), m.PlayerTransferHistory.objects.count())
            old_stadium = m.Stadium.objects.get(club=club).nord_seating
            changed = copy.deepcopy(DATA)
            changed["club"]["motto"] += " test"
            changed["stadium"]["name"] += " test"
            changed["players"][0]["last_name"] += " test"
            changed["players"][0]["market_value_eur"] = 1
            changed["players"][0]["ratings"]["fminside"]["rating"] = 1
            changed["players"][0]["positions"]["main"] = ["ST"]
            changed["players"].pop()
            apply_package(pack(changed), league)
            assert list(m.Player.objects.order_by("pk").values(*old_players[0])) == old_players
            assert list(m.PlayerSourceRating.objects.order_by("pk").values()) == old_ratings
            assert old_history == (m.PlayerMarketValueSnapshot.objects.count(), m.PlayerTransferHistory.objects.count())
            assert m.Stadium.objects.get(club=club).nord_seating == old_stadium
            assert m.Stadium.objects.get(club=club).name.endswith(" test")
            assert m.Player.objects.get(pk=old_players[0]["pk"]).last_name.endswith(" test")
            transaction.set_rollback(True)
        results["post_start_positive_mask"] = True
        # Later imported reference club links by TM ID, not by matching its name.
        with transaction.atomic():
            foreign = copy.deepcopy(DATA)
            foreign["club"]["name"] = "Different name, same destination identity"
            foreign["club"]["ids"]["tm"]["value"] = 190
            for key, val in (("fmi", 900000907), ("cmtracker", 90000022), ("api_football", 90000165)):
                foreign["club"]["ids"][key]["value"] = val
            foreign["players"] = []
            foreign["persons"] = []
            foreign["records"] = []
            foreign["titles"] = []
            foreign["gaps"] = []
            manifest = copy.deepcopy(MANIFEST)
            manifest["club"]["tm_id"] = 190
            manifest["club"]["fmi_id"] = 900000907
            foreign_league = m.League.objects.create(name="T2 non-playable", country="Danmark", is_playable=False)
            imported = apply_package(pack(foreign, manifest), foreign_league)
            destination = m.Club.objects.get(pk=imported["club"])
            p = m.Player.objects.get(transfermarkt_id=next(
                p["ids"]["tm"]["value"] for p in DATA["players"] if p["display_name"] == "Diant Ramaj"))
            assert p.club_id == destination.pk and p.loan_club_id == destination.pk and not p.is_in_loan_pool
            assert p.loan_status == "loaned_in" and can_scout(p)
            assert m.Player.objects.filter(scouting_condition(), pk=p.pk).exists()
            transaction.set_rollback(True)
        results["external_reference_backfill_and_nonplayable_scouting"] = True
        # Admin helpers/forms never expose RL ownership in package mode.
        from game.admin import PlayerNationalityForm
        request = RequestFactory().get("/")
        request.user = User(is_superuser=True, is_staff=True, is_active=True)
        for model in (m.Player, m.PlayerDataReview):
            ma = admin.site._registry[model]
            assert "real_life_club" not in str(ma.get_list_filter(request))
            assert "real_life_club" not in str(ma.get_fieldsets(request))
        assert "real_life_club" not in PlayerNationalityForm().fields
        assert m.Player.objects.filter(match_condition()).count() == 28
        results["n35_admin_and_first_team_eligibility"] = True
        transaction.set_rollback(True)
    assert state() == before
    results["rollback_restores_all_pilot_table_fingerprints"] = True
    output = ROOT / "docs/import-pilot/t2-backend-checks.json"
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    check()
