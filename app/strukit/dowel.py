"""Lateral design values of dowel-type fasteners (nails, bolts), 2018 NDS Sect. 12.3.

Read from the standard (document pp. 83-85; equations and Table 12.3.1B from the page images):
  Table 12.3.1A  yield limit equations, single shear: Im Z = D lm Fem / Rd; Is Z = D ls Fes / Rd;
                 II Z = k1 D ls Fes / Rd; IIIm Z = k2 D lm Fem / [(1 + 2Re) Rd];
                 IIIs Z = k3 D ls Fem / [(2 + Re) Rd]; IV Z = (D^2 / Rd) sqrt(2 Fem Fyb / (3 (1 + Re))).
                 Double shear: Im as above; Is, IIIs and IV doubled; no II or IIIm.
                 k1, k2, k3 as in the table notes; Re = Fem / Fes; Rt = lm / ls.
  Table 12.3.1B  Rd: D from 0.25 to 1 in.: 4 Ktheta (Im, Is), 3.6 Ktheta (II), 3.2 Ktheta (IIIm,
                 IIIs, IV), Ktheta = 1 + 0.25 (theta / 90); D under 0.25 in.: KD = 2.2 for D of
                 0.17 in. or less, 10 D + 0.5 above.
  Table 12.3.3 note 2  dowel bearing strength: Fe parallel = 11,200 G; Fe perpendicular =
                 6,100 G^1.45 / sqrt(D); for D under 1/4 in. Fe = 16,600 G^1.84; the table rounds
                 to the nearest 50 psi and the rounded value is used here, as the tables do.
  Eq. 12.3-11    Fe at an angle theta to the grain (Hankinson).
  Sect. 12.3.5.3 nails: the bearing length in the main member is the penetration, less half
                 the tapered tip (E = 2D).
  Table 12N note 2  nail bending yield strength Fyb: 100,000 psi for D 0.099 to 0.142 in.;
                 90,000 to 0.177; 80,000 to 0.236; 70,000 to 0.273. Bolts 45,000 psi (Tables 12A on).
Not covered: adjustment factors (Table 11.3.1), group action, spacing and edge distances,
lag screws and wood screws (root diameter), withdrawal, steel side plates.
"""
import math


class DowelError(ValueError):
    pass


def _r50(x):
    return 50.0 * math.floor(x / 50.0 + 0.5)


def fe(G, D, theta=0.0):
    """Dowel bearing strength, psi, at theta degrees to the grain."""
    if G is None or not 0.3 <= G <= 0.75:
        raise DowelError("dowel: the specific gravity is missing or out of range")
    if D is None or D <= 0 or D > 1.0:
        raise DowelError("dowel: the diameter is over 0 and not over 1 in.")
    if D < 0.25:
        return _r50(16600.0 * G ** 1.84)
    par, perp = _r50(11200.0 * G), _r50(6100.0 * G ** 1.45 / math.sqrt(D))
    t = math.radians(theta)
    return par * perp / (par * math.sin(t) ** 2 + perp * math.cos(t) ** 2)


def nail_fyb(D):
    for top, v in ((0.142, 100000.0), (0.177, 90000.0), (0.236, 80000.0), (0.273, 70000.0)):
        if D <= top + 1e-9:
            return v
    raise DowelError("dowel: nail bending yield strength is given for diameters up to 0.273 in.")


def rd(D, mode, theta=0.0):
    if D < 0.25:
        return 2.2 if D <= 0.17 else 10.0 * D + 0.5
    k = 1.0 + 0.25 * theta / 90.0
    return {"Im": 4.0, "Is": 4.0, "II": 3.6}.get(mode, 3.2) * k


def lateral(D, ls, lm, Fes, Fem, Fyb, double=False, theta=0.0):
    """Reference lateral design value Z, lb, for one fastener: the least yield mode.
    ls, lm: dowel bearing lengths in the side and main member, in. theta: the largest angle
    of load to grain of either member (for Rd). Returns dict(Z, mode, modes)."""
    for nm, v in (("the diameter", D), ("the side member bearing length", ls), ("the main member bearing length", lm), ("Fes", Fes), ("Fem", Fem), ("Fyb", Fyb)):
        if v is None or v <= 0:
            raise DowelError(f"dowel: {nm} must be positive")
    Re, Rt = Fem / Fes, lm / ls
    k1 = (math.sqrt(Re + 2 * Re ** 2 * (1 + Rt + Rt ** 2) + Rt ** 2 * Re ** 3) - Re * (1 + Rt)) / (1 + Re)
    k2 = -1 + math.sqrt(2 * (1 + Re) + 2 * Fyb * (1 + 2 * Re) * D ** 2 / (3 * Fem * lm ** 2))
    k3 = -1 + math.sqrt(2 * (1 + Re) / Re + 2 * Fyb * (2 + Re) * D ** 2 / (3 * Fem * ls ** 2))
    R = lambda m: rd(D, m, theta)
    n = 2.0 if double else 1.0
    modes = {"Im": D * lm * Fem / R("Im"), "Is": n * D * ls * Fes / R("Is"),
             "IIIs": n * k3 * D * ls * Fem / ((2 + Re) * R("IIIs")),
             "IV": n * D ** 2 / R("IV") * math.sqrt(2 * Fem * Fyb / (3 * (1 + Re)))}
    if not double:
        modes["II"] = k1 * D * ls * Fes / R("II")
        modes["IIIm"] = k2 * D * lm * Fem / ((1 + 2 * Re) * R("IIIm"))
    mode = min(modes, key=modes.get)
    return dict(Z=modes[mode], mode=mode, modes=modes, Re=Re, Rt=Rt, k1=k1, k2=k2, k3=k3)


