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


def ftao(panel, spacing, panel_type, G, h, L1, Lo, L2, ho, sill, V, load, method, holddown_inside=None, sides=1):
    """Shear wall with one opening designed for force transfer around the opening (SDPWS-2021
    4.3.2.2, 4.3.3.3), forces by the Diekmann technique as published by APA (Force Transfer
    Around Openings design examples; Technical Note T555). L1, L2: wall piers each side of
    the opening; Lo: opening width; ho: clear height of the opening; sill: height of the
    sheathing below it (0 for a door), ft. V at the level of `method`. Blocked panels."""
    key = panel_key(panel)
    if spacing not in SPACINGS or (load, method) not in FACTORS or panel_type not in ("OSB", "plywood") or sides not in (1, 2):
        raise ShearWallError("shear wall: check the nail spacing, the load, the method, the panel type and the number of sides")
    if G is None or not 0.2 < G < 1.0:
        raise ShearWallError("shear wall: the specific gravity of the framing is missing or out of range")
    if min(h, L1, Lo, L2, ho) <= 0 or sill < 0:
        raise ShearWallError("shear wall: the wall height, pier lengths and opening size must be positive")
    ha = h - ho - sill
    if ha <= 0:
        raise ShearWallError("shear wall: the opening and the sheathing below it leave no sheathing above the opening")
    if min(L1, L2) < 2.0 - 1e-9:
        raise ShearWallError("shear wall: each wall pier of a force-transfer shear wall is at least 2 ft long (SDPWS 4.3.2.2)")
    L = L1 + Lo + L2
    if h / L > 3.5 + 1e-9:
        raise ShearWallError("shear wall: the wall as a whole is over the 3.5 aspect ratio limit (SDPWS 4.3.3.3)")
    piers = []
    for b in (L1, L2):
        r = ho / b
        if r > 3.5 + 1e-9:
            raise ShearWallError(f"shear wall: a {b:g} ft pier beside a {ho:g} ft high opening is over the 3.5 aspect ratio limit (SDPWS 4.3.3.3)")
        piers.append((b, r, 2 * b / ho if r > 2 else 1.0))
    vn_t, ga_osb, ga_ply = TABLE_4_3A[key][SPACINGS.index(spacing)]
    sg = min(1.0, 1.0 - (0.5 - G))
    nail = 1.0
    if key[2] == "10d":
        if holddown_inside is None:
            raise ShearWallError("shear wall: with 10d nails, say whether the hold-down is on the inside face of the end post (Table 4.3A note 10)")
        nail = 0.92 if holddown_inside else 1.0
    txt, fac = FACTORS[(load, method)]
    v_cap = vn_t * sg * nail * sides * fac
    H = V * h / L                                   # hold-down force
    vh = V / (L1 + L2)                              # piers beside the opening
    vv = H / (ha + sill)                            # sheathing above and below the opening
    F = vv * Lo                                     # boundary force above (and below) the opening
    F1, F2 = F * L1 / (L1 + L2), F * L2 / (L1 + L2) # corner (strap) forces
    vc1, vc2 = F1 / L1, F2 / L2                     # corner zones
    red = min(p[2] for p in piers)
    lines = [Line("vn", vn_t, "plf", "SDPWS Table 4.3A", f"{panel}, edge nails at {spacing} in"),
             Line("specific gravity factor, 1 - (0.5 - G)", sg, "", "Table 4.3A note 3", f"G = {G:g}"),
             Line("design unit shear capacity", v_cap, "plf", "SDPWS 4.1.4", f"{load}, {method}: nominal {txt}" + (", both sides" if sides == 2 else "")),
             Line("hold-down force, H = V h / L", H, "lb", "statics", f"L = {L:g} ft"),
             Line("unit shear in the piers beside the opening, V / (L1 + L2)", vh, "plf", "Diekmann technique (APA T555)", ""),
             Line("unit shear above and below the opening, H / (ha + hb)", vv, "plf", "Diekmann technique (APA T555)", f"ha = {ha:g} ft above, hb = {sill:g} ft below"),
             Line("boundary force at the opening, F = vv Lo", F, "lb", "Diekmann technique (APA T555)", ""),
             Line("corner force F1 = F L1 / (L1 + L2)", F1, "lb", "Diekmann technique (APA T555)", f"pier {L1:g} ft"),
             Line("corner force F2 = F L2 / (L1 + L2)", F2, "lb", "Diekmann technique (APA T555)", f"pier {L2:g} ft"),
             Line("unit shear in the corner zones, F1 / L1 = F2 / L2", vc1, "plf", "Diekmann technique (APA T555)", "")]
    return dict(h=h, L=L, L1=L1, Lo=Lo, L2=L2, ho=ho, sill=sill, ha=ha, H=H, vh=vh, vv=vv, F=F, F1=F1, F2=F2, vc=vc1, v_cap=v_cap, piers=piers,
                Ga=(ga_osb if panel_type == "OSB" else ga_ply) * sides,
                reduction=red, v_max=max(vh, vv, vc1), lines=lines, design_text=txt)


