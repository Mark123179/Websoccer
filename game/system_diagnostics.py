"""Read-only Systemdiagnose fuer den Creator Mode.

Der Port folgt dem PHP-Muster aus SystemDiagnosticsService:
Section -> Items, Ampel-Level ok/warn/error/info, Zusammenfassung.
Alle Checks sind lesend: ORM-Counts, DB-Introspection, Migrations-Status,
Settings- und Logdatei-Lesezugriffe. Es werden keine Management-Commands
oder Schreibaktionen ausgefuehrt.
"""

from __future__ import annotations

import os
import platform
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable

import django
from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Avg, Count, Max, Min
from django.db.utils import DatabaseError, OperationalError, ProgrammingError
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

LEVELS = ("error", "warn", "ok", "info")
ERROR_MARKERS = ("ERROR", "CRITICAL", "Traceback", "Exception")
WARN_MARKERS = ("WARNING", "WARN")
MAX_DETAIL_LINES = 18


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_system_diagnostics_report() -> dict[str, Any]:
    """Erzeugt den vollstaendigen Systemanalyse-Report.

    Rueckgabeformat:
    {
        "sections": [{"id", "title", "severity", "items"}],
        "summary": {"error": int, "warn": int, "ok": int, "info": int},
    }
    """
    sections = [
        _safe_section(section_feature_overview),
        _safe_section(section_season_and_simulation),
        _safe_section(section_economy_and_facilities),
        _safe_section(section_database_and_migrations),
        _safe_section(section_django_python_environment),
        _safe_section(section_log_quickcheck),
        _safe_section(section_settings_hints),
    ]

    summary = {level: 0 for level in LEVELS}
    for section in sections:
        for item in section.get("items", []):
            level = item.get("level", "info")
            summary[level if level in summary else "info"] += 1

    return {"sections": sections, "summary": summary}


# ---------------------------------------------------------------------------
# Core helpers: Items, Sections, Severity
# ---------------------------------------------------------------------------


def _item(level: str, title: str, detail: Any) -> dict[str, str]:
    level = level if level in LEVELS else "info"
    return {
        "level": level,
        "title": str(title),
        "detail": _stringify_detail(detail),
    }


def _wrap_section(section_id: str, title: str, items: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "id": section_id,
        "title": title,
        "severity": _severity(items),
        "items": items,
    }


def _severity(items: Iterable[dict[str, str]]) -> str:
    levels = [item.get("level", "info") for item in items]
    if "error" in levels:
        return "error"
    if "warn" in levels:
        return "warn"
    if "ok" in levels:
        return "ok"
    return "info"


def _safe_section(func):
    try:
        return func()
    except Exception as exc:  # Diagnose darf nie die Seite zerstoeren.
        return _wrap_section(
            getattr(func, "__name__", "system-diagnostics"),
            "Systemdiagnose",
            [_item("error", "Sektion konnte nicht aufgebaut werden", f"{exc.__class__.__name__}: {exc}")],
        )


def _stringify_detail(detail: Any) -> str:
    if isinstance(detail, (list, tuple)):
        return "\n".join(str(part) for part in detail)
    if isinstance(detail, dict):
        return "\n".join(f"{key}: {value}" for key, value in detail.items())
    return "" if detail is None else str(detail)


def _limited(lines: Iterable[str], limit: int = MAX_DETAIL_LINES) -> list[str]:
    lines = [str(line) for line in lines if str(line).strip()]
    if len(lines) <= limit:
        return lines
    return lines[:limit] + [f"… {len(lines) - limit} weitere"]


# ---------------------------------------------------------------------------
# Django model / DB introspection helpers
# ---------------------------------------------------------------------------


def _get_model(model_ref: str):
    """Findet ein Model robust per 'app.Model' oder nur per Klassenname.

    Fehlende Models sind Diagnosebefunde, keine Importfehler.
    """
    if not model_ref:
        return None

    if "." in model_ref:
        app_label, model_name = model_ref.split(".", 1)
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    try:
        return apps.get_model("game", model_ref)
    except LookupError:
        pass

    for model in apps.get_models():
        if model.__name__ == model_ref:
            return model
    return None


