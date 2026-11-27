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
diaphragms, collectors, torsion. Cantilevered diaphragms of open front structures (4.2.6, Eq. 4.2-2) by _design(cant=...).
One rectangular interior opening by opening() (force transfer around the opening, below).
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


def blocked(panel, face_in, spacing, panel_type, G, L, W, w, load, method, chord_E=None, chord_A=None, splice=(), cant=None):
    """Blocked diaphragm, Table 4.2A. spacing: nail spacing at the boundaries, 6, 4, 2.5 or 2 in."""
    key, _ = row(panel)
    if face_in not in (2, 3):
        raise DiaphragmError("diaphragm: the nominal width of the nailed face is 2 or 3 in.")
    if spacing not in OTHER_EDGES:
        raise DiaphragmError("diaphragm: the boundary nail spacing of a blocked diaphragm is 6, 4, 2-1/2 or 2 in.")
    vn_tab, g_osb, g_ply = BLOCKED[key][face_in][spacing]
    return _design(key, vn_tab, g_osb, g_ply, MAX_RATIO_BLOCKED, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice, cant)


def unblocked(panel, face_in, case, panel_type, G, L, W, w, load, method, chord_E=None, chord_A=None, splice=(), cant=None):
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
    return _design(key, t[i], t[i + 1], t[i + 2], MAX_RATIO_UNBLOCKED, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice, cant)


def _design(key, vn_tab, g_osb, g_ply, ratio_max, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice, cant=None):
    """cant: None for a single span between two lines of resistance; or dict(irregular=bool, stories=int) for a diaphragm cantilevered L
    (= L') past one line of resistance of width W (= W'), uniformly loaded (open front structure, Sect. 4.2.6): v = w L' / W' at the line,
    chord T = C = w L'^2 / (2 W'), deflection at the free edge by Eq. 4.2-2."""
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
    if cant is not None:
        v, T, R = w * L / W, w * L * L / (2.0 * W), w * L
        lim, lim_txt = ratio_max, "Table 4.2.2"
        if load == "seismic" and L > 6.0:                                   # Sect. 4.2.6.1 (wood structural panels, 4.2.8.1); exception: L' of 6 ft or less
            if cant.get("irregular"):
                lim, lim_txt = (0.67, "Sect. 4.2.6.1 item 2, torsionally irregular, over one story") if (cant.get("stories") or 1) > 1 else \
                    (1.0, "Sect. 4.2.6.1 item 2, torsionally irregular, one story")
            else:
                lim, lim_txt = min(1.5, ratio_max), "Sect. 4.2.6.1 item 2"
        out = dict(key=key, vn_table=vn_tab, Ga=Ga, sg=sg, vn=vn, factor_text=txt, factor=fac, capacity=cap, v=v, reaction=R, chord=T,
                   ratio=L / W, ratio_max=lim, ratio_src=lim_txt, defl=None, cant=True,
                   length_max=(35.0 if (load == "seismic" and L > 6.0) else None),
                   rigid_ok=(load == "seismic" and (cant.get("stories") or 1) == 1 and L <= 25.0 and L / W <= 1.0))
        if chord_E and chord_A:
            b = 3.0 * v * L ** 3 / (chord_E * chord_A * W)                  # Eq. 4.2-2
            s_ = 0.5 * v * L / (1000.0 * Ga)
            c = sum(x * d for x, d in splice) / W
            out.update(defl=b + s_ + c, defl_bending=b, defl_shear=s_, defl_splice=c)
        return out
    v = w * L / (2.0 * W)
    T = w * L * L / (8.0 * W)
    out = dict(key=key, vn_table=vn_tab, Ga=Ga, sg=sg, vn=vn, factor_text=txt, factor=fac, capacity=cap, v=v, reaction=w * L / 2.0, chord=T,
               ratio=L / W, ratio_max=ratio_max, ratio_src="Table 4.2.2", defl=None, cant=False)
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


