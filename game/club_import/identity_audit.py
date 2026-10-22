"""Read-only inventory audit. Never invoke package preview/apply (even dry-run).

Edges come exclusively from source IDs and explicit links, never from names.
An edge denotes evidence to inspect, not permission to merge its endpoints.
"""
from collections import Counter, defaultdict

from game import models as m
from .historical_identity import PROVIDERS


LABELS = {
    "split_identity": "Quellidentität ist auf mehrere aktive Spieler verteilt",
    "multiple_people": "Mehrere Rekordpersonen teilen eine aktive Identität",
    "unlinked_person": "Historische Quell-ID passt zu aktivem Spieler, aber Verknüpfung fehlt",
    "conflicting_ids": "Bekannte Quell-IDs widersprechen einander",
    "conflicting_birth_dates": "Bekannte Geburtsdaten widersprechen einander",
    "missing_canonical": "Spiegel-ID hat keinen kanonischen Beleg",
    "missing_mirror": "Kanonische ID hat keine aktive Spiegel-ID",
    "wrong_kind": "Spielerbeleg oder Verknüpfung hat widersprüchlichen Personentyp",
    "orphan_owner": "Kanonischer Beleg hat keinen vorhandenen Eigentümer",
}


def audit_player_identities():
    """Return deterministic JSON-compatible evidence using SELECTs only.

    Historical-only identities are counted, not treated as broken: retired
    record holders need not have an active Player. Missing evidence is a gap,
    not an ID contradiction. Person-owned canonical rows satisfy active IDs
    through linked_player without requiring duplicate canonical ownership.
    """
    mirrors = {code: field for code, field in PROVIDERS.values() if field}
    players = {r["id"]: r for r in m.Player.objects.order_by("pk").values(
        "id", "first_name", "last_name", "club_id", "date_of_birth", *mirrors.values())}
    people = {r["id"]: r for r in m.HistoricCoach.objects.order_by("pk").values(
        "id", "name", "person_kind", "birth_date", "fm_inside_id", "linked_player_id")}
    rows = list(m.PlayerExternalId.objects.order_by("pk").values(
        "id", "player_id", "person_id", "identity_kind", "source__code",
        "external_id", "status", "source_url", "profile_url", "match_evidence"))
    records = list(m.ClubRecord.objects.order_by("pk").values(
        "id", "club_id", "record_key", "source", "holder_player_id", "holder_coach_id"))
    records_by_owner = defaultdict(dict)
    for record in records:
        for kind, field in (("player", "holder_player_id"), ("person", "holder_coach_id")):
            if record[field] is not None:
                records_by_owner[(kind, record[field])][record["id"]] = record

    parent, evidence, canonical = {}, defaultdict(list), defaultdict(list)
    problems = defaultdict(list)

    def root(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def join(a, b):
        parent[root(a)] = root(b)

    def problem(node, code, **details):
        problems[node].append(dict(code=code, message=LABELS[code], **details))

    def add(node, provider, value, origin, **details):
        if value is None or str(value).strip() == "":
            return
        item = dict(provider=provider, value=str(value), origin=origin, **details)
        evidence[node].append(item)

    for pk, player in players.items():
        node = ("player", pk)
        root(node)
        for code, field in mirrors.items():
            add(node, code, player[field], f"Player.{field}")
    for pk, person in people.items():
        node = ("person", pk)
        if person["person_kind"] != "spieler" and not person["linked_player_id"]:
            continue
        root(node)
        if person["person_kind"] == "spieler":
            add(node, "FM", person["fm_inside_id"], "HistoricCoach.fm_inside_id")
        if person["linked_player_id"] in players:
            join(node, ("player", person["linked_player_id"]))
            if person["person_kind"] != "spieler":
                problem(node, "wrong_kind", person_kind=person["person_kind"])

    for row in rows:
        node = ("player", row["player_id"]) if row["player_id"] else ("person", row["person_id"])
        if row["identity_kind"] != "spieler":
            if row["player_id"] or (
                row["person_id"] in people and people[row["person_id"]]["person_kind"] == "spieler"
            ):
                root(node)
                canonical[node].append(row)
                problem(node, "wrong_kind", external_row_id=row["id"],
                        identity_kind=row["identity_kind"])
            continue  # TM trainer IDs have a separate namespace.
        root(node)
        if ((node[0] == "player" and node[1] not in players)
                or (node[0] == "person" and node[1] not in people)):
            problem(node, "orphan_owner", external_row_id=row["id"])
        if node[0] == "person" and node[1] in people:
            if people[node[1]]["person_kind"] != "spieler":
                problem(node, "wrong_kind", external_row_id=row["id"],
                        person_kind=people[node[1]]["person_kind"])
        canonical[node].append(row)
        add(node, row["source__code"], row["external_id"],
            "PlayerExternalId", external_row_id=row["id"],
            source_url=row["source_url"], profile_url=row["profile_url"],
            status=row["status"], match_evidence=row["match_evidence"])

    by_id = {}
    for node in sorted(evidence):
        for item in evidence[node]:
            key = (item["provider"], item["value"])
            if key in by_id:
                join(node, by_id[key])
            else:
                by_id[key] = node
    groups = defaultdict(list)
    for node in sorted(parent):
        groups[root(node)].append(node)

    findings, historical_only = [], 0
    for nodes in sorted(groups.values()):
        active = [players[pk] for kind, pk in nodes if kind == "player" and pk in players]
        historic = [people[pk] for kind, pk in nodes if kind == "person" and pk in people]
        group_problems = [p for node in nodes for p in problems[node]]
        if historic and not active:
            historical_only += 1
        if len(active) > 1:
            group_problems.append(dict(code="split_identity", message=LABELS["split_identity"]))
        if len(historic) > 1 and active:
            group_problems.append(dict(code="multiple_people", message=LABELS["multiple_people"]))
        for person in historic:
            if active and not person["linked_player_id"]:
                group_problems.append(dict(code="unlinked_person", message=LABELS["unlinked_person"],
                                           person_id=person["id"]))
        entries = [dict(owner_type=node[0], owner_id=node[1], **item)
                   for node in nodes for item in evidence[node]]
        values = defaultdict(set)
        for entry in entries:
            values[entry["provider"]].add(entry["value"])
        for code, ids in sorted(values.items()):
            if len(ids) > 1:
                group_problems.append(dict(code="conflicting_ids", message=LABELS["conflicting_ids"],
                                           provider=code, values=sorted(ids)))
        dates = {str(p["date_of_birth"]) for p in active if p["date_of_birth"]}
        dates.update(str(p["birth_date"]) for p in historic if p["birth_date"])
        if len(dates) > 1:
            group_problems.append(dict(code="conflicting_birth_dates",
                                       message=LABELS["conflicting_birth_dates"], values=sorted(dates)))

        # Coverage uses only actual linked owners, not speculative graph edges.
        for player in active:
            node = ("player", player["id"])
            owners = [node] + [("person", p["id"]) for p in historic
                              if p["linked_player_id"] == player["id"] and p["person_kind"] == "spieler"]
            for code, field in mirrors.items():
                ids = {r["external_id"] for owner in owners for r in canonical[owner]
                       if r["identity_kind"] == "spieler"
                       and r["source__code"] == code and r["external_id"]}
                value = player[field]
                if value is not None and str(value) not in ids:
                    group_problems.append(dict(code="missing_canonical", message=LABELS["missing_canonical"],
                                               player_id=player["id"], provider=code, value=str(value)))
                if value is None and ids:
                    group_problems.append(dict(code="missing_mirror", message=LABELS["missing_mirror"],
                                               player_id=player["id"], provider=code, values=sorted(ids)))
        for person in historic:
            value = person["fm_inside_id"]
            owners = [("person", person["id"])]
            if person["linked_player_id"] in players and person["person_kind"] == "spieler":
                owners.append(("player", person["linked_player_id"]))
            if person["person_kind"] == "spieler" and value and not any(
                r["source__code"] == "FM" and r["external_id"] == str(value)
                and r["identity_kind"] == "spieler"
                for owner in owners for r in canonical[owner]
            ):
                group_problems.append(dict(code="missing_canonical", message=LABELS["missing_canonical"],
                                           person_id=person["id"], provider="FM", value=str(value)))
        if not group_problems:
            continue
        references = {pk: record for node in nodes for pk, record in records_by_owner[node].items()}
        findings.append(dict(
            players=[dict(p, date_of_birth=str(p["date_of_birth"]) if p["date_of_birth"] else None)
                     for p in active],
            people=[dict(p, birth_date=str(p["birth_date"]) if p["birth_date"] else None)
                    for p in historic],
            problems=group_problems, evidence=entries,
            canonical_rows=[r for node in nodes for r in canonical[node]],
            record_references=[references[pk] for pk in sorted(references)],
        ))
    counts = Counter(p["code"] for finding in findings for p in finding["problems"])
    return dict(
        schema_version=1, read_only=True,
        policy="Keine Zusammenführung, ID-Übertragung, Löschung oder Paketimporte.",
        summary=dict(players_scanned=len(players), people_scanned=len(people),
                     external_rows_scanned=len(rows), affected_components=len(findings),
                     historical_only_components=historical_only, problems_by_code=dict(sorted(counts.items()))),
        findings=findings,
    )
