"""Steel column worksheet: one column under axial load, from loads to the check.

Ties together the Shapes Database (shapes.py) and the AISC 360-22 Chapter E strength
check (steel_column.py). Axial compression only: a column with moment, or with load
applied off its centre, is outside this worksheet and the sheet says so.

Nothing is defaulted: the effective length factors and where they come from, the
unbraced length about each axis, the load combinations, and whether self-weight is
included are all inputs, and each is printed.

Units: feet, kips, ksi.
"""
from dataclasses import dataclass, field

import math

import numpy as np

from . import beam, shapes, steel_beam, steel_beamcol, steel_column
from .steel_beam import Line
from .ws_steel_beam import Row, WorksheetError, _cb

E = steel_beam.E_STEEL
NOT_CHECKED = ["load applied off the centre of the column", "base plate and anchor rods",
               "connections at the top and bottom", "tension or uplift",
               "columns whose top can move sideways (cantilevered or moment-frame columns)"]


@dataclass
class SteelColumnSheet:
    mark: str
    shape: str
    Fy: float
    height_ft: float
    method: str
    props: dict
    loads: list                    # dicts: case, P (kips), label
    Lx_ft: float
    Ly_ft: float
    Kx: float
    Ky: float
    k_source: str
    totals: dict = field(default_factory=dict)         # combo name -> axial load, kips
    rows: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    governing: str = ""
    assumptions: list = field(default_factory=list)
    not_checked: list = field(default_factory=lambda: list(NOT_CHECKED))
    lateral: list = field(default_factory=list)        # dicts: case, bending, kind, w / P, x_ft
    combined: dict = field(default_factory=dict)       # combo name -> H1-1 value
    diagram: dict = field(default_factory=dict)        # x, Mx, My of the governing combo
    base: dict = field(default_factory=dict)           # combo -> P, Mx, My, Vx, Vy at the base (kips, kip-ft)
    sway: tuple = ()                                   # bending axes in which the top is free
    leaning: list = field(default_factory=list)        # dicts: case, P (load stabilised by this column)

    @property
    def ok(self):
        return all(r.status == "OK" for r in self.rows)


def _statics(height, brace, EI, lateral, axis, factors):
    """First-order shear and moment along the column for the loads bending it about
    one axis. The column is held sideways at its ends and at every brace point for
    that direction."""
    pts, dists = [], []
    for ld in lateral:
        f = factors.get(ld["case"], 0.0)
        if ld["bending"] != axis or f == 0:
            continue
        if ld["kind"] == "uniform":
            dists.append(beam.DistLoad(ld.get("x1_ft", 0.0), ld.get("x2_ft", height), f * ld["w"], f * ld["w"]))
        else:
            pts.append(beam.PointLoad(ld["x_ft"], f * ld["P"]))
    if not pts and not dists:
        return None
    n = max(1, int(round(height / brace)))
    sup = sorted({0.0, float(height)} | {brace * k for k in range(1, n) if brace * k < height - 1e-6})
    return beam.solve(height, sup, EI, point_loads=pts, dist_loads=dists), sup