def opening(L, W, w, cant, x0, a, y0, b, e1, e2):
    """Force transfer around one rectangular interior opening in a uniformly loaded diaphragm (SDPWS-2021 Sect. 4.2.1 last sentence,
    boundary elements at interior openings, definitions; 4.2.7.1). No published diaphragm example is on file: the Diekmann / APA T555
    force-transfer analysis of a shear wall with one opening (shearwall.ftao_multi) is applied to the diaphragm turned flat, the region
    of diaphragm around the opening taken as the free body:
      wall length L  -> diaphragm depth W (along the load); piers L1, L2 -> strips d1 = y0 and d2 = W - y0 - b beside the opening;
      opening width Lo -> b; wall height h -> region length Lr = e1 + a + e2 along the span; ho -> a; sheathing above and below the
      opening -> e1, e2, the lengths of full-depth diaphragm each side of the opening into which the opening's framing extends.
    Shear V: the larger of the diaphragm shears at the two ends of the region, used through the whole region (the load inside the region
    not deducted). L, W, x0 (support or line of resistance to the near edge of the opening, along the span), a, y0 (chord to the opening,
    across the depth), b, e1, e2 in ft; w plf at the level of the design method; cant True for a cantilever (x0 from the line of resistance).
    Returns dict of the region forces; every unit shear plf, forces lb."""
    for nm, v in (("the opening length", a), ("the opening width", b), ("the distance from the chord to the opening", y0),
                  ("the length of diaphragm before the opening", e1), ("the length of diaphragm past the opening", e2)):
        if v is None or v <= 0:
            raise DiaphragmError(f"diaphragm opening: {nm} must be positive")
    if x0 is None or x0 < 0:
        raise DiaphragmError("diaphragm opening: the distance from the support to the opening must not be negative")
    d1, d2 = y0, W - y0 - b
    if d2 <= 1e-9:
        raise DiaphragmError("diaphragm opening: the opening reaches the far chord; an opening at the edge is not an interior opening")
    xs, xe = x0 - e1, x0 + a + e2
    if xs < -1e-9 or xe > L + 1e-9:
        raise DiaphragmError(f"diaphragm opening: the opening and its framing extensions run from {xs:g} to {xe:g} ft, outside the "
                             f"{'cantilever' if cant else 'span'} (0 to {L:g} ft); shorten the extensions")
    Vx = (lambda x: w * (L - x)) if cant else (lambda x: w * (L / 2.0 - x))
    V = max(abs(Vx(xs)), abs(Vx(xe)))
    Lr = e1 + a + e2
    H = V * Lr / W                                   # chord force change across the region (the hold-down force of the wall analysis)
    va = H / (e1 + e2)                               # full-depth diaphragm each side of the opening
    O = va * b                                       # boundary force at each end of the opening
    S = d1 + d2
    strips = []
    for d in (d1, d2):
        F = O * d / S                                # corner force
        T = d * b / S                                # tributary width of the opening
        v = (V / W) * (d + T) / d                    # = V / (d1 + d2)
        R = v * d
        vc = (R - F) / d                             # corner zone, T555
        strips.append(dict(d=d, F=F, T=T, v=v, R=R, vc=vc, vF=F / d,
                           N=abs(va - vc) * max(e1, e2)))     # member along the opening side at the opening corner
    checks = [s_["vc"] * (e1 + e2) + s_["v"] * a - H for s_ in strips]     # each chord line carries H; the opening sides net zero
    checks += [va * (e1 + e2) - s_["vc"] * (e1 + e2) - s_["v"] * a for s_ in strips]
    v_max = max(va, max(max(s_["v"], abs(s_["vc"]), s_["vF"]) for s_ in strips))
    return dict(V=V, xs=xs, xe=xe, Lr=Lr, H=H, va=va, O=O, strips=strips, d1=d1, d2=d2, x0=x0, a=a, y0=y0, b=b, e1=e1, e2=e2,
                F_end=max(s_["F"] for s_ in strips), N_side=max(s_["N"] for s_ in strips), checks=checks, v_max=v_max, v_plain=V / W)


