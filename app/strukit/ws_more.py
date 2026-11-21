"""Worksheets for a column base plate and a footing with moment.

Both hand the calc sheet a SimpleSheet: the facts to print, the checks, and the name of
the picture to draw. Nothing is defaulted; see base_plate.py and footing_moment.py for the
calculations and their sources.
"""
from dataclasses import dataclass, field

from . import base_plate, footing, footing_moment, shapes
from .ws_steel_beam import Row, WorksheetError


@dataclass
class SimpleSheet:
    mark: str
    title: str                   # sheet title after the mark
    section: str                 # heading of the first block
    method: str                  # printed in the footer beside the code
    info: list                   # (label, text) pairs
    load_lines: list             # text lines
    combo_lines: list            # (text, source) pairs
    steps_title: str
    steps: list
    rows: list
    assumptions: list
    not_checked: list
    picture: tuple = ()          # (name, data) drawn by the calc sheet
    governing: str = ""

    @property
    def ok(self):
        return all(r.status == "OK" for r in self.rows)


def base_plate_sheet(mark, shape, N, B, t, Fy_plate, fc_psi, support, loads, combos, method):
    """shape: the column (its d and bf come from the Shapes Database). N: plate length
    parallel to the column depth; B: plate width; t: plate thickness provided.
    support: "full" when the plate covers the whole concrete support, or (length, width) of
    the support parallel to N and B. loads: dict(case, P) axial compression, kips."""
    if not combos:
        raise WorksheetError(f"{mark}: no load combinations given")
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    if support != "full" and (not isinstance(support, (tuple, list)) or len(support) != 2):
        raise WorksheetError(f"{mark}: support must be 'full' or the support's (length, width)")
    p = shapes.get(shape)
    totals = {cb.name: sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads) for cb in combos}
    worst = max(totals, key=lambda k: totals[k])
    A2 = N * B if support == "full" else base_plate.similar_area(N, B, support[0], support[1])
    res = base_plate.check(p["d"], p["bf"], N, B, Fy_plate, fc_psi / 1000.0, A2, totals[worst], method)
    rows = [Row("bearing on concrete", worst, totals[worst], res.P_avail, "kip",
                "AISC 360-22 Sect. J8, " + ("Eq. J8-1" if support == "full" else "Eq. J8-2"),
                f"A1 = {N * B:g} in2; A2 = {A2:g} in2"),
            Row("plate thickness", worst, res.t_min, t, "in",
                "AISC Manual Part 14, Eq. 14-2 to 14-7 (as printed in AISC Design Examples v16.0, Example J.6)",
                "demand is the minimum thickness, capacity is the thickness provided")]
    info = [("Column", f"{shapes.normalize(shape)}  (d = {p['d']:g} in, bf = {p['bf']:g} in)"),
            ("Plate", f"{N:g} in (along the column depth) x {B:g} in x {t:g} in thick, Fy = {Fy_plate:g} ksi"),
            ("Concrete", f"f'c = {fc_psi:,.0f} psi"),
            ("Support", "plate covers the full support" if support == "full" else
             f"{support[0]:g} in x {support[1]:g} in, plate centred on it")]
    return SimpleSheet(
        mark, "Column Base Plate", "Base Plate", method, info,
        [f"{ld['case']:<3} {ld['P']:.2f} kip" + (f"   ({ld['label']})" if ld.get("label") else "") for ld in loads],
        [(f"{cb.name:<18} P = {totals[cb.name]:.2f} kip" + ("   governs" if cb.name == worst else ""), cb.source)
         for cb in combos],
        "Bearing and Plate Thickness", res.lines, rows,
        ["The column load is centred on the plate and is compression only.",
         "The plate is centred on the concrete support. Grout strength is not counted."],
        ["moment, uplift or shear at the column base", "anchor rods (ACI 318-19 Chapter 17)",
         "weld of the column to the plate", "the concrete pedestal or footing itself"],
        picture=("base_plate", dict(d=p["d"], bf=p["bf"], tf=p["tf"], tw=p["tw"], N=N, B=B,
                                    support=None if support == "full" else tuple(support))),
        governing=worst)


