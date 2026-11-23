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


# ---- Drifts on a lower roof and sliding snow: ASCE/SEI 7-22 Sect. 7.7.1 and 7.9 ----------
# Read from the standard (page images, text confirmed against the image):
#   7.7.1  drift loads are added to the balanced load; not required where hc / hb < 0.2
#          leeward: hd from Eq. 7.6-1 with lu = length of the upper roof, need not be over
#          0.6 x the length of the lower roof; if hd <= hc, w = 4 hd and the height is hd;
#          otherwise w = 4 hd^2 / hc and the height is hc; w not more than 8 hc
#          windward: 0.75 x Eq. 7.6-1 with lu = length of the lower roof; w = 8 x that
#          height. The surcharge height cannot exceed hc.
#          a drift wider than the lower roof tapers to zero at its far end
#          pd = hd x gamma, gamma from Eq. 7.7-1; hb = ps / gamma
#   7.9    sliding snow from a slippery upper roof steeper than 1/4 on 12, or another
#          upper roof steeper than 2 on 12: 0.4 pf W per foot of eave (pf and W of the
#          upper roof), spread over 15 ft from the eave; on a lower roof narrower than
#          15 ft the load is reduced in proportion (the same psf)
#   7.8    parapets and roof projections: the windward method of 7.7.1, height 0.75 hd
#          from Eq. 7.6-1 with lu = the roof length upwind of a parapet (for a projection,
#          the greater of the lengths upwind and downwind). Exception (read from the page
#          image): no drift where the side of a roof projection is less than 15 ft long, or
#          the clear distance between the balanced snow and the bottom of the projection
#          is at least 2 ft.
# Not covered: adjacent structures with a gap (7.7.2, 7.9), intersecting drifts (7.7.3).
@dataclass
class Drift:
    kind: str
    hd_eq: float             # height from Eq. 7.6-1 (x 0.75 for windward), before limits
    height: float            # surcharge height at the step, ft
    width: float             # ft
    pd: float                # peak surcharge, psf
    at_far_end: float        # surcharge at the far edge of the lower roof where the drift is wider than the roof, psf
    extent: float            # length loaded on the lower roof, ft


@dataclass
class LowerRoof:
    gamma: float
    hb: float
    hc: float
    required: bool
    why: str
    leeward: object
    windward: object
    governing: object
    sliding_psf: float
    sliding_extent: float
    sliding_total: float
    sliding_why: str


def lower_roof(pg, W2, ps_lower, lu_upper, lu_lower, step_ft, sliding=None, parapet=False, separation=None):
    """Drift surcharge on a lower roof at a roof step, and sliding snow from the upper
    roof. ps_lower: balanced snow load on the lower roof, psf. lu_upper, lu_lower: roof
    lengths perpendicular to the step, ft. step_ft: height of the upper roof above the
    lower roof at the step. sliding: None, or dict(pf, W, rise_on_12, slippery) for the
    upper roof draining toward the lower roof. separation: horizontal gap s, ft, between
    two adjacent structures (Sect. 7.7.2, pdf p. 126): where s is under 20 ft and under 6 h
    (h = step_ft, the vertical separation) the leeward drift on the lower structure has the
    height min(hd, (6h - s)/6) and the extent min(6 hd, 6h - s); the windward drift follows
    Sect. 7.7.1 (its permitted truncation is not taken); otherwise no drift is required."""
    if separation is not None and parapet:
        raise SnowError("snow: a gap between structures does not apply to a parapet")
    if separation is not None and separation <= 0:
        separation = None
    if parapet:
        lu_upper, sliding = lu_lower, None                  # 7.8: one drift, by the windward method, on the roof beside the parapet
    for nm, v in (("the ground snow load", pg), ("the winter wind parameter W2", W2), ("the balanced snow load on the roof", ps_lower),
                  ("the upper roof length", lu_upper), ("the roof length", lu_lower), ("the height of the step or parapet", step_ft)):
        if v is None or v <= 0:
            raise SnowError(f"snow: {nm} must be a positive number")
    g = density(pg)
    hb = ps_lower / g
    hc = step_ft - hb
    lee = wind = gov = None
    required, why = True, ""
    if hc <= 0:
        required, why = False, "the balanced snow on the lower roof reaches the upper roof"
    elif separation is not None and not (separation < 20.0 and separation < 6.0 * step_ft):
        required, why = False, ("the structures are 20 ft or more apart" if separation >= 20.0 else
                                "the gap is not less than six times the height difference") + " (Sect. 7.7.2)"
    elif hc / hb < 0.2 and separation is None:
        required, why = False, "hc / hb is less than 0.2"
    if required:
        def shape(kind, hd_eq, height, width):
            pd = height * g
            far = pd * (1 - lu_lower / width) if width > lu_lower else 0.0
            return Drift(kind, hd_eq, height, width, pd, far, min(width, lu_lower))
        h_w = 0.75 * drift_height(pg, lu_lower, W2)
        wind = shape("windward", h_w, min(h_w, hc), 8 * h_w)
        if parapet:
            gov = wind
        elif separation is not None:
            h_eq = drift_height(pg, lu_upper, W2)
            h_l = min(h_eq, (6.0 * step_ft - separation) / 6.0)
            lee = shape("leeward", h_eq, h_l, min(6.0 * h_l, 6.0 * step_ft - separation))
            gov = lee if lee.height >= wind.height else wind
        else:
            h_l = min(drift_height(pg, lu_upper, W2), 0.6 * lu_lower)
            if h_l <= hc:
                lee = shape("leeward", h_l, h_l, 4 * h_l)
            else:
                lee = shape("leeward", h_l, hc, min(4 * h_l ** 2 / hc, 8 * hc))
            gov = lee if lee.height >= wind.height else wind
    s_psf = s_ext = s_tot = 0.0
    s_why = ""
    if sliding:
        lim = 0.25 if sliding["slippery"] else 2.0
        if sliding["rise_on_12"] > lim and separation is not None and not (step_ft / separation > 1.0 and separation < 15.0):
            # Sect. 7.9, separated structures (pdf pp. 128-129): considered when h/s > 1 and s < 15 ft
            s_why = ("the gap is 15 ft or more" if separation >= 15.0 else "h / s is not over 1") + " (Sect. 7.9)"
        elif sliding["rise_on_12"] > lim:
            s_tot = 0.4 * sliding["pf"] * sliding["W"]
            reach = 15.0 - (separation or 0.0)            # separated: extent 15 - s, load per foot of eave 0.4 pf W (15 - s) / 15
            s_psf, s_ext = s_tot / 15.0, min(reach, lu_lower)
            s_tot = s_psf * s_ext
        else:
            s_why = f"upper roof slope not over {'1/4' if sliding['slippery'] else '2'} on 12"
    return LowerRoof(g, hb, hc, required, why, lee, wind, gov, s_psf, s_ext, s_tot, s_why)
