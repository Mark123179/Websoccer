"""Central N37 package transaction. Existing game anchors, no UI or network."""
from datetime import date, datetime, time
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone

from game import models as m
from game.import_schema import POST_START_FIELDS
from .package_validation import PackageError, digest, read_package
from .runtime import package_mode
from .import_ready_csv import FMI_ATTR_MAP, SOFIFA_ATTR_MAP

PROVIDERS = {"fmi": "FM", "tm": "TM", "cmtracker": "CMTRACKER",
             "api_football": "API_FOOTBALL"}
SIDES = {"N": "nord", "E": "ost", "S": "sued", "W": "west"}


def league_started(league):
    return (m.LeagueSeasonState.objects.filter(league=league).filter(
        Q(current_matchday__gt=1) | Q(is_simulated=True) | Q(completed_at__isnull=False)).exists()
        or m.SimulatedMatch.objects.filter(
            Q(home_club__league=league) | Q(away_club__league=league)).exists())


def patch(obj, values, after_start=False):
    if after_start:
        values = {k: v for k, v in values.items()
                  if k in POST_START_FIELDS.get(type(obj).__name__, ())}
    for key, value in values.items():
        setattr(obj, key, value)
    obj._suppress_club_history = True
    obj.save()


def source(code):
    return m.DataSource.objects.get_or_create(code=code, defaults={"name": code})[0]


def resolve_club(reference):
    return (m.Club.objects.filter(transfermarkt_id=reference.get("tm_id")).first()
            if reference and reference.get("tm_id") else None)


def issue(run, entity, ref, field, note, severity="info", reference=None):
    return m.ImportIssue.objects.get_or_create(
        package=run, entity=entity, entity_ref=ref, field=field,
        note=note, severity=severity,
        defaults={"external_reference": reference or {}})[0]


def identity(ids, model, kind="spieler"):
    """All external IDs must agree. No matching by name, birth date or local ref."""
    found = set()
    for provider, entry in ids.items():
        value = entry.get("value")
        if value is None:
            continue
        if model is m.Club:
            rows = m.ClubExternalId.objects.filter(
                source__code=PROVIDERS[provider], external_id=str(value))
            found.update(rows.values_list("club_id", flat=True))
        else:
            rows = m.PlayerExternalId.objects.filter(
                source__code=PROVIDERS[provider], external_id=str(value), identity_kind=kind)
            found.update(rows.values_list(
                "player_id" if model is m.Player else "person_id", flat=True))
            if provider == "tm" and model is m.Player:
                found.update(m.Player.objects.filter(transfermarkt_id=value).values_list("pk", flat=True))
            if provider == "fmi" and model is m.Player:
                found.update(m.Player.objects.filter(fm_inside_id=value).values_list("pk", flat=True))
        found.discard(None)
    if len(found) > 1:
        raise PackageError("Conflicting external identities; no automatic merge.")
    return model.objects.select_for_update().filter(pk=next(iter(found))).first() if found else None


def sync_ids(obj, ids, run, kind="spieler"):
    table = m.ClubExternalId if isinstance(obj, m.Club) else m.PlayerExternalId
    owner_key = "club" if table is m.ClubExternalId else (
        "player" if isinstance(obj, m.Player) else "person")
    mirror = {"fmi": "fm_inside_id", "tm": "transfermarkt_id",
              "cmtracker": "cmtracker_id", "api_football": "api_football_id"}
    for provider, entry in ids.items():
        ds = source(PROVIDERS[provider])
        value = entry.get("value")
        if value is not None:
            conflict = table.objects.filter(source=ds, external_id=str(value))
            if table is m.PlayerExternalId:
                conflict = conflict.filter(identity_kind=kind)
            if conflict.exclude(**{owner_key: obj}).exists():
                issue(run, owner_key, str(obj.pk), "ids." + provider,
                      "ID already belongs to another identity.", "player_lock", entry)
                if isinstance(obj, m.Player):
                    obj.import_lock = True
                    obj.save(update_fields=["import_lock"])
                continue
        defaults = {"external_id": str(value) if value is not None else None,
                    "status": entry.get("status", "nicht_gefunden"),
                    "checked_at": entry.get("checked_at") or None}
        if table is m.PlayerExternalId:
            defaults.update(identity_kind=kind, match_evidence={"match": entry.get("match")})
        table.objects.update_or_create(**{owner_key: obj}, source=ds, defaults=defaults)
        field = mirror[provider]
        if any(f.name == field for f in obj._meta.fields):
            setattr(obj, field, value)
            obj.save(update_fields=[field])


