"""Roof snow loads: ASCE/SEI 7-22 Chapter 7.

Read from the standard (provisions pages 55 to 68; Commentary C7 for the slope-factor
equations and the worked examples):
  7.3     flat roof snow load, Eq. 7.3-1: pf = 0.7 Ce Ct pg (no importance factor in 7-22;
          the ground snow load is by Risk Category)
  Table 7.3-1   exposure factor Ce
  Tables 7.3-2, 7.3-3   thermal factor Ct (7.3-3 by roof R-value and pg, interpolated)
  7.3.3, Table 7.3-4    minimum snow load for low-slope roofs, pm
  7.4, Fig. 7.4-1       slope factor Cs; which graph applies is by Ct (Sect. 7.4.4 text):
          (a) Ct <= 1.1, (b) 1.1 < Ct < 1.2, (c) Ct >= 1.2. Graph (a) has one line for all
          surfaces. Line equations as in Commentary C7.4.
  7.6.1   unbalanced load on hip and gable roofs; drift height Eq. 7.6-1
  Eq. 7.7-1     snow density
  7.10    rain-on-snow surcharge

Covered: monoslope, hip and gable roofs. Not covered here: curved, sawtooth, dome and
air-supported roofs; partial loading of continuous members (7.5); drifts on lower roofs
and at parapets and projections (7.7, 7.8); sliding snow (7.9); ice dams at eaves (7.4.4);
ponding (7.11); the small-snow exception of 7.2.

Units: psf, ft, degrees.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import Line


class SnowError(ValueError):
    pass


CE = {  # Table 7.3-1: surface roughness -> (fully exposed, partially exposed, sheltered)
    "B": (0.9, 1.0, 1.2),
    "C": (0.9, 1.0, 1.1),
    "D": (0.8, 0.9, 1.0),
    "above the tree line": (0.7, 0.8, None),
    "Alaska, no trees within 2 mi": (0.7, 0.8, None),
}
EXPOSURES = ("fully exposed", "partially exposed", "sheltered")

CT_FIXED = {  # Table 7.3-2
    "unheated, open-air, kept just above freezing, or cold ventilated roof": 1.2,
    "freezer building": 1.3,
    "continuously heated greenhouse": 0.85,
}
HEATED = "heated, unventilated roof"
THERMAL = (HEATED,) + tuple(CT_FIXED)

CT_PG = (10, 20, 30, 40, 50, 60, 70)                 # Table 7.3-3 columns, psf
CT_TABLE = {                                         # rows by roof R-value, h ft2 F / Btu
    20: (1.20, 1.11, 1.05, 1.01, 1.00, 1.00, 1.00),
    30: (1.20, 1.17, 1.14, 1.13, 1.12, 1.11, 1.10),
    40: (1.20, 1.19, 1.17, 1.16, 1.16, 1.15, 1.15),
    50: (1.20, 1.20, 1.19, 1.19, 1.19, 1.18, 1.18),
}
PM_MAX = {"I": 25.0, "II": 30.0, "III": 35.0, "IV": 40.0}   # Table 7.3-4


def _interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1])


def ce(roughness, exposure):
    if roughness not in CE or exposure not in EXPOSURES:
        raise SnowError("snow: surface roughness or roof exposure is not one of the Table 7.3-1 choices")
    v = CE[roughness][EXPOSURES.index(exposure)]
    if v is None:
        raise SnowError(f"snow: Table 7.3-1 gives no sheltered value for '{roughness}'")
    return v


def ct(thermal, pg, r_roof=None):
    """Thermal factor and its source text."""
    if thermal in CT_FIXED:
        return CT_FIXED[thermal], "Table 7.3-2"
    if thermal != HEATED:
        raise SnowError("snow: the thermal condition is not one of the Table 7.3-2 choices")
    if r_roof is None or r_roof <= 0:
        raise SnowError("snow: a heated, unventilated roof needs its R-value (Table 7.3-3)")
    if r_roof > 50:
        return 1.2, "Table 7.3-3, note b (R-value above 50)"
    rs = sorted(CT_TABLE)
    col = [_interp(pg, CT_PG, CT_TABLE[r]) for r in rs]
    return _interp(r_roof, rs, col), "Table 7.3-3"


def cs(Ct, slope_deg, slippery):
    """Slope factor and the graph of Fig. 7.4-1 it comes from."""
    if Ct <= 1.1:
        start, graph = 30.0, "Fig. 7.4-1(a), all surfaces"
    elif Ct < 1.2:
        start, graph = (10.0, "Fig. 7.4-1(b), unobstructed slippery surface") if slippery else (37.5, "Fig. 7.4-1(b), all other surfaces")
    else:
        start, graph = (15.0, "Fig. 7.4-1(c), unobstructed slippery surface") if slippery else (45.0, "Fig. 7.4-1(c), all other surfaces")
    if slope_deg <= start:
        return 1.0, graph
    if slope_deg >= 70:
        return 0.0, graph
    return 1.0 - (slope_deg - start) / (70.0 - start), graph


def density(pg):
    return min(0.13 * pg + 14.0, 30.0)                 # Eq. 7.7-1


def drift_height(pg, lu, W2):
    return 1.5 * math.sqrt(pg ** 0.74 * lu ** 0.70 * W2 ** 1.7 / density(pg))   # Eq. 7.6-1


@dataclass
class RoofSnow:
    Ce: float
    Ct: float
    Cs: float
    pf: float
    ps: float
    pm: float                    # 0 where the minimum does not apply
    rain_on_snow: float          # 0 or 8 psf, added to the balanced case
    balanced: float              # ps plus any rain-on-snow surcharge
    uniform_design: float        # larger of the balanced case and the minimum
    unbalanced: dict             # {} or windward, leeward, surcharge, extent (psf, ft)
    slope_deg: float
    lines: list = field(default_factory=list)


def roof(pg, risk, roughness, exposure, thermal, roof_type, rise_on_12, slippery, W_ft, r_roof=None, W2=None,
         simple_members=None):
    """Snow loads on a monoslope, hip or gable roof.

    pg: ground snow load for the Risk Category (psf); risk: "I".."IV"; roof_type: "gable"
    (also hip) or "monoslope"; rise_on_12: roof rise in 12; slippery: unobstructed
    slippery surface; W_ft: horizontal eave to ridge distance (gable) or eave to upper
    edge (monoslope); W2: winter wind parameter (needed for the gable drift surcharge);
    simple_members: gable roof framed with simply supported prismatic members spanning
    from ridge to eave (7.6.1)."""
    if pg is None or pg < 0:
        raise SnowError("snow: the ground snow load must be zero or more")
    if risk not in PM_MAX:
        raise SnowError("snow: the Risk Category must be I, II, III or IV")
    if roof_type not in ("gable", "monoslope"):
        raise SnowError("snow: the roof must be gable (or hip) or monoslope")
    if rise_on_12 is None or rise_on_12 < 0:
        raise SnowError("snow: the roof rise in 12 must be zero or more")
    if W_ft is None or W_ft <= 0:
        raise SnowError("snow: the eave to ridge distance must be a positive number")
    slope = math.degrees(math.atan(rise_on_12 / 12.0))
    Ce = ce(roughness, exposure)
    Ct, ct_src = ct(thermal, pg, r_roof)
    pf = 0.7 * Ce * Ct * pg
    Cs, graph = cs(Ct, slope, slippery)
    ps = Cs * pf
    L = [Line("roof slope", slope, "deg", "geometry", f"{rise_on_12:g} on 12"),
         Line("Ce", Ce, "", "Table 7.3-1", f"surface roughness {roughness}, {exposure}"),
         Line("Ct", Ct, "", ct_src, thermal + (f", R = {r_roof:g}" if thermal == HEATED else "")),
         Line("pf = 0.7 Ce Ct pg", pf, "psf", "Eq. 7.3-1"),
         Line("Cs", Cs, "", graph),
         Line("ps = Cs pf", ps, "psf", "Eq. 7.4-1", "on the horizontal projection of the roof")]
    pm = 0.0
    if slope < 15:
        pm = pg if pg <= PM_MAX[risk] else PM_MAX[risk]
        L.append(Line("pm", pm, "psf", "Sect. 7.3.3, Table 7.3-4",
                      f"slope less than 15 deg; upper limit {PM_MAX[risk]:g} psf for Risk Category {risk}; a separate load case"))
    ros = 0.0
    if 0 < pg <= PM_MAX[risk] and slope < W_ft / 50.0:
        ros = 8.0
        L.append(Line("rain-on-snow surcharge", ros, "psf", "Sect. 7.10",
                      f"slope {slope:.2f} deg is less than W/50 = {W_ft / 50:.2f} deg; added to the balanced case only"))
    balanced = ps + ros
    L.append(Line("balanced snow load", balanced, "psf", "Sect. 7.4" + (", 7.10" if ros else "")))
    unb = {}
    if roof_type == "gable" and 2.38 <= slope <= 30.2 and pg > 0:
        if simple_members is None:
            raise SnowError("snow: say whether the roof members are simply supported prismatic members spanning from "
                            "ridge to eave (Sect. 7.6.1)")
        if W_ft <= 20 and simple_members:
            unb = dict(windward=0.0, leeward=pg, surcharge=0.0, extent=0.0)
            L.append(Line("unbalanced: leeward side", pg, "psf", "Sect. 7.6.1",
                          "W of 20 ft or less with simply supported prismatic members; windward side unloaded"))
        else:
            if W2 is None or W2 <= 0:
                raise SnowError("snow: the winter wind parameter W2 is needed for the unbalanced load (Eq. 7.6-1)")
            S = 12.0 / rise_on_12
            g = density(pg)
            hd = drift_height(pg, W_ft, W2)
            sur, ext = hd * g / math.sqrt(S), min(8 * hd * math.sqrt(S) / 3, W_ft)
            unb = dict(windward=0.3 * ps, leeward=ps, surcharge=sur, extent=ext, hd=hd, gamma=g)
            L += [Line("snow density", g, "pcf", "Eq. 7.7-1"),
                  Line("hd", hd, "ft", "Eq. 7.6-1", f"lu = W = {W_ft:g} ft, W2 = {W2:g}"),
                  Line("unbalanced: windward side, 0.3 ps", 0.3 * ps, "psf", "Sect. 7.6.1"),
                  Line("unbalanced: leeward side, ps", ps, "psf", "Sect. 7.6.1"),
                  Line("unbalanced: surcharge, hd x density / sqrt(S)", sur, "psf", "Sect. 7.6.1", f"S = {S:g}"),
                  Line("unbalanced: surcharge extent from the ridge", ext, "ft", "Sect. 7.6.1", "8 hd sqrt(S) / 3")]
    return RoofSnow(Ce, Ct, Cs, pf, ps, pm, ros, balanced, max(balanced, pm), unb, slope, L)
