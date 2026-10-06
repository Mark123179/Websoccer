"""Approved N28–N31 extensions of the existing game anchors.

N33: installed unconditionally in every environment. The temporary
IMPORT_PACKAGE_MODE flag controls behavior only, never model definitions.
Remove the flag and old behavior branches after the approved live takeover.
"""
from django.db import models

IDENTITY_STATUS = [(v, v) for v in (
    "gefunden", "nicht_gefunden", "nicht_vorhanden", "von_hand")]
ORIGIN = [("real", "Real"), ("sim", "Simulation")]

# N30 is a positive list, never a catch-all "all real fields".
POST_START_FIELDS = {
    "Club": frozenset(("name", "short_name", "official_name", "founded_year",
                      "color_primary", "color_secondary", "color_tertiary", "nickname", "motto")),
    "ClubPublicProfile": frozenset(("city_name", "city_country", "map_lat", "map_lng")),
    "Player": frozenset(("first_name", "last_name", "display_name", "date_of_birth",
                        "nationalities", "height_cm", "strong_foot")),
    "HistoricCoach": frozenset(("name", "nationality", "birth_date")),
    "Stadium": frozenset(("name",)),
}


def text(size=200):
    return models.CharField(max_length=size, blank=True, null=True)


def fk(target, related_name="+"):
    return models.ForeignKey(target, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name=related_name)


class ClubTrophyEntry(models.Model):
    club = models.ForeignKey("game.Club", on_delete=models.CASCADE, related_name="trophy_entries")
    competition_name = models.CharField(max_length=200)
    competition_fm_id = models.PositiveBigIntegerField(null=True, blank=True)
    season = models.CharField(max_length=20)
    category = models.CharField(max_length=50)
    origin = models.CharField(max_length=4, choices=ORIGIN)
    source_url = models.URLField(blank=True, null=True)
    package = fk("game.SourceImportRun")
    source_row_key = models.CharField(max_length=64)

    class Meta:
        app_label = "game"
        constraints = [
            models.UniqueConstraint(fields=["club", "origin", "source_row_key"],
                                    name="unique_club_title_fact"),
            models.CheckConstraint(condition=models.Q(origin__in=["real", "sim"]),
                                   name="club_title_origin_valid"),
        ]


class ImportIssue(models.Model):
    club = models.ForeignKey("game.Club", on_delete=models.CASCADE, related_name="import_issues")
    package = models.ForeignKey("game.SourceImportRun", on_delete=models.CASCADE,
                                related_name="issues")
    last_seen_package = fk("game.SourceImportRun")
    subkey = models.CharField(max_length=64, blank=True, default="")
    manual_value = models.JSONField(null=True, blank=True)
    entity = models.CharField(max_length=40)
    entity_ref = models.CharField(max_length=200, blank=True)
    field = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=[
        ("info", "Info"), ("player_lock", "Player lock"), ("blocking", "Blocking")])
    note = models.TextField(blank=True)
    external_reference = models.JSONField(default=dict, blank=True)
    proposed_tm_id = models.PositiveBigIntegerField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = fk("auth.User")
    resolution_status = models.CharField(max_length=20, default="open",
        choices=[("open", "Open"), ("resolved", "Von Hand erledigt"),
                 ("package", "Durch neues Paket erledigt")])

    class Meta:
        app_label = "game"
        constraints = [
            models.UniqueConstraint(fields=["club", "entity", "entity_ref", "field", "subkey"],
                                    name="unique_club_issue_subkey"),
            models.CheckConstraint(condition=models.Q(
                severity__in=["info", "player_lock", "blocking"]), name="import_issue_severity_valid"),
        ]