def ftao_multi(panel, spacing, panel_type, G, h, piers, openings, V, load, method, holddown_inside=None, sides=1):
    """Shear wall with two or more openings in one line designed for force transfer around openings (SDPWS-2021 4.3.2.2, 4.3.3.3), by the
    rational method of APA Technical Note T555 for asymmetric piers and multiple openings, as worked in its published examples (STRUCTURE /
    IIBEC Interface 2018, 20 ft wall with two windows; Beebe and Skaggs, SEAOC 2015). piers: lengths left to right (ft), one more than the
    openings; openings: dicts w (width), ho (clear height), sill (sheathing below, 0 for a door), ft. V at the level of `method`.
      H = V h / L; above and below opening j: va_j = H / (ha_j + hb_j); boundary force O_j = va_j Lo_j, shared to the corners in proportion
      to the pier on each side; tributary length of each pier into an opening T = L_pier Lo / (L_left + L_right); pier unit shear
      v_i = (V / L)(L_i + sum T) / L_i; corner zone of pier i: (v_i L_i - sum F at its corners) / L_i (T555), and the corner force per foot
      of pier, sum F / L_i (the Diekmann corner shear of APA's one-opening example), both reported."""
    key = panel_key(panel)
    if spacing not in SPACINGS or (load, method) not in FACTORS or panel_type not in ("OSB", "plywood") or sides not in (1, 2):
        raise ShearWallError("shear wall: check the nail spacing, the load, the method, the panel type and the number of sides")
    if G is None or not 0.2 < G < 1.0:
        raise ShearWallError("shear wall: the specific gravity of the framing is missing or out of range")
    n = len(openings)
    if n < 1 or len(piers) != n + 1:
        raise ShearWallError("shear wall: give one pier more than the openings (a pier at each end and between each pair of openings)")
    if h <= 0 or min(piers) <= 0 or any(o["w"] <= 0 or o["ho"] <= 0 or (o.get("sill") or 0) < 0 for o in openings):
        raise ShearWallError("shear wall: the wall height, pier lengths and opening sizes must be positive")
    if min(piers) < 2.0 - 1e-9:
        raise ShearWallError(f"shear wall: a {min(piers):g} ft pier is under the 2 ft minimum for a force-transfer shear wall (SDPWS 4.3.2.2)")
    L = sum(piers) + sum(o["w"] for o in openings)
    if h / L > 3.5 + 1e-9:
        raise ShearWallError("shear wall: the wall as a whole is over the 3.5 aspect ratio limit (SDPWS 4.3.3.3)")
    ops = []
    for j, o in enumerate(openings):
        sill = o.get("sill") or 0.0
        ha = h - o["ho"] - sill
        if ha <= 0:
            raise ShearWallError(f"shear wall: opening {j + 1} and the sheathing below it leave no sheathing above it")
        ops.append(dict(w=o["w"], ho=o["ho"], sill=sill, ha=ha))
    vn_t, ga_osb, ga_ply = TABLE_4_3A[key][SPACINGS.index(spacing)]
    sg = min(1.0, 1.0 - (0.5 - G))
    nail = 1.0
    if key[2] == "10d":
        if holddown_inside is None:
            raise ShearWallError("shear wall: with 10d nails, say whether the hold-down is on the inside face of the end post (Table 4.3A note 10)")
        nail = 0.92 if holddown_inside else 1.0
    txt, fac = FACTORS[(load, method)]
    v_cap = vn_t * sg * nail * sides * fac
    H = V * h / L
    T = [[0.0, 0.0] for _ in piers]                  # tributary length of each pier into the opening at its left and at its right
    F = [[0.0, 0.0] for _ in piers]                  # corner force at the left and right side of each pier
    for j, o in enumerate(ops):
        a, b = piers[j], piers[j + 1]
        o["va"] = H / (o["ha"] + o["sill"])
        o["O"] = o["va"] * o["w"]
        F[j][1], F[j + 1][0] = o["O"] * a / (a + b), o["O"] * b / (a + b)
        T[j][1], T[j + 1][0] = a * o["w"] / (a + b), b * o["w"] / (a + b)
        o["F_left"], o["F_right"], o["T_left"], o["T_right"] = F[j][1], F[j + 1][0], T[j][1], T[j + 1][0]
    out_piers = []
    for i, Li in enumerate(piers):
        hos = [ops[k]["ho"] for k in (i - 1, i) if 0 <= k < n]
        ho = max(hos)
        r = ho / Li
        if r > 3.5 + 1e-9:
            raise ShearWallError(f"shear wall: the {Li:g} ft pier beside a {ho:g} ft high opening is over the 3.5 aspect ratio limit (SDPWS 4.3.3.3)")
        v = (V / L) * (Li + T[i][0] + T[i][1]) / Li
        R = v * Li
        sF = F[i][0] + F[i][1]
        out_piers.append(dict(L=Li, ho=ho, ratio=r, reduction=2 * Li / ho if r > 2 else 1.0, T=tuple(T[i]), v=v, R=R, F=tuple(F[i]),
                              vc=(R - sF) / Li, vF=sF / Li))
    checks = []                                      # T555 shear-line checks: the end lines equal H, the lines at the openings net zero
    p0 = out_piers[0]; o0 = ops[0]
    checks.append(p0["vc"] * (o0["ha"] + o0["sill"]) + p0["v"] * o0["ho"])
    for j, o in enumerate(ops):
        pl, pr = out_piers[j], out_piers[j + 1]
        hh = o["ha"] + o["sill"]
        checks.append(o["va"] * hh - pl["vc"] * hh - pl["v"] * o["ho"])
        checks.append(pr["vc"] * hh + pr["v"] * o["ho"] - o["va"] * hh)
    pn, on = out_piers[-1], ops[-1]
    checks.append(pn["vc"] * (on["ha"] + on["sill"]) + pn["v"] * on["ho"])
    lines = [Line("vn", vn_t, "plf", "SDPWS Table 4.3A", f"{panel}, edge nails at {spacing} in"),
             Line("specific gravity factor, 1 - (0.5 - G)", sg, "", "Table 4.3A note 3", f"G = {G:g}"),
             Line("design unit shear capacity", v_cap, "plf", "SDPWS 4.1.4", f"{load}, {method}: nominal {txt}" + (", both sides" if sides == 2 else "")),
             Line("hold-down force, H = V h / L", H, "lb", "statics", f"L = {L:g} ft")]
    for j, o in enumerate(ops):
        lines += [Line(f"opening {j + 1}: va = vb = H / (ha + hb)", o["va"], "plf", "APA T555", f"ha = {o['ha']:g} ft, hb = {o['sill']:g} ft"),
                  Line(f"opening {j + 1}: O = va Lo", o["O"], "lb", "APA T555", f"Lo = {o['w']:g} ft"),
                  Line(f"opening {j + 1}: corner forces, O L_pier / (L_left + L_right)", f"{o['F_left']:,.0f} lb left, {o['F_right']:,.0f} lb right", "", "APA T555", ""),
                  Line(f"opening {j + 1}: tributary lengths, L_pier Lo / (L_left + L_right)", f"{o['T_left']:.2f} ft left, {o['T_right']:.2f} ft right", "", "APA T555", "")]
    for i, p in enumerate(out_piers):
        lines += [Line(f"pier {i + 1}: v = (V / L)(L + T) / L", p["v"], "plf", "APA T555", f"L = {p['L']:g} ft, T = {p['T'][0] + p['T'][1]:.2f} ft; R = v L = {p['R']:,.0f} lb"),
                  Line(f"pier {i + 1}: corner zone (R - F) / L", p["vc"], "plf", "APA T555", f"F = {sum(p['F']):,.0f} lb; F / L = {p['vF']:.0f} plf")]
    lines.append(Line("shear lines: end lines equal H, lines at the openings net zero", "; ".join(f"{(0.0 if abs(c) < 0.5 else c):,.0f}" for c in checks) + " lb", "", "APA T555", ""))
    return dict(h=h, L=L, piers=out_piers, openings=ops, H=H, v_cap=v_cap, checks=checks, lines=lines, design_text=txt,
                Ga=(ga_osb if panel_type == "OSB" else ga_ply) * sides,
                v_max=max(max(p["v"] for p in out_piers), max(o["va"] for o in ops), max(max(abs(p["vc"]), p["vF"]) for p in out_piers)))