def run(mark, shape, Fy, height_ft, loads, combos, Kx, Ky, k_source, method,
        include_self_weight, Lx_ft=None, Ly_ft=None, self_weight_case="D", lateral=(),
        sway=(), leaning=(), drift_checks=()):
    """Lx_ft and Ly_ft are the unbraced lengths for buckling about the x (strong) and
    y (weak) axes; left as None they are the full height. k_source says where Kx and Ky
    come from (for example "pinned top and bottom, braced frame")."""
    if method not in ("ASD", "LRFD"):
        raise WorksheetError("method must be ASD or LRFD")
    if not combos:
        raise WorksheetError(f"{mark}: no load combinations given")
    if include_self_weight not in (True, False):
        raise WorksheetError(f"{mark}: say whether self-weight is included (True or False)")
    if not k_source:
        raise WorksheetError(f"{mark}: say where the effective length factors come from")
    if Kx is None or Ky is None or Kx <= 0 or Ky <= 0:
        raise WorksheetError(f"{mark}: Kx and Ky must be given")
    for ld in loads:
        for k in ("case", "P"):
            if k not in ld:
                raise WorksheetError(f"{mark}: a load is missing '{k}'")
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    try:
        props = shapes.get(shape)
    except shapes.ShapeError:
        try:
            props = shapes.hss(shape)
        except shapes.ShapeError:
            raise WorksheetError(f"{mark}: shape '{shape}' is not in the {shapes.SOURCE} I-shape, HSS or pipe tables")
    Lx = height_ft if Lx_ft is None else Lx_ft
    Ly = height_ft if Ly_ft is None else Ly_ft
    all_loads = list(loads)
    assumptions = ["Load is applied along the centre of the column; no bending is considered."]
    if include_self_weight:
        sw = props["W"] * height_ft / 1000.0
        all_loads.append(dict(case=self_weight_case, P=sw,
                              label=f"self-weight {props['W']:.0f} lb/ft x {height_ft:g} ft"))
        assumptions.append(f"Column self-weight ({props['W']:.0f} lb/ft, {props.get('source') or shapes.SOURCE}) added "
                           f"to load case {self_weight_case}.")
    else:
        assumptions.append("Column self-weight is NOT added separately; it is taken as "
                           "included in the loads entered.")
    chk = steel_column.check(props, Fy, Kx * Lx * 12, Ky * Ly * 12, method=method)
    sheet = SteelColumnSheet(mark, shapes.normalize(shape), Fy, height_ft, method, props,
                             all_loads, Lx, Ly, Kx, Ky, k_source, assumptions=assumptions)
    for cb in combos:
        sheet.totals[cb.name] = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in all_loads)
    for cb in combos:
        sheet.base[cb.name] = dict(P=sheet.totals[cb.name], Mx=0.0, My=0.0, Vx=0.0, Vy=0.0)
    worst = max(sheet.totals, key=lambda k: sheet.totals[k])
    if sheet.totals[worst] <= 0:
        raise WorksheetError(f"{mark}: no combination puts the column in compression; "
                             "tension is not covered by this worksheet")
    sheet.governing = worst
    sheet.rows.append(Row("axial compression", worst, sheet.totals[worst], chk.P_avail, "kip",
                          "AISC 360-22 Ch. E: " + chk.governs,
                          f"Lcx = {Kx:g} x {Lx:g} ft, Lcy = {Ky:g} x {Ly:g} ft"))
    sheet.rows.append(Row("slenderness", "-", chk.slenderness, 200.0, "",
                          "AISC 360-22 Sect. E2 User Note (recommended limit, not a requirement)",
                          "governing Lc / r"))
    sheet.steps = list(chk.lines)
    if props.get("type") == "BU":
        sheet.not_checked.append("the flange-to-web welds of the built-up section")
    if sway:
        _sway(sheet, chk, list(lateral), combos, tuple(sway), list(leaning), list(drift_checks))
    elif leaning or drift_checks:
        raise WorksheetError(f"{mark}: leaning loads and drift checks apply only to a sway column")
    elif lateral:
        _lateral(sheet, chk, list(lateral), combos)
    else:
        sheet.assumptions.insert(0, "No sideways load is applied to the column.")
        sheet.not_checked.insert(0, "bending and shear (no lateral load was entered)")
    return sheet