def _first_model(candidates: Iterable[str]):
    for candidate in candidates:
        model = _get_model(candidate)
        if model is not None:
            return model
    return None


def _model_has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _model_field_column(model, field_name: str) -> str | None:
    try:
        return model._meta.get_field(field_name).column
    except FieldDoesNotExist:
        return None


def _all_table_names() -> set[str]:
    try:
        with connection.cursor() as cursor:
            return set(connection.introspection.table_names(cursor))
    except Exception:
        return set()


def _table_exists(table_name: str | None, table_names: set[str] | None = None) -> bool:
    if not table_name:
        return False
    table_names = table_names if table_names is not None else _all_table_names()
    return table_name in table_names


def _table_columns(table_name: str) -> set[str]:
    try:
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
    except Exception:
        return set()

    columns: set[str] = set()
    for col in description:
        # Django liefert FieldInfo mit .name; einige Backends koennen Tupel liefern.
        columns.add(getattr(col, "name", None) or col[0])
    return columns


def _missing_columns(table_name: str, required_columns: Iterable[str]) -> list[str]:
    existing = _table_columns(table_name)
    return [column for column in required_columns if column not in existing]


def _safe_count(model, **filters) -> tuple[int | None, str | None]:
    try:
        return model.objects.filter(**filters).count(), None
    except Exception as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def _safe_total(model) -> tuple[int | None, str | None]:
    try:
        return model.objects.count(), None
    except Exception as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def _date_value_for_field(model, field_name: str):
    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return timezone.now()
    internal = getattr(field, "get_internal_type", lambda: "")()
    if internal == "DateField":
        return timezone.localdate()
    return timezone.now()


def _format_number(value: Any) -> str:
    if value is None:
        return "–"
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def _format_dt(value: Any) -> str:
    if value is None:
        return "–"
    try:
        if hasattr(value, "strftime"):
            return value.strftime("%d.%m.%Y %H:%M")
    except Exception:
        pass
    return str(value)


# ---------------------------------------------------------------------------
# Sektion 1: Feature-Ampel
# ---------------------------------------------------------------------------


