"""Worksheets for a column base plate and a footing with moment.

Both hand the calc sheet a SimpleSheet: the facts to print, the checks, and the name of
the picture to draw. Nothing is defaulted; see base_plate.py and footing_moment.py for the
calculations and their sources.
"""
from dataclasses import dataclass, field

from . import anchorage as anch, base_plate, footing, footing_moment, shapes, shearwall, snow, wind
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
    blocks: list = field(default_factory=list)   # further calculation blocks: dict(title, steps, picture, lead)

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
                            n_rods, rod_edge, rod_side_edge, n_shear, cases, method, anchorage=None,
                            cases_factored=None):
    """A column base that carries moment about the column's strong axis.

    N: plate length in the direction of the moment (parallel to the column depth); B: width.
    Anchor rods: n_rods on each of the two sides across the moment, rod_edge from the plate
    end, rod_side_edge from the plate sides; diameter rod_d, tensile strength rod_Fu (ksi)
    with rod_source saying where Fu comes from (for example "ASTM F1554 Grade 36").
    n_shear: how many rods are counted on to carry the base shear (0 = the rods do not
    carry shear; shear transfer is then not checked here).
    cases: dict(name, P, M, V) for each load combination at the level of `method`:
    P kips (compression positive), M kip-ft, V kips.
    anchorage: None to leave the rods' anchorage in the concrete unchecked, or the inputs
    of _anchorage below. cases_factored: the same load cases under the LRFD combinations
    (ACI 318-19 Chapter 17 is strength design); not needed when method is LRFD."""
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
                                    method, n_rods, p["tf"])
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
                        "AISC Design Guide 1 (3rd Ed.) Eq. 4-58; bearing at the available stress of AISC 360-22 Sect. J8",
                        f"bearing stress {fp:.3f} ksi over this length; the limit is the distance from the "
                        "compression edge to the rods"))
    o = max(out, key=lambda o: o["mc"].t_req)
    rows.append(Row("plate thickness", o["c"]["name"], o["mc"].t_req, t, "in",
                    "AISC Design Guide 1 (3rd Ed.) Eq. 4-47 to 4-50, 4-60, 4-61; AISC 360-22 Eq. F11-1",
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
             Line("bearing length, Y", g.Y, "in", "DG1 Eq. 4-42 or 4-58"),
             Line("rod tension, T = q_max Y - P", g.T, "kip", "DG1 Eq. 4-55"),
             Line("m = (N - 0.95 d) / 2", (N - 0.95 * p["d"]) / 2, "in", "DG1 Eq. 4-10"),
             Line("n = (B - 0.8 bf) / 2", (B - 0.8 * p["bf"]) / 2, "in", "DG1 Eq. 4-11"),
             Line("x = f - d/2 + tf/2", g.x, "in", "DG1 Eq. 4-61", "rods to the centre of the column flange"),
             Line("plate width resisting the rod tension", g.b_eff, "in", "DG1 Sect. 4.3.2 item 4",
                  "45 degree distribution from each rod, not more than B"),
             Line("t required", o_t := max(x["mc"].t_req for x in out), "in", "DG1 Eq. 4-51, 4-52, 4-62")]
    info = [("Column", f"{shapes.normalize(shape)}  (d = {p['d']:g} in, bf = {p['bf']:g} in), moment about its strong axis"),
            ("Plate", f"{N:g} in (in the direction of the moment) x {B:g} in x {t:g} in thick, Fy = {Fy_plate:g} ksi"),
            ("Anchor Rods", f"({2 * n_rods}) {rod_d:g} in diameter, {n_rods} each side, {rod_edge:g} in from the plate "
                            f"ends, {rod_side_edge:g} in from the sides; Fu = {rod_Fu:g} ksi ({rod_source})"),
            ("Shear", f"{n_shear} rod(s) counted on for shear" if n_shear else "not carried by the rods"),
            ("Concrete", f"f'c = {fc_psi:,.0f} psi; " + ("plate covers the full support" if support == "full" else
                                                         f"support {support[0]:g} in x {support[1]:g} in, plate centred"))]
    not_checked = ["anchorage of the rods in the concrete: breakout, pullout, side blowout, pryout (ACI 318-19 Chapter 17)"
                   if anchorage is None else None,
                   "weld of the column to the plate", "the column flange and web at the base",
                   "moment about the column's weak axis", "all rods in tension (net uplift with little moment)"]
    not_checked = [x for x in not_checked if x]
    if not n_shear:
        not_checked.insert(1, "transfer of the base shear (friction, shear lug or rods)")
    extra = None
    if anchorage is not None:
        extra = _anchorage(mark, p, N, B, support, fc_psi, rod_d, rod_Fu, n_rods, rod_edge, rod_side_edge, n_shear,
                           cases if method == "LRFD" else cases_factored, Fy_plate, anchorage)
        rows += extra["rows"]
        not_checked += extra["not_checked"]
    sheet = SimpleSheet(
        mark, "Column Base Plate with Moment", "Base Plate", method, info,
        [f"{c['name']:<26} P = {c['P']:>8.2f} kip   M = {c['M']:>8.2f} kip-ft   V = {c['V']:>7.2f} kip" for c in cases], [],
        f"Bearing, Rod Tension and Plate Thickness ({gov['c']['name']})", steps, rows,
        ["Method: AISC Design Guide 1, 3rd Ed. (2024), Sect. 4.3.7. The concrete bears on the plate at a uniform "
         "stress over a length Y from the compression edge; when bearing alone cannot balance the moment, the stress "
         "is the available bearing stress and the rods on the far side take tension.",
         "Plate bending from the rod tension uses the lesser of the full plate width (Eq. 4-60) and a 45 degree "
         "distribution from each rod to the column flange (Sect. 4.3.2).",
         "Rod strengths are steel strengths only. Grout strength is not counted."],
        not_checked,
        picture=("base_plate_moment", dict(d=p["d"], bf=p["bf"], tf=p["tf"], tw=p["tw"], N=N, B=B, n=n_rods,
                                           edge=rod_edge, side=rod_side_edge, rod_d=rod_d, Y=g.Y, T=g.T,
                                           t=t, case=g.name)),
        governing=gov["c"]["name"])
    if extra:
        sheet.load_lines += extra["load_lines"]
        sheet.assumptions += extra["assumptions"]
        sheet.blocks.append(extra["block"])
    return sheet


def _anchorage(mark, p, N, B, support, fc_psi, rod_d, rod_Fu, n_rods, rod_edge, rod_side, n_shear, cases, Fy_plate, a):
    """Anchorage of the rods of a base plate with moment in the concrete, ACI 318-19
    Chapter 17 (see anchorage.py). a: dict with hef, ha, nt (threads per inch), fya, ductile,
    Abrg, head (text describing the head), cracked, supplementary, edge_reinf (0, 1, 2),
    grout, sdc (text). cases: the factored (LRFD) load cases."""
    need = ("hef", "ha", "nt", "fya", "ductile", "Abrg", "head", "cracked", "supplementary", "edge_reinf", "grout", "sdc")
    gone = [k for k in need if a.get(k) is None]
    if gone:
        raise WorksheetError(f"{mark}: rod anchorage is missing: " + ", ".join(gone))
    if str(a["sdc"]).strip().upper() not in ("A", "B", "A OR B"):
        raise WorksheetError(f"{mark}: rod anchorage in Seismic Design Category C to F needs ACI 318-19 Sect. 17.10, "
                             "which is not built")
    if not cases:
        raise WorksheetError(f"{mark}: rod anchorage needs the load cases under the LRFD combinations "
                             "(ACI 318-19 Chapter 17 is strength design, Sect. 17.4)")
    if n_shear not in (0, n_rods, 2 * n_rods):
        raise WorksheetError(f"{mark}: for the anchorage check the rods counted on for shear must be 0, {n_rods} (one row) "
                             f"or {2 * n_rods} (both rows)")
    sup = (N, B) if support == "full" else support
    c_end = (sup[0] - N) / 2 + rod_edge
    c_side = (sup[1] - B) / 2 + rod_side
    s_rows = N - 2 * rod_edge
    s_row = (B - 2 * rod_side) / (n_rods - 1) if n_rods > 1 else 0.0
    try:
        res = anch.check(rod_d, a["nt"], rod_Fu, a["fya"], a["ductile"], a["hef"], a["Abrg"], fc_psi, a["ha"], n_rods,
                         s_row, s_rows, c_end, c_side, a["cracked"], a["supplementary"], a["edge_reinf"], a["grout"],
                         n_shear // n_rods)
    except anch.AnchorageError as e:
        raise WorksheetError(f"{mark}: {e}")
    A1 = N * B
    A2 = A1 if support == "full" else base_plate.similar_area(N, B, support[0], support[1])
    fp = 0.65 * 0.85 * fc_psi / 1000.0 * min((A2 / A1) ** 0.5, 2.0)
    f_rod = N / 2 - rod_edge
    runs, loads = [], []
    for c in cases:
        for key in ("name", "P", "M", "V"):
            if c.get(key) is None:
                raise WorksheetError(f"{mark}: a factored load case is missing '{key}'")
        mc = base_plate.moment_case(c["name"], c["P"], c["M"] * 12, p["d"], p["bf"], N, B, f_rod, fp, Fy_plate, "LRFD", n_rods, p["tf"])
        dem, inter, rt, rv = anch.demands(res, mc.T, c["V"])
        runs.append(dict(c=c, T=mc.T, dem=dem, inter=inter, rt=rt, rv=rv))
        loads.append(f"{c['name']:<26} Pu = {c['P']:>7.2f} kip   Mu = {c['M']:>7.2f} kip-ft   Vu = {c['V']:>6.2f} kip   "
                     f"row tension = {mc.T:>6.2f} kip")
    rows = []
    for i, m in enumerate(res.modes):
        r = max(runs, key=lambda r: r["dem"][i][2])
        d = r["dem"][i][1]
        if d <= 0:
            continue
        rows.append(Row("ACI " + m.label, r["c"]["name"], d, m.design, "kip", m.source,
                        f"phi = {m.phi:g}, nominal {m.Rn:.2f} kip; {m.note}"))
    both = [r for r in runs if r["inter"] is not None]
    if both:
        r = max(both, key=lambda r: r["inter"])
        rows.append(Row("ACI tension + shear", r["c"]["name"], r["inter"], 1.2, "", "ACI 318-19 Eq. 17.8.3",
                        f"tension ratio {r['rt']:.2f} + shear ratio {r['rv']:.2f}, each for its governing strength"))
    spc = [x for x in (s_row if n_rods > 1 else None, s_rows) if x]
    rows.append(Row("ACI rod spacing, minimum", "all", 4 * rod_d, min(spc), "in",
                    "ACI 318-19 Table 17.9.2(a), cast-in anchors not torqued",
                    "demand is the minimum spacing 4 da; capacity is the least spacing provided"))
    steps = list(res.lines)
    g = max(runs, key=lambda r: max(r["rt"], r["rv"]))
    steps.append(footing_line(f"row tension, {g['c']['name']}", g["T"], "kip", "statics at the factored loads",
                              "same bearing-block model, bearing at phi 0.65 x 0.85 f'c sqrt(A2/A1)"))
    crk = "cracked at service load" if a["cracked"] else "uncracked at service load"
    er = ("no edge reinforcement counted", "No. 4 or larger between the rods and the edge",
          "No. 4 or larger between the rods and the edge, in stirrups at 4 in. or less")[a["edge_reinf"]]
    info = [("Rod Anchorage", f"cast-in, embedment hef = {a['hef']:g} in to the head; {a['head']} (Abrg = {a['Abrg']:.3f} in2); "
                              f"{a['nt']:g} threads per inch; Fy = {a['fya']:g} ksi; "
                              f"{'ductile' if a['ductile'] else 'brittle'} steel element (ACI 318-19 Ch. 2)"),
            ("Concrete at Rods", f"{a['ha']:g} in thick; {crk}; supplementary reinforcement "
                                 f"{'present' if a['supplementary'] else 'not present'}; {er}; "
                                 f"{'grout pad under the plate' if a['grout'] else 'no grout pad'}; Seismic Design Category {a['sdc']}")]
    assumptions = [
        "Rod anchorage is checked for the factored (LRFD) load cases; ACI 318-19 Chapter 17 is strength design. The row "
        "tension for each case comes from the same bearing-block model as the plate, with bearing at the LRFD stress.",
        "Anchorage: normalweight concrete (lambda_a = 1.0, Table 17.2.4.1); rods cast in with a head or nut, not torqued; "
        "the plate is centred on the concrete; anchor reinforcement is not counted; the moment and the shear act toward "
        "the end of the concrete.",
        "Shear breakout follows the load-distribution cases of ACI 318-19 Fig. R17.7.2.1b for rods not welded to the plate."]
    if not both:
        assumptions.append("Anchorage: tension and shear interaction is neglected under ACI 318-19 17.8.2; the tension "
                           "ratio or the shear ratio is 0.2 or less in every load case.")
    assumptions += ["Anchorage: " + n for n in res.notes]
    return dict(rows=rows, load_lines=["Factored load cases for the rod anchorage:"] + loads,
                assumptions=assumptions,
                not_checked=["edge cover of the rods (ACI 318-19 17.9.2 refers to 20.5.1.3)",
                             "anchor reinforcement (17.5.2.1)", "hooked rods"],
                block=dict(title="Rod Anchorage in the Concrete (ACI 318-19 Chapter 17)", steps=steps, info=info,
                           picture=("anchorage", dict(N=N, B=B, sup_N=sup[0], sup_B=sup[1], n=n_rods, edge=rod_edge,
                                                      side=rod_side, rod_d=rod_d, hef=a["hef"], ha=a["ha"],
                                                      c_end=c_end, c_side=c_side, s_row=s_row, s_rows=s_rows))))


def snow_sheet(mark, pg, pg_source, risk, roughness, exposure, thermal, roof_type, rise_on_12, slippery, W_ft,
               r_roof=None, W2=None, W2_source=None, simple_members=None):
    """Roof snow load sheet, ASCE/SEI 7-22 Chapter 7 (see snow.py). pg_source and W2_source
    say where the site values come from (the ASCE 7 Hazard Tool query, or the
    jurisdiction's table)."""
    if not (pg_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the ground snow load is blank")
    try:
        r = snow.roof(pg, risk, roughness, exposure, thermal, roof_type, rise_on_12, slippery, W_ft, r_roof, W2,
                      simple_members)
    except snow.SnowError as e:
        raise WorksheetError(f"{mark}: {e}")
    u = r.unbalanced
    if u.get("surcharge") and not (W2_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the winter wind parameter W2 is blank")
    roof_txt = ("gable or hip" if roof_type == "gable" else "monoslope") + f", {rise_on_12:g} on 12 ({r.slope_deg:.1f} deg); " \
        + (f"eave to ridge W = {W_ft:g} ft" if roof_type == "gable" else f"eave to upper edge W = {W_ft:g} ft") \
        + "; " + ("unobstructed slippery surface" if slippery else "surface not slippery, or obstructed")
    info = [("Ground Snow", f"pg = {pg:g} psf, Risk Category {risk} ({pg_source.strip()})"),
            ("Exposure", f"surface roughness {roughness}; roof {exposure}"),
            ("Thermal", thermal + (f"; roof R-value {r_roof:g} h ft2 F/Btu" if thermal == snow.HEATED else "")),
            ("Roof", roof_txt)]
    if u.get("surcharge"):
        info.append(("Winter Wind", f"W2 = {W2:g} ({W2_source.strip()})"))
    loads = [f"Balanced snow load                    {r.balanced:7.1f} psf   on the horizontal projection"
             + ("   (includes 8 psf rain-on-snow)" if r.rain_on_snow else "")]
    if r.pm:
        loads.append(f"Minimum snow load, separate case      {r.pm:7.1f} psf")
    if u:
        if u["surcharge"]:
            loads.append(f"Unbalanced: windward {u['windward']:.1f} psf; leeward {u['leeward']:.1f} psf plus {u['surcharge']:.1f} psf "
                         f"for {u['extent']:.1f} ft from the ridge")
        else:
            loads.append(f"Unbalanced: windward 0 psf; leeward {u['leeward']:.1f} psf")
    elif roof_type == "gable":
        loads.append("Unbalanced load not required for this slope (Sect. 7.6.1)")
    assumptions = ["Snow loads act on the horizontal projection of the roof (Sect. 7.4).",
                   "The minimum snow load is a separate uniform case; it is not combined with unbalanced, drift or "
                   "sliding loads (Sect. 7.3.3)."] if r.pm else ["Snow loads act on the horizontal projection of the roof (Sect. 7.4)."]
    if u:
        assumptions.append("Balanced and unbalanced loads are separate cases, with the wind from either direction (Sect. 7.6).")
    sheet = SimpleSheet(
        mark, "Roof Snow Load", "Site and Roof", "Chapter 7", info, [], [], "Roof Snow Load", r.lines, [],
        assumptions,
        ["drifts at roof steps, parapets and projections (Sect. 7.7, 7.8)", "sliding snow from a higher roof (Sect. 7.9)",
         "partial loading of continuous members (Sect. 7.5)", "ice dams and icicles at eaves (Sect. 7.4.4)",
         "ponding instability (Sect. 7.11)"])
    sheet.blocks.append(dict(title="Design Snow Loads", head="Design Snow Loads", steps=[], text=loads,
                             picture=("snow", dict(roof=roof_type, W=W_ft, rise=rise_on_12, balanced=r.balanced,
                                                   pm=r.pm, unb=u))))
    sheet.snow = r
    return sheet


def shear_wall_sheet(mark, panel, spacing, panel_type, G, G_source, h, lengths, V, load, method, v_source, holddown_inside=None,
                     arm_offset_in=0.0, chord_E=None, chord_A=None, anchor_slip_in=None, sides=1, blocked=True, stud_spacing=None,
                     field_nails=None, dead_plf=0.0, dead_factor=None, dead_source=""):
    """Wood structural panel shear wall line, SDPWS-2021 Sect. 4.3 (see shearwall.py).
    V is the design shear on the line at the level of `method`; v_source says where it
    comes from. G_source says where the framing specific gravity comes from."""
    for nm, v in (("the source of the framing specific gravity", G_source), ("the source of the design shear", v_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if dead_plf and not (dead_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the dead load and its factor is blank")
    if V is None or V <= 0:
        raise WorksheetError(f"{mark}: the design shear must be a positive number")
    try:
        w = shearwall.line(panel, spacing, panel_type, G, h, lengths, V, load, method, holddown_inside, arm_offset_in,
                           chord_E, chord_A, anchor_slip_in, sides, blocked, stud_spacing, field_nails, dead_plf or 0.0, dead_factor)
    except shearwall.ShearWallError as e:
        raise WorksheetError(f"{mark}: {e}")
    rows = [Row("shear in the wall line", f"{load}, {method}", V, w.capacity, "lb", "SDPWS-2021 4.1.4, Table 4.3A, 4.3.5.5.1",
                f"nominal {w.design_text}; sum of {len(w.segments)} segment(s)")]
    info = [("Sheathing", f"wood structural panels, {panel}, {panel_type}, {'both sides' if sides == 2 else 'one side'}, "
             + ("blocked" if blocked else f"unblocked, studs at {stud_spacing:g} in") + f"; edge nails at {spacing:g} in"
             + ("" if blocked else f", intermediate nails at {field_nails:g} in")),
            ("Framing", f"specific gravity G = {G:g} ({G_source.strip()})"),
            ("Wall", f"{h:g} ft high; full-height segments " + ", ".join(f"{b:g} ft" for b in lengths)),
            ("Design Shear", f"{V:,.0f} lb, {load}, {method} ({v_source.strip()})"),
            ("Overturning", (f"moment arm = segment length less {arm_offset_in:g} in" if arm_offset_in else "moment arm = segment length")
             + (f"; dead load {dead_plf:g} plf x {dead_factor:g} ({dead_source.strip()})" if dead_plf else ""))]
    if chord_E and chord_A and anchor_slip_in is not None:
        info.append(("Deflection", f"end posts A = {chord_A:g} in2, E = {chord_E:,.0f} psi; anchorage slip {anchor_slip_in:g} in"))
    text = [f"Segment {i}: {s.b:>5g} ft   shear {s.V:>7,.0f} lb ({s.v:>4.0f} plf)   chord tension {s.T:>7,.0f} lb, compression {s.C:>7,.0f} lb"
            + (f"   deflection {s.defl:.2f} in" if s.defl is not None else "") for i, s in enumerate(w.segments, 1)]
    sheet = SimpleSheet(
        mark, "Wood Shear Wall", "Wall Line", f"{load}, {method}", info, [], [], "Capacity and Forces", w.lines, rows,
        ["Individual full-height segments; the shear is shared in proportion to the design capacities of the segments "
         "(SDPWS 4.3.5.5.1, exception 1).",
         ("Chord tension is the overturning force less the factored dead load on the segment, taken at mid-length. Chord "
          "compression is from overturning alone; gravity load is not added." if dead_plf else
          "Chord forces are from overturning of each segment alone; dead load is not counted against uplift.")],
        ["hold-down and its connection", "gravity load in the compression chord" if dead_plf else "dead load resisting uplift", "anchor bolts and plate washers (SDPWS 4.3.6.4.3)",
         "end posts in tension and compression; bearing on the plate", "collectors and the connection to the diaphragm",
         "construction requirements of SDPWS 4.3.6 and 4.3.7.1, including 3 in. framing at close nailing"]
        + ([] if w.segments[0].defl is not None else ["deflection (SDPWS 4.3.4)"]))
    sheet.blocks.append(dict(title="Segment Forces", head="Segment Forces", steps=[], text=text,
                             picture=("shear_wall", dict(h=h, segs=[dict(b=s.b, V=s.V, v=s.v, T=s.T, C=s.C) for s in w.segments], V=V))))
    sheet.wall = w
    return sheet


def perforated_wall_sheet(mark, panel, spacing, panel_type, G, G_source, h, length, openings, V, load, method, v_source,
                          holddown_inside=None, sides=1, chord_E=None, chord_A=None, anchor_slip_in=None):
    """Perforated wood structural panel shear wall, SDPWS-2021 (see shearwall.perforated).
    openings: dicts x, w, h (clear height), sill (for the drawing; 0 for a door), ft."""
    for nm, v in (("the source of the framing specific gravity", G_source), ("the source of the design shear", v_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if V is None or V <= 0:
        raise WorksheetError(f"{mark}: the design shear must be a positive number")
    try:
        w = shearwall.perforated(panel, spacing, panel_type, G, h, length, [(o["x"], o["w"], o["h"]) for o in openings], V, load, method,
                                 holddown_inside, sides, chord_E, chord_A, anchor_slip_in)
    except shearwall.ShearWallError as e:
        raise WorksheetError(f"{mark}: {e}")
    for o in openings:
        if (o.get("sill") or 0.0) + o["h"] > h + 1e-9:
            raise WorksheetError(f"{mark}: an opening's sill height plus its clear height is more than the wall height")
    rows = [Row("shear in the wall", f"{load}, {method}", V, w.capacity, "lb", "SDPWS-2021 4.3.5.6, Eq. 4.3-5, 4.1.4",
                f"Co = {w.Co:.3f}; sum of segment lengths {w.sum_b:.2f} ft")]
    info = [("Sheathing", f"wood structural panels, {panel}, {panel_type}, {'both sides' if sides == 2 else 'one side'}, blocked; "
             f"edge nails at {spacing:g} in; the same sheathing and nailing on all sheathed areas"),
            ("Framing", f"specific gravity G = {G:g} ({G_source.strip()})"),
            ("Wall", f"{h:g} ft high, {length:g} ft long; " + str(len(openings)) + " opening(s); full-height segments "
             + ", ".join(f"{b:g} ft" for _, b, _, _ in w.segments)),
            ("Design Shear", f"{V:,.0f} lb, {load}, {method} ({v_source.strip()})")]
    if w.defl is not None:
        info.append(("Deflection", f"end posts A = {chord_A:g} in2, E = {chord_E:,.0f} psi; anchorage slip {anchor_slip_in:g} in"))
    text = [f"Hold-down at each end of the wall: tension and compression {w.T:,.0f} lb",
            f"Bottom plate at full-height sheathing: shear anchorage and uplift {w.v_max:,.0f} plf"]
    if w.defl is not None:
        text.append(f"Deflection {w.defl:.2f} in")
    sheet = SimpleSheet(
        mark, "Perforated Wood Shear Wall", "Wall", f"{load}, {method}", info, [], [], "Capacity and Forces", w.lines, rows,
        ["Designed as a perforated shear wall: framing and connections around the openings are not designed for force transfer "
         "(SDPWS 4.3.2.3).",
         "Chord forces are from overturning of the wall alone; dead load is not counted against uplift."],
        ["hold-downs and their connections; dead load resisting uplift", "anchor bolts and plate washers for the shear and uplift "
         "anchorage (SDPWS 4.3.6.4)", "compression at each end of each segment; end posts and bearing on the plate",
         "collector over the full length of the wall and its connection to the diaphragm (SDPWS 4.3.2.3)",
         "construction requirements of SDPWS 4.3.6 and 4.3.7.1"] + ([] if w.defl is not None else ["deflection (SDPWS 4.3.4.2)"]))
    sheet.blocks.append(dict(title="Wall Forces", head="Wall Forces", steps=[], text=text,
                             picture=("perforated_wall", dict(h=h, L=length, openings=[dict(x=o["x"], w=o["w"], h=o["h"], sill=o.get("sill") or 0.0)
                                                                                         for o in openings],
                                                              segs=[dict(x=x0, b=b, counted=c) for x0, b, _, c in w.segments], V=V, T=w.T))))
    sheet.wall = w
    return sheet


def snow_drift_sheet(mark, pg, pg_source, W2, W2_source, ps_lower, ps_source, lu_upper, lu_lower, step_ft, sliding=None, parapet=False):
    """Drift on a lower roof at a roof step and sliding snow from the upper roof,
    ASCE/SEI 7-22 Sect. 7.7.1 and 7.9 (see snow.lower_roof). sliding: None or
    dict(pf, pf_source, W, rise_on_12, slippery) for the upper roof."""
    for nm, v in (("the source of the ground snow load", pg_source), ("the source of W2", W2_source),
                  ("the source of the balanced load on the lower roof", ps_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if sliding and not (sliding.get("pf_source") or "").strip():
        raise WorksheetError(f"{mark}: the source of the upper roof's flat roof snow load is blank")
    try:
        r = snow.lower_roof(pg, W2, ps_lower, lu_upper, lu_lower, step_ft, sliding, parapet)
    except snow.SnowError as e:
        raise WorksheetError(f"{mark}: {e}")
    L = footing_line
    steps = [L("gamma = 0.13 pg + 14", r.gamma, "pcf", "ASCE/SEI 7-22 Eq. 7.7-1", "not more than 30 pcf"),
             L("hb = ps / gamma", r.hb, "ft", "Sect. 7.7.1", f"ps = {ps_lower:g} psf"),
             L("hc = height - hb", r.hc, "ft", "Sect. 7.7.1", f"{'parapet' if parapet else 'step'} {step_ft:g} ft"),
             L("hc / hb", r.hc / r.hb if r.hb else 0.0, "", "Sect. 7.7.1", "drift loads are not required below 0.2")]
    loads = [f"Balanced snow on the {'roof' if parapet else 'lower roof'}: {ps_lower:.1f} psf"]
    if r.required:
        for d in [x for x in (r.leeward, r.windward) if x]:
            lu = lu_upper if d.kind == "leeward" else lu_lower
            nm = "drift" if parapet else d.kind
            steps += [L(f"{nm}: hd" + (" = 0.75 x Eq. 7.6-1" if d.kind == "windward" else ""), d.hd_eq, "ft", "Eq. 7.6-1, Sect. 7.8, 7.7.1" if parapet else "Eq. 7.6-1, Sect. 7.7.1",
                        f"lu = {lu:g} ft, W2 = {W2:g}" + ("; not more than 0.6 x the lower roof length" if d.kind == "leeward" else "")),
                      L(f"{nm}: height", d.height, "ft", "Sect. 7.7.1", "not more than hc"),
                      L(f"{nm}: width w", d.width, "ft", "Sect. 7.7.1",
                        ("4 hd, or 4 hd^2 / hc where hd exceeds hc; not more than 8 hc" if d.kind == "leeward" else "8 x 0.75 hd")),
                      L(f"{nm}: pd = height x gamma", d.pd, "psf", "Sect. 7.7.1")]
            loads.append(("Drift surcharge: " if parapet else f"{d.kind.capitalize()} drift surcharge: ")
                         + f"{d.pd:.1f} psf at the {'parapet' if parapet else 'step'}, to "
                         + (f"{d.at_far_end:.1f} psf at the far edge of the roof, {d.extent:g} ft" if d.at_far_end else f"zero at {d.width:.1f} ft"))
        g = r.governing
        loads.append((f"Peak load at the parapet: " if parapet else f"Peak load at the step, {g.kind} drift: ")
                     + f"{ps_lower + g.pd:.1f} psf (balanced plus surcharge)")
    else:
        loads.append(f"Drift surcharge: not required ({r.why})")
    if sliding:
        if r.sliding_psf:
            steps += [L("sliding: 0.4 pf W", 0.4 * sliding["pf"] * sliding["W"], "plf", "Sect. 7.9", f"pf = {sliding['pf']:g} psf, W = {sliding['W']:g} ft"),
                      L("sliding load", r.sliding_psf, "psf", "Sect. 7.9", f"over 15 ft from the eave; {r.sliding_extent:g} ft is on the lower roof")]
            loads.append(f"Sliding snow surcharge: {r.sliding_psf:.1f} psf over {r.sliding_extent:g} ft from the upper roof eave "
                         f"({r.sliding_total:,.0f} plf of eave)")
        else:
            loads.append(f"Sliding snow: not required ({r.sliding_why})")
    info = [("Ground Snow", f"pg = {pg:g} psf ({pg_source.strip()}); W2 = {W2:g} ({W2_source.strip()})")]
    if parapet:
        info += [("Roof", f"balanced snow load ps = {ps_lower:g} psf ({ps_source.strip()}); {lu_lower:g} ft long upwind of the parapet or projection"),
                 ("Parapet", f"{step_ft:g} ft above the roof")]
    else:
        info += [("Lower Roof", f"balanced snow load ps = {ps_lower:g} psf ({ps_source.strip()}); {lu_lower:g} ft long perpendicular to the step"),
                 ("Upper Roof", f"{lu_upper:g} ft long perpendicular to the step; {step_ft:g} ft above the lower roof at the step")]
    if sliding:
        info.append(("Sliding", f"upper roof pf = {sliding['pf']:g} psf ({sliding['pf_source'].strip()}); eave to ridge W = {sliding['W']:g} ft; "
                     f"{sliding['rise_on_12']:g} on 12; " + ("slippery surface" if sliding["slippery"] else "not a slippery surface")))
    sheet = SimpleSheet(
        mark, "Snow Drift at a Parapet" if parapet else "Snow Drift on a Lower Roof", "Parapet" if parapet else "Roof Step", "Chapter 7",
        info, [], [], "Drift" if parapet else "Drift and Sliding Snow", steps, [],
        (["The drift surcharge is added to the balanced snow load on the roof (Sect. 7.8, 7.7.1).",
          "For a roof projection, the roof length entered is the greater of the lengths upwind and downwind of it, and its side is "
          "15 ft or longer (Sect. 7.8)."] if parapet else
         ["Drift and sliding snow surcharges are added to the balanced snow load on the lower roof (Sect. 7.7.1, 7.9). Leeward and "
          "windward drifts are separate load cases; drift and sliding surcharges are not added to each other.",
          "The upper and lower roofs are parts of one structure with no gap between them."]),
        (["intersecting drifts at parapet corners (Sect. 7.7.3)", "unbalanced and partial loading of the roof"] if parapet else
         ["structures separated by a gap (Sect. 7.7.2, 7.9)", "intersecting drifts at corners (Sect. 7.7.3)",
          "drifts at roof projections and parapets (Sect. 7.8)", "unbalanced and partial loading of the lower roof"]
         + ([] if sliding else ["sliding snow (Sect. 7.9)"])))
    sheet.blocks.append(dict(title="Design Loads on the Roof" if parapet else "Design Loads on the Lower Roof",
                             head="Design Loads on the Roof" if parapet else "Design Loads on the Lower Roof", steps=[], text=loads,
                             picture=("snow_drift", dict(ps=ps_lower, step=step_ft, lu=lu_lower, hb=r.hb,
                                                         drifts=[dict(kind=("" if parapet else d.kind), h=d.height, w=d.extent, pd=d.pd, far=d.at_far_end)
                                                                 for d in ((r.leeward, r.windward) if r.required else ()) if d],
                                                         sliding=dict(psf=r.sliding_psf, ext=r.sliding_extent) if r.sliding_psf else None))))
    sheet.drift = r
    return sheet


def wind_pressure_sheet(mark, V, V_source, exposure, exposure_basis, heights, h_mean, Kzt, Kzt_source, elevation_ft=None,
                        elevation_source=""):
    """Wind velocity pressure qz at the heights listed and qh at the mean roof height,
    ASCE/SEI 7-22 Sect. 26.10 (see wind.py). elevation_ft None: Ke = 1.0."""
    for nm, v in (("the source of the basic wind speed", V_source), ("the basis of the exposure category", exposure_basis),
                  ("the source of Kzt", Kzt_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if elevation_ft is not None and not (elevation_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the ground elevation is blank")
    if h_mean is None or h_mean <= 0:
        raise WorksheetError(f"{mark}: the mean roof height must be positive")
    Ke = wind.ke(elevation_ft) if elevation_ft is not None else 1.0
    L = footing_line
    try:
        qh, kh = wind.velocity_pressure(V, exposure, h_mean, Kzt, Ke)
        table = [(z,) + wind.velocity_pressure(V, exposure, z, Kzt, Ke) for z in sorted(set(heights or []))]
    except wind.WindError as e:
        raise WorksheetError(f"{mark}: {e}")
    steps = [L("V", V, "mi/h", "ASCE/SEI 7-22 Sect. 26.5", V_source.strip()),
             L("Kzt", Kzt, "", "Sect. 26.8", Kzt_source.strip()),
             L("Ke" + (" = e^(-0.0000362 ze)" if elevation_ft is not None else ""), Ke, "", "Sect. 26.9, Table 26.9-1",
               f"ze = {elevation_ft:,.0f} ft" if elevation_ft is not None else "taken as 1.0"),
             L("Kh", kh, "", "Table 26.10-1", f"Exposure {exposure}, h = {h_mean:g} ft"),
             L("qh = 0.00256 Kh Kzt Ke V^2", qh, "psf", "Eq. 26.10-1", "at the mean roof height")]
    for z, q, k in table:
        steps += [L(f"Kz at {z:g} ft", k, "", "Table 26.10-1"), L(f"qz at {z:g} ft", q, "psf", "Eq. 26.10-1")]
    text = [f"qh = {qh:.1f} psf at the mean roof height, {h_mean:g} ft"] + [f"qz = {q:.1f} psf at {z:g} ft" for z, q, k in table]
    info = [("Wind Speed", f"V = {V:g} mi/h ({V_source.strip()})"),
            ("Exposure", f"{exposure} ({exposure_basis.strip()})"),
            ("Topography", f"Kzt = {Kzt:g} ({Kzt_source.strip()})"),
            ("Elevation", f"{elevation_ft:,.0f} ft above sea level ({elevation_source.strip()})" if elevation_ft is not None else "Ke taken as 1.0"),
            ("Heights", f"mean roof height h = {h_mean:g} ft" + ("; " + ", ".join(f"{z:g}" for z, _, _ in table) + " ft" if table else ""))]
    sheet = SimpleSheet(
        mark, "Wind Velocity Pressure", "Site and Building", "Chapter 26", info, [], [], "Velocity Pressure", steps, [],
        ["Velocity pressures are strength-level (ASCE/SEI 7-22 basic wind speed). The directionality factor Kd is applied with the "
         "pressure coefficients (Sect. 26.6), not here."],
        ["design wind pressures on the main wind force resisting system (Chapters 27 and 28)",
         "design wind pressures on components and cladding (Chapter 30)", "enclosure classification and internal pressure (Sect. 26.12, 26.13)",
         "the 0.70 minimum Kz of Chapter 28 for Exposure B below 30 ft"])
    sheet.wind = dict(qh=qh, Kh=kh, Ke=Ke, table=table)
    return sheet


def wind_mwfrs_sheet(mark, V, V_source, exposure, exposure_basis, h_mean, eave, across_ridge, along_ridge, theta, enclosure,
                     enclosure_basis, Kzt, Kzt_source, elevation_ft=None, elevation_source="", roof="gable"):
    """Design wind pressures on the main wind force resisting system of a rigid building with
    a gable, monoslope or flat roof, ASCE/SEI 7-22 Chapter 27 (directional procedure), for
    each wind direction (see wind.py). across_ridge, along_ridge: plan dimensions; eave: the
    eave height (the low eave of a monoslope roof)."""
    import math as _m
    for nm, v in (("the source of the basic wind speed", V_source), ("the basis of the exposure category", exposure_basis),
                  ("the source of Kzt", Kzt_source), ("the basis of the enclosure classification", enclosure_basis)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if elevation_ft is not None and not (elevation_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the ground elevation is blank")
    if roof == "monoslope" and not theta > 0:
        raise WorksheetError(f"{mark}: a monoslope roof needs a roof angle above 0")
    Ke = wind.ke(elevation_ft) if elevation_ft is not None else 1.0
    L = footing_line
    flat = not theta > 0
    if roof == "monoslope":
        cases = [("normal_low", "Wind Normal to the Ridge, Toward the Low Eave Wall", along_ridge, across_ridge),
                 ("normal_high", "Wind Normal to the Ridge, Toward the High Eave Wall", along_ridge, across_ridge),
                 ("parallel", "Wind Parallel to the Ridge", across_ridge, along_ridge)]
    elif flat:
        cases = [("normal", f"Wind Along the {across_ridge:g} ft Dimension", along_ridge, across_ridge),
                 ("parallel", f"Wind Along the {along_ridge:g} ft Dimension", across_ridge, along_ridge)]
    else:
        cases = [("normal", "Wind Normal to the Ridge", along_ridge, across_ridge),
                 ("parallel", "Wind Parallel to the Ridge", across_ridge, along_ridge)]
    try:
        res = [(t, Bd, Ld, wind.mwfrs(V, exposure, h_mean, eave, Bd, Ld, enclosure, d, theta, Kzt, Ke, roof=roof)) for d, t, Bd, Ld in cases]
    except wind.WindError as e:
        raise WorksheetError(f"{mark}: {e}")
    r0 = res[0][3]
    qh, kh, gc = r0["qh"], r0["Kh"], r0["GCpi"]
    steps = [L("V", V, "mi/h", "ASCE/SEI 7-22 Sect. 26.5", V_source.strip()),
             L("Kzt", Kzt, "", "Sect. 26.8", Kzt_source.strip()),
             L("Ke" + (" = e^(-0.0000362 ze)" if elevation_ft is not None else ""), Ke, "", "Sect. 26.9, Table 26.9-1",
               f"ze = {elevation_ft:,.0f} ft" if elevation_ft is not None else "taken as 1.0"),
             L("Kh", kh, "", "Table 26.10-1", f"Exposure {exposure}, h = {h_mean:g} ft"),
             L("qh = 0.00256 Kh Kzt Ke V^2", qh, "psf", "Eq. 26.10-1", "at the mean roof height")]
    seen = {}
    for t, Bd, Ld, r in res:
        for s in r["windward"]:
            seen.setdefault(round(s.z, 6), s)
    for z in sorted(seen):
        s = seen[z]
        steps += [L(f"qz at {round(s.z, 1):g} ft", s.q, "psf", "Eq. 26.10-1, Table 26.10-1", f"Kz = {s.Kz:.2f}")]
    steps += [L("Kd", wind.KD_MWFRS, "", "Table 26.6-1", "buildings, main wind force resisting system"),
              L("G", wind.G_RIGID, "", "Sect. 26.11.1", "rigid building"),
              L("GCpi", gc, "", "Table 26.13-1", f"{enclosure} building; plus and minus"),
              L("qi Kd GCpi", qh * wind.KD_MWFRS * gc, "psf", "Eq. 27.3-1", "internal pressure, qi = qh; acts on every surface, plus and minus")]

    def two(r, name):
        return [x for x in r["roof"] if x.name == name and not x.zone]

    def table(r):
        out = [f"{'surface':<34}{'q psf':>8}{'Cp':>8}{'q Kd G Cp':>12}{'with +GCpi':>12}{'with -GCpi':>12}{'less leeward wall':>20}"]
        together = {id(x): p_ for x, (z_, p_) in zip(r["windward"], r["walls_together"])}
        for s in r["windward"] + [r["leeward"], r["side"]] + r["roof"]:
            nm = s.name if not s.zone else f"roof, {s.zone[0]} ({s.zone[1]:.1f} to {s.zone[2]:.1f} ft)"
            same = two(r, s.name)
            if r["sloped"] and len(same) == 2 and s.name in ("windward roof", "roof"):
                nm += ", value 1" if s is same[0] else ", value 2"
            out.append(f"{nm:<34}{s.q:>8.1f}{s.Cp:>8.2f}{s.external:>12.1f}{s.p_pos_internal:>12.1f}{s.p_neg_internal:>12.1f}"
                       + (f"{together[id(s)]:>20.1f}" if id(s) in together else ""))
        f = f"horizontal force: windward wall {r['F_windward']:,.0f} + leeward wall {r['F_leeward']:,.0f} = {r['F_walls']:,.0f} lb"
        out.append(f)
        if any(abs(x) > 0.5 for x in r["F_roof"]):
            out.append("  roof, horizontal: " + " or ".join(f"{x:+,.0f}" for x in r["F_roof"]) + f" lb; total {r['F_total']:,.0f} lb (not less than the walls alone)")
        out.append(f"  minimum: {wind.MIN_WALL:g} psf x {r['A_wall']:,.0f} ft2" + (f" + {wind.MIN_ROOF:g} psf x {r['A_roof']:,.0f} ft2" if r["A_roof"] else "")
                   + f" = {r['F_min']:,.0f} lb;  design horizontal force = {r['F_design']:,.0f} lb")
        return out

    def basis(r, Bd, Ld):
        t = f"B = {Bd:g} ft normal to the wind, L = {Ld:g} ft parallel to it; L/B = {r['L_over_B']:.2f}, h/L = {r['h_over_L']:.2f}. "
        t += "Less leeward wall: the windward and leeward walls together (internal pressure cancels). "
        if r["sloped"]:
            t += "Where two roof values are listed, the roof is designed for each."
        else:
            t += "Roof zones are measured from the windward edge; each zone is also designed for Cp = -0.18."
        return [t]

    shape = "flat roof" if flat else f"{roof} roof at {theta:g} degrees"
    info = [("Wind Speed", f"V = {V:g} mi/h ({V_source.strip()})"),
            ("Exposure", f"{exposure} ({exposure_basis.strip()})"),
            ("Topography", f"Kzt = {Kzt:g} ({Kzt_source.strip()})"),
            ("Elevation", f"{elevation_ft:,.0f} ft above sea level ({elevation_source.strip()})" if elevation_ft is not None else "Ke taken as 1.0"),
            ("Enclosure", f"{enclosure} ({enclosure_basis.strip()})"),
            ("Building", f"{across_ridge:g} ft x {along_ridge:g} ft; roof height h = {h_mean:g} ft; flat roof" if flat else
                         f"{across_ridge:g} ft across the ridge x {along_ridge:g} ft along it; {'low ' if roof == 'monoslope' else ''}eave {eave:g} ft; "
                         f"mean roof height h = {h_mean:g} ft; {shape}")]
    sheet = SimpleSheet(
        mark, "Wind Pressures, Main Wind Force Resisting System", "Site and Building", "Chapter 27", info, [], [],
        "Velocity Pressure and Factors", steps, [],
        ["Pressures are strength-level (ASCE/SEI 7-22 basic wind speed), in psf, positive toward the surface and negative away from it.",
         "p = q Kd G Cp - qi Kd (GCpi), Eq. 27.3-1, with q = qz on the windward wall and qh on the leeward wall, side walls and roof; qi = qh.",
         "Rigid building (Sect. 26.2): G = 0.85.",
         "Cp from Figure 27.3-1 with linear interpolation (notes 2 and 3). The area reduction of the -1.3 roof value is not taken.",
         "Horizontal force: the windward wall pressure at the top of each height band is used over that band; the total is not less than the "
         "force on the walls alone (Figure 27.3-1, note 6); the horizontal force on a roof designed by zones is neglected.",
         f"Minimum design wind load: {wind.MIN_WALL:g} psf on the wall area and {wind.MIN_ROOF:g} psf on the roof area projected on a "
         "vertical plane normal to the wind (Sect. 27.1.5)."],
        ["the torsional load cases of Figure 27.3-8 (Sect. 27.3.5)",
         "parapets and roof overhangs (Sect. 27.3.3, 27.3.4)", "components and cladding (Chapter 30)",
         "whether the building is rigid (Sect. 26.2) and its enclosure classification (Sect. 26.12)"])

    def panel(t, r, Ld):
        d = r["direction"]
        pn = dict(title=t.upper().replace("WIND NORMAL TO THE RIDGE, ", "WIND "), L=Ld, hl=r["top_w"], hr=r["top_l"], rise=r["rise"],
                  windward=r["windward"][-1].external, leeward=r["leeward"].external)
        if r["sloped"] and roof == "gable":
            pn.update(shape="gable", hl=eave, hr=eave, roof_windward=[x.external for x in two(r, "windward roof")],
                      roof_leeward=[x.external for x in two(r, "leeward roof")])
        elif r["sloped"]:
            pn.update(shape="mono", roof_values=[x.external for x in r["roof"]])
        else:
            pn.update(shape="flat", zones=[(x.zone[1], x.zone[2], x.external) for x in r["roof"] if x.zone], other=r["roof"][-1].external)
            if d != "parallel" and roof == "monoslope":
                pn["shape"] = "mono_zones"
        return pn

    sheet.blocks.append(dict(title="External Pressures", picture=("wind_mwfrs", dict(panels=[panel(t, r, Ld) for t, Bd, Ld, r in res]))))
    for t, Bd, Ld, r in res:
        sheet.blocks.append(dict(title=t, lines=table(r), after=basis(r, Bd, Ld)))
    sheet.wind = dict(qh=qh, cases=[r for t, Bd, Ld, r in res], normal=res[0][3], parallel=res[-1][3])
    return sheet


def wind_cc_walls_sheet(mark, V, V_source, exposure, exposure_basis, h_mean, least_dim, theta, enclosure, enclosure_basis, areas,
                        Kzt, Kzt_source, elevation_ft=None, elevation_source=""):
    """Wind pressures on wall components and cladding, buildings with h of 60 ft or less,
    ASCE/SEI 7-22 Chapter 30 Part 1 (see wind.py)."""
    for nm, v in (("the source of the basic wind speed", V_source), ("the basis of the exposure category", exposure_basis),
                  ("the source of Kzt", Kzt_source), ("the basis of the enclosure classification", enclosure_basis)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if elevation_ft is not None and not (elevation_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the ground elevation is blank")
    Ke = wind.ke(elevation_ft) if elevation_ft is not None else 1.0
    L = footing_line
    try:
        r = wind.cc_walls(V, exposure, h_mean, least_dim, enclosure, areas, theta, Kzt, Ke)
    except wind.WindError as e:
        raise WorksheetError(f"{mark}: {e}")
    qh, gc, a = r["qh"], r["GCpi"], r["a"]
    steps = [L("V", V, "mi/h", "ASCE/SEI 7-22 Sect. 26.5", V_source.strip()),
             L("Kzt", Kzt, "", "Sect. 26.8", Kzt_source.strip()),
             L("Ke" + (" = e^(-0.0000362 ze)" if elevation_ft is not None else ""), Ke, "", "Sect. 26.9, Table 26.9-1",
               f"ze = {elevation_ft:,.0f} ft" if elevation_ft is not None else "taken as 1.0"),
             L("Kh", r["Kh"], "", "Table 26.10-1", f"Exposure {exposure}, h = {h_mean:g} ft"),
             L("qh = 0.00256 Kh Kzt Ke V^2", qh, "psf", "Eq. 26.10-1", "at the mean roof height"),
             L("Kd", wind.KD_CC, "", "Table 26.6-1", "buildings, components and cladding"),
             L("GCpi", gc, "", "Table 26.13-1", f"{enclosure} building; plus and minus"),
             L("a", a, "ft", "Figure 30.3-1", f"width of the corner zone (zone 5) at each wall corner; least horizontal dimension {least_dim:g} ft")]
    lines = [f"{'area':>8}{'(GCp) +':>12}{'zone 4 -':>10}{'zone 5 -':>10}{'p + (4, 5)':>14}{'p - zone 4':>12}{'p - zone 5':>12}",
             f"{'ft2':>8}{'':>12}{'':>10}{'':>10}{'psf':>14}{'psf':>12}{'psf':>12}"]
    for x in r["rows"]:
        g, d = x["gcp"], x["design"]
        lines.append(f"{x['area']:>8g}{g['positive']:>12.2f}{g[4]:>10.2f}{g[5]:>10.2f}{d['positive']:>14.1f}{d[4]:>12.1f}{d[5]:>12.1f}")
    info = [("Wind Speed", f"V = {V:g} mi/h ({V_source.strip()})"),
            ("Exposure", f"{exposure} ({exposure_basis.strip()})"),
            ("Topography", f"Kzt = {Kzt:g} ({Kzt_source.strip()})"),
            ("Elevation", f"{elevation_ft:,.0f} ft above sea level ({elevation_source.strip()})" if elevation_ft is not None else "Ke taken as 1.0"),
            ("Enclosure", f"{enclosure} ({enclosure_basis.strip()})"),
            ("Building", f"mean roof height h = {h_mean:g} ft; least horizontal dimension {least_dim:g} ft; roof at {theta:g} degrees")]
    sheet = SimpleSheet(
        mark, "Wind Pressures, Wall Components and Cladding", "Site and Building", "Chapter 30, Part 1", info, [], [],
        "Velocity Pressure and Factors", steps, [],
        ["Pressures are strength-level (ASCE/SEI 7-22 basic wind speed), in psf, positive toward the wall and negative away from it.",
         "p = qh Kd [(GCp) - (GCpi)], Eq. 30.3-1; the internal pressure sign that adds is used with each value.",
         "(GCp) from Figure 30.3-1 by effective wind area (Sect. 26.2)" + ("; reduced 10 percent for a roof at 10 degrees or less (note 5)." if theta <= 10 else "."),
         f"Net pressure not less than {wind.MIN_CC:g} psf in either direction (Sect. 30.2.2).",
         "Zone 5 is within the distance a of a wall corner; zone 4 is the rest of the wall."],
        ["roof components and cladding (Figures 30.3-2 and on)", "parapets and roof overhangs",
         "the enclosure classification (Sect. 26.12)", "the effective wind area of each component (Sect. 26.2)"])
    sheet.blocks.append(dict(title="Design Pressures by Effective Wind Area", lines=lines))
    sheet.wind = dict(r)
    return sheet


def wind_cc_roof_sheet(mark, V, V_source, exposure, exposure_basis, h, theta, enclosure, enclosure_basis, areas,
                       Kzt, Kzt_source, elevation_ft=None, elevation_source="", least_dim=None):
    """Wind pressures on roof components and cladding, flat roofs and gable roofs up to 45
    degrees, buildings with h of 60 ft or less, ASCE/SEI 7-22 Chapter 30 Part 1 (see wind.py).
    h: the mean roof height (the eave height at 10 degrees or less)."""
    for nm, v in (("the source of the basic wind speed", V_source), ("the basis of the exposure category", exposure_basis),
                  ("the source of Kzt", Kzt_source), ("the basis of the enclosure classification", enclosure_basis)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if elevation_ft is not None and not (elevation_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the ground elevation is blank")
    Ke = wind.ke(elevation_ft) if elevation_ft is not None else 1.0
    L = footing_line
    try:
        r = wind.cc_roof(V, exposure, h, enclosure, areas, theta, Kzt, Ke, least_dim=least_dim)
    except wind.WindError as e:
        raise WorksheetError(f"{mark}: {e}")
    qh, gc, fig = r["qh"], r["GCpi"], "Figure " + r["figure"]
    hname = "eave height" if theta <= 10 else "mean roof height"
    steps = [L("V", V, "mi/h", "ASCE/SEI 7-22 Sect. 26.5", V_source.strip()),
             L("Kzt", Kzt, "", "Sect. 26.8", Kzt_source.strip()),
             L("Ke" + (" = e^(-0.0000362 ze)" if elevation_ft is not None else ""), Ke, "", "Sect. 26.9, Table 26.9-1",
               f"ze = {elevation_ft:,.0f} ft" if elevation_ft is not None else "taken as 1.0"),
             L("Kh", r["Kh"], "", "Table 26.10-1", f"Exposure {exposure}, h = {h:g} ft"),
             L("qh = 0.00256 Kh Kzt Ke V^2", qh, "psf", "Eq. 26.10-1", f"at the {hname}"),
             L("Kd", wind.KD_CC, "", "Table 26.6-1", "buildings, components and cladding"),
             L("GCpi", gc, "", "Table 26.13-1", f"{enclosure} building; plus and minus")]
    if "a" in r:
        steps += [L("a", r["a"], "ft", fig, f"width of the edge zones; least horizontal dimension {least_dim:g} ft")]
        zone_text = ("Zone 2: within a of a gable end. Zone 3: at each eave corner, a by a. Zone 1: the rest of the roof." if r["figure"] == "30.3-2D" else
                     "Zone 2: within a of a gable end, and within a of the ridge on each side. Zone 3: where those meet, at each end of the ridge. "
                     "Zone 1: the rest of the roof.")
    else:
        steps += [L("0.6h", r["edge"], "ft", fig, "width of the edge zone (zone 2) and of the zone 1 band inside it; length of a corner zone"),
                  L("0.2h", r["corner"], "ft", fig, "depth of a corner zone (zone 3)")]
        zone_text = ("Zone 2: within 0.6h of a roof edge. Zone 3: at each corner, 0.6h along each edge by 0.2h deep. Zone 1: from 0.6h to 1.2h from an edge. "
                     "Zone 1': the rest of the roof.")
    zs = r["zones"]
    lines = [f"{'area ft2':>9}  (GCp):{'+':>6}" + "".join(f"{z:>7}" for z in zs) + f"   p psf:{'+':>6}" + "".join(f"{z:>8}" for z in zs)]
    for x in r["rows"]:
        g, d = x["gcp"], x["design"]
        lines.append(f"{x['area']:>9g}        {g['positive']:>6.2f}" + "".join(f"{g[z]:>7.2f}" for z in zs)
                     + f"         {d['positive']:>6.1f}" + "".join(f"{d[z]:>8.1f}" for z in zs))
    info = [("Wind Speed", f"V = {V:g} mi/h ({V_source.strip()})"),
            ("Exposure", f"{exposure} ({exposure_basis.strip()})"),
            ("Topography", f"Kzt = {Kzt:g} ({Kzt_source.strip()})"),
            ("Elevation", f"{elevation_ft:,.0f} ft above sea level ({elevation_source.strip()})" if elevation_ft is not None else "Ke taken as 1.0"),
            ("Enclosure", f"{enclosure} ({enclosure_basis.strip()})"),
            ("Building", f"{hname} h = {h:g} ft; " + ("flat roof" if not theta > 0 else f"gable roof at {theta:g} degrees"))]
    not_checked = ["roof overhangs (Sect. 30.7)", "wall components and cladding (Figure 30.3-1)",
                   "the enclosure classification (Sect. 26.12)", "the effective wind area of each component (Sect. 26.2)"]
    if theta <= 7:
        not_checked.insert(0, "a parapet 3 ft or higher around the roof (Figure 30.3-2A, note 5)")
    sheet = SimpleSheet(
        mark, "Wind Pressures, Roof Components and Cladding", "Site and Building", "Chapter 30, Part 1", info, [], [],
        "Velocity Pressure and Factors", steps, [],
        ["Pressures are strength-level (ASCE/SEI 7-22 basic wind speed), in psf, positive toward the roof and negative away from it.",
         "p = qh Kd [(GCp) - (GCpi)], Eq. 30.3-1; the internal pressure sign that adds is used with each value.",
         f"(GCp) from {fig} by effective wind area (Sect. 26.2).",
         f"Net pressure not less than {wind.MIN_CC:g} psf in either direction (Sect. 30.2.2).", zone_text],
        not_checked)
    sheet.blocks.append(dict(title="Design Pressures by Effective Wind Area and Zone", lines=lines))
    sheet.wind = dict(r)
    return sheet
