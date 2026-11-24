"""Bolts in bearing-type connections.

Source on file: ANSI/AISC 360-22 Section J3 (Tables J3.2 and J3.3; J3.7, J3.8, J3.11a).
Covered: bolt shear and tension rupture (Eq. J3-1), combined tension and shear
(Eq. J3-2, J3-3a/b), bearing and tearout at standard holes (Eq. J3-6a to J3-6d), and
the strength of a bolt line as the sum of each bolt's effective strength (J3.7 User Note).
Not covered: slip-critical connections (J3.9, J3.10), long-slotted holes, prying action,
block shear and the other connected-element checks of J4, eccentric bolt groups,
bolt spacing and edge distance limits (J3.3 to J3.6), the 38 in pattern length reduction.

Units: kip, inch, ksi.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import Line, SteelInputError

# AISC 360-22 Table J3.2: Fnt, Fnv threads not excluded (N), Fnv threads excluded (X)
TABLE_J3_2 = {
    "A307": (45.0, 27.0, 27.0),
    "GROUP 120": (90.0, 54.0, 68.0),      # e.g. A325
    "GROUP 144": (108.0, 65.0, 81.0),     # e.g. F3148
    "GROUP 150": (113.0, 68.0, 84.0),     # e.g. A490
}
ALIASES = {"A325": "GROUP 120", "F1852": "GROUP 120", "A490": "GROUP 150", "F2280": "GROUP 150",
           "F3148": "GROUP 144"}
PHI, OMEGA = 0.75, 2.00


@dataclass
class BoltResult:
    Rn: float
    R_avail: float
    governs: str = ""
    lines: list = field(default_factory=list)


def _group(name):
    key = str(name).upper().strip()
    if key.startswith("FU="):                       # threaded part (anchor rod) of the given Fu, Table J3.2 last row
        try:
            Fu = float(key[3:])
        except ValueError:
            raise SteelInputError(f"bolt: cannot read the tensile strength in '{name}'")
        if Fu <= 0:
            raise SteelInputError("bolt: the tensile strength Fu must be positive")
        return f"threaded part, Fu = {Fu:g} ksi", (0.75 * Fu, 0.450 * Fu, 0.563 * Fu)
    key = ALIASES.get(key, key)
    if key not in TABLE_J3_2:
        raise SteelInputError(f"bolt: '{name}' is not in Table J3.2 as loaded "
                              f"({', '.join(TABLE_J3_2)})")
    return key, TABLE_J3_2[key]


def _avail(Rn, method):
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("bolt: method must be ASD or LRFD")
    return PHI * Rn if method == "LRFD" else Rn / OMEGA


def area(d):
    """Nominal unthreaded body area, in^2 (J3.7 definition of Ab)."""
    return math.pi * d ** 2 / 4


def standard_hole(d):
    """Standard hole diameter, AISC 360-22 Table J3.3."""
    if d < 0.5:
        raise SteelInputError("bolt: Table J3.3 starts at 1/2 in diameter")
    return d + 1 / 16 if d < 1.0 else d + 1 / 8


def shear(d, group, threads="N", planes=1, method="ASD"):
    """Shear rupture of one bolt. Eq. J3-1 with Fnv from Table J3.2."""
    if threads not in ("N", "X"):
        raise SteelInputError("bolt: threads must be N (not excluded) or X (excluded)")
    key, (Fnt, FnvN, FnvX) = _group(group)
    Fnv = FnvN if threads == "N" else FnvX
    Rn = Fnv * area(d) * planes
    lines = [Line("Rn = Fnv Ab", Rn, "kip", "Eq. J3-1; Table J3.2",
                  f"{key}, threads {threads}, Fnv = {Fnv:.0f} ksi, Ab = {area(d):.3f} in^2, "
                  f"{planes} shear plane(s)")]
    return BoltResult(Rn, _avail(Rn, method), "bolt shear rupture (J3.7)", lines)


def tension(d, group, method="ASD"):
    """Tension rupture of one bolt. Eq. J3-1 with Fnt from Table J3.2."""
    key, (Fnt, _, _) = _group(group)
    Rn = Fnt * area(d)
    return BoltResult(Rn, _avail(Rn, method), "bolt tension rupture (J3.7)",
                      [Line("Rn = Fnt Ab", Rn, "kip", "Eq. J3-1; Table J3.2", f"{key}, Fnt = {Fnt:.0f} ksi")])


def tension_with_shear(d, group, V_req, threads="N", planes=1, method="ASD"):
    """Available tension of one bolt that also carries shear V_req (required, for the
    chosen method). Eq. J3-2 with Fnt' from Eq. J3-3a (LRFD) or J3-3b (ASD)."""
    key, (Fnt, FnvN, FnvX) = _group(group)
    Fnv = FnvN if threads == "N" else FnvX
    frv = V_req / (area(d) * planes)
    fv_avail = _avail(Fnv, method)
    if frv > fv_avail:
        raise SteelInputError(f"bolt: required shear stress {frv:.1f} ksi exceeds the available "
                              f"{fv_avail:.1f} ksi (J3.7); combined check not applicable")
    Fnt_p = min(1.3 * Fnt - Fnt / fv_avail * frv, Fnt)
    Rn = Fnt_p * area(d)
    lines = [Line("frv", frv, "ksi", "J3.8", f"available {fv_avail:.1f} ksi"),
             Line("Fnt'", Fnt_p, "ksi", "Eq. J3-3a" if method == "LRFD" else "Eq. J3-3b"),
             Line("Rn = Fnt' Ab", Rn, "kip", "Eq. J3-2")]
    return BoltResult(Rn, _avail(Rn, method), "combined tension and shear (J3.8)", lines)


