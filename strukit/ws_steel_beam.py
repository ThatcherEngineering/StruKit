"""Steel beam worksheet: one member, from loads to checks.

Ties together beam statics (beam.py), the Shapes Database (shapes.py) and the
AISC 360-22 strength checks (steel_beam.py). Nothing is defaulted silently: load
combinations, bracing, deflection limits and whether self-weight is included are all
inputs, and each is printed on the result.

Units at this level: feet, kips, kip/ft, ksi. Output moments in kip-ft.
"""
from dataclasses import dataclass, field

import math

import numpy as np

from . import beam, shapes, steel_beam

E = steel_beam.E_STEEL


class WorksheetError(ValueError):
    pass


@dataclass
class Combo:
    name: str
    factors: dict                 # load case -> factor
    source: str


@dataclass
class DeflCheck:
    label: str
    factors: dict                 # load case -> factor (service)
    ratio: float                  # span / ratio is the limit
    source: str


@dataclass
class Row:
    check: str
    combo: str
    demand: float
    capacity: float
    unit: str
    source: str
    note: str = ""

    @property
    def dc(self):
        return self.demand / self.capacity if self.capacity else float("inf")

    @property
    def status(self):
        return "OK" if self.demand <= self.capacity else "FLAG"


@dataclass
class SteelBeamSheet:
    mark: str
    shape: str
    Fy: float
    span_ft: float
    method: str
    props: dict
    loads: list
    bracing_text: str
    self_weight: bool
    rows: list = field(default_factory=list)
    steps: list = field(default_factory=list)          # steel_beam.Line items for the governing flexure case
    reactions: dict = field(default_factory=dict)      # combo -> (left, right)
    governing: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)
    brace_points: list = field(default_factory=list)   # ft, interior and end brace locations
    diagram: dict = field(default_factory=dict)        # x, V, M of the governing strength combo

    @property
    def ok(self):
        return all(r.status == "OK" for r in self.rows)


def _solve(span, EI, loads, factors):
    pts, dists = [], []
    for ld in loads:
        f = factors.get(ld["case"], 0.0)
        if f == 0:
            continue
        if ld["kind"] == "uniform":
            x1, x2 = ld.get("x1_ft", 0.0), ld.get("x2_ft", span)
            dists.append(beam.DistLoad(x1, x2, f * ld["w"], f * ld["w"]))
        elif ld["kind"] == "point":
            pts.append(beam.PointLoad(ld["x_ft"], f * ld["P"]))
        else:
            raise WorksheetError(f"load kind '{ld['kind']}' is not uniform or point")
    return beam.solve(span, [0.0, span], EI, point_loads=pts, dist_loads=dists)


def _cb(res, a, b):
    """Eq. F1-1 on the unbraced segment a..b of a solved beam."""
    xq = [a + (b - a) * k for k in (0.25, 0.5, 0.75)]
    MA, MB, MC = (abs(float(np.interp(x, res.x, res.M))) for x in xq)
    seg = (res.x >= a - 1e-9) & (res.x <= b + 1e-9)
    Mmax = float(np.max(np.abs(res.M[seg])))
    return steel_beam.cb_factor(Mmax, MA, MB, MC), Mmax


def _bu_welds(sheet, props, method):
    """Built-up section: the flange-to-web weld shear flow at the largest shear, stated (the welds are not checked on the beam sheet)."""
    if props.get("type") != "BU":
        return
    d, yb, Ix = props["d"], props["yb"], props["Ix"]
    Q = max(props["bft"] * props["tft"] * (d - yb - props["tft"] / 2), props["bfb"] * props["tfb"] * (yb - props["tfb"] / 2))
    V = max((r.demand for r in sheet.rows if r.check == "shear"), default=0.0)
    sheet.assumptions.append(f"Built-up section: flanges welded continuously to the web. The welds are not checked on this sheet; the shear flow they carry at "
                             f"the largest shear is V Q / Ix = {V:.2f} x {Q:.1f} / {Ix:,.0f} = {V * Q / Ix:.2f} kip/in. ({method} level, both welds together).")


def _signed(check, props, Fy, Lb_in, Cb, method, M_seg, M_abs):
    """[(moment, check result)] for one segment. A singly symmetric built-up section is checked for its largest positive moment with the top
    flange in compression and its largest negative moment with the bottom flange in compression; any other section once for the largest
    moment either way."""
    if props.get("type") == "BU" and not props.get("symmetric"):
        pos, neg = max(float(np.max(M_seg)), 0.0), max(-float(np.min(M_seg)), 0.0)
        out = [(pos, check(props, Fy, Lb_in, Cb, method, compression="top"))]
        if neg > 1e-9:
            out.append((neg, check(props, Fy, Lb_in, Cb, method, compression="bottom")))
        return out
    return [(M_abs, check(props, Fy, Lb_in, Cb, method))]


