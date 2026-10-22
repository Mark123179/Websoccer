"""Read-only historical identity decisions, shared by preview and application.

Canonical IDs remain owned by the historical person (XOR constraint). The
linked_player pointer projects that same identity into the active squad.
"""
from django.db.models import Q

from game import models as m
from .package_validation import PackageError


PROVIDERS = {"tm": ("TM", "transfermarkt_id"), "fmi": ("FM", "fm_inside_id"),
             "cmtracker": ("CMTRACKER", None),
             "api_football": ("API_FOOTBALL", "api_football_id")}


def historical_plan(data, *, lock=False):
    decisions = []
    for player in data["players"]:
        ids = player["ids"]
        label = f"{player['display_name']} (TM {ids['tm']['value']})"

        def stop(reason):
            raise PackageError(f"Historische Identität {label}: {reason} Kein Import.")

        matches = Q(pk__in=[])
        active_ids = set()
        for provider, (code, mirror) in PROVIDERS.items():
            value = (ids.get(provider) or {}).get("value")
            if value is None:
                continue
            matches |= Q(source__code=code, external_id=str(value))
            if mirror:
                active_ids.update(m.Player.objects.filter(
                    **{mirror: value}).values_list("pk", flat=True))
        matched = m.PlayerExternalId.objects.filter(matches, identity_kind="spieler")
        active_ids.update(matched.exclude(player=None).values_list("player_id", flat=True))
        person_ids = set(matched.exclude(person=None).values_list("person_id", flat=True))
        fmi = (ids.get("fmi") or {}).get("value")
        people = m.HistoricCoach.objects.filter(person_kind="spieler").filter(
            Q(pk__in=person_ids) | Q(linked_player_id__in=active_ids)
            | (Q(fm_inside_id=str(fmi)) if fmi is not None else Q(pk__in=[])))
        if lock:
            people = people.select_for_update()
        people = list(people)
        if not people and not person_ids:
            continue
        if len(people) != 1 or person_ids - {p.pk for p in people}:
            stop("Mehrere oder widersprüchlich typisierte Rekordpersonen")
        person = people[0]
        if person.linked_player_id:
            active_ids.add(person.linked_player_id)
        if len(active_ids) > 1:
            stop("Quell-IDs gehören zu unterschiedlichen aktiven Spielern")
        active = m.Player.objects.filter(pk__in=active_ids)
        if lock:
            active = active.select_for_update()
        active = active.first()
        linked = m.HistoricCoach.objects.filter(linked_player=active) if active else None
        if linked is not None and linked.exclude(pk=person.pk).exists():
            stop("Aktiver Spieler ist bereits mit einer anderen Rekordperson verknüpft")
        evidence = m.PlayerExternalId.objects.filter(
            Q(person=person) | (Q(player=active) if active else Q(pk__in=[])))
        if lock:
            evidence = evidence.select_for_update()
        evidence = list(evidence.select_related("source").order_by("pk"))
        for dob in (person.birth_date, active.date_of_birth if active else None):
            if dob and str(dob) != player["date_of_birth"]:
                stop("Bekanntes Geburtsdatum widerspricht dem Paket")
        for provider, (code, mirror) in PROVIDERS.items():
            known = {row.external_id for row in evidence
                     if row.source.code == code and row.external_id is not None}
            if provider == "fmi" and person.fm_inside_id:
                known.add(str(person.fm_inside_id))
            if active and mirror and getattr(active, mirror) is not None:
                known.add(str(getattr(active, mirror)))
            incoming = (ids.get(provider) or {}).get("value")
            if incoming is not None:
                known.add(str(incoming))
            if len(known) > 1:
                stop(f"Widersprüchliche {code}-ID")
        # IDs, not name or date of birth, are the match evidence.
        decisions.append(dict(
            name=player["display_name"], tm=ids["tm"]["value"],
            person_id=person.pk, person_name=person.name,
            player_id=active.pk if active else None,
            person_state={f.attname: getattr(person, f.attname) for f in person._meta.fields},
            player_state={f.attname: getattr(active, f.attname) for f in active._meta.fields}
                         if active else None,
            evidence=[{f.attname: getattr(row, f.attname) for f in row._meta.fields}
                      for row in evidence],
        ))
    return decisions