def install(namespace):
    """Add fields to the SAME classes; called once at the end of game.models."""
    def add(model, name, field):
        namespace[model].add_to_class(name, field)

    def change(model, name, **kwargs):
        field = namespace[model]._meta.get_field(name)
        for key, value in kwargs.items():
            setattr(field, key, value)

    def constrain(model, constraint):
        meta = namespace[model]._meta
        meta.constraints = [*meta.constraints, constraint]
        meta.original_attrs["constraints"] = meta.constraints

    def replace_constraints(model, constraints):
        meta = namespace[model]._meta
        meta.constraints = constraints
        meta.original_attrs["constraints"] = constraints

    for name in ("official_name", "nickname", "motto"):
        add("Club", name, text())
    add("Club", "color_tertiary", text(7))
    add("Club", "import_state", models.CharField(max_length=20, default="nicht_spielbar",
        choices=[("spielbar", "Spielbar"), ("nicht_spielbar", "Nicht spielbar")]))
    constrain("Club", models.CheckConstraint(condition=models.Q(
        import_state__in=["spielbar", "nicht_spielbar"]), name="club_import_state_valid"))
    # league remains the existing required FK. No reference-club state/row.

    for name in ("home_end", "main_stand"):
        add("Stadium", name, models.CharField(max_length=1, blank=True, null=True,
                                            choices=[(x, x) for x in "NESW"]))
    for name in ("map_lat", "map_lng"):
        add("Stadium", name, models.DecimalField(max_digits=11, decimal_places=7,
                                               blank=True, null=True))
    add("Stadium", "source_tier", models.PositiveSmallIntegerField(null=True, blank=True))
    for name in ("real_capacity_national", "real_total_standing",
                 "real_total_seating_incl_vip", "real_total_vip"):
        add("Stadium", name, models.PositiveIntegerField(null=True, blank=True))
    for name in ("standing", "seating_incl_vip", "vip"):
        add("Stadium", "real_total_" + name + "_basis",
            models.CharField(max_length=10, null=True, blank=True,
                             choices=[("belegt", "Belegt"), ("berechnet", "Berechnet")]))
    for side in ("nord", "ost", "sued", "west"):
        for kind in ("standing", "seating", "vip"):
            base = side + "_" + kind
            add("Stadium", "real_" + base, models.PositiveIntegerField(null=True, blank=True))
            add("Stadium", "real_" + base + "_basis", models.CharField(
                max_length=10, null=True, blank=True,
                choices=[("belegt", "Belegt"), ("berechnet", "Berechnet")]))
            # Keep legacy constructor defaults. Package initialization explicitly
            # writes None for unknown capacity; model state must never depend on mode.
            change("Stadium", base, null=True, blank=True, default=0)
    old_capacities = {
        kind: getattr(namespace["Stadium"], "capacity_" + kind)
        for kind in ("total", "standing", "seating", "vip")
    }
    def capacity(stadium, kinds):
        values = [getattr(stadium, side + "_" + kind)
                  for side in ("nord", "ost", "sued", "west") for kind in kinds]
        return None if any(value is None for value in values) else sum(values)
    def capacity_property(kind, kinds):
        def get_capacity(stadium):
            from django.conf import settings
            if not getattr(settings, "IMPORT_PACKAGE_MODE", False):
                return old_capacities[kind].fget(stadium)
            return capacity(stadium, kinds)
        return property(get_capacity)
    namespace["Stadium"].add_to_class("capacity_total", capacity_property(
        "total", ("standing", "seating", "vip")))
    for kind in ("standing", "seating", "vip"):
        namespace["Stadium"].add_to_class("capacity_" + kind,
                                        capacity_property(kind, (kind,)))

    add("Player", "display_name", text())
    add("Player", "selection_evidence", models.JSONField(default=dict, blank=True))
    add("Player", "squad_team", models.CharField(max_length=10, null=True, blank=True,
        choices=[("first", "First"), ("u21", "U21")]))
    for role in ("owner_club", "loan_club"):
        add("Player", role, fk("game.Club"))
        add("Player", role + "_tm_id", models.PositiveBigIntegerField(null=True, blank=True))
        add("Player", role + "_original_name", text())
    add("Player", "import_lock", models.BooleanField(default=False))
    add("Player", "import_lock_reasons", models.JSONField(default=list, blank=True))
    add("Player", "review_pool", models.BooleanField(default=False))
    change("Player", "potential", null=True, blank=True)
    add("League", "is_playable", models.BooleanField(default=True))
    constrain("Player", models.CheckConstraint(condition=(
        models.Q(squad_team__isnull=True) | models.Q(squad_team__in=["first", "u21"])),
        name="player_squad_team_valid"))
    # N31: no real_loan_* columns. real_life_club is retained ONLY for old readers.
    namespace["Player"].add_to_class("is_in_loan_pool", property(
        lambda p: bool(not p.review_pool and p.club_id is None and p.owner_club_tm_id and p.loan_club_tm_id
                       and p.loan_club_tm_id != p.owner_club_tm_id
                       and p.loan_club_id is None)))

    for model in ("PlayerExternalId", "ClubExternalId"):
        add(model, "status", models.CharField(max_length=20, choices=IDENTITY_STATUS,
                                            default="nicht_gefunden"))
        add(model, "checked_at", models.DateField(null=True, blank=True))
        change(model, "external_id", null=True, blank=True)
        constrain(model, models.CheckConstraint(condition=models.Q(
            status__in=[x[0] for x in IDENTITY_STATUS]), name=model.lower() + "_status_valid"))
    change("PlayerExternalId", "player", null=True, blank=True)
    add("PlayerExternalId", "person", fk("game.HistoricCoach", "external_ids"))
    add("PlayerExternalId", "identity_kind", models.CharField(
        max_length=20, default="spieler", choices=[("spieler", "Spieler"), ("trainer", "Trainer")]))
    add("PlayerExternalId", "match_evidence", models.JSONField(default=dict, blank=True))
    replace_constraints("PlayerExternalId", [
        models.UniqueConstraint(fields=["source", "identity_kind", "external_id"],
            condition=models.Q(external_id__isnull=False), name="unique_typed_external_person_id"),
        models.UniqueConstraint(fields=["player", "source"], name="unique_player_external_id_per_source"),
        models.UniqueConstraint(fields=["person", "source"], name="unique_person_external_id_per_source"),
        models.CheckConstraint(condition=(
            models.Q(player__isnull=False, person__isnull=True)
            | models.Q(player__isnull=True, person__isnull=False)), name="external_id_exactly_one_owner"),
        models.CheckConstraint(condition=models.Q(
            status__in=[x[0] for x in IDENTITY_STATUS]), name="playerexternalid_status_valid"),
    ])
    change("HistoricCoach", "fm_inside_id", null=True, blank=True)
    add("HistoricCoach", "person_kind", models.CharField(
        max_length=20, default="trainer", choices=[("spieler", "Spieler"), ("trainer", "Trainer")]))
    add("HistoricCoach", "linked_player", fk("game.Player"))
    add("PlayerSourceRatingSnapshot", "payload_hash", models.CharField(max_length=64, default=""))
    replace_constraints("PlayerSourceRatingSnapshot", [
        models.UniqueConstraint(fields=["player", "source", "recorded_at", "source_version", "payload_hash"],
                                name="unique_versioned_source_snapshot")])

    for model in ("PlayerMarketValueSnapshot", "PlayerTransferHistory"):
        add(model, "origin", models.CharField(max_length=4, choices=ORIGIN, default="sim"))
        add(model, "package", fk("game.SourceImportRun"))
        add(model, "source_row_key", models.CharField(max_length=64, blank=True, null=True))
        constrain(model, models.CheckConstraint(condition=models.Q(
            origin__in=["real", "sim"]), name=model.lower() + "_origin_valid"))
    add("PlayerMarketValueSnapshot", "club", fk("game.Club"))
    add("PlayerMarketValueSnapshot", "club_tm_id", models.PositiveBigIntegerField(null=True, blank=True))
    add("PlayerMarketValueSnapshot", "club_original_name", text())
    add("PlayerMarketValueSnapshot", "is_start_value", models.BooleanField(default=False))
    replace_constraints("PlayerMarketValueSnapshot", [
        models.UniqueConstraint(fields=["player", "origin", "source_row_key"],
            condition=models.Q(source_row_key__isnull=False), name="unique_market_value_fact"),
        models.CheckConstraint(condition=models.Q(origin__in=["real", "sim"]),
                               name="playermarketvaluesnapshot_origin_valid"),
    ])
    constrain("PlayerTransferHistory", models.UniqueConstraint(
        fields=["player", "origin", "source_row_key"],
        condition=models.Q(source_row_key__isnull=False), name="unique_transfer_fact"))
    add("PlayerTransferHistory", "is_loan", models.BooleanField(default=False))
    for direction in ("from", "to"):
        add("PlayerTransferHistory", direction + "_tm_id",
            models.PositiveBigIntegerField(null=True, blank=True))
        add("PlayerTransferHistory", direction + "_original_name", text())
    add("PlayerTransferHistory", "fee_text", text())
    change("ClubRecord", "value_numeric", null=True, blank=True)
    for name in ("basis", "evidence_status"):
        add("ClubRecord", name, text(30))
    add("ClubRecord", "opponent_tm_id", models.PositiveBigIntegerField(null=True, blank=True))
    add("ClubRecord", "evidence", models.JSONField(default=list, blank=True))
    add("ClubRecord", "searched", models.JSONField(default=list, blank=True))
    add("ClubRecord", "package", fk("game.SourceImportRun"))
    add("ClubTrophy", "origin", models.CharField(max_length=4, choices=ORIGIN, default="sim"))
    add("ClubTrophy", "category", text(50))
    add("ClubTrophy", "competition_fm_id", models.PositiveBigIntegerField(null=True, blank=True))
    constrain("ClubTrophy", models.CheckConstraint(condition=models.Q(
        origin__in=["real", "sim"]), name="club_trophy_origin_valid"))

    change("SourceImportRun", "source", choices=[
        ("cmtracker", "CMTracker"), ("club_package", "Club package")])
    for name in ("format", "package_type"):
        add("SourceImportRun", name, text(80))
    add("SourceImportRun", "format_version", models.PositiveSmallIntegerField(null=True, blank=True))
    add("SourceImportRun", "data_sha256", text(64))
    add("SourceImportRun", "collected_at", models.DateTimeField(null=True, blank=True))
    add("SourceImportRun", "titles_through_season", text(20))
    for name in ("source_versions", "position_window", "manifest", "package_data"):
        add("SourceImportRun", name, models.JSONField(default=dict, blank=True))
    add("SourceImportRun", "club", fk("game.Club"))
    add("SourceImportRun", "target_league", fk("game.League"))
    add("SourceImportRun", "status", models.CharField(max_length=20, default="draft",
        choices=[("draft", "Draft"), ("validated", "Validated"), ("applied", "Applied"),
                 ("failed", "Failed")]))
    add("SourceImportRun", "applied_at", models.DateTimeField(null=True, blank=True))
    namespace.update(ClubTrophyEntry=ClubTrophyEntry, ImportIssue=ImportIssue)
    # Proxy metadata may have cached inherited fields before the shared base
    # extensions were installed. Invalidate it too, not just the base model.
    from django.apps import apps
    for registry in apps.all_models.values():
        for model in registry.values():
            model._meta._expire_cache()