def openings(L, W, w, cant, ops):
    """Several interior openings (each dict x0, a, y0, b, e1, e2 as in opening()). Openings with the same position and length along the span
    (x0, a, e1, e2 equal) side by side across the depth share one region: the APA T555 analysis for several openings in a line (as
    shearwall.ftao_multi) turned flat, the strips between and beside them as the piers. Regions of different groups must not overlap.
    Returns a list of region results; a single opening gives opening()'s result."""
    if not ops:
        return []
    groups = {}
    for o in ops:
        groups.setdefault((round(o["x0"], 6), round(o["a"], 6), round(o["e1"], 6), round(o["e2"], 6)), []).append(o)
    spans = []
    for k in groups:
        spans.append((k[0] - k[2], k[0] + k[1] + k[3], k))
    spans.sort()
    for (s0, e0, k0), (s1, e1_, k1) in zip(spans, spans[1:]):
        if s1 < e0 - 1e-9:
            raise DiaphragmError("diaphragm openings: the regions around two openings overlap along the span (openings side by side across the depth "
                                 "must have the same position, length and framing extensions; others must be far enough apart that their extensions do not overlap)")
    out = []
    for k, grp in groups.items():
        if len(grp) == 1:
            out.append(opening(L, W, w, cant, **{q: grp[0][q] for q in ("x0", "a", "y0", "b", "e1", "e2")}))
        else:
            out.append(_openings_in_line(L, W, w, cant, grp))
    return out


def _openings_in_line(L, W, w, cant, grp):
    o0 = grp[0]
    x0, a, e1, e2 = o0["x0"], o0["a"], o0["e1"], o0["e2"]
    gr = sorted(grp, key=lambda o: o["y0"])
    piers, y = [], 0.0
    for o in gr:
        if o["b"] <= 0 or o["y0"] < y + 1e-9:
            raise DiaphragmError("diaphragm openings: openings side by side across the depth overlap or touch, or one reaches the chord")
        piers.append(o["y0"] - y)
        y = o["y0"] + o["b"]
    if W - y <= 1e-9:
        raise DiaphragmError("diaphragm openings: an opening reaches the far chord")
    piers.append(W - y)
    base = opening(L, W, w, cant, x0, a, gr[0]["y0"], gr[0]["b"], e1, e2)              # region, V and the checks of opening() on the span
    V, Lr = base["V"], base["Lr"]
    H = V * Lr / W
    va = H / (e1 + e2)
    n = len(gr)
    F = [[0.0, 0.0] for _ in piers]
    T = [[0.0, 0.0] for _ in piers]
    for j, o in enumerate(gr):
        dl, dr = piers[j], piers[j + 1]
        O = va * o["b"]
        F[j][1], F[j + 1][0] = O * dl / (dl + dr), O * dr / (dl + dr)
        T[j][1], T[j + 1][0] = dl * o["b"] / (dl + dr), dr * o["b"] / (dl + dr)
    strips = []
    for i, d in enumerate(piers):
        v = (V / W) * (d + T[i][0] + T[i][1]) / d
        R = v * d
        sF = F[i][0] + F[i][1]
        vc = (R - sF) / d
        strips.append(dict(d=d, F=sF, T=T[i][0] + T[i][1], v=v, R=R, vc=vc, vF=sF / d))
    # members along the opening sides: each opening edge against the strip beside it
    N_side = max(abs(va - strips[i]["vc"]) * max(e1, e2) for j in range(n) for i in (j, j + 1))
    # members across the depth at the opening ends: the running force from one chord to the other
    run, N_end = 0.0, 0.0
    for i, s_ in enumerate(strips):
        run += (s_["vc"] - s_["v"]) * s_["d"]
        N_end = max(N_end, abs(run))
        if i < n:
            run += va * gr[i]["b"]
            N_end = max(N_end, abs(run))
    checks = [strips[0]["vc"] * (e1 + e2) + strips[0]["v"] * a - H, strips[-1]["vc"] * (e1 + e2) + strips[-1]["v"] * a - H, run]
    for j in range(n):                                                    # the lines at each opening's sides net zero (T555)
        checks += [va * (e1 + e2) - strips[j]["vc"] * (e1 + e2) - strips[j]["v"] * a, strips[j + 1]["vc"] * (e1 + e2) + strips[j + 1]["v"] * a - va * (e1 + e2)]
    v_max = max(va, max(max(s_["v"], abs(s_["vc"]), s_["vF"]) for s_ in strips))
    return dict(base, multi=True, openings=[dict(y0=o["y0"], b=o["b"]) for o in gr], strips=strips, H=H, va=va, O=sum(va * o["b"] for o in gr),
                F_end=N_end, N_side=N_side, checks=checks, v_max=v_max, d1=piers[0], d2=piers[-1], piers=piers)
