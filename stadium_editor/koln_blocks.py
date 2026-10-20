"""Reviewed Cologne plan sectors; not surveyed aisle or seating capacities."""
from collections import Counter, defaultdict
from bisect import bisect_right
from copy import deepcopy
import hashlib
import math

PLAN_PAGE = "https://fc.de/club/ueber-den-fc/spiel-und-trainingsstaette/rheinenergiestadion"
PLAN_URL = ("https://images.ctfassets.net/nurz7nsnha04/1drujCRR6glLPE8lUq5YL0/"
            "7d0692accee51fb318caa1a742be4a8d/Lageplan_Stadion_2627.png")
TOPOLOGY = "koln-official-plan-2026-27"


def source_stand(section):
    # UltraAway on back1 belongs to the north-east corner, not east midfield.
    return ("NORD" if "left1" in section or "UltraAway" in section else
            "SUED" if "right1" in section else
            "WEST" if "front" in section else "OST")


def build_official_geometry(old_geometry, seats):
    """Intersect registered plan sectors with actual Unity seat-group bounds.

    The FC plan is schematic: internal cuts are proportional plan sectors,
    NOT measured aisle boundaries. Source identities/counts are evidence only.
    """
    groups = defaultdict(list)
    for seat in seats:
        a, y, b = seat["pos"]
        groups[(source_stand(seat["section"]), "UNTER" if y < 12 else "OBER")].append(
            (b, y, -a, seat["section"]))
    if set(groups) != {(s, t) for s in ("NORD", "SUED", "OST", "WEST")
                       for t in ("UNTER", "OBER")}:
        raise ValueError("Die acht Köln-Tribünen-/Ranggruppen sind unvollständig.")
    theta = old_geometry["meta"]["axisTheta"]
    center = old_geometry["meta"].get("fieldC", [0, 0])

    def project(x, z):
        return [center[0] + z * math.cos(theta) + x * math.sin(theta),
                center[1] + z * math.sin(theta) - x * math.cos(theta)]

    result = deepcopy(old_geometry)
    blocks, evidence = [], []
    for stand, prefix in (("NORD", "N"), ("SUED", "S"), ("OST", "O"), ("WEST", "W")):
        end = stand in ("NORD", "SUED")
        count = 6 if end else 8
        for tier in ("UNTER", "OBER"):
            points = groups[stand, tier]
            tangents = [p[0 if end else 2] for p in points]
            lo, hi = min(tangents) - .25, max(tangents) + .25
            boundaries = [lo + (hi-lo)*i/count for i in range(count+1)]
            anchor = None
            if stand == "NORD":
                home_edge = max(p[0] for p in points if "UltraAway" not in p[3])
                away_edge = min(p[0] for p in points if "UltraAway" in p[3])
                if home_edge >= away_edge:
                    raise ValueError("Nord-Gästequellen haben keine eindeutige räumliche Trennung.")
                anchor = (home_edge + away_edge)/2
                # The source's separated away groups fix N6 in the lower
                # terrace and N15/N16 in the upper terrace, independently
                # of the schematic equal-width drawing in the FC plan.
                home_count = 5 if tier == "UNTER" else 4
                away_count = count - home_count
                boundaries = ([lo + (anchor-lo)*i/home_count for i in range(home_count+1)]
                              + [anchor + (hi-anchor)*i/away_count for i in range(1, away_count+1)])
            # FC plan ordering: N west->east, S east->west, O north->south,
            # W south->north. This is deliberately not Unity name ordering.
            reverse = stand in ("SUED", "OST")
            bins = defaultdict(list)
            for p in points:
                index = min(count - 1, bisect_right(boundaries, p[0 if end else 2]) - 1)
                bins[index].append(p)
            for index in range(count):
                selected = bins[index]
                if not selected:
                    raise ValueError(f"{stand}/{tier}: unbelegter Plansektor {index}.")
                number = (count - index if reverse else index + 1) + (10 if tier == "OBER" else 0)
                label = f"{prefix}{number}"
                t0, t1 = boundaries[index:index+2]
                radii = [abs(p[2 if end else 0]) for p in selected]
                r0, r1 = min(radii) - .4, max(radii) + .4
                sign = 1 if stand in ("NORD", "OST") else -1

                def point(t, r):
                    return project(t, sign*r) if end else project(sign*r, t)

                seat_type = ("STEH" if tier == "UNTER" and (
                    stand == "SUED" or label == "N6") else
                    "VIP" if label in ("W4", "W5") else "SITZ")
                block = {
                    # Disjoint from the old 0..32 IDs: old browser tabs fail closed.
                    "id": 1000 + len(blocks), "officialBlock": label,
                    "stand": stand, "tier": tier, "type": seat_type,
                    "quad": [point(t0, r1), point(t1, r1), point(t1, r0), point(t0, r0)],
                    "rows": max(1, math.ceil((r1-r0)/.8)),
                    "seats": max(1, math.ceil((t1-t0)/.5)),
                    "z0": min(p[1] for p in selected), "z1": max(p[1] for p in selected),
                    "fanZone": ("HEIM" if stand == "SUED" and tier == "UNTER" else
                                "GAST" if label in ("N6", "N15", "N16", "O11") else ""),
                    "sourceSeatCount": len(selected),
                    "sourceSections": dict(Counter(p[3] for p in selected)),
                }
                blocks.append(block)
                evidence.append({**{k: block[k] for k in (
                    "id", "officialBlock", "stand", "tier", "sourceSeatCount", "sourceSections")},
                    "modelTangentRange": [t0, t1], "modelRadialRange": [r0, r1],
                    "sourceAwayBoundary": anchor})
    result.update(blocks=blocks, homeStand="SUED", mainStand="WEST",
                  physical_grid="v2", blockTopology=TOPOLOGY,
                  officialPlan={"page": PLAN_PAGE, "image": PLAN_URL,
                                "season": "2026/27",
                                "limits": "Schematische Plansektoren auf Unity-Sitzgruppen; "
                                          "keine vermessenen Ganggrenzen oder Blockkapazitäten."})
    result["meta"].update(homeStand="SUED", mainStand="WEST")
    evidence = {"topology": TOPOLOGY, "sourceSeatPoints": len(seats),
                "plan": result["officialPlan"], "blocks": evidence}
    return result, evidence


def fingerprint(value):
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    default=str).encode()).hexdigest()
