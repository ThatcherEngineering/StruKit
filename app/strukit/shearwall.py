"""Wood structural panel shear walls: SDPWS-2021 (ANSI/AWC Special Design Provisions for
Wind and Seismic), Sect. 4.3.

Read from the standard:
  4.1.4      ASD allowable capacity = nominal / 2.0 (wind) or / 2.8 (seismic); LRFD
             factored resistance = 0.80 x nominal (wind) or 0.50 x nominal (seismic)
  Table 4.3A nominal unit shear capacity vn and apparent shear stiffness Ga for wood
             structural panels, blocked, sheathed on one side (values read from the table
             image and re-read at high resolution); note 3 specific gravity adjustment
             1 - (0.5 - G), not more than 1; note 10, 10d nails with the hold-down on the
             inside face of the end post: x 0.92
  Table 4.3.3   maximum aspect ratio h/b = 3.5 for blocked wood structural panels
  4.3.5.5.1  exception 1: shear to the full-height segments of a line in proportion to
             their design capacities, with the nominal capacity of every segment with
             h/b over 2 multiplied by 2b/h (and no further reduction by 4.3.3.2)
  Eq. 4.3-7  chord tension and compression T = C = V h / b_eff
  Eq. 4.3-1  deflection = 8 v h^3 / (E A b) + v h / (1000 Ga) + h Da / b

  4.3.5.3    unblocked walls: vn(ub) = vn(b) x C(ub) (Eq. 4.3-2), vn(b) the Table 4.3A
             value for 6 in. edge nailing; C(ub) from Table 4.3.5.3 by stud spacing and
             intermediate nail spacing (read from the page image); height not over 16 ft;
             Table 4.3.3 maximum aspect ratio 2 for unblocked walls
  4.3.4.3    unblocked deflection: Ga for 6 in. edge nailing, and v divided by C(ub)
  4.3.5.4.1  the same sheathing system on both sides: combined Ga = Ga1 + Ga2 and
             combined vn = Kmin x Ga(c) (Eq. 4.3-3, 4.3-4), which for identical sides is
             twice the one-side values

Covered: individual full-height wall segments in one line; blocked or unblocked; panels on
one side, or the same panels and nailing on both sides. Chord tension may be reduced by
dead load: T = V h / b_eff - (factor x w x b / 2), the dead load taken at the middle of
the segment and moments about the compression chord, with the arm b_eff / 2.
Not covered: different sheathing on the two sides of unblocked or perforated walls, perforated walls and force
transfer around openings (4.3.2.2, 4.3.2.3), other sheathing materials, the increase of
Table 4.3A note 2, moisture above 19 percent (note 5), anchor bolts and plate washers
(4.3.6.4.3), and the added seismic construction requirements of 4.3.7.1.

Units: lb, ft, plf; Ga in kips/in.; chord area in2, E in psi; deflection in inches.
"""
from dataclasses import dataclass, field

from .steel_beam import Line


class ShearWallError(ValueError):
    pass


