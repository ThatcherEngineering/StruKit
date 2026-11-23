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
                     field_nails=None, dead_plf=0.0, dead_factor=None, dead_source="", other=None):
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
                           chord_E, chord_A, anchor_slip_in, sides, blocked, stud_spacing, field_nails, dead_plf or 0.0, dead_factor, other=other)
    except shearwall.ShearWallError as e:
        raise WorksheetError(f"{mark}: {e}")
    rows = [Row("shear in the wall line", f"{load}, {method}", V, w.capacity, "lb", "SDPWS-2021 4.1.4, Table 4.3A, 4.3.5.5.1",
                f"nominal {w.design_text}; sum of {len(w.segments)} segment(s)")]
    info = [("Sheathing", f"wood structural panels, {panel}, {panel_type}, {'side 1' if other else 'both sides' if sides == 2 else 'one side'}, "
             + ("blocked" if blocked else f"unblocked, studs at {stud_spacing:g} in") + f"; edge nails at {spacing:g} in"
             + ("" if blocked else f", intermediate nails at {field_nails:g} in")),
            *([("Side 2", f"wood structural panels, {other['panel']}, {other['panel_type']}, blocked; edge nails at {other['spacing']:g} in")] if other else []),
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
                     enclosure_basis, Kzt, Kzt_source, elevation_ft=None, elevation_source="", roof="gable", parapet=0.0, theta_hip=None, overhang=0.0):
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
    if roof == "hip" and (not theta > 0 or not (theta_hip or 0) > 0):
        raise WorksheetError(f"{mark}: a hip roof needs the roof angle and the hip end roof angle")
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
        res = [(t, Bd, Ld, wind.mwfrs(V, exposure, h_mean, eave, Bd, Ld, enclosure, d, theta, Kzt, Ke, roof=roof, parapet=parapet or 0.0, theta_hip=theta_hip)) for d, t, Bd, Ld in cases]
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
            nm = s.name if not s.zone else f"{'roof' if s.name == 'roof' else 'sides'}, {s.zone[0]} ({s.zone[1]:.1f} to {s.zone[2]:.1f} ft)"
            same = two(r, s.name)
            if r["sloped"] and len(same) == 2 and s.name in ("windward roof", "roof"):
                nm += ", value 1" if s is same[0] else ", value 2"
            out.append(f"{nm:<34}{s.q:>8.1f}{s.Cp:>8.2f}{s.external:>12.1f}{s.p_pos_internal:>12.1f}{s.p_neg_internal:>12.1f}"
                       + (f"{together[id(s)]:>20.1f}" if id(s) in together else ""))
        pr = r["parapet"]
        if pr:
            out.append(f"parapets, {pr['height']:g} ft high: windward qp {pr['q_windward']:.1f} psf x Kd x 1.5 = {pr['p_windward']:+.1f} psf; "
                       f"leeward qp {pr['q_leeward']:.1f} psf x Kd x -1.0 = {pr['p_leeward']:+.1f} psf (net, Eq. 27.3-3)")
        if overhang:
            o = wind.mwfrs_overhang(r, overhang)
            out.append(f"windward roof overhang, {overhang:g} ft: bottom surface qh Kd G x 0.8 = {o['bottom']:.1f} psf upward; net with the top surface "
                       + " or ".join(f"{v['net']:+.1f} psf (top Cp {v['Cp']:.2f})" for v in o["values"]))
            out.append(f"  governing uplift {-o['net']:.1f} psf = {-o['w']:,.0f} lb per ft of eave on the {overhang:g} ft horizontal projection")
        f = (f"horizontal force: windward wall {r['F_windward']:,.0f} + leeward wall {r['F_leeward']:,.0f}"
             + (f" + parapets {pr['F']:,.0f}" if pr else "") + f" = {r['F_walls']:,.0f} lb")
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
            if roof == "hip":
                t += " Sides: the roof planes at the sides, by zones measured from the windward edge; each zone is also designed for Cp = -0.18."
        else:
            t += "Roof zones are measured from the windward edge; each zone is also designed for Cp = -0.18."
        return [t]

    shape = "flat roof" if flat else f"{roof} roof at {theta:g} degrees" + (f", hip ends at {theta_hip:g} degrees" if roof == "hip" else "")
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
         *([] if (parapet and overhang) else ["parapets (Sect. 27.3.4)"] if overhang else ["roof overhangs (Sect. 27.3.3)"] if parapet
           else ["parapets and roof overhangs (Sect. 27.3.3, 27.3.4)"]), "components and cladding (Chapter 30)",
         "whether the building is rigid (Sect. 26.2) and its enclosure classification (Sect. 26.12)"])

    def panel(t, r, Ld):
        d = r["direction"]
        pn = dict(title=t.upper().replace("WIND NORMAL TO THE RIDGE, ", "WIND "), L=Ld, hl=r["top_w"], hr=r["top_l"], rise=r["rise"],
                  windward=r["windward"][-1].external, leeward=r["leeward"].external)
        if r["sloped"] and roof in ("gable", "hip"):
            pn.update(shape="gable", hl=eave, hr=eave, top=(r.get("ridge", 0.0) if (roof == "hip" and d == "parallel") else 0.0), roof_windward=[x.external for x in two(r, "windward roof")],
                      roof_leeward=[x.external for x in two(r, "leeward roof")])
        elif r["sloped"]:
            pn.update(shape="mono", roof_values=[x.external for x in r["roof"]])
        else:
            pn.update(shape="flat", zones=[(x.zone[1], x.zone[2], x.external) for x in r["roof"] if x.zone], other=r["roof"][-1].external)
            if d != "parallel" and roof == "monoslope":
                pn["shape"] = "mono_zones"
        return pn

    if parapet:
        sheet.info.append(("Parapets", f"{parapet:g} ft above the top of the windward and leeward walls"))
        sheet.assumptions.append("Parapets: net pressure pp = qp Kd (GCpn), Eq. 27.3-3, qp at the top of the parapet, (GCpn) = +1.5 windward and -1.0 leeward; "
                                 "their force and area are included in the horizontal force and in the minimum.")
    if overhang:
        sheet.info.append(("Roof Overhang", f"{overhang:g} ft horizontal projection"))
        sheet.assumptions.append("Windward roof overhang: positive pressure on the bottom surface with Cp = 0.8 and q = qh, combined with the top surface pressure "
                                 "of Figure 27.3-1 at the windward edge (Sect. 27.3.3); no internal pressure acts. The horizontal force on the overhang is not "
                                 "included in the horizontal force.")
    if roof == "hip":
        sheet.assumptions.insert(4, "Hip roof: for each wind direction the roof plane facing the wind takes the windward roof coefficients at its slope, the opposite "
                                    "plane the leeward coefficients, and the planes at the sides the coefficients by distance from the windward edge (Figure 27.3-1). "
                                    "The horizontal roof force acts on the area of the facing plane projected on a vertical plane.")
    sheet.blocks.append(dict(title="External Pressures", picture=("wind_mwfrs", dict(panels=[panel(t, r, Ld) for t, Bd, Ld, r in res]))))
    for t, Bd, Ld, r in res:
        sheet.blocks.append(dict(title=t, lines=table(r), after=basis(r, Bd, Ld)))
    nres = [x for x in res if x[3]["direction"] != "parallel"]
    xr = max(nres, key=lambda x: x[3]["F_walls"])
    yr = res[-1]
    xn, yn = ("across the ridge", "along the ridge") if not flat else (f"along the {across_ridge:g} ft dimension", f"along the {along_ridge:g} ft dimension")
    lc = wind.load_cases(xr[3]["F_walls"], xr[1], yr[3]["F_walls"], yr[1])
    cl = [f"{'case':<12}{'force ' + xn + ' lb':>34}{'force ' + yn + ' lb':>34}{'torsion lb-ft':>16}"]
    for nm, fx, fy, mz in lc:
        cl.append(f"{nm.replace(', x', ', ' + ('across' if not flat else 'first')).replace(', y', ', ' + ('along' if not flat else 'second')):<18}"
                  f"{fx:>28,.0f}{fy:>34,.0f}{mz:>16,.0f}")
    sheet.blocks.append(dict(title="Design Wind Load Cases, Wall Forces", lines=cl, after=[
        f"Figure 27.3-8, rigid building, from the forces on the windward and leeward walls{' and parapets' if parapet else ''} of each direction "
        f"({xr[3]['F_walls']:,.0f} lb on walls {xr[1]:g} ft wide; {yr[3]['F_walls']:,.0f} lb on walls {yr[1]:g} ft wide). Case 2: 0.75 of the wall force with a "
        "torsional moment at an eccentricity of 0.15 B, either way. Case 3: 0.75 in both directions together. Case 4: 0.563 in both directions with both "
        "torsional moments. Roof pressures: Case 2, 75 percent of Case 1; Cases 3 and 4, the larger of the Case 1 and Case 2 roof pressures on each "
        "roof area (note 2)."]))
    sheet.not_checked = [t for t in sheet.not_checked if not t.startswith("the torsional load cases")] + [
        "the share of each load case taken by each wall or frame line", "the exception for buildings meeting Appendix D, Sect. D.1 (Sect. 27.3.5)"]
    sheet.wind = dict(qh=qh, cases=[r for t, Bd, Ld, r in res], normal=res[0][3], parallel=res[-1][3], load_cases=lc, titles=[t for t, Bd, Ld, r in res])
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
    sheet.blocks.append(dict(title="Zones", picture=("wind_zones", dict(kind="wall", a=a))))
    sheet.blocks.append(dict(title="Design Pressures by Effective Wind Area", lines=lines))
    sheet.wind = dict(r)
    return sheet