FEATURE_SPECS: list[dict[str, Any]] = [
    {
        "name": "Match Engine / Spielberechnung",
        "models": [
            {"candidates": ["SimulatedMatch"], "fields": ["home_club", "away_club", "home_goals", "away_goals", "report_data", "simulated_at"]},
            {"candidates": ["MatchResult"], "fields": ["home_club", "away_club", "home_goals", "away_goals", "result_label"]},
        ],
        "urls": ["creator_simulation_diagnostics"],
    },
    {
        "name": "Scouting",
        "models": [
            {"candidates": ["ScoutingDepartment"], "fields": ["club", "level", "updated_at"]},
            {"candidates": ["ScoutingAssignment"], "fields": ["club", "status", "started_on", "completes_on", "finds_generated"]},
            {"candidates": ["ScoutingFind"], "fields": ["assignment", "player", "status", "min_bid"]},
            {"candidates": ["ScoutingBid"], "fields": ["club", "player", "amount", "status", "window_date"]},
        ],
        "urls": ["transfer_scouting", "creator_scouting_overview"],
    },
    {
        "name": "Economy & Einrichtungen",
        "models": [
            {"candidates": ["Club"], "fields": ["name", "budget", "league"]},
            {"candidates": ["ClubFinancialTransaction"], "fields": ["club", "date", "category", "amount"]},
            {"candidates": ["ClubSponsor"], "fields": ["club", "name", "sponsor_type", "amount_per_season", "is_active"]},
            {"candidates": ["FacilityConstruction"], "fields": ["club", "facility", "target_level", "completes_at", "status"]},
        ],
        "urls": ["management_finanzen", "management_stadionumfeld"],
    },
    {
        "name": "Verletzungen & Sperren",
        "models": [
            {"candidates": ["Player"], "fields": ["ws_injury_type", "ws_injury_days_remaining", "ws_suspension_reason", "ws_suspension_matches_remaining"]},
            {"candidates": ["PlayerInjuryRecord"], "fields": ["player", "start_date", "end_date", "injury_type", "is_active"]},
            {"candidates": ["PlayerSuspensionRecord"], "fields": ["player", "start_date", "end_date", "reason", "is_active"]},
        ],
    },
    {
        "name": "Saisonlogik",
        "models": [
            {"candidates": ["GameSeasonState", "LeagueSeasonState"], "fields": ["season", "is_active", "current_matchday"]},
            {"candidates": ["LeagueStandings"], "fields": ["league", "club", "season"]},
            {"candidates": ["SeasonGoal"], "fields": ["club", "season"]},
            {"candidates": ["SeasonFixture"], "fields": ["league", "home_club", "away_club", "scheduled_date", "is_simulated"], "optional": True},
        ],
        "urls": ["creator_season_end"],
    },
    {
        "name": "Taktik",
        "models": [
            {"candidates": ["TacticSetup"], "fields": ["club", "squad_scope", "formation", "lineup", "bench", "instructions", "is_locked"]},
            {"candidates": ["TacticTemplate"], "fields": ["club", "squad_scope", "name", "formation", "lineup", "bench"]},
        ],
        "urls": ["club_tactics"],
    },
    {
        "name": "KO-Modus / Pokal",
        "models": [
            {"candidates": ["CupSeason"], "fields": ["competition", "season", "status"]},
            {"candidates": ["CupRound"], "fields": ["cup_season", "round_number", "round_code", "status", "scheduled_date"]},
            {"candidates": ["CupFixture"], "fields": ["cup_round", "home_club", "away_club", "winner_club", "status", "bracket_position"]},
        ],
        "urls": ["cup_tree"],
    },
    {
        "name": "Liveticker / Spielbericht",
        "models": [
            {"candidates": ["SimulatedMatch"], "fields": ["report_data", "simulated_at"]},
        ],
        "urls": ["creator_simulation_diagnostics"],
    },
]


def section_feature_overview() -> dict[str, Any]:
    table_names = _all_table_names()
    items = [_feature_status_item(feature, table_names) for feature in FEATURE_SPECS]
    return _wrap_section("feature-overview", "Feature-Ampel", items)


def _feature_status_item(feature: dict[str, Any], table_names: set[str]) -> dict[str, str]:
    ok: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    for model_spec in feature.get("models", []):
        candidates = model_spec.get("candidates", [])
        model = _first_model(candidates)
        optional = bool(model_spec.get("optional"))
        label = " / ".join(candidates)

        if model is None:
            target = warnings if optional else errors
            target.append(f"Model fehlt: {label}")
            continue

        table_name = model._meta.db_table
        ok.append(f"Model ladbar: {model._meta.label}")
        if _table_exists(table_name, table_names):
            ok.append(f"Tabelle vorhanden: {table_name}")
        else:
            errors.append(f"Tabelle fehlt: {table_name} ({model._meta.label})")
            continue

        required_fields = list(model_spec.get("fields", []))
        missing_fields = [field for field in required_fields if not _model_has_field(model, field)]
        if missing_fields:
            warnings.append(f"Felder fehlen in {model.__name__}: {', '.join(missing_fields)}")

        required_columns = [
            column
            for field in required_fields
            for column in [_model_field_column(model, field)]
            if column
        ]
        missing_columns = _missing_columns(table_name, required_columns)
        if missing_columns:
            warnings.append(f"DB-Spalten fehlen in {table_name}: {', '.join(missing_columns)}")

    for url_name in feature.get("urls", []):
        try:
            reverse(url_name)
            ok.append(f"URL-Name vorhanden: {url_name}")
        except NoReverseMatch:
            warnings.append(f"URL-Name nicht auflösbar: {url_name}")
        except Exception as exc:
            warnings.append(f"URL-Check fehlgeschlagen ({url_name}): {exc}")

    level = "error" if errors else ("warn" if warnings else "ok")
    detail: list[str] = []
    if errors:
        detail += ["Fehler:"] + [f"- {line}" for line in errors]
    if warnings:
        detail += ["Prüfen:"] + [f"- {line}" for line in warnings]
    if ok:
        detail += ["OK:"] + [f"- {line}" for line in _limited(ok)]

    return _item(level, feature.get("name", "Feature"), detail)


