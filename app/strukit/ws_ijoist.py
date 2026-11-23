"""I-joist worksheet: a simply supported BCI or TJI joist, 2018 NDS Chapter 7, ASD. See
ijoist.py for the provisions and data used."""
from . import beam as bm, contbeam, ijoist as ij, wood
from .steel_beam import Line as L
from .ws_more import SimpleSheet
from .ws_steel_beam import Row, WorksheetError


def joist(mark, name, depth, span_ft, spacing_in, loads, combos, defl_checks, bearing_in, stiffeners, flange_supported,
          spans=None, overhang_left=0.0, overhang_right=0.0, bearing_int_in=None, stiffeners_int=False, snow_partial=True, rise_on_12=0.0):
    """name: "BCI 6000-1.8" or "TJI 210"; depth in.; loads: dict(case, kind "area"|"uniform"|
    "point", q psf / w plf / P lb, x1_ft, x2_ft or x_ft, label). Self-weight is added to D."""
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    try:
        lay = contbeam.layout(span_ft, spans, overhang_left, overhang_right)
    except (ValueError, TypeError) as e:
        raise WorksheetError(f"{mark}: {e}")
    span_ft = lay.total
    multi = len(lay.spans) > 1
    if not flange_supported:
        raise WorksheetError(f"{mark}: the compression flange must be supported throughout its length (NDS 7.3.5); "
                             "an I-joist with an unsupported compression flange is not covered")
    try:
        j = ij.joist(name, depth)
        Re, re_how = ij.end_reaction(j, bearing_in or 0.0, stiffeners)
        Ri, ri_how = ij.intermediate_reaction(j, bearing_int_in or 0.0, stiffeners_int) if multi else (None, "")
    except ij.IJoistError as e:
        raise WorksheetError(f"{mark}: {e}")
    rpt = j["source"].replace("ICC-ES ", "")
    Lin = span_ft * 12.0
    loads = [dict(x) for x in loads]
    for ld in loads:
        if ld.get("kind") == "area":
            if not spacing_in or spacing_in <= 0:
                raise WorksheetError(f"{mark}: an area load needs the joist spacing")
            ld.update(kind="uniform", w=ld["q"] * spacing_in / 12.0, area=ld["q"])
            if ld.get("q2") is not None:
                ld.update(w2=ld["q2"] * spacing_in / 12.0, area2=ld["q2"])
    loads.append(dict(case="D", kind="uniform", w=j["weight"], label="joist weight"))
    from .ws_wood import _slope, SLOPE_ASSUMPTION, SLOPE_NOT_CHECKED
    cos_s = _slope(rise_on_12, loads, mark)
    by_case = {}
    for ld in loads:
        if not ld.get("case") or not ld.get("kind"):
            raise WorksheetError(f"{mark}: a load is missing its case or its type")
        by_case.setdefault(ld["case"], []).append(ld)

    def run(factors):
        pts, dist = [], []
        for case, fac in factors.items():
            for ld in by_case.get(case, []):
                if ld["kind"] == "uniform":
                    x1, x2 = ld.get("x1_ft", 0.0) * 12, ld.get("x2_ft", span_ft) * 12
                    w = fac * ld["w"] / 12.0
                    dist.append(bm.DistLoad(x1, x2, w, w))
                else:
                    pts.append(bm.PointLoad(ld["x_ft"] * 12, fac * ld["P"]))
        if not pts and not dist:
            return None
        return bm.solve(Lin, [0.0, Lin], j["EI"], pts, dist)

    out = []
    for cb in combos:
        present = [c for c, v in cb.factors.items() if v and c in by_case]
        env = contbeam.envelope(lay, j["EI"], by_case, cb.factors, snow_partial)
        if env is None:
            continue
        res = env.res_neg if env.Mneg > env.Mpos else env.res_pos
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        M, V, R = max(env.Mpos, env.Mneg) / 12.0, env.V * cos_s, env.R_end
        out.append(dict(res=res, cb=cb, CD=CD, cd_case=cd_case, cd_dur=cd_dur, M=M, V=V, R=R, Rint=env.R_int, Rmin=env.R_min,
                        neg=env.Mneg > env.Mpos))
    gm = max(out, key=lambda o: o["M"] / o["CD"])
    gv = max(out, key=lambda o: o["V"] / o["CD"])
    gr = max(out, key=lambda o: o["R"] / o["CD"])
    cd = lambda o: f"CD = {o['CD']:g} ({o['cd_case']}, {o['cd_dur']})"
    rows = [Row("moment", gm["cb"].name, gm["M"], j["M"] * gm["CD"], "lb-ft", f"2018 NDS 7.3, Table 7.3.1; {rpt}",
                ("negative, over a support; " if gm["neg"] else "") + cd(gm)),
            Row("shear", gv["cb"].name, gv["V"], j["V"] * gv["CD"], "lb", f"2018 NDS 7.3, Table 7.3.1; {rpt}", cd(gv)),
            Row("end reaction", gr["cb"].name, gr["R"], Re * gr["CD"], "lb", f"2018 NDS 7.3, Table 7.3.1; {rpt}",
                f"{bearing_in:g} in. bearing, {'with' if stiffeners else 'without'} web stiffeners ({re_how}); {cd(gr)}")]
    if multi:
        gi = max(out, key=lambda o: o["Rint"] / o["CD"])
        rows.append(Row("intermediate reaction", gi["cb"].name, gi["Rint"], Ri * gi["CD"], "lb", f"2018 NDS 7.3, Table 7.3.1; {rpt}",
                        f"{bearing_int_in:g} in. bearing, {'with' if stiffeners_int else 'without'} web stiffeners ({ri_how}); {cd(gi)}"))
    for dc in defl_checks:
        wd = contbeam.deflection(lay, j["EI"], by_case, dc.factors, dc.ratio, snow_partial)
        if wd is None:
            continue
        bend = wd[0] / cos_s ** 2
        Md = max(float(wd[4].M.max()), 0.0) + max(-float(wd[4].M.min()), 0.0)
        shear = 8.0 * Md / j["K"]
        rows.append(Row(f"deflection, {dc.label}", " + ".join(f"{v:g}{k}" if v != 1 else k for k, v in dc.factors.items()),
                        bend + shear, wd[1] / cos_s, "in", dc.source + "; " + ("ESR-1336 Sect. 4.11" if j["product"] == "BCI" else "ESR-1153 Table 3 note 2"),
                        (f"limit span/{dc.ratio:g}" if lay.simple else f"{wd[2]}, limit {wd[3]}") + f"; bending {bend:.3f} in + shear {shear:.3f} in"))
    k_note = "K x 10^6 lb" if j["product"] == "BCI" else "K d x 10^5 lb"
    steps = [L("Mr", j["M"], "lb-ft", j["source"], "reference design moment"),
             L("Vr", j["V"], "lb", j["source"], "reference design shear"),
             L("Rr", Re, "lb", j["source"], f"end reaction, {re_how}, {'with' if stiffeners else 'without'} web stiffeners"),
             L("EI", j["EI"], "lb-in2", j["source"]), L("shear stiffness", j["K"], "lb", j["source"], k_note),
             L("CD", gm["CD"], "", "NDS Table 2.3.2", f"{gm['cd_case']}, {gm['cd_dur']}"),
             L("Mr' = Mr CD", j["M"] * gm["CD"], "lb-ft", "NDS Table 7.3.1", "no repetitive member increase"),
             L("M", gm["M"], "lb-ft", "statics", gm["cb"].name),
             L("Vr' = Vr CD", j["V"] * gv["CD"], "lb", "NDS Table 7.3.1", cd(gv)),
             L("V", gv["V"], "lb", "statics", gv["cb"].name),
             L("Rr' = Rr CD", Re * gr["CD"], "lb", "NDS Table 7.3.1", cd(gr)),
             L("R", gr["R"], "lb", "statics", gr["cb"].name)]
    info = [("Member", f"{j['product']} {j['series']} I-joist, {j['depth']:g} in deep" + (f", at {spacing_in:g} in on centre" if spacing_in else "")),
            ("Span", lay.describe()),
            ("Bearing", f"{bearing_in:g} in at each end, {'with' if stiffeners else 'without'} web stiffeners"
             + (f"; {bearing_int_in:g} in at intermediate supports, {'with' if stiffeners_int else 'without'} web stiffeners" if multi else "")),
            ("Bracing", "compression flange supported throughout its length"),
            ("Conditions", "dry use")]
    load_lines = []
    for ld in loads:
        if ld["kind"] == "uniform":
            where = f"{ld.get('x1_ft', 0):g} to {ld.get('x2_ft', span_ft):g} ft"
            if "area" in ld:
                load_lines.append((f"{ld['case']:<3} area    {ld['area']:>9.1f} psf x {spacing_in:g} in = {ld.get('w_slope', ld['w']):.1f} plf"
                                   + (f" along the slope = {ld['w']:.1f} plf of horizontal" if "w_slope" in ld else "") + f"   {where:<14} {ld.get('label', '')}")
                                  if "w2" not in ld else
                                  (f"{ld['case']:<3} area    {ld['area']:.1f} to {ld['area2']:.1f} psf x {spacing_in:g} in = {ld['w']:.1f} to {ld['w2']:.1f} plf   "
                                   f"{where:<14} {ld.get('label', '')}"))
            else:
                load_lines.append((f"{ld['case']:<3} uniform {ld['w']:>9.1f} plf   {where:<16} {ld.get('label', '')}" if "w_slope" not in ld else
                                   f"{ld['case']:<3} uniform {ld['w_slope']:.1f} plf along the slope = {ld['w']:.1f} plf of horizontal   {where:<14} {ld.get('label', '')}")
                                  if "w2" not in ld else
                                  f"{ld['case']:<3} tapered {ld['w']:.1f} to {ld['w2']:.1f} plf   {where:<16} {ld.get('label', '')}")
        else:
            load_lines.append(f"{ld['case']:<3} point   {ld['P']:>9.0f} lb    at {ld['x_ft']:g} ft{'':<8} {ld.get('label', '')}")
    sheet = SimpleSheet(
        mark, "I-Joist", "Member", "ASD", info, load_lines, [(c.name, c.source) for c in combos],
        f"Governing Calculation ({gm['cb'].name})", steps, rows,
        ["Allowable stress design, 2018 NDS Chapter 7, with reference design values from " + j["source"].split(" Table")[0] + ".",
         "Deflection is bending deflection plus shear deflection, taken as 8 M / (shear stiffness) with M the maximum moment in lb-in"
         + ("." if lay.simple else " (the largest positive plus the largest negative moment).") ,
         f"Joist weight {j['weight']:g} plf added to load case D."],
        ["web holes; concentrated loads on the flange and web stiffeners under them", "bearing on the supporting member",
         "hangers and connections", "blocking, rim and lateral restraint at supports", "floor vibration"],
        picture=("ijoist", dict(supports=lay.supports, d=j["depth"], span=span_ft, loads=[dict(case=x["case"], kind=x["kind"], w=x.get("w"), w2=x.get("w2"), P=x.get("P"), x_ft=x.get("x_ft"), **({"x1_ft": x["x1_ft"], "x2_ft": x.get("x2_ft", span_ft)} if "x1_ft" in x else {})) for x in loads])), governing=gm["cb"].name)
    from .ws_wood import _diagram_data
    sheet.diagram = _diagram_data(gm)
    if cos_s < 1.0:
        sheet.assumptions.insert(1, SLOPE_ASSUMPTION.format(r=rise_on_12, c=cos_s))
        sheet.not_checked[:0] = SLOPE_NOT_CHECKED
        sheet.info.insert(2, ("Slope", f"{rise_on_12:g} on 12; spans are horizontal; sloped length {lay.total / cos_s:.2f} ft"))
    if not lay.simple:
        sheet.assumptions.insert(1, "Live load (cases L and Lr) is placed on every combination of whole spans and overhangs, and each "
                                    "check uses the worst arrangement (ASCE/SEI 7-22 Sect. 4.3.3). The reference moment applies to "
                                    "positive and negative moment.")
        sheet.not_checked[:0] = ["lateral restraint of the bottom flange at supports"]
        sheet.assumptions.insert(2, "Snow load (case S) is applied balanced and in the partial loadings of ASCE/SEI 7-22 Sect. 7.5.1."
                                 if snow_partial else
                                 "Partial snow loading is not applied: the member spans perpendicular to the ridge of a gable roof "
                                 "sloped between 1/2 on 12 and 7 on 12 (ASCE/SEI 7-22 Sect. 7.5.1).")
        if min(o["Rmin"] for o in out) < 0:
            sheet.not_checked.insert(0, "uplift at a support (a reaction is upward in at least one load arrangement)")
    sheet.code = "2018 NDS, " + j["source"].split(" Table")[0]
    sheet.reactions = {o["cb"].name: o["R"] for o in out}
    return sheet