def footing_moment_sheet(mark, soil_source, supported, limits_source="", **inp):
    """A footing with moment about one axis; see footing_moment.check_eccentric for inp.
    soil_source: where the allowable bearing pressure comes from. limits_source: where the
    overturning / sliding limits and friction coefficient come from (required when any of
    them is entered)."""
    if not soil_source or not str(soil_source).strip():
        raise WorksheetError(f"{mark}: give the source of the allowable soil bearing pressure")
    if supported not in ("wood", "steel", "concrete"):
        raise WorksheetError(f"{mark}: supported must be wood, steel or concrete")
    has_limits = any(inp.get(k) is not None for k in ("ot_required", "slide_mu", "slide_required"))
    if has_limits and not str(limits_source or "").strip():
        raise WorksheetError(f"{mark}: give the source of the overturning / sliding limits and friction coefficient")
    res = footing_moment.check_eccentric(**inp)
    rows = [Row(c.name, c.combo, c.demand, c.capacity, c.unit, c.source, c.note) for c in res.checks]
    i = inp
    sup = f"{i['col_x_in']:g} x {i['col_y_in']:g} in {supported} column"
    if i.get("plate_x_in"):
        sup += f" on {i['plate_x_in']:g} x {i['plate_y_in']:g} in base plate"
    info = [("Size", f"{i['B_ft']:g} ft (in the direction of the moment) x {i['L_ft']:g} ft x {i['h_in']:g} in thick"),
            ("Supports", sup),
            ("Reinforcing", f"({i['n_x']}) #{i['bar']} in x, ({i['n_y']}) #{i['bar']} in y, {i['cover_in']:g} in clear "
                            f"cover, {i.get('bottom_layer', 'x')}-direction bars lowest"),
            ("Concrete", f"f'c = {i['fc']:,.0f} psi, {i['conc_pcf']:g} pcf; bars fy = {i['fy']:,.0f} psi"),
            ("Soil", f"allowable bearing {i['q_allow_psf']:,.0f} psf ({soil_source})")]
    if i.get("soil_depth_ft"):
        info.append(("", f"{i['soil_depth_ft']:g} ft of soil over the footing at {i['soil_pcf']:g} pcf"))
    if has_limits:
        t = []
        if i.get("ot_required") is not None:
            t.append(f"overturning safety factor {i['ot_required']:g}")
        if i.get("slide_mu") is not None:
            t.append(f"sliding: friction {i['slide_mu']:g}, safety factor {i['slide_required']:g}")
        info.append(("Stability Limits", "; ".join(t) + f" ({limits_source})"))
    v = res.values
    loads = [f"Service   {c['name']:<22} P = {c['P']:>9,.0f} lb   M = {c['M']:>9,.0f} lb-ft   V = {c['V']:>7,.0f} lb"
             for c in i["service"]]
    loads += [f"Factored  {c['name']:<22} P = {c['P']:>9,.0f} lb   M = {c['M']:>9,.0f} lb-ft   V = {c['V']:>7,.0f} lb"
              f"   weight x {c['wt_factor']:g}" for c in i["strength"]]
    Line = footing_line
    steps = [Line("footing weight", v["W_ftg"], "lb", "geometry"),
             Line("soil over footing", v["W_soil"], "lb", "geometry"),
             Line("eccentricity, governing service case", v["e_service_in"], "in", "e = M / P at the underside",
                  f"B/6 = {i['B_ft'] * 2:.2f} in"),
             Line("soil bearing length", v["bearing_in"], "in", "statics", f"footing width {i['B_ft'] * 12:g} in"),
             Line("q max", v["q_max_psf"], "psf", "statics"), Line("q min", v["q_min_psf"], "psf", "statics"),
             Line("d, x direction", v["d_x"], "in", "geometry"), Line("d, y direction", v["d_y"], "in", "geometry"),
             Line("d for two-way shear", v["d_avg"], "in", "ACI 318-19 22.6.2.1")]
    return SimpleSheet(
        mark, "Isolated Footing with Moment", "Footing", "Strength design (LRFD)", info, loads, [],
        "Soil Pressure and Section Values", steps, rows,
        ["The footing is rigid and the soil takes no tension, so the soil pressure is a straight line.",
         "M and V act at the top of the footing; V times the footing thickness is added to M at the underside.",
         "Strength checks use the soil pressure caused by the factored loads (ACI 318-19 13.2.6.3)."] + list(res.notes),
        list(res.not_checked),
        picture=("footing_moment", dict(B=i["B_ft"] * 12, h=i["h_in"], col=i["col_x_in"], plate=i.get("plate_x_in"),
                                        supported=supported, cover=i["cover_in"], db=footing.BAR_DIA[i["bar"]],
                                        n=i["n_y"], soil=i.get("soil_depth_ft", 0) * 12, qmax=v["q_max_psf"],
                                        qmin=v["q_min_psf"], bearing=v["bearing_in"])))


def footing_line(label, value, unit, source, note=""):
    from .steel_beam import Line
    return Line(label, value, unit, source, note)