SPACINGS = (6, 4, 3, 2)
# (grade, thickness, nail): [(vn plf, Ga OSB, Ga PLY) for edge nail spacing 6, 4, 3, 2 in.]
TABLE_4_3A = {
    ("Structural I", "5/16", "6d"): [(560, 13, 10), (840, 18, 13), (1090, 23, 16), (1430, 35, 22)],
    ("Structural I", "3/8", "8d"): [(645, 19, 14), (1010, 24, 17), (1290, 30, 20), (1710, 43, 24)],
    ("Structural I", "7/16", "8d"): [(715, 16, 13), (1105, 21, 16), (1415, 27, 19), (1875, 40, 24)],
    ("Structural I", "15/32", "8d"): [(785, 14, 11), (1205, 18, 14), (1540, 24, 17), (2045, 37, 23)],
    ("Structural I", "15/32", "10d"): [(950, 22, 16), (1430, 29, 20), (1860, 36, 22), (2435, 51, 28)],
    ("Sheathing", "5/16", "6d"): [(505, 13, 9.5), (755, 18, 12), (980, 24, 14), (1260, 37, 18)],
    ("Sheathing", "3/8", "6d"): [(560, 11, 8.5), (840, 15, 11), (1090, 20, 13), (1430, 32, 17)],
    ("Sheathing", "3/8", "8d"): [(615, 17, 12), (895, 25, 15), (1150, 31, 17), (1485, 45, 20)],
    ("Sheathing", "7/16", "8d"): [(670, 15, 11), (980, 22, 14), (1260, 28, 17), (1640, 42, 21)],
    ("Sheathing", "15/32", "8d"): [(730, 13, 10), (1065, 19, 13), (1370, 25, 15), (1790, 39, 20)],
    ("Sheathing", "15/32", "10d"): [(870, 22, 14), (1290, 30, 17), (1680, 37, 19), (2155, 52, 23)],
    ("Sheathing", "19/32", "10d"): [(950, 19, 13), (1430, 26, 16), (1860, 33, 18), (2435, 48, 22)],
}
PANELS = [f"{g}, {t} in, {n} common" for (g, t, n) in TABLE_4_3A]
# Table 4.3.5.3: intermediate nail spacing -> stud spacing -> C(ub); edge nails at 6 in.
CUB = {6: {12: 1.0, 16: 0.8, 20: 0.6, 24: 0.5}, 12: {12: 0.8, 16: 0.6, 20: 0.5, 24: 0.4}}
FACTORS = {("wind", "ASD"): ("divided by 2.0", 1 / 2.0), ("seismic", "ASD"): ("divided by 2.8", 1 / 2.8),
           ("wind", "LRFD"): ("x 0.80", 0.80), ("seismic", "LRFD"): ("x 0.50", 0.50)}


def panel_key(text):
    for k in TABLE_4_3A:
        if text == f"{k[0]}, {k[1]} in, {k[2]} common":
            return k
    raise ShearWallError("shear wall: the sheathing and nail choice is not a row of SDPWS Table 4.3A")


@dataclass
class Segment:
    b: float
    ratio: float                 # h / b
    reduction: float             # 2b/h where h/b exceeds 2, else 1
    vn: float                    # nominal unit shear capacity used, plf
    Vcap: float                  # design capacity of the segment, lb
    V: float                     # shear carried, lb
    v: float                     # unit shear carried, plf
    b_eff: float
    T: float                     # chord tension, lb (reduced by dead load where given)
    defl: float                  # in, or None when the chord data is not given
    C: float = 0.0               # chord compression from overturning, lb
    T_dead: float = 0.0          # dead load reduction of the tension, lb


@dataclass
class WallLine:
    vn_table: float
    Ga: float
    sg_factor: float
    nail_factor: float
    design_factor: float
    design_text: str
    segments: list
    V: float
    capacity: float              # design capacity of the line, lb
    lines: list = field(default_factory=list)
    cub: float = 1.0
    sides: int = 1


