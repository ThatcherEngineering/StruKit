"""Wood structural panel diaphragms, SDPWS-2021 Sect. 4.2: unblocked, single span, simply
supported between two lines of resistance, uniformly loaded.

Read from the standard (pp. 18-19 and 27 of the document; tables read from the page images):
  Table 4.2C     nominal unit shear capacity vn (plf) and apparent shear stiffness Ga
                 (kips/in., OSB and plywood) of unblocked diaphragms, 6 in. nail spacing at
                 diaphragm boundaries and supported panel edges, for Case 1 and for Cases 2 to
                 6, by sheathing grade, common nail, panel thickness and the nominal width of
                 the nailed face (2 or 3 in.). ROWS below, all 20 rows.
  Table 4.2C note 2  specific gravity adjustment factor 1 - (0.5 - G), not over 1.
  Sect. 4.1.4    ASD: vn / 2.8 for seismic, vn / 2.0 for wind; LRFD: 0.50 vn for seismic,
                 0.80 vn for wind (shearwall.FACTORS).
  Table 4.2.2    maximum L/W: unblocked wood structural panel diaphragms 3:1.
  Table 4.2.3    mid-span deflection of a single span, uniformly loaded diaphragm,
                 Eq. 4.2-1: 5 v L^3 / (8 E A W) + 0.25 v L / (1000 Ga) + sum(x Dc) / (2 W).
Unit shear v = w L / (2 W); chord force T = C = w L^2 / (8 W) (statics).
Not covered: blocked and high load diaphragms (Tables 4.2A, 4.2B), lumber sheathed
diaphragms, cantilevered and open front diaphragms (4.2.6), openings, collectors, torsion.
"""
from .shearwall import FACTORS

# (grade, nail, thickness): {face width: (vn Case 1, Ga OSB, Ga PLY, vn Cases 2-6, Ga OSB, Ga PLY)}
ROWS = {
    ("Structural I", "6d", "5/16"): {2: (460, 9.0, 7.0, 350, 6.0, 4.5), 3: (520, 7.0, 6.0, 390, 4.5, 4.0)},
    ("Structural I", "8d", "3/8"): {2: (670, 8.5, 7.0, 505, 6.0, 4.5), 3: (740, 7.5, 6.0, 560, 5.0, 4.0)},
    ("Structural I", "10d", "15/32"): {2: (800, 14, 10, 600, 9.5, 7.0), 3: (895, 12, 9.0, 670, 8.0, 6.0)},
    ("Sheathing and Single-Floor", "6d", "5/16"): {2: (420, 9.0, 6.5, 310, 6.0, 4.0), 3: (475, 7.0, 5.5, 350, 5.0, 3.5)},
    ("Sheathing and Single-Floor", "6d", "3/8"): {2: (460, 7.5, 5.5, 350, 5.0, 4.0), 3: (520, 6.0, 4.5, 390, 4.0, 3.0)},
    ("Sheathing and Single-Floor", "8d", "3/8"): {2: (600, 9.0, 6.5, 450, 6.0, 4.5), 3: (670, 7.5, 5.5, 505, 5.0, 3.5)},
    ("Sheathing and Single-Floor", "8d", "7/16"): {2: (645, 8.5, 6.0, 475, 5.5, 4.0), 3: (715, 7.0, 5.5, 530, 4.5, 3.5)},
    ("Sheathing and Single-Floor", "8d", "15/32"): {2: (670, 7.5, 5.5, 505, 5.0, 4.0), 3: (740, 6.5, 5.0, 560, 4.0, 3.5)},
    ("Sheathing and Single-Floor", "10d", "15/32"): {2: (715, 15, 9.0, 530, 10, 6.0), 3: (810, 12, 8.0, 600, 8.0, 5.5)},
    ("Sheathing and Single-Floor", "10d", "19/32"): {2: (800, 13, 8.5, 600, 8.5, 5.5), 3: (895, 10, 7.5, 670, 7.0, 5.0)},
}
PANELS = [f"{g}, {t} in, {n} common" for (g, n, t) in ROWS]
MAX_RATIO_UNBLOCKED = 3.0


class DiaphragmError(ValueError):
    pass


def row(panel):
    for (g, n, t), v in ROWS.items():
        if panel == f"{g}, {t} in, {n} common":
            return (g, n, t), v
    raise DiaphragmError("diaphragm: the sheathing and nail choice is not a row of SDPWS Table 4.2C")


def unblocked(panel, face_in, case, panel_type, G, L, W, w, load, method, chord_E=None, chord_A=None, splice=()):
    """L: span between the lines of resistance, ft; W: diaphragm width (depth) parallel to
    the load, ft; w: uniform load on the diaphragm, plf, at the level of `method`.
    case: 1, or 2 for Cases 2 to 6. splice: [(x ft from the nearest support, slip in)]."""
    key, r = row(panel)
    if face_in not in (2, 3):
        raise DiaphragmError("diaphragm: the nominal width of the nailed face is 2 or 3 in.")
    if case not in (1, 2):
        raise DiaphragmError("diaphragm: the case is 1, or 2 for Cases 2 to 6")
    if panel_type not in ("OSB", "plywood"):
        raise DiaphragmError("diaphragm: the panel is OSB or plywood")
    if G is None or not 0.3 <= G <= 0.75:
        raise DiaphragmError("diaphragm: the specific gravity of the framing is missing or out of range")
    for nm, v in (("the span", L), ("the width", W), ("the load", w)):
        if v is None or v <= 0:
            raise DiaphragmError(f"diaphragm: {nm} must be positive")
    if (load, method) not in FACTORS:
        raise DiaphragmError("diaphragm: the load is wind or seismic and the method ASD or LRFD")
    t = r[face_in]
    i = 0 if case == 1 else 3
    vn_tab, Ga = t[i], t[i + (1 if panel_type == "OSB" else 2)]
    sg = min(1.0, 1.0 - (0.5 - G))
    txt, fac = FACTORS[(load, method)]
    vn = vn_tab * sg
    cap = vn * fac
    v = w * L / (2.0 * W)
    T = w * L * L / (8.0 * W)
    out = dict(key=key, vn_table=vn_tab, Ga=Ga, sg=sg, vn=vn, factor_text=txt, factor=fac, capacity=cap, v=v, reaction=w * L / 2.0, chord=T,
               ratio=L / W, ratio_max=MAX_RATIO_UNBLOCKED, defl=None)
    if chord_E and chord_A:
        b = 5.0 * v * L ** 3 / (8.0 * chord_E * chord_A * W)
        s = 0.25 * v * L / (1000.0 * Ga)
        c = sum(x * d for x, d in splice) / (2.0 * W)
        out.update(defl=b + s + c, defl_bending=b, defl_shear=s, defl_splice=c)
    return out