def nail(D, side_t, G_side, G_main, penetration=None):
    """Single shear nail, both members wood, side grain. penetration None: 10 D."""
    p = 10.0 * D if penetration is None else penetration
    if p < 6.0 * D - 1e-9:
        raise DowelError("dowel: the nail penetration into the main member is less than 6 D (Sect. 12.1.6.5)")
    lm = p - D                                              # p less E/2, E = 2D
    r = lateral(D, side_t, lm, fe(G_side, D), fe(G_main, D), nail_fyb(D))
    return dict(r, lm=lm, p=p, Fyb=nail_fyb(D))


BOLT_FYB = 45000.0


def bolt(D, side_t, main_t, G_side, G_main, theta_side=0.0, theta_main=0.0, double=False):
    """Bolt through wood members, full body diameter 1/4 to 1 in. theta: angle of load to
    grain in each member, degrees. double: two side members of side_t each."""
    if D < 0.25 or D > 1.0:
        raise DowelError("dowel: bolts from 1/4 to 1 in. diameter")
    r = lateral(D, side_t, main_t, fe(G_side, D, theta_side), fe(G_main, D, theta_main), BOLT_FYB, double, max(theta_side, theta_main))
    return dict(r, Fes=fe(G_side, D, theta_side), Fem=fe(G_main, D, theta_main), Fyb=BOLT_FYB)


def group_action(D, n, s, Es_As, Em_Am, metal=False):
    """Group action factor Cg, NDS Eq. 11.3-1, for n fasteners in a row at spacing s (in.).
    Es_As, Em_Am: E times gross area of the side member(s) and of the main member, lb.
    gamma = 180,000 D^1.5 wood to wood, 270,000 D^1.5 wood to metal. Cg = 1.0 for D under 1/4 in."""
    if n is None or n < 1 or int(n) != n:
        raise DowelError("dowel: the number of fasteners in a row is a whole number, 1 or more")
    if D < 0.25 or n == 1:
        return 1.0
    if s is None or s <= 0 or Es_As <= 0 or Em_Am <= 0:
        raise DowelError("dowel: the spacing and the member stiffnesses must be positive")
    gamma = (270000.0 if metal else 180000.0) * D ** 1.5
    u = 1.0 + gamma * s / 2.0 * (1.0 / Em_Am + 1.0 / Es_As)
    m = u - math.sqrt(u * u - 1.0)
    R = min(Es_As / Em_Am, Em_Am / Es_As)
    return min(1.0, m * (1 - m ** (2 * n)) / (n * ((1 + R * m ** n) * (1 + m) - 1 + m ** (2 * n))) * (1 + R) / (1 - m))


# ---- Geometry, load parallel to grain in every member (NDS 12.5.1; document pp. 89-91, page images) ----
# Table 12.5.1A end distance (C-delta 0.5, C-delta 1.0): compression 2D, 4D; tension, softwoods 3.5D, 7D; hardwoods 2.5D, 5D.
# Table 12.5.1B spacing in a row: minimum 3D, 4D for C-delta 1.0. Table 12.5.1C edge distance: 1.5D where l/D is 6 or
# less, otherwise the greater of 1.5D and half the row spacing. Table 12.5.1D spacing between rows: 1.5D.
# Sect. 12.5.1.3: the distance between the outermost rows not over 5 in. unless detailed for shrinkage.
END = {("tension", "softwood"): (3.5, 7.0), ("tension", "hardwood"): (2.5, 5.0), ("compression", "softwood"): (2.0, 4.0), ("compression", "hardwood"): (2.0, 4.0)}