def _bu_stiffeners(mark, sheet, props, Fy, method, results, span_ft):
    """Built-up girder with transverse stiffener pairs (AISC 360-22 Sect. G2). One clear spacing a: stiffeners at a along the whole girder;
    the end panel is checked by Sect. G2.1 with kv from a (the beam's shear row); with tension field action the first interior panel, from a
    beyond each support, by Sect. G2.2. A list of spacings (panel by panel from each support, as AISC Design Examples G.8A / G.8B): the end
    panel as above, each further panel for the largest shear in it at its own a (Sect. G2.2 with tension field action when asked and a / h
    not over 3, else G2.1), and the web beyond the last stiffener as unstiffened (kv = 5.34). The stiffeners by Sect. G2.4 (Eq. G2-16,
    G2-17) at the smallest spacing and the largest rho_w of the stiffened panels."""
    from . import builtup
    st = props["stiff"]
    a = st["a"]
    panels = st.get("panels")
    lrfd = method == "LRFD"
    av = lambda Vn: 0.90 * Vn if lrfd else Vn / 1.67
    h = props["h"]
    for ai in (panels or [a]):
        if ai / h > 3.0:
            raise WorksheetError(f"{mark}: a stiffener spacing a / h = {ai / h:.2f} is over 3.0: the stiffeners do not raise kv (Sect. G2.1(b)(2))")
    end = builtup.shear_panel(props, Fy, a, False)
    Vc1_end, Vc2 = av(end["Vn"]), av(end["Vn2"])
    Vr_end = max((max(abs(float(r.V[0])), abs(float(r.V[-1]))), n) for n, r in results)
    rows, lines = [], []
    rho = [max((Vr_end[0] - Vc2) / (Vc1_end - Vc2), 0.0) if Vc1_end > Vc2 else 0.0]

    def vmax_in(x0_in, x1_in):
        """Largest shear between x0 and x1 (in. from each support, mirrored), over the combinations."""
        best_ = (0.0, "")
        for n, r in results:
            for lo, hi in ((x0_in / 12.0, x1_in / 12.0), (span_ft - x1_in / 12.0, span_ft - x0_in / 12.0)):
                xs_ = [lo + (hi - lo) * k / 40 for k in range(41)] + [float(x) for x in r.x if lo + 1e-6 < x < hi - 1e-6]
                v_ = max(abs(float(np.interp(x, r.x, r.V))) for x in xs_)
                if v_ > best_[0]:
                    best_ = (v_, n)
        return best_

    if panels:
        x = panels[0]
        for i, ai in enumerate(panels[1:], 2):
            if x >= span_ft * 6.0 - 1e-6:
                break
            x1 = min(x + ai, span_ft * 6.0)
            Vr = vmax_in(x, x1)
            tfa = bool(st.get("tfa"))
            pn = builtup.shear_panel(props, Fy, ai, tfa)
            Vc = av(pn["Vn"])
            rows.append(Row(f"shear, panel {i} ({x:g} to {x + ai:g} in. from each support)", Vr[1], Vr[0], Vc, "kip",
                            f"AISC 360-22 Sect. {'G2.2' if pn['eq'] in ('Eq. G2-6', 'Eq. G2-7', 'Eq. G2-8') else 'G2.1'}, {pn['eq']}",
                            f"a = {ai:g} in., kv = {pn['kv']:.2f}" + (f", Cv2 = {pn['Cv2']:.3f}" if tfa else f", Cv1 = {pn['Cv']:.3f}")))
            lines.append(steel_beam.Line(f"Vn, panel {i}", pn["Vn"], "kip", f"AISC 360-22 {pn['eq']}", f"a = {ai:g} in., a / h = {ai / h:.2f}"
                                         + ("; tension field action, 2 Aw / (Afc + Aft), h / bfc and h / bft by Sect. G2.2(b)(1)" if tfa else "")))
            c1, c2 = Vc, av(pn["Vn2"])                                   # Vc1 by Sect. G2.1 or G2.2 as applicable (Sect. G2.4)
            rho.append(max((Vr[0] - c2) / (c1 - c2), 0.0) if c1 > c2 else 0.0)
            x += ai
        if x < span_ft * 6.0 - 1e-6:
            Vr = vmax_in(x, span_ft * 6.0)
            un = builtup.shear_panel(props, Fy, None, False)
            rows.append(Row(f"shear, web beyond the last stiffener ({x:g} in. from each support)", Vr[1], Vr[0], av(un["Vn"]), "kip",
                            f"AISC 360-22 Sect. G2.1, {un['eq']}", f"no stiffeners, kv = 5.34, Cv1 = {un['Cv']:.3f}"))
    elif st.get("tfa"):
        tf_ = builtup.shear_panel(props, Fy, a, True)
        best = None
        for n, r in results:
            Vint = max(abs(float(np.interp(a / 12.0, r.x, r.V))), abs(float(np.interp(span_ft - a / 12.0, r.x, r.V))))
            if best is None or Vint > best[0]:
                best = (Vint, n)
        rows.append(Row("shear, first interior panel (tension field action)", best[1], best[0], av(tf_["Vn"]), "kip", f"AISC 360-22 Sect. G2.2, {tf_['eq']}",
                        f"a = {a:g} in. beyond each end panel; kv = {tf_['kv']:.2f}, Cv2 = {tf_['Cv2']:.3f}"))
        lines.append(steel_beam.Line("Vn, interior panel with tension field action", tf_["Vn"], "kip", f"AISC 360-22 {tf_['eq']}",
                                     f"Cv2 = {tf_['Cv2']:.3f} (Eq. G2-9 to G2-11); 2 Aw / (Afc + Aft), h / bfc and h / bft by Sect. G2.2(b)(1)"))
    rho_w = max(rho)
    a_min = min(panels or [a])
    sc = builtup.stiffener_check(props, Fy, a_min, st["ts"], st["bs"], st["Fy"], rho_w)
    rows += [Row("transverse stiffener width-to-thickness, (b / t)st", "", sc["bt"], sc["bt_lim"], "", "AISC 360-22 Eq. G2-16",
                 f"{st['bs']:g} x {st['ts']:g} in. plates, one each side of the web, Fyst = {st['Fy']:g} ksi"),
             Row("transverse stiffener moment of inertia, Ist", Vr_end[1], sc["need"], sc["Ist"], "in4", "AISC 360-22 Eq. G2-17 to G2-19",
                 f"Ist1 = {sc['Ist1']:.1f}, Ist2 = {sc['Ist2']:.2f} in4, rho_w = {rho_w:.2f}" + (f", b = {a_min:g} in. (smallest spacing)" if panels else ""))]
    lines += [steel_beam.Line("Stiffener pair Ist about the web centre, ts (2 bs + tw)^3 / 12", sc["Ist"], "in4", "AISC 360-22 Sect. G2.4", ""),
              steel_beam.Line("rho_w = (Vr - Vc2) / (Vc1 - Vc2), largest of the stiffened panels", rho_w, "", "AISC 360-22 Sect. G2.4",
                              f"end panel: Vr = {Vr_end[0]:.1f}, Vc1 = {Vc1_end:.1f}, Vc2 = {Vc2:.1f} kip")]
    sheet.rows += rows
    sheet.steps = list(sheet.steps) + lines
    if panels:
        sheet.assumptions.append("Transverse stiffener pairs at clear spacings of " + ", ".join(f"{x:g}" for x in panels) + " in. from each support, panel by panel; "
                                 "the end panel is designed without tension field action" + ("; tension field action in the other stiffened panels" if st.get("tfa") else "")
                                 + "; the web beyond the last stiffener is unstiffened.")
    else:
        sheet.assumptions.append(f"Transverse stiffener pairs at a clear spacing of {a:g} in. along the girder; the end panel is designed without tension field action"
                                 + ("; tension field action in the interior panels." if st.get("tfa") else "."))