def line(panel, spacing, panel_type, G, h, lengths, V, load, method, holddown_inside=None, arm_offset_in=0.0,
         chord_E=None, chord_A=None, anchor_slip_in=None, sides=1, blocked=True, stud_spacing=None, field_nails=None,
         dead_plf=0.0, dead_factor=None, other=None):
    """A line of individual full-height segments. other: dict(panel, spacing, panel_type) of
    a different sheathing system on the opposite side (SDPWS 4.3.5.4.2), blocked walls. panel: an entry of PANELS; spacing: edge
    nail spacing, in.; panel_type: "OSB" or "plywood" (for Ga); G: specific gravity of the
    framing; h: wall height, ft; lengths: segment lengths, ft; V: design shear on the line,
    lb, at the level of `method` ("ASD" or "LRFD"); load: "wind" or "seismic";
    holddown_inside: for 10d nails, whether the hold-down is on the inside face of the end
    post; arm_offset_in: total reduction of the overturning moment arm from the segment
    length (b_eff = b - offset); chord_E, chord_A, anchor_slip_in: for the deflection."""
    key = panel_key(panel)
    if spacing not in SPACINGS:
        raise ShearWallError("shear wall: edge nail spacing must be 6, 4, 3 or 2 in.")
    if (load, method) not in FACTORS:
        raise ShearWallError("shear wall: the load must be wind or seismic, and the method ASD or LRFD")
    if panel_type not in ("OSB", "plywood"):
        raise ShearWallError("shear wall: the panel must be OSB or plywood")
    if G is None or not 0.2 < G < 1.0:
        raise ShearWallError("shear wall: the specific gravity of the framing is missing or out of range")
    if h is None or h <= 0 or not lengths or any(b is None or b <= 0 for b in lengths):
        raise ShearWallError("shear wall: the height and every segment length must be positive")
    if sides not in (1, 2):
        raise ShearWallError("shear wall: panels are on one side or on both sides")
    cub = 1.0
    if not blocked:
        if spacing != 6:
            raise ShearWallError("shear wall: an unblocked wall has edge nails at 6 in. (SDPWS Table 4.3.5.3)")
        if field_nails not in CUB or stud_spacing not in CUB[6]:
            raise ShearWallError("shear wall: an unblocked wall needs the stud spacing (12, 16, 20 or 24 in.) and the nail "
                                 "spacing at intermediate framing (6 or 12 in.)")
        if h > 16:
            raise ShearWallError("shear wall: an unblocked wall is limited to 16 ft high (SDPWS 4.3.5.3)")
        cub = CUB[field_nails][stud_spacing]
    if dead_plf and dead_factor is None:
        raise ShearWallError("shear wall: the dead load needs its factor in the uplift load combination")
    max_ratio = 3.5 if blocked else 2.0
    vn_t, ga_osb, ga_ply = TABLE_4_3A[key][SPACINGS.index(spacing)]
    Ga = (ga_osb if panel_type == "OSB" else ga_ply) * sides
    sg = min(1.0, 1.0 - (0.5 - G))
    nail = 1.0
    key2 = panel_key(other["panel"]) if other else None
    if key[2] == "10d" or (key2 and key2[2] == "10d"):
        if holddown_inside is None:
            raise ShearWallError("shear wall: with 10d nails, say whether the hold-down is on the inside face of the end post "
                                 "(Table 4.3A note 10)")
        nail = (0.92 if holddown_inside else 1.0) if key[2] == "10d" else 1.0
    dis = None
    if other:                                               # SDPWS 4.3.5.4.2: different sheathing systems on the two sides
        if sides != 1 or not blocked:
            raise ShearWallError("shear wall: different sheathing on the two sides is built for blocked walls; choose it in place of 'both sides'")
        if other.get("spacing") not in SPACINGS or other.get("panel_type") not in ("OSB", "plywood"):
            raise ShearWallError("shear wall: the other side needs its edge nail spacing (6, 4, 3 or 2 in.) and its panel (OSB or plywood)")
        if len({round(b, 6) for b in lengths}) > 1:
            raise ShearWallError("shear wall: with different sheathing on the two sides the segments of a line must be the same length "
                                 "(shear distribution, SDPWS 4.3.5.5.1)")
        vn2_t, g2o, g2p = TABLE_4_3A[key2][SPACINGS.index(other["spacing"])]
        nail2 = (0.92 if holddown_inside else 1.0) if key2[2] == "10d" else 1.0
        Ga1, Ga2 = Ga, (g2o if other["panel_type"] == "OSB" else g2p)
        a1, a2 = vn_t * nail, vn2_t * nail2
        (lo_v, lo_ga), (hi_v, hi_ga) = sorted(((a1, Ga1), (a2, Ga2)))
        twice = 2 * lo_v >= hi_v
        dis = dict(vn1=vn_t, vn2=vn2_t, nail1=nail, nail2=nail2, a1=a1, a2=a2, Ga1=Ga1, Ga2=Ga2, twice=twice,
                   vn=(2 * lo_v if twice else hi_v), Ga=(2 * lo_ga if twice else hi_ga))
        Ga = dis["Ga"]
    txt, fac = FACTORS[(load, method)]
    segs = []
    for b in lengths:
        r = h / b
        if r > max_ratio + 1e-9:
            raise ShearWallError(f"shear wall: a {b:g} ft segment of a {h:g} ft wall has h/b = {r:.2f}, over the {max_ratio:g} limit "
                                 "of SDPWS Table 4.3.3" + ("" if blocked else " for unblocked walls"))
        red = 2 * b / h if r > 2 else 1.0
        vn = (dis["vn"] * sg * red) if dis else vn_t * sg * nail * red * sides * cub
        segs.append(dict(b=b, r=r, red=red, vn=vn, cap=vn * b * fac))
    total = sum(s["cap"] for s in segs)
    out = []
    for s in segs:
        Vi = V * s["cap"] / total
        be = s["b"] - arm_offset_in / 12.0
        if be <= 0:
            raise ShearWallError("shear wall: the moment arm reduction is not less than a segment length")
        v = Vi / s["b"]
        d = None
        if chord_E and chord_A and anchor_slip_in is not None:
            vd = v / cub                                        # 4.3.4.3
            d = 8 * vd * h ** 3 / (chord_E * chord_A * s["b"]) + vd * h / (1000 * Ga) + h * anchor_slip_in / s["b"]
        ot = Vi * h / be
        td = (dead_factor or 0.0) * (dead_plf or 0.0) * s["b"] / 2.0
        out.append(Segment(s["b"], s["r"], s["red"], s["vn"], s["cap"], Vi, v, be, max(ot - td, 0.0), d, ot, td))
    L = [Line("vn", vn_t, "plf", "SDPWS Table 4.3A", f"{panel}, edge nails at {spacing} in"),
         Line("specific gravity factor, 1 - (0.5 - G)", sg, "", "Table 4.3A note 3", f"G = {G:g}"),
         Line("design factor", fac, "", "SDPWS 4.1.4", f"{load}, {method}: nominal {txt}")]
    if dis:
        L[0] = Line("vn, side 1", dis["vn1"], "plf", "SDPWS Table 4.3A", f"{panel}, edge nails at {spacing} in")
        L.insert(1, Line("vn, side 2", dis["vn2"], "plf", "SDPWS Table 4.3A", f"{other['panel']}, edge nails at {other['spacing']} in"))
        L.insert(2, Line("vn(c), both sides", dis["vn"], "plf", "SDPWS 4.3.5.4.2",
                         ("two times the smaller" if dis["twice"] else "the larger") + (" (after the 10d nail factor)" if min(dis["nail1"], dis["nail2"]) < 1 else "")))
        L.insert(3, Line("Ga(c)", dis["Ga"], "kips/in", "SDPWS 4.3.5.4.2",
                         f"{'two times that of the side with the smaller vn' if dis['twice'] else 'that of the side with the larger vn'}; side 1 {dis['Ga1']:g}, side 2 {dis['Ga2']:g}"))
    if sides == 2:
        L.insert(2, Line("panels on both sides", 2.0, "", "SDPWS 4.3.5.4.1", "the same panels and nailing on each side; vn and Ga doubled"))
    if not blocked:
        L.insert(2, Line("C(ub)", cub, "", "SDPWS Table 4.3.5.3, Eq. 4.3-2",
                         f"unblocked; studs at {stud_spacing:g} in, intermediate nails at {field_nails:g} in"))
    if key[2] == "10d" or (key2 and key2[2] == "10d"):
        L.insert(4 if dis else 2, Line("10d nail factor", 0.92 if holddown_inside else 1.0, "", "Table 4.3A note 10",
                         "hold-down on the inside face of the end post" if holddown_inside else "hold-down not on the inside face"))
    for i, s in enumerate(out, 1):
        L.append(Line(f"segment {i}: h/b", s.ratio, "", "SDPWS Table 4.3.3",
                      f"b = {s.b:g} ft" + (f"; capacity x 2b/h = {s.reduction:.3f} (4.3.5.5.1)" if s.reduction < 1 else "")))
        L.append(Line(f"segment {i}: design capacity", s.Vcap, "lb", "SDPWS 4.1.4, 4.3.5.5.1", f"{s.vn * fac:.0f} plf x {s.b:g} ft"))
    L.append(Line("design capacity of the line", total, "lb", "sum of the segments"))
    for i, s in enumerate(out, 1):
        L.append(Line(f"segment {i}: shear", s.V, "lb", "SDPWS 4.3.5.5.1, exception 1", f"{s.v:.0f} plf; in proportion to capacity"))
        L.append(Line(f"segment {i}: V h / b_eff", s.C, "lb", "SDPWS Eq. 4.3-7", f"b_eff = {s.b_eff:.2f} ft"))
        if dead_plf:
            L.append(Line(f"segment {i}: T = V h / b_eff - factor x w b / 2", s.T, "lb", "statics",
                          f"dead load {dead_factor:g} x {dead_plf:g} plf x {s.b:g} ft / 2 = {s.T_dead:,.0f} lb"))
        if s.defl is not None:
            L.append(Line(f"segment {i}: deflection", s.defl, "in", "SDPWS Eq. 4.3-1", f"Ga = {Ga:g} kips/in"))
    return WallLine(vn_t, Ga, sg, nail, fac, txt, out, V, total, L, cub, sides)