def geometry_parallel(D, end, spacing, n_in_row, sense="tension", wood="softwood"):
    """Geometry factor for load parallel to grain: (C-delta, by end distance, by spacing).
    Raises where a distance is under the minimum for C-delta = 0.5."""
    lo, full = END[(sense, wood)]
    if end < lo * D - 1e-9:
        raise DowelError(f"dowel: the end distance {end:g} in. is less than the minimum {lo:g} D = {lo * D:g} in. (NDS Table 12.5.1A)")
    ce = min(1.0, end / (full * D))
    cs = 1.0
    if n_in_row > 1:
        if spacing is None or spacing < 3 * D - 1e-9:
            raise DowelError(f"dowel: the spacing in a row is less than the minimum 3 D = {3 * D:g} in. (NDS Table 12.5.1B)")
        cs = min(1.0, spacing / (4 * D))
    return min(ce, cs), ce, cs


def edge_minimum(D, lm, ls_total, row_spacing=None):
    """Minimum edge distance, load parallel to grain, NDS Table 12.5.1C."""
    if min(lm, ls_total) / D <= 6 or not row_spacing:
        return 1.5 * D
    return max(1.5 * D, row_spacing / 2.0)


def local_stresses(Ft, Fv, t, w, rows_n, n_row, spacing, end, row_spacing, hole):
    """Net section tension, row tear-out and group tear-out of one member at a bolted
    connection loaded in tension parallel to grain, NDS Appendix E (document pp. 164-166, page
    images), all rows alike. Ft, Fv: adjusted design values, psi. hole: bolt hole diameter.
      ZNT = Ft t (w - nrow Dh), Eq. E.2-1 and E.6; ZRTi = ni Fv t s_critical, Eq. E.3-2, with
      s_critical the lesser of the end distance and the spacing in the row; ZRT = sum of the
      rows, Eq. E.3-3; ZGT = ZRT-1 / 2 + ZRT-n / 2 + Ft t (nrow - 1)(s_row - Dh), Eq. E.4-1."""
    s_crit = end if n_row < 2 else min(end, spacing)
    ZNT = Ft * t * (w - rows_n * hole)
    row = n_row * Fv * t * s_crit
    ZRT = rows_n * row
    out = dict(s_critical=s_crit, ZNT=ZNT, ZRTi=row, ZRT=ZRT, ZGT=None)
    if rows_n > 1:
        out["ZGT"] = row / 2 + row / 2 + Ft * t * (rows_n - 1) * (row_spacing - hole)
    out["capacity"] = min(v for v in (ZNT, ZRT, out["ZGT"]) if v is not None)
    out["governs"] = "net section tension" if out["capacity"] == ZNT else "row tear-out" if out["capacity"] == ZRT else "group tear-out"
    return out


# ---- NDS Appendix Table L4: standard common, box and sinker steel wire nails: (length in., diameter in.) ----
_PENNY = ("6d", "7d", "8d", "10d", "12d", "16d", "20d", "30d", "40d", "50d", "60d")
_L4 = {"common": ((2, 0.113), (2.25, 0.113), (2.5, 0.131), (3, 0.148), (3.25, 0.148), (3.5, 0.162), (4, 0.192), (4.5, 0.207), (5, 0.225), (5.5, 0.244), (6, 0.263)),
       "box": ((2, 0.099), (2.25, 0.099), (2.5, 0.113), (3, 0.128), (3.25, 0.128), (3.5, 0.135), (4, 0.148), (4.5, 0.148), (5, 0.162), None, None),
       "sinker": ((1.875, 0.092), (2.125, 0.099), (2.375, 0.113), (2.875, 0.120), (3.125, 0.135), (3.25, 0.148), (3.75, 0.177), (4.25, 0.192), (4.75, 0.207), None, (5.75, 0.244))}
NAILS = {f"{p} {kind}": v for kind, row in _L4.items() for p, v in zip(_PENNY, row) if v}


def row_spacing_min_perp(D, l):
    """Minimum spacing between rows for a member loaded perpendicular to grain, NDS Table
    12.5.1D: 2.5 D where l/D is 2 or less, (5 l + 10 D) / 8 between, 5 D where l/D is 6 or more."""
    r = l / D
    return 2.5 * D if r <= 2 else 5.0 * D if r >= 6 else (5.0 * l + 10.0 * D) / 8.0


def geometry_perp_member(D, end_perp):
    """End distance factor of a member loaded perpendicular to grain, NDS Table 12.5.1A: 2 D minimum, 4 D for 1.0."""
    if end_perp < 2 * D - 1e-9:
        raise DowelError(f"dowel: the end distance of the member loaded perpendicular to grain, {end_perp:g} in., is less than 2 D = {2 * D:g} in. (NDS Table 12.5.1A)")
    return min(1.0, end_perp / (4 * D))
