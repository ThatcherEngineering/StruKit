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