# ---------------------------------------------------------------------------
# Sektion 2: Saison & Simulation
# ---------------------------------------------------------------------------


def section_season_and_simulation() -> dict[str, Any]:
    items: list[dict[str, str]] = []

    fixture_model = _first_model(["SeasonFixture"])
    if fixture_model is None:
        items.append(_item("warn", "SeasonFixture", "Model nicht gefunden. Offene Ligaspiel-Queue kann nur geprüft werden, wenn SeasonFixture existiert."))
    else:
        items.extend(_season_fixture_items(fixture_model))

    # CupFixture ist kein Ersatz fuer SeasonFixture, aber als KO-Queue hilfreich.
    cup_fixture_model = _first_model(["CupFixture"])
    if cup_fixture_model is not None:
        items.extend(_cup_fixture_items(cup_fixture_model))

    state_model = _first_model(["LeagueSeasonState", "GameSeasonState"])
    if state_model is None:
        items.append(_item("warn", "Saisonstatus", "Weder LeagueSeasonState noch GameSeasonState gefunden."))
    else:
        items.append(_active_state_item(state_model))

    sim_model = _first_model(["SimulatedMatch"])
    if sim_model is None:
        items.append(_item("warn", "Letzte Simulation", "SimulatedMatch nicht gefunden."))
    else:
        items.append(_last_simulated_match_item(sim_model))

    return _wrap_section("season-simulation", "Saison & Simulation", items)


def _season_fixture_items(model) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not all(_model_has_field(model, field) for field in ["is_simulated", "scheduled_date"]):
        missing = [field for field in ["is_simulated", "scheduled_date"] if not _model_has_field(model, field)]
        return [_item("warn", "SeasonFixture-Felder", f"Fehlende Felder: {', '.join(missing)}")]

    today_or_now = _date_value_for_field(model, "scheduled_date")
    open_count, err = _safe_count(model, is_simulated=False)
    if err:
        items.append(_item("error", "Offene Fixtures", err))
    else:
        items.append(_item("ok" if open_count == 0 else "info", "Offene SeasonFixture", f"{open_count} Fixture(s) mit is_simulated=False."))

    due_count, err = _safe_count(model, is_simulated=False, scheduled_date__lt=today_or_now)
    if err:
        items.append(_item("error", "Vergangene offene Fixtures", err))
    else:
        items.append(_item("warn" if due_count else "ok", "Vergangene offene Fixtures", f"{due_count} offene Fixture(s) mit scheduled_date < heute/jetzt."))

    league_field = "league" if _model_has_field(model, "league") else None
    if league_field:
        try:
            rows = (
                model.objects.filter(is_simulated=False, scheduled_date__lt=today_or_now)
                .values(f"{league_field}_id")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )
            lines = [f"Liga {row[f'{league_field}_id']}: {row['count']} hängend" for row in rows]
            items.append(_item("warn" if lines else "ok", "Hängende Fixtures pro Liga", lines or "Keine hängenden fälligen Fixtures."))
        except Exception as exc:
            items.append(_item("warn", "Hängende Fixtures pro Liga", f"Nicht auswertbar: {exc}"))

    return items