def _lateral(sheet, chk, lateral, combos):
    """Sideways load on a column whose ends are held: shear, bending, the B1 increase
    in moment from the axial load, and the combined check of AISC 360-22 H1.1."""
    mark, pr, Fy, method, H = sheet.mark, sheet.props, sheet.Fy, sheet.method, sheet.height_ft
    for ld in lateral:
        for k in ("case", "bending", "kind"):
            if k not in ld:
                raise WorksheetError(f"{mark}: a lateral load is missing '{k}'")
        if ld["bending"] not in ("x", "y"):
            raise WorksheetError(f"{mark}: lateral load 'bending' must be x (strong axis) or y (weak axis)")
        if ld["kind"] not in ("uniform", "point"):
            raise WorksheetError(f"{mark}: lateral load kind must be uniform or point")
    sheet.lateral = lateral
    sheet.assumptions[0] = ("Axial load is applied along the centre of the column. The column is "
                            "held against sideways movement at its top, its base and its brace "
                            "points; the bracing itself is not designed here.")
    sheet.assumptions.append(
        "Second-order effects by the approximate method of AISC 360-22 Appendix 8 with the "
        "effective length method (Appendix 7.2): B1 from Eq. A-8-3 with Cm = 1.0 (App. 8.1.2(b)) "
        "and Pe1 from Eq. A-8-5 with EI. No sidesway, so B2 does not apply.")
    wy = steel_beamcol.weak_axis_flexure(pr, Fy, method)
    vy = steel_beamcol.weak_axis_shear(pr, Fy, method)
    best, outs = None, []
    sheet._outs = outs
    for cb in combos:
        P = sheet.totals[cb.name]
        if P < 0:
            raise WorksheetError(f"{mark}: combination {cb.name} puts the column in tension; not covered")
        out = dict(P=P, Mx=0.0, My=0.0, Vx=0.0, Vy=0.0, B1x=1.0, B1y=1.0, x=None, Cb=1.0,
                   Lb=sheet.Ly_ft)
        sx = _statics(H, sheet.Lx_ft, E * pr["Ix"] / 144.0, lateral, "x", cb.factors)
        sy = _statics(H, sheet.Ly_ft, E * pr["Iy"] / 144.0, lateral, "y", cb.factors)
        # strong-axis bending: lateral-torsional buckling between weak-axis brace points
        n = max(1, int(round(H / sheet.Ly_ft)))
        segs = sorted({0.0, float(H)} | {sheet.Ly_ft * k for k in range(1, n) if sheet.Ly_ft * k < H - 1e-6})
        fx = None
        if sx:
            res = sx[0]
            cand = []
            for a, b in zip(segs[:-1], segs[1:]):
                Cb, Mseg = _cb(res, a, b)
                c = steel_beam.check(pr, Fy, (b - a) * 12, Cb, method)
                cand.append((Mseg / (c.M_avail / 12) if c.M_avail else 0, Mseg, c, Cb, b - a))
            _, Mseg, fx, Cb, Lb = max(cand, key=lambda t: t[0])
            out.update(Mx=Mseg, Vx=res.V_abs_max()[0], Cb=Cb, Lb=Lb, x=res.x, mx=res.M)
            sheet.base[cb.name]["Vx"] = abs(float(res.reactions[0.0]))       # pinned base: shear only
            out["B1x"], out["Pe1x"] = steel_beamcol.b1(P, pr["Ix"], sheet.Lx_ft * 12, method)
        if sy:
            res = sy[0]
            out.update(My=float(np.max(np.abs(res.M))), Vy=res.V_abs_max()[0], x=res.x, my=res.M)
            sheet.base[cb.name]["Vy"] = abs(float(res.reactions[0.0]))
            out["B1y"], out["Pe1y"] = steel_beamcol.b1(P, pr["Iy"], sheet.Ly_ft * 12, method)
        out["fx"] = fx or steel_beam.check(pr, Fy, sheet.Ly_ft * 12, 1.0, method)
        out["Mrx"], out["Mry"] = out["B1x"] * out["Mx"], out["B1y"] * out["My"]
        out["val"], out["eq"] = steel_beamcol.interaction(
            P, chk.P_avail, out["Mrx"] * 12, out["fx"].M_avail, out["Mry"] * 12, wy.available)
        sheet.combined[cb.name] = out["val"]
        outs.append((cb.name, out))
        if best is None or out["val"] > best[1]["val"]:
            best = (cb.name, out)
    name, o = best
    fx = o["fx"]
    sheet.governing = name
    allo = sheet._outs
    rows = [sheet.rows[0]]

    def worst(key):
        return max(allo, key=lambda t: key(t[1]))

    if any(t[1]["Mx"] for t in allo):
        n1, q = worst(lambda t: t["Mrx"] * 12 / t["fx"].M_avail)
        rows.append(Row("bending about x (strong axis)", n1, q["Mrx"], q["fx"].M_avail / 12, "kip-ft",
                        "AISC 360-22 Ch. F: " + q["fx"].governs,
                        f"first-order {q['Mx']:.2f} kip-ft x B1 = {q['B1x']:.3f}; Lb = {q['Lb']:g} ft, "
                        f"Cb = {q['Cb']:.2f}"))
        n1, q = worst(lambda t: t["Vx"])
        rows.append(Row("shear, strong direction", n1, q["Vx"], fx.V_avail, "kip",
                        getattr(fx, "v_source", "AISC 360-22 Sect. G2.1"), getattr(fx, "v_note", "shear carried by the web")))
    if any(t[1]["My"] for t in allo):
        n1, q = worst(lambda t: t["Mry"])
        rows.append(Row("bending about y (weak axis)", n1, q["Mry"], wy.available / 12, "kip-ft",
                        getattr(wy, "prefix", "AISC 360-22 Sect. F6: ") + wy.governs,
                        f"first-order {q['My']:.2f} kip-ft x B1 = {q['B1y']:.3f}"))
        n1, q = worst(lambda t: t["Vy"])
        rows.append(Row("shear, weak direction", n1, q["Vy"], vy.available, "kip",
                        getattr(vy, "source", "AISC 360-22 Sect. G6"), getattr(vy, "note", "shear carried by the two flanges")))
    rows.append(Row("combined compression and bending", name, o["val"], 1.0, "",
                    f"AISC 360-22 Sect. H1.1, {o['eq']}",
                    f"Pr/Pc = {o['P'] / chk.P_avail:.3f}; Mrx/Mcx = {o['Mrx'] * 12 / fx.M_avail:.3f}; "
                    f"Mry/Mcy = {o['Mry'] * 12 / wy.available:.3f}"))
    sheet.rows = rows + sheet.rows[1:]
    L = sheet.steps
    L.append(Line("Pr, axial load", o["P"], "kip", "combination " + name))
    if o["Mx"]:
        L += [ln for ln in fx.lines if ln.label[:2] in ("Mp", "Lp", "Lr", "Mn")]
        L.append(Line("Pe1x = pi^2 E Ix / Lc1^2", o["Pe1x"], "kip", "Eq. A-8-5",
                      f"Lc1 = {sheet.Lx_ft:g} ft"))
        L.append(Line("B1x", o["B1x"], "", "Eq. A-8-3", "Cm = 1.0; alpha = "
                      + ("1.0" if method == "LRFD" else "1.6")))
        L.append(Line("Mrx = B1x Mx", o["Mrx"], "kip-ft", "Eq. A-8-1"))
    if o["My"]:
        L += wy.lines
        L.append(Line("Pe1y = pi^2 E Iy / Lc1^2", o["Pe1y"], "kip", "Eq. A-8-5",
                      f"Lc1 = {sheet.Ly_ft:g} ft"))
        L.append(Line("B1y", o["B1y"], "", "Eq. A-8-3", "Cm = 1.0"))
        L.append(Line("Mry = B1y My", o["Mry"], "kip-ft", "Eq. A-8-1"))
        L += vy.lines
    L.append(Line("combined ratio", o["val"], "", o["eq"], "limit 1.0"))
    if o["x"] is not None:
        zeros = [0.0] * len(o["x"])
        sheet.diagram = dict(x=list(map(float, o["x"])),
                             Mx=list(map(float, o.get("mx", zeros))),
                             My=list(map(float, o.get("my", zeros))))
    sheet.not_checked.append("sideways deflection of the column (no limit entered)")