def attributes(block, provider, is_gk):
    """Use the existing PSR mapping, keeping every unused raw attribute in archive."""
    if provider == "cmtracker":
        from game.cmtracker_api import CSV_COLUMNS, player_to_row
        from game.management.commands.import_sofifa_csv import (
            COLUMN_ALIASES, normalize_header, GK_ATTR_COLUMNS, OUTFIELD_ATTR_COLUMNS)
        allowed = GK_ATTR_COLUMNS if is_gk else OUTFIELD_ATTR_COLUMNS
        return {COLUMN_ALIASES[normalize_header(key)]: int(value) if value else None
                for key, value in zip(CSV_COLUMNS, player_to_row(block.get("raw") or {}))
                if COLUMN_ALIASES.get(normalize_header(key)) in allowed}
    raw = (block.get("raw") or {}).get("attributes") or {}
    normalized = {k.lower().replace(" ", "_").replace("-", "_"): v for k, v in raw.items()}
    mapping = FMI_ATTR_MAP if provider == "fminside" else SOFIFA_ATTR_MAP
    aliases = ({"gk_reflexes": "reflexes", "gk_handling": "handling",
                "gk_one_on_ones": "one_on_ones", "gk_positioning": "positioning",
                "gk_passing": "passing"} if provider == "fminside" else {
                    "pace": "sprintspeed", "short_passing": "shortpassing",
                    "standing_tackle": "standingtackle", "defensive_awareness": "marking",
                    "heading": "headingaccuracy", "free_kick": "freekickaccuracy",
                    "gk_reflexes": "gkreflexes", "gk_handling": "gkhandling",
                    "gk_positioning": "gkpositioning", "gk_passing": "gkkicking"})
    return {column: normalized.get(aliases.get(key, key))
            for key, column in mapping.items() if column.startswith("tw_") == is_gk}


def project_ratings(player, data, run):
    for provider, code in (("fminside", "FM"), ("cmtracker", "CMTRACKER")):
        block = data["ratings"].get(provider)
        if not block or block.get("rating") is None:
            m.PlayerSourceRating.objects.filter(player=player, source=code).delete()
            continue
        ds = source(code)
        version = str(block.get("version") or block.get("db") or "")
        m.PlayerSourceRatingSnapshot.objects.get_or_create(
            player=player, source=ds, recorded_at=run.collected_at.date(),
            source_version=version, payload_hash=digest(block),
            defaults={"rating": block["rating"], "potential": block.get("potential"),
                      "raw_payload": block, "source_url": block.get("url") or "",
                      "update_current": False})
        # Explicit projection, bulk avoids implicit signal-based recalculation.
        values = {"rating": block["rating"], "potential": block.get("potential"),
                  "source_version": version, "checked_at": run.collected_at.date(),
                  "source_url": block.get("url") or ""}
        attr_fields = [f.name for f in m.PlayerSourceRating._meta.fields
                       if f.get_internal_type() == "PositiveSmallIntegerField"
                       and f.name not in ("rating", "potential")]
        values.update({name: None for name in attr_fields})
        values.update(attributes(block, provider, player.position == "TW"))
        m.PlayerSourceRating.objects.filter(player=player, source=code).delete()
        m.PlayerSourceRating.objects.bulk_create([
            m.PlayerSourceRating(player=player, source=code, **values)])
    potentials = [r.potential for r in player.source_ratings.all() if r.potential is not None]
    player.potential = max(potentials) if potentials else None
    player.save(update_fields=["potential"])
    from game.strength_service import compute_strength_for_player
    result = compute_strength_for_player(player)
    if result["computable"]:
        m.PlayerStrengthProfile.objects.update_or_create(player=player, defaults={
            "base_strength": result["base_strength"], "form_modifier": Decimal("0"),
            "freshness": Decimal("100")})
    else:
        m.PlayerStrengthProfile.objects.filter(player=player).delete()
    return result


def reference_issue(run, ref):
    if ref and not ref.get("tm_id") and ref.get("name"):
        # The reference package already lists these thirteen names as club gaps.
        gap = next((g for g in run.package_data["gaps"]
                    if g["entity"] == "club" and ref["name"] in g["ref"]), None)
        if gap:
            m.ImportIssue.objects.filter(package=run, entity="club",
                entity_ref=gap["ref"], field=gap["field"]).update(external_reference=ref)
            return
        issue(run, "club_reference", ref["name"], "tm_id",
              "Club TM identity missing; original name retained.", reference=ref)