def hole(d, t, Fu, lc, deformation=True, method="ASD"):
    """Bearing and tearout of one connected element at one bolt, standard hole.
    lc is the clear distance, in the direction of force, from the edge of the hole to
    the edge of the next hole or of the material. deformation=True means deformation at
    the hole at service load is a design consideration (Eq. J3-6a, J3-6c)."""
    if min(d, t, Fu) <= 0 or lc < 0:
        raise SteelInputError("bolt: d, t and Fu must be positive and lc not negative")
    kb, kt = (2.4, 1.2) if deformation else (3.0, 1.5)
    bearing, tearout = kb * d * t * Fu, kt * lc * t * Fu
    eb, et = ("Eq. J3-6a", "Eq. J3-6c") if deformation else ("Eq. J3-6b", "Eq. J3-6d")
    lines = [Line("Rn, bearing", bearing, "kip", eb), Line("Rn, tearout", tearout, "kip", et,
                                                           f"lc = {lc:.3f} in")]
    governs = "bearing (J3.11a)" if bearing <= tearout else "tearout (J3.11a)"
    Rn = min(bearing, tearout)
    return BoltResult(Rn, _avail(Rn, method), governs, lines)


def bolt_line(d, group, n, spacing, edge, plies, threads="N", planes=1, deformation=True,
              method="ASD"):
    """Strength of a line of n bolts loaded along the line, toward the edge.

    plies: list of (t, Fu, has_edge) or (t, Fu, has_edge, count) for each connected
    element. has_edge=True means the end bolt bears toward a free edge at distance `edge`
    (bolt center to edge) in that element; False means there is no edge in the load
    direction (e.g. a beam web), so every bolt uses the clear distance between holes.
    count is the number of identical elements sharing the bolt force on that side (2 for
    a pair of angles on a web in double shear); their strength is multiplied by it.
    Each bolt's effective strength is the least of its shear strength and the bearing or
    tearout strength of every ply at that bolt; the line is the sum (J3.7 User Note)."""
    if n < 1:
        raise SteelInputError("bolt: at least one bolt")
    dh = standard_hole(d)
    v = shear(d, group, threads, planes, method).Rn
    total, lines, limits = 0.0, [], []
    for i in range(n):
        end_bolt = (i == 0)
        cands = {"bolt shear": v}
        for j, ply in enumerate(plies, 1):
            t, Fu, has_edge = ply[:3]
            count = ply[3] if len(ply) > 3 else 1
            if end_bolt and has_edge:
                lc = edge - dh / 2
            elif n == 1 and not has_edge:
                continue                    # single bolt, no edge: bearing only
            else:
                lc = spacing - dh
            h = hole(d, t, Fu, lc, deformation, method)
            cands[f"ply {j} {h.governs.split(' ')[0]}"] = h.Rn * count
        lim = min(cands, key=cands.get)
        total += cands[lim]
        limits.append(lim)
        lines.append(Line(f"bolt {i + 1} effective Rn", cands[lim], "kip", "J3.7 User Note",
                          f"limited by {lim}"))
    return BoltResult(total, _avail(total, method), ", ".join(sorted(set(limits))), lines)


# Minimum edge distance from the centre of a standard hole, AISC 360-22 Table J3.4, in.
TABLE_J3_4 = {0.5: 0.75, 0.625: 0.875, 0.75: 1.0, 0.875: 1.125, 1.0: 1.25, 1.125: 1.5, 1.25: 1.625}


def min_edge(d):
    """Table J3.4; over 1-1/4 in.: 1.25 d."""
    if d > 1.25:
        return 1.25 * d
    if d not in TABLE_J3_4:
        raise SteelInputError(f"bolt: no Table J3.4 edge distance for a {d:g} in. bolt")
    return TABLE_J3_4[d]


def group_coefficient(n, spacing, e):
    """Coefficient C for one vertical row of n bolts at the given spacing carrying a vertical force at eccentricity e from the row
    (AISC Manual Table 7-6, angle 0): available strength of the group = C x the strength of one bolt.  Instantaneous centre of rotation
    method, AISC Manual Part 7: bolt force R = Rult (1 - exp(-10 delta))^0.55, delta = 0.34 in. at the bolt farthest from the centre.
    Reproduces the tabulated values quoted in the AISC Design Examples v16 and Design Guide 24 (see the tests)."""
    import math
    if n < 1 or spacing <= 0 or e < 0:
        raise SteelInputError("bolt group: need at least one bolt, a positive spacing and an eccentricity of zero or more")
    if e == 0 or n == 1:
        return float(n) if e == 0 else 0.0 if n == 1 and e > 0 else float(n)
    ys = [(i - (n - 1) / 2) * spacing for i in range(n)]

    def forces(r0):
        ds = [math.hypot(r0, y) for y in ys]
        dm = max(ds)
        R = [(1 - math.exp(-10 * 0.34 * d / dm)) ** 0.55 for d in ds]
        Pv = sum(r * r0 / d for r, d in zip(R, ds))            # vertical equilibrium
        Pm = sum(r * d for r, d in zip(R, ds)) / (e + r0)      # moment about the instantaneous centre
        return Pv, Pm
    lo, hi = 1e-6, 1e4
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        Pv, Pm = forces(mid)
        if Pv < Pm:
            lo = mid
        else:
            hi = mid
    return sum(forces(math.sqrt(lo * hi))) / 2
