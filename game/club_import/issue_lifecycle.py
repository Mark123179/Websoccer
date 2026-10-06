"""N43/N47 matching shared by preview and confirmed imports."""
from collections import Counter, defaultdict
import hashlib
from django.utils import timezone
from game import models as m


def text_key(note):
    return hashlib.sha256(note.encode()).hexdigest()


def prospective_strength(data):
    """Unsaved PSR adapter into the shared, unchanged strength service."""
    from types import SimpleNamespace
    from .package_service import attributes
    from game.strength_service import compute_strength_for_player
    main, secondary = data["positions"]["main"], data["positions"]["secondary"]
    position = main[0] if main else ""
    rows = []
    for provider, code in (("fminside", "FM"), ("cmtracker", "CMTRACKER")):
        block = data["ratings"].get(provider)
        if block and block.get("rating") is not None:
            rows.append(m.PlayerSourceRating(source=code, rating=block["rating"],
                potential=block.get("potential"), **attributes(block, provider, position == "TW")))
    player = SimpleNamespace(position=position, main_positions=main,
        secondary_positions=secondary, source_ratings=SimpleNamespace(all=lambda: rows),
        strength_profile=SimpleNamespace(freshness=None),
        form_snapshots=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(order_by=lambda *args: [])))
    return compute_strength_for_player(player)


def prospective_locks(data):
    reasons = []
    for provider in ("fmi", "tm", "cmtracker"):
        entry = data["ids"].get(provider)
        if entry is None or entry.get("status") == "nicht_gefunden":
            reasons.append(provider + ": ID nicht_gefunden")
        elif provider != "tm" and entry.get("value") is not None and entry.get("status") in ("gefunden", "von_hand"):
            block = data["ratings"].get("fminside" if provider == "fmi" else "cmtracker") or {}
            if block.get("rating") is None:
                reasons.append(provider + ": ID vorhanden, Rating fehlt")
    if not prospective_strength(data)["computable"]:
        reasons.append("Keine Stärke berechnet")
    return reasons


def conflicting_providers(ids, model):
    """Read-only conflict lookup; a known TM identity cannot be renamed via FMI."""
    tm = ids["tm"].get("value")
    target = model.objects.filter(transfermarkt_id=tm).first() if tm is not None else None
    table, owner = (m.PlayerExternalId, "player_id") if model is m.Player else (m.ClubExternalId, "club_id")
    bad = []
    for provider, code in (("fmi", "FM"), ("tm", "TM"), ("cmtracker", "CMTRACKER"), ("api_football", "API_FOOTBALL")):
        entry = ids.get(provider) or {}
        value = entry.get("value")
        if value is None:
            continue
        rows = table.objects.filter(source__code=code, external_id=str(value))
        if model is m.Player:
            rows = rows.filter(identity_kind="spieler")
        owners = set(rows.values_list(owner, flat=True))
        if provider in ("fmi", "tm"):
            mirror = "fm_inside_id" if provider == "fmi" else "transfermarkt_id"
            owners.update(model.objects.filter(**{mirror: value}).values_list("pk", flat=True))
        owners.discard(None)
        if target:
            conflict = bool(owners - {target.pk})
        else:
            conflict = model.objects.filter(pk__in=owners, transfermarkt_id__isnull=False).exclude(transfermarkt_id=tm).exists()
        if conflict:
            bad.append(provider)
    return bad