def _bu_bearing(mark, sheet, props, Fy, method, results):
    """Built-up girder bearing on its supports at its ends (bottom flange on the support, bearing length lb): web local yielding (AISC 360-22
    Eq. J10-3, k = the flange thickness, the flange-to-web welds not counted) and web local crippling (Eq. J10-5a / J10-5b); with a pair of
    full-depth bearing stiffeners: bearing on their ends (Sect. J7, Eq. J7-1, contact area 2 (bs - clip) ts), and the stiffeners with a 12 tw
    strip of web as a column of effective length 0.75 h (Sect. J10.8, J4.4; Chapter E where Lc / r is over 25), and their width-to-thickness
    (Table B4.1a Case 3, 0.56 (E / Fyst)^0.5)."""
    b = props["brg"]
    lrfd = method == "LRFD"
    f = (lambda Rn, phi, om: phi * Rn if lrfd else Rn / om)
    d, tw, h = props["d"], props["tw"], props["h"]
    tf = props.get("tfb") or props.get("tf")
    lb = b["lb"]
    R = max((max(abs(float(r.V[0])), abs(float(r.V[-1]))), n) for n, r in results)
    E_ = 29000.0
    Ry = Fy * tw * (2.5 * tf + lb)
    root = math.sqrt(E_ * Fy * tf / tw)
    if lb / d <= 0.2:
        Rc, eqc = 0.40 * tw ** 2 * (1 + 3 * (lb / d) * (tw / tf) ** 1.5) * root, "Eq. J10-5a"
    else:
        Rc, eqc = 0.40 * tw ** 2 * (1 + (4 * lb / d - 0.2) * (tw / tf) ** 1.5) * root, "Eq. J10-5b"
    rows, lines = [], []
    lines += [steel_beam.Line("Support reaction, largest", R[0], "kip", R[1], ""),
              steel_beam.Line("Web local yielding at the end, Rn = Fy tw (2.5 k + lb)", Ry, "kip", "AISC 360-22 Eq. J10-3",
                              f"lb = {lb:g} in., k = tf = {tf:g} in. (flange-to-web welds not counted); phi = 1.00, Omega = 1.50"),
              steel_beam.Line("Web local crippling at the end", Rc, "kip", f"AISC 360-22 {eqc}", f"lb / d = {lb / d:.3f}; phi = 0.75, Omega = 2.00")]
    if not b.get("ts"):
        rows += [Row("web local yielding at the supports", R[1], R[0], f(Ry, 1.0, 1.5), "kip", "AISC 360-22 Eq. J10-3", f"lb = {lb:g} in., no bearing stiffeners"),
                 Row("web local crippling at the supports", R[1], R[0], f(Rc, 0.75, 2.0), "kip", f"AISC 360-22 {eqc}", f"lb = {lb:g} in., no bearing stiffeners")]
    else:
        ts, bs, clip, Fyst = b["ts"], b["bs"], b["clip"], b["Fy"]
        if clip >= bs:
            raise WorksheetError(f"{mark}: the bearing stiffener corner clip is as wide as the stiffener")
        Apb = 2 * (bs - clip) * ts
        Rb = 1.8 * Fyst * Apb
        A = 2 * bs * ts + 12 * tw * tw
        I = ts * (2 * bs + tw) ** 3 / 12.0 + 12 * tw * tw ** 3 / 12.0
        r_ = math.sqrt(I / A)
        Lc = 0.75 * h
        slr = Lc / r_
        Fyc = min(Fy, Fyst)
        if slr <= 25:
            Pn, eqp = Fyc * A, "Sect. J4.4(a), Lc / r not over 25: Pn = Fy Ag"
        else:
            Fe = math.pi ** 2 * E_ / slr ** 2
            Fn = 0.658 ** (Fyc / Fe) * Fyc if Fyc / Fe <= 2.25 else 0.877 * Fe
            Pn, eqp = Fn * A, f"Sect. J4.4(b), Chapter E: Fe = {Fe:.1f} ksi, Fn = {Fn:.1f} ksi (Eq. E3-2 / E3-3)"
        bt, bt_lim = bs / ts, 0.56 * math.sqrt(E_ / Fyst)
        lines += [steel_beam.Line("Bearing stiffeners: contact area Apb = 2 (bs - clip) ts", Apb, "in2", "AISC 360-22 Sect. J7", f"{bs:g} x {ts:g} in. pair, {clip:g} in. corner clips"),
                  steel_beam.Line("Bearing, Rn = 1.8 Fy Apb", Rb, "kip", "AISC 360-22 Eq. J7-1", f"Fy = {Fyst:g} ksi; phi = 0.75, Omega = 2.00"),
                  steel_beam.Line("Stiffener column: A = 2 bs ts + 12 tw^2", A, "in2", "AISC 360-22 Sect. J10.8", f"12 tw web strip at the end of the member; I = {I:.1f} in4, r = {r_:.2f} in."),
                  steel_beam.Line("Lc / r, Lc = 0.75 h", slr, "", "AISC 360-22 Sect. J10.8", f"Lc = {Lc:.2f} in."),
                  steel_beam.Line("Stiffener column, Pn", Pn, "kip", eqp, f"Fy = {Fyc:g} ksi (the lower of web and stiffener); phi = 0.90, Omega = 1.67")]
        rows += [Row("bearing stiffeners, bearing on the ends", R[1], R[0], f(Rb, 0.75, 2.0), "kip", "AISC 360-22 Sect. J7, Eq. J7-1", f"Apb = {Apb:.2f} in2"),
                 Row("bearing stiffeners as a column", R[1], R[0], f(Pn, 0.90, 1.67), "kip", "AISC 360-22 Sect. J10.8, J4.4", f"Lc / r = {slr:.1f}"),
                 Row("bearing stiffener width-to-thickness, bs / ts", "", bt, bt_lim, "", "AISC 360-22 Table B4.1a Case 3", f"0.56 (E / Fy)^0.5, Fy = {Fyst:g} ksi")]
        sheet.assumptions.append(f"A pair of full-depth bearing stiffeners {bs:g} x {ts:g} in. at each support, fitted to the bearing flange, corner clips {clip:g} in.; "
                                 "the web is not counted on for yielding or crippling at the supports.")
    sheet.rows += rows
    sheet.steps = list(sheet.steps) + lines
    sheet.assumptions.append(f"The girder bears on its supports at its ends through the bottom flange over {lb:g} in.")


