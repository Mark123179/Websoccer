"""Local comparison of saved identity audits; intentionally no Django imports."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path


class AuditFormatError(ValueError):
    """The saved report cannot safely be compared."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sorted(values):
    return sorted(values, key=_json)


def _normalize(value):
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return _sorted([_normalize(item) for item in value])
    return value


def _owner(kind, pk):
    return (kind, pk)


def _owners(finding):
    owners = {_owner("player", p["id"]) for p in finding["players"]}
    owners.update(_owner("person", p["id"]) for p in finding["people"])
    owners.update(_owner(e["owner_type"], e["owner_id"]) for e in finding["evidence"])
    for row in finding["canonical_rows"]:
        if row["player_id"] is not None:
            owners.add(_owner("player", row["player_id"]))
        elif row["person_id"] is not None:
            owners.add(_owner("person", row["person_id"]))
        else:
            owners.add(_owner("external_row", row["id"]))
    return owners


def _evidence(finding):
    # URLs, row PKs, statuses and display names are not identity keys.
    return {
        (e["owner_type"], e["owner_id"], e["provider"], e["value"], e["origin"])
        for e in finding["evidence"]
    }


def _source_ids(finding):
    return {(e["provider"], e["value"]) for e in finding["evidence"]}


def _links(finding):
    return {(p["id"], p["linked_player_id"]) for p in finding["people"]
            if p["linked_player_id"] is not None}


def _key(prefix, value):
    return prefix + sha256(_json(value).encode("utf-8")).hexdigest()


def _require(condition, label, detail):
    if not condition:
        raise AuditFormatError(f"{label}: ungültiger Prüfbericht ({detail}).")


def validate_report(report, label="Prüfbericht"):
    """Reject incompatible versions and incomplete evidence, not just bad JSON."""
    _require(isinstance(report, dict), label, "JSON-Objekt erwartet")
    version = report.get("schema_version")
    if type(version) is not int or version != 1:
        raise AuditFormatError(
            f"{label}: nicht unterstützte schema_version {version!r}; erwartet wird 1. "
            "Bitte zwei JSON-Ausgaben von audit_player_identities im Schema 1 verwenden."
        )
    _require(report.get("read_only") is True, label, "read_only muss true sein")
    _require(isinstance(report.get("findings"), list), label, "findings muss eine Liste sein")
    try:
        for finding in report["findings"]:
            for field in ("players", "people", "problems", "evidence",
                          "canonical_rows", "record_references"):
                _require(isinstance(finding[field], list), label, f"{field} muss eine Liste sein")
            for kind in ("players", "people"):
                for owner in finding[kind]:
                    _require(type(owner["id"]) is int, label, "Eigentümer-ID muss ganzzahlig sein")
            for person in finding["people"]:
                _require(person["linked_player_id"] is None
                         or type(person["linked_player_id"]) is int,
                         label, "ungültige linked_player_id")
            for e in finding["evidence"]:
                _require(e["owner_type"] in ("player", "person")
                         and type(e["owner_id"]) is int, label, "ungültiger Beleg-Eigentümer")
                for field in ("provider", "value", "origin"):
                    _require(isinstance(e[field], str) and bool(e[field]),
                             label, f"Beleg ohne {field}")
            for row in finding["canonical_rows"]:
                _require(type(row["id"]) is int, label, "ungültige kanonische Zeilen-ID")
                for field in ("player_id", "person_id"):
                    _require(row[field] is None or type(row[field]) is int,
                             label, f"ungültige {field}")
                # The audit can expose an orphan with neither owner; preserve it.
                for field in ("source__code", "external_id", "identity_kind"):
                    _require(row[field] is None or isinstance(row[field], str),
                             label, f"ungültige {field}")
            for problem in finding["problems"]:
                _require(isinstance(problem["code"], str) and bool(problem["code"]),
                         label, "Problem ohne code")
                for field in ("player_id", "person_id", "external_row_id"):
                    if field in problem:
                        _require(type(problem[field]) is int, label, f"ungültige {field}")
                if "external_row_id" in problem:
                    _require(any(r["id"] == problem["external_row_id"]
                                 for r in finding["canonical_rows"]),
                             label, "Problem verweist auf fehlende kanonische Zeile")
                if problem["code"] == "conflicting_ids":
                    _require(isinstance(problem["provider"], str), label, "fehlende Konfliktquelle")
                if problem["code"] in ("conflicting_ids", "conflicting_birth_dates"):
                    _require(isinstance(problem["values"], list)
                             and len(problem["values"]) > 1
                             and all(isinstance(v, str) for v in problem["values"]),
                             label, "Konflikt braucht bekannte values")
                if problem["code"] == "conflicting_birth_dates":
                    for owner in finding["players"]:
                        _require("date_of_birth" in owner, label, "fehlendes date_of_birth")
                    for owner in finding["people"]:
                        _require("birth_date" in owner, label, "fehlendes birth_date")
            _require(bool(_owners(finding)), label, "Komponente ohne Eigentümerbelege")
    except (KeyError, TypeError, AttributeError) as exc:
        raise AuditFormatError(
            f"{label}: unvollständiger oder ungültiger Schema-1-Prüfbericht ({exc})."
        ) from exc