def wind_cc_roof_sheet(mark, V, V_source, exposure, exposure_basis, h, theta, enclosure, enclosure_basis, areas,
                       Kzt, Kzt_source, elevation_ft=None, elevation_source="", least_dim=None, roof="gable", overhang=False, parapet=False):
    """Wind pressures on roof components and cladding, flat roofs, gable roofs up to 45 degrees and monoslope roofs up to 30
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
        r = wind.cc_roof(V, exposure, h, enclosure, areas, theta, Kzt, Ke, least_dim=least_dim, roof=roof, overhang=overhang, parapet=parapet)
    except wind.WindError as e:
        raise WorksheetError(f"{mark}: {e}")
    qh, gc, fig = r["qh"], r["GCpi"], ("Figures " if "and" in r["figure"] else "Figure ") + r["figure"]
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
        zone_text = ("Zone 3: within a of the eaves. Zone 2: within a of the ridge and of each hip, on each side. Zone 1: the rest of the roof."
                     + (" (GCp) is interpolated between Figures 30.3-2F and 30.3-2G by roof angle (Figure 30.3-2G, note 6)." if "and" in r["figure"] else "")
                     if roof == "hip" else
                     "Zones 3' and 2': along the high eave, 2a wide, zone 3' for 4a from each end; zone 2' also along each sloping edge, 2a wide. "
                     "Zone 3: at each low eave corner, 2a by 2a. Zone 2: along the low eave, a wide. Zone 1: the rest of the roof." if r["figure"] == "30.3-5A" else
                     "Zones 3 and 2: along the high eave, 2a wide, zone 3 for 4a from each end. Zone 2 also along the other three edges, a wide. "
                     "Zone 1: the rest of the roof." if r["figure"] == "30.3-5B" else
                     "Zone 2: within a of a gable end. Zone 3: at each eave corner, a by a. Zone 1: the rest of the roof." if r["figure"] == "30.3-2D" else
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
            ("Building", f"{hname} h = {h:g} ft; " + ("flat roof" if not theta > 0 else f"{roof} roof at {theta:g} degrees"))]
    not_checked = ["roof overhangs (Sect. 30.7)", "wall components and cladding (Figure 30.3-1)",
                   "the enclosure classification (Sect. 26.12)", "the effective wind area of each component (Sect. 26.2)"]
    if r["figure"] == "30.3-2A" and not parapet:
        not_checked.insert(0, "a parapet 3 ft or higher around the roof (Figure 30.3-2A, note 5)")
    if parapet:
        not_checked.insert(0, "the parapets themselves (Sect. 30.6)")
    sheet = SimpleSheet(
        mark, "Wind Pressures, Roof Components and Cladding", "Site and Building", "Chapter 30, Part 1", info, [], [],
        "Velocity Pressure and Factors", steps, [],
        ["Pressures are strength-level (ASCE/SEI 7-22 basic wind speed), in psf, positive toward the roof and negative away from it.",
         "p = qh Kd [(GCp) - (GCpi)], Eq. 30.3-1; the internal pressure sign that adds is used with each value.",
         f"(GCp) from {fig} by effective wind area (Sect. 26.2).",
         f"Net pressure not less than {wind.MIN_CC:g} psf in either direction (Sect. 30.2.2).", zone_text],
        not_checked)
    zp = dict(kind="flat", edge=r["edge"], corner=r["corner"]) if "edge" in r else dict(kind="hip" if roof == "hip" else {"30.3-2D": "corner", "30.3-5A": "mono_a", "30.3-5B": "mono_b"}.get(r["figure"], "ridge"), a=r["a"])
    sheet.blocks.append(dict(title="Zones", picture=("wind_zones", zp)))
    if parapet:
        lines[0] += f"{'+ (2, 3)':>10}"
        for k, x in enumerate(r["rows"]):
            lines[k + 1] += f"{x['edge_positive']:>10.1f}"
        sheet.assumptions.append("A parapet 3 ft or higher runs around the perimeter of the roof: the negative zone 3 values equal those of zone 2, and the "
                                 "positive pressure in zones 2 and 3, column + (2, 3), uses the positive wall value of Figure 30.3-1 (Figure 30.3-2A, note 5).")
    sheet.blocks.append(dict(title="Design Pressures by Effective Wind Area and Zone", lines=lines))
    if r["overhang"]:
        chart = r["figure"] == "30.3-2A"
        ol = [f"{'area ft2':>9}  {'      ' if chart else 'wall +'}{'':>4}(GCp):" + "".join(f"{z:>7}" for z in zs) + f"   p psf:" + "".join(f"{z:>8}" for z in zs)]
        for x in r["rows"]:
            ol.append(f"{x['area']:>9g}" + (f"{'':>8}" if chart else f"{x['overhang_wall']:>8.2f}") + f"{'':>10}" + "".join(f"{x['overhang_gcp'][z]:>7.2f}" for z in zs)
                      + f"{'':>9}" + "".join(f"{x['overhang'][z]:>8.1f}" for z in zs))
        sheet.blocks.append(dict(title="Roof Overhangs: Uplift by Effective Wind Area and Zone", lines=ol, after=[
            "p = qh Kd [(GCp) - (GCpi)], Eq. 30.7-1. (GCp) from the overhang chart of Figure 30.3-2A, which includes both surfaces (note 6)." if chart else
            "p = qh Kd [(GCp) - (GCpi)], Eq. 30.7-1. (GCp) = the roof zone value on the top surface less the positive wall value of Figure 30.3-1 "
            "on the bottom surface, for the same effective wind area (Sect. 30.7)."]))
        sheet.not_checked = [t for t in sheet.not_checked if not t.startswith("roof overhangs")] + ["downward pressure on roof overhangs"]
    sheet.wind = dict(r)
    return sheet


def wind_cc_parapet_sheet(mark, V, V_source, exposure, exposure_basis, hp_top, h_eave, least_dim, theta, areas,
                          Kzt, Kzt_source, elevation_ft=None, elevation_source=""):
    """Net wind pressure on parapets as components and cladding, roofs at 7 degrees or less,
    ASCE/SEI 7-22 Sect. 30.6 (see wind.py)."""
    for nm, v in (("the source of the basic wind speed", V_source), ("the basis of the exposure category", exposure_basis), ("the source of Kzt", Kzt_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if elevation_ft is not None and not (elevation_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the ground elevation is blank")
    Ke = wind.ke(elevation_ft) if elevation_ft is not None else 1.0
    L = footing_line
    try:
        r = wind.cc_parapet(V, exposure, hp_top, h_eave, least_dim, areas, theta, Kzt, Ke)
    except wind.WindError as e:
        raise WorksheetError(f"{mark}: {e}")
    qp = r["qp"]
    steps = [L("V", V, "mi/h", "ASCE/SEI 7-22 Sect. 26.5", V_source.strip()),
             L("Kzt", Kzt, "", "Sect. 26.8", Kzt_source.strip()),
             L("Ke" + (" = e^(-0.0000362 ze)" if elevation_ft is not None else ""), Ke, "", "Sect. 26.9, Table 26.9-1",
               f"ze = {elevation_ft:,.0f} ft" if elevation_ft is not None else "taken as 1.0"),
             L("Kz at the top of the parapet", r["Kp"], "", "Table 26.10-1", f"Exposure {exposure}, {hp_top:g} ft"),
             L("qp = 0.00256 Kz Kzt Ke V^2", qp, "psf", "Eq. 26.10-1, Sect. 30.6", "at the top of the parapet"),
             L("Kd", wind.KD_CC, "", "Table 26.6-1", "buildings, components and cladding"),
             L("0.6h", r["edge"], "ft", "Figure 30.3-2A", "Load Case A, corner: the parapet beside a roof corner zone (zone 3), this far from a building corner"),
             L("a", r["a"], "ft", "Figure 30.3-1", "Load Case B, corner: the parapet within this distance of a building corner (wall zone 5)")]
    lines = [f"{'area':>8}  (GCp):{'wall +':>8}{'roof 2':>8}{'roof 3':>8}{'wall 4':>8}{'wall 5':>8}   net p psf:{'A edge':>9}{'A corner':>10}{'B edge':>9}{'B corner':>10}",
             f"{'ft2':>8}"]
    for x in r["rows"]:
        g, p = x["gcp"], x["p"]
        lines.append(f"{x['area']:>8g}        {g['wall_pos']:>8.2f}{g['roof2']:>8.2f}{g['roof3']:>8.2f}{g['wall4']:>8.2f}{g['wall5']:>8.2f}"
                     f"             {p['A_edge']:>9.1f}{p['A_corner']:>10.1f}{p['B_edge']:>9.1f}{p['B_corner']:>10.1f}")
    info = [("Wind Speed", f"V = {V:g} mi/h ({V_source.strip()})"),
            ("Exposure", f"{exposure} ({exposure_basis.strip()})"),
            ("Topography", f"Kzt = {Kzt:g} ({Kzt_source.strip()})"),
            ("Elevation", f"{elevation_ft:,.0f} ft above sea level ({elevation_source.strip()})" if elevation_ft is not None else "Ke taken as 1.0"),
            ("Building", f"top of parapet {hp_top:g} ft; eave height h = {h_eave:g} ft (parapet {hp_top - h_eave:g} ft high); least horizontal dimension {least_dim:g} ft; "
                         + ("flat roof" if not theta > 0 else f"roof at {theta:g} degrees"))]
    sheet = SimpleSheet(
        mark, "Wind Pressures, Parapets", "Site and Building", "Chapter 30, Part 4", info, [], [],
        "Velocity Pressure and Factors", steps, [],
        ["Pressures are strength-level (ASCE/SEI 7-22 basic wind speed), in psf: the net pressure on the two faces of the parapet together.",
         "p = qp Kd [(GCp) - (GCpi)], Eq. 30.6-1, on each face. The two faces enclose one parapet cavity, so the internal pressure cancels in the net pressure.",
         "Load Case A, windward parapet, net pressure toward the roof: the positive wall value (Figure 30.3-1) on the outside face and the negative roof "
         "zone 2 (edge) or zone 3 (corner) value (Figure 30.3-2A) on the roof side face.",
         "Load Case B, leeward parapet, net pressure away from the roof: the positive wall value on the roof side face and the negative wall zone 4 (edge) "
         "or zone 5 (corner) value on the outside face.",
         "Roof zone 3 values are used as charted, without the change of Figure 30.3-2A note 5.",
         f"Net pressure not less than {wind.MIN_CC:g} psf (Sect. 30.2.2)."],
        ["the parapet as part of the main wind force resisting system (Sect. 27.3.4)", "the parapet's own strength and its anchorage to the wall and roof",
         "the effective wind area of each component (Sect. 26.2)"])
    sheet.blocks.append(dict(title="Net Design Pressure on the Parapet by Effective Wind Area", lines=lines))
    sheet.wind = dict(r)
    return sheet


def seismic_elf_sheet(mark, SDS, SD1, S1, TL, ground_source, R, R_source, Ie, Ie_source, structure, hn, levels, T_analysis=None,
                      T_source="", unit="kips", risk=None, drift=None, wall_lines=None, rho=None, rho_source="", system=None):
    """Seismic base shear and story forces, ASCE/SEI 7-22 Sect. 12.8 (see seismic.py).
    levels: [(name, weight, height above the base ft)]."""
    from . import seismic
    for nm, v in (("the source of the ground motion values", ground_source), ("the source of R", R_source), ("the source of Ie", Ie_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if T_analysis is not None and not (T_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the period from analysis is blank")
    L = footing_line
    try:
        r = seismic.elf(SDS, SD1, S1, TL, R, Ie, structure, hn, levels, T_analysis)
    except seismic.SeismicError as e:
        raise WorksheetError(f"{mark}: {e}")
    T = r["T"]
    steps = [L("SDS", SDS, "g", "ASCE/SEI 7-22 Sect. 11.4", ground_source.strip()),
             L("SD1", SD1, "g", "Sect. 11.4", ""), L("S1", S1, "g", "Sect. 11.4", ""), L("TL", TL, "s", "Sect. 11.4.6", ""),
             L("R", R, "", "Table 12.2-1", R_source.strip()),
             L("Ie", Ie, "", "Sect. 11.5.1", Ie_source.strip()),
             L(f"Ta = Ct hn^x = {r['Ct']:g} x {hn:g}^{r['x']:g}", r["Ta"], "s", "Eq. 12.8-8, Table 12.8-2", structure)]
    if T_analysis is not None:
        steps += [L("T from analysis", T_analysis, "s", "Sect. 12.8.2", T_source.strip()),
                  L("Cu", f"{r['Cu']:.1f}", "", "Table 12.8-1", f"upper limit Cu Ta = {r['Cu'] * r['Ta']:.3f} s"),
                  L("T", T, "s", "Sect. 12.8.2", r["T_note"])]
    else:
        steps += [L("T", T, "s", "Sect. 12.8.2", "taken as Ta")]
    cat = None
    if risk:
        try:
            cat = seismic.sdc(SDS, SD1, S1, risk)
        except seismic.SeismicError as e:
            raise WorksheetError(f"{mark}: {e}")
        steps += [L("Seismic Design Category", cat[0], "", "Sect. 11.6, Tables 11.6-1, 11.6-2",
                    f"Risk Category {risk}; by SDS: {cat[1]}; by SD1: {cat[2]}; {cat[3]}")]
    steps += [L("Cs = SDS / (R/Ie)", f"{r['Cs_123']:.4f}", "", "Eq. 12.8-3"),
              L("Cs need not exceed " + ("SD1 / [T (R/Ie)]" if r["cap_eq"] == "Eq. 12.8-4" else "SD1 TL / [T^2 (R/Ie)]"), f"{r['Cs_cap']:.4f}", "", r["cap_eq"]),
              L("Cs not less than 0.044 SDS Ie, 0.01", f"{r['Cs_min']:.4f}", "", "Eq. 12.8-6")]
    if r["Cs_s1"] is not None:
        steps += [L("Cs not less than 0.5 S1 / (R/Ie)", f"{r['Cs_s1']:.4f}", "", "Eq. 12.8-7", "S1 is 0.6 or more")]
    steps += [L("Cs", f"{r['Cs']:.4f}", "", r["governs"]),
              L("W", r["W"], unit, "Sect. 12.7.2", "the sum of the level weights entered"),
              L("V = Cs W", r["V"], unit, "Eq. 12.8-1"),
              L("k", r["k"], "", "Sect. 12.8.3", f"T = {T:.3f} s")]
    lines = [f"{'level':<16}{'wx ' + unit:>11}{'hx ft':>9}{'wx hx^k':>13}{'Cvx':>8}{'Fx ' + unit:>11}{'Vx ' + unit:>11}{'Mx ' + unit[:-1] + '-ft':>13}"]
    for x in r["rows"]:
        lines.append(f"{str(x['name'])[:15]:<16}{x['w']:>11,.1f}{x['h']:>9.2f}{x['whk']:>13,.0f}{x['Cvx']:>8.3f}{x['F']:>11.2f}{x['V']:>11.2f}{x['M']:>13,.1f}")
    lines.append(f"{'base':<16}{r['W']:>11,.1f}{'':>9}{'':>13}{1.0:>8.3f}{r['V']:>11.2f}{r['V']:>11.2f}{r['M_base']:>13,.1f}")
    info = [("Ground Motion", f"SDS = {SDS:g}, SD1 = {SD1:g}, S1 = {S1:g}, TL = {TL:g} s ({ground_source.strip()})"),
            ("System", f"R = {R:g} ({R_source.strip()})"),
            ("Importance", f"Ie = {Ie:g} ({Ie_source.strip()})"),
            ("Structure", f"structural height hn = {hn:g} ft; period type: {structure}; {len(levels)} level" + ("s" if len(levels) != 1 else ""))]
    sheet = SimpleSheet(
        mark, "Seismic Base Shear and Story Forces", "Site and Building", "Sect. 12.8", info, [], [],
        "Base Shear", steps, [],
        ["Forces are strength-level seismic forces QE, before the redundancy factor.",
         "Fx = Cvx V, Cvx = wx hx^k / sum(wi hi^k), Eq. 12.8-12 and 12.8-13. Vx: story shear below the level, Eq. 12.8-14. "
         "Mx: overturning moment at the level, from the forces above it.",
         "Level weights are the effective seismic weights of Sect. 12.7.2, as entered."],
        ["whether the equivalent lateral force procedure is permitted (Table 12.6-1)", ("" if risk else "the Seismic Design Category (Sect. 11.6) and ") + "system limits and height limits (Table 12.2-1)",
         "the redundancy factor (Sect. 12.3.4) and the vertical seismic load effect (Sect. 12.4.2.2)", "structural irregularities (Sect. 12.3.2)",
         "torsion (Sect. 12.8.4), story drift (Sect. 12.8.6) and P-delta effects (Sect. 12.8.7)",
         "diaphragm transfer forces, collectors and their overstrength forces (Sect. 12.10.1.1, 12.10.2)"])
    sheet.blocks.append(dict(title="Story Forces", picture=("seismic_forces", dict(rows=r["rows"], V=r["V"], unit=unit, hn=hn))))
    sheet.blocks.append(dict(title="Vertical Distribution", lines=lines))
    dl = [f"{'level':<16}{'wpx ' + unit:>11}{'Eq. 12.10-1':>13}{'minimum':>10}{'maximum':>10}{'Fpx ' + unit:>11}   governed by"]
    for x in r["rows"]:
        dl.append(f"{str(x['name'])[:15]:<16}{x['wp']:>11,.1f}{x['Fpx_eq']:>13.2f}{x['Fpx_min']:>10.2f}{x['Fpx_max']:>10.2f}{x['Fpx']:>11.2f}   {x['Fpx_by']}")
    sheet.blocks.append(dict(title="Diaphragm Design Forces", lines=dl, after=[
        "Fpx = (sum of Fi at and above the level / sum of wi at and above the level) wpx, Eq. 12.10-1; not less than 0.2 SDS Ie wpx, Eq. 12.10-2; "
        "need not exceed 0.4 SDS Ie wpx, Eq. 12.10-3. wpx is the weight tributary to the diaphragm: the level weight unless a diaphragm weight is entered."]))
    if wall_lines:                              # [(wall or frame line, level name, percent of the story shear below that level)]
        if rho not in (1.0, 1.3):
            raise WorksheetError(f"{mark}: the redundancy factor for the wall lines is 1.0 or 1.3 (Sect. 12.3.4)")
        if not (rho_source or "").strip():
            raise WorksheetError(f"{mark}: the basis of the redundancy factor is blank")
        by = {str(x["name"]).strip().lower(): x for x in r["rows"]}
        wl = [f"{'line':<14}{'story below':<16}{'Vx ' + unit:>10}{'share %':>9}{'QE ' + unit:>10}{'rho QE ' + unit:>13}{'0.7 rho QE ' + unit:>17}"]
        out_lines, tot = [], {}
        for nm, lvl, pct in wall_lines:
            x = by.get(str(lvl).strip().lower())
            if x is None:
                raise WorksheetError(f"{mark}: wall line {nm}: '{lvl}' is not one of the levels")
            if pct is None or pct <= 0 or pct > 100:
                raise WorksheetError(f"{mark}: wall line {nm}: the share is between 0 and 100 percent")
            q = x["V"] * pct / 100.0
            tot[x["name"]] = tot.get(x["name"], 0.0) + pct
            out_lines.append(dict(line=nm, level=x["name"], Vx=x["V"], share=pct, QE=q, Eh=rho * q, asd=0.7 * rho * q))
            wl.append(f"{str(nm)[:13]:<14}{str(x['name'])[:15]:<16}{x['V']:>10.2f}{pct:>9.1f}{q:>10.2f}{rho * q:>13.2f}{0.7 * rho * q:>17.2f}")
        notes = [f"Each line takes the listed share of the story shear below the level (as entered). Eh = rho QE, Eq. 12.4-3, rho = {rho:g} "
                 f"({rho_source.strip()}). 0.7 rho QE is the horizontal seismic load effect in the allowable stress design combinations (Sect. 2.4.5)."]
        sheet.blocks.append(dict(title="Shear to Each Wall or Frame Line", lines=wl, after=notes))
        sheet.assumptions.append("Shares of the story shear to the wall or frame lines total: "
                                 + "; ".join(f"{k} {v:g} percent" for k, v in tot.items()) + ".")
        sheet.not_checked = [t.replace("the redundancy factor (Sect. 12.3.4) and the vertical seismic load effect (Sect. 12.4.2.2)",
                                       "the value of the redundancy factor (Sect. 12.3.4.2) and the vertical seismic load effect (Sect. 12.4.2.2)")
                             for t in sheet.not_checked] + ["how the story shear divides among the lines (diaphragm flexibility, Sect. 12.3.1; torsion, Sect. 12.8.4)"]
        r = dict(r, lines=out_lines)
    if drift:                                   # dict(Cd, Cd_source, structure, de={level name: elastic displacement in}, de_source)
        for nm, v in (("the source of Cd", drift.get("Cd_source")), ("the source of the elastic displacements", drift.get("de_source"))):
            if not (v or "").strip():
                raise WorksheetError(f"{mark}: {nm} is blank")
        if not risk:
            raise WorksheetError(f"{mark}: the Risk Category is needed for the drift limit")
        try:
            dr = seismic.drift([(nm, h, drift["de"].get(str(nm))) for nm, w, h in [tuple(x[:3]) for x in levels]], drift["Cd"], Ie, drift["structure"], risk)
        except seismic.SeismicError as e:
            raise WorksheetError(f"{mark}: {e}")
        tl = [f"{'story below':<16}{'hsx ft':>9}{'Cd de / Ie in':>16}{'drift in':>11}{'allowable in':>14}"]
        for x in dr:
            tl.append(f"{str(x['name'])[:15]:<16}{x['hsx']:>9.2f}{x['dDE']:>16.3f}{x['drift']:>11.3f}{x['allow']:>14.3f}")
            sheet.rows.append(Row(f"Story drift below {x['name']}", "E", x["drift"], x["allow"], "in", "Sect. 12.8.6, 12.12.1, Table 12.12-1",
                                  f"{x['factor']:g} hsx"))
        sheet.blocks.append(dict(title="Story Drift", lines=tl, after=[
            f"Design earthquake displacement = Cd de / Ie, Eq. 12.8-16, Cd = {drift['Cd']:g} ({drift['Cd_source'].strip()}); elastic displacements de: "
            f"{drift['de_source'].strip()}. Allowable story drift {dr[0]['factor']:g} hsx, Table 12.12-1: {drift['structure']}, Risk Category {risk}."]))
        sheet.not_checked = [t.replace("torsion (Sect. 12.8.4), story drift (Sect. 12.8.6) and P-delta effects (Sect. 12.8.7)",
                                       "torsion (Sect. 12.8.4) and P-delta effects (Sect. 12.8.7)") for t in sheet.not_checked]
        sheet.not_checked += ["how the elastic displacements were found (forces, period, torsion: Sect. 12.8.6.1, 12.8.6.2)",
                              "the drift limit divided by the redundancy factor for moment frames in Seismic Design Category D, E or F (Sect. 12.12.1.1)",
                              "building separation (Sect. 12.12.2)"]
        r = dict(r, drift=dr)
    if system:
        if not cat:
            raise WorksheetError(f"{mark}: the Risk Category is needed to check the system against Table 12.2-1")
        try:
            sy = seismic.system(system, cat[0])
        except seismic.SeismicError as e:
            raise WorksheetError(f"{mark}: {e}")
        note = f", with note {sy['note']} of the table" if sy["note"] else ""
        if not sy["permitted"] and not sy["note"]:
            raise WorksheetError(f"{mark}: Table 12.2-1 line {sy['line']} does not permit this system in Seismic Design Category {cat[0]}")
        if not sy["permitted"]:
            sheet.rows.append(Row(f"System in Seismic Design Category {cat[0]}", "", 1.0, 0.0, "", f"Table 12.2-1 line {sy['line']}",
                                  f"not permitted, except as note {sy['note']} of the table allows"))
        elif sy["limit"] is not None:
            sheet.rows.append(Row("Structural height", "", hn, sy["limit"], "ft", f"Table 12.2-1 line {sy['line']}",
                                  f"limit in Seismic Design Category {cat[0]}{note}"))
        sheet.not_checked = [t for t in sheet.not_checked if "system limits and height limits" not in t]
        sheet.not_checked.append("the detailing requirements of the system (Chapter 14)" + (f" and note {sy['note']} of Table 12.2-1" if sy["note"] else ""))
        r = dict(r, system=sy)
    if cat:
        sheet.info.insert(3, ("Category", f"Risk Category {risk}; Seismic Design Category {cat[0]}"))
        r = dict(r, sdc=cat[0])
    sheet.seismic = r
    return sheet


def live_load_sheet(mark, floors, roofs):
    """Reduced uniform live loads, ASCE/SEI 7-22 Sect. 4.7 (floors) and 4.8 (ordinary roofs).
    floors: [dict(name, element, AT, Lo, source, floors, occupancy)]; roofs: [dict(name, AT, F, Lo, source)]."""
    from . import liveload
    if not floors and not roofs:
        raise WorksheetError(f"{mark}: enter at least one floor member or roof member")
    fl, rf = [], []
    try:
        for x in floors or []:
            if not (x.get("source") or "").strip():
                raise WorksheetError(f"{mark}: {x['name']}: the source of the live load is blank")
            fl.append((x, liveload.floor(x["Lo"], x["element"], x["AT"], x["floors"], x.get("occupancy") or "ordinary")))
        for x in roofs or []:
            if not (x.get("source") or "").strip():
                raise WorksheetError(f"{mark}: {x['name']}: the source of the roof live load is blank")
            rf.append((x, liveload.roof(x["Lo"], x["AT"], x["F"])))
    except liveload.LiveLoadError as e:
        raise WorksheetError(f"{mark}: {e}")
    sheet = SimpleSheet(
        mark, "Live Load Reduction", "Members", "Sect. 4.7, 4.8",
        [("Members", f"{len(fl)} floor member" + ("s" if len(fl) != 1 else "") + f", {len(rf)} roof member" + ("s" if len(rf) != 1 else ""))],
        [], [], "", [], [],
        (["Floors: L = Lo (0.25 + 15 / sqrt(KLL AT)), Eq. 4.7-1, for KLL AT of 400 ft2 or more; not less than 0.50 Lo for one floor supported and "
          "0.40 Lo for two or more; live loads over 100 psf and passenger vehicle garages are reduced only for two or more floors, by at most "
          "20 percent (Sect. 4.7.3, 4.7.4); assembly areas are not reduced (Sect. 4.7.5). KLL from Table 4.7-1."] if fl else [])
        + (["Roofs: Lr = Lo R1 R2, not less than 12 psf and not more than 20 psf, Eq. 4.8-1; R1 by tributary area, R2 by the rise F in inches per foot."] if rf else []),
        ["the tributary area of each member", "the one-way slab area limit (Sect. 4.7.6)", "roofs with an occupancy (Sect. 4.8.3)",
         "partial loading of the reduced load (Sect. 4.3.3)"])
    if fl:
        def short(by):
            return ("0.50 Lo minimum" if "minimum 0.50" in by else "0.40 Lo minimum" if "minimum 0.40" in by else "20 percent limit" if "exception" in by
                    else "not reduced" if "not reduced" in by else "Eq. 4.7-1")
        t = [f"{'member':<10}{'element':<41}{'Lo psf':>7}{'AT ft2':>8}{'floors':>7}{'KLL AT':>8}{'factor':>7}{'L psf':>7}   by"]
        for x, r in fl:
            t.append(f"{str(x['name'])[:9]:<10}{x['element'][:40]:<41}{x['Lo']:>7g}{x['AT']:>8,.0f}{int(x['floors']):>7d}{r['KLL_AT']:>8,.0f}{r['factor']:>7.3f}{r['L']:>7.1f}   {short(r['by'])}")
        occ = sorted({(x.get('occupancy') or 'ordinary') for x, r in fl if (x.get('occupancy') or 'ordinary') != 'ordinary'})
        sheet.blocks.append(dict(title="Floor Members", lines=t, after=["Unreduced loads Lo: " + "; ".join(sorted({f"{x['Lo']:g} psf ({x['source'].strip()})" for x, r in fl})) + "."]
                                 + (["Occupancy: " + "; ".join(f"{x['name']}: {x['occupancy']}" for x, r in fl if (x.get('occupancy') or 'ordinary') != 'ordinary') + "."] if occ else [])))
    if rf:
        t = [f"{'member':<14}{'Lo psf':>8}{'AT ft2':>9}{'F in/ft':>9}{'R1':>7}{'R2':>7}{'Lr psf':>8}   by"]
        for x, r in rf:
            t.append(f"{str(x['name'])[:13]:<14}{x['Lo']:>8g}{x['AT']:>9,.0f}{x['F']:>9g}{r['R1']:>7.2f}{r['R2']:>7.2f}{r['Lr']:>8.1f}   {r['by']}")
        sheet.blocks.append(dict(title="Roof Members", lines=t, after=["Unreduced roof loads Lo: " + "; ".join(sorted({f"{x['Lo']:g} psf ({x['source'].strip()})" for x, r in rf})) + "."]))
    sheet.live = dict(floors=[r for x, r in fl], roofs=[r for x, r in rf])
    return sheet


def diaphragm_sheet(mark, panel, face_in, case, panel_type, G, G_source, L, W, w, w_source, load, method, chord_E=None, chord_A=None,
                    splice=(), defl_limit=None, defl_limit_source="", blocked=False, spacing=None):
    """Unblocked or blocked wood structural panel diaphragm, single span between two lines of resistance,
    uniformly loaded, SDPWS-2021 Sect. 4.2 (see diaphragm.py). w is at the level of `method`."""
    from . import diaphragm as dp
    for nm, v in (("the source of the framing specific gravity", G_source), ("the source of the load", w_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    if defl_limit is not None and not (defl_limit_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the deflection limit is blank")
    try:
        r = (dp.blocked(panel, face_in, spacing, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice) if blocked else
             dp.unblocked(panel, face_in, case, panel_type, G, L, W, w, load, method, chord_E, chord_A, splice))
    except dp.DiaphragmError as e:
        raise WorksheetError(f"{mark}: {e}")
    Ln = footing_line
    cname = "Case 1" if case == 1 else "Cases 2 to 6"
    tab = "Table 4.2A" if blocked else "Table 4.2C"
    sp_txt = {2.5: "2-1/2"}.get(spacing, f"{spacing:g}") if blocked else "6"
    nail_txt = (f"nails at {sp_txt} in. at boundaries (and at continuous panel edges parallel to the load, Cases 3 and 4; all panel edges, Cases 5 and 6), "
                f"{dp.OTHER_EDGES[spacing]} in. at other panel edges" if blocked else f"{cname}; nails at 6 in. at boundaries and supported edges")
    steps = [Ln("vn, table", r["vn_table"], "plf", "SDPWS-2021 " + tab, f"{panel}; {face_in} in. nominal nailed face; {nail_txt}"),
             Ln("specific gravity factor, 1 - (0.5 - G)", r["sg"], "", tab + " note 2", f"G = {G:g} ({G_source.strip()})"),
             Ln("vn", r["vn"], "plf", tab),
             Ln(f"capacity = vn {r['factor_text']}", r["capacity"], "plf", "Sect. 4.1.4", f"{load}, {method}"),
             Ln("v = w L / (2 W)", r["v"], "plf", "statics", f"w = {w:g} plf ({w_source.strip()})"),
             Ln("reaction at each line = w L / 2", r["reaction"], "lb", "statics"),
             Ln("chord force T = C = w L^2 / (8 W)", r["chord"], "lb", "statics"),
             Ln("L / W", r["ratio"], "", "Table 4.2.2", ("blocked" if blocked else "unblocked") + f" wood structural panel diaphragm: {r['ratio_max']:g} maximum")]
    rows = [Row("Unit shear", load, r["v"], r["capacity"], "plf", "SDPWS-2021 Sect. 4.2.4, " + tab, ""),
            Row("Aspect ratio L/W", "", r["ratio"], r["ratio_max"], "", "Table 4.2.2", "")]
    not_checked = ["the chords, their splices and connections for the chord force", "the transfer of the reactions to the walls or frames below (collectors, Sect. 4.1.9)",
                   "openings in the diaphragm", "torsion and open front conditions (Sect. 4.2.5, 4.2.6)", "the panel layout and nailing against the cases of the " + tab + " figure"]
    if r["defl"] is not None:
        steps += [Ln("Ga", r["Ga"], "kips/in", tab, panel_type),
                  Ln("bending: 5 v L^3 / (8 E A W)", f"{r['defl_bending']:.3f} in", "", "Eq. 4.2-1", f"chord E = {chord_E:,.0f} psi, A = {chord_A:g} in2"),
                  Ln("shear and nail slip: 0.25 v L / (1000 Ga)", f"{r['defl_shear']:.3f} in", "", "Eq. 4.2-1"),
                  Ln("chord splice slip: sum(x Dc) / (2 W)", f"{r['defl_splice']:.3f} in", "", "Eq. 4.2-1",
                     "; ".join(f"{d:g} in. at {x:g} ft" for x, d in splice) if splice else "no splice slip entered"),
                  Ln("mid-span deflection", f"{r['defl']:.3f} in", "", "Eq. 4.2-1", "at the load level of the design method")]
        if defl_limit is not None:
            rows.append(Row("Mid-span deflection", load, r["defl"], defl_limit, "in", "SDPWS-2021 Eq. 4.2-1; limit: " + defl_limit_source.strip(), ""))
        else:
            not_checked.append("the deflection against a limit (Sect. 4.2.1)")
    else:
        not_checked.append("diaphragm deflection (Sect. 4.2.3)")
    info = [("Sheathing", f"{panel}, {panel_type}, " + (f"blocked, boundary nails at {sp_txt} in." if blocked else f"unblocked, {cname}")), ("Framing", f"{face_in} in. nominal nailed face; G = {G:g} ({G_source.strip()})"),
            ("Diaphragm", f"span L = {L:g} ft between lines of resistance; width W = {W:g} ft"),
            ("Load", f"{load}, w = {w:g} plf at {method} level ({w_source.strip()})")]
    sheet = SimpleSheet(
        mark, "Wood Diaphragm", "Diaphragm", method, info, [], [], "Unit Shear and Chord Force", steps, rows,
        ["Single span, simply supported between two lines of resistance, uniform load over the full span.",
         ("Blocked wood structural panel diaphragm: all adjoining panel edges over and fastened to common framing or blocking (Sect. 4.2.8.1.1)."
          + (" Framing and blocking at adjoining panel edges 3 in. nominal or wider with nails staggered (Sect. 4.2.8.1.1, item 3)."
             if blocked and (spacing <= 2.5 or (spacing == 2 and "10d" in panel)) else "") if blocked else
          "Unblocked wood structural panel diaphragm with common nails at 6 in. on centre at diaphragm boundaries and supported panel edges (Sect. 4.2.8.1.3)."),
         "The load w is entered at the level of the design method."],
        not_checked, picture=None)
    sheet.blocks.append(dict(title="Plan", picture=("diaphragm", dict(L=L, W=W, w=w, v=r["v"], R=r["reaction"], T=r["chord"]))))
    sheet.diaphragm = r
    return sheet


def collector_sheet(mark, W, R, R_source, level, segments, line_name=""):
    """Axial force in a collector (drag strut) along one line of resistance (see
    diaphragm.collector). R: the force the diaphragm delivers to the line, lb, at the load
    level named in `level` (text, for example "seismic, strength level"); segments:
    [dict(start, length)] of the walls on the line, ft."""
    from . import diaphragm
    if not (R_source or "").strip():
        raise WorksheetError(f"{mark}: say where the force on the line comes from")
    if not (level or "").strip():
        raise WorksheetError(f"{mark}: say what load and load level the force is (for example seismic, strength level)")
    try:
        r = diaphragm.collector(W, R, [(x["start"], x["length"]) for x in segments])
    except diaphragm.DiaphragmError as e:
        raise WorksheetError(f"{mark}: {e}")
    Ln = footing_line
    steps = [Ln("force on the line, R", R, "lb", "", f"{level.strip()}; {R_source.strip()}"),
             Ln("vd = R / W", r["vd"], "plf", "", f"diaphragm shear delivered along the line, W = {W:g} ft"),
             Ln("wall length on the line", f"{r['Lw']:g} ft", "", "", f"{len(r['segments'])} length" + ("s" if len(r["segments"]) != 1 else "")),
             Ln("vw = R / wall length", r["vw"], "plf", "", "shear taken out by the walls"),
             Ln("largest collector force", r["Fmax"], "lb", "", f"at {r['x_max']:g} ft; tension or compression as the load reverses")]
    t = [f"{'x ft':>8}{'force lb':>12}   at"]
    ends = {round(a, 6): "start of a wall" for a, b in r["segments"]}
    ends.update({round(a + b, 6): "end of a wall" for a, b in r["segments"]})
    for x, F in r["points"]:
        t.append(f"{x:>8.2f}{F:>12,.0f}   " + ("end of the line" if x in (0.0, W) or abs(x - W) < 1e-9 else ends.get(round(x, 6), "")))
    info = [("Line", (line_name.strip() + "; " if (line_name or "").strip() else "") + f"{W:g} ft long"),
            ("Force", f"{R:,.0f} lb, {level.strip()} ({R_source.strip()})"),
            ("Walls", "; ".join(f"{b:g} ft starting at {a:g} ft" for a, b in r["segments"]))]
    sheet = SimpleSheet(
        mark, "Collector Force", "Line of Resistance", "Sect. 12.10.2", info, [], [], "Shear Along the Line", steps, [],
        ["The diaphragm delivers its shear uniformly along the line; the walls on the line take it in proportion to their lengths.",
         "The collector force at a point is the sum, from one end of the line, of the diaphragm shear delivered less the shear taken out by the walls; "
         "it is zero at both ends of the line. Positive and negative values are of opposite sense and both reverse with the load.",
         "The force is at the load level of the force entered."],
        ["the collector member, its splices and its connections to the walls", "the load combinations with overstrength where Sect. 12.10.2.1 requires them",
         "the diaphragm forces of Eq. 12.10-1 and 12.10-2 and transfer forces (Sect. 12.10.1.1)", "walls of different stiffness sharing the line other than by length",
         "diaphragm shear from both sides of the line where the two differ along it"])
    sheet.blocks.append(dict(title="Collector Force Along the Line", picture=("collector", dict(W=W, segments=r["segments"], points=r["points"], Fmax=r["Fmax"],
                                                                                              vd=r["vd"], vw=r["vw"]))))
    sheet.blocks.append(dict(title="Force at Each Change", lines=t))
    sheet.collector = r
    return sheet


def nailed_connection_sheet(mark, nail_name, D, length, side_t, G_side, G_side_source, main_t, G_main, G_main_source, n, service, loads, combos,
                            end_grain=False, diaphragm=False, toe_nail=False, screw=None):
    """Laterally loaded nailed connection, single shear, wood to wood, 2018 NDS Ch. 11 and 12
    (see dowel.py). loads: [dict(case, P lb)]; combos: ASD combinations. service: "dry",
    "wet in service" or "wet at fabrication, dry in service"."""
    from . import dowel, wood
    fs = "wood screw" if screw else "nail"                # screw: the wood screw number, e.g. "#10"
    if screw and (toe_nail or diaphragm):
        raise WorksheetError(f"{mark}: the toe-nail and diaphragm factors are for nails")
    for nm, v in (("the source of the side member specific gravity", G_side_source), ("the source of the main member specific gravity", G_main_source),
                  (f"the {fs} description", nail_name)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    CMs = {"dry": 1.0, "wet in service": 0.7, "wet at fabrication, dry in service": 0.7}
    if service not in CMs:
        raise WorksheetError(f"{mark}: the service condition is one of: " + "; ".join(CMs))
    if n is None or n < 1 or int(n) != n:
        raise WorksheetError(f"{mark}: the number of {fs}s is a whole number, 1 or more")
    if D is None or D <= 0 or D >= 0.25:
        raise WorksheetError(f"{mark}: the {fs} diameter is under 1/4 in.")
    for nm, v in ((f"the {fs} length", length), ("the side member thickness", side_t), ("the main member thickness", main_t)):
        if v is None or v <= 0:
            raise WorksheetError(f"{mark}: {nm} must be positive")
    ls = side_t
    if toe_nail:                                          # NDS 12.1.6.3, 12.3.10.2, Figure 12A
        import math as _m
        ls = min(side_t, length / 3.0)
        p = min(length * _m.cos(_m.radians(30.0)) - length / 3.0, main_t)
    else:
        p = min(length - side_t, main_t)
    if p <= 0:
        raise WorksheetError(f"{mark}: the {fs} does not reach the main member")
    if p < 6 * D:
        raise WorksheetError(f"{mark}: the penetration into the main member, {p:.2f} in., is less than 6 D = {6 * D:.2f} in. (NDS 12.1.6.4)")
    try:
        r = dowel.wood_screw(screw, ls, G_side, G_main, penetration=p) if screw else dowel.nail(D, ls, G_side, G_main, penetration=p)
    except dowel.DowelError as e:
        raise WorksheetError(f"{mark}: {e}")
    CM, Ceg, Cdi, Ctn = CMs[service], (0.67 if end_grain else 1.0), (1.1 if diaphragm else 1.0), (0.83 if toe_nail else 1.0)
    base = r["Z"] * CM * Ceg * Cdi * Ctn
    Ln = footing_line
    modes = r["modes"]
    steps = [Ln("D", f"{D:g} in", "", "NDS Table L3" if screw else "NDS Table L4", f"{nail_name.strip()}, {length:g} in. long"),
             *([Ln("Dr", f"{r['Dr']:g} in", "", "NDS Table L3, 12.3.7.1(c)", "root diameter, used in the yield equations")] if screw else []),
             Ln("penetration into the main member, p" + (" = L cos 30 - L/3" if toe_nail else ""), f"{p:.2f} in", "", ("NDS 12.1.5.6" if screw else "NDS 12.1.6.4") + (", Figure 12A" if toe_nail else ""),
                f"not less than 6 D = {6 * D:.2f} in."),
             Ln("ls, lm", f"{ls:.3g} in, {r['lm']:.2f} in", "", "NDS 12.3.5" + (", 12.3.10.2" if toe_nail else ""),
                ("ls = the lesser of the side member thickness and L/3; " if toe_nail else "") + "lm = p less half the tapered tip (E = 2 D)"),
             Ln("Fes", dowel.fe(G_side, r["Dr"] if screw else D), "psi", "NDS Table 12.3.3", f"G = {G_side:g} ({G_side_source.strip()})"),
             Ln("Fem", dowel.fe(G_main, r["Dr"] if screw else D), "psi", "NDS Table 12.3.3", f"G = {G_main:g} ({G_main_source.strip()})"),
             Ln("Fyb", r["Fyb"], "psi", "NDS Table 12L note 2" if screw else "NDS Table 12N note 2"),
             Ln("Rd = KD", dowel.rd(r["Dr"] if screw else D, "IV"), "", "NDS Table 12.3.1B")]
    names = {"Im": "Eq. 12.3-1", "Is": "Eq. 12.3-2", "II": "Eq. 12.3-3", "IIIm": "Eq. 12.3-4", "IIIs": "Eq. 12.3-5", "IV": "Eq. 12.3-6"}
    for m in ("Im", "Is", "II", "IIIm", "IIIs", "IV"):
        steps.append(Ln(f"Z, mode {m}", modes[m], "lb", "NDS " + names[m]))
    steps += [Ln("Z", r["Z"], "lb", "NDS 12.3.1", f"mode {r['mode']} governs"),
              Ln("CM", CM, "", "NDS Table 11.3.3", service), Ln("Cg", 1.0, "", "NDS 11.3.6.1", "D under 1/4 in."),
              Ln("C-delta", 1.0, "", "NDS 12.5.1.1", "D under 1/4 in.")]
    if end_grain:
        steps.append(Ln("Ceg", Ceg, "", "NDS 12.5.2.2", f"{fs} in the end grain of the main member"))
    if diaphragm:
        steps.append(Ln("Cdi", Cdi, "", "NDS 12.5.3", "diaphragm construction"))
    if toe_nail:
        steps.append(Ln("Ctn", Ctn, "", "NDS 12.5.4.2", "toe-nailed connection"))
    rows, worst = [], None
    for cb in combos:
        P = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads)
        present = [ld["case"] for ld in loads if cb.factors.get(ld["case"], 0.0) and ld["P"]]
        if not present or abs(P) < 1e-9:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        cap = n * base * CD
        g = dict(name=cb.name, P=abs(P), CD=CD, cd_case=cd_case, cd_dur=cd_dur, cap=cap, source=cb.source)
        if worst is None or g["P"] / cap > worst["P"] / worst["cap"]:
            worst = g
    if worst is None:
        raise WorksheetError(f"{mark}: no load combination puts load on the connection")
    steps += [Ln("CD", worst["CD"], "", "NDS Table 2.3.2", f"{worst['cd_case']}, {worst['cd_dur']}; combination {worst['name']}"),
              Ln("Z' = Z CD CM Ct Cg C-delta" + (" Ceg" if end_grain else "") + (" Cdi" if diaphragm else "") + (" Ctn" if toe_nail else ""), base * worst["CD"], "lb", "NDS Table 11.3.1", "Ct = 1.0"),
              Ln(f"capacity = {int(n)} Z'", worst["cap"], "lb", "")]
    rows = [Row(f"Lateral load on the {fs}s", worst["name"], worst["P"], worst["cap"], "lb", "NDS Table 11.3.1, 12.3.1", f"{int(n)} {fs}s; mode {r['mode']}"),
            Row("Wood screw penetration" if screw else "Nail penetration", "", 6 * D, p, "in", "NDS 12.1.5.6" if screw else "NDS 12.1.6.4", "6 D minimum against the penetration provided")]
    info = [("Fastener", f"{int(n)} - {nail_name.strip()} {fs}s, {D:g} in. diameter x {length:g} in. long, single shear"),
            ("Side Member", f"{side_t:g} in. thick, G = {G_side:g} ({G_side_source.strip()})"),
            ("Main Member", f"{main_t:g} in. thick, G = {G_main:g} ({G_main_source.strip()})"),
            ("Conditions", service + " service" + (f"; {fs}s in the end grain of the main member" if end_grain else "") + ("; diaphragm construction" if diaphragm else "") + ("; toe-nailed" if toe_nail else ""))]
    load_lines = [f"{ld['case']}: {ld['P']:,.0f} lb" + (f"  ({ld['label']})" if ld.get("label") else "") for ld in loads]
    sheet = SimpleSheet(
        mark, "Wood Screw Connection" if screw else "Nailed Connection", "Connection", "ASD", info, load_lines, [(f"{worst['name']}", worst["source"])], "Lateral Design Value", steps, rows,
        [("Standard wood screws (NDS Table L3) turned into lead holes bored to NDS 12.1.5.3, into side grain perpendicular to the wood fibers" if screw else
          "Common, box or sinker steel wire nails driven into side grain perpendicular to the wood fibers") + (" of the side member" if end_grain else "") + f", members in contact, load perpendicular to the {fs}.",
         "Sustained temperature not over 100 degrees F (Ct = 1.0, NDS Table 11.3.4).",
         f"All {fs}s share the load equally."]
        + (["Toe-nails driven at about 30 degrees to the side member and started about one third of the nail length from its end (NDS 12.1.6.3, Figure 12A); "
            "the penetration into the main member is the projection of the nail along the side member, L cos 30 - L/3."] if toe_nail else []),
        [("wood screw spacing, edge and end distances against splitting (NDS 12.1.5.7)" if screw else "nail spacing, edge and end distances against splitting (NDS 12.1.6.5)"), "the members at the connection: net section, shear at the connection (NDS 3.4.3.3) and local stresses (NDS 11.1.2, Appendix E)",
         "withdrawal and combined lateral and withdrawal loading"] + ([] if (toe_nail or screw) else ["toe-nailed connections (NDS 12.1.6.3, 12.5.4)"]))
    sheet.blocks.append(dict(title="Section", picture=("toe_nail" if toe_nail else "nailed", dict(side_t=side_t, main_t=main_t, length=length, p=p, D=D,
                                                                      label=f"{nail_name.strip()}, {D:g} x {length:g} in.", screw=bool(screw)))))
    sheet.connection = dict(r, Zp=base * worst["CD"], n=int(n), capacity=worst["cap"], demand=worst["P"], CM=CM)
    return sheet


def nail_withdrawal_sheet(mark, nail_name, D, length, head, side_t, G_side, G_side_source, main_t, G_main, G_main_source, n, service, loads, combos, toe_nail=False):
    """Nails loaded in withdrawal from side grain, with head pull-through of the side member,
    2018 NDS 12.2.3 and 12.2.5 (see dowel.py). Smooth shank carbon steel nails. loads:
    [dict(case, P lb)], P pulling the side member off the main member; combos: ASD combinations.
    service: one of the four conditions of Table 11.3.3."""
    import math as _m
    from . import dowel, wood
    for nm, v in (("the source of the side member specific gravity", G_side_source), ("the source of the main member specific gravity", G_main_source),
                  ("the nail description", nail_name)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    CMs = {"dry": (1.0, 1.0), "wet in service": (0.25, 0.7), "wet at fabrication, dry in service": (0.25, 1.0), "wet at fabrication and in service": (1.0, 0.7)}
    if service not in CMs:
        raise WorksheetError(f"{mark}: the service condition is one of: " + "; ".join(CMs))
    if n is None or n < 1 or int(n) != n:
        raise WorksheetError(f"{mark}: the number of nails is a whole number, 1 or more")
    for nm, v in (("the nail diameter", D), ("the nail length", length), ("the side member thickness", side_t), ("the main member thickness", main_t)):
        if v is None or v <= 0:
            raise WorksheetError(f"{mark}: {nm} must be positive")
    if not toe_nail and (head is None or head <= 0):
        raise WorksheetError(f"{mark}: the nail head diameter is blank")
    pt = min(length * _m.cos(_m.radians(30.0)) - length / 3.0, main_t) if toe_nail else min(length - side_t, main_t)
    if pt <= 0:
        raise WorksheetError(f"{mark}: the nail does not reach the main member")
    try:
        W = dowel.nail_withdrawal(G_main, D)
        pth = None if toe_nail else dowel.pull_through(head, G_side, side_t)
    except dowel.DowelError as e:
        raise WorksheetError(f"{mark}: {e}")
    CMw, CMh = CMs[service]
    if toe_nail:
        CMw = 1.0
    Ctn = 0.67 if toe_nail else 1.0
    Ln = footing_line
    steps = [Ln("D", f"{D:g} in", "", "NDS Table L4", f"{nail_name.strip()}, {length:g} in. long"),
             Ln("W = 1380 G^2.5 D", W, "lb/in", "NDS Eq. 12.2-3", f"G = {G_main:g} ({G_main_source.strip()})"),
             Ln("penetration into the main member, pt" + (" = L cos 30 - L/3" if toe_nail else ""), f"{pt:.2f} in", "", "NDS 12.2.3.1(c)" + (", Figure 12A" if toe_nail else "")),
             Ln("W pt", W * pt, "lb", "NDS 12.2.3.1(c)", "one nail")]
    steps.append(Ln("CM, withdrawal", CMw, "", "NDS Table 11.3.1 note 2, 12.5.4.1" if toe_nail else "NDS Table 11.3.3", "does not apply to toe-nails" if toe_nail else service))
    if toe_nail:
        steps.append(Ln("Ctn", Ctn, "", "NDS 12.5.4.1", "toe-nailed connection"))
    else:
        steps += [Ln("DH", f"{head:g} in", "", "NDS Table L4", "head diameter"),
                  Ln("WH = 690 pi DH G^2 tns" if pth["thin"] else "WH = 1725 pi DH^2 G^2", pth["WH"], "lb", f"NDS Eq. {pth['eq']}",
                     f"G = {G_side:g} ({G_side_source.strip()}); tns = {side_t:g} in. {'not over' if pth['thin'] else 'over'} 2.5 DH = {2.5 * head:.2f} in."),
                  Ln("CM, pull-through", CMh, "", "NDS Table 11.3.3", service)]
    base_w = W * pt * CMw * Ctn
    base_h = pth["WH"] * CMh if pth else None
    worst = None
    for cb in combos:
        P = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads)
        present = [ld["case"] for ld in loads if cb.factors.get(ld["case"], 0.0) and ld["P"]]
        if not present or P < 1e-9:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        cap = n * min(base_w, base_h if base_h is not None else base_w) * CD
        g = dict(name=cb.name, P=P, CD=CD, cd_case=cd_case, cd_dur=cd_dur, cap=cap, source=cb.source)
        if worst is None or g["P"] / cap > worst["P"] / worst["cap"]:
            worst = g
    if worst is None:
        raise WorksheetError(f"{mark}: no load combination pulls on the connection")
    CD = worst["CD"]
    steps += [Ln("CD", CD, "", "NDS Table 2.3.2", f"{worst['cd_case']}, {worst['cd_dur']}; combination {worst['name']}"),
              Ln("W' pt = W pt CD CM Ct" + (" Ctn" if toe_nail else ""), base_w * CD, "lb", "NDS Table 11.3.1", "Ct = 1.0; one nail")]
    rows = [Row("Withdrawal of the nails", worst["name"], worst["P"], n * base_w * CD, "lb", "NDS Table 11.3.1, 12.2.3", f"{int(n)} nails")]
    if pth:
        steps.append(Ln("W'H = WH CD CM Ct", base_h * CD, "lb", "NDS Table 11.3.1", "Ct = 1.0; one nail"))
        rows.append(Row("Head pull-through of the side member", worst["name"], worst["P"], n * base_h * CD, "lb", "NDS Table 11.3.1, 12.2.5", f"{int(n)} nails"))
    info = [("Fastener", f"{int(n)} - {nail_name.strip()} nails, {D:g} in. diameter x {length:g} in. long" + ("" if toe_nail else f", {head:g} in. head")),
            ("Side Member", f"{side_t:g} in. thick, G = {G_side:g} ({G_side_source.strip()})"),
            ("Main Member", f"{main_t:g} in. thick, G = {G_main:g} ({G_main_source.strip()})"),
            ("Conditions", service + ("" if service.endswith("service") else " service") + ("; toe-nailed" if toe_nail else ""))]
    load_lines = [f"{ld['case']}: {ld['P']:,.0f} lb" + (f"  ({ld['label']})" if ld.get("label") else "") for ld in loads]
    sheet = SimpleSheet(
        mark, "Nails in Withdrawal", "Connection", "ASD", info, load_lines, [(f"{worst['name']}", worst["source"])], "Withdrawal Design Value", steps, rows,
        ["Smooth shank (bright or galvanized) carbon steel nails driven into the side grain of the main member, perpendicular to the wood fibers; load along the nail.",
         "Sustained temperature not over 100 degrees F (Ct = 1.0, NDS Table 11.3.4).",
         "All nails share the load equally."]
        + (["Toe-nails driven at about 30 degrees to the side member and started about one third of the nail length from its end (NDS 12.1.6.3, Figure 12A); "
            "the penetration into the main member is taken as L cos 30 - L/3."] if toe_nail else []),
        ["nail spacing, edge and end distances against splitting (NDS 12.1.6.5)", "the members at the connection",
         "combined lateral and withdrawal loading (NDS 12.4.1)"] + (["head pull-through at the toe-nails"] if toe_nail else []))
    sheet.blocks.append(dict(title="Section", picture=("toe_nail" if toe_nail else "nailed", dict(side_t=side_t, main_t=main_t, length=length, p=pt, D=D,
                                                       label=f"{nail_name.strip()}, {D:g} x {length:g} in.", withdrawal=True))))
    sheet.connection = dict(W=W, pt=pt, WH=pth["WH"] if pth else None, capacity=worst["cap"], demand=worst["P"], CD=CD, CM=CMw)
    return sheet


def lag_withdrawal_sheet(mark, D, length, n, side_t, main_t, G_main, G_main_source, service, loads, combos, washer=0.0, end_grain=False,
                         edge=None, end=None, spacing=None, steel=None, steel_source="", steel_side=False):
    """Lag screws loaded in withdrawal, 2018 NDS 12.2.1 (see dowel.py). side_t: thickness of
    the part the screw passes through (wood or steel). loads: [dict(case, P lb)], P pulling
    the screw out; combos: ASD combinations. service: "dry" or "wet in service". steel:
    allowable tension of one screw, lb (optional, with its source). edge, end, spacing:
    provided distances, in. (optional; checked against Table 12.5.1E)."""
    from . import dowel, wood
    if not (G_main_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the main member specific gravity is blank")
    CMs = {"dry": 1.0, "wet in service": 0.7}
    if service not in CMs:
        raise WorksheetError(f"{mark}: the service condition is one of: " + "; ".join(CMs))
    if n is None or n < 1 or int(n) != n:
        raise WorksheetError(f"{mark}: the number of lag screws is a whole number, 1 or more")
    if side_t is None or side_t < 0 or main_t is None or main_t <= 0:
        raise WorksheetError(f"{mark}: the side and main member thicknesses are needed")
    if steel is not None and not (steel_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the screw's allowable tension is blank")
    washer = washer or 0.0
    try:
        th = dowel.lag_thread(D, length)
        W = dowel.lag_withdrawal(G_main, D)
    except dowel.DowelError as e:
        raise WorksheetError(f"{mark}: {e}")
    in_main = length - washer - side_t
    if in_main > main_t + 1e-9:
        raise WorksheetError(f"{mark}: the lag screw is longer than the washer, side member and main member together")
    pt = min(th["T"], in_main) - th["E"]
    if pt <= 0:
        raise WorksheetError(f"{mark}: no thread reaches the main member beyond the tapered tip")
    CM, Ceg = CMs[service], (0.75 if end_grain else 1.0)
    Ln = footing_line
    steps = [Ln("W = 1800 G^1.5 D^0.75", W, "lb/in", "NDS Eq. 12.2-1", f"G = {G_main:g} ({G_main_source.strip()}); D = {D:g} in."),
             Ln("thread length T, tapered tip E", f"{th['T']:g} in, {th['E']:.3f} in", "", "NDS Table L2", f"{length:g} in. lag screw"),
             Ln("length in the main member", f"{in_main:.3f} in", "", "", f"L - {'washer - ' if washer else ''}side member"),
             Ln("thread penetration, pt", f"{pt:.3f} in", "", "NDS 12.2.1.2", "the lesser of T and the length in the main member, less E"),
             Ln("W pt", W * pt, "lb", "NDS 12.2.1.2", "one lag screw"),
             Ln("CM", CM, "", "NDS Table 11.3.3", service)]
    if end_grain:
        steps.append(Ln("Ceg", Ceg, "", "NDS 12.2.1.3", "withdrawal from end grain"))
    base = W * pt * CM * Ceg
    worst = None
    for cb in combos:
        P = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads)
        present = [ld["case"] for ld in loads if cb.factors.get(ld["case"], 0.0) and ld["P"]]
        if not present or P < 1e-9:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        g = dict(name=cb.name, P=P, CD=CD, cd_case=cd_case, cd_dur=cd_dur, cap=n * base * CD, source=cb.source)
        if worst is None or g["P"] / g["cap"] > worst["P"] / worst["cap"]:
            worst = g
    if worst is None:
        raise WorksheetError(f"{mark}: no load combination pulls on the connection")
    steps += [Ln("CD", worst["CD"], "", "NDS Table 2.3.2", f"{worst['cd_case']}, {worst['cd_dur']}; combination {worst['name']}"),
              Ln("W' pt = W pt CD CM Ct" + (" Ceg" if end_grain else ""), base * worst["CD"], "lb", "NDS Table 11.3.1", "Ct = 1.0; one lag screw"),
              Ln(f"capacity = {int(n)} W' pt", worst["cap"], "lb", "")]
    rows = [Row("Withdrawal of the lag screws", worst["name"], worst["P"], worst["cap"], "lb", "NDS Table 11.3.1, 12.2.1", f"{int(n)} lag screws")]
    not_checked = ["combined lateral and withdrawal loading (NDS 12.4.1)", "bearing of the washer or head on the side member, and the side member itself"]
    if steel is not None:
        rows.append(Row("Tension in the lag screws", worst["name"], worst["P"], n * steel, "lb", "NDS 12.2.1.4, 11.2.3", f"{steel:,.0f} lb per screw ({steel_source.strip()})"))
    else:
        not_checked.insert(0, "the tensile strength of the lag screw at the root diameter (NDS 12.2.1.4)")
    given = [(nm, v, k) for nm, v, k in (("Edge distance", edge, 1.5), ("End distance", end, 4.0), ("Spacing", spacing, 4.0)) if v is not None]
    for nm, v, k in given:
        rows.append(Row(nm, "", k * D, v, "in", "NDS Table 12.5.1E", f"{k:g} D minimum against the distance provided"))
    if len(given) < 3:
        not_checked.append("edge distance, end distance and spacing where not entered (NDS Table 12.5.1E)")
    info = [("Fastener", f"{int(n)} - {D:g} in. diameter x {length:g} in. long lag screws" + (f", {washer:g} in. washer" if washer else "")),
            ("Side Plate" if steel_side else "Side Member", f"{side_t:g} in. thick" + (", steel" if steel_side else "")),
            ("Main Member", f"{main_t:g} in. thick, G = {G_main:g} ({G_main_source.strip()})"),
            ("Conditions", service + (" service" if service == "dry" else "") + ("; screws in the end grain of the main member" if end_grain else ""))]
    load_lines = [f"{ld['case']}: {ld['P']:,.0f} lb" + (f"  ({ld['label']})" if ld.get("label") else "") for ld in loads]
    sheet = SimpleSheet(
        mark, "Lag Screws in Withdrawal", "Connection", "ASD", info, load_lines, [(f"{worst['name']}", worst["source"])], "Withdrawal Design Value", steps, rows,
        ["Standard hex lag screws (NDS Table L2) turned into " + ("the end grain" if end_grain else "the side grain") + " of the main member in lead holes bored to NDS 12.1.4.2; load along the screw.",
         "Thread length is the minimum of NDS Table L2.",
         "Sustained temperature not over 100 degrees F (Ct = 1.0, NDS Table 11.3.4).",
         "All lag screws share the load equally."],
        not_checked)
    if side_t > 0:
        sheet.blocks.append(dict(title="Section", picture=("lag", dict(D=D, L=length, side_t=side_t, main_t=main_t, T=th["T"], E=th["E"], pt=pt, washer=washer,
                                                                       steel_side=steel_side, label=f"{D:g} x {length:g} in. lag screw"))))
    sheet.connection = dict(W=W, pt=pt, T=th["T"], E=th["E"], capacity=worst["cap"], demand=worst["P"], CD=worst["CD"], CM=CM)
    return sheet


def screw_withdrawal_sheet(mark, number, length, n, side_t, G_side, G_side_source, main_t, G_main, G_main_source, service, loads, combos,
                           steel=None, steel_source="", steel_side=False):
    """Wood screws loaded in withdrawal from side grain, with head pull-through of a wood side
    member, 2018 NDS 12.2.2 and 12.2.5 (see dowel.py). loads: [dict(case, P lb)], P pulling the
    side member off; combos: ASD combinations. service: "dry" or "wet in service". steel:
    allowable tension of one screw, lb (optional, with its source). steel_side: the side
    member is a steel part (no pull-through check)."""
    from . import dowel, wood
    if number not in dowel.WOOD_SCREWS:
        raise WorksheetError(f"{mark}: the wood screw number is one of " + ", ".join(dowel.WOOD_SCREWS))
    if not (G_main_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the main member specific gravity is blank")
    if not steel_side and (G_side is None or not (G_side_source or "").strip()):
        raise WorksheetError(f"{mark}: the side member specific gravity and its source are needed for head pull-through")
    CMs = {"dry": 1.0, "wet in service": 0.7}
    if service not in CMs:
        raise WorksheetError(f"{mark}: the service condition is one of: " + "; ".join(CMs))
    if n is None or n < 1 or int(n) != n:
        raise WorksheetError(f"{mark}: the number of wood screws is a whole number, 1 or more")
    for nm, v in (("the screw length", length), ("the side member thickness", side_t), ("the main member thickness", main_t)):
        if v is None or v <= 0:
            raise WorksheetError(f"{mark}: {nm} must be positive")
    if steel is not None and not (steel_source or "").strip():
        raise WorksheetError(f"{mark}: the source of the screw's allowable tension is blank")
    D, Dr, DH = dowel.WOOD_SCREWS[number]
    in_main = length - side_t
    if in_main > main_t + 1e-9:
        raise WorksheetError(f"{mark}: the wood screw is longer than the side member and main member together")
    T = 2.0 * length / 3.0
    pt = min(T, in_main)
    if pt <= 0:
        raise WorksheetError(f"{mark}: the wood screw does not reach the main member")
    try:
        W = dowel.wood_screw_withdrawal(G_main, D)
        pth = None if steel_side else dowel.pull_through(DH, G_side, side_t)
    except dowel.DowelError as e:
        raise WorksheetError(f"{mark}: {e}")
    CM = CMs[service]
    Ln = footing_line
    steps = [Ln("D", f"{D:g} in", "", "NDS Table L3", f"{number} wood screw, {length:g} in. long"),
             Ln("W = 2850 G^2 D", W, "lb/in", "NDS Eq. 12.2-2", f"G = {G_main:g} ({G_main_source.strip()})"),
             Ln("thread length, T = 2/3 L", f"{T:.3f} in", "", "NDS Table L3 notes 2, 3"),
             Ln("thread penetration, pt", f"{pt:.3f} in", "", "NDS 12.2.2.2", f"the lesser of T and the length in the main member, {in_main:g} in."),
             Ln("W pt", W * pt, "lb", "NDS 12.2.2.2", "one wood screw"),
             Ln("CM", CM, "", "NDS Table 11.3.3", service + "; withdrawal" + ("" if steel_side else " and pull-through"))]
    if pth:
        steps += [Ln("DH", f"{DH:g} in", "", "NDS Table L3", "head diameter"),
                  Ln("WH = 690 pi DH G^2 tns" if pth["thin"] else "WH = 1725 pi DH^2 G^2", pth["WH"], "lb", f"NDS Eq. {pth['eq']}",
                     f"G = {G_side:g} ({G_side_source.strip()}); tns = {side_t:g} in. {'not over' if pth['thin'] else 'over'} 2.5 DH = {2.5 * DH:.2f} in.")]
    base_w = W * pt * CM
    base_h = pth["WH"] * CM if pth else None
    worst = None
    for cb in combos:
        P = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads)
        present = [ld["case"] for ld in loads if cb.factors.get(ld["case"], 0.0) and ld["P"]]
        if not present or P < 1e-9:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        cap = n * min(base_w, base_h if base_h is not None else base_w) * CD
        g = dict(name=cb.name, P=P, CD=CD, cd_case=cd_case, cd_dur=cd_dur, cap=cap, source=cb.source)
        if worst is None or g["P"] / cap > worst["P"] / worst["cap"]:
            worst = g
    if worst is None:
        raise WorksheetError(f"{mark}: no load combination pulls on the connection")
    CD = worst["CD"]
    steps += [Ln("CD", CD, "", "NDS Table 2.3.2", f"{worst['cd_case']}, {worst['cd_dur']}; combination {worst['name']}"),
              Ln("W' pt = W pt CD CM Ct", base_w * CD, "lb", "NDS Table 11.3.1", "Ct = 1.0; one wood screw")]
    rows = [Row("Withdrawal of the wood screws", worst["name"], worst["P"], n * base_w * CD, "lb", "NDS Table 11.3.1, 12.2.2", f"{int(n)} wood screws")]
    not_checked = ["wood screw spacing, edge and end distances against splitting (NDS 12.1.5.7)", "the members at the connection",
                   "combined lateral and withdrawal loading (NDS 12.4.1)"]
    if pth:
        steps.append(Ln("W'H = WH CD CM Ct", base_h * CD, "lb", "NDS Table 11.3.1", "Ct = 1.0; one wood screw"))
        rows.append(Row("Head pull-through of the side member", worst["name"], worst["P"], n * base_h * CD, "lb", "NDS Table 11.3.1, 12.2.5", f"{int(n)} wood screws"))
    else:
        not_checked.insert(1, "the steel side member at the screw heads")
    if steel is not None:
        rows.append(Row("Tension in the wood screws", worst["name"], worst["P"], n * steel, "lb", "NDS 12.2.2.5, 11.2.3", f"{steel:,.0f} lb per screw ({steel_source.strip()})"))
    else:
        not_checked.insert(0, "the tensile strength of the wood screw at the root diameter (NDS 12.2.2.5)")
    info = [("Fastener", f"{int(n)} - {number} wood screws, {D:g} in. diameter x {length:g} in. long" + ("" if steel_side else f", {DH:g} in. head")),
            ("Side Member", f"{side_t:g} in. thick, steel" if steel_side else f"{side_t:g} in. thick, G = {G_side:g} ({G_side_source.strip()})"),
            ("Main Member", f"{main_t:g} in. thick, G = {G_main:g} ({G_main_source.strip()})"),
            ("Conditions", service + (" service" if service == "dry" else ""))]
    load_lines = [f"{ld['case']}: {ld['P']:,.0f} lb" + (f"  ({ld['label']})" if ld.get("label") else "") for ld in loads]
    sheet = SimpleSheet(
        mark, "Wood Screws in Withdrawal", "Connection", "ASD", info, load_lines, [(f"{worst['name']}", worst["source"])], "Withdrawal Design Value", steps, rows,
        ["Standard wood screws (NDS Table L3) turned into lead holes bored to NDS 12.1.5.2, into the side grain of the main member, perpendicular to the wood fibers; load along the screw.",
         "Thread length two thirds of the screw length, at the point end.",
         "Sustained temperature not over 100 degrees F (Ct = 1.0, NDS Table 11.3.4).",
         "All wood screws share the load equally."],
        not_checked)
    sheet.blocks.append(dict(title="Section", picture=("nailed", dict(side_t=side_t, main_t=main_t, length=length, p=in_main, D=D,
                                                       label=f"{number} x {length:g} in. wood screw", withdrawal=True, screw=True))))
    sheet.connection = dict(W=W, pt=pt, T=T, WH=pth["WH"] if pth else None, capacity=worst["cap"], demand=worst["P"], CD=CD, CM=CM)
    return sheet


def bolted_connection_sheet(mark, D, rows_n, n_row, spacing, row_spacing, end, edge, shear, side_t, side_w, G_side, E_side, side_source,
                            main_t, main_w, G_main, E_main, main_source, sense, wood_type, service, loads, combos, local=None, grain="parallel", perp=None, lag=None, steel=None):
    """Bolted wood-to-wood connection loaded parallel to grain in every member (a splice or
    tension tie), 2018 NDS Ch. 11 and 12 (see dowel.py). shear: "single" or "double" (two
    side members of side_t each). rows_n rows of n_row bolts. loads: [dict(case, P lb)]."""
    from . import dowel, wood
    fs = "lag screw" if lag else "bolt"
    if steel:
        if steel not in dowel.STEEL_FE:
            raise WorksheetError(f"{mark}: the steel side plate is one of: " + "; ".join(dowel.STEEL_FE))
        if grain == "side":
            raise WorksheetError(f"{mark}: with steel side plates the load is parallel or perpendicular to the grain of the main member")
        G_side, E_side, side_source = None, 29000000.0, steel
    steel_perp = bool(steel) and grain == "main"           # no wood member is loaded parallel to grain
    if not steel_perp:
        for nm, v in (("the end distance", end), ("the edge distance", edge)):
            if v is None or v <= 0:
                raise WorksheetError(f"{mark}: {nm} of the member loaded parallel to grain is needed")
        if sense not in ("tension", "compression") or wood_type not in ("softwood", "hardwood"):
            raise WorksheetError(f"{mark}: the load sense (tension or compression) and the wood type (softwood or hardwood) are needed")
    for nm, v in (("the source of the side member values", side_source), ("the source of the main member values", main_source)):
        if not (v or "").strip():
            raise WorksheetError(f"{mark}: {nm} is blank")
    CMs = {"dry": 1.0, "wet in service": 0.7, "wet at fabrication, dry in service": 0.4}
    if service not in CMs:
        raise WorksheetError(f"{mark}: the service condition is one of: " + "; ".join(CMs))
    for nm, v in (("the number of rows", rows_n), ("the number of bolts in a row", n_row)):
        if v is None or v < 1 or int(v) != v:
            raise WorksheetError(f"{mark}: {nm} is a whole number, 1 or more")
    rows_n, n_row = int(rows_n), int(n_row)
    double = shear == "double"
    if lag and (double or local):
        raise WorksheetError(f"{mark}: lag screws are single shear; net section and tear-out are not checked for lag screws")
    if shear not in ("single", "double"):
        raise WorksheetError(f"{mark}: the connection is single or double shear")
    if rows_n > 1 and (row_spacing is None or row_spacing <= 0):
        raise WorksheetError(f"{mark}: the spacing between rows is needed for more than one row")
    if grain not in ("parallel", "side", "main"):
        raise WorksheetError(f"{mark}: the grain direction is parallel in every member, or perpendicular in the side or in the main member")
    # perp: dict(loaded_edge, unloaded_edge, end) of the member loaded perpendicular to grain
    need = 2 * (edge or 0) + (rows_n - 1) * (row_spacing or 0)
    for nm, wd_ in (("main", main_w), ("side", side_w)):
        if grain == nm or (steel and nm == "side"):
            continue
        if edge is not None and wd_ is not None and need > wd_ + 1e-6:
            raise WorksheetError(f"{mark}: the rows and edge distances need {need:g} in. and the {nm} member is {wd_:g} in. wide")
    try:
        if lag:
            th = dowel.lag_thread(D, lag["L"])
            wash = lag.get("washer") or 0.0
            p_lag = lag["L"] - wash - side_t - th["E"]
            if lag["L"] - wash - side_t > main_t + 1e-9:
                raise WorksheetError(f"{mark}: the lag screw is longer than the washer, side member and main member together")
            if p_lag <= 0:
                raise WorksheetError(f"{mark}: the lag screw does not reach the main member")
            r = dowel.lag(D, side_t, G_side, G_main, p_lag, 90.0 if grain == "side" else 0.0, 90.0 if grain == "main" else 0.0, Fes=dowel.STEEL_FE.get(steel))
        else:
            r = dowel.bolt(D, side_t, main_t, G_side, G_main, 90.0 if grain == "side" else 0.0, 90.0 if grain == "main" else 0.0, double=double, Fes=dowel.STEEL_FE.get(steel))
        if steel_perp:
            if n_row > 1 and (spacing is None or spacing < 3 * D - 1e-9):
                raise dowel.DowelError(f"dowel: the spacing in a row is less than the minimum 3 D = {3 * D:g} in. (NDS Table 12.5.1B)")
            cdel = ce = cs = 1.0
        else:
            cdel, ce, cs = dowel.geometry_parallel(D, end, spacing, n_row, sense, wood_type)
        As = side_t * side_w * (2 if double else 1)
        Am = main_t * main_w
        cp = None
        if grain != "parallel":
            for k_, lab in (("loaded_edge", "loaded edge distance"), ("unloaded_edge", "unloaded edge distance"), ("end", "end distance")):
                if not perp or perp.get(k_) is None or perp[k_] <= 0:
                    raise WorksheetError(f"{mark}: the {lab} of the member loaded perpendicular to grain is needed")
            wp_ = side_w if grain == "side" else main_w
            fit = perp["loaded_edge"] + perp["unloaded_edge"] + (n_row - 1) * (spacing or 0)
            if fit > wp_ + 1e-6:
                raise WorksheetError(f"{mark}: the bolts and edge distances need {fit:g} in. across the member loaded perpendicular to grain, which is {wp_:g} in. wide")
            cp = dowel.geometry_perp_member(D, perp["end"])
            cdel = min(cdel, cp)
            gw = (rows_n - 1) * row_spacing if rows_n > 1 else min(spacing or 4 * D, 4 * D)      # NDS 11.3.6.3
            if grain == "side":
                As = side_t * gw * (2 if double else 1)
            else:
                Am = main_t * gw
        Cg = dowel.group_action(D, n_row, spacing, E_side * As, E_main * Am, metal=bool(steel))
        e_min = dowel.edge_minimum(D, (p_lag if lag else main_t), (1e9 if steel else side_t * (2 if double else 1)), row_spacing if rows_n > 1 else None)
    except dowel.DowelError as e:
        raise WorksheetError(f"{mark}: {e}")
    CM = CMs[service]
    one_row_dry = service == "wet at fabrication, dry in service" and rows_n == 1 and grain == "parallel"
    if one_row_dry:
        CM = 1.0                                           # Table 11.3.3 note 2: one row parallel to grain
    n = rows_n * n_row
    base = r["Z"] * CM * Cg * cdel
    base_lat, comb = base, None
    alpha = (lag or {}).get("alpha") or 0.0
    if lag and alpha:
        if not 0 < alpha <= 90:
            raise WorksheetError(f"{mark}: the angle of the load to the wood surface is from 0 to 90 degrees")
        import math as _m
        try:
            Wl = dowel.lag_withdrawal(G_main, D)
        except dowel.DowelError as e:
            raise WorksheetError(f"{mark}: {e}")
        pt_l = min(th["T"], lag["L"] - wash - side_t) - th["E"]
        if pt_l <= 0:
            raise WorksheetError(f"{mark}: no thread reaches the main member beyond the tapered tip")
        CMw = 0.7 if service == "wet in service" else 1.0
        Wp = Wl * pt_l * CMw
        ca, sa = _m.cos(_m.radians(alpha)), _m.sin(_m.radians(alpha))
        base = Wp * base_lat / (Wp * ca ** 2 + base_lat * sa ** 2)
        comb = dict(W=Wl, pt=pt_l, CMw=CMw, Wp=Wp, alpha=alpha)
    Ln = footing_line
    names = {"Im": "Eq. 12.3-7" if double else "Eq. 12.3-1", "Is": "Eq. 12.3-8" if double else "Eq. 12.3-2", "II": "Eq. 12.3-3", "IIIm": "Eq. 12.3-4",
             "IIIs": "Eq. 12.3-9" if double else "Eq. 12.3-5", "IV": "Eq. 12.3-10" if double else "Eq. 12.3-6"}
    steps = [Ln("Fes", r["Fes"], "psi", "NDS Table 12K note 2" if lag else "NDS Table 12B note 2", f"{steel} steel side plate" + ("s" if double else "")) if steel else
             Ln("Fes", r["Fes"], "psi", "NDS Table 12.3.3", f"G = {G_side:g}, {'perpendicular' if grain == 'side' else 'parallel'} to grain ({side_source.strip()})"),
             Ln("Fem", r["Fem"], "psi", "NDS Table 12.3.3", f"G = {G_main:g}, {'perpendicular' if grain == 'main' else 'parallel'} to grain ({main_source.strip()})"),
             Ln("Fyb", r["Fyb"], "psi", "NDS Table 12J note 2" if lag else "NDS Table 12A note 2", f"{D:g} in. lag screw" if lag else "full body diameter bolt")]
    if lag:
        steps += [Ln("Dr", f"{r['Dr']:g} in", "", "NDS Table L2, 12.3.7.1(c)", "root diameter, used in the yield equations"),
                  Ln("penetration, p = L - washer - ts - E" if wash else "penetration, p = L - ts - E", f"{p_lag:.3f} in", "", "NDS 12.1.4.6, Table L2",
                     f"L = {lag['L']:g} in., tapered tip E = {th['E']:.3f} in." + (f", washer {wash:g} in." if wash else "") + f"; not less than 4 D = {4 * D:g} in."),
                  Ln("ls, lm", f"{side_t:g} in, {p_lag:.3f} in", "", "NDS 12.3.5.3", "lm = p")]
    else:
        steps += [Ln("ls, lm", f"{side_t:g} in, {main_t:g} in", "", "NDS 12.3.5")]
    for m in ("Im", "Is", "II", "IIIm", "IIIs", "IV"):
        if m in r["modes"]:
            steps.append(Ln(f"Z, mode {m}", r["modes"][m], "lb", "NDS " + names[m], f"Rd = {dowel.rd(r['Dr'] if lag else D, m, 0.0 if grain == 'parallel' else 90.0, D if lag else None):.3g}"))
    steps += [Ln("Z", r["Z"], "lb", "NDS 12.3.1", f"mode {r['mode']} governs; per {fs}"),
              Ln("CM", CM, "", "NDS Table 11.3.3", service + ("; one row parallel to grain (note 2)" if one_row_dry else "")),
              Ln("Cg", f"{Cg:.3f}", "", "NDS Eq. 11.3-1", f"{n_row} in a row at {spacing:g} in.; Es As = {E_side * As:,.0f} lb, Em Am = {E_main * Am:,.0f} lb" + ("; wood to metal" if steel else "") if n_row > 1 else f"one {fs} in a row"),
              *([Ln("C-delta, spacing in a row", f"{cs:.3f}", "", "NDS 12.5.1.2(c), Table 12.5.1B",
                    f"{spacing:g} in. provided, not less than 3 D = {3 * D:g} in.; the spacing for 1.0 is that required for the steel plate" if n_row > 1 else f"one {fs} in a row")]
                if steel_perp else
                [Ln("C-delta, end distance", f"{ce:.3f}", "", "NDS 12.5.1.2(a), Table 12.5.1A", f"{end:g} in. provided; {dowel.END[(sense, wood_type)][1] * D:g} in. for 1.0 ({sense}, {wood_type})"),
                 Ln("C-delta, spacing in a row", f"{cs:.3f}", "", "NDS 12.5.1.2(c), Table 12.5.1B", f"{spacing:g} in. provided; {4 * D:g} in. for 1.0" if n_row > 1 else f"one {fs} in a row")]),
              ]
    if cp is not None:
        steps.append(Ln("C-delta, end distance of the member loaded perpendicular to grain", f"{cp:.3f}", "", "NDS 12.5.1.2(a), Table 12.5.1A",
                        f"{perp['end']:g} in. provided; {4 * D:g} in. for 1.0"))
    steps += [Ln("C-delta", f"{cdel:.3f}", "", "NDS 12.5.1.2", "the smallest")]
    worst = None
    for cb in combos:
        P = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads)
        present = [ld["case"] for ld in loads if cb.factors.get(ld["case"], 0.0) and ld["P"]]
        if not present or abs(P) < 1e-9:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        g = dict(name=cb.name, P=abs(P), CD=CD, cd_case=cd_case, cd_dur=cd_dur, cap=n * base * CD, source=cb.source)
        if worst is None or g["P"] / g["cap"] > worst["P"] / worst["cap"]:
            worst = g
    if worst is None:
        raise WorksheetError(f"{mark}: no load combination puts load on the connection")
    steps += [Ln("CD", worst["CD"], "", "NDS Table 2.3.2", f"{worst['cd_case']}, {worst['cd_dur']}; combination {worst['name']}"),
              Ln("Z' = Z CD CM Ct Cg C-delta", base_lat * worst["CD"], "lb", "NDS Table 11.3.1", "Ct = 1.0")]
    if comb:
        steps += [Ln("W = 1800 G^1.5 D^0.75", comb["W"], "lb/in", "NDS Eq. 12.2-1", f"G = {G_main:g}"),
                  Ln("thread penetration, p", f"{comb['pt']:.3f} in", "", "NDS 12.2.1.2, Table L2", f"thread length T = {th['T']:g} in., less the tapered tip"),
                  Ln("W' p = W p CD CM Ct", comb["Wp"] * worst["CD"], "lb", "NDS Table 11.3.1", f"CM = {comb['CMw']:g} for withdrawal (Table 11.3.3); Ct = 1.0"),
                  Ln("Z'a = W'p Z' / (W'p cos^2 a + Z' sin^2 a)", base * worst["CD"], "lb", "NDS Eq. 12.4-1", f"a = {alpha:g} degrees between the wood surface and the load")]
    steps += [Ln(f"capacity = {n} Z'" + ("a" if comb else ""), worst["cap"], "lb", "")]
    rows = [Row(f"Load on the {fs}s", worst["name"], worst["P"], worst["cap"], "lb", "NDS Table 11.3.1, 12.3.1" + (", 12.4.1" if comb else ""),
                f"{n} {fs}s; mode {r['mode']}" + (f"; load at {alpha:g} degrees to the wood surface" if comb else "")),
            Row("Edge distance", "", e_min, edge, "in", "NDS Table 12.5.1C", "minimum against the distance provided")]
    if grain != "parallel":
        pname = "side member" + ("s" if double else "") if grain == "side" else "main member"
        rows[-1] = Row(f"Edge distance, {'main member' if grain == 'side' else 'side member' + ('s' if double else '')}", "", e_min, edge, "in", "NDS Table 12.5.1C", "member loaded parallel to grain")
        if steel_perp:
            rows.pop()
        rows.append(Row(f"Loaded edge distance, {pname}", "", 4 * D, perp["loaded_edge"], "in", "NDS Table 12.5.1C", "4 D minimum"))
        rows.append(Row(f"Unloaded edge distance, {pname}", "", 1.5 * D, perp["unloaded_edge"], "in", "NDS Table 12.5.1C", "1.5 D minimum"))
        if n_row > 1:
            rows.append(Row(f"Distance between outer {fs}s across the grain, {pname}", "", (n_row - 1) * spacing, 5.0, "in", "NDS 12.5.1.3",
                            "5 in. maximum without detailing for shrinkage"))
    if rows_n > 1:
        rs_min = 1.5 * D if grain == "parallel" else max(1.5 * D, dowel.row_spacing_min_perp(D, min(main_t, side_t * (2 if double else 1))))
        rows.append(Row("Spacing between rows", "", rs_min, row_spacing, "in", "NDS Table 12.5.1D", "minimum against the spacing provided"))
        rows.append(Row("Distance between outer rows", "", (rows_n - 1) * row_spacing, 5.0, "in", "NDS 12.5.1.3", "5 in. maximum without detailing for shrinkage"))
    not_checked = ["staggered rows (NDS 11.3.6.2)", f"load at an angle to the grain or to the {fs}", ("bearing of the washer or head on the side member, the tensile strength of the lag screw (NDS 12.2.1.4), steel side plates" if comb else
                    "withdrawal and combined lateral and withdrawal loading (NDS 12.2.1, 12.4.1), steel side plates") if lag else "the bolts in tension, the washers, steel side plates"]
    if lag:
        rows.insert(1, Row("Penetration into the main member", "", 4 * D, p_lag, "in", "NDS 12.1.4.6", "4 D minimum, tapered tip excluded"))
    if local and sense == "tension" and grain == "parallel":
        # local: dict(Ft_main, Fv_main, Ft_side, Fv_side, source, hole); design values with every factor except CD
        if not (local.get("source") or "").strip():
            raise WorksheetError(f"{mark}: the source of Ft and Fv for the members is blank")
        hole = local.get("hole") or (D + 1.0 / 16.0)
        CDw = worst["CD"]
        for nm, tt, ww, Ft, Fv in (("main member", main_t, main_w, local["Ft_main"], local["Fv_main"]),
                                    ("side member" + ("s" if double else ""), side_t * (2 if double else 1), side_w, local.get("Ft_side"), local.get("Fv_side")))[:1 if steel else 2]:
            ls_ = dowel.local_stresses(Ft * CDw, Fv * CDw, tt, ww, rows_n, n_row, spacing, end, row_spacing, hole)
            steps += [Ln(f"{nm}: ZNT' = Ft' t (w - nrow Dh)", ls_["ZNT"], "lb", "NDS Eq. E.2-1", f"Ft' = {Ft * CDw:,.0f} psi, t = {tt:g} in., Dh = {hole:g} in."),
                      Ln(f"{nm}: ZRT' = nrow ni Fv' t s_critical", ls_["ZRT"], "lb", "NDS Eq. E.3-2, E.3-3", f"Fv' = {Fv * CDw:,.0f} psi, s_critical = {ls_['s_critical']:g} in.")]
            if ls_["ZGT"] is not None:
                steps.append(Ln(f"{nm}: ZGT' = ZRT-1'/2 + ZRT-n'/2 + Ft' t (nrow - 1)(s_row - Dh)", ls_["ZGT"], "lb", "NDS Eq. E.4-1"))
            rows.append(Row(f"{nm.capitalize()}: {ls_['governs']}", worst["name"], worst["P"], ls_["capacity"], "lb", "NDS 11.1.2, Appendix E",
                            "the least of net section tension, row tear-out and group tear-out"))
        info_local = ("Members", f"Ft and Fv before CD: main {local['Ft_main']:,.0f} and {local['Fv_main']:,.0f} psi" + ("" if steel else f"; side {local['Ft_side']:,.0f} and {local['Fv_side']:,.0f} psi") + " "
                                 f"({local['source'].strip()}); bolt holes {hole:g} in.")
    else:
        info_local = None
        not_checked.insert(0, "the members at the connection: tension or compression on the net section (NDS 3.1.2), row and group tear-out (NDS Appendix E)")
    info = [("Lag Screws" if lag else "Bolts", f"{n} - {D:g} in. diameter" + (f" x {lag['L']:g} in. long" if lag else "") + f", {rows_n} row" + ("s" if rows_n > 1 else "") + f" of {n_row}, {shear} shear"),
            ("Side Plate" + ("s" if double else ""), f"{'2 - ' if double else ''}{side_t:g} x {side_w:g} in. {steel} steel, E = 29,000,000 psi") if steel else
            ("Side Member" + ("s" if double else ""), f"{'2 - ' if double else ''}{side_t:g} x {side_w:g} in., G = {G_side:g}, E = {E_side:,.0f} psi ({side_source.strip()})"),
            ("Main Member", f"{main_t:g} x {main_w:g} in., G = {G_main:g}, E = {E_main:,.0f} psi ({main_source.strip()})"),
            ("Layout", (f"spacing in a row {spacing:g} in." + ("" if steel_perp and rows_n == 1 else "; ") if n_row > 1 and spacing else "") + (f"between rows {row_spacing:g} in.; " if rows_n > 1 else "") + ("" if steel_perp else f"end distance {end:g} in.; edge distance {edge:g} in.")),
            ("Conditions", ("load parallel to grain in every member" if grain == "parallel" else
                            f"load perpendicular to grain in the {grain} member{'s' if (grain == 'side' and double) else ''}" + ("" if steel_perp else ", parallel in the other"))
                           + ("" if steel_perp else f", {sense}; {wood_type}") + f"; {service} service")]
    if grain != "parallel" and perp.get("Fv") is not None:
        if not (perp.get("Fv_source") or "").strip():
            raise WorksheetError(f"{mark}: the source of Fv for the member loaded perpendicular to grain is blank")
        bp_ = side_t * (2 if double else 1) if grain == "side" else main_t
        dp_ = side_w if grain == "side" else main_w
        de_ = dp_ - perp["unloaded_edge"]
        try:
            Vr, eq = dowel.shear_at_connection(perp["Fv"] * worst["CD"], bp_, dp_, de_, perp["end"])
        except dowel.DowelError as e:
            raise WorksheetError(f"{mark}: {e}")
        steps.append(Ln("Vr' = (2/3) Fv' b de" + (" (de/d)^2" if eq == "Eq. 3.4-6" else ""), Vr, "lb", "NDS 3.4.3.3, " + eq,
                        f"Fv' = {perp['Fv'] * worst['CD']:,.0f} psi, b = {bp_:g} in., d = {dp_:g} in., de = {de_:g} in.; connection {perp['end']:g} in. from the member end (5 d = {5 * dp_:g} in.)"))
        rows.append(Row("Shear at the connection, " + ("side member" + ("s" if double else "") if grain == "side" else "main member"), worst["name"], worst["P"], Vr, "lb",
                        "NDS 3.4.3.3, " + eq, "member loaded perpendicular to grain"))
        shear_done = True
    else:
        shear_done = False
    if grain != "parallel":
        info.append(("Perpendicular Member", f"loaded edge {perp['loaded_edge']:g} in.; unloaded edge {perp['unloaded_edge']:g} in.; end distance {perp['end']:g} in."))
        if shear_done:
            info.append(("Shear", f"Fv before CD = {perp['Fv']:,.0f} psi ({perp['Fv_source'].strip()})"))
        else:
            not_checked.insert(0, "shear in the member loaded perpendicular to grain at the connection (NDS 3.4.3.3)")
    load_lines = [f"{ld['case']}: {ld['P']:,.0f} lb" + (f"  ({ld['label']})" if ld.get("label") else "") for ld in loads]
    sheet = SimpleSheet(
        mark, "Lag Screw Connection" if lag else "Bolted Connection", "Connection", "ASD", info, load_lines, [(worst["name"], worst["source"])], "Lateral Design Value", steps, rows,
        [("Standard hex lag screws (NDS Table L2) turned into the side grain of the main member in lead holes bored to NDS 12.1.4.2, members in contact; "
          "the root diameter is used in the yield equations and the nominal diameter for the dowel bearing strengths." if lag else
          "Full body diameter bolts with Fyb = 45,000 psi, in holes 1/32 to 1/16 in. larger than the bolt, members in contact, washers under head and nut (NDS 12.1.3)."),
         ("The load acts parallel to the grain of every member" if grain == "parallel" else
          f"The load acts perpendicular to the grain of the {grain} member{'s' if (grain == 'side' and double) else ''}" + ("" if steel_perp else " and parallel to the grain of the other") + "; "
          f"a row of {fs}s is a line of {fs}s along the load. For the group action factor the area of the member loaded perpendicular to grain is its "
          f"thickness times the width of the {fs} group (NDS 11.3.6.3)") + f" and through the centroid of the {fs} group; all {fs}s share the load after the group action factor.",
         "Sustained temperature not over 100 degrees F (Ct = 1.0, NDS Table 11.3.4).",
         "E and the gross areas of the members are used for the group action factor as entered."]
        + (["The shear in the member loaded perpendicular to grain at the connection is taken as the whole load on the connection; Fv as entered "
            "(every adjustment factor except CD applied) times CD of the governing combination."] if shear_done else []),
        not_checked)
    if info_local:
        sheet.info.append(info_local)
        sheet.assumptions.append("Member capacities at the connection use Ft and Fv as entered (every adjustment factor except CD applied), times CD of the governing "
                                 "combination, on the gross thickness and the hole diameter stated.")
    if not steel_perp:
      sheet.blocks.append(dict(title="Layout" if grain == "parallel" else "Layout, Member Loaded Parallel to Grain",
                             picture=("bolted", dict(D=D, rows=rows_n, n=n_row, s=spacing, g=row_spacing or 0.0, end=end, edge=edge,
                                                     w=(side_w if grain == "main" else main_w), sense=sense))))
    if grain != "parallel":
        sheet.blocks.append(dict(title="Layout, Member Loaded Perpendicular to Grain",
                                 picture=("bolted_perp", dict(D=D, rows=rows_n, n=n_row, s=spacing, g=row_spacing or 0.0, w=(side_w if grain == "side" else main_w),
                                                              loaded_edge=perp["loaded_edge"], unloaded_edge=perp["unloaded_edge"], end=perp["end"]))))
    if steel:
        sheet.not_checked[:] = [x.replace(", steel side plates", "").replace(", the washers, steel side plates", ", the washers") for x in sheet.not_checked]
        sheet.not_checked.insert(0, "the steel side plate" + ("s" if double else "") + " and the fastener spacing and edge distances in the steel (AISC 360)")
        sheet.assumptions.append(f"Steel side plate{'s' if double else ''}: dowel bearing strength Fe = {dowel.STEEL_FE[steel]:,.0f} psi for {steel} steel; the group action factor uses "
                                 "the wood-to-metal load/slip modulus (NDS 11.3.6).")
    if comb:
        sheet.assumptions.append(f"The load acts at {alpha:g} degrees to the wood surface, in the plane of the lateral load direction stated; the lateral and withdrawal "
                                 "design values are combined by NDS Eq. 12.4-1. The force entered is the resultant.")
        sheet.info.append(("Load Angle", f"{alpha:g} degrees between the wood surface and the load"))
    if lag:
        sheet.blocks.append(dict(title="Section", picture=("lag", dict(D=D, L=lag["L"], side_t=side_t, main_t=main_t, T=th["T"], E=th["E"], pt=p_lag, washer=wash,
                                                                       steel_side=bool(steel), lateral=True, label=f"{D:g} x {lag['L']:g} in. lag screw"))))
        sheet.connection_lag = dict(th, p=p_lag, comb=comb)
    sheet.connection = dict(r, Zp=base * worst["CD"], n=n, Cg=Cg, Cdelta=cdel, CM=CM, capacity=worst["cap"], demand=worst["P"], edge_min=e_min)
    return sheet