def ftao_deflection(h, piers, Ga, EA, Da):
    """Deflection of a force-transfer shear wall by its piers (APA: Beebe and Skaggs, SEAOC 2015; APA Technical Note T555): each pier by
    SDPWS-2021 Eq. 4.3-1 with its own unit shear v and length b, once for each direction of load; the wall deflection is the average of the
    pier values. Height of a pier: the full wall height h (Zach's ruling 2026-11-26, the more conservative reading), unless hb_left / hb_right
    are given: then, pushed toward an opening, from the top of the sheathing below it to the top of the wall (h - hb), APA's reading.
    piers: dicts L (ft), v (plf), hb_left, hb_right (ft of sheathing below the opening at that side; None where there is no opening).
    Ga kips/in.; EA lb (E psi x A in2); Da in. Returns dict(cases=[dict(pier, dir, h, b, v, bend, shear, anch, d)], delta)."""
    if not (EA > 0 and Ga > 0 and Da >= 0):
        raise ShearWallError("shear wall deflection: the end post area and E and the anchorage slip are needed")
    cases = []
    for i, p in enumerate(piers, 1):
        for dr, hb in (("+", p.get("hb_right")), ("-", p.get("hb_left"))):
            hp = h - (hb or 0.0) if hb is not None else h
            b, v = p["L"], p["v"]
            bend, shear, anch = 8 * v * hp ** 3 / (EA * b), v * hp / (1000.0 * Ga), hp * Da / b
            cases.append(dict(pier=i, dir=dr, h=hp, b=b, v=v, bend=bend, shear=shear, anch=anch, d=bend + shear + anch))
    return dict(cases=cases, delta=sum(c["d"] for c in cases) / len(cases))


