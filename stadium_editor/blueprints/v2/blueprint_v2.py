"""Blaupause V2 — Blöcke aus OSM-Tribünenpolygonen (Entscheidung 13a), Python-Referenz.

Reihenfolge je Stadion:
  1. building=grandstand / building:part innerhalb des Stadions  → ein Polygon je Tribüne (Elversberg)
  2. building=stadium als Multipolygon mit Innenring           → Ring an den Feldecken in Seiten + Ecken geschnitten (Dortmund)
  3. (Rückfall, hier nicht nötig) Außenkontur um Feld + Rand
Blöcke: parallel zur feldnahen Kante, ~22 m breit, Tiefe per Strahl bis zur Rückkante des Polygons.
Ränge: aus der Tiefe (bis 22 m ein Rang, sonst zwei, Trennung bei 46 %), Steigung 16° / 30°, 2 m Umlauf.
Raster: physisch (0,8 m je Reihe, 0,5 m je Sitz) — Design-Raster folgt der Fläche, nicht der Kapazität.
Namen: Himmelsrichtung aus der OSM-Lage; OSM-Name (Nord/Ost/Süd/West) bricht Gleichstände.
Fehlt eine Tribüne in OSM, die die DB kennt (Elversberg Nord): parametrisch ergänzen.
"""
import json, math
from pathlib import Path
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont

# Keep the reference implementation self-contained when it is imported by the
# management command (and when it is run directly from a checkout).
ROOT = Path(__file__).resolve().parent
OSM = ROOT
OUT = ROOT
PITCH_L, PITCH_W = 105.0, 68.0
BLOCK_W, ROW_M, SEAT_M = 22.0, 0.8, 0.5
RAKE = {'UNTER': math.tan(math.radians(16)), 'OBER': math.tan(math.radians(30)), 'EINRANG': math.tan(math.radians(22))}
TIER_GAP, CHAMFER, ONE_TIER_MAX = 2.0, 9.0, 22.0
# Ebene 2 — Stadion-Steckbrief: was OSM nicht weiß, einmal je Verein (Ränge, Steigung, Stehplätze, Dach)
STECKBRIEF = {
    'Signal Iduna Park': {
        'SUED': {'tiers': 1, 'rake': 30, 'standing': True},   # Südtribüne: ein durchgehender Stehrang
        '_global': {'corners': 'closed', 'roofType': 'ring', 'pylons': {'count': 8, 'color': '#f7d418', 'height': 62}},
    },
    'Olympiastadion Berlin': {
        '_global': {'corners': 'oval', 'roofType': 'ring', 'track': True, 'gap': 'Marathontor (West)', 'sunken': 12},
    },
    'Camp Nou': {
        'WEST': {'roof': True, 'span': 30},                     # Tribuna: einzige überdachte Seite; Dach bis 30° Kurvenwinkel (Luftbild)
        '_global': {'corners': 'oval', 'roofType': 'partial', 'floodlights': {'type': 'rim'}},
    },
    'URSAPHARM-Arena an der Kaiserlinde': {
        'OST':  {'standing': True},                            # C1 Stehplätze Heim
        'NORD': {'tiers': 1, 'rake': 24, 'roof': True},        # Neubau, in OSM noch nicht enthalten
        '_global': {'corners': 'open', 'roofType': 'separate', 'floodlights': {'count': 4, 'height': 30}},
    },
}
PALETTE = ['#3a4148', '#f4f6f8', '#101216', '#c8102e', '#7a0c1e', '#1554b8', '#0a2a6b', '#6fb7e8',
           '#ffd400', '#f07818', '#1d9e50', '#0c5a2e', '#9aa3ab', '#6b4a2b', '#7a3fa0', '#22e6ff']


# ── OSM → Feldsystem ───────────────────────────────────────────────────
def to_m(lat, lon, lat0, lon0):
    k = 111320.0
    return (lon - lon0) * k * math.cos(math.radians(lat0)), (lat - lat0) * k


def load(path):
    j = json.load(open(path))
    els = j['elements']
    pitches = [e for e in els if e['type'] == 'way' and e.get('tags', {}).get('leisure') == 'pitch' and e['tags'].get('sport') == 'soccer']
    stad = next(e for e in els if e.get('tags', {}).get('leisure') == 'stadium')
    ref = stad['geometry'][0]; lat0, lon0 = ref['lat'], ref['lon']
    P = lambda geom: [to_m(g['lat'], g['lon'], lat0, lon0) for g in geom]
    outline = Polygon(P(stad['geometry']))
    pitch = min(pitches, key=lambda e: Polygon(P(e['geometry'])).centroid.distance(outline.centroid))
    pp = P(pitch['geometry']); pp = pp[:-1] if pp[0] == pp[-1] else pp
    cx = sum(p[0] for p in pp) / len(pp); cy = sum(p[1] for p in pp) / len(pp)
    L, th = max(((math.hypot(b[0] - a[0], b[1] - a[1]), math.atan2(b[1] - a[1], b[0] - a[0]))
                 for a, b in zip(pp, pp[1:] + pp[:1])), key=lambda t: t[0])
    cs, sn = math.cos(-th), math.sin(-th)
    rot = lambda p: ((p[0] - cx) * cs - (p[1] - cy) * sn, (p[0] - cx) * sn + (p[1] - cy) * cs)
    north = rot((cx, cy + 1))                                       # Nordrichtung im Feldsystem
    def poly(geom): return Polygon([rot(p) for p in P(geom)])
    stands = []
    for e in els:
        t = e.get('tags', {})
        if e['type'] == 'way' and t.get('building') == 'grandstand':
            pg = poly(e['geometry'])
            if pg.centroid.distance(Point(0, 0)) < 150: stands.append((t.get('name', ''), pg))
    ring = None
    for e in els:
        if e['type'] == 'relation' and e.get('tags', {}).get('building') == 'stadium':
            outers = [poly(m['geometry']) for m in e['members'] if m.get('role') == 'outer' and 'geometry' in m]
            inners = [poly(m['geometry']) for m in e['members'] if m.get('role') == 'inner' and 'geometry' in m]
            if outers and inners: ring = (unary_union(outers), unary_union(inners))
    return {'stands': stands, 'ring': ring, 'outline': Polygon([rot(p) for p in P(stad['geometry'])]), 'north': north, 'pitchLen': L}


# ── Tribünen aus Polygonen ────────────────────────────────────────────
def compass_name(centroid, north):
    ang = math.atan2(centroid[1], centroid[0]) - math.atan2(north[1], north[0])   # Winkel gegen Nord (mathematisch, ccw)
    ang = (ang + math.pi) % (2 * math.pi) - math.pi
    # ccw von Nord: +90° = West, −90° = Ost
    names = [('NORD', 0), ('WEST', math.pi / 2), ('SUED', math.pi), ('OST', -math.pi / 2)]
    return min(names, key=lambda n: abs((ang - n[1] + math.pi) % (2 * math.pi) - math.pi))[0]