def _cup_fixture_items(model) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not _model_has_field(model, "status"):
        return [_item("info", "CupFixture", "CupFixture vorhanden, aber ohne Statusfeld.")]
    try:
        status_counts = Counter(model.objects.values_list("status", flat=True))
        detail = ", ".join(f"{status}: {count}" for status, count in sorted(status_counts.items())) or "Keine CupFixtures."
        level = "info" if status_counts else "ok"
        items.append(_item(level, "CupFixture-Status", detail))
    except Exception as exc:
        items.append(_item("warn", "CupFixture-Status", f"Nicht auswertbar: {exc}"))
    return items


def _active_state_item(model) -> dict[str, str]:
    try:
        if _model_has_field(model, "is_active"):
            count = model.objects.filter(is_active=True).count()
            return _item("ok" if count else "warn", "Aktive Saisonstatus-Einträge", f"{count} aktive {model.__name__}-Einträge.")
        if _model_has_field(model, "active"):
            count = model.objects.filter(active=True).count()
            return _item("ok" if count else "warn", "Aktive Saisonstatus-Einträge", f"{count} aktive {model.__name__}-Einträge.")
        count = model.objects.count()
        return _item("info", "Saisonstatus-Einträge", f"{count} {model.__name__}-Einträge; kein is_active/active-Feld vorhanden.")
    except Exception as exc:
        return _item("error", "Saisonstatus", f"{exc.__class__.__name__}: {exc}")


def _last_simulated_match_item(model) -> dict[str, str]:
    for field in ["simulated_at", "created_at", "played_at", "updated_at"]:
        if _model_has_field(model, field):
            try:
                last = model.objects.order_by(f"-{field}").values(field).first()
                value = last[field] if last else None
                level = "ok" if value else "info"
                return _item(level, "Letzter SimulatedMatch", f"{field}: {_format_dt(value)}")
            except Exception as exc:
                return _item("warn", "Letzter SimulatedMatch", f"Nicht auswertbar: {exc}")
    return _item("info", "Letzter SimulatedMatch", "Kein geeignetes Datumsfeld gefunden.")


# ---------------------------------------------------------------------------
# Sektion 3: Economy & Einrichtungen
# ---------------------------------------------------------------------------


def section_economy_and_facilities() -> dict[str, Any]:
    items: list[dict[str, str]] = []

    facility_model = _first_model(["FacilityConstruction"])
    if facility_model is None:
        items.append(_item("warn", "FacilityConstruction", "Model nicht gefunden."))
    else:
        items.extend(_facility_items(facility_model))

    club_model = _first_model(["Club"])
    if club_model is None:
        items.append(_item("error", "Club-Budgets", "Club-Model nicht gefunden."))
    else:
        items.append(_club_budget_item(club_model))

    bid_model = _first_model(["ScoutingBid"])
    if bid_model is None:
        items.append(_item("info", "Scouting-Bids", "ScoutingBid-Model nicht gefunden."))
    else:
        items.append(_status_distribution_item(bid_model, "Scouting-Bids", "status"))

    return _wrap_section("economy-facilities", "Economy & Einrichtungen", items)


def _facility_items(model) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        if _model_has_field(model, "status"):
            active_qs = model.objects.filter(status="active")
        elif _model_has_field(model, "is_active"):
            active_qs = model.objects.filter(is_active=True)
        else:
            active_qs = model.objects.all()
        active_count = active_qs.count()
        items.append(_item("info" if active_count else "ok", "Laufende Bauten", f"{active_count} aktive FacilityConstruction-Einträge."))

        if _model_has_field(model, "completes_at"):
            overdue = active_qs.filter(completes_at__lt=timezone.now()).count()
            items.append(_item("warn" if overdue else "ok", "Überfällige Bauten", f"{overdue} aktive Bauten mit completes_at < jetzt."))
    except Exception as exc:
        items.append(_item("error", "FacilityConstruction", f"{exc.__class__.__name__}: {exc}"))
    return items