def base_plate_moment_sheet(mark, shape, N, B, t, Fy_plate, fc_psi, support, rod_d, rod_Fu, rod_source,
                            n_rods, rod_edge, rod_side_edge, n_shear, cases, method):
    """A column base that carries moment about the column's strong axis.

    N: plate length in the direction of the moment (parallel to the column depth); B: width.
    Anchor rods: n_rods on each of the two sides across the moment, rod_edge from the plate
    end, rod_side_edge from the plate sides; diameter rod_d, tensile strength rod_Fu (ksi)
    with rod_source saying where Fu comes from (for example "ASTM F1554 Grade 36").
    n_shear: how many rods are counted on to carry the base shear (0 = the rods do not
    carry shear; shear transfer is then not checked here).
    cases: dict(name, P, M, V) for each load combination at the level of `method`:
    P kips (compression positive), M kip-ft, V kips."""
    from . import bolts
    if method not in ("ASD", "LRFD"):
        raise WorksheetError("method must be ASD or LRFD")
    if not cases:
        raise WorksheetError(f"{mark}: no load cases given")
    if not str(rod_source or "").strip():
        raise WorksheetError(f"{mark}: give the anchor rod material (where Fu comes from)")
    if support != "full" and (not isinstance(support, (tuple, list)) or len(support) != 2):
        raise WorksheetError(f"{mark}: support must be 'full' or the support's (length, width)")
    if n_rods < 1 or rod_edge <= 0 or rod_edge >= N / 2:
        raise WorksheetError(f"{mark}: the rods must be between the plate end and the plate centre")
    p = shapes.get(shape)
    A1 = N * B
    A2 = A1 if support == "full" else base_plate.similar_area(N, B, support[0], support[1])
    k = 0.65 if method == "LRFD" else 1 / 2.31
    fc = fc_psi / 1000.0
    fp = k * 0.85 * fc * min((A2 / A1) ** 0.5, 2.0)
    f_rod = N / 2 - rod_edge
    grp = f"FU={rod_Fu:g}"
    Line = footing_line
    out = []
    for c in cases:
        for key in ("name", "P", "M", "V"):
            if c.get(key) is None:
                raise WorksheetError(f"{mark}: a load case is missing '{key}'")
        mc = base_plate.moment_case(c["name"], c["P"], c["M"] * 12, p["d"], p["bf"], N, B, f_rod, fp, Fy_plate,
                                    method, n_rods)
        per_rod = mc.T / n_rods
        v_rod = abs(c["V"]) / n_shear if n_shear else 0.0
        v_av = bolts.shear(rod_d, grp, "N", 1, method).R_avail
        if v_rod and v_rod < v_av:
            t_av = bolts.tension_with_shear(rod_d, grp, v_rod, "N", 1, method).R_avail
        else:
            t_av = bolts.tension(rod_d, grp, method).R_avail
        out.append(dict(c=c, mc=mc, per_rod=per_rod, t_av=t_av, v_rod=v_rod, v_av=v_av))
    rows = []
    plain = [o for o in out if not o["mc"].uplift]
    if plain:
        o = max(plain, key=lambda o: o["mc"].f_bearing)
        rows.append(Row("concrete bearing stress", o["c"]["name"], o["mc"].f_bearing, fp, "ksi",
                        "AISC 360-22 Sect. J8, " + ("Eq. J8-1" if support == "full" else "Eq. J8-2"),
                        f"no rod tension in this case; bearing over {o['mc'].Y:.2f} in of the {N:g} in plate"))
    lifted = [o for o in out if o["mc"].uplift]
    if lifted:
        o = max(lifted, key=lambda o: o["mc"].Y)
        rows.append(Row("bearing block length", o["c"]["name"], o["mc"].Y, f_rod + N / 2, "in",
                        "statics; bearing at the available stress of AISC 360-22 Sect. J8",
                        f"bearing stress {fp:.3f} ksi over this length; the limit is the distance from the "
                        "compression edge to the rods"))
    o = max(out, key=lambda o: o["mc"].t_req)
    rows.append(Row("plate thickness", o["c"]["name"], o["mc"].t_req, t, "in",
                    "AISC 360-22 Eq. F11-1 (Mn = Fy Z, Z = t^2/4); strips per Manual Eq. 14-2, 14-3",
                    f"governed by: {o['mc'].t_govern}; demand is the minimum thickness, capacity is the "
                    "thickness provided"))
    gov = max(out, key=lambda o: o["per_rod"] / o["t_av"])
    if gov["per_rod"] > 0:
        rows.append(Row("anchor rod tension", gov["c"]["name"], gov["per_rod"], gov["t_av"], "kip",
                        "AISC 360-22 Sect. J9, J3.7" + (", J3.8 (with shear)" if gov["v_rod"] else "")
                        + "; Table J3.2 threaded parts",
                        f"per rod, {n_rods} rod(s) on the tension side; total {gov['mc'].T:.2f} kip; steel strength only"))
    if n_shear:
        o = max(out, key=lambda o: o["v_rod"])
        rows.append(Row("anchor rod shear", o["c"]["name"], o["v_rod"], o["v_av"], "kip",
                        "AISC 360-22 Sect. J9, J3.7; Table J3.2 threaded parts, threads in the shear plane",
                        f"per rod, {n_shear} rod(s) counted on for shear; steel strength only"))
    g = gov["mc"]
    steps = [Line("A1 = N B", A1, "in2", "Sect. J8"), Line("A2", A2, "in2", "Sect. J8"),
             Line("available bearing stress, fp", fp, "ksi", "Sect. J8: phi_c = 0.65, Omega_c = 2.31",
                  "0.85 f'c sqrt(A2/A1), not more than 1.7 f'c"),
             Line("rods to plate centre, f", f_rod, "in", "geometry"),
             Line("eccentricity e = M / P", g.e if g.e != float("inf") else 0.0, "in", f"case {g.name}",
                  "no axial load" if g.e == float("inf") else f"bearing alone balances up to "
                  f"{N / 2 - max(gov['c']['P'], 0) / (2 * fp * B):.2f} in"),
             Line("bearing length, Y", g.Y, "in", "moments about the rod line"),
             Line("rod tension, T", g.T, "kip", "T = fp B Y - P"),
             Line("m = (N - 0.95 d) / 2", (N - 0.95 * p["d"]) / 2, "in", "Manual Eq. 14-2 (Design Example J.6)"),
             Line("n = (B - 0.8 bf) / 2", (B - 0.8 * p["bf"]) / 2, "in", "Manual Eq. 14-3"),
             Line("rods to bending line at the flange", f_rod - 0.95 * p["d"] / 2, "in", "geometry"),
             Line("t required", o_t := max(x["mc"].t_req for x in out), "in", "Eq. F11-1")]
    info = [("Column", f"{shapes.normalize(shape)}  (d = {p['d']:g} in, bf = {p['bf']:g} in), moment about its strong axis"),
            ("Plate", f"{N:g} in (in the direction of the moment) x {B:g} in x {t:g} in thick, Fy = {Fy_plate:g} ksi"),
            ("Anchor Rods", f"({2 * n_rods}) {rod_d:g} in diameter, {n_rods} each side, {rod_edge:g} in from the plate "
                            f"ends, {rod_side_edge:g} in from the sides; Fu = {rod_Fu:g} ksi ({rod_source})"),
            ("Shear", f"{n_shear} rod(s) counted on for shear" if n_shear else "not carried by the rods"),
            ("Concrete", f"f'c = {fc_psi:,.0f} psi; " + ("plate covers the full support" if support == "full" else
                                                         f"support {support[0]:g} in x {support[1]:g} in, plate centred"))]
    not_checked = ["anchorage of the rods in the concrete: breakout, pullout, side blowout, pryout (ACI 318-19 Chapter 17)",
                   "weld of the column to the plate", "the column flange and web at the base",
                   "moment about the column's weak axis", "all rods in tension (net uplift with little moment)"]
    if not n_shear:
        not_checked.insert(1, "transfer of the base shear (friction, shear lug or rods)")
    return SimpleSheet(
        mark, "Column Base Plate with Moment", "Base Plate", method, info,
        [f"{c['name']:<26} P = {c['P']:>8.2f} kip   M = {c['M']:>8.2f} kip-ft   V = {c['V']:>7.2f} kip" for c in cases], [],
        f"Bearing, Rod Tension and Plate Thickness ({gov['c']['name']})", steps, rows,
        ["The concrete bears on the plate at a uniform stress over a length Y from the compression edge; when "
         "bearing alone cannot balance the moment, the stress is the available bearing stress and the rods on "
         "the far side take tension. This is the usual rectangular-block model; it is built here from statics. "
         "AISC Design Guide 1, which describes it, is not on file.",
         "The tension in each rod is taken to spread at 45 degrees to the column flange when the plate is "
         "checked in bending (an engineering assumption, for the same reason).",
         "Rod strengths are steel strengths only. Grout strength is not counted."],
        not_checked,
        picture=("base_plate_moment", dict(d=p["d"], bf=p["bf"], tf=p["tf"], tw=p["tw"], N=N, B=B, n=n_rods,
                                           edge=rod_edge, side=rod_side_edge, rod_d=rod_d, Y=g.Y, T=g.T,
                                           t=t, case=g.name)),
        governing=gov["c"]["name"])
