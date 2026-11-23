"""Wood structural panel diaphragms, SDPWS-2021 Sect. 4.2: unblocked and blocked, single
span, simply supported between two lines of resistance, uniformly loaded.

Read from the standard (pp. 18-19 and 27 of the document; tables read from the page images):
  Table 4.2C     nominal unit shear capacity vn (plf) and apparent shear stiffness Ga
                 (kips/in., OSB and plywood) of unblocked diaphragms, 6 in. nail spacing at
                 diaphragm boundaries and supported panel edges, for Case 1 and for Cases 2 to
                 6, by sheathing grade, common nail, panel thickness and the nominal width of
                 the nailed face (2 or 3 in.). ROWS below, all 20 rows.
  Table 4.2A     blocked diaphragms (document p. 25, read from a 330 dpi page image): vn and Ga
                 for nail spacing at diaphragm boundaries (all cases), at continuous panel edges
                 parallel to the load (Cases 3 and 4) and at all panel edges (Cases 5 and 6) of
                 6, 4, 2-1/2 and 2 in., with 6, 6, 4 and 3 in. at the other panel edges (Cases
                 1 to 4). BLOCKED below, all 20 rows. Sect. 4.2.8.1.1 item 3: where the spacing
                 is 2-1/2 in. or less (or 10d nails at 3 in.), framing and blocking at adjoining
                 panel edges 3 in. nominal with staggered nails.
  Table 4.2C note 2  specific gravity adjustment factor 1 - (0.5 - G), not over 1.
  Sect. 4.1.4    ASD: vn / 2.8 for seismic, vn / 2.0 for wind; LRFD: 0.50 vn for seismic,
                 0.80 vn for wind (shearwall.FACTORS).
  Table 4.2.2    maximum L/W: wood structural panel diaphragms, unblocked 3:1, blocked 4:1.
  Table 4.2.3    mid-span deflection of a single span, uniformly loaded diaphragm,
                 Eq. 4.2-1: 5 v L^3 / (8 E A W) + 0.25 v L / (1000 Ga) + sum(x Dc) / (2 W).
Unit shear v = w L / (2 W); chord force T = C = w L^2 / (8 W) (statics).
Not covered: high load diaphragms (Table 4.2B), lumber sheathed
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
# Blocked, Table 4.2A: (grade, nail, thickness): {face width: {boundary nail spacing: (vn, Ga OSB, Ga PLY)}}
def _b(*v):
    return {6: v[0:3], 4: v[3:6], 2.5: v[6:9], 2: v[9:12]}


BLOCKED = {
    ("Structural I", "6d", "5/16"): {2: _b(520, 15, 12, 700, 8.5, 7.5, 1050, 12, 10, 1175, 20, 15), 3: _b(590, 12, 9.5, 785, 7.0, 6.0, 1175, 9.5, 8.5, 1330, 17, 13)},
    ("Structural I", "8d", "3/8"): {2: _b(755, 14, 11, 1010, 9.0, 7.5, 1485, 13, 10, 1680, 21, 15), 3: _b(840, 12, 10, 1120, 7.5, 6.5, 1680, 10, 9.0, 1890, 18, 13)},
    ("Structural I", "10d", "15/32"): {2: _b(895, 24, 17, 1190, 15, 12, 1790, 20, 15, 2045, 31, 21), 3: _b(1010, 20, 15, 1345, 12, 9.5, 2015, 16, 13, 2295, 26, 18)},
    ("Sheathing and Single-Floor", "6d", "5/16"): {2: _b(475, 15, 10, 630, 9.0, 7.0, 940, 13, 9.5, 1065, 21, 13), 3: _b(530, 12, 9.0, 700, 7.0, 6.0, 1065, 10, 8.0, 1205, 17, 12)},
    ("Sheathing and Single-Floor", "6d", "3/8"): {2: _b(520, 13, 9.5, 700, 7.0, 6.0, 1050, 10, 8.0, 1175, 18, 12), 3: _b(590, 10, 8.0, 785, 5.5, 5.0, 1175, 8.5, 7.0, 1330, 14, 10)},
    ("Sheathing and Single-Floor", "8d", "3/8"): {2: _b(670, 15, 11, 895, 9.5, 7.5, 1345, 13, 9.5, 1525, 21, 13), 3: _b(755, 12, 9.5, 1010, 7.5, 6.0, 1510, 11, 8.5, 1710, 18, 12)},
    ("Sheathing and Single-Floor", "8d", "7/16"): {2: _b(715, 14, 10, 950, 8.5, 7.0, 1415, 12, 9.5, 1610, 20, 13), 3: _b(800, 11, 9.0, 1065, 7.0, 6.0, 1595, 10, 8.0, 1805, 17, 12)},
    ("Sheathing and Single-Floor", "8d", "15/32"): {2: _b(755, 13, 9.5, 1010, 7.5, 6.5, 1485, 11, 8.5, 1680, 19, 13), 3: _b(840, 10, 8.5, 1120, 6.0, 5.5, 1680, 9.0, 7.5, 1890, 15, 11)},
    ("Sheathing and Single-Floor", "10d", "15/32"): {2: _b(810, 25, 15, 1080, 15, 11, 1610, 21, 14, 1835, 33, 18), 3: _b(910, 21, 14, 1205, 12, 9.5, 1820, 17, 12, 2060, 28, 16)},
    ("Sheathing and Single-Floor", "10d", "19/32"): {2: _b(895, 21, 14, 1190, 13, 9.5, 1790, 18, 12, 2045, 28, 17), 3: _b(1010, 17, 12, 1345, 10, 8.0, 2015, 14, 11, 2295, 24, 15)},
}
OTHER_EDGES = {6: 6, 4: 6, 2.5: 4, 2: 3}                 # nail spacing at the other panel edges, Cases 1 to 4
MAX_RATIO_BLOCKED = 4.0
PANELS = [f"{g}, {t} in, {n} common" for (g, n, t) in ROWS]
MAX_RATIO_UNBLOCKED = 3.0


class DiaphragmError(ValueError):
    pass


def row(panel):
    for (g, n, t), v in ROWS.items():
        if panel == f"{g}, {t} in, {n} common":
            return (g, n, t), v
    raise DiaphragmError("diaphragm: the sheathing and nail choice is not a row of SDPWS Table 4.2C")


def blocked(panel, face_in, spacing, panel_type, G, L, W, w, load, method, chord_E=None, chord_A=None, splice=()):
    """Blocked diaphragm, Table 4.2A. spacing: nail spacing at the boundaries, 6, 4, 2.5 or 2 in."""
    key, _ = row(panel)
    if face_in not in (2, 3):
        raise DiaphragmError("diaphragm: the nominal width of the nailed face is 2 or 3 in.")
    if spacing not in OTHER_EDGES:
        raise DiaphragmError("diaphragm: the boundary nail spacing of a blocked diaphragm is 6, 4, 2-1/2 or 2 in.")
    vn_tab, g_osb, g_ply = BLOCKED[key][face_in][spacing]
    return _design(key, vn_tab, g_osb, g_ply, MAX_RATIO_BLOCKED, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice)


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
    return _design(key, t[i], t[i + 1], t[i + 2], MAX_RATIO_UNBLOCKED, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice)


def _design(key, vn_tab, g_osb, g_ply, ratio_max, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice):
    if panel_type not in ("OSB", "plywood"):
        raise DiaphragmError("diaphragm: the panel is OSB or plywood")
    if G is None or not 0.3 <= G <= 0.75:
        raise DiaphragmError("diaphragm: the specific gravity of the framing is missing or out of range")
    for nm, v in (("the span", L), ("the width", W), ("the load", w)):
        if v is None or v <= 0:
            raise DiaphragmError(f"diaphragm: {nm} must be positive")
    if (load, method) not in FACTORS:
        raise DiaphragmError("diaphragm: the load is wind or seismic and the method ASD or LRFD")
    Ga = g_osb if panel_type == "OSB" else g_ply
    sg = min(1.0, 1.0 - (0.5 - G))
    txt, fac = FACTORS[(load, method)]
    vn = vn_tab * sg
    cap = vn * fac
    v = w * L / (2.0 * W)
    T = w * L * L / (8.0 * W)
    out = dict(key=key, vn_table=vn_tab, Ga=Ga, sg=sg, vn=vn, factor_text=txt, factor=fac, capacity=cap, v=v, reaction=w * L / 2.0, chord=T,
               ratio=L / W, ratio_max=ratio_max, defl=None)
    if chord_E and chord_A:
        b = 5.0 * v * L ** 3 / (8.0 * chord_E * chord_A * W)
        s = 0.25 * v * L / (1000.0 * Ga)
        c = sum(x * d for x, d in splice) / (2.0 * W)
        out.update(defl=b + s + c, defl_bending=b, defl_shear=s, defl_splice=c)
    return out


def collector(W, R, segments):
    """Axial force along a collector (drag strut) on a line of resistance. W: length of the line
    (the diaphragm dimension along it), ft; R: force the diaphragm delivers to the line, lb, taken
    as uniform along the line (vd = R / W); segments: [(start ft, length ft)] of the wall or frame
    lengths on the line, which take R in proportion to their length (vw = R / sum of lengths).
    The force at x is the running sum of (vd - vw inside a segment); it is zero at both ends.
    Returns dict(vd, vw, Lw, points [(x, F)], Fmax, x_max). The sign of F reverses with the load."""
    if W is None or W <= 0 or R is None or R <= 0:
        raise DiaphragmError("collector: the line length and the force on the line must be positive")
    segs = sorted((float(a), float(b)) for a, b in segments)
    if not segs:
        raise DiaphragmError("collector: enter at least one wall length on the line")
    end = 0.0
    for a, b in segs:
        if b <= 0 or a < -1e-9 or a + b > W + 1e-6:
            raise DiaphragmError(f"collector: a wall length runs outside the line (0 to {W:g} ft)")
        if a < end - 1e-6:
            raise DiaphragmError("collector: two wall lengths overlap")
        end = a + b
    Lw = sum(b for a, b in segs)
    vd, vw = R / W, R / Lw
    pts, x, F = [(0.0, 0.0)], 0.0, 0.0
    for a, b in segs:
        if a > x + 1e-9:
            F += vd * (a - x); x = a
            pts.append((x, F))
        F += (vd - vw) * b; x = a + b
        pts.append((x, F))
    if x < W - 1e-9:
        F += vd * (W - x)
        pts.append((W, F))
    pts[-1] = (pts[-1][0], 0.0 if abs(pts[-1][1]) < 1e-6 * R else pts[-1][1])
    xm, Fm = max(pts, key=lambda p_: abs(p_[1]))
    return dict(vd=vd, vw=vw, Lw=Lw, points=pts, Fmax=abs(Fm), x_max=xm, segments=segs, full=abs(Lw - W) < 1e-6)