def candidates(data, club=None):
    from .package_service import league_started
    started = bool(club and league_started(club.league))
    rows = [dict(g, severity="info" if g["entity"] == "player"
                 and g["severity"] == "player_lock" else g["severity"]) for g in data["gaps"]]
    for entity, item, model in [("club", data["club"], m.Club)] + [
            ("player", player, m.Player) for player in data["players"]]:
        for provider in conflicting_providers(item["ids"], model):
            rows.append(dict(entity=entity, ref=f"tm:{item['ids']['tm']['value']}",
                field="identity." + provider, severity="blocking" if entity == "club" else "player_lock",
                note="ID already belongs to another identity.", external_reference=item["ids"][provider]))
    references = []
    for player in data["players"]:
        references += [p.get("club") for p in player["market_values"]]
        for fact in player["transfers"]:
            references += [fact.get("from"), fact.get("to")]
    references += [r.get("opponent") for r in data["records"]]
    seen = set()
    for ref in references:
        if ref and not ref.get("tm_id") and ref.get("name") and ref["name"] not in seen:
            seen.add(ref["name"])
            gap = next((g for g in rows if g["entity"] == "club" and ref["name"] in g["ref"]), None)
            if gap:
                gap["external_reference"] = ref
            else:
                rows.append({"entity": "club_reference", "ref": ref["name"], "field": "tm_id",
                    "note": "Club TM identity missing; original name retained.",
                    "severity": "info", "external_reference": ref})
    if club and m.ImportIssue.objects.filter(club=club, field="image").exists():
        from .package_preview import image_gaps
        rows.extend(image_gaps(data))
    for player in data["players"]:
        ref = f"tm:{player['ids']['tm']['value']}"
        reasons = prospective_locks(player)
        if started:
            current = m.Player.objects.filter(transfermarkt_id=player["ids"]["tm"]["value"]).first()
            reasons = lock_reasons(current) if current else []
        if reasons:
            fields = ["ids." + provider for provider in ("fmi", "tm", "cmtracker")
                      if any(reason.startswith(provider + ":") for reason in reasons)]
            fields += ["ratings.fminside.potential", "ratings.cmtracker.potential"]
            gap = next((g for field in fields for g in rows
                        if g["entity"] == "player" and g["ref"] == ref and g["field"] == field), None)
            if gap:
                gap["severity"] = "player_lock"
            else:
                rows.append(dict(entity="player", ref=ref, field="import_lock",
                                 severity="player_lock", note="; ".join(reasons)))
    if club and not started:
        included = [p["ids"]["tm"]["value"] for p in data["players"]]
        for player in m.Player.objects.filter(owner_club=club).exclude(transfermarkt_id__in=included):
            rows.append(dict(entity="player", ref=f"tm:{player.transfermarkt_id}",
                field="review_pool", severity="info",
                note="Missing from pre-start reupload; retained in review pool."))
    return rows


def plan(club, desired, field=None):
    old = list(m.ImportIssue.objects.filter(club=club).order_by("pk")) if club else []
    if field:
        old = [row for row in old if row.field == field]
    groups = defaultdict(list)
    for row in old:
        groups[(row.entity, row.entity_ref, row.field)].append(row)
    counts = Counter((r["entity"], r["ref"], r["field"]) for r in desired)
    matched = set()
    operations = []
    balance = dict(new=0, kept=0, closed=0, reopened=0)
    for item in {(r["entity"], r["ref"], r["field"], r["note"]): r for r in desired}.values():
        key = item["entity"], item["ref"], item["field"]
        multiple = counts[key] > 1
        subkey = text_key(item["note"]) if multiple else ""
        available = [r for r in groups[key] if r.pk not in matched]
        same_text = next((r for r in available if r.note == item["note"]), None)
        previous_multiple = any(r.subkey for r in available if r.resolution_status != "package")
        row = same_text if multiple or previous_multiple else next(
            (r for r in available if r.subkey == ""), same_text)
        status = "open"
        if row:
            matched.add(row.pk)
            status = "open" if row.resolution_status == "package" else row.resolution_status
            if row.severity == "player_lock" and item["severity"] != "player_lock":
                status = "resolved" if row.manual_value is not None else "package"
                balance["closed"] += int(row.resolution_status == "open")
            if status == "open":
                balance["reopened" if row.resolution_status == "package" else "kept"] += 1
        else:
            balance["new"] += 1
        operations.append((row, item, subkey, status))
    close = [r for r in old if r.pk not in matched and r.resolution_status == "open"]
    balance["closed"] += len(close)
    return operations, close, balance


