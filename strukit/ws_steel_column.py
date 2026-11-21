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
        include_self_weight, Lx_ft=None, Ly_ft=None, self_weight_case="D", lateral=()):
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
    props = shapes.get(shape)
    Lx = height_ft if Lx_ft is None else Lx_ft
    Ly = height_ft if Ly_ft is None else Ly_ft
    all_loads = list(loads)
    assumptions = ["Load is applied along the centre of the column; no bending is considered."]
    if include_self_weight:
        sw = props["W"] * height_ft / 1000.0
        all_loads.append(dict(case=self_weight_case, P=sw,
                              label=f"self-weight {props['W']:.0f} lb/ft x {height_ft:g} ft"))
        assumptions.append(f"Column self-weight ({props['W']:.0f} lb/ft, {shapes.SOURCE}) added "
                           f"to load case {self_weight_case}.")
    else:
        assumptions.append("Column self-weight is NOT added separately; it is taken as "
                           "included in the loads entered.")
    chk = steel_column.check(props, Fy, Kx * Lx * 12, Ky * Ly * 12, method=method)
    sheet = SteelColumnSheet(mark, shapes.normalize(shape), Fy, height_ft, method, props,
                             all_loads, Lx, Ly, Kx, Ky, k_source, assumptions=assumptions)
    for cb in combos:
        sheet.totals[cb.name] = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in all_loads)
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
    if lateral:
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
            out["B1x"], out["Pe1x"] = steel_beamcol.b1(P, pr["Ix"], sheet.Lx_ft * 12, method)
        if sy:
            res = sy[0]
            out.update(My=float(np.max(np.abs(res.M))), Vy=res.V_abs_max()[0], x=res.x, my=res.M)
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
                        "AISC 360-22 Sect. G2.1", "shear carried by the web"))
    if any(t[1]["My"] for t in allo):
        n1, q = worst(lambda t: t["Mry"])
        rows.append(Row("bending about y (weak axis)", n1, q["Mry"], wy.available / 12, "kip-ft",
                        "AISC 360-22 Sect. F6: " + wy.governs,
                        f"first-order {q['My']:.2f} kip-ft x B1 = {q['B1y']:.3f}"))
        n1, q = worst(lambda t: t["Vy"])
        rows.append(Row("shear, weak direction", n1, q["Vy"], vy.available, "kip",
                        "AISC 360-22 Sect. G6", "shear carried by the two flanges"))
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