def assign_names(stands, north):
    """stands: list of dict(poly, osm_name). Kompass, OSM-Name bricht Gleichstände."""
    hint = {'nord': 'NORD', 'ost': 'OST', 'süd': 'SUED', 'sued': 'SUED', 'west': 'WEST'}
    for s in stands:
        c = s['poly'].centroid
        s['side'] = 'LANG' if abs(c.y) > abs(c.x) else 'KURZ'
        s['name'] = compass_name((c.x, c.y), north)
        for k, v in hint.items():
            if k in s['osm_name'].lower(): s['name'] = v
    # Kollisionen: gleiche Namen → nach Lage in den vier Quadranten neu verteilen
    used = {}
    for s in stands: used.setdefault(s['name'], []).append(s)
    if any(len(v) > 1 for v in used.values()):
        by_pos = {('LANG', 1): None, ('LANG', -1): None, ('KURZ', 1): None, ('KURZ', -1): None}
        fixed = {s['name'] for v in used.values() if len(v) == 1 for s in v}
        free = [n for n in ('NORD', 'OST', 'SUED', 'WEST') if n not in fixed]
        for s in stands:
            if len(used[s['name']]) > 1 and free: s['name'] = free.pop(0)
    return stands


CLEAR_SIDE, CLEAR_END = 5.0, 7.0      # Mindestabstand Tribünenfront zum Feld: Langseite / Torseite (Auslaufzone, Tornetz)


def clearance_zone():
    return Polygon([(-PITCH_L / 2 - CLEAR_END, -PITCH_W / 2 - CLEAR_SIDE), (PITCH_L / 2 + CLEAR_END, -PITCH_W / 2 - CLEAR_SIDE),
                    (PITCH_L / 2 + CLEAR_END, PITCH_W / 2 + CLEAR_SIDE), (-PITCH_L / 2 - CLEAR_END, PITCH_W / 2 + CLEAR_SIDE)])


def enforce_clearance(poly):
    """OSM-Gebäudepolygone enthalten Dachüberstände und Kartierungsfehler bis in den Rasen — die Front wird
    auf den Mindestabstand zurückgeschoben, die Rückkante bleibt."""
    pg = poly.difference(clearance_zone())
    if isinstance(pg, MultiPolygon): pg = max(pg.geoms, key=lambda g: g.area)
    return pg if not pg.is_empty else poly


def front_edge(poly):
    """Feldnahe Kante: längste Polygonkante, deren Mittelpunkt dem Feld am nächsten liegt."""
    pts = list(poly.exterior.coords)[:-1]
    field = Polygon([(-PITCH_L / 2, -PITCH_W / 2), (PITCH_L / 2, -PITCH_W / 2), (PITCH_L / 2, PITCH_W / 2), (-PITCH_L / 2, PITCH_W / 2)])
    edges = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); L = math.hypot(b[0] - a[0], b[1] - a[1])
        edges.append((Point(m).distance(field), -L, a, b))
    edges.sort()
    # alle Kanten, die annähernd so nah liegen wie die nächste und lang sind, zu einer Front verbinden
    near = [e for e in edges if e[0] <= edges[0][0] + 4 and -e[1] > 8]
    if not near: near = edges[:1]
    # Front = von der Gesamtausdehnung dieser Kanten entlang ihrer Hauptrichtung
    a, b = near[0][2], near[0][3]
    d = (b[0] - a[0], b[1] - a[1]); n = math.hypot(*d); d = (d[0] / n, d[1] / n)
    ts = [((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1]) for e in near for p in (e[2], e[3])]
    A = (a[0] + d[0] * min(ts), a[1] + d[1] * min(ts)); B = (a[0] + d[0] * max(ts), a[1] + d[1] * max(ts))
    # Orientierung: links = Z × n aus Feldsicht
    m = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2); nrm = (m[0], m[1]); nn = math.hypot(*nrm) or 1; nrm = (nrm[0] / nn, nrm[1] / nn)
    left = (-nrm[1], nrm[0])
    if (A[0] * left[0] + A[1] * left[1]) < (B[0] * left[0] + B[1] * left[1]): A, B = B, A
    return A, B, nrm


def depth_at(poly, p, nrm, maxd=200):
    ray = LineString([p, (p[0] + nrm[0] * maxd, p[1] + nrm[1] * maxd)])
    inter = ray.intersection(poly)
    if inter.is_empty: return 0
    geoms = getattr(inter, 'geoms', [inter])
    return max(Point(p).distance(Point(c)) for g in geoms for c in g.coords)