# ---- Perforated shear walls, SDPWS-2021 4.3.2.3, 4.3.3.4, 4.3.4.2, 4.3.5.6, 4.3.6.1.3 ----
# Read from the standard (equations and Table 4.3.5.6 from the page images):
#   4.3.2.3    a full-height segment at each end; height not over 20 ft; nominal unit shear
#              capacity not over 2,435 plf, single- or double-sided; uniform top and bottom
#   4.3.3.4    segments over 3.5:1 are left out of the sum of b_i; a segment over 2:1 counts
#              as b_i x 2 b_i / h; 4.3.3.2 and the exceptions of 4.3.5.5.1 do not apply
#   Eq. 4.3-5  Vn = vn Co (sum of b_i)
#   Eq. 4.3-6  Co = A_wall / (3 A_o + A_fhs), not more than 1.0; A_fhs is all full-height
#              sheathing regardless of aspect ratio; A_o = opening width x clear height
#   Eq. 4.3-8  T = C = V h / (Co x sum of b_i) at each end of the wall
#   4.3.6.4.1.1, 4.3.6.4.2.1  maximum unit shear v_max = V / (Co x sum of b_i) for the
#              in-plane shear anchorage, and the same value as a uniform uplift on the
#              bottom plate at full-height sheathing
#   4.3.4.2    deflection by Eq. 4.3-1 with v = v_max and b = sum of b_i
@dataclass
class Perforated:
    segments: list               # (x0, length, h/b, counted length) of each full-height segment
    A_wall: float
    A_o: float
    A_fhs: float
    Co: float
    sum_b: float
    vn: float                    # nominal unit shear capacity used, plf
    capacity: float              # design capacity, lb
    v_max: float
    T: float
    defl: float
    Ga: float
    lines: list = field(default_factory=list)