def real_histories(player, data, run):
    ds = source("TM")
    for point in data["market_values"]:
        reference = point.get("club")
        reference_issue(run, reference)
        m.PlayerMarketValueSnapshot.objects.get_or_create(
            player=player, origin="real", source_row_key=digest(point), defaults={
                "source": ds, "recorded_at": point["date"], "value_eur": point["value_eur"],
                "club": resolve_club(reference),
                "club_tm_id": (reference or {}).get("tm_id"),
                "club_original_name": (reference or {}).get("name"),
                "raw_payload": point, "package": run, "update_current": False})
    current = data.get("market_value_eur")
    if current is None:
        m.PlayerMarketValueSnapshot.objects.get_or_create(
            player=player, origin="sim", source_row_key="initial-value-50000", defaults={
                "source": ds, "recorded_at": run.collected_at.date(),
                "value_eur": 50000, "is_start_value": True, "package": run,
                "notes": "N10 game start value; not a researched TM value.",
                "update_current": False})
        current = 50000
    player.market_value = Decimal(current)
    player.salary_per_match = Decimal(current) / 1_000_000 * 5000
    player.save(update_fields=["market_value", "salary_per_match"])
    for fact in data["transfers"]:
        origin, destination = fact.get("from"), fact.get("to")
        reference_issue(run, origin)
        reference_issue(run, destination)
        m.PlayerTransferHistory.objects.get_or_create(
            player=player, origin="real", source_row_key=digest(fact), defaults={
                "transfer_date": fact["date"], "season": fact.get("season") or "",
                "from_club": resolve_club(origin), "to_club": resolve_club(destination),
                "from_tm_id": (origin or {}).get("tm_id"),
                "to_tm_id": (destination or {}).get("tm_id"),
                "from_original_name": (origin or {}).get("name"),
                "to_original_name": (destination or {}).get("name"),
                "is_loan": fact.get("is_loan", False), "fee_eur": fact.get("fee_eur"),
                "fee_text": fact.get("fee_text"), "package": run})


def initialize_player(player, data, club, run):
    squad = data["squad"]
    owner_ref, loan_ref = squad.get("owner_club"), squad.get("loan_club")
    player.owner_club = resolve_club(owner_ref)
    player.loan_club = resolve_club(loan_ref)
    for key, ref in (("owner", owner_ref), ("loan", loan_ref)):
        setattr(player, key + "_club_tm_id", (ref or {}).get("tm_id"))
        setattr(player, key + "_club_original_name", (ref or {}).get("name"))
    player.club = player.loan_club if squad["status"] != "own" else player.owner_club
    player.loan_until = squad.get("loan_until") or None
    player.loan_status = ("none" if squad["status"] == "own" else
                          "loaned_in" if player.loan_club_id else "loaned_out")
    player.loan_partner_club = player.owner_club if player.loan_status == "loaned_in" else player.loan_club
    player.squad_team = squad["team"]
    player.shirt_number = squad.get("shirt_number")
    player.review_pool = False
    locks = [g for g in run.package_data["gaps"]
             if g["severity"] == "player_lock" and g["ref"] == f"tm:{player.transfermarkt_id}"]
    player.import_lock = bool(locks)
    player.import_lock_reasons = [g["note"] for g in locks]
    player.selection_evidence = squad
    player.pool_status = ("scoutable" if player.club_id and
                          player.club.import_state == "nicht_spielbar" and not locks else
                          "unavailable" if player.club_id is None or locks else "none")
    for kind, prefix in (("main", "main_position"), ("secondary", "secondary_position")):
        for i in range(1, 4):
            setattr(player, f"{prefix}_{i}", (data["positions"][kind] + [""] * 3)[i - 1])
    player.position = player.primary_position = player.main_position_1
    player.source_positions = ",".join(data["positions"]["main"] + data["positions"]["secondary"])
    player._suppress_club_history = True
    player.save()
    m.ImportIssue.objects.filter(entity="player", entity_ref=f"tm:{player.transfermarkt_id}",
        field="review_pool", resolution_status="open").update(
            resolution_status="resolved", resolved_at=timezone.now(), resolved_by=run.created_by)
    real_histories(player, data, run)
    return project_ratings(player, data, run)


