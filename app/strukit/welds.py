"""Fillet welds.

Source on file: ANSI/AISC 360-22 Section J2 (J2.2a, J2.2b, J2.4, Tables J2.4 and J2.5).
Covered: fillet weld rupture strength on a linear weld group (Eq. J2-4), directional
strength increase (Eq. J2-5), end-loaded length reduction (Eq. J2-1), minimum and
maximum weld size, minimum length, and the base-metal shear rupture check of Eq. J2-2.
Not covered: groove, plug and slot welds; eccentrically loaded weld groups
(instantaneous center); fatigue; AWS D1.1 prequalification and matching filler metal.

Units: kip, inch, ksi, degrees.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import Line, SteelInputError


@dataclass
class WeldResult:
    Rn: float
    R_avail: float
    governs: str
    flags: list = field(default_factory=list)
    lines: list = field(default_factory=list)


def min_fillet_size(t_thinner):
    """Minimum fillet weld leg, AISC 360-22 Table J2.4, by the thinner part joined."""
    if t_thinner <= 0.25:
        return 1 / 8
    if t_thinner <= 0.5:
        return 3 / 16
    if t_thinner <= 0.75:
        return 1 / 4
    return 5 / 16


def max_fillet_size(t_edge):
    """Maximum fillet weld leg along an edge, AISC 360-22 J2.2b(b)."""
    return t_edge if t_edge < 0.25 else t_edge - 1 / 16


def fillet(size, length, n_lines, FEXX, theta_deg=0.0, directional=True, end_loaded=False,
           t_thinner=None, t_edge=None, base_t=None, base_Fu=None, method="ASD"):
    """Strength of n_lines equal, parallel fillet welds of leg `size` and `length` each.

    theta_deg is the angle between the load and the weld axis. directional=True applies
    Eq. J2-5 (valid for a linear weld group of uniform size loaded through its center of
    gravity; see the J2.4 User Note). end_loaded applies J2.2b(d). t_thinner turns on the
    Table J2.4 minimum size check, t_edge the J2.2b(b) maximum. base_t with base_Fu adds
    the base metal shear rupture check of Eq. J2-2 (per weld line, 0.60 Fu t).
    """
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("weld: method must be ASD or LRFD")
    if size <= 0 or length <= 0 or n_lines <= 0 or FEXX <= 0:
        raise SteelInputError("weld: size, length, number of lines and FEXX must be positive")
    if not 0 <= theta_deg <= 90:
        raise SteelInputError("weld: theta must be between 0 and 90 degrees")
    if (base_t is None) != (base_Fu is None):
        raise SteelInputError("weld: give both base_t and base_Fu, or neither")
    L, flags = [], []

    w_eff = size
    if length < 4 * size:                                        # J2.2b(c)
        w_eff = length / 4
        flags.append(f"length {length:.2f} in is less than 4 x weld size; effective size "
                     f"taken as length/4 = {w_eff:.3f} in (J2.2b(c))")
    if t_thinner is not None and size < min_fillet_size(t_thinner):
        flags.append(f"weld size {size:.4f} in is below the Table J2.4 minimum "
                     f"{min_fillet_size(t_thinner):.4f} in for a {t_thinner:.3f} in part")
    if t_edge is not None and size > max_fillet_size(t_edge) + 1e-9:
        flags.append(f"weld size {size:.4f} in exceeds the J2.2b(b) maximum "
                     f"{max_fillet_size(t_edge):.4f} in along a {t_edge:.3f} in edge")

    beta, l_eff = 1.0, length
    if end_loaded:                                               # J2.2b(d)
        ratio = length / size
        if ratio > 300:
            l_eff = 180 * size
            L.append(Line("effective length", l_eff, "in", "J2.2b(d)(3)", "l/w > 300: 180 w"))
        elif ratio > 100:
            beta = min(1.2 - 0.002 * ratio, 1.0)
            l_eff = beta * length
            L.append(Line("beta", beta, "", "Eq. J2-1", f"l/w = {ratio:.0f}"))
    kds = 1.0 + 0.50 * math.sin(math.radians(theta_deg)) ** 1.5 if directional else 1.0
    L.append(Line("kds", kds, "", "Eq. J2-5" if directional else "J2.4(a)(3)",
                  f"theta = {theta_deg:.0f} deg"))
    throat = w_eff / math.sqrt(2)                                # J2.2a, equal-leg fillet
    r_per_in = 0.60 * FEXX * throat * kds
    L.append(Line("Rn per inch, one line", r_per_in, "kip/in",
                  "Eq. J2-4; Fnw = 0.60 FEXX (Table J2.5); throat = w / sqrt(2) (J2.2a)"))
    Rn_weld = r_per_in * l_eff * n_lines
    cands = {"weld metal rupture (Eq. J2-4)": Rn_weld}
    L.append(Line("Rn, weld metal", Rn_weld, "kip", "Eq. J2-4", f"{n_lines} line(s) x {l_eff:.2f} in"))
    if base_t is not None:
        Rn_bm = 0.60 * base_Fu * base_t * length * n_lines
        cands["base metal shear rupture (Eq. J2-2)"] = Rn_bm
        L.append(Line("Rn, base metal", Rn_bm, "kip", "Eq. J2-2; FnBM = 0.60 Fu (J4.2)"))
    governs = min(cands, key=cands.get)
    Rn = cands[governs]
    R_avail = 0.75 * Rn if method == "LRFD" else Rn / 2.00
    L.append(Line("phi Rn" if method == "LRFD" else "Rn / Omega", R_avail, "kip",
                  "Table J2.5: phi = 0.75, Omega = 2.00", f"governs: {governs}"))
    return WeldResult(Rn, R_avail, governs, flags, L)
