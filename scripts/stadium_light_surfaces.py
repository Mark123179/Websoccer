"""Exact lamp-surface evidence for offline source-model studies (world metres)."""
import numpy as np


def closest_surface(point, triangles):
    """Return distance, closest point and triangle index, including degenerate faces.

    A vertex/AABB/centroid distance is not a distance to a lamp face. Check the
    plane projection inside each triangle and its three closed edge segments.
    No spatial approximation or tolerance inflation is used for acceptance.
    """
    point = np.asarray(point, dtype=float)
    triangles = np.asarray(triangles, dtype=float)
    if point.shape != (3,) or triangles.ndim != 3 or triangles.shape[1:] != (3, 3):
        raise ValueError("Expected a point and nonempty Nx3x3 lamp triangles")
    if not len(triangles) or not np.isfinite(triangles).all() or not np.isfinite(point).all():
        raise ValueError("Lamp surface and point must be nonempty and finite")
    a, b, c = triangles.transpose(1, 0, 2)
    ab, ac = b-a, c-a
    normal = np.cross(ab, ac)
    normal2 = np.einsum("ij,ij->i", normal, normal)
    offset = point-a
    projection = point - normal * np.divide(
        np.einsum("ij,ij->i", offset, normal), normal2,
        out=np.zeros_like(normal2), where=normal2 > 0)[:, None]
    # Barycentric coordinates of the plane projection.
    d00 = np.einsum("ij,ij->i", ab, ab)
    d01 = np.einsum("ij,ij->i", ab, ac)
    d11 = np.einsum("ij,ij->i", ac, ac)
    ap = projection-a
    d20 = np.einsum("ij,ij->i", ap, ab)
    d21 = np.einsum("ij,ij->i", ap, ac)
    denominator = d00*d11 - d01*d01
    valid = denominator > 0
    u = np.divide(d11*d20-d01*d21, denominator,
                  out=np.zeros_like(denominator), where=valid)
    v = np.divide(d00*d21-d01*d20, denominator,
                  out=np.zeros_like(denominator), where=valid)
    inside = valid & (u >= 0) & (v >= 0) & (u+v <= 1)
    candidates = [projection]
    distances = [np.where(inside, np.sum((projection-point)**2, axis=1), np.inf)]
    for start, end in ((a, b), (b, c), (c, a)):
        edge = end-start
        length2 = np.einsum("ij,ij->i", edge, edge)
        t = np.divide(np.einsum("ij,ij->i", point-start, edge), length2,
                      out=np.zeros_like(length2), where=length2 > 0)
        closest = start + np.clip(t, 0, 1)[:, None]*edge
        candidates.append(closest)
        distances.append(np.sum((closest-point)**2, axis=1))
    distances = np.asarray(distances)
    kind, index = np.unravel_index(np.argmin(distances), distances.shape)
    return float(np.sqrt(distances[kind, index])), candidates[kind][index].tolist(), int(index)


def rejection_reasons(position, direction, distance):
    """The original exporter's gates, with explicit, independent reasons."""
    point, axis = np.asarray(position), np.asarray(direction)
    reasons = []
    if point[1] < 18:
        reasons.append("below_roof_18m")
    if axis[1] >= -.05:
        reasons.append("not_downward")
    if distance > 2:
        reasons.append("lamp_distance_over_2m")
    if axis[1] < -.05:
        hit = point-axis*point[1]/axis[1]
        if abs(hit[0]) > 40 or abs(hit[2]) > 60:
            reasons.append("axis_misses_pitch_envelope")
    return reasons


def select_representatives(lights, stand_axes):
    """Pick up to three real sites per stand; never average source positions.

    Assign represented IDs within each stand, not across the pitch. Coincident
    Unity components remain evidence but do not consume additional runtime slots.
    """
    groups = {}
    for light in sorted(lights, key=lambda row: row["id"]):
        x, _, z = light["position"]
        axis = ("+x" if x > 0 else "-x") if abs(x) > abs(z) else ("+z" if z > 0 else "-z")
        groups.setdefault(stand_axes[axis], []).append(light)
    selected = []
    for stand, rows in sorted(groups.items()):
        sites = [rows[0]]
        while len(sites) < 3:
            candidate = max(rows, key=lambda row: min(np.linalg.norm(
                np.asarray(row["position"])-site["position"]) for site in sites))
            if min(np.linalg.norm(np.asarray(candidate["position"])-site["position"])
                   for site in sites) < 1e-6:
                break
            sites.append(candidate)
        for site in sites:
            representative = dict(site)
            representative["stand"] = stand
            representative["representedIds"] = [
                row["id"] for row in rows if min(sites, key=lambda s: np.linalg.norm(
                    np.asarray(row["position"])-s["position"])) is site]
            selected.append(representative)
    return selected


def calibrate_intensity(fixtures, scale):
    """HSV package calibration, always from preserved Unity values (idempotent)."""
    if isinstance(scale, bool) or not np.isfinite(scale) or not 0 < scale <= 128:
        raise ValueError("Browser scale must be finite, positive and at most 128")
    result = []
    for fixture in fixtures:
        source = fixture["sourceIntensity"]  # no silent recovery from a scaled value
        if isinstance(source, bool) or not np.isfinite(source) or source < 0:
            raise ValueError("Invalid preserved source intensity")
        result.append({**fixture, "intensity": source*scale, "browserIntensityScale": scale})
    return result