def link_references(club):
    tm = club.transfermarkt_id
    m.PlayerMarketValueSnapshot.objects.filter(club_tm_id=tm, club__isnull=True).update(club=club)
    m.PlayerTransferHistory.objects.filter(from_tm_id=tm, from_club__isnull=True).update(from_club=club)
    m.PlayerTransferHistory.objects.filter(to_tm_id=tm, to_club__isnull=True).update(to_club=club)
    m.ClubRecord.objects.filter(opponent_tm_id=tm, opponent_club__isnull=True).update(opponent_club=club)
    m.Player.objects.filter(owner_club_tm_id=tm, owner_club__isnull=True).update(owner_club=club)
    m.Player.objects.filter(loan_club_tm_id=tm, loan_club__isnull=True).update(loan_club=club)
    m.Player.objects.filter(owner_club_tm_id=tm, loan_status="loaned_in").update(loan_partner_club=club)
    for player in m.Player.objects.filter(loan_club_tm_id=tm, club__isnull=True, review_pool=False):
        player.club = club
        player.loan_status = "loaned_in"
        player.loan_partner_club = player.owner_club
        player.pool_status = ("unavailable" if player.import_lock else
                              "scoutable" if club.import_state == "nicht_spielbar" else "none")
        player._suppress_club_history = True
        player.save(update_fields=["club", "loan_status", "loan_partner_club", "pool_status"])


def persons_and_facts(data, club, run, after_start):
    persons = {}
    for person in data["persons"]:
        kind = person.get("tm_type", "spieler")
        ids = {"tm": {"value": person.get("tm_id"), "status": "gefunden" if person.get("tm_id") else "nicht_gefunden"},
               "fmi": {"value": person.get("fmi_id"), "status": "gefunden" if person.get("fmi_id") else "nicht_gefunden"}}
        active = m.Player.objects.filter(transfermarkt_id=person.get("tm_id")).first() if kind == "spieler" and person.get("tm_id") else None
        row = (m.HistoricCoach.objects.filter(linked_player=active).first() if active
               else identity(ids, m.HistoricCoach, kind))
        row = row or m.HistoricCoach(person_kind=kind, linked_player=active)
        patch(row, {"name": person["name"], "nationality": person.get("nationality") or "",
                    "birth_date": person.get("date_of_birth") or None}, after_start)
        if not active:
            sync_ids(row, ids, run, kind)
        persons[person["ref"]] = row
    for fact in data["records"]:
        holder = persons.get((fact.get("holder") or {}).get("person_ref"))
        ref = fact.get("opponent")
        reference_issue(run, ref)
        m.ClubRecord.objects.update_or_create(club=club, record_key=fact["key"], source="SEED",
            defaults={"value_numeric": fact.get("value_numeric"),
                "value_display": fact.get("value_display") or "", "holder_coach": holder,
                "holder_player": holder.linked_player if holder else None,
                "holder_name": holder.name if holder else "",
                "basis": fact.get("basis"), "evidence_status": fact.get("status"),
                "opponent_tm_id": (ref or {}).get("tm_id"), "opponent_club": resolve_club(ref),
                "opponent_name": (ref or {}).get("name") or "",
                "record_date": fact.get("date"), "period_from": fact.get("period_from"),
                "period_to": fact.get("period_to"), "season": fact.get("season") or "",
                "competition": fact.get("competition") or "",
                "context_line": (fact.get("context") or "")[:200],
                "evidence": fact.get("sources") or [], "searched": fact.get("searched") or [],
                "package": run})
    for fact in data["titles"]:
        if fact.get("origin") != "real" or int(fact["season"][:4]) > int(run.titles_through_season[:4]):
            continue
        competition = fact["competition"]
        m.ClubTrophyEntry.objects.get_or_create(club=club, origin="real", source_row_key=digest(fact),
            defaults={"competition_name": competition["name"], "season": fact["season"],
                "competition_fm_id": competition.get("fm_id"), "category": competition["category"],
                "source_url": fact.get("source_url"), "package": run})
    for group in m.ClubTrophyEntry.objects.filter(club=club, origin="real").values(
            "competition_name", "category", "competition_fm_id").annotate(total=Count("id")):
        m.ClubTrophy.objects.update_or_create(club=club, origin="real",
            competition_name=group["competition_name"], defaults={
                "count": group["total"], "category": group["category"],
                "competition_fm_id": group["competition_fm_id"]})