def _check_lateral_inputs(mark, lateral):
    for ld in lateral:
        for k in ("case", "bending", "kind"):
            if k not in ld:
                raise WorksheetError(f"{mark}: a lateral load is missing '{k}'")
        if ld["bending"] not in ("x", "y"):
            raise WorksheetError(f"{mark}: lateral load 'bending' must be x (strong axis) or y (weak axis)")
        if ld["kind"] not in ("uniform", "point"):
            raise WorksheetError(f"{mark}: lateral load kind must be uniform or point")


def _sway(sheet, chk, lateral, combos, sway, leaning, drift_checks):
    """A column whose top is free to move sideways in one or both directions: fixed
    base, free top (cantilevered column, flagpole column).

    Stability by the direct analysis method, AISC 360-22 Chapter C:
      C2.1   second-order analysis including P-Delta and P-delta, done here with the
             geometric stiffness method (beam.solve), checked against the Commentary
             benchmark problems (Figs. C-C2.2, C-C2.3);
      C2.1(d) for ASD the analysis runs at 1.6 times the loads and results are divided
             by 1.6;
      C2.2b  notional load 0.002 alpha Y at the top, in gravity-only combinations, and in
             every combination when second-order drift exceeds 1.7 times first-order;
      C2.3   stiffness 0.8 tau_b EI;
      C3     effective length = unbraced length (K = 1).
    """
    mark, pr, Fy, method, H = sheet.mark, sheet.props, sheet.Fy, sheet.method, sheet.height_ft
    _check_lateral_inputs(mark, lateral)
    if not set(sway) <= {"x", "y"} or not sway:
        raise WorksheetError(f"{mark}: sway must name the bending axes (x, y) in which the top is free")
    if sheet.Kx != 1.0 or sheet.Ky != 1.0:
        raise WorksheetError(f"{mark}: a sway column is designed by the direct analysis method, which "
                             "uses K = 1.0 (AISC 360-22 C3). Enter Kx = Ky = 1.0.")
    for ld in leaning:
        if "case" not in ld or "P" not in ld:
            raise WorksheetError(f"{mark}: a leaning load needs 'case' and 'P'")
    for ax, L in (("x", sheet.Lx_ft), ("y", sheet.Ly_ft)):
        if ax in sway and abs(L - H) > 1e-9:
            raise WorksheetError(f"{mark}: the column is free at the top for bending about {ax}, so its "
                                 f"unbraced length for that axis must be the full height")
    sheet.lateral, sheet.sway, sheet.leaning = lateral, tuple(sway), leaning
    alpha = 1.0 if method == "LRFD" else 1.6
    Pns, pns_txt = Fy * pr["A"], "Pns = Fy Ag"
    if pr.get("type") in ("HSS-RECT", "HSS-ROUND", "PIPE"):
        from . import hss
        Pns, pns_txt = hss.pns(pr, Fy)
    I = {"x": pr["Ix"], "y": pr["Iy"]}
    brace = {"x": sheet.Lx_ft, "y": sheet.Ly_ft}
    wy = steel_beamcol.weak_axis_flexure(pr, Fy, method)
    vy = steel_beamcol.weak_axis_shear(pr, Fy, method)
    vx_avail = steel_beam.check(pr, Fy, sheet.Ly_ft * 12, 1.0, method).V_avail

    def loads_for(axis, factors, scale):
        pts, dists = [], []
        for ld in lateral:
            f = factors.get(ld["case"], 0.0) * scale
            if ld["bending"] != axis or f == 0:
                continue
            if ld["kind"] == "uniform":
                dists.append(beam.DistLoad(ld.get("x1_ft", 0.0), ld.get("x2_ft", H), f * ld["w"], f * ld["w"]))
            else:
                pts.append(beam.PointLoad(ld["x_ft"], f * ld["P"]))
        return pts, dists

    def supports(axis):
        if axis in sway:
            return [], [0.0]
        n = max(1, int(round(H / brace[axis])))
        return sorted({0.0, float(H)} | {brace[axis] * k for k in range(1, n)
                                         if brace[axis] * k < H - 1e-6}), []

    outs = []
    for cb in combos:
        P = sheet.totals[cb.name]
        if P < 0:
            raise WorksheetError(f"{mark}: combination {cb.name} puts the column in tension; not covered")
        Pl = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in leaning)
        r = alpha * P / Pns
        if r >= 1.0:
            raise WorksheetError(f"{sheet.mark}: combination {cb.name}: the axial load ({alpha:g} x {P:.1f} kips) reaches the cross-section strength "
                                 f"Pns = {Pns:.0f} kips; the column is too small")
        tau = 1.0 if r <= 0.5 else 4 * r * (1 - r)
        o = dict(P=P, Pl=Pl, tau=tau, M={"x": 0.0, "y": 0.0}, M1={"x": 0.0, "y": 0.0},
                 V={"x": 0.0, "y": 0.0}, N={}, ratio={}, res={}, Cb=1.0)
        for ax in ("x", "y"):
            pts, dists = loads_for(ax, cb.factors, alpha)
            sup, fix = supports(ax)
            EIr = 0.8 * tau * E * I[ax] / 144.0
            spr = [(float(H), -alpha * Pl / H)] if (ax in sway and Pl) else []
            N, why = 0.0, "not required: lateral load present and drift ratio <= 1.7 (C2.2b(d))"
            if ax in sway and not pts and not dists:
                N = 0.002 * alpha * (P + Pl)                       # C2.2b, gravity-only combination
                why = "0.002 Y; this combination has no lateral load in this direction (C2.2b)"
            elif not pts and not dists:
                continue

            def analyse(extra):
                p2 = pts + ([beam.PointLoad(float(H), extra)] if extra else [])
                first = beam.solve(H, sup, EIr, point_loads=p2, dist_loads=dists, fixed=fix)
                try:
                    second = beam.solve(H, sup, EIr, point_loads=p2, dist_loads=dists, fixed=fix,
                                        axial=alpha * P, springs=spr)
                except ValueError:
                    raise WorksheetError(
                        f"{mark}: combination {cb.name}: the column is unstable for bending about "
                        f"{ax} (the load reaches its buckling load with the reduced stiffness of "
                        "AISC 360-22 C2.3). Use a stiffer section.")
                return first, second

            first, second = analyse(N)
            if ax in sway:
                d1, d2 = float(first.defl[-1]), float(second.defl[-1])
                ratio = abs(d2 / d1) if d1 else 1.0
                if ratio > 1.7 and N == 0.0:                     # C2.2b(d): notional load in every combination
                    N = math.copysign(0.002 * alpha * (P + Pl), d1 or 1.0)
                    why = "0.002 Y; added to the lateral load because the drift ratio exceeds 1.7 (C2.2b(d))"
                    first, second = analyse(N)
                    d1, d2 = float(first.defl[-1]), float(second.defl[-1])
                    ratio = abs(d2 / d1) if d1 else 1.0
                o["ratio"][ax], o["N"][ax] = ratio, abs(N) / alpha
                o.setdefault("Nwhy", {})[ax] = why
            o["M"][ax] = float(np.max(np.abs(second.M))) / alpha
            o["M1"][ax] = float(np.max(np.abs(first.M))) / alpha
            o["V"][ax] = float(np.max(np.abs(second.V))) / alpha
            o["res"][ax] = second
            if ax in sway:                                         # fixed base: moment and shear, second-order
                sheet.base[cb.name]["M" + ax] = abs(float(second.fixed_moments[0.0])) / alpha
                sheet.base[cb.name]["V" + ax] = abs(float(first.reactions[0.0])) / alpha
            else:
                sheet.base[cb.name]["V" + ax] = abs(float(first.reactions[0.0])) / alpha
        # strong-axis flexural strength: lateral-torsional buckling
        if "y" in sway or o["res"].get("x") is None:
            Cb, Lb = 1.0, sheet.Ly_ft                              # F1: free end unbraced, Cb = 1.0
            fx = steel_beam.check(pr, Fy, Lb * 12, Cb, method)
        else:
            res = o["res"]["x"]
            n = max(1, int(round(H / sheet.Ly_ft)))
            segs = sorted({0.0, float(H)} | {sheet.Ly_ft * k for k in range(1, n) if sheet.Ly_ft * k < H - 1e-6})
            cand = []
            for a, b in zip(segs[:-1], segs[1:]):
                Cbs, Mseg = _cb(res, a, b)
                c = steel_beam.check(pr, Fy, (b - a) * 12, Cbs, method)
                cand.append((Mseg / c.M_avail, c, Cbs, b - a))
            _, fx, Cb, Lb = max(cand, key=lambda t: t[0])
        o.update(fx=fx, Cb=Cb, Lb=Lb)
        o["val"], o["eq"] = steel_beamcol.interaction(P, chk.P_avail, o["M"]["x"] * 12, fx.M_avail,
                                                      o["M"]["y"] * 12, wy.available)
        sheet.combined[cb.name] = o["val"]
        outs.append((cb.name, o))

    name, o = max(outs, key=lambda t: t[1]["val"])
    fx = o["fx"]
    sheet.governing = name
    rows = [sheet.rows[0]]

    def worst(key):
        return max(outs, key=lambda t: key(t[1]))

    def amp(q, ax):
        return f"second-order {q['M'][ax]:.2f} kip-ft (first-order {q['M1'][ax]:.2f} kip-ft)"

    if any(t[1]["M"]["x"] for t in outs):
        n1, q = worst(lambda t: t["M"]["x"] * 12 / t["fx"].M_avail)
        rows.append(Row("bending about x (strong axis)", n1, q["M"]["x"], q["fx"].M_avail / 12, "kip-ft",
                        "AISC 360-22 Ch. F: " + q["fx"].governs,
                        amp(q, "x") + f"; Lb = {q['Lb']:g} ft, Cb = {q['Cb']:.2f}"))
        n1, q = worst(lambda t: t["V"]["x"])
        rows.append(Row("shear, strong direction", n1, q["V"]["x"], vx_avail, "kip",
                        getattr(fx, "v_source", "AISC 360-22 Sect. G2.1"), getattr(fx, "v_note", "shear carried by the web")))
    if any(t[1]["M"]["y"] for t in outs):
        n1, q = worst(lambda t: t["M"]["y"])
        rows.append(Row("bending about y (weak axis)", n1, q["M"]["y"], wy.available / 12, "kip-ft",
                        getattr(wy, "prefix", "AISC 360-22 Sect. F6: ") + wy.governs, amp(q, "y")))
        n1, q = worst(lambda t: t["V"]["y"])
        rows.append(Row("shear, weak direction", n1, q["V"]["y"], vy.available, "kip",
                        getattr(vy, "source", "AISC 360-22 Sect. G6"), getattr(vy, "note", "shear carried by the two flanges")))
    rows.append(Row("combined compression and bending", name, o["val"], 1.0, "",
                    f"AISC 360-22 Sect. H1.1, {o['eq']}",
                    f"Pr/Pc = {o['P'] / chk.P_avail:.3f}; Mrx/Mcx = {o['M']['x'] * 12 / fx.M_avail:.3f}; "
                    f"Mry/Mcy = {o['M']['y'] * 12 / wy.available:.3f}"))
    for ax in sway:
        n1, q = worst(lambda t: t["ratio"].get(ax, 0.0))
        rows.append(Row(f"drift amplification, about {ax}", n1, q["ratio"][ax], 2.5, "",
                        "AISC 360-22 Commentary C1 (recommended limit, not a requirement)",
                        "sideways movement at the top with the axial load acting, divided by the "
                        "movement without it; stiffness 0.8 tau_b EI, loads x " + f"{alpha:g}"))
    # service drift at the top, when a limit is entered
    for dc in drift_checks:
        for ax in sway:
            pts, dists = loads_for(ax, dc.factors, 1.0)
            if not pts and not dists:
                continue
            d = beam.solve(H, [], E * I[ax] / 144.0, point_loads=pts, dist_loads=dists, fixed=[0.0])
            rows.append(Row(f"drift at top, {dc.label}, about {ax}", "+".join(
                (f"{f:g}" if f != 1 else "") + c for c, f in dc.factors.items()),
                abs(float(d.defl[-1])) * 12, H * 12 / dc.ratio, "in", dc.source,
                f"limit H/{dc.ratio:g}; first-order, full stiffness E I"))
    sheet.rows = rows + sheet.rows[1:]

    L = sheet.steps
    L.append(Line("Pr, axial load", o["P"], "kip", "combination " + name))
    if o["Pl"]:
        L.append(Line("load leaning on this column", o["Pl"], "kip", "combination " + name,
                      "carried by other columns; this column keeps them from moving sideways"))
    L.append(Line("alpha Pr / Pns", alpha * o["P"] / Pns, "", "Sect. C2.3(b)", f"{pns_txt} = {Pns:.0f} kip"))
    L.append(Line("tau_b", o["tau"], "", "Eq. C2-2a" if o["tau"] == 1.0 else "Eq. C2-2b",
                  "analysis stiffness = 0.8 tau_b E I (Sect. C2.3)"))
    for ax in ("x", "y"):
        if not o["M"][ax]:
            continue
        if ax in sway:
            L.append(Line(f"notional load at top, bending about {ax}", o["N"][ax], "kip", "Eq. C2-1",
                          o["Nwhy"][ax]))
            L.append(Line(f"drift ratio, bending about {ax}", o["ratio"][ax], "", "Sect. C2.1(b)",
                          "second-order / first-order movement at the top"))
        L.append(Line(f"M{ax}, first-order", o["M1"][ax], "kip-ft", "statics"))
        L.append(Line(f"Mr{ax}, second-order", o["M"][ax], "kip-ft", "Sect. C2.1(b), C2.1(d)",
                      f"increase x {o['M'][ax] / o['M1'][ax]:.3f}" if o["M1"][ax] else ""))
    if o["M"]["x"]:
        L += [ln for ln in fx.lines if ln.label[:2] in ("Mp", "Lp", "Lr", "Mn")]
    if o["M"]["y"]:
        L += wy.lines + vy.lines
    L.append(Line("combined ratio", o["val"], "", o["eq"], "limit 1.0"))
    x = next((r.x for r in o["res"].values()), None)
    if x is not None:
        zeros = np.zeros(len(x))
        sheet.diagram = dict(x=list(map(float, x)),
                             Mx=list(map(float, (o["res"]["x"].M if "x" in o["res"] else zeros) / alpha)),
                             My=list(map(float, (o["res"]["y"].M if "y" in o["res"] else zeros) / alpha)))
    free = " and ".join("x (strong axis)" if a == "x" else "y (weak axis)" for a in sway)
    sheet.assumptions[0] = ("Axial load is applied along the centre of the column. The base is fixed "
                            f"against rotation and the top is free to move sideways for bending about {free}. "
                            "The base connection and footing must be designed for the base moment; "
                            "they are not designed here.")
    sheet.assumptions.append(
        "Stability by the direct analysis method (AISC 360-22 Chapter C): second-order analysis "
        "including P-Delta and P-delta effects; stiffness 0.8 tau_b EI (C2.3); notional load "
        "0.002 Y at the top (C2.2b); K = 1.0 (C3)."
        + (" For ASD the analysis is run at 1.6 times the loads and the results divided by 1.6 "
           "(C2.1(d))." if method == "ASD" else ""))
    sheet.not_checked = [n for n in sheet.not_checked if "sideways" not in n and "move" not in n]
    sheet.not_checked += ["base plate, anchor rods and footing for the base moment",
                          "a top that moves sideways but is held against rotation (moment-frame column)"]
    if not drift_checks:
        sheet.not_checked.append("sideways drift at the top under service load (no limit entered)")
