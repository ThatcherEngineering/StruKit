"""Rolled I-shape columns that also carry sideways (lateral) load: the pieces needed
beyond axial compression (steel_column.py) and strong-axis bending and shear
(steel_beam.py).

Source on file: ANSI/AISC 360-22.
  F6          bending about the weak (minor) axis
  G1, G2.2, G6  shear from weak-axis loading, carried by the two flanges
  App. 8.1.2  B1 multiplier for the extra moment caused by axial load acting on the
              bowed column (P-delta effect), for a column whose ends do not move
              sideways
  H1.1        combined compression and bending, Eq. H1-1a and H1-1b

Not covered here: columns whose top can move sideways (cantilevered or moment-frame
columns); they need the B2 multiplier of App. 8.1.3 and the stability rules of
Chapter C / Appendix 7.

Units: kips, inches, ksi.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import E_STEEL, Line, SteelInputError


@dataclass
class Strength:
    nominal: float
    available: float
    governs: str
    lines: list = field(default_factory=list)


def weak_axis_flexure(props, Fy, method="ASD", E=E_STEEL):
    """Mn and available strength for bending about the y axis. AISC 360-22 Sect. F6."""
    p = props
    for k in ("Zy", "Sy"):
        if p.get(k) in (None, ""):
            raise SteelInputError(f"steel column: missing section property {k}")
    rt = math.sqrt(E / Fy)
    lam = p["bf_2tf"] if p.get("bf_2tf") else p["bf"] / (2 * p["tf"])
    lam_p, lam_r = 0.38 * rt, 1.0 * rt
    L = [Line("flange bf/2tf (weak-axis bending)", lam, "", "Table B4.1b Case 13",
              f"compact limit {lam_p:.2f}, noncompact limit {lam_r:.2f}")]
    Mp = min(Fy * p["Zy"], 1.6 * Fy * p["Sy"])
    L.append(Line("Mpy = Fy Zy <= 1.6 Fy Sy", Mp, "kip-in", "Eq. F6-1"))
    if lam <= lam_p:
        Mn, gov = Mp, "yielding (F6.1)"
    elif lam <= lam_r:
        Mn = Mp - (Mp - 0.70 * Fy * p["Sy"]) * (lam - lam_p) / (lam_r - lam_p)
        gov = "flange local buckling, noncompact flange (F6.2(b))"
        L.append(Line("Mny, flange local buckling", Mn, "kip-in", "Eq. F6-2"))
    else:
        Fcr = 0.70 * E / lam ** 2
        Mn = Fcr * p["Sy"]
        gov = "flange local buckling, slender flange (F6.2(c))"
        L.append(Line("Fcr", Fcr, "ksi", "Eq. F6-4"))
        L.append(Line("Mny, flange local buckling", Mn, "kip-in", "Eq. F6-3"))
    avail = 0.90 * Mn if method == "LRFD" else Mn / 1.67
    L.append(Line("phi_b Mny" if method == "LRFD" else "Mny / Omega_b", avail, "kip-in",
                  "Sect. F1(a): phi_b = 0.90, Omega_b = 1.67", f"governs: {gov}"))
    return Strength(Mn, avail, gov, L)


def weak_axis_shear(props, Fy, method="ASD", E=E_STEEL):
    """Shear strength for load applied in the weak direction (parallel to the flanges).
    AISC 360-22 Sect. G6: each flange is a shear-resisting element; an I-shape has two."""
    p = props
    lam = p["bf_2tf"] if p.get("bf_2tf") else p["bf"] / (2 * p["tf"])
    kv = 1.2
    lim1, lim2 = 1.10 * math.sqrt(kv * E / Fy), 1.37 * math.sqrt(kv * E / Fy)
    if lam <= lim1:
        cv2, src = 1.0, "Eq. G2-9"
    elif lam <= lim2:
        cv2, src = lim1 / lam, "Eq. G2-10"
    else:
        cv2, src = 1.51 * kv * E / (lam ** 2 * Fy), "Eq. G2-11"
    Vn = 2 * 0.6 * Fy * p["bf"] * p["tf"] * cv2
    avail = 0.90 * Vn if method == "LRFD" else Vn / 1.67
    L = [Line("Cv2 (flanges, kv = 1.2)", cv2, "", src, f"bf/2tf = {lam:.2f}, limit {lim1:.1f}"),
         Line("Vny = 2 x 0.6 Fy bf tf Cv2", Vn, "kip", "Eq. G6-1, two flanges"),
         Line("phi_v Vny" if method == "LRFD" else "Vny / Omega_v", avail, "kip",
              "Sect. G1(a): phi_v = 0.90, Omega_v = 1.67")]
    return Strength(Vn, avail, "shear in the flanges (G6)", L)


def b1(Pr, I, Lc1, method="ASD", Cm=1.0, E=E_STEEL):
    """B1 multiplier, Eq. A-8-3, with Pe1 from Eq. A-8-5 using EI (effective length
    method). Pr is the first-order axial load, as App. 8.1.2 permits. Cm = 1.0 is the
    conservative value 8.1.2(b) allows for members with load between their supports.
    Returns (B1, Pe1)."""
    Pe1 = math.pi ** 2 * E * I / Lc1 ** 2
    alpha = 1.0 if method == "LRFD" else 1.6
    if alpha * Pr >= Pe1:
        raise SteelInputError(
            f"steel column: the axial load ({alpha:g} x {Pr:.1f} kips) reaches the elastic "
            f"buckling load in the plane of bending (Pe1 = {Pe1:.1f} kips). The column is unstable.")
    return max(Cm / (1 - alpha * Pr / Pe1), 1.0), Pe1


def interaction(Pr, Pc, Mrx, Mcx, Mry=0.0, Mcy=None):
    """Combined compression and bending, AISC 360-22 Eq. H1-1a / H1-1b.
    Returns (value, equation name); the limit is 1.0."""
    my = (abs(Mry) / Mcy) if Mcy else 0.0
    if Mry and not Mcy:
        raise SteelInputError("steel column: weak-axis moment given without its strength")
    r = abs(Pr) / Pc
    if r >= 0.2:
        return r + 8.0 / 9.0 * (abs(Mrx) / Mcx + my), "Eq. H1-1a"
    return r / 2 + (abs(Mrx) / Mcx + my), "Eq. H1-1b"