def apply_package(path_or_bytes, target_league, *, user=None):
    if not package_mode():
        raise PackageError("Package import is disabled in legacy mode.")
    manifest, data = read_package(path_or_bytes)
    with transaction.atomic():
        league = m.League.objects.select_for_update().get(pk=target_league.pk)
        existing = m.SourceImportRun.objects.filter(
            club__transfermarkt_id=manifest["club"]["tm_id"], target_league=league,
            status="applied").order_by("-applied_at", "-pk").first()
        if existing and existing.data_sha256 == manifest["data_sha256"]:
            return {"run": existing.pk, "club": existing.club_id, "unchanged": True}
        after_start = league_started(league)
        club = identity(data["club"]["ids"], m.Club)
        if club is None:
            if after_start:
                raise PackageError("New club initialization is not allowed after league start.")
            club = m.Club(league=league, budget=0)
        values = {k: data["club"].get(k) for k in (
            "name", "short_name", "official_name", "founded_year", "nickname", "motto")}
        values.update({"color_" + key: value for key, value in data["club"]["colors"].items()})
        if not after_start:
            values["import_state"] = "spielbar" if league.is_playable else "nicht_spielbar"
        patch(club, values, after_start)
        run = m.SourceImportRun.objects.create(source="club_package", club=club, target_league=league,
            manifest=manifest, package_data=data, data_sha256=manifest["data_sha256"],
            format=manifest["format"], format_version=manifest["format_version"], package_type="club",
            collected_at=timezone.make_aware(datetime.combine(date.fromisoformat(manifest["collected_at"]), time())),
            titles_through_season=manifest["titles_through_season"],
            source_versions=manifest["source_versions"], position_window=manifest["position_window"],
            status="validated", created_by=user, total_rows=len(data["players"]))
        sync_ids(club, data["club"]["ids"], run)
        if after_start and (not m.ClubPublicProfile.objects.filter(club=club).exists()
                            or not m.Stadium.objects.filter(club=club).exists()):
            raise PackageError("Existing club anchors are incomplete after league start.")
        profile, _ = m.ClubPublicProfile.objects.get_or_create(club=club)
        patch(profile, {"city_name": data["club"].get("city") or "",
            "city_country": data["club"].get("country") or "",
            "map_lat": data["club"].get("lat"), "map_lng": data["club"].get("lng")}, after_start)
        stadium, _ = m.Stadium.objects.get_or_create(club=club)
        sv = data["stadium"]
        stadium_values = {"name": sv["name"], "city": sv["city"], "home_end": sv["home_end"],
                          "main_stand": sv["main_stand"], "source_tier": sv["tier"],
                          "map_lat": sv.get("lat"), "map_lng": sv.get("lng"),
                          "real_capacity_national": sv.get("capacity_national")}
        for side, label in SIDES.items():
            for kind in ("standing", "seating", "vip"):
                point = sv["stands"][side][kind]
                stadium_values["real_" + label + "_" + kind] = point["value"]
                stadium_values["real_" + label + "_" + kind + "_basis"] = point["basis"]
                if not stadium.pk or not m.StadiumExpansion.objects.filter(stadium=stadium).exists():
                    stadium_values[label + "_" + kind] = point["value"]
        for name, point in sv["totals"].items():
            stadium_values["real_total_" + name] = point["value"]
            stadium_values["real_total_" + name + "_basis"] = point["basis"]
        patch(stadium, stadium_values, after_start)
        for gap in data["gaps"]:
            issue(run, gap["entity"], gap["ref"], gap["field"], gap["note"], gap["severity"])
        included = set()
        for pdata in data["players"]:
            player = identity(pdata["ids"], m.Player)
            if player is None and after_start:
                issue(run, "player", f"tm:{pdata['ids']['tm']['value']}", "identity",
                      "New player ignored after league start.")
                continue
            if player is None:
                player = m.Player(age=0, potential=None)
            dob = date.fromisoformat(pdata["date_of_birth"])
            today = date.fromisoformat(manifest["collected_at"])
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            patch(player, {"first_name": pdata["first_name"], "last_name": pdata["last_name"],
                "display_name": pdata.get("display_name"), "date_of_birth": dob,
                "nationalities": ", ".join(pdata.get("nationalities") or []),
                "height_cm": pdata.get("height_cm"), "strong_foot": pdata.get("foot") or "",
                "age": age}, after_start)
            sync_ids(player, pdata["ids"], run)
            included.add(player.pk)
            if not after_start:
                initialize_player(player, pdata, club, run)
        if not after_start:
            missing = m.Player.objects.filter(Q(club=club) | Q(owner_club=club)).exclude(pk__in=included)
            for player in missing:
                player.club = None
                player.review_pool = True
                player.pool_status = "unavailable"
                player._suppress_club_history = True
                player.save(update_fields=["club", "review_pool", "pool_status"])
                issue(run, "player", f"tm:{player.transfermarkt_id}", "review_pool",
                      "Missing from pre-start reupload; retained in review pool.")
        persons_and_facts(data, club, run, after_start)
        link_references(club)
        run.status = "applied"
        run.applied_at = timezone.now()
        run.save(update_fields=["status", "applied_at"])
        return {"run": run.pk, "club": club.pk, "unchanged": False}