def _club_budget_item(model) -> dict[str, str]:
    if not _model_has_field(model, "budget"):
        return _item("warn", "Club-Budgets", "Club.budget fehlt.")
    try:
        agg = model.objects.aggregate(min_budget=Min("budget"), max_budget=Max("budget"), avg_budget=Avg("budget"))
        return _item(
            "ok",
            "Club-Budgets",
            f"MIN {_format_number(agg['min_budget'])} / AVG {_format_number(agg['avg_budget'])} / MAX {_format_number(agg['max_budget'])}",
        )
    except Exception as exc:
        return _item("error", "Club-Budgets", f"{exc.__class__.__name__}: {exc}")


def _status_distribution_item(model, title: str, field_name: str) -> dict[str, str]:
    if not _model_has_field(model, field_name):
        return _item("warn", title, f"{model.__name__}.{field_name} fehlt.")
    try:
        rows = model.objects.values(field_name).annotate(count=Count("id")).order_by(field_name)
        detail = ", ".join(f"{row[field_name] or 'leer'}: {row['count']}" for row in rows) or "Keine Einträge."
        return _item("info", title, detail)
    except Exception as exc:
        return _item("warn", title, f"Nicht auswertbar: {exc}")


# ---------------------------------------------------------------------------
# Sektion 4: Datenbank & Migrationen
# ---------------------------------------------------------------------------


def section_database_and_migrations() -> dict[str, Any]:
    items: list[dict[str, str]] = []

    table_names = _all_table_names()
    items.append(_item("ok" if table_names else "warn", "Tabellenzahl", f"{len(table_names)} Tabellen via Introspection gefunden."))

    try:
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        unapplied = [f"{migration.app_label}.{migration.name}" for migration, backwards in plan if not backwards]
        if unapplied:
            items.append(_item("warn", "Unangewendete Migrationen", _limited(unapplied, 25)))
        else:
            items.append(_item("ok", "Migrationsstatus", "Keine unangewendeten Migrationen."))
    except Exception as exc:
        items.append(_item("warn", "Migrationsstatus", f"Nicht auswertbar: {exc.__class__.__name__}: {exc}"))

    items.append(_database_version_item())

    return _wrap_section("database-migrations", "Datenbank & Migrationen", items)


def _database_version_item() -> dict[str, str]:
    vendor = connection.vendor
    try:
        with connection.cursor() as cursor:
            if vendor == "sqlite":
                cursor.execute("SELECT sqlite_version()")
            else:
                cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
        return _item("info", "Datenbank-Version", f"{vendor}: {version}")
    except Exception as exc:
        return _item("warn", "Datenbank-Version", f"{vendor}: {exc.__class__.__name__}: {exc}")


# ---------------------------------------------------------------------------
# Sektion 5: Django/Python-Umgebung
# ---------------------------------------------------------------------------


def section_django_python_environment() -> dict[str, Any]:
    default_db = settings.DATABASES.get("default", {})
    allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
    installed_apps = list(getattr(settings, "INSTALLED_APPS", []))
    registered_models = list(apps.get_models())

    items = [
        _item("info", "Python-Version", sys.version.replace("\n", " ")),
        _item("info", "Django-Version", django.get_version()),
        _item("warn" if getattr(settings, "DEBUG", False) else "ok", "DEBUG", str(getattr(settings, "DEBUG", False))),
        _item("info", "Datenbank-Engine", str(default_db.get("ENGINE", "–"))),
        _item("info", "Installierte Apps", str(len(installed_apps))),
        _item("info", "Registrierte Models", str(len(registered_models))),
        _item("info", "ALLOWED_HOSTS", ", ".join(allowed_hosts) if allowed_hosts else "leer"),
        _item("info", "Plattform", platform.platform()),
    ]
    return _wrap_section("environment", "Django/Python-Umgebung", items)


# ---------------------------------------------------------------------------
# Sektion 6: Log-Schnellcheck
# ---------------------------------------------------------------------------