SILL_BOLTS = (0.5, 0.625, 0.75, 0.875, 1.0)


def anchor_bolts(v_plf, D, sill_t, G, load, method, spacing_in=None, plate_w=3.5, washer_w=3.0, washer_l=3.0, washer_t=0.229,
                 offset_in=None, vn_side=0.0):
    """Foundation anchor bolts through the wall bottom plate (sill) into concrete, for the in-plane shear of the wall.
    Bolt in the sill: NDS 2018 Sect. 12.3 yield limit equations, single shear, wood side member of thickness sill_t on concrete with
    Fe = 7,500 psi and 6 in. embedment (the basis of NDS Table 12E, notes 2 to 4), load parallel to grain (along the wall), Fyb 45,000 psi.
    Adjusted: ASD CD = 1.6 (NDS Table 2.3.2, wind or earthquake); LRFD KF = 3.32, phi = 0.65, lambda = 1.0 (NDS Table N1, N2, N3).
    Plate washer: SDPWS-2021 4.3.6.4.3, at least 0.229 x 3 x 3 in., and, where the nominal unit shear capacity of the sheathing on a
    side is over 400 plf, extending to within 1/2 in. of the edge of the bottom plate on that side. offset_in: bolt centre to the
    sheathed edge of the plate (None: centred). v_plf at the design method's level. Returns dict(Z, Zp, s_max, rows, lines)."""
    from . import dowel
    if D not in SILL_BOLTS:
        raise ShearWallError("anchor bolts: diameter 1/2, 5/8, 3/4, 7/8 or 1 in. (NDS Table 12E)")
    if not sill_t or sill_t <= 0 or not plate_w or plate_w <= 0 or G is None or not 0.2 < G < 1.0:
        raise ShearWallError("anchor bolts: the bottom plate thickness, width and specific gravity are needed")
    if (load, method) not in FACTORS:
        raise ShearWallError("anchor bolts: check the load and the design method")
    r = dowel.lateral(D, sill_t, 6.0, dowel.fe(G, D, 0.0), 7500.0, dowel.BOLT_FYB, theta=0.0)
    Z = r["Z"]
    if method == "ASD":
        Zp, adj = Z * 1.6, "CD = 1.6 (NDS Table 2.3.2, wind or earthquake)"
    else:
        Zp, adj = Z * 3.32 * 0.65 * 1.0, "KF = 3.32, phi = 0.65, lambda = 1.0 (NDS Tables N1 to N3)"
    s_max = Zp / v_plf * 12.0 if v_plf > 0 else float("inf")
    lines = [Line("anchor bolt in the bottom plate, Z (parallel to grain)", Z, "lb", "NDS 2018 Sect. 12.3, Eq. 12.3-1 to 12.3-6",
                  f"D = {D:g} in., plate {sill_t:g} in. on concrete (Fe 7,500 psi, 6 in. embedment, NDS Table 12E basis), G = {G:g}; mode {r['mode']}"),
             Line("Z' = Z x adjustments", Zp, "lb", "NDS 2018 Table 11.3.1", adj + "; CM = Ct = Cg = C-delta = 1.0"),
             Line("largest anchor bolt spacing, Z' / v", s_max, "in", "statics", f"v = {v_plf:,.0f} plf at the bottom plate")]
    rows = []
    if spacing_in:
        rows.append(("anchor bolts, shear per bolt", v_plf * spacing_in / 12.0, Zp, "lb", "NDS 2018 Sect. 12.3, Table 11.3.1; SDPWS-2021 4.3.6.4.1",
                     f"{D:g} in. bolts at {spacing_in:g} in.; v s = {v_plf:,.0f} plf x {spacing_in / 12:.3g} ft"))
    rows.append(("plate washer thickness", 0.229, washer_t, "in", "SDPWS-2021 4.3.6.4.3", "0.229 in. minimum"))
    rows.append(("plate washer size", 3.0, min(washer_w, washer_l), "in", "SDPWS-2021 4.3.6.4.3", f"{washer_w:g} x {washer_l:g} in.; 3 x 3 in. minimum"))
    off = plate_w / 2.0 if offset_in is None else offset_in
    gap = off - washer_w / 2.0
    if vn_side > 400.0 + 1e-9:
        rows.append(("plate washer to the sheathed edge of the plate", gap, 0.5, "in", "SDPWS-2021 4.3.6.4.3",
                     f"nominal unit shear {vn_side:,.0f} plf on a side, over 400 plf; plate {plate_w:g} in. wide, bolt "
                     + ("centred" if offset_in is None else f"{offset_in:g} in. from the sheathed edge")))
    else:
        lines.append(Line("plate washer to the sheathed edge", f"{gap:.3g} in.", "", "SDPWS-2021 4.3.6.4.3",
                          f"no limit: nominal unit shear {vn_side:,.0f} plf on a side, not over 400 plf"))
    return dict(Z=Z, Zp=Zp, s_max=s_max, rows=rows, lines=lines, gap=gap, mode=r["mode"])
