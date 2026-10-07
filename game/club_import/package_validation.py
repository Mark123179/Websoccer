"""Pure ZIP/JSON validation. No network, ORM writes, name matching or UI."""
import hashlib
import json
import zipfile
from datetime import date
from io import BytesIO


class PackageError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_package(path_or_bytes):
    try:
        with zipfile.ZipFile(BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes)
                             else path_or_bytes) as archive:
            if sorted(archive.namelist()) != ["data.json", "manifest.json"]:
                raise PackageError("Exactly manifest.json and data.json are required.")
            if any(i.file_size > 8_000_000 for i in archive.infolist()):
                raise PackageError("Package exceeds the size limit.")
            raw = archive.read("data.json")
            manifest = json.loads(archive.read("manifest.json"))
            data = json.loads(raw)
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as error:
        raise PackageError("Invalid package archive/JSON.") from error
    validate_package(manifest, data, hashlib.sha256(raw).hexdigest())
    return manifest, data


def validate_package(manifest, data, raw_checksum):
    from game.models import Player
    if (manifest.get("format"), manifest.get("format_version"),
            manifest.get("package_type")) != ("WS_CLUB_PACKAGE", 1, "club"):
        raise PackageError("Unsupported format/version/type.")
    if manifest.get("data_sha256") != raw_checksum:
        raise PackageError("data.json checksum mismatch.")
    try:
        date.fromisoformat(manifest["collected_at"])
        for field in ("club", "stadium", "players", "persons", "records", "titles", "gaps"):
            if field not in data:
                raise PackageError("Required section missing: " + field)
        for title in data["titles"]:
            if title["competition"]["category"] not in (
                    "championship", "national_cup", "super_cup", "international_cup", "lower_tier"):
                raise PackageError("Unknown title category.")
        for field in ("name", "short_name", "founded_year", "ids", "colors"):
            if data["club"].get(field) is None:
                raise PackageError("Required club field missing: " + field)
        if data["club"]["ids"]["tm"]["value"] != manifest["club"]["tm_id"]:
            raise PackageError("Manifest/data club identity mismatch.")
        if data["club"]["ids"]["fmi"]["value"] != manifest["club"]["fmi_id"]:
            raise PackageError("Manifest/data FMI identity mismatch.")
        capacities = []
        for side in "NESW":
            for kind in ("standing", "seating", "vip"):
                point = data["stadium"]["stands"][side][kind]
                value = point["value"]
                if value is not None and (type(value) is not int or value < 0):
                    raise PackageError("Invalid capacity.")
                if point.get("basis") not in ("belegt", "berechnet", None):
                    raise PackageError("Invalid capacity basis.")
                capacities.append(value)
        total = data["stadium"].get("capacity_national")
        if all(v is not None for v in capacities) and total is not None and sum(capacities) != total:
            raise PackageError("Twelve capacity values do not match national capacity.")
        seen = set()
        locks = {g["ref"] for g in data["gaps"] if g["severity"] == "player_lock"}
        positions = {v for v, _ in Player.POSITION_CHOICES}
        for player in data["players"]:
            tm = player["ids"]["tm"]["value"]
            if type(tm) is not int or tm <= 0 or tm in seen:
                raise PackageError("Missing/duplicate player TM identity.")
            seen.add(tm)
            for field in ("first_name", "last_name", "date_of_birth", "squad", "ratings"):
                if player.get(field) is None:
                    raise PackageError("Required player field missing: " + field)
            date.fromisoformat(player["date_of_birth"])
            for provider in ("fmi", "tm", "cmtracker", "api_football"):
                entry = player["ids"][provider]
                value = entry["value"]
                if value is not None and (type(value) is not int or value <= 0):
                    raise PackageError("Invalid external identity.")
                if entry["status"] not in (
                        "gefunden", "nicht_gefunden", "nicht_vorhanden", "von_hand"):
                    raise PackageError("Unknown external identity status.")
                if value is None and entry["status"] in ("gefunden", "von_hand"):
                    raise PackageError("Found identity has no ID.")
            if player["squad"]["team"] not in ("first", "u21"):
                raise PackageError("Unknown squad.")
            if player["squad"]["status"] not in ("own", "loaned_in", "loaned_out"):
                raise PackageError("Unknown loan status.")
            squad = player["squad"]
            owner = (squad.get("owner_club") or {}).get("tm_id")
            loan = (squad.get("loan_club") or {}).get("tm_id")
            target = manifest["club"]["tm_id"]
            if owner is None or (
                squad["status"] == "own" and (owner != target or loan is not None)
                or squad["status"] == "loaned_in" and (loan != target or owner == loan)
                or squad["status"] == "loaned_out" and (owner != target or not loan or loan == owner)):
                raise PackageError("Inconsistent owner/loan identities.")
            if squad["status"] != "own":
                date.fromisoformat(squad["loan_until"])
            for kind in ("main", "secondary"):
                values = player["positions"][kind]
                if (len(values) > 3 or len(set(values)) != len(values)
                        or any(v not in positions for v in values)
                        or len(values) == 3 and values[2] not in {"ROV", "ROM", "LOV", "LOM"}):
                    raise PackageError("Invalid main/secondary positions.")
            for key in ("market_value_eur",):
                value = player.get(key)
                if value is not None and (type(value) is not int or value < 0):
                    raise PackageError("Invalid monetary value.")
            if player["ids"]["fmi"]["value"] is None and f"tm:{tm}" not in locks:
                raise PackageError("Missing FMI must have an explicit player lock.")
            if (player["squad"]["team"] == "first"
                    and player["ids"]["cmtracker"]["value"] is None
                    and player["ids"]["cmtracker"]["status"] != "nicht_vorhanden"):
                if f"tm:{tm}" not in locks:
                    raise PackageError("Missing first-team CMTracker must have a player lock.")
        for gap in data["gaps"]:
            if gap["severity"] not in ("info", "player_lock", "blocking"):
                raise PackageError("Invalid gap severity.")
        if any(g["severity"] == "blocking" for g in data["gaps"]):
            raise PackageError("Package contains blocking gaps.")
        refs = [p["ref"] for p in data["persons"]]
        if len(set(refs)) != len(refs):
            raise PackageError("Duplicate package-local person reference.")
        for record in data["records"]:
            ref = (record.get("holder") or {}).get("person_ref")
            if ref is not None and ref not in refs:
                raise PackageError("Unknown record holder reference.")
        for name in ("players", "persons", "records", "titles"):
            if manifest["counts"][name] != len(data[name]):
                raise PackageError("Manifest count mismatch: " + name)
        for severity in ("blocking", "player_lock", "info"):
            if manifest["counts"]["gaps_" + severity] != sum(
                    g["severity"] == severity for g in data["gaps"]):
                raise PackageError("Manifest severity count mismatch.")
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, PackageError):
            raise
        raise PackageError("Malformed required fields: " + str(error)) from error