def run(mark, shape, Fy, span_ft, loads, combos, defl_checks, bracing, method,
        include_self_weight, self_weight_case="D", spans=None, overhang_left=0.0, overhang_right=0.0, fixed=False, bu_stiff=None, bu_brg=None):
    """bracing: "continuous", or a list of brace locations in ft (ends are added)."""
    if method not in ("ASD", "LRFD"):
        raise WorksheetError("method must be ASD or LRFD")
    if not combos:
        raise WorksheetError(f"{mark}: no load combinations given")
    if include_self_weight not in (True, False):
        raise WorksheetError(f"{mark}: say whether self-weight is included (True or False)")
    for ld in loads:
        for k in ("case", "kind"):
            if k not in ld:
                raise WorksheetError(f"{mark}: a load is missing '{k}'")
    hss_props = None
    try:
        props, check = shapes.get(shape), steel_beam.check
    except shapes.ShapeError:
        try:
            props, check = shapes.channel(shape), steel_beam.check
        except shapes.ShapeError:
            try:
                hss_props = props = shapes.hss(shape)
            except shapes.ShapeError:
                raise WorksheetError(f"{mark}: shape '{shape}' is not in the {shapes.SOURCE} I-shape, channel, HSS or pipe tables")
    if bu_stiff:
        if props.get("type") != "BU":
            raise WorksheetError(f"{mark}: transverse stiffeners are for a built-up section (BU ...)")
        st_ = dict(bu_stiff)
        aa = st_["a"] if isinstance(st_["a"], (list, tuple)) else [st_["a"]]
        if not aa or min(aa) <= 0:
            raise WorksheetError(f"{mark}: the stiffener spacings must be positive")
        st_.update(a=float(aa[0]), panels=[float(x) for x in aa] if len(aa) > 1 else None)
        props = dict(props, stiff=st_)
    if bu_brg:
        if props.get("type") != "BU":
            raise WorksheetError(f"{mark}: the bearing checks at the supports are for a built-up section (BU ...)")
        props = dict(props, brg=bu_brg)
    if hss_props is not None:
        from . import hss
        def check(pr, Fy_, Lb_, Cb_, method_):
            try:
                return hss.beam_check(pr, Fy_, Lb_, Cb_, method_)
            except hss.HSSError as e:
                raise WorksheetError(f"{mark}: {e}")
    side = [ld for ld in loads if str(ld.get("dir") or "").startswith("side")]
    loads = [ld for ld in loads if ld not in side]
    all_loads = list(loads)
    assumptions = []
    if include_self_weight:
        all_loads.append(dict(case=self_weight_case, kind="uniform", w=props["W"] / 1000.0,
                              label=f"self-weight {props['W']:.0f} lb/ft"))
        assumptions.append(f"Beam self-weight ({props['W']:.0f} lb/ft, {props.get('source') or shapes.SOURCE}) added "
                           f"to load case {self_weight_case}.")
    else:
        assumptions.append("Beam self-weight is NOT added separately; it is taken as "
                           "included in the loads entered.")
    if props.get("type") in ("C", "MC"):
        assumptions.append("The loads act through the shear center of the channel; torsion is not checked.")
    from . import contbeam
    try:
        lay = contbeam.layout(span_ft, spans, overhang_left, overhang_right, fixed)
    except ValueError as e:
        raise WorksheetError(f"{mark}: {str(e).replace('beam: ', '')}")
    if fixed and bracing == "continuous":
        raise WorksheetError(f"{mark}: on a cantilever the bottom flange is in compression; choose 'at points' and list where the bottom flange is braced "
                             "(leave the list blank if it is braced only at the support)")
    total_ft = lay.total
    if bracing == "continuous":
        segs, btxt, brace_pts = None, "continuously braced (Lb = 0)", []
    else:
        pts = sorted({0.0, float(total_ft)} | {float(x) for x in bracing})
        if pts[0] < 0 or pts[-1] > total_ft + 1e-9:
            raise WorksheetError(f"{mark}: a brace point is off the beam")
        segs = list(zip(pts[:-1], pts[1:]))
        btxt = "braced at " + ", ".join(f"{x:g}" for x in pts) + " ft"
        brace_pts = pts
    twist = [ld for ld in loads + side if ld.get("e_in")]
    if twist and (not lay.simple or props.get("type") not in ("HSS-RECT", "HSS-ROUND", "PIPE")):
        raise WorksheetError(f"{mark}: loads off the shear center (torsion) are checked on a single simple span of an HSS or pipe "
                             "(AISC 360-22 Sect. H3); torsion of W shapes and channels is not covered")
    if side and (not lay.simple or props.get("type") in ("C", "MC")):
        raise WorksheetError(f"{mark}: sideways (weak-axis) loads are checked on a single simple span of a W, M, S or HP shape, HSS or pipe; "
                             "this beam has more than one span, an overhang, a fixed support or is a channel")
    if not lay.simple:
        if bracing != "continuous":
            pts = sorted({0.0, float(lay.total)} | {float(x) for x in bracing} | {float(x) for x in lay.supports})
            if pts[0] < 0 or pts[-1] > lay.total + 1e-9:
                raise WorksheetError(f"{mark}: a brace point is off the beam")
            segs = list(zip(pts[:-1], pts[1:]))
            btxt = "braced at " + ", ".join(f"{x:g}" for x in pts) + " ft (supports and brace points)"
            brace_pts = pts
        if props.get("brg") or props.get("stiff"):
            raise WorksheetError(f"{mark}: transverse and bearing stiffener checks are for a single simple span")
        return _run_continuous(mark, shape, Fy, lay, all_loads, combos, defl_checks, segs, btxt, brace_pts, method, include_self_weight,
                               props, check, assumptions)
    EI = E * props["Ix"] / 144.0                                   # kip-ft^2
    sheet = SteelBeamSheet(mark, shapes.normalize(shape), Fy, span_ft, method, props, all_loads,
                           btxt, include_self_weight, assumptions=assumptions,
                           brace_points=brace_pts)

    worst_m, worst_v = None, None
    if side:
        from . import steel_beamcol
        wk = steel_beamcol.weak_axis_flexure(props, Fy, method)
        wv = steel_beamcol.weak_axis_shear(props, Fy, method)
        EIy = E * props["Iy"] / 144.0
        worst_wm = worst_wv = worst_h = None
        sheet.loads = list(all_loads) + [dict(ld, label=(ld.get("label") + ", " if ld.get("label") else "") + "sideways, weak axis") for ld in side]
        sheet.assumptions.append("Sideways loads act in the plane of the flanges (bending about the y axis) through the shear center; torsion is not checked. "
                                 "Bending about both axes is combined by AISC 360-22 Eq. H1-1b with Pr = 0.")
    if twist:
        from . import hss as _hss
        try:
            tc = _hss.torsion(props, Fy, span_ft * 12.0, method)
        except _hss.HSSError as e:
            raise WorksheetError(f"{mark}: {e}")
        torques = [dict(ld, w=ld["w"] * ld["e_in"]) if ld["kind"] == "uniform" else dict(ld, P=ld["P"] * ld["e_in"]) for ld in twist]
        worst_t = worst_ti = None
        sheet.assumptions.append("Torque is the load times its distance from the shear center; both ends are held against twisting, and the torque "
                                 "divides between them as a simple-span shear does. Where Tr is over 0.2 Tc, AISC 360-22 Eq. H3-6 is checked at every point "
                                 "along the span; elsewhere torsion is neglected (Sect. H3.2).")
        sheet.torsion_lines = tc.lines
    for cb in combos:
        res = _solve(span_ft, EI, all_loads, cb.factors)
        sheet.reactions[cb.name] = (res.reactions[0.0], res.reactions[float(span_ft)])
        Vmax = res.V_abs_max()[0]
        if segs is None:
            Mmax = float(np.max(np.abs(res.M)))
            cand = [(M_, chk, 0.0, 1.0, (0.0, span_ft)) for M_, chk in _signed(check, props, Fy, 0.0, 1.0, method, res.M, Mmax)]
        else:
            cand = []
            for a, b in segs:
                Cb, Mseg = _cb(res, a, b)
                sg = (res.x >= a - 1e-9) & (res.x <= b + 1e-9)
                cand += [(M_, chk, (b - a), Cb, (a, b)) for M_, chk in _signed(check, props, Fy, (b - a) * 12, Cb, method, res.M[sg], Mseg)]
        Mseg, chk, Lb, Cb, seg = max(cand, key=lambda c: c[0] / c[1].M_avail)
        m_row = Row("flexure", cb.name, Mseg, chk.M_avail / 12, "kip-ft",
                    "AISC 360-22 Ch. F: " + chk.governs,
                    f"Lb = {Lb:g} ft, Cb = {Cb:.2f}, segment {seg[0]:g} to {seg[1]:g} ft")
        v_row = Row("shear", cb.name, Vmax, chk.V_avail, "kip", getattr(chk, "v_source", "AISC 360-22 Sect. G2.1"))
        if worst_m is None or m_row.dc > worst_m[0].dc:
            worst_m = (m_row, chk, res)
        if worst_v is None or v_row.dc > worst_v.dc:
            worst_v = v_row
        if side and any(cb.factors.get(ld["case"], 0.0) for ld in side):
            rw = _solve(span_ft, EIy, side, cb.factors)
            My = float(np.max(np.abs(rw.M)))
            row_wm = Row("flexure, y axis (sideways loads)", cb.name, My, wk.available / 12, "kip-ft", "AISC 360-22 Sect. F6: " + wk.governs)
            row_wv = Row("shear, sideways loads", cb.name, rw.V_abs_max()[0], wv.available, "kip", "AISC 360-22 Sect. G6: " + wv.governs if props.get("type") not in ("HSS-RECT", "HSS-ROUND", "PIPE") else "AISC 360-22 Sect. G4, G5")
            # Eq. H1-1b with Pr = 0, at every station, each x moment against the strength of the segment it lies in
            My_x = np.interp(res.x, rw.x, np.abs(rw.M))
            best = (-1.0, 0.0, 0.0, 0.0, 0.0)
            for Mseg_, chk_, Lb_, Cb_, seg_ in cand:
                sel = (res.x >= seg_[0] - 1e-9) & (res.x <= seg_[1] + 1e-9)
                if not np.any(sel):
                    continue
                u = np.abs(res.M[sel]) / (chk_.M_avail / 12) + My_x[sel] / (wk.available / 12)
                i_ = int(np.argmax(u))
                if u[i_] > best[0]:
                    best = (float(u[i_]), float(res.x[sel][i_]), float(abs(res.M[sel][i_])), float(My_x[sel][i_]), chk_.M_avail / 12)
            row_h = Row("flexure about both axes", cb.name, best[0], 1.0, "", "AISC 360-22 Eq. H1-1b (Pr = 0)",
                        f"at {best[1]:.2f} ft: Mrx = {best[2]:.2f} kip-ft / Mcx = {best[4]:.2f}, Mry = {best[3]:.2f} kip-ft / Mcy = {wk.available / 12:.2f}")
            if worst_wm is None or row_wm.dc > worst_wm.dc:
                worst_wm = row_wm
            if worst_wv is None or row_wv.dc > worst_wv.dc:
                worst_wv = row_wv
            if worst_h is None or row_h.dc > worst_h.dc:
                worst_h = row_h
        if twist and any(cb.factors.get(ld["case"], 0.0) for ld in twist):
            rt = _solve(span_ft, EI, torques, cb.factors)
            Tmax = float(np.max(np.abs(rt.V)))
            row_t = Row("torsion", cb.name, Tmax, tc.available, "kip-in", "AISC 360-22 Eq. H3-1: " + tc.governs)
            if worst_t is None or row_t.dc > worst_t.dc:
                worst_t = row_t
            xs = np.unique(np.concatenate([np.linspace(0.0, span_ft, 1601), res.x, rt.x]))
            T_ = np.abs(np.interp(xs, rt.x, rt.V))
            if np.any(T_ > 0.2 * tc.available):
                Mx_ = np.abs(np.interp(xs, res.x, res.M))
                Vx_ = np.abs(np.interp(xs, res.x, res.V)) / chk.V_avail
                if side and any(cb.factors.get(ld["case"], 0.0) for ld in side):
                    My_ = np.abs(np.interp(xs, rw.x, rw.M)) / (wk.available / 12)
                    Vy_ = np.abs(np.interp(xs, rw.x, rw.V)) / wv.available
                else:
                    My_ = Vy_ = np.zeros_like(xs)
                Mc_ = np.full_like(xs, chk.M_avail / 12)
                for Mseg_, chk_, Lb_, Cb_, seg_ in cand:
                    sel_ = (xs >= seg_[0] - 1e-9) & (xs <= seg_[1] + 1e-9)
                    Mc_[sel_] = chk_.M_avail / 12
                u = Mx_ / Mc_ + My_ + (np.maximum(Vx_, Vy_) + T_ / tc.available) ** 2
                u[T_ <= 0.2 * tc.available] = 0.0
                k_ = int(np.argmax(u))
                row_ti = Row("torsion with shear and flexure", cb.name, float(u[k_]), 1.0, "", "AISC 360-22 Eq. H3-6 (Pr = 0)",
                             f"at {xs[k_]:.2f} ft: Mrx = {Mx_[k_]:.2f} kip-ft, Vr / Vc = {max(Vx_[k_], Vy_[k_]):.3f}, Tr = {T_[k_]:.1f} kip-in")
                if worst_ti is None or row_ti.dc > worst_ti.dc:
                    worst_ti = row_ti
    sheet.rows += [worst_m[0], worst_v]
    if side and worst_h is not None:
        sheet.rows += [worst_wm, worst_wv, worst_h]
    if twist:
        sheet.rows += [r_ for r_ in (worst_t, worst_ti) if r_ is not None]
    sheet.steps = worst_m[1].lines
    sheet.governing = dict(flexure=worst_m[0].combo, shear=worst_v.combo)
    r = worst_m[2]
    sheet.diagram = dict(x=r.x.tolist(), V=r.V.tolist(), M=r.M.tolist())

    for dc in defl_checks:
        if side and any(dc.factors.get(ld["case"], 0.0) for ld in side):
            rwd = _solve(span_ft, E * props["Iy"] / 144.0, side, dc.factors)
            sheet.rows.append(Row(f"deflection, {dc.label}, sideways", "+".join((f"{f:g}" if f != 1 else "") + c for c, f in dc.factors.items()),
                                  rwd.defl_max()[0] * 12, span_ft * 12 / dc.ratio, "in", dc.source, f"limit L/{dc.ratio:g}; E Iy = {E:.0f} x {props['Iy']:.3g}"))
            if not any(dc.factors.get(ld["case"], 0.0) for ld in all_loads):
                continue
        res = _solve(span_ft, EI, all_loads, dc.factors)
        d_in = res.defl_max()[0] * 12
        sheet.rows.append(Row(f"deflection, {dc.label}", "+".join(
            (f"{f:g}" if f != 1 else "") + c for c, f in dc.factors.items()), d_in,
            span_ft * 12 / dc.ratio, "in", dc.source, f"limit L/{dc.ratio:g}; E Ix = "
            f"{E:.0f} x {props['Ix']:.0f}"))
    if not defl_checks:
        sheet.assumptions.append("No deflection limit was given; deflection is not checked.")
    _bu_welds(sheet, props, method)
    if props.get("stiff"):
        _bu_stiffeners(mark, sheet, props, Fy, method, [(cb.name, _solve(span_ft, EI, all_loads, cb.factors)) for cb in combos], span_ft)
    if props.get("brg"):
        _bu_bearing(mark, sheet, props, Fy, method, [(cb.name, _solve(span_ft, EI, all_loads, cb.factors)) for cb in combos])
    return sheet


