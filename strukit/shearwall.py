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

Covered: individual full-height wall segments in one line, blocked, panels on one side.
Not covered: unblocked walls (4.3.5.3), panels on both sides (4.3.5.4), perforated walls
and force transfer around openings (4.3.2.2, 4.3.2.3), other sheathing materials, the
increase of Table 4.3A note 2, moisture above 19 percent (note 5), dead load resisting
uplift, anchor bolts and plate washers (4.3.6.4.3), and the added seismic construction
requirements of 4.3.7.1.

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
    T: float                     # chord tension = compression, lb
    defl: float                  # in, or None when the chord data is not given


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


def line(panel, spacing, panel_type, G, h, lengths, V, load, method, holddown_inside=None, arm_offset_in=0.0,
         chord_E=None, chord_A=None, anchor_slip_in=None):
    """A line of individual full-height segments. panel: an entry of PANELS; spacing: edge
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
    vn_t, ga_osb, ga_ply = TABLE_4_3A[key][SPACINGS.index(spacing)]
    Ga = ga_osb if panel_type == "OSB" else ga_ply
    sg = min(1.0, 1.0 - (0.5 - G))
    nail = 1.0
    if key[2] == "10d":
        if holddown_inside is None:
            raise ShearWallError("shear wall: with 10d nails, say whether the hold-down is on the inside face of the end post "
                                 "(Table 4.3A note 10)")
        nail = 0.92 if holddown_inside else 1.0
    txt, fac = FACTORS[(load, method)]
    segs = []
    for b in lengths:
        r = h / b
        if r > 3.5:
            raise ShearWallError(f"shear wall: a {b:g} ft segment of a {h:g} ft wall has h/b = {r:.2f}, over the 3.5 limit "
                                 "of SDPWS Table 4.3.3")
        red = 2 * b / h if r > 2 else 1.0
        vn = vn_t * sg * nail * red
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
            d = 8 * v * h ** 3 / (chord_E * chord_A * s["b"]) + v * h / (1000 * Ga) + h * anchor_slip_in / s["b"]
        out.append(Segment(s["b"], s["r"], s["red"], s["vn"], s["cap"], Vi, v, be, Vi * h / be, d))
    L = [Line("vn", vn_t, "plf", "SDPWS Table 4.3A", f"{panel}, edge nails at {spacing} in"),
         Line("specific gravity factor, 1 - (0.5 - G)", sg, "", "Table 4.3A note 3", f"G = {G:g}"),
         Line("design factor", fac, "", "SDPWS 4.1.4", f"{load}, {method}: nominal {txt}")]
    if key[2] == "10d":
        L.insert(2, Line("10d nail factor", nail, "", "Table 4.3A note 10",
                         "hold-down on the inside face of the end post" if holddown_inside else "hold-down not on the inside face"))
    for i, s in enumerate(out, 1):
        L.append(Line(f"segment {i}: h/b", s.ratio, "", "SDPWS Table 4.3.3",
                      f"b = {s.b:g} ft" + (f"; capacity x 2b/h = {s.reduction:.3f} (4.3.5.5.1)" if s.reduction < 1 else "")))
        L.append(Line(f"segment {i}: design capacity", s.Vcap, "lb", "SDPWS 4.1.4, 4.3.5.5.1", f"{s.vn * fac:.0f} plf x {s.b:g} ft"))
    L.append(Line("design capacity of the line", total, "lb", "sum of the segments"))
    for i, s in enumerate(out, 1):
        L.append(Line(f"segment {i}: shear", s.V, "lb", "SDPWS 4.3.5.5.1, exception 1", f"{s.v:.0f} plf; in proportion to capacity"))
        L.append(Line(f"segment {i}: T = C = V h / b_eff", s.T, "lb", "SDPWS Eq. 4.3-7", f"b_eff = {s.b_eff:.2f} ft"))
        if s.defl is not None:
            L.append(Line(f"segment {i}: deflection", s.defl, "in", "SDPWS Eq. 4.3-1", f"Ga = {Ga:g} kips/in"))
    return WallLine(vn_t, Ga, sg, nail, fac, txt, out, V, total, L)