def perforated(panel, spacing, panel_type, G, h, length, openings, V, load, method, holddown_inside=None, sides=1,
               chord_E=None, chord_A=None, anchor_slip_in=None):
    """openings: list of (x from the left end, width, clear height), ft. Blocked wood
    structural panels on one side or the same panels on both sides."""
    key = panel_key(panel)
    if spacing not in SPACINGS or (load, method) not in FACTORS or panel_type not in ("OSB", "plywood") or sides not in (1, 2):
        raise ShearWallError("shear wall: check the nail spacing, the load, the method, the panel type and the number of sides")
    if G is None or not 0.2 < G < 1.0:
        raise ShearWallError("shear wall: the specific gravity of the framing is missing or out of range")
    if h is None or h <= 0 or length is None or length <= 0:
        raise ShearWallError("shear wall: the wall height and length must be positive")
    if h > 20:
        raise ShearWallError("shear wall: a perforated shear wall is limited to 20 ft high (SDPWS 4.3.2.3)")
    ops = sorted((float(x), float(w), float(ho)) for x, w, ho in openings)
    if not ops:
        raise ShearWallError("shear wall: a perforated shear wall has at least one opening")
    segs, at = [], 0.0
    for x, w, ho in ops:
        if w <= 0 or ho <= 0 or ho > h + 1e-9:
            raise ShearWallError("shear wall: every opening needs a positive width and a clear height not more than the wall height")
        if x < at - 1e-9:
            raise ShearWallError("shear wall: the openings overlap")
        if x - at > 1e-9:
            segs.append((at, x - at))
        at = x + w
    if at > length + 1e-9:
        raise ShearWallError("shear wall: an opening runs past the end of the wall")
    if length - at > 1e-9:
        segs.append((at, length - at))
    if ops[0][0] <= 1e-9 or at >= length - 1e-9:
        raise ShearWallError("shear wall: a full-height segment is needed at each end of a perforated shear wall (SDPWS 4.3.2.3)")
    vn_t, ga_osb, ga_ply = TABLE_4_3A[key][SPACINGS.index(spacing)]
    Ga = (ga_osb if panel_type == "OSB" else ga_ply) * sides
    sg = min(1.0, 1.0 - (0.5 - G))
    nail = 1.0
    if key[2] == "10d":
        if holddown_inside is None:
            raise ShearWallError("shear wall: with 10d nails, say whether the hold-down is on the inside face of the end post "
                                 "(Table 4.3A note 10)")
        nail = 0.92 if holddown_inside else 1.0
    vn_calc = vn_t * sg * nail * sides
    vn = min(vn_calc, 2435.0)
    rows, sum_b = [], 0.0
    for x0, b in segs:
        r = h / b
        counted = 0.0 if r > 3.5 + 1e-9 else (b * 2 * b / h if r > 2 else b)
        rows.append((x0, b, r, counted)); sum_b += counted
    if rows[0][3] <= 0 or rows[-1][3] <= 0:
        raise ShearWallError("shear wall: the segment at each end of a perforated shear wall must be within the 3.5 aspect ratio "
                             "limit (SDPWS 4.3.2.3, 4.3.3.4)")
    A_wall, A_o, A_fhs = length * h, sum(w * ho for _, w, ho in ops), sum(b for _, b in segs) * h
    Co = min(A_wall / (3 * A_o + A_fhs), 1.0)
    txt, fac = FACTORS[(load, method)]
    cap = vn * Co * sum_b * fac
    v_max = V / (Co * sum_b)
    T = V * h / (Co * sum_b)
    d = None
    if chord_E and chord_A and anchor_slip_in is not None:
        d = 8 * v_max * h ** 3 / (chord_E * chord_A * sum_b) + v_max * h / (1000 * Ga) + h * anchor_slip_in / sum_b
    L = [Line("vn", vn_t, "plf", "SDPWS Table 4.3A", f"{panel}, edge nails at {spacing} in"),
         Line("specific gravity factor, 1 - (0.5 - G)", sg, "", "Table 4.3A note 3", f"G = {G:g}")]
    if key[2] == "10d":
        L.append(Line("10d nail factor", nail, "", "Table 4.3A note 10",
                      "hold-down on the inside face of the end post" if holddown_inside else "hold-down not on the inside face"))
    if sides == 2:
        L.append(Line("panels on both sides", 2.0, "", "SDPWS 4.3.5.4.1", "the same panels and nailing on each side"))
    L.append(Line("vn used", vn, "plf", "SDPWS 4.3.2.3", "not more than 2,435 plf" + ("; limit governs" if vn < vn_calc else "")))
    for i, (x0, b, r, c) in enumerate(rows, 1):
        note = "not counted, h/b over 3.5" if c == 0 else (f"counted as b x 2b/h = {c:.2f} ft" if r > 2 else f"counted as {c:g} ft")
        L.append(Line(f"segment {i}: h/b", r, "", "SDPWS 4.3.3.4", f"b = {b:g} ft; {note}"))
    L += [Line("sum of b_i", sum_b, "ft", "SDPWS 4.3.3.4"),
          Line("A_wall = L h", A_wall, "ft2", "SDPWS Eq. 4.3-6"), Line("A_o", A_o, "ft2", "SDPWS Eq. 4.3-6", "opening widths x clear heights"),
          Line("A_fhs", A_fhs, "ft2", "SDPWS Eq. 4.3-6", "all full-height sheathing"),
          Line("Co = A_wall / (3 A_o + A_fhs)", Co, "", "SDPWS Eq. 4.3-6", "not more than 1.0"),
          Line("design factor", fac, "", "SDPWS 4.1.4", f"{load}, {method}: nominal {txt}"),
          Line("design capacity = vn Co (sum of b_i) x factor", cap, "lb", "SDPWS Eq. 4.3-5, 4.1.4"),
          Line("v_max = V / (Co x sum of b_i)", v_max, "plf", "SDPWS 4.3.6.4.1.1", "in-plane shear anchorage; uplift on the bottom plate"),
          Line("T = C = V h / (Co x sum of b_i)", T, "lb", "SDPWS Eq. 4.3-8", "at each end of the wall")]
    if d is not None:
        L.append(Line("deflection", d, "in", "SDPWS Eq. 4.3-1, 4.3.4.2", f"v = v_max, b = sum of b_i; Ga = {Ga:g} kips/in"))
    return Perforated(rows, A_wall, A_o, A_fhs, Co, sum_b, vn, cap, v_max, T, d, Ga, L)