def _run_continuous(mark, shape, Fy, lay, all_loads, combos, defl_checks, segs, btxt, brace_pts, method, include_self_weight, props, check,
                    assumptions):
    """More than one span, or overhangs (contbeam.py): every arrangement of the live load cases
    on whole spans and overhangs (ASCE/SEI 7-22 Sect. 4.3.3) and the partial snow cases
    (Sect. 7.5.1); each unbraced segment is checked with its own Cb for the moment diagram
    of each arrangement. Supports are taken as brace points. Units inside: kips, in."""
    from . import contbeam
    L_ft = lay.total
    for ld in all_loads:
        if ld["kind"] == "point" and not (0 <= ld["x_ft"] <= L_ft + 1e-9):
            raise WorksheetError(f"{mark}: a point load is off the beam")
    by_case = {}
    for ld in all_loads:
        by_case.setdefault(ld["case"], []).append(ld)
    EI = E * props["Ix"]                                           # kip-in^2
    sheet = SteelBeamSheet(mark, shapes.normalize(shape), Fy, L_ft, method, props, all_loads, btxt, include_self_weight,
                           assumptions=assumptions, brace_points=brace_pts)
    sheet.span_text = lay.describe()
    sheet.supports = list(lay.supports)
    sheet.support_moment = {}
    sheet.fixed = lay.fixed
    whole = [(0.0, L_ft)]
    basis = contbeam.Basis(lay, EI, by_case)
    worst_m, worst_v, n_arr = None, None, 0
    for cb in combos:
        arrs = contbeam.arrangements(lay, by_case, cb.factors)
        first = True
        for _, items in arrs:
            res = basis.solve(items)
            if res is None:
                continue
            n_arr += 1
            if lay.fixed and res.fixed_moments:
                Mf = max(abs(v) for v in res.fixed_moments.values()) / 12.0
                sheet.support_moment[cb.name] = max(sheet.support_moment.get(cb.name, 0.0), Mf)
            if first:                                              # the arrangement with every span loaded comes first
                sheet.reactions[cb.name] = tuple(res.reactions[min(res.reactions, key=lambda k: abs(k - s_ * 12))] for s_ in lay.supports)
                first = False
            Vmax = float(np.max(np.abs(res.V)))
            for a, b in (segs if segs is not None else whole):
                m = (res.x >= a * 12 - 1e-6) & (res.x <= b * 12 + 1e-6)
                Mseg = float(np.max(np.abs(res.M[m]))) / 12.0      # kip-ft
                if segs is None:
                    Lb, Cb = 0.0, 1.0
                else:
                    xq = [(a + (b - a) * k) * 12 for k in (0.25, 0.5, 0.75)]
                    MA, MB, MC = (abs(float(np.interp(x, res.x, res.M))) for x in xq)
                    Lb, Cb = (b - a), (steel_beam.cb_factor(Mseg * 12, MA, MB, MC) if Mseg > 1e-9 else 1.0)
                    if lay.fixed and (a <= 1e-9 or b >= L_ft - 1e-9):
                        Cb = 1.0                                   # a segment that reaches the free end of a cantilever (Sect. F1)
                for Mseg_, chk in _signed(check, props, Fy, Lb * 12, Cb, method, res.M[m] / 12.0, Mseg):
                    row = Row("flexure", cb.name, Mseg_, chk.M_avail / 12, "kip-ft", "AISC 360-22 Ch. F: " + chk.governs,
                              f"Lb = {Lb:g} ft, Cb = {Cb:.2f}, segment {a:g} to {b:g} ft")
                    if worst_m is None or row.dc > worst_m[0].dc:
                        worst_m = (row, chk, res)
            v_row = Row("shear", cb.name, Vmax, chk.V_avail, "kip", getattr(chk, "v_source", "AISC 360-22 Sect. G2.1"))
            if worst_v is None or v_row.dc > worst_v.dc:
                worst_v = v_row
        if cb.name not in sheet.reactions:
            sheet.reactions[cb.name] = tuple(0.0 for _ in lay.supports)
    if worst_m is None:
        raise WorksheetError(f"{mark}: no load combination loads the beam")
    sheet.rows += [worst_m[0], worst_v]
    sheet.steps = worst_m[1].lines
    sheet.governing = dict(flexure=worst_m[0].combo, shear=worst_v.combo)
    r = worst_m[2]
    sheet.diagram = dict(x=(r.x / 12).tolist(), V=r.V.tolist(), M=(r.M / 12).tolist())
    for dc in defl_checks:
        w = contbeam.deflection(lay, EI, by_case, dc.factors, dc.ratio, basis=basis)
        if w is None:
            continue
        sheet.rows.append(Row(f"deflection, {dc.label}", "+".join((f"{f:g}" if f != 1 else "") + c for c, f in dc.factors.items()), w[0], w[1], "in",
                              dc.source, f"{w[2]}; limit {w[3]}; E Ix = {E:.0f} x {props['Ix']:.0f}"))
    if not defl_checks:
        sheet.assumptions.append("No deflection limit was given; deflection is not checked.")
    sheet.assumptions += [
        "Live load is placed on every combination of spans and overhangs and each check takes the worst arrangement (ASCE/SEI 7-22 Sect. 4.3.3); "
        "snow is placed by the partial loading cases of Sect. 7.5.1.",
        ("The compression flange is braced continuously, top or bottom, wherever it is in compression." if segs is None else
         "Each brace point and each support braces the compression flange, top or bottom, whichever is in compression there."),
        "Reactions shown are for every span loaded."]
    if lay.fixed:
        sheet.assumptions[-3:] = [
            "The beam is fixed to its one support (a column); the support takes the moment listed with the reactions, which is the largest over the arrangements "
            "of live and snow load on one cantilever or both (ASCE/SEI 7-22 Sect. 4.3.3, 7.5.1).",
            "The bottom flange is braced at the support and at the listed brace points only; Cb = 1.0 for a segment that reaches a free end (AISC 360-22 Sect. F1).",
            "Reactions shown are for both cantilevers loaded. The connection to the column and the column are checked separately."]
    _bu_welds(sheet, props, method)
    return sheet