def blocks_for_stand(stand, next_id, standing=False, one_tier=None):
    poly, name = stand['poly'], stand['name']
    ov = stand.get('override', {})
    standing = ov.get('standing', standing)
    if 'tiers' in ov: one_tier = ov['tiers'] == 1
    rake_ov = math.tan(math.radians(ov['rake'])) if 'rake' in ov else None
    dpoly = stand.get('depth_poly', poly)
    A, B, nrm = front_edge(poly)
    W = math.hypot(B[0] - A[0], B[1] - A[1])
    n_blocks = max(1, round(W / BLOCK_W))
    d = ((B[0] - A[0]) / W, (B[1] - A[1]) / W)
    uniform = None
    if stand.get('uniform_depth', stand['kind'] == 'side' and 'depth_poly' not in stand):
        samples = sorted(depth_at(dpoly, (A[0] + d[0] * W * t, A[1] + d[1] * W * t), nrm) for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        uniform = samples[len(samples) // 2]          # Median: Pfeiler, Treppentürme und Ecken der Kontur fallen heraus
    out = []
    for i in range(n_blocks):
        u0, u1 = i / n_blocks, (i + 1) / n_blocks
        f0 = (A[0] + d[0] * W * u0, A[1] + d[1] * W * u0); f1 = (A[0] + d[0] * W * u1, A[1] + d[1] * W * u1)
        d0, d1 = (uniform, uniform) if uniform else (depth_at(dpoly, f0, nrm), depth_at(dpoly, f1, nrm))
        if max(d0, d1) < 4: continue
        d0, d1 = max(d0, 4), max(d1, 4)
        depth = (d0 + d1) / 2
        tiers = [('EINRANG', 0.0, 1.0)] if (one_tier if one_tier is not None else depth <= ONE_TIER_MAX) else [('UNTER', 0.0, 0.46), ('OBER', 0.46, 1.0)]
        z_prev_top = None
        for tier, v0, v1 in tiers:
            b0 = (f0[0] + nrm[0] * d0 * v0, f0[1] + nrm[1] * d0 * v0); b1 = (f1[0] + nrm[0] * d1 * v0, f1[1] + nrm[1] * d1 * v0)
            c0 = (f0[0] + nrm[0] * d0 * v1, f0[1] + nrm[1] * d0 * v1); c1 = (f1[0] + nrm[0] * d1 * v1, f1[1] + nrm[1] * d1 * v1)
            td = depth * (v1 - v0)
            rake = rake_ov if (rake_ov and tier == 'EINRANG') else (RAKE['EINRANG'] if tier == 'EINRANG' else RAKE[tier])
            z0 = 1.0 if z_prev_top is None else z_prev_top + TIER_GAP
            z1 = z0 + td * rake
            z_prev_top = z1
            rows, seats = max(1, round(td / ROW_M)), max(1, round(W / n_blocks / SEAT_M))
            out.append({'id': next_id[0], 'stand': name, 'tier': 'UNTER' if tier == 'EINRANG' else tier, 'order': i,
                        'rows': rows, 'seats': seats, 'quad': [list(b0), list(b1), list(c1), list(c0)],
                        'z0': round(z0, 2), 'z1': round(z1, 2), 'type': 'standing' if standing else 'seating',
                        'rle': [[rows * seats, 0]]})
            next_id[0] += 1
    return out


def corner_blocks(stand, outer, next_id, k=5, order_base=100):
    """Eckblöcke als Fächer: Front = Fase, Rückkante = Außenring, Richtung dreht von Seite zu Seite."""
    pg, key = stand['poly'], stand['key']
    x0, y0, x1, y1 = stand['inner_bounds']; c = CHAMFER
    sx = 1 if 'e' in key else -1; sy = 1 if 'n' in key else -1
    Px = (sx * (abs(x1 if sx > 0 else x0)), sy * (abs(y1 if sy > 0 else y0) - c))   # Ende der Torseiten-Kante
    Py = (sx * (abs(x1 if sx > 0 else x0) - c), sy * (abs(y1 if sy > 0 else y0)))   # Ende der Langseiten-Kante
    th_x, th_y = math.atan2(0, sx), math.atan2(sy, 0)                                  # Strahlrichtungen
    # Front von links nach rechts aus Feldsicht: links = Z × n mit n = Richtung zur Ecke
    n = (sx, sy); left = (-n[1], n[0])
    P_l, P_r = (Px, Py) if (Px[0] * left[0] + Px[1] * left[1]) > (Py[0] * left[0] + Py[1] * left[1]) else (Py, Px)
    th_l, th_r = (th_x, th_y) if P_l == Px else (th_y, th_x)
    # kürzester Drehweg
    dth = (th_r - th_l + math.pi) % (2 * math.pi) - math.pi
    def front(t): return (P_l[0] + (P_r[0] - P_l[0]) * t, P_l[1] + (P_r[1] - P_l[1]) * t)
    def ray(t):
        th = th_l + dth * t; return (math.cos(th), math.sin(th))
    def back(t, v=1.0):
        f, d = front(t), ray(t)
        L = LineString([f, (f[0] + d[0] * 300, f[1] + d[1] * 300)]).intersection(outer)
        geoms = getattr(L, 'geoms', [L]); far = max((Point(f).distance(Point(cd)) for g in geoms for cd in g.coords), default=8)
        return (f[0] + d[0] * far * v, f[1] + d[1] * far * v), far
    out = []
    for i in range(k):
        t0, t1 = i / k, (i + 1) / k
        (_, d0), (_, d1) = back(t0), back(t1); depth = (d0 + d1) / 2
        tiers = [('UNTER', 0.0, 0.46), ('OBER', 0.46, 1.0)] if depth > ONE_TIER_MAX else [('EINRANG', 0.0, 1.0)]
        z_prev = None
        for tier, v0, v1 in tiers:
            b0, _ = back(t0, v0); b1, _ = back(t1, v0); c0, _ = back(t0, v1); c1, _ = back(t1, v1)
            td = depth * (v1 - v0); rake = RAKE['EINRANG'] if tier == 'EINRANG' else RAKE[tier]
            z0 = 1.0 if z_prev is None else z_prev + TIER_GAP; z1 = z0 + td * rake; z_prev = z1
            wf = math.hypot(b1[0] - b0[0], b1[1] - b0[1]); wb = math.hypot(c1[0] - c0[0], c1[1] - c0[1])
            rows, seats = max(1, round(td / ROW_M)), max(1, round((wf + wb) / 2 / SEAT_M))
            out.append({'id': next_id[0], 'stand': stand['name'], 'tier': 'UNTER' if tier == 'EINRANG' else tier, 'order': order_base + i,
                        'rows': rows, 'seats': seats, 'quad': [list(b0), list(b1), list(c1), list(c0)],
                        'z0': round(z0, 2), 'z1': round(z1, 2), 'type': 'seating', 'rle': [[rows * seats, 0]]})
            next_id[0] += 1
    return out


def ring_to_stands(outer, inner):
    """Kesselring an den Innenecken mit Fase in vier Seiten und vier Ecken schneiden."""
    inner = inner.union(clearance_zone())
    ring = outer.difference(inner)
    ib = inner.bounds
    x0, y0, x1, y1 = ib
    c = CHAMFER; big = 400
    sides = {
        'y+': Polygon([(x0 + c, y1), (x1 - c, y1), (x1 - c, big), (x0 + c, big)]),
        'y-': Polygon([(x0 + c, y0), (x1 - c, y0), (x1 - c, -big), (x0 + c, -big)]),
        'x+': Polygon([(x1, y0 + c), (x1, y1 - c), (big, y1 - c), (big, y0 + c)]),
        'x-': Polygon([(x0, y0 + c), (x0, y1 - c), (-big, y1 - c), (-big, y0 + c)]),
    }
    corners = {
        'ne': Polygon([(x1 - c, y1), (x1, y1 - c), (big, y1 - c), (big, big), (x1 - c, big)]),
        'nw': Polygon([(x0 + c, y1), (x0, y1 - c), (-big, y1 - c), (-big, big), (x0 + c, big)]),
        'se': Polygon([(x1 - c, y0), (x1, y0 + c), (big, y0 + c), (big, -big), (x1 - c, -big)]),
        'sw': Polygon([(x0 + c, y0), (x0, y0 + c), (-big, y0 + c), (-big, -big), (x0 + c, -big)]),
    }
    res = []
    for k, w in list(sides.items()) + list(corners.items()):
        pg = ring.intersection(w)
        if pg.is_empty: continue
        if isinstance(pg, MultiPolygon): pg = max(pg.geoms, key=lambda g: g.area)
        res.append({'osm_name': '', 'poly': pg, 'kind': 'side' if k in sides else 'corner', 'key': k, 'inner_bounds': ib, 'outer': outer})
    return res


def parametric_stand(side, length, depth, offset=None):
    """Tribüne ohne OSM-Polygon: Rechteck parallel zur Feldkante. side: 'y+','y-','x+','x-'."""
    if side in ('y+', 'y-'):
        s = 1 if side == 'y+' else -1; off = offset if offset is not None else PITCH_W / 2 + 7
        pg = Polygon([(-length / 2, s * off), (length / 2, s * off), (length / 2, s * (off + depth)), (-length / 2, s * (off + depth))])
    else:
        s = 1 if side == 'x+' else -1; off = offset if offset is not None else PITCH_L / 2 + 9
        pg = Polygon([(s * off, -length / 2), (s * off, length / 2), (s * (off + depth), length / 2), (s * (off + depth), -length / 2)])
    return {'osm_name': '', 'poly': pg, 'kind': 'side', 'key': side}


# ── Dach, Design, Testmuster ─────────────────────────────────────────
def roof_for(blocks, stands_with_roof, fraction=0.62):
    """Ringdach je Block: vom obersten Rang bis fraction der Gesamttiefe nach innen. Zusammengehörige Ränge werden
    über order + räumliche Nähe gefunden, nicht über den Tribünennamen — in Kurven kann der Kompassname zwischen
    Unter- und Oberrang desselben Sektors wechseln (das erzeugte die verschobenen Platten)."""
    def cen(b): return (sum(p[0] for p in b['quad']) / 4, sum(p[1] for p in b['quad']) / 4)
    def stack(b):                      # alle Ränge desselben Sektors
        c = cen(b)
        return [x for x in blocks if x['order'] == b['order'] and math.hypot(cen(x)[0] - c[0], cen(x)[1] - c[1]) < 70]
    segs = []
    for b in blocks:
        if b['stand'] not in stands_with_roof: continue
        st = stack(b)
        if b['z1'] < max(x['z1'] for x in st) - 0.01: continue      # nur der oberste Rang trägt das Dach
        front = min(st, key=lambda x: x['z0'])['quad']
        F0, F1 = front[0], front[1]; f0, f1, c1, c0 = b['quad']
        i0 = (F0[0] + (c0[0] - F0[0]) * (1 - fraction), F0[1] + (c0[1] - F0[1]) * (1 - fraction))
        i1 = (F1[0] + (c1[0] - F1[0]) * (1 - fraction), F1[1] + (c1[1] - F1[1]) * (1 - fraction))
        z = max(x['z1'] for x in st)
        segs.append({'id': f'roof-{len(segs)}', 'quad': [list(i0), list(i1), list(c1), list(c0)], 'heights': [z + 3, z + 3, z + 4.5, z + 4.5]})
    return segs


def roof_plate(blocks, stand, inner_tier='MITTEL', clearance=(3.0, 5.0), span_deg=30.0):
    """Tribuna-Dach (Camp Nou): folgt der Tribünenkrümmung. Es deckt alle Blöcke ab, deren Frontkante um weniger
    als span_deg von der Tribünenachse abweicht — unabhängig vom Kompassnamen, damit die Kurvenanfänge dazugehören.
    Je Block ein Segment von der Front des inner_tier bis zur Hinterkante des obersten Rangs; Nachbarn teilen sich
    die Punkte, die Höhe ist für alle gleich → eine durchgehende, gekrümmte Platte."""
    side = [b for b in blocks if b['stand'] == stand]
    if not side: return []
    cx = sum(sum(p[0] for p in b['quad']) / 4 for b in side) / len(side); cy = sum(sum(p[1] for p in b['quad']) / 4 for b in side) / len(side)
    long_side = abs(cy) > abs(cx); sgn = 1 if (cy if long_side else cx) > 0 else -1
    def on_side(b):
        c = (sum(p[0] for p in b['quad']) / 4, sum(p[1] for p in b['quad']) / 4)
        return (c[1] * sgn > 0) if long_side else (c[0] * sgn > 0)
    def angle(b):
        f0, f1 = b['quad'][0], b['quad'][1]; a = math.degrees(math.atan2(f1[1] - f0[1], f1[0] - f0[0]))
        return abs(((a + 90) % 180) - 90) if long_side else abs(((a) % 180) - 90)
    top_tier = max(blocks, key=lambda b: b['z1'])['tier']
    tops = [b for b in blocks if b['tier'] == top_tier and on_side(b) and angle(b) <= span_deg]
    fronts = {b['order']: b for b in blocks if b['tier'] == inner_tier and on_side(b)}
    z_top = max(b['z1'] for b in tops)
    segs = []
    for b in sorted(tops, key=lambda x: x['order']):
        # Frontblock des Mittelrangs mit größter Überdeckung entlang der Tribüne (Blockzahl je Rang kann abweichen)
        bx = sum(p[0] for p in b['quad']) / 4; by = sum(p[1] for p in b['quad']) / 4
        fb = min(fronts.values(), key=lambda f: (sum(p[0] for p in f['quad']) / 4 - bx) ** 2 + (sum(p[1] for p in f['quad']) / 4 - by) ** 2)
        i0, i1 = fb['quad'][0], fb['quad'][1]
        c1, c0 = b['quad'][2], b['quad'][3]
        # Vorderkante entlang der Oberrang-Blockbreite parametrisieren, damit Nachbarsegmente sich die Punkte teilen
        f0, f1 = b['quad'][0], b['quad'][1]
        d0 = (i0[0] - f0[0], i0[1] - f0[1]); d1 = (i1[0] - f1[0], i1[1] - f1[1])
        in0 = (f0[0] + (d0[0] + d1[0]) / 2, f0[1] + (d0[1] + d1[1]) / 2); in1 = (f1[0] + (d0[0] + d1[0]) / 2, f1[1] + (d0[1] + d1[1]) / 2)
        segs.append({'id': f'roof-{stand}-{b["order"]}', 'quad': [list(in0), list(in1), list(c1), list(c0)],
                     'heights': [z_top + clearance[0], z_top + clearance[0], z_top + clearance[1], z_top + clearance[1]]})
    return segs


def encode(seq):
    rle = []
    for c in seq:
        if rle and rle[-1][1] == c: rle[-1][0] += 1
        else: rle.append([1, c])
    return rle


def color_index(palette, hexcol):
    if hexcol not in palette: palette.append(hexcol)
    return palette.index(hexcol)


def standard_design(blocks, palette, col1, col2):
    i1, i2 = color_index(palette, col1), color_index(palette, col2)
    for b in blocks:
        rows, seats = b['rows'], b['seats']; seq = []
        for r in range(rows):
            v = (r + 0.5) / rows
            seq.extend([i2 if 0.45 <= v < 0.60 else i1] * seats)
        b['rle'] = encode(seq)


def press_letter(block, palette, letter, col_bg, col_fg):
    rows, seats = block['rows'], block['seats']
    img = Image.new('L', (seats, rows), 0); d = ImageDraw.Draw(img)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', int(rows * 0.9))
    bb = d.textbbox((0, 0), letter, font=font); w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((seats - w) / 2 - bb[0], (rows - h) / 2 - bb[1]), letter, fill=255, font=font)
    px = img.load(); i_bg, i_fg = color_index(palette, col_bg), color_index(palette, col_fg)
    seq = []
    for r in range(rows):
        y = rows - 1 - r
        seq.extend([i_fg if px[c, y] > 127 else i_bg for c in range(seats)])
    block['rle'] = encode(seq)


def finish_scene(name, club, blocks, roof, outline, main_stand, colors, letter_stand, capacity=None, facade=True):
    palette = list(PALETTE)
    standard_design(blocks, palette, *colors)
    far = [b for b in blocks if b['stand'] == letter_stand and b['tier'] == 'UNTER']
    far.sort(key=lambda b: b['order'])
    if far: press_letter(far[len(far) // 2], palette, 'R', colors[0], colors[1])
    scene = {'schema': 'websoccer.stadium-live-scene', 'version': 1, 'stadium': name, 'club': {'name': club}, 'units': 'm',
             'frame': {'name': 'pitch', 'origin': 'pitch-center', 'xAxis': 'goal-to-goal', 'yAxis': 'touchline-to-touchline', 'zAxis': 'up'},
             'pitch': {'length': PITCH_L, 'width': PITCH_W}, 'homeStand': main_stand, 'mainStand': main_stand, 'source': 'OSM building/grandstand (ODbL) + BLUEPRINT V2',
             'clubColors': {'primary': colors[0], 'secondary': colors[1]}, 'capacity': capacity, 'facade': facade, 'farStand': letter_stand, 'steckbrief': STECKBRIEF.get(name, {}).get('_global', {}), 'palette': palette, 'blocks': blocks,
             'outline': [list(p) for p in outline.exterior.coords], 'roof': {'mode': 'explicit', 'segments': roof}}
    for b in blocks: assert sum(n for n, _ in b['rle']) == b['rows'] * b['seats']
    bb = unary_union([Polygon(b['quad']) for b in blocks]).bounds
    scene['standsBounds'] = [round(v, 1) for v in bb]
    return scene


# ── Die zwei Stadien ─────────────────────────────────────────────────
def build_dortmund():
    o = load(OSM / 'dortmund.json')
    outer, inner = o['ring']
    stands = ring_to_stands(outer, inner)
    sides = [s for s in stands if s['kind'] == 'side']; corners = [s for s in stands if s['kind'] == 'corner']
    assign_names(sides, o['north'])
    for s in corners:                                  # Ecke zählt zur angrenzenden Torseite (Kurve)
        c = s['poly'].centroid
        s['name'] = next(x['name'] for x in sides if x['key'] == ('x+' if c.x > 0 else 'x-'))
        s['side'] = 'KURZ'
    for s in sides: s['depth_poly'] = outer.difference(inner.union(clearance_zone()))   # Tiefe bis zum Außenring, nicht bis zum Schnitt
    nid = [0]; blocks = []
    sb = STECKBRIEF.get('Signal Iduna Park', {})
    ci = 0
    for s in stands:
        s['override'] = sb.get(s['name'], {}) if s['kind'] == 'side' else {}
        if s['kind'] == 'corner':
            ci += 1; blocks += corner_blocks(s, outer, nid, order_base=100 * ci)
        else:
            blocks += blocks_for_stand(s, nid)
    roof = roof_for(blocks, {n for n in ('NORD', 'OST', 'SUED', 'WEST') if sb.get(n, {}).get('roof', True)})
    return finish_scene('Signal Iduna Park', 'Borussia Dortmund', blocks, roof, outer, 'WEST', ('#ffd400', '#101216'), 'OST', capacity=81365)


def build_elversberg():
    o = load(OSM / 'elversberg.json')
    # OSM-Tribünen: Haupttribüne (Süd), C1 (Ost), Westtribüne + E1–E3 (West) → je Seite vereinigen
    groups = {}
    for nm, pg in o['stands']:
        c = pg.centroid; key = ('y+' if c.y > 0 else 'y-') if abs(c.y) > abs(c.x) else ('x+' if c.x > 0 else 'x-')
        groups.setdefault(key, []).append((nm, pg))
    stands = []
    for key, lst in groups.items():
        pg = unary_union([p for _, p in lst]).buffer(0.5).buffer(-0.5)
        if isinstance(pg, MultiPolygon): pg = max(pg.geoms, key=lambda g: g.area)
        stands.append({'osm_name': ' / '.join(n for n, _ in lst), 'poly': enforce_clearance(pg), 'kind': 'side', 'key': key})
    # Nordtribüne fehlt in OSM (Neubau): parametrisch, so lang wie die Haupttribüne, 4.400 Plätze ≈ 18 m Tiefe
    if 'y+' not in groups:
        main = groups['y-'][0][1].bounds
        stands.append(parametric_stand('y+', length=main[2] - main[0], depth=18.0))
    stands = assign_names(stands, o['north'])
    sb = STECKBRIEF.get('URSAPHARM-Arena an der Kaiserlinde', {})
    nid = [0]; blocks = []
    for s in stands:
        s['override'] = sb.get(s['name'], {})
        blocks += blocks_for_stand(s, nid, standing=('Steh' in s['osm_name']), one_tier=True)
    roof = roof_for(blocks, {n for n in ('NORD', 'OST', 'SUED', 'WEST') if sb.get(n, {}).get('roof', True)})
    return finish_scene('URSAPHARM-Arena an der Kaiserlinde', 'SV 07 Elversberg', blocks, roof, o['outline'], 'SUED', ('#17191c', '#f4f7fb'), 'NORD', capacity=14643, facade=False)


# ── Weg 3: Oval aus konzentrischen Ringen (building:part-Multipolygone mit Höhen) ───────────
def load_rings(path, stadium_name):
    """Pitch-Rahmen + konzentrische Ringe (nach min_height sortiert) + Außenkontur."""
    j = json.load(open(path)); els = j['elements']
    stad = next(e for e in els if e.get('tags', {}).get('name') == stadium_name)
    ref = stad['geometry'][0]; lat0, lon0 = ref['lat'], ref['lon']
    P = lambda geom: [to_m(g['lat'], g['lon'], lat0, lon0) for g in geom]
    outline = Polygon(P(stad['geometry']))
    pitch = next(e for e in els if e['type'] == 'way' and e.get('tags', {}).get('leisure') == 'pitch'
                 and outline.contains(Polygon(P(e['geometry'])).centroid))
    pp = P(pitch['geometry']); pp = pp[:-1] if pp[0] == pp[-1] else pp
    cx = sum(p[0] for p in pp) / len(pp); cy = sum(p[1] for p in pp) / len(pp)
    L, th = max(((math.hypot(b[0] - a[0], b[1] - a[1]), math.atan2(b[1] - a[1], b[0] - a[0]))
                 for a, b in zip(pp, pp[1:] + pp[:1])), key=lambda t: t[0])
    cs, sn = math.cos(-th), math.sin(-th)
    rot = lambda p: ((p[0] - cx) * cs - (p[1] - cy) * sn, (p[0] - cx) * sn + (p[1] - cy) * cs)
    north = rot((cx, cy + 1))
    poly = lambda geom: Polygon([rot(p) for p in P(geom)])
    rings = []
    for e in els:
        t = e.get('tags', {})
        if e['type'] == 'relation' and t.get('building:part') == 'yes' and 'height' in t:
            outers = [poly(m['geometry']) for m in e['members'] if m.get('role') == 'outer' and 'geometry' in m]
            inners = [poly(m['geometry']) for m in e['members'] if m.get('role') == 'inner' and 'geometry' in m]
            if not outers or not outline.contains(outers[0].centroid.__class__(0, 0)) and False: pass
            o = unary_union(outers)
            if not Polygon([rot(p) for p in P(stad['geometry'])]).contains(o.centroid): continue
            rings.append({'min': float(t.get('min_height', 0)), 'max': float(t['height']), 'outer': o,
                          'inner': unary_union(inners) if inners else None, 'colour': t.get('building:facade:colour')})
    rings.sort(key=lambda r: r['min'])
    return {'rings': rings, 'outline': Polygon([rot(p) for p in P(stad['geometry'])]), 'north': north, 'pitchLen': L}


def oval_blocks(rings, tiers, next_id, block_w=BLOCK_W, north=(0, 1)):
    """Jeder Ring wird zu einem Rang: Front = Innenkante des Rings (bzw. Feld + Abstand), Rückkante = Außenkante.
    Blöcke als Winkelsektoren von ~block_w m an der Front; Tribünenname aus der Himmelsrichtung der Sektormitte."""
    out = []
    z_prev = None
    zone = clearance_zone()
    for ring, (tier, rake_deg, overhang) in zip(rings, tiers):
        rounded_zone = zone.buffer(-14).buffer(14)              # Auslaufzone mit runden Ecken — Ovalkessel haben keine Ecken
        inner = ring['inner'] if ring['inner'] is not None else rounded_zone
        if overhang: inner = inner.buffer(-overhang)          # Kragarm: Oberrang hängt über den Rang darunter
        inner = inner.union(rounded_zone)
        outer = ring['outer']
        # Front entlang der Innenkante in Bogenlängen-Schritten; Rückpunkt je Frontpunkt entlang der
        # lokalen Normalen der Innenkante — Nachbarblöcke teilen sich damit exakt die Punkte (keine Keile)
        ib = inner.exterior
        n = max(8, round(ib.length / block_w))
        pts = [ib.interpolate(i / n, normalized=True) for i in range(n)]
        backs = []
        for i, pt in enumerate(pts):
            prv, nxt = pts[i - 1], pts[(i + 1) % n]
            tx, ty = nxt.x - prv.x, nxt.y - prv.y; tl = math.hypot(tx, ty) or 1
            nx, ny = ty / tl, -tx / tl                              # Normale, nach außen zeigend
            if nx * pt.x + ny * pt.y < 0: nx, ny = -nx, -ny
            ray = LineString([(pt.x, pt.y), (pt.x + nx * 400, pt.y + ny * 400)])
            L = ray.intersection(outer); geoms = getattr(L, 'geoms', [L])
            cands = [c for g in geoms for c in getattr(g, 'coords', [])]
            far = max(cands, key=lambda c: math.hypot(c[0] - pt.x, c[1] - pt.y)) if cands else (pt.x, pt.y)
            backs.append((far, math.hypot(far[0] - pt.x, far[1] - pt.y)))
        # Eine Tiefe je Rang (Median): Rückkante = Front + Normale × Tiefe → alle Blöcke gleich viele Reihen,
        # Reihen laufen um die Kurve durch, Dach und Oberkante liegen auf einer Höhe
        med_d = sorted(b[1] for b in backs)[len(backs) // 2]
        uni = []
        for i, pt in enumerate(pts):
            prv, nxt = pts[i - 1], pts[(i + 1) % n]
            tx, ty = nxt.x - prv.x, nxt.y - prv.y; tl = math.hypot(tx, ty) or 1
            nx, ny = ty / tl, -tx / tl
            if nx * pt.x + ny * pt.y < 0: nx, ny = -nx, -ny
            uni.append(((pt.x + nx * med_d, pt.y + ny * med_d), med_d))
        backs = uni
        depths = []
        for i in range(n):
            f0, f1 = pts[i], pts[(i + 1) % n]; (b0, d0), (b1, d1) = backs[i], backs[(i + 1) % n]
            depths.append(((f0.x, f0.y), (f1.x, f1.y), b0, b1, (d0 + d1) / 2))
        # Höhe je Rang aus der Median-Tiefe (ein Rang, eine Steigung — die Rückkante folgt der echten Kontur)
        med = sorted(d[4] for d in depths)[len(depths) // 2]
        rake = math.tan(math.radians(rake_deg))
        z0 = 1.0 if z_prev is None else z_prev + TIER_GAP
        z1 = z0 + med * rake; z_prev = z1
        for i, (f0, f1, b0, b1, depth) in enumerate(depths):
            if depth < 3: continue
            mx = (f0[0] + f1[0] + b0[0] + b1[0]) / 4; my = (f0[1] + f1[1] + b0[1] + b1[1]) / 4
            name = compass_name((mx, my), north)
            # Front links→rechts aus Feldsicht
            nrm = (mx, my); nn = math.hypot(*nrm) or 1; left = (-nrm[1] / nn, nrm[0] / nn)
            if (f0[0] * left[0] + f0[1] * left[1]) < (f1[0] * left[0] + f1[1] * left[1]): f0, f1, b0, b1 = f1, f0, b1, b0
            # Treppe zwischen den Blöcken: je 0,6 m Einzug an beiden Enden — an den Knicken der Kurve entstehen so
            # saubere Gänge statt ineinander laufender Sitzreihen (das Modul füllt den Gang als Trittfläche)
            def inset(a, b, d=0.6):
                L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1; ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                return (a[0] + ux * d, a[1] + uy * d), (b[0] - ux * d, b[1] - uy * d)
            f0, f1 = inset(f0, f1); b0, b1 = inset(b0, b1)
            w = (math.hypot(f1[0] - f0[0], f1[1] - f0[1]) + math.hypot(b1[0] - b0[0], b1[1] - b0[1])) / 2
            rows, seats = max(1, round(depth / ROW_M)), max(1, round(w / SEAT_M))
            out.append({'id': next_id[0], 'stand': name, 'tier': tier, 'order': i, 'rows': rows, 'seats': seats,
                        'quad': [list(f0), list(f1), list(b1), list(b0)], 'z0': round(z0, 2), 'z1': round(z0 + depth * rake, 2),
                        'type': 'seating', 'rle': [[rows * seats, 0]]})
            next_id[0] += 1
    return out


def load_ring_building(path, stadium_name, building_way, track_rel):
    """Ovalstadion als ein Gebäudepolygon (ggf. mit Lücke) + Laufbahn-Relation als Innengrenze."""
    j = json.load(open(path)); els = {(e['type'], e['id']): e for e in j['elements']}
    stad = next(e for e in j['elements'] if e.get('tags', {}).get('name') == stadium_name)
    ref = stad['geometry'][0]; lat0, lon0 = ref['lat'], ref['lon']
    P = lambda geom: [to_m(g['lat'], g['lon'], lat0, lon0) for g in geom]
    outline = Polygon(P(stad['geometry']))
    pitch = next(e for e in j['elements'] if e['type'] == 'way' and e.get('tags', {}).get('leisure') == 'pitch'
                 and e['tags'].get('sport') == 'soccer' and outline.contains(Polygon(P(e['geometry'])).centroid))
    pp = P(pitch['geometry']); pp = pp[:-1] if pp[0] == pp[-1] else pp
    cx = sum(p[0] for p in pp) / len(pp); cy = sum(p[1] for p in pp) / len(pp)
    L, th = max(((math.hypot(b[0] - a[0], b[1] - a[1]), math.atan2(b[1] - a[1], b[0] - a[0]))
                 for a, b in zip(pp, pp[1:] + pp[:1])), key=lambda t: t[0])
    cs, sn = math.cos(-th), math.sin(-th)
    rot = lambda p: ((p[0] - cx) * cs - (p[1] - cy) * sn, (p[0] - cx) * sn + (p[1] - cy) * cs)
    poly = lambda geom: Polygon([rot(p) for p in P(geom)])
    building = poly(els[('way', building_way)]['geometry']).buffer(0)
    tr = els[('relation', track_rel)]
    t_outer = unary_union([poly(m['geometry']) for m in tr['members'] if m.get('role') == 'outer' and 'geometry' in m])
    t_inner = unary_union([poly(m['geometry']) for m in tr['members'] if m.get('role') == 'inner' and 'geometry' in m])
    return {'building': building, 'track_outer': t_outer, 'track_inner': t_inner, 'north': rot((cx, cy + 1)), 'pitchLen': L,
            'outline': Polygon([rot(p) for p in P(stad['geometry'])])}


def oval_blocks_split(ring, tiers, next_id, block_w=BLOCK_W, north=(0, 1)):
    """Ein Ring (Innenkante, Außenkante) in mehrere Ränge nach Tiefenanteilen; Sektoren ohne Treffer auf der
    Außenkante (Lücke, z. B. Marathontor) entfallen."""
    out = []
    inner, outer = ring['inner'], ring['outer']
    ib = inner.exterior
    n = max(8, round(ib.length / block_w))
    pts = [ib.interpolate(i / n, normalized=True) for i in range(n)]
    normals, depths = [], []
    for i, pt in enumerate(pts):
        prv, nxt = pts[i - 1], pts[(i + 1) % n]
        tx, ty = nxt.x - prv.x, nxt.y - prv.y; tl = math.hypot(tx, ty) or 1
        nx, ny = ty / tl, -tx / tl
        if nx * pt.x + ny * pt.y < 0: nx, ny = -nx, -ny
        normals.append((nx, ny))
        ray = LineString([(pt.x, pt.y), (pt.x + nx * 400, pt.y + ny * 400)])
        L = ray.intersection(outer); geoms = getattr(L, 'geoms', [L])
        cands = [c for g in geoms for c in getattr(g, 'coords', [])]
        depths.append(max((math.hypot(c[0] - pt.x, c[1] - pt.y) for c in cands), default=0))
    med = sorted(d for d in depths if d > 3)[len([d for d in depths if d > 3]) // 2]
    z_prev = None
    for tier, rake_deg, (v0, v1) in tiers:
        rake = math.tan(math.radians(rake_deg))
        z0 = 1.0 if z_prev is None else z_prev + TIER_GAP
        td = med * (v1 - v0); z1 = z0 + td * rake; z_prev = z1
        for i in range(n):
            j2 = (i + 1) % n
            if depths[i] < 3 or depths[j2] < 3: continue          # Lücke im Ring
            def at(k, v): return (pts[k].x + normals[k][0] * med * v, pts[k].y + normals[k][1] * med * v)
            f0, f1, b0, b1 = at(i, v0), at(j2, v0), at(i, v1), at(j2, v1)
            mx = (f0[0] + f1[0] + b0[0] + b1[0]) / 4; my = (f0[1] + f1[1] + b0[1] + b1[1]) / 4
            name = compass_name((mx, my), north)
            nrm = (mx, my); nn = math.hypot(*nrm) or 1; left = (-nrm[1] / nn, nrm[0] / nn)
            if (f0[0] * left[0] + f0[1] * left[1]) < (f1[0] * left[0] + f1[1] * left[1]): f0, f1, b0, b1 = f1, f0, b1, b0
            def inset(a, b, d=0.6):
                Lg = math.hypot(b[0] - a[0], b[1] - a[1]) or 1; ux, uy = (b[0] - a[0]) / Lg, (b[1] - a[1]) / Lg
                return (a[0] + ux * d, a[1] + uy * d), (b[0] - ux * d, b[1] - uy * d)
            f0, f1 = inset(f0, f1); b0, b1 = inset(b0, b1)
            w = (math.hypot(f1[0] - f0[0], f1[1] - f0[1]) + math.hypot(b1[0] - b0[0], b1[1] - b0[1])) / 2
            rows, seats = max(1, round(td / ROW_M)), max(1, round(w / SEAT_M))
            out.append({'id': next_id[0], 'stand': name, 'tier': tier, 'order': i, 'rows': rows, 'seats': seats,
                        'quad': [list(f0), list(f1), list(b1), list(b0)], 'z0': round(z0, 2), 'z1': round(z1, 2),
                        'type': 'seating', 'rle': [[rows * seats, 0]]})
            next_id[0] += 1
    return out


def build_olympiastadion():
    o = load_ring_building(OSM / 'olympiastadion.json', 'Olympiastadion Berlin', building_way=24296022, track_rel=2418295)
    inner = o['track_outer'].union(clearance_zone())          # Ränge beginnen hinter der Laufbahn
    nid = [0]
    blocks = oval_blocks_split({'inner': inner, 'outer': o['building']}, [('UNTER', 16, (0.0, 0.45)), ('OBER', 28, (0.45, 1.0))], nid, north=o['north'])
    sb = STECKBRIEF['Olympiastadion Berlin']
    roof = roof_for(blocks, {'NORD', 'OST', 'SUED', 'WEST'}, fraction=0.7)     # Ringdach, Lücke am Marathontor ergibt sich aus den Blöcken
    facade_outline = o['building'].union(o['track_outer']).buffer(0)
    if isinstance(facade_outline, MultiPolygon): facade_outline = max(facade_outline.geoms, key=lambda g: g.area)
    facade_outline = facade_outline.simplify(1.0)
    scene = finish_scene('Olympiastadion Berlin', 'Hertha BSC', blocks, roof, facade_outline, 'SUED', ('#1f4ea1', '#f4f6f8'), 'NORD', capacity=74475)
    scene['outline'] = [list(p) for p in facade_outline.exterior.coords][:-1]
    hull = facade_outline.convex_hull.buffer(1.5).simplify(1.0)                       # konvexes Loch im Gelände — Earcut-sicher
    scene['groundHole'] = [list(p) for p in hull.exterior.coords][:-1]
    # Fassade nur an der Außenkante: das C-förmige Gebäudepolygon läuft mit seinem Rand auch an der Laufbahn entlang —
    # Kanten, die näher als 1,3 × Laufbahnradius liegen, sind Innenkanten und bekommen keine Wand
    track_r = lambda ang: max((math.hypot(x, y) for x, y in o['track_outer'].exterior.coords if abs(((math.atan2(y, x) - ang) + math.pi) % (2 * math.pi) - math.pi) < 0.12), default=60)
    segs = []
    pts = scene['outline']
    for a, b in zip(pts, pts[1:] + pts[:1]):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if math.hypot(mx, my) > 1.3 * track_r(math.atan2(my, mx)): segs.append([a, b])
    scene['facadeSegments'] = segs
    scene['steckbrief'] = sb.get('_global', {}); scene['facade'] = True
    scene['track'] = {'outer': [list(p) for p in o['track_outer'].exterior.coords], 'inner': [list(p) for p in o['track_inner'].exterior.coords]}
    bb = unary_union([Polygon(b['quad']) for b in blocks]).bounds
    scene['standsBounds'] = [round(v, 1) for v in bb]
    return scene


def build_camp_nou():
    o = load_rings(OSM / 'campnou.json', 'Spotify Camp Nou')
    rings = o['rings']
    # OSM: vier Terrassen (0–5, 5–10, 10–20, 20–25 m). Steckbrief: drei Ränge — Ring 0+1 = unten, Ring 2 = Mitte, Ring 3 = oben
    r0, r1, r2, r3 = rings
    lower = {'min': 0, 'max': 10, 'outer': r1['outer'], 'inner': None}
    merged = [lower, r2, r3]
    nid = [0]
    blocks = oval_blocks(merged, [('UNTER', 18, 0), ('MITTEL', 30, 10), ('OBER', 34, 12)], nid, north=o['north'])
    # Steckbrief: Dach nur über der Haupttribüne (West); Farbwechsel je Block; Schriftzug im Mittelrang gegenüber
    sb = STECKBRIEF['Camp Nou']
    roof = []
    for n in ('NORD', 'OST', 'SUED', 'WEST'):
        if sb.get(n, {}).get('roof', False): roof += roof_plate(blocks, n, span_deg=sb[n].get('span', 30))
    scene = finish_scene('Camp Nou', 'FC Barcelona', blocks, roof, r3['outer'], 'WEST', ('#0979e0', '#c43d60'), 'OST', capacity=99354)
    palette = scene['palette']
    i_b, i_g = color_index(palette, '#0979e0'), color_index(palette, '#c43d60')
    for b in blocks:                                   # Blockweise Blau/Grana wie im Original, Band als Trennung
        base = i_b if (b['order'] // 2) % 2 == 0 else i_g
        b['rle'] = encode([base] * (b['rows'] * b['seats']))
    text = 'MES QUE UN CLUB'
    mid = sorted([b for b in blocks if b['stand'] == 'OST' and b['tier'] == 'MITTEL'], key=lambda b: b['order'])
    start = max(0, (len(mid) - len(text)) // 2)
    i_w = color_index(palette, '#f4f6f8')
    for k, ch in enumerate(text):
        if start + k >= len(mid): break
        blk = mid[start + k]
        if ch != ' ': press_letter(blk, palette, ch, palette[decode_first(blk)], '#f4f6f8')
    scene['steckbrief'] = sb.get('_global', {})
    scene['facade'] = True
    bb = unary_union([Polygon(b['quad']) for b in blocks]).bounds
    scene['standsBounds'] = [round(v, 1) for v in bb]
    return scene


def decode_first(block):
    return block['rle'][0][1]


# ── Umfeld aus dem Bundle (OSM: Gebäude, Straßen, Grün) in den Szenenrahmen drehen ─────────
def attach_surroundings(scene, entry, radius=380, seed=7):
    import random, gzip
    m = entry['meta']; fc = m.get('fieldC', [0, 0]); th = m.get('axisTheta', 0)
    osm_out = Polygon(scene['outline']).buffer(0)
    def mk(flip):
        c, s_ = math.cos(-th), math.sin(-th); f = -1 if flip else 1
        return lambda p: [f * ((p[0] - fc[0]) * c - (p[1] - fc[1]) * s_), f * ((p[0] - fc[0]) * s_ + (p[1] - fc[1]) * c)]
    best = None
    for flip in (False, True):                       # Bundle-Rahmen kann um 180° gedreht sein → Konturabgleich
        rot = mk(flip); bo = Polygon([rot(p) for p in entry['outline']]).buffer(0)
        iou = bo.intersection(osm_out).area / bo.union(osm_out).area
        if not best or iou > best[0]: best = (iou, rot)
    rot = best[1]; rnd = random.Random(seed)
    near = lambda pts: any(math.hypot(*p) < radius for p in pts)
    buildings = []
    for poly in entry['bg']['buildings']:
        pts = [rot(p) for p in poly]
        if not near(pts): continue
        pg = Polygon(pts)
        if not pg.is_valid or pg.area < 25 or pg.intersects(osm_out): continue
        buildings.append({'poly': [[round(x, 1), round(y, 1)] for x, y in pts], 'h': rnd.choice([6, 8, 9, 11, 12, 14, 18])})
    roads = []
    for r in entry['bg']['roads']:
        pts = [rot(p) for p in r['p']]
        if near(pts): roads.append({'w': r.get('w', 1), 'p': [[round(x, 1), round(y, 1)] for x, y in pts]})
    green = []
    for g in entry['bg']['green']:
        pts = [rot(p) for p in g]
        if near(pts) and Polygon(pts).is_valid: green.append([[round(x, 1), round(y, 1)] for x, y in pts])
    scene['surroundings'] = {'source': 'OpenStreetMap (ODbL)', 'buildings': buildings, 'roads': roads, 'green': green}
    return best[0]


def load_bundle():
    import gzip, re as _re
    text = gzip.open(ROOT.parent / 'stadium_data_all.js.gz', 'rt', encoding='utf-8').read()
    arr = json.loads(_re.search(r'const\s+STADIUMS\s*=\s*(\[.*\])\s*;\s*$', text, _re.S).group(1))
    out = {x['meta']['club']: x for x in arr}
    # The historical handoff source is not part of the repository.  The
    # checked-in V2 cache is the authoritative Elversberg input now.
    return out


if __name__ == '__main__':
    bundle = load_bundle()
    for key, fn, club in (('bvb', build_dortmund, 'Borussia Dortmund'), ('elversberg', build_elversberg, 'SV Elversberg'), ('campnou', build_camp_nou, None), ('olympiastadion', build_olympiastadion, 'Olympiastadion (PoC)')):
        sc = fn()
        if club: attach_surroundings(sc, bundle[club])
        json.dump(sc, open(OUT / f'{key}_v2.json', 'w'), separators=(',', ':'))
        by = {}
        for b in sc['blocks']: by.setdefault(b['stand'], [0, 0]); by[b['stand']][0] += 1; by[b['stand']][1] += b['rows'] * b['seats']
        print(key, 'blocks', len(sc['blocks']), 'seats', sum(b['rows'] * b['seats'] for b in sc['blocks']), 'roof', len(sc['roof']['segments']), by)