def reconcile(run, desired, field=None):
    operations, close, balance = plan(run.club, desired, field=field)
    # Vacate an old simple key before promoting its same-text sibling.
    for row, item, subkey, status in operations:
        if row is None or row.subkey != subkey:
            occupied = m.ImportIssue.objects.filter(club=run.club, entity=item["entity"],
                entity_ref=item["ref"], field=item["field"], subkey=subkey)
            if row:
                occupied = occupied.exclude(pk=row.pk)
            occupied = occupied.first()
            if occupied:
                occupied.subkey = text_key(occupied.note)
                occupied.save(update_fields=["subkey"])
    for row, item, subkey, status in operations:
        row = row or m.ImportIssue(club=run.club, package=run, entity=item["entity"],
                                  entity_ref=item["ref"], field=item["field"])
        row.subkey = subkey
        row.last_seen_package = run
        row.note = item["note"]
        row.severity = item["severity"]
        reference = item.get("external_reference", row.external_reference or {})
        if row.manual_value is not None and row.field == "tm_id" and not reference.get("tm_id"):
            reference = dict(reference, tm_id=row.manual_value, status="von_hand")
        row.external_reference = reference
        if row.entity == "club_reference":
            matches = list(m.Club.objects.filter(name__iexact=row.entity_ref,
                            transfermarkt_id__isnull=False).values_list("transfermarkt_id", flat=True)[:2])
            row.proposed_tm_id = matches[0] if len(matches) == 1 else None
        row.resolution_status = status
        if status == "open":
            row.resolved_at = row.resolved_by = None
        elif status == "package" and row.resolved_at is None:
            row.resolved_at = timezone.now()
        row.save()
    for row in close:
        row.resolution_status = "package"
        row.resolved_at = timezone.now()
        row.resolved_by = None
        row.save(update_fields=["resolution_status", "resolved_at", "resolved_by"])
    return balance


def lock_reasons(player):
    ids = {r.source.code: r for r in player.external_ids.select_related("source").all()}
    ratings = {r.source: r.rating for r in player.source_ratings.all()}
    reasons = []
    for code in ("FM", "TM", "CMTRACKER"):
        row = ids.get(code)
        if row is None or row.status == "nicht_gefunden":
            reasons.append(f"{code}: ID nicht_gefunden")
        elif code in ("FM", "CMTRACKER") and row.status in ("gefunden", "von_hand"):
            if row.external_id is not None and ratings.get(code) is None:
                reasons.append(f"{code}: ID vorhanden, Rating fehlt")
    if not m.PlayerStrengthProfile.objects.filter(player=player).exists():
        reasons.append("Keine Stärke berechnet")
    return reasons


def refresh_lock(player):
    reasons = lock_reasons(player)
    player.import_lock = bool(reasons)
    player.import_lock_reasons = reasons
    if reasons:
        player.pool_status = "unavailable"
    elif player.club_id and player.club.import_state == "nicht_spielbar":
        player.pool_status = "scoutable"
    elif player.club_id:
        player.pool_status = "none"
    player.save(update_fields=["import_lock", "import_lock_reasons", "pool_status"])
    club = player.owner_club or player.club
    if reasons and club:
        entries = m.ImportIssue.objects.filter(club=club, entity="player",
            entity_ref=f"tm:{player.transfermarkt_id}", resolution_status="open")
        row = entries.filter(severity="player_lock").first()
        if not row:
            row = entries.filter(field__in=["ids.fmi", "ids.tm", "ids.cmtracker",
                    "ratings.fminside.potential", "ratings.cmtracker.potential"]).first()
        if row:
            row.severity = "player_lock"
            row.external_reference = dict(row.external_reference or {}, lock_reasons=reasons)
            row.save(update_fields=["severity", "external_reference"])
    if not reasons:
        m.ImportIssue.objects.filter(entity="player",
            entity_ref=f"tm:{player.transfermarkt_id}", club__in=[player.club, player.owner_club],
            severity="player_lock", resolution_status="open").update(
                resolution_status="package", resolved_at=timezone.now(), resolved_by=None)
    return reasons