def load_report(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            report = json.load(stream)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuditFormatError(f"{path}: JSON-Prüfbericht konnte nicht gelesen werden: {exc}") from exc
    validate_report(report, str(path))
    return report


def _components(report):
    components = {}
    for finding in report["findings"]:
        identity = {
            "owners": _sorted(_owners(finding)),
            "evidence": _sorted(_evidence(finding)),
            "links": _sorted(_links(finding)),
        }
        component_id = _key("component:", identity)
        if component_id in components:
            raise AuditFormatError("Prüfbericht enthält dieselbe Komponente mehrfach.")
        components[component_id] = dict(
            id=component_id, **identity, source_ids=_sorted(_source_ids(finding)),
            finding=_normalize(finding),
        )
    return components


def _problem_identity(problem, finding):
    """Use the narrowest evidence supporting a problem, not its component index."""
    details = {k: _normalize(v) for k, v in problem.items() if k != "message"}
    code = problem["code"]
    if "player_id" in problem:
        support = [("player", problem["player_id"])]
    elif "person_id" in problem:
        support = [("person", problem["person_id"])]
    elif "external_row_id" in problem:
        row = next((r for r in finding["canonical_rows"]
                    if r["id"] == problem["external_row_id"]), None)
        details.pop("external_row_id")
        support = [{k: row.get(k) for k in (
            "player_id", "person_id", "source__code", "external_id", "identity_kind")}]
        if row["player_id"] is None and row["person_id"] is None:
            support[0]["external_row_id"] = row["id"]
    elif code == "conflicting_ids":
        support = _sorted(e for e in _evidence(finding)
                          if e[2] == problem["provider"] and e[3] in problem["values"])
    elif code == "conflicting_birth_dates":
        support = _sorted(
            [("player", p["id"], p["date_of_birth"]) for p in finding["players"]
             if p.get("date_of_birth") in problem["values"]]
            + [("person", p["id"], p["birth_date"]) for p in finding["people"]
               if p.get("birth_date") in problem["values"]])
    elif code == "split_identity":
        support = _sorted(("player", p["id"]) for p in finding["players"])
    elif code == "multiple_people":
        support = _sorted(_owners(finding))
    else:
        # Unknown future codes in schema 1 are compared conservatively.
        support = _sorted(_owners(finding))
    return dict(problem=details, support=support)


def _problems(components):
    problems = {}
    for component_id, component in components.items():
        finding = component["finding"]
        for problem in finding["problems"]:
            identity = _problem_identity(problem, finding)
            problem_id = _key("problem:", identity)
            entry = problems.setdefault(problem_id, dict(
                id=problem_id, **identity, components=[]))
            entry["components"].append(component_id)
    for entry in problems.values():
        entry["components"] = sorted(set(entry["components"]))
    return problems


def _assignment_changes(before, after):
    """Bipartite overlap groups make merges, splits and many-to-many moves explicit."""
    old_index, new_index = defaultdict(set), defaultdict(set)
    for side, components in ((old_index, before), (new_index, after)):
        for cid, component in components.items():
            for owner in component["owners"]:
                side[("owner", *owner)].add(cid)
            for source_id in component["source_ids"]:
                side[("source_id", *source_id)].add(cid)
    adjacency, node_evidence = defaultdict(set), defaultdict(set)
    for token in old_index.keys() & new_index.keys():
        for old in old_index[token]:
            for new in new_index[token]:
                adjacency[("before", old)].add(("after", new))
                adjacency[("after", new)].add(("before", old))
                node_evidence[("before", old)].add(token)
                node_evidence[("after", new)].add(token)
    seen, changes = set(), []
    for start in sorted(adjacency):
        if start in seen:
            continue
        pending, group = [start], set()
        while pending:
            node = pending.pop()
            if node in group:
                continue
            group.add(node)
            pending.extend(adjacency[node] - group)
        seen.update(group)
        old = sorted(cid for side, cid in group if side == "before")
        new = sorted(cid for side, cid in group if side == "after")
        if old == new:
            continue
        kind = ("merged" if len(old) > 1 and len(new) == 1 else
                "split" if len(old) == 1 and len(new) > 1 else
                "reconfigured" if len(old) > 1 or len(new) > 1 else "changed")
        shared = set().union(*(node_evidence[node] for node in group))
        changes.append(dict(kind=kind, before_components=old, after_components=new,
                            shared_evidence=_sorted(shared)))
    return _sorted(changes)


def compare_reports(before, after):
    validate_report(before, "Vorher")
    validate_report(after, "Nachher")
    old_components, new_components = _components(before), _components(after)
    old, new = _problems(old_components), _problems(new_components)
    findings = {}
    for status, keys in (("added", new.keys() - old.keys()),
                         ("unchanged", new.keys() & old.keys()),
                         ("removed", old.keys() - new.keys())):
        findings[status] = [
            dict(id=key, problem=(new.get(key) or old[key])["problem"],
                 support=(new.get(key) or old[key])["support"],
                 before_components=old[key]["components"] if key in old else [],
                 after_components=new[key]["components"] if key in new else [])
            for key in sorted(keys)
        ]
    changes = _assignment_changes(old_components, new_components)
    return dict(
        schema_version=1, input_schema_version=1, read_only=True,
        policy="Nur Dateivergleich; keine Datenänderung. Wegfall ist kein Reparaturnachweis.",
        summary=dict(**{k: len(v) for k, v in findings.items()},
                     assignment_changes=len(changes)),
        findings=findings, assignment_changes=changes,
        components=dict(before=[old_components[k] for k in sorted(old_components)],
                        after=[new_components[k] for k in sorted(new_components)]),
    )


def render_text(report):
    labels = {"added": "Neu hinzugekommen", "unchanged": "Unverändert",
              "removed": "Nicht mehr vorhanden"}
    kinds = {"merged": "Verbunden", "split": "Getrennt",
             "reconfigured": "Neu zugeordnet", "changed": "Zuordnung geändert"}
    lines = ["Spieleridentitäten – lokaler Prüfstandsvergleich", report["policy"]]
    for status, label in labels.items():
        lines.append(f"\n{label}: {report['summary'][status]}")
        for entry in report["findings"][status]:
            lines.append(json.dumps(entry, ensure_ascii=False, indent=2))
    lines.append(f"\nZuordnungsänderungen: {report['summary']['assignment_changes']}")
    for change in report["assignment_changes"]:
        lines.append(f"{kinds[change['kind']]}: {_json(change)}")
    # Include the component evidence so text is as traceable as JSON.
    lines.append("\nKomponentenbelege (Vorher/Nachher):")
    lines.append(json.dumps(report["components"], ensure_ascii=False, indent=2))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zwei gespeicherte Spieleridentitätsprüfungen vergleichen.")
    parser.add_argument("before", help="Älterer JSON-Prüfbericht")
    parser.add_argument("after", help="Neuerer JSON-Prüfbericht")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        report = compare_reports(load_report(args.before), load_report(args.after))
    except AuditFormatError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json"
          else render_text(report))


if __name__ == "__main__":
    main()
