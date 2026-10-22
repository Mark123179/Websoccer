"""Creator ID additions without moving historical identity evidence."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from game import models as m
from .package_validation import PackageError
from .package_service import source


@transaction.atomic
def supplement_player_id(player, code, value, mirror):
    # Serialize manual additions for a source, including previously absent rows.
    ds = source(code)
    m.DataSource.objects.select_for_update().get(pk=ds.pk)
    player = m.Player.objects.select_for_update().get(pk=player.pk)
    people = list(m.HistoricCoach.objects.select_for_update().filter(
        linked_player=player).order_by("pk"))
    if len(people) > 1 or any(p.person_kind != "spieler" for p in people):
        raise PackageError("Rekordperson ist nicht eindeutig als Spieler verknüpft.")
    rows = list(m.PlayerExternalId.objects.select_for_update().filter(
        Q(player=player) | Q(person_id__in=[p.pk for p in people]),
        source=ds).order_by("pk"))
    if any(r.identity_kind != "spieler" for r in rows):
        raise PackageError("Quell-ID hat eine widersprüchliche Identitätsart.")

    incoming = str(value)
    known = {r.external_id for r in rows if r.external_id is not None}
    has_mirror = any(f.name == mirror for f in player._meta.fields)
    if has_mirror and getattr(player, mirror) is not None:
        known.add(str(getattr(player, mirror)))
    if code == "FM":
        known.update(str(p.fm_inside_id) for p in people if p.fm_inside_id is not None)
    if known - {incoming}:
        raise PackageError(
            f"Widersprüchliche {code}-ID: vorhandene Quell-ID darf nicht ersetzt werden.")
    if m.PlayerExternalId.objects.filter(
            source=ds, identity_kind="spieler", external_id=incoming
    ).exclude(pk__in=[r.pk for r in rows]).exists():
        raise PackageError("ID gehört bereits einer anderen Identität.")
    if has_mirror and m.Player.objects.filter(
            **{mirror: value}).exclude(pk=player.pk).exists():
        raise PackageError("Spiegel-ID gehört bereits einem anderen Spieler.")
    if code == "FM" and m.HistoricCoach.objects.filter(
            fm_inside_id=incoming).exclude(pk__in=[p.pk for p in people]).exists():
        raise PackageError("FM-ID gehört bereits einer anderen Rekordperson.")

    # Prefer existing evidence, then the historical placeholder. Never duplicate
    # a historical ID on the active player or change its XOR owner.
    canonical = next(iter(sorted(rows, key=lambda r: (
        r.external_id is None, r.person_id is None, r.pk))), None)
    if canonical is None:
        m.PlayerExternalId.objects.create(
            player=player, source=ds, identity_kind="spieler",
            external_id=incoming, status="von_hand", checked_at=timezone.now().date())
    elif canonical.external_id is None:
        canonical.external_id = incoming
        canonical.status = "von_hand"
        canonical.checked_at = timezone.now().date()
        canonical.save(update_fields=["external_id", "status", "checked_at", "updated_at"])
    if has_mirror and getattr(player, mirror) != value:
        setattr(player, mirror, value)
        player.save(update_fields=[mirror])