def section_log_quickcheck() -> dict[str, Any]:
    files = _discover_log_files()
    items: list[dict[str, str]] = []

    if not files:
        return _wrap_section(
            "logs",
            "Log-Schnellcheck",
            [_item("info", "Logdateien", "Keine *.log-Dateien unter /tmp/logs, .local/state, tmp/logs oder logs gefunden.")],
        )

    any_hits = False
    for path in files[:30]:
        try:
            lines = _tail_file(path, 50)
        except Exception as exc:
            items.append(_item("warn", path.name, f"Nicht lesbar: {exc}"))
            continue

        hits = [line for line in lines if _line_has_marker(line)]
        if hits:
            any_hits = True
            level = "error" if any(marker in "\n".join(hits) for marker in ("ERROR", "CRITICAL", "Traceback")) else "warn"
            items.append(_item(level, str(path), _limited(hits[-8:], 8)))
        else:
            items.append(_item("ok", str(path), f"Letzte {len(lines)} Zeilen ohne ERROR/CRITICAL/Traceback."))

    if len(files) > 30:
        items.append(_item("info", "Weitere Logdateien", f"{len(files) - 30} weitere Logdatei(en) ausgelassen."))

    if not any_hits and items:
        # Einzelitems bleiben ok; die Sektion wird dadurch ebenfalls ok.
        pass

    return _wrap_section("logs", "Log-Schnellcheck", items)


def _discover_log_files() -> list[Path]:
    base_dir = Path(getattr(settings, "BASE_DIR", "."))
    candidates = [
        Path("/tmp/logs"),
        base_dir / ".local" / "state",
        base_dir / "tmp" / "logs",
        base_dir / "logs",
    ]
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        candidates.append(Path(xdg_state_home))

    files: list[Path] = []
    seen: set[Path] = set()
    for directory in candidates:
        try:
            if not directory.exists() or not directory.is_dir():
                continue
            for path in directory.rglob("*.log"):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    files.append(path)
        except Exception:
            continue
    return sorted(files, key=lambda p: str(p))


def _tail_file(path: Path, lines: int) -> list[str]:
    buf: deque[str] = deque(maxlen=lines)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if len(line) > 800:
                line = line[:800] + " …"
            buf.append(line)
    return list(buf)


def _line_has_marker(line: str) -> bool:
    upper = line.upper()
    return any(marker.upper() in upper for marker in ERROR_MARKERS + WARN_MARKERS)


# ---------------------------------------------------------------------------
# Sektion 7: Einstellungen / Hinweise
# ---------------------------------------------------------------------------


def section_settings_hints() -> dict[str, Any]:
    items: list[dict[str, str]] = []

    debug = bool(getattr(settings, "DEBUG", False))
    items.append(_item("warn" if debug else "ok", "DEBUG", "DEBUG=True — im Deployment abschalten." if debug else "DEBUG=False."))

    secret_env_keys = ["SECRET_KEY", "DJANGO_SECRET_KEY"]
    secret_from_env = next((key for key in secret_env_keys if os.environ.get(key)), None)
    if secret_from_env:
        items.append(_item("ok", "SECRET_KEY", f"Als Env-Variable gesetzt ({secret_from_env})."))
    else:
        items.append(_item("info", "SECRET_KEY", "Nicht als SECRET_KEY/DJANGO_SECRET_KEY-Env-Variable erkennbar. Falls lokal hart gesetzt: für Deployment in Env auslagern."))

    allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
    if allowed_hosts == ["*"] or "*" in allowed_hosts:
        items.append(_item("info", "ALLOWED_HOSTS", "Wildcard '*' gesetzt. Für Produktion besser konkrete Hosts setzen."))
    elif allowed_hosts:
        items.append(_item("ok", "ALLOWED_HOSTS", ", ".join(allowed_hosts)))
    else:
        items.append(_item("warn", "ALLOWED_HOSTS", "Leer. Im Deployment muss mindestens der Zielhost gesetzt sein."))

    csrf_hosts = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []))
    items.append(_item("info", "CSRF_TRUSTED_ORIGINS", ", ".join(csrf_hosts) if csrf_hosts else "leer"))

    return _wrap_section("settings-hints", "Einstellungen (Hinweise)", items)
