"""Wood beam worksheet: a simply supported sawn lumber beam, 2018 NDS, ASD.
Loads in plf and lb, span in ft. See wood.py for the provisions used."""
import math

from . import beam as bm, wood
from .steel_beam import Line
from .ws_more import SimpleSheet
from .ws_steel_beam import Row, WorksheetError

footing_line = Line


def _diagram_data(o):
    """Shear (lb) and moment (lb-ft) along the span (ft) for one combination."""
    r = o["res"]
    return dict(combo=o["cb"].name, x=[v / 12.0 for v in r.x.tolist()], V=r.V.tolist(), M=[v / 12.0 for v in r.M.tolist()])


def beam(mark, species, grade, size, plies, span_ft, loads, combos, defl_checks, lu_ft, bearing_in, wet, incised,
         repetitive, unit_weight_pcf=None, self_weight_case="D", spacing_in=None):
    """species, grade: as listed in 2018 NDS Supplement Table 4A. size: nominal, "2x10".
    plies: number of pieces side by side, fastened to act together. lu_ft: unbraced length
    of the compression edge (0 when it is supported throughout). bearing_in: bearing
    length at each support. unit_weight_pcf: wood unit weight for self-weight, or None to
    leave self-weight out. loads: dict(case, kind "uniform"|"point"|"area", w plf, P lb or
    q psf, x1_ft, x2_ft or x_ft, label). An area load is carried over the member spacing
    spacing_in (joists and rafters). defl_checks: ws_steel_beam.DeflCheck."""
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    if plies not in (1, 2, 3, 4, 5, 6):
        raise WorksheetError(f"{mark}: the number of plies must be 1 to 6")
    if span_ft is None or span_ft <= 0 or bearing_in is None or bearing_in <= 0:
        raise WorksheetError(f"{mark}: span and bearing length must be positive")
    timber = size in wood.TIMBER_SIZES
    try:
        if timber:
            if plies != 1 or incised or repetitive:
                raise wood.WoodError("wood: a timber (5x5 and larger) is a single piece; the incising and repetitive member "
                                     "factors are for dimension lumber (NDS 4.3.8, 4.3.9)")
            ref, _, (b1, d), table, grade_note = wood.post_values(species, grade, size)
            CF = (12.0 / d) ** (1 / 9) if d > 12 else 1.0            # Table 4D adjustment factors; NDS 4.3.6.2
        else:
            ref, CF, grade_note = wood.values(species, grade, size)
            b1, d = wood.SIZES[size]
            table = "Table 4A"
    except wood.WoodError as e:
        raise WorksheetError(f"{mark}: {e}")
    b = b1 * plies
    A, S, I = b * d, b * d * d / 6, b * d ** 3 / 12
    Lin = span_ft * 12.0
    if timber:                                                       # Table 4D wet service factors
        f = wood.Factors(1.0, 1.0, 0.67 if wet else 1.0, 1.0, 1.0, 1.0, 1.0)
    else:
        f = wood.factors(ref["Fb"], CF, wet, incised, repetitive)
    E_adj, Emin_adj = ref["E"] * f.CM_E * f.Ci_E, ref["Emin"] * f.CM_E * f.Ci_E
    loads = [dict(x) for x in loads]
    for ld in loads:
        if ld.get("kind") == "area":
            if not spacing_in or spacing_in <= 0:
                raise WorksheetError(f"{mark}: an area load needs the member spacing")
            ld.update(kind="uniform", w=ld["q"] * spacing_in / 12.0, area=ld["q"])
    sw = None
    if unit_weight_pcf:
        sw = unit_weight_pcf * A / 144.0
        loads.append(dict(case=self_weight_case, kind="uniform", w=sw, label="self-weight"))
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    by_case = {}
    for ld in loads:
        for k in ("case", "kind"):
            if not ld.get(k):
                raise WorksheetError(f"{mark}: a load is missing its {k}")
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
        return bm.solve(Lin, [0.0, Lin], E_adj * I, pts, dist)

    out = []
    for cb in combos:
        present = [c for c, v in cb.factors.items() if v and c in by_case]
        res = run(cb.factors)
        if res is None:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        Fb_star = ref["Fb"] * CD * f.CM_b * CF * f.Ci_b * f.Cr
        try:
            CL, st = wood.beam_stability(Fb_star, Emin_adj, lu_ft * 12.0, b, d)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        Fb_adj = Fb_star * CL
        Fv_adj = ref["Fv"] * CD * f.CM_v * f.Ci_b
        M = max(abs(res.M_max()[0]), abs(res.M_min()[0]))
        V = abs(res.V_abs_max()[0])
        R = max(abs(v) for v in res.reactions.values())
        out.append(dict(res=res, cb=cb, CD=CD, cd_case=cd_case, cd_dur=cd_dur, CL=CL, st=st, Fb_star=Fb_star, Fb_adj=Fb_adj,
                        Fv_adj=Fv_adj, M=M, V=V, R=R, fb=M / S, fv=1.5 * V / A, reactions=dict(res.reactions)))
    if not out:
        raise WorksheetError(f"{mark}: no load combination loads this beam")
    Fperp_adj = ref["Fc_perp"] * f.CM_perp
    gb = max(out, key=lambda o: o["fb"] / o["Fb_adj"])
    gv = max(out, key=lambda o: o["fv"] / o["Fv_adj"])
    gr = max(out, key=lambda o: o["R"])
    fac_txt = lambda o: f"CD = {o['CD']:g} ({o['cd_case']}, {o['cd_dur']})"
    rows = [Row("bending", gb["cb"].name, gb["fb"], gb["Fb_adj"], "psi", "2018 NDS 3.3.1, Table 4.3.1",
                f"M = {gb['M'] / 12:,.0f} lb-ft; {fac_txt(gb)}; CL = {gb['CL']:.3f}"),
            Row("shear", gv["cb"].name, gv["fv"], gv["Fv_adj"], "psi", "2018 NDS 3.4.1, 3.4.2, Table 4.3.1",
                f"V = {gv['V']:,.0f} lb at the support; {fac_txt(gv)}"),
            Row("bearing at support", gr["cb"].name, gr["R"] / (b * bearing_in), Fperp_adj, "psi",
                "2018 NDS 3.10.2, Table 4.3.1",
                f"reaction {gr['R']:,.0f} lb on {b:g} in x {bearing_in:g} in; Cb = 1.0 at the end of a member")]
    for dc in defl_checks:
        res = run(dc.factors)
        if res is None:
            continue
        dl = max(abs(res.defl_max()[0]), abs(res.defl_min()[0]))
        rows.append(Row(f"deflection, {dc.label}", " + ".join(f"{v:g}{k}" if v != 1 else k for k, v in dc.factors.items()),
                        dl, Lin / dc.ratio, "in", dc.source, f"limit span/{dc.ratio:g}; E' = {E_adj:,.0f} psi"))
    L = footing_line
    st = gb["st"]
    steps = [L("b x d", b, "in", f"{SUPP_T1B}", f"{plies} x {b1:g} in wide, d = {d:g} in" if plies > 1 else f"d = {d:g} in"),
             L("A = b d", A, "in2", "geometry"), L("S = b d^2 / 6", S, "in3", "NDS Eq. 3.3-4"),
             L("I = b d^3 / 12", I, "in4", "NDS Eq. 3.3-3"),
             L("Fb", ref["Fb"], "psi", f"2018 NDS Supplement {table}"), L("CD", gb["CD"], "", "NDS Table 2.3.2", f"{gb['cd_case']}, {gb['cd_dur']}"),
             L("CM", f.CM_b, "", table[:8] + " adjustment factors", "wet service" if wet else "dry service"),
             L("CF", CF, "", table[:8] + " adjustment factors", "(12/d)^(1/9) for d over 12 in" if timber else f"{size}, {grade}"),
             L("Ci", f.Ci_b, "", "NDS Table 4.3.8", "incised" if incised else "not incised"),
             L("Cr", f.Cr, "", "NDS 4.3.9", "repetitive member" if repetitive else "not a repetitive member")]
    if "RB" in st:
        steps += [L("le", st["le"], "in", "NDS Table 3.3.3, note 1", f"lu = {lu_ft * 12:g} in"),
                  L("RB = sqrt(le d / b^2)", st["RB"], "", "NDS Eq. 3.3-5"),
                  L("Emin'", Emin_adj, "psi", "NDS Table 4.3.1"),
                  L("FbE = 1.20 Emin' / RB^2", st["FbE"], "psi", "NDS 3.3.3.8"),
                  L("Fb*", gb["Fb_star"], "psi", "NDS 3.3.3.8"),
                  L("CL", gb["CL"], "", "NDS Eq. 3.3-6")]
    else:
        steps.append(L("CL", 1.0, "", "NDS 3.3.3", st["why"]))
    steps += [L("Fb' = Fb CD CM CL CF Ci Cr", gb["Fb_adj"], "psi", "NDS Table 4.3.1"),
              L("fb = M / S", gb["fb"], "psi", "NDS Eq. 3.3-1", f"M = {gb['M'] / 12:,.0f} lb-ft, {gb['cb'].name}"),
              L("Fv' = Fv CD CM Ci", gv["Fv_adj"], "psi", "NDS Table 4.3.1", f"Fv = {ref['Fv']:g} psi; {fac_txt(gv)}"),
              L("fv = 3V / (2 b d)", gv["fv"], "psi", "NDS Eq. 3.4-2", f"V = {gv['V']:,.0f} lb, {gv['cb'].name}"),
              L("Fc_perp' = Fc_perp CM Ci Cb", Fperp_adj, "psi", "NDS Table 4.3.1", f"Fc_perp = {ref['Fc_perp']:g} psi"),
              L("E' = E CM Ci", E_adj, "psi", "NDS Table 4.3.1", f"E = {ref['E']:,.0f} psi")]
    sp = species.title().replace("Fir-Larch", "Fir-Larch")
    info = [("Member", f"({plies}) {size} {sp} {grade}" + (f" ({grade_note})" if grade_note else "") + (f"; {table}" if timber else "")),
            ("Size", f"{b:g} in x {d:g} in dressed" + (f" ({plies} plies of {b1:g} in)" if plies > 1 else "")),
            ("Span", f"{span_ft:g} ft, simply supported; bearing length {bearing_in:g} in at each support"
             + (f"; members at {spacing_in:g} in on centre" if spacing_in else "")),
            ("Bracing", "compression edge supported throughout its length" if lu_ft <= 0 else
             f"compression edge braced at {lu_ft:g} ft; ends held against rotation"),
            ("Conditions", ("wet service" if wet else "dry service") + "; " + ("incised" if incised else "not incised") + "; "
             + ("repetitive member" if repetitive else "not a repetitive member"))]
    load_lines = []
    for ld in loads:
        if ld["kind"] == "uniform":
            where = f"{ld.get('x1_ft', 0):g} to {ld.get('x2_ft', span_ft):g} ft"
            if "area" in ld:
                load_lines.append(f"{ld['case']:<3} area    {ld['area']:>9.1f} psf x {spacing_in:g} in = {ld['w']:.1f} plf   {where:<14} {ld.get('label', '')}")
            else:
                load_lines.append(f"{ld['case']:<3} uniform {ld['w']:>9.1f} plf   {where:<16} {ld.get('label', '')}")
        else:
            load_lines.append(f"{ld['case']:<3} point   {ld['P']:>9.0f} lb    at {ld['x_ft']:g} ft{'':<8} {ld.get('label', '')}")
    assumptions = ["Allowable stress design, 2018 NDS. Temperature factor Ct = 1.0 (NDS 2.3.3, sustained temperature to 100 F).",
                   "Shear is taken at the face of the support with no reduction for loads near the support (NDS 3.4.3.1)."]
    if plies > 1:
        assumptions.append("The plies are fastened together to act as one member of the combined width.")
    if sw is not None:
        assumptions.append(f"Self-weight {sw:.1f} plf (unit weight {unit_weight_pcf:g} pcf) added to load case {self_weight_case}.")
    else:
        assumptions.append("Self-weight is not added separately.")
    sheet = SimpleSheet(
        mark, "Wood Beam", "Member", "ASD", info, load_lines, [(c.name, c.source) for c in combos],
        f"Governing Calculation ({gb['cb'].name})", steps, rows, assumptions,
        ["notches (NDS 3.2.3, 3.4.3.2)", "fastening of the plies to each other" if plies > 1 else None,
         "lateral support at the ends against rotation (NDS 3.3.3.4)", "connections and hangers"],
        picture=("wood_beam", dict(b=b, d=d, plies=plies, span=span_ft, size=size, loads=[dict(case=x["case"], kind=x["kind"], w=x.get("w"), P=x.get("P"), x_ft=x.get("x_ft"), **({"x1_ft": x["x1_ft"], "x2_ft": x["x2_ft"]} if "x1_ft" in x else {})) for x in loads])), governing=gb["cb"].name)
    sheet.not_checked = [x for x in sheet.not_checked if x]
    sheet.reactions = {o["cb"].name: o["reactions"] for o in out}
    sheet.diagram = _diagram_data(gb)
    return sheet


def post(mark, species, grade, size, height_ft, loads, combos, Ke1, Ke2, k_source, wet, incised, lu1_ft=None, lu2_ft=None,
         unit_weight_pcf=None, self_weight_case="D", lateral=()):
    """Solid sawn post, 2018 NDS 3.6, 3.7 and 3.9.2, ASD: axial compression, with or
    without lateral load bending it about its strong axis (load on the narrow face).
    size: nominal, dimension lumber or a timber. Ke1, lu1: buckling in the plane of the
    larger dimension d1; Ke2, lu2: in the plane of the smaller dimension d2 (unbraced
    lengths default to the height). loads: dict(case, P lb, label). lateral: dict(case,
    kind "uniform"|"point", w plf or P lb, x_ft, label), on the post spanning simply
    between its base and its top."""
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    if height_ft is None or height_ft <= 0:
        raise WorksheetError(f"{mark}: the height must be positive")
    if not (k_source or "").strip():
        raise WorksheetError(f"{mark}: say where the effective length factors come from")
    try:
        ref, CF, (bb, dd), table, note = wood.post_values(species, grade, size)
    except wood.WoodError as e:
        raise WorksheetError(f"{mark}: {e}")
    d1, d2 = max(bb, dd), min(bb, dd)
    A = bb * dd
    timber = table.startswith("Table 4D")
    if timber:
        if incised:
            raise WorksheetError(f"{mark}: the incising factor of NDS 4.3.8 is for dimension lumber, not timbers")
        CM_c, CM_E, Ci_c, Ci_E = (0.91 if wet else 1.0), 1.0, 1.0, 1.0
    else:
        CM_c = (1.0 if ref["Fc"] * CF <= 750 else 0.8) if wet else 1.0
        CM_E, Ci_c, Ci_E = (0.9 if wet else 1.0), (0.80 if incised else 1.0), (0.95 if incised else 1.0)
    Emin_adj = ref["Emin"] * CM_E * Ci_E
    lu1 = (lu1_ft if lu1_ft else height_ft) * 12.0
    lu2 = (lu2_ft if lu2_ft else height_ft) * 12.0
    loads = [dict(x) for x in loads]
    sw = None
    if unit_weight_pcf:
        sw = unit_weight_pcf * A / 144.0 * height_ft
        loads.append(dict(case=self_weight_case, P=sw, label="self-weight"))
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    by_case = {}
    for ld in loads:
        if not ld.get("case") or ld.get("P") is None:
            raise WorksheetError(f"{mark}: a load is missing its case or its value")
        by_case[ld["case"]] = by_case.get(ld["case"], 0.0) + ld["P"]
    lat_by = {}
    for ld in lateral:
        if not ld.get("case") or ld.get("kind") not in ("uniform", "point"):
            raise WorksheetError(f"{mark}: a lateral load is missing its case or its type")
        lat_by.setdefault(ld["case"], []).append(ld)
    Hin = height_ft * 12.0
    S1 = d2 * d1 ** 2 / 6
    if lat_by:
        t_nom, w_nom = wood.nominal(size)
        if timber:
            CF_b = (12.0 / d1) ** (1 / 9) if d1 > 12 else 1.0          # Table 4D adjustment factors
            CM_b = 1.0
            Fb_ref = ref["Fb"]
        else:
            Fb_ref, CF_b = wood.values(species, grade, size)[0]["Fb"], wood.values(species, grade, size)[1]
            CM_b = (1.0 if Fb_ref * CF_b <= 1150 else 0.85) if wet else 1.0
        CM_v = 1.0 if timber else (0.97 if wet else 1.0)
    out = []
    for cb in combos:
        present = [c for c, v in cb.factors.items() if v and (c in by_case or c in lat_by)]
        if not present:
            continue
        P = sum(cb.factors[c] * by_case[c] for c in present if c in by_case)
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
            Fc_star = ref["Fc"] * CD * CM_c * CF * Ci_c
            CP, st = wood.column_stability(Fc_star, Emin_adj, Ke1 * lu1, d1, Ke2 * lu2, d2)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        o = dict(cb=cb, P=P, CD=CD, cd_case=cd_case, cd_dur=cd_dur, Fc_star=Fc_star, CP=CP, st=st, Fc_adj=Fc_star * CP,
                 fc=P / A, M=0.0, V=0.0, ratio=(P / A) / (Fc_star * CP))
        pts, dist = [], []
        for c in present:
            for ld in lat_by.get(c, []):
                if ld["kind"] == "uniform":
                    w = cb.factors[c] * ld["w"] / 12.0
                    dist.append(bm.DistLoad(0.0, Hin, w, w))
                else:
                    pts.append(bm.PointLoad(ld["x_ft"] * 12.0, cb.factors[c] * ld["P"]))
        if pts or dist:
            res = bm.solve(Hin, [0.0, Hin], ref["E"] * d2 * d1 ** 3 / 12, pts, dist)
            o["M"] = max(abs(res.M_max()[0]), abs(res.M_min()[0]))
            o["V"] = abs(res.V_abs_max()[0])
            fb = o["M"] / S1
            Fb_star = Fb_ref * CD * CM_b * CF_b * Ci_c
            try:
                CL, bst = wood.beam_stability(Fb_star, Emin_adj, lu2, d2, d1)
            except wood.WoodError as e:
                raise WorksheetError(f"{mark}: {e}")
            FcE1 = 0.822 * Emin_adj / (Ke1 * lu1 / d1) ** 2
            FcE2 = 0.822 * Emin_adj / (Ke2 * lu2 / d2) ** 2
            if o["fc"] >= FcE1:
                raise WorksheetError(f"{mark}: {cb.name}: the axial stress reaches the buckling stress FcE1; the post is too slender")
            FbE = bst.get("FbE")
            i3 = (o["fc"] / o["Fc_adj"]) ** 2 + fb / (Fb_star * CL * (1 - o["fc"] / FcE1))          # Eq. 3.9-3
            i4 = (o["fc"] / FcE2 + (fb / FbE) ** 2) if FbE else 0.0                                  # Eq. 3.9-4
            o.update(fb=fb, Fb_star=Fb_star, CL=CL, Fb_adj=Fb_star * CL, FcE1=FcE1, FcE2=FcE2, FbE=FbE, i3=i3, i4=i4,
                     fv=1.5 * o["V"] / A, Fv_adj=ref["Fv"] * CD * CM_v * Ci_c, ratio=max(i3, i4, o["ratio"]))
        out.append(o)
    if not out:
        raise WorksheetError(f"{mark}: no load combination loads this post")
    axial = [o for o in out if o["P"] > 0]
    rows = []
    g = max(axial, key=lambda o: o["fc"] / o["Fc_adj"]) if axial else max(out, key=lambda o: o["ratio"])
    if axial:
        rows.append(Row("compression", g["cb"].name, g["fc"], g["Fc_adj"], "psi", "2018 NDS 3.6.3, 3.7.1, Table 4.3.1",
                        f"P = {g['P']:,.0f} lb; CD = {g['CD']:g} ({g['cd_case']}, {g['cd_dur']}); CP = {g['CP']:.3f}; "
                        f"le/d = {g['st']['ratio']:.2f}"))
    bent = [o for o in out if o["M"] > 0]
    gb = None
    if bent:
        gb = max(bent, key=lambda o: o["i3"])
        rows.append(Row("compression with bending", gb["cb"].name, gb["i3"], 1.0, "", "2018 NDS Eq. 3.9-3",
                        f"fc = {gb['fc']:.1f} psi, fb = {gb['fb']:.1f} psi; M = {gb['M'] / 12:,.0f} lb-ft; "
                        f"CD = {gb['CD']:g} ({gb['cd_case']}, {gb['cd_dur']}); CL = {gb['CL']:.3f}"))
        g4 = max(bent, key=lambda o: o["i4"])
        if g4["i4"] > 0:
            rows.append(Row("stability under bending", g4["cb"].name, g4["i4"], 1.0, "", "2018 NDS Eq. 3.9-4",
                            f"fc / FcE2 + (fb / FbE)^2; FcE2 = {g4['FcE2']:,.0f} psi, FbE = {g4['FbE']:,.0f} psi"))
        gv = max(bent, key=lambda o: o["fv"] / o["Fv_adj"])
        rows.append(Row("shear", gv["cb"].name, gv["fv"], gv["Fv_adj"], "psi", "2018 NDS 3.4.1, 3.4.2, Table 4.3.1",
                        f"V = {gv['V']:,.0f} lb; CD = {gv['CD']:g} ({gv['cd_case']}, {gv['cd_dur']})"))
    L = footing_line
    src_t = f"2018 NDS Supplement {table}"
    steps = [L("b x d", bb, "in", SUPP_T1B, f"{bb:g} in x {dd:g} in dressed"), L("A", A, "in2", "geometry"),
             L("Fc", ref["Fc"], "psi", src_t), L("Emin", ref["Emin"], "psi", src_t),
             L("CD", g["CD"], "", "NDS Table 2.3.2", f"{g['cd_case']}, {g['cd_dur']}"),
             L("CM", CM_c, "", ("Table 4D" if timber else "Table 4A") + " adjustment factors", "wet service" if wet else "dry service"),
             L("CF", CF, "", ("Table 4D" if timber else "Table 4A") + " adjustment factors"),
             L("Ci", Ci_c, "", "NDS Table 4.3.8", "incised" if incised else "not incised"),
             L("Fc* = Fc CD CM CF Ci", g["Fc_star"], "psi", "NDS 3.7.1.5"),
             L("le1 / d1", Ke1 * lu1 / d1, "", "NDS 3.7.1.3", f"Ke = {Ke1:g}, l = {lu1:g} in, d1 = {d1:g} in"),
             L("le2 / d2", Ke2 * lu2 / d2, "", "NDS 3.7.1.3", f"Ke = {Ke2:g}, l = {lu2:g} in, d2 = {d2:g} in"),
             L("Emin'", Emin_adj, "psi", "NDS Table 4.3.1"),
             L("FcE = 0.822 Emin' / (le/d)^2", g["st"]["FcE"], "psi", "NDS 3.7.1.5", f"le/d = {g['st']['ratio']:.2f}"),
             L("CP", g["CP"], "", "NDS Eq. 3.7-1", "c = 0.8 for sawn lumber"),
             L("Fc' = Fc* CP", g["Fc_adj"], "psi", "NDS Table 4.3.1"),
             L("fc = P / A", g["fc"], "psi", "NDS 3.6.3", f"P = {g['P']:,.0f} lb, {g['cb'].name}")]
    if gb:
        tb = "Table 4D" if timber else "Table 4A"
        steps += [L("S1 = d2 d1^2 / 6", S1, "in3", "NDS Eq. 3.3-4", f"bending about the strong axis, {gb['cb'].name}"),
                  L("Fb", Fb_ref, "psi", f"2018 NDS Supplement {tb}"), L("CF for Fb", CF_b, "", tb + " adjustment factors"),
                  L("Fb1' = Fb CD CM CL CF Ci", gb["Fb_adj"], "psi", "NDS Table 4.3.1",
                    f"CD = {gb['CD']:g}, CM = {CM_b:g}, CL = {gb['CL']:.3f}"),
                  L("fb1 = M / S1", gb["fb"], "psi", "NDS Eq. 3.3-1", f"M = {gb['M'] / 12:,.0f} lb-ft"),
                  L("fc", gb["fc"], "psi", "NDS 3.6.3", f"P = {gb['P']:,.0f} lb"),
                  L("Fc'", gb["Fc_adj"], "psi", "NDS Table 4.3.1", f"CD = {gb['CD']:g}, CP = {gb['CP']:.3f}"),
                  L("FcE1 = 0.822 Emin' / (le1/d1)^2", gb["FcE1"], "psi", "NDS 3.9.2"),
                  L("(fc/Fc')^2 + fb1 / [Fb1' (1 - fc/FcE1)]", gb["i3"], "", "NDS Eq. 3.9-3", "not more than 1.0")]
    info = [("Member", f"{size} {species.title()} {grade}" + (f" ({note})" if note else "") + f"; {table}"),
            ("Size", f"{bb:g} in x {dd:g} in dressed"),
            ("Height", f"{height_ft:g} ft; unbraced {lu1 / 12:g} ft for the {d1:g} in dimension and {lu2 / 12:g} ft for the {d2:g} in dimension"),
            ("Ends", f"Ke = {Ke1:g} and {Ke2:g} ({k_source.strip()})"),
            ("Conditions", ("wet service" if wet else "dry service") + "; " + ("incised" if incised else "not incised"))]
    load_lines = [f"{ld['case']:<3} axial {ld['P']:>10,.0f} lb   {ld.get('label', '')}" for ld in loads]
    for ld in lateral:
        load_lines.append(f"{ld['case']:<3} lateral uniform {ld['w']:>7.1f} plf   {ld.get('label', '')}" if ld["kind"] == "uniform" else
                          f"{ld['case']:<3} lateral point {ld['P']:>9,.0f} lb at {ld['x_ft']:g} ft   {ld.get('label', '')}")
    assumptions = ["Allowable stress design, 2018 NDS. Temperature factor Ct = 1.0 (NDS 2.3.3, sustained temperature to 100 F).",
                   "The axial load acts along the centre of the post." + (" Lateral load bends the post about its strong axis; "
                   "the post spans simply between its base and its top." if lateral else " No bending is considered."),
                   f"Self-weight {sw:,.0f} lb (unit weight {unit_weight_pcf:g} pcf) added to load case {self_weight_case}." if sw is not None
                   else "Self-weight is not added separately."]
    sheet = SimpleSheet(
        mark, "Wood Post", "Member", "ASD", info, load_lines, [(c.name, c.source) for c in combos],
        f"Governing Calculation ({g['cb'].name})", steps, rows, assumptions,
        (["bending from eccentric load (NDS 15.4)", "bending about the weak axis"] if lateral else
         ["bending from eccentric or lateral load (NDS 3.9)"])
        + ["bearing on the end grain and on the supporting member (NDS 3.10)", "connections at the top and base"],
        picture=("wood_post", dict(b=bb, d=dd, height=height_ft, size=size, axial=[f"{x['case']} {x['P']:,.0f} lb" for x in loads], lateral=[dict(x) for x in lateral])), governing=g["cb"].name)
    sheet.base = {o["cb"].name: o["P"] for o in out}
    sheet.governing = max(out, key=lambda o: o["ratio"])["cb"].name
    return sheet


SUPP_T1B = "2018 NDS Supplement Table 1B"
SUPP_T4A = "2018 NDS Supplement Table 4A"


def lvl_beam(mark, grade, thickness, depth, plies, span_ft, loads, combos, defl_checks, lu_ft, bearing_in, repetitive,
             unit_weight_pcf=None, self_weight_case="D", spacing_in=None, product="Versa-Lam LVL"):
    """Structural composite lumber beam (Versa-Lam LVL, Microllam LVL, Parallam PSL or
    TimberStrand LSL), joist orientation, simply supported; evaluation report values and
    the 2018 NDS Chapter 8, ASD, dry use. thickness: of one ply, in.; depth, in. Loads as
    for beam(). See scl.py for the provisions used."""
    from . import scl
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    if plies not in (1, 2, 3, 4):
        raise WorksheetError(f"{mark}: the number of plies must be 1 to 4")
    if span_ft is None or span_ft <= 0 or bearing_in is None or bearing_in <= 0:
        raise WorksheetError(f"{mark}: span and bearing length must be positive")
    if thickness is None or thickness < 1.25:
        raise WorksheetError(f"{mark}: ply thickness must be 1.25 in. or more")
    try:
        ref = scl.beam_spec(product, grade, thickness, plies, depth)
        CV = ref["CV"]
    except scl.SclError as e:
        raise WorksheetError(f"{mark}: {e}")
    b, d = thickness * plies, depth
    A, S, I = b * d, b * d * d / 6, b * d ** 3 / 12
    Lin = span_ft * 12.0
    Emin = ref["Emin"]
    rpt = ref["report"].replace("ICC-ES ", "")
    Cr = 1.04 if repetitive else 1.0
    loads = [dict(x) for x in loads]
    for ld in loads:
        if ld.get("kind") == "area":
            if not spacing_in or spacing_in <= 0:
                raise WorksheetError(f"{mark}: an area load needs the member spacing")
            ld.update(kind="uniform", w=ld["q"] * spacing_in / 12.0, area=ld["q"])
    sw = None
    if unit_weight_pcf:
        sw = unit_weight_pcf * A / 144.0
        loads.append(dict(case=self_weight_case, kind="uniform", w=sw, label="self-weight"))
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    by_case = {}
    for ld in loads:
        for k in ("case", "kind"):
            if not ld.get(k):
                raise WorksheetError(f"{mark}: a load is missing its {k}")
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
        return bm.solve(Lin, [0.0, Lin], ref["E"] * I, pts, dist)

    out = []
    for cb in combos:
        present = [c for c, v in cb.factors.items() if v and c in by_case]
        res = run(cb.factors)
        if res is None:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
            Fb_star = ref["Fb"] * CD * Cr * (CV if CV > 1 else 1.0)          # NDS 3.3.3.8, 8.3.6.1
            CL, st = wood.beam_stability(Fb_star, Emin, lu_ft * 12.0, b, d)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        vol = CV if CV > 1 else min(CV, CL)                                  # the lesser of CV and CL when CV <= 1
        Fb_adj = ref["Fb"] * CD * Cr * (CV * CL if CV > 1 else vol)
        M = max(abs(res.M_max()[0]), abs(res.M_min()[0]))
        V = abs(res.V_abs_max()[0])
        R = max(abs(v) for v in res.reactions.values())
        out.append(dict(res=res, cb=cb, CD=CD, cd_case=cd_case, cd_dur=cd_dur, CL=CL, st=st, Fb_star=Fb_star, Fb_adj=Fb_adj,
                        Fv_adj=ref["Fv"] * CD, M=M, V=V, R=R, fb=M / S, fv=1.5 * V / A, reactions=dict(res.reactions)))
    if not out:
        raise WorksheetError(f"{mark}: no load combination loads this beam")
    gb = max(out, key=lambda o: o["fb"] / o["Fb_adj"])
    gv = max(out, key=lambda o: o["fv"] / o["Fv_adj"])
    gr = max(out, key=lambda o: o["R"])
    fac_txt = lambda o: f"CD = {o['CD']:g} ({o['cd_case']}, {o['cd_dur']})"
    rows = [Row("bending", gb["cb"].name, gb["fb"], gb["Fb_adj"], "psi", f"2018 NDS 3.3.1, Table 8.3.1; {rpt} Table 1",
                f"M = {gb['M'] / 12:,.0f} lb-ft; {fac_txt(gb)}; CV = {CV:.3f}; CL = {gb['CL']:.3f}"),
            Row("shear", gv["cb"].name, gv["fv"], gv["Fv_adj"], "psi", f"2018 NDS 3.4.1, 3.4.2, Table 8.3.1; {rpt} Table 1",
                f"V = {gv['V']:,.0f} lb at the support; {fac_txt(gv)}"),
            Row("bearing at support", gr["cb"].name, gr["R"] / (b * bearing_in), ref["Fc_perp"], "psi",
                f"2018 NDS 3.10.2, Table 8.3.1; {rpt} Table 1",
                f"reaction {gr['R']:,.0f} lb on {b:g} in x {bearing_in:g} in; Cb = 1.0 at the end of a member")]
    for dc in defl_checks:
        res = run(dc.factors)
        if res is None:
            continue
        bend = max(abs(res.defl_max()[0]), abs(res.defl_min()[0]))
        Md = max(abs(res.M_max()[0]), abs(res.M_min()[0]))
        shear = scl.shear_deflection(Md, ref["E"], b, d)
        rows.append(Row(f"deflection, {dc.label}", " + ".join(f"{v:g}{k}" if v != 1 else k for k, v in dc.factors.items()),
                        bend + shear, Lin / dc.ratio, "in", dc.source + "; " + ref["defl_src"],
                        f"limit span/{dc.ratio:g}; bending {bend:.3f} in + shear {shear:.3f} in; E = {ref['E']:,.0f} psi"))
    L = footing_line
    st = gb["st"]
    steps = [L("b x d", b, "in", "member size", f"{plies} x {thickness:g} in wide, d = {d:g} in" if plies > 1 else f"d = {d:g} in"),
             L("A = b d", A, "in2", "geometry"), L("S = b d^2 / 6", S, "in3", "NDS Eq. 3.3-4"),
             L("I = b d^3 / 12", I, "in4", "NDS Eq. 3.3-3"),
             L("Fb", ref["Fb"], "psi", ref["source"], ref["fb_note"]),
             L("CD", gb["CD"], "", "NDS Table 2.3.2", f"{gb['cd_case']}, {gb['cd_dur']}"),
             L(ref["cv_label"], CV, "", ref["cv_src"], ref["cv_note"]),
             L("Cr", Cr, "", "NDS 8.3.7", "repetitive member" if repetitive else "not a repetitive member")]
    if "RB" in st:
        steps += [L("le", st["le"], "in", "NDS Table 3.3.3, note 1", f"lu = {lu_ft * 12:g} in"),
                  L("RB = sqrt(le d / b^2)", st["RB"], "", "NDS Eq. 3.3-5"),
                  L(ref["emin_label"], Emin, "psi", ref["emin_src"], ref["emin_note"]),
                  L("FbE = 1.20 Emin' / RB^2", st["FbE"], "psi", "NDS 3.3.3.8"),
                  L("Fb*", gb["Fb_star"], "psi", "NDS 3.3.3.8"),
                  L("CL", gb["CL"], "", "NDS Eq. 3.3-6")]
    else:
        steps.append(L("CL", 1.0, "", "NDS 3.3.3", st["why"]))
    steps += [L("Fb' = Fb CD Cr x (lesser of CV and CL)" if CV <= 1 else "Fb' = Fb CD CV CL Cr", gb["Fb_adj"], "psi",
                "NDS Table 8.3.1, 8.3.6.1"),
              L("fb = M / S", gb["fb"], "psi", "NDS Eq. 3.3-1", f"M = {gb['M'] / 12:,.0f} lb-ft, {gb['cb'].name}"),
              L("Fv' = Fv CD", gv["Fv_adj"], "psi", "NDS Table 8.3.1", f"Fv = {ref['Fv']:g} psi ({ref['source']}); {fac_txt(gv)}"),
              L("fv = 3V / (2 b d)", gv["fv"], "psi", "NDS Eq. 3.4-2", f"V = {gv['V']:,.0f} lb, {gv['cb'].name}"),
              L("Fc_perp' = Fc_perp Cb", ref["Fc_perp"], "psi", "NDS Table 8.3.1", f"{ref['source']}, joist orientation"),
              L("E", ref["E"], "psi", ref["source"], "shear deflection added separately")]
    info = [("Member", f"({plies}) {thickness:g} in x {d:g} in {ref['name']} {grade}"),
            ("Size", f"{b:g} in x {d:g} in" + (f" ({plies} plies of {thickness:g} in)" if plies > 1 else "") + "; load on the narrow face"),
            ("Span", f"{span_ft:g} ft, simply supported; bearing length {bearing_in:g} in at each support"
             + (f"; members at {spacing_in:g} in on centre" if spacing_in else "")),
            ("Bracing", "compression edge supported throughout its length" if lu_ft <= 0 else
             f"compression edge braced at {lu_ft:g} ft; ends held against rotation"),
            ("Conditions", "dry use, moisture content under 16 percent; " + ("repetitive member" if repetitive else "not a repetitive member"))]
    load_lines = []
    for ld in loads:
        if ld["kind"] == "uniform":
            where = f"{ld.get('x1_ft', 0):g} to {ld.get('x2_ft', span_ft):g} ft"
            if "area" in ld:
                load_lines.append(f"{ld['case']:<3} area    {ld['area']:>9.1f} psf x {spacing_in:g} in = {ld['w']:.1f} plf   {where:<14} {ld.get('label', '')}")
            else:
                load_lines.append(f"{ld['case']:<3} uniform {ld['w']:>9.1f} plf   {where:<16} {ld.get('label', '')}")
        else:
            load_lines.append(f"{ld['case']:<3} point   {ld['P']:>9.0f} lb    at {ld['x_ft']:g} ft{'':<8} {ld.get('label', '')}")
    assumptions = ["Allowable stress design, 2018 NDS Chapter 8, with reference design values from " + ref["report"] + ". "
                   "Temperature factor Ct = 1.0 (NDS 2.3.3, sustained temperature to 100 F).",
                   "Shear is taken at the face of the support with no reduction for loads near the support (NDS 3.4.3.1).",
                   "Deflection is bending deflection with the true modulus of elasticity plus shear deflection, taken as "
                   "19.2 M / (E b d) with M the maximum moment in lb-in (" + ref["defl_src"] + ", written in terms of moment)."]
    if plies > 1:
        assumptions.append("The plies are fastened together to act as one member of the combined width.")
    assumptions.append(f"Self-weight {sw:.1f} plf (unit weight {unit_weight_pcf:g} pcf) added to load case {self_weight_case}."
                       if sw is not None else "Self-weight is not added separately.")
    sheet = SimpleSheet(
        mark, {"Parallam PSL": "PSL Beam", "TimberStrand LSL": "LSL Beam"}.get(product, "LVL Beam"), "Member", "ASD", info, load_lines, [(c.name, c.source) for c in combos],
        f"Governing Calculation ({gb['cb'].name})", steps, rows, assumptions,
        [x for x in ["notches and holes (NDS 8.4.1; manufacturer's limits)", "fastening of the plies to each other" if plies > 1 else None,
                     "lateral support at the ends against rotation (NDS 3.3.3.4)", "connections and hangers",
                     "bearing on the supporting member"] if x],
        picture=("wood_beam", dict(b=b, d=d, plies=plies, span=span_ft, size=f"{thickness:g}x{d:g}", kind="lvl", loads=[dict(case=x["case"], kind=x["kind"], w=x.get("w"), P=x.get("P"), x_ft=x.get("x_ft"), **({"x1_ft": x["x1_ft"], "x2_ft": x["x2_ft"]} if "x1_ft" in x else {})) for x in loads])), governing=gb["cb"].name)
    sheet.reactions = {o["cb"].name: o["reactions"] for o in out}
    sheet.diagram = _diagram_data(gb)
    return sheet


def lvl_post(mark, grade, b_in, d_in, height_ft, loads, combos, Ke1, Ke2, k_source, lu1_ft=None, lu2_ft=None, e1_in=0.0, e2_in=0.0,
             unit_weight_pcf=None, self_weight_case="D", product="Versa-Lam LVL", lateral=()):
    """One-piece structural composite lumber column, evaluation report values, 2018 NDS 3.6, 3.7 and
    15.4.1(b), ASD, dry use. b_in x d_in: the section. Ke1, lu1 and e1 go with the larger
    dimension d1; Ke2, lu2 and e2 with the smaller dimension d2. e1, e2: eccentricity of
    the axial load from the centre, in. loads: dict(case, P lb, label)."""
    from . import scl
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    if height_ft is None or height_ft <= 0:
        raise WorksheetError(f"{mark}: the height must be positive")
    if not (k_source or "").strip():
        raise WorksheetError(f"{mark}: say where the effective length factors come from")
    if b_in is None or d_in is None or min(b_in, d_in) <= 0:
        raise WorksheetError(f"{mark}: the section dimensions must be positive")
    e1, e2 = abs(e1_in or 0.0), abs(e2_in or 0.0)
    d1, d2 = max(b_in, d_in), min(b_in, d_in)
    A = d1 * d2
    lu1 = (lu1_ft if lu1_ft else height_ft) * 12.0
    lu2 = (lu2_ft if lu2_ft else height_ft) * 12.0
    try:
        ref = scl.column_spec(product, grade, d1, d2, lu2 / 12.0)
    except scl.SclError as e:
        raise WorksheetError(f"{mark}: {e}")
    e2_typed = e2
    e2 = max(e2, ref["e2_min"])
    Emin = ref["Emin"]
    rpt = ref["report"].replace("ICC-ES ", "")
    loads = [dict(x) for x in loads]
    sw = None
    if unit_weight_pcf:
        sw = unit_weight_pcf * A / 144.0 * height_ft
        loads.append(dict(case=self_weight_case, P=sw, label="self-weight"))
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    by_case = {}
    for ld in loads:
        if not ld.get("case") or ld.get("P") is None:
            raise WorksheetError(f"{mark}: a load is missing its case or its value")
        by_case[ld["case"]] = by_case.get(ld["case"], 0.0) + ld["P"]
    lat_by = {}
    for ld in lateral:
        if not ld.get("case") or ld.get("kind") not in ("uniform", "point"):
            raise WorksheetError(f"{mark}: a lateral load is missing its case or its type")
        lat_by.setdefault(ld["case"], []).append(ld)
    Hin, S1 = height_ft * 12.0, d2 * d1 ** 2 / 6
    FcE1 = 0.822 * Emin / (Ke1 * lu1 / d1) ** 2
    FcE2 = 0.822 * Emin / (Ke2 * lu2 / d2) ** 2
    CV1, CV2 = ref["CV1"], ref["CV2"]
    out = []
    for cb in combos:
        present = [c for c, v in cb.factors.items() if v and (c in by_case or c in lat_by)]
        if not present:
            continue
        P = sum(cb.factors[c] * by_case[c] for c in present if c in by_case)
        pts, dist = [], []
        for c in present:
            for ld in lat_by.get(c, []):
                if ld["kind"] == "uniform":
                    w = cb.factors[c] * ld["w"] / 12.0
                    dist.append(bm.DistLoad(0.0, Hin, w, w))
                else:
                    pts.append(bm.PointLoad(ld["x_ft"] * 12.0, cb.factors[c] * ld["P"]))
        Mlat = Vlat = 0.0
        if pts or dist:
            res = bm.solve(Hin, [0.0, Hin], 1.0e9, pts, dist)
            Mlat, Vlat = max(abs(res.M_max()[0]), abs(res.M_min()[0])), abs(res.V_abs_max()[0])
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
            Fc_star = ref["Fc"] * CD
            CP, st = wood.column_stability(Fc_star, Emin, Ke1 * lu1, d1, Ke2 * lu2, d2, c=0.9)
            CL, bst = wood.beam_stability(ref["Fb1"] * CD * (CV1 if CV1 > 1 else 1.0), Emin, lu2, d2, d1)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        Fb1 = ref["Fb1"] * CD * (CV1 * CL if CV1 > 1 else min(CV1, CL))
        Fb2 = ref["Fb2"] * CD * CV2
        fc = P / A
        o = dict(cb=cb, P=P, CD=CD, cd_case=cd_case, cd_dur=cd_dur, Fc_star=Fc_star, CP=CP, st=st, Fc_adj=Fc_star * CP, fc=fc,
                 Fb1=Fb1, Fb2=Fb2, CL=CL, FbE=bst.get("FbE"), i3=0.0, i4=0.0, M=Mlat, V=Vlat, fb1=Mlat / S1,
                 fv=1.5 * Vlat / A, Fv_adj=ref["Fv1"] * CD)
        if ((e1 or e2) and P > 0) or Mlat:
            o["i3"], o["i4"] = scl.eccentric_column(fc, o["Fc_adj"], d1, d2, e1, e2, Fb1, Fb2, FcE1, FcE2,
                                                    o["FbE"] if (e1 or Mlat) else None, fb1=o["fb1"])
            if o["i3"] == float("inf"):
                raise WorksheetError(f"{mark}: {cb.name}: the axial stress reaches the buckling stress; the column is too slender")
        o["ratio"] = max(fc / o["Fc_adj"], o["i3"])
        out.append(o)
    if not out:
        raise WorksheetError(f"{mark}: no load combination loads this column")
    g = max(out, key=lambda o: o["fc"] / o["Fc_adj"])
    has_lat = any(o["M"] for o in out)
    eq = "15.4-1" if has_lat else "15.4-3"
    rows = [Row("compression", g["cb"].name, g["fc"], g["Fc_adj"], "psi", f"2018 NDS 3.6.3, 3.7.1, Table 8.3.1; {rpt} Table 1",
                f"P = {g['P']:,.0f} lb; CD = {g['CD']:g} ({g['cd_case']}, {g['cd_dur']}); CP = {g['CP']:.3f}; le/d = {g['st']['ratio']:.2f}")]
    ge = None
    if e1 or e2 or has_lat:
        ge = max(out, key=lambda o: o["i3"])
        rows.append(Row("compression with bending" if has_lat else "compression with eccentric load", ge["cb"].name, ge["i3"], 1.0, "",
                        f"2018 NDS Eq. {eq}",
                        f"fc = {ge['fc']:.1f} psi; " + (f"fb1 = {ge['fb1']:.1f} psi, M = {ge['M'] / 12:,.0f} lb-ft; " if has_lat else "")
                        + f"e1 = {e1:.3g} in, e2 = {e2:.3g} in; CD = {ge['CD']:g} ({ge['cd_case']}, {ge['cd_dur']})"))
        g4 = max(out, key=lambda o: o["i4"])
        if (e1 or has_lat) and g4["FbE"]:
            rows.append(Row("stability under bending" if has_lat else "stability under eccentric load", g4["cb"].name, g4["i4"], 1.0, "",
                            "2018 NDS Eq. 15.4-2" if has_lat else "2018 NDS Eq. 15.4-4",
                            f"fc / FcE2 + [(fb1 + fc (6 e1 / d1)) / FbE]^2; FcE2 = {FcE2:,.0f} psi, FbE = {g4['FbE']:,.0f} psi"))
        if has_lat:
            gv = max(out, key=lambda o: o["fv"] / o["Fv_adj"])
            rows.append(Row("shear", gv["cb"].name, gv["fv"], gv["Fv_adj"], "psi", f"2018 NDS 3.4.1, 3.4.2, Table 8.3.1; {rpt} Table 1",
                            f"V = {gv['V']:,.0f} lb; CD = {gv['CD']:g} ({gv['cd_case']}, {gv['cd_dur']})"))
    L = footing_line
    steps = [L("d1 x d2", d1, "in", "member size", f"{d1:g} in x {d2:g} in"), L("A", A, "in2", "geometry"),
             L("Fc", ref["Fc"], "psi", ref["source"]),
             L(ref["emin_label"], Emin, "psi", ref["emin_src"], ref["emin_note"]),
             L("CD", g["CD"], "", "NDS Table 2.3.2", f"{g['cd_case']}, {g['cd_dur']}"),
             L("Fc* = Fc CD", g["Fc_star"], "psi", "NDS 3.7.1.5"),
             L("le1 / d1", Ke1 * lu1 / d1, "", "NDS 3.7.1.3", f"Ke = {Ke1:g}, l = {lu1:g} in, d1 = {d1:g} in"),
             L("le2 / d2", Ke2 * lu2 / d2, "", "NDS 3.7.1.3", f"Ke = {Ke2:g}, l = {lu2:g} in, d2 = {d2:g} in"),
             L("FcE = 0.822 Emin / (le/d)^2", g["st"]["FcE"], "psi", "NDS 3.7.1.5", f"le/d = {g['st']['ratio']:.2f}"),
             L("CP", g["CP"], "", "NDS Eq. 3.7-1", "c = 0.9 for structural composite lumber"),
             L("Fc' = Fc* CP", g["Fc_adj"], "psi", "NDS Table 8.3.1"),
             L("fc = P / A", g["fc"], "psi", "NDS 3.6.3", f"P = {g['P']:,.0f} lb, {g['cb'].name}")]
    if ge:
        if ref["e2_min"]:
            steps.append(L("e2, minimum", ref["e2_min"], "in", ref["e2_src"], f"t = {d2:g} in, L = {lu2 / 12:g} ft"))
        steps += [L("fc", ge["fc"], "psi", "NDS 3.6.3", f"P = {ge['P']:,.0f} lb"),
                  L("Fc'", ge["Fc_adj"], "psi", "NDS Table 8.3.1", f"CD = {ge['CD']:g}, CP = {ge['CP']:.3f}"),
                  L("FcE1 = 0.822 Emin / (le1/d1)^2", FcE1, "psi", "NDS 15.4.1"),
                  L("FcE2 = 0.822 Emin / (le2/d2)^2", FcE2, "psi", "NDS 15.4.1")]
        if has_lat:
            steps += [L("S1 = d2 d1^2 / 6", S1, "in3", "NDS Eq. 3.3-4", "bending about the strong axis"),
                      L("fb1 = M / S1", ge["fb1"], "psi", "NDS Eq. 3.3-1", f"M = {ge['M'] / 12:,.0f} lb-ft")]
        if e1 or has_lat:
            steps += [L("Fb1' = Fb CD x (lesser of CV and CL)" if CV1 <= 1 else "Fb1' = Fb CD CV CL", ge["Fb1"], "psi", "NDS Table 8.3.1, 8.3.6.1",
                        f"Fb = {ref['Fb1']:,.0f} psi, {ref['fb1_note']} ({ref['source']}); CV = {CV1:.3f} ({ref['cv_src']}), CL = {ge['CL']:.3f}"),
                      L("fc (6 e1 / d1)", ge["fc"] * 6 * e1 / d1, "psi", "NDS 15.4.1", f"e1 = {e1:.3g} in")]
            if ge["FbE"]:
                steps.append(L("FbE = 1.20 Emin / RB^2", ge["FbE"], "psi", "NDS 3.3.3.8", f"unbraced {lu2 / 12:g} ft"))
        if e2:
            steps += [L("Fb2' = Fb CD CV", ge["Fb2"], "psi", "NDS Table 8.3.1", f"Fb = {ref['Fb2']:,.0f} psi, {ref['fb2_note']} ({ref['source']}); CV = {CV2:.3f} ({ref['cv_src']})"),
                      L("fc (6 e2 / d2)", ge["fc"] * 6 * e2 / d2, "psi", "NDS 15.4.1", f"e2 = {e2:.3g} in")]
        steps.append(L(f"Eq. {eq}", ge["i3"], "", f"NDS Eq. {eq}", "not more than 1.0"))
    info = [("Member", f"{d2:g} in x {d1:g} in {ref['name']} {grade}, one piece"),
            ("Height", f"{height_ft:g} ft; unbraced {lu1 / 12:g} ft for the {d1:g} in dimension and {lu2 / 12:g} ft for the {d2:g} in dimension"),
            ("Ends", f"Ke = {Ke1:g} and {Ke2:g} ({k_source.strip()})"),
            ("Load Position", f"eccentricity {e1:.3g} in parallel to the {d1:g} in face and {e2:.3g} in parallel to the {d2:g} in face"
             if (e1 or e2) else "along the centre of the column"),
            ("Conditions", "dry use, moisture content under 16 percent")]
    load_lines = [f"{ld['case']:<3} axial {ld['P']:>10,.0f} lb   {ld.get('label', '')}" for ld in loads]
    for ld in lateral:
        load_lines.append(f"{ld['case']:<3} lateral uniform {ld['w']:>7.1f} plf   {ld.get('label', '')}" if ld["kind"] == "uniform" else
                          f"{ld['case']:<3} lateral point {ld['P']:>9,.0f} lb at {ld['x_ft']:g} ft   {ld.get('label', '')}")
    assumptions = ["Allowable stress design, 2018 NDS Chapter 8, with reference design values from " + ref["report"] + ". "
                   "Temperature factor Ct = 1.0 (NDS 2.3.3, sustained temperature to 100 F)."]
    if lateral:
        assumptions.append("Lateral load acts on the narrow face and bends the column about its strong axis; the column spans simply "
                           "between its base and its top.")
    if e1 or e2 or lateral:
        assumptions.append(ref["assumption"])
        if ref["e2_min"] and e2_typed < ref["e2_min"]:
            assumptions.append(f"The eccentricity parallel to the {d2:g} in face is the minimum of {ref['e2_min']:.3f} in "
                               "(ESR-1387 Table 1 note 13).")
    else:
        assumptions.append("The axial load acts along the centre of the column. No bending is considered.")
    assumptions.append(f"Self-weight {sw:,.0f} lb (unit weight {unit_weight_pcf:g} pcf) added to load case {self_weight_case}."
                       if sw is not None else "Self-weight is not added separately.")
    sheet = SimpleSheet(
        mark, {"Parallam PSL": "PSL Column", "TimberStrand LSL": "LSL Column"}.get(product, "LVL Column"), "Member", "ASD", info, load_lines, [(c.name, c.source) for c in combos],
        f"Governing Calculation ({g['cb'].name})", steps, rows, assumptions,
        (["deflection under lateral load", "lateral load on the wide face"] if lateral else ["bending from lateral load (NDS 15.4.1(a))"]) + ["bearing on the end grain and on the supporting member (NDS 3.10)",
         "connections at the top and base"],
        picture=("wood_post", dict(b=b_in, d=d_in, height=height_ft, size=f"{d2:g}x{d1:g}", kind="lvl", axial=[f"{x['case']} {x['P']:,.0f} lb" for x in loads], lateral=[dict(x) for x in lateral])), governing=g["cb"].name)
    sheet.base = {o["cb"].name: o["P"] for o in out}
    sheet.governing = max(out, key=lambda o: o["ratio"])["cb"].name
    return sheet


def glulam_beam(mark, stress_class, southern_pine, b, d, span_ft, loads, combos, defl_checks, lu_ft, bearing_in, wet,
                unit_weight_pcf=None, self_weight_case="D", spacing_in=None):
    """Glued laminated timber beam, simply supported, bent about the x-x axis; 2018 NDS
    Chapter 5 and Supplement Table 5A, ASD. b, d in inches. See glulam.py."""
    from . import glulam
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    if span_ft is None or span_ft <= 0 or bearing_in is None or bearing_in <= 0:
        raise WorksheetError(f"{mark}: span and bearing length must be positive")
    try:
        ref = glulam.values(stress_class)
        if ref["sp_only"] and not southern_pine:
            raise glulam.GlulamError(f"glulam: stress class {stress_class} is Southern Pine")
        CV = glulam.volume_factor(span_ft, d or 0, b or 0, southern_pine)
    except glulam.GlulamError as e:
        raise WorksheetError(f"{mark}: {e}")
    CMb, CMv, CMp, CME = ((glulam.WET["Fb"], glulam.WET["Fv"], glulam.WET["Fc_perp"], glulam.WET["E"]) if wet else (1.0, 1.0, 1.0, 1.0))
    A, S, I = b * d, b * d * d / 6, b * d ** 3 / 12
    Lin = span_ft * 12.0
    E_adj, Emin_adj = ref["E"] * CME, ref["Ey_min"] * CME
    loads = [dict(x) for x in loads]
    for ld in loads:
        if ld.get("kind") == "area":
            if not spacing_in or spacing_in <= 0:
                raise WorksheetError(f"{mark}: an area load needs the member spacing")
            ld.update(kind="uniform", w=ld["q"] * spacing_in / 12.0, area=ld["q"])
    sw = None
    if unit_weight_pcf:
        sw = unit_weight_pcf * A / 144.0
        loads.append(dict(case=self_weight_case, kind="uniform", w=sw, label="self-weight"))
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    by_case = {}
    for ld in loads:
        for k in ("case", "kind"):
            if not ld.get(k):
                raise WorksheetError(f"{mark}: a load is missing its {k}")
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
        return bm.solve(Lin, [0.0, Lin], E_adj * I, pts, dist)

    out = []
    for cb in combos:
        present = [c for c, v in cb.factors.items() if v and c in by_case]
        res = run(cb.factors)
        if res is None:
            continue
        try:
            CD, cd_case, cd_dur = wood.load_duration(present)
            Fb_star = ref["Fb"] * CD * CMb
            CL, st = wood.beam_stability(Fb_star, Emin_adj, lu_ft * 12.0, b, d)
        except wood.WoodError as e:
            raise WorksheetError(f"{mark}: {e}")
        Fb_adj = Fb_star * min(CV, CL)
        M = max(abs(res.M_max()[0]), abs(res.M_min()[0]))
        V = abs(res.V_abs_max()[0])
        R = max(abs(v) for v in res.reactions.values())
        out.append(dict(res=res, cb=cb, CD=CD, cd_case=cd_case, cd_dur=cd_dur, CL=CL, st=st, Fb_star=Fb_star, Fb_adj=Fb_adj,
                        Fv_adj=ref["Fv"] * CD * CMv, M=M, V=V, R=R, fb=M / S, fv=1.5 * V / A, reactions=dict(res.reactions)))
    if not out:
        raise WorksheetError(f"{mark}: no load combination loads this beam")
    Fperp = ref["Fc_perp"] * CMp
    gb = max(out, key=lambda o: o["fb"] / o["Fb_adj"])
    gv = max(out, key=lambda o: o["fv"] / o["Fv_adj"])
    gr = max(out, key=lambda o: o["R"])
    fac_txt = lambda o: f"CD = {o['CD']:g} ({o['cd_case']}, {o['cd_dur']})"
    rows = [Row("bending", gb["cb"].name, gb["fb"], gb["Fb_adj"], "psi", "2018 NDS 3.3.1, Table 5.3.1",
                f"M = {gb['M'] / 12:,.0f} lb-ft; {fac_txt(gb)}; CV = {CV:.3f}; CL = {gb['CL']:.3f}"),
            Row("shear", gv["cb"].name, gv["fv"], gv["Fv_adj"], "psi", "2018 NDS 3.4.1, 3.4.2, Table 5.3.1",
                f"V = {gv['V']:,.0f} lb at the support; {fac_txt(gv)}"),
            Row("bearing at support", gr["cb"].name, gr["R"] / (b * bearing_in), Fperp, "psi", "2018 NDS 3.10.2, Table 5.3.1",
                f"reaction {gr['R']:,.0f} lb on {b:g} in x {bearing_in:g} in; Cb = 1.0 at the end of a member")]
    for dc in defl_checks:
        res = run(dc.factors)
        if res is None:
            continue
        dl = max(abs(res.defl_max()[0]), abs(res.defl_min()[0]))
        rows.append(Row(f"deflection, {dc.label}", " + ".join(f"{v:g}{k}" if v != 1 else k for k, v in dc.factors.items()),
                        dl, Lin / dc.ratio, "in", dc.source, f"limit span/{dc.ratio:g}; Ex' = {E_adj:,.0f} psi"))
    L = footing_line
    st = gb["st"]
    x_txt = "20, Southern Pine" if southern_pine else "10"
    steps = [L("b x d", b, "in", "member size", f"d = {d:g} in"),
             L("A = b d", A, "in2", "geometry"), L("S = b d^2 / 6", S, "in3", "NDS Eq. 3.3-4"),
             L("I = b d^3 / 12", I, "in4", "NDS Eq. 3.3-3"),
             L("Fbx+", ref["Fb"], "psi", ref["source"], "bottom of the beam in tension"),
             L("CD", gb["CD"], "", "NDS Table 2.3.2", f"{gb['cd_case']}, {gb['cd_dur']}"),
             L("CM", CMb, "", "Table 5A adjustment factors", "wet service" if wet else "dry service"),
             L("CV = (21/L)^(1/x) (12/d)^(1/x) (5.125/b)^(1/x)", CV, "", "NDS Eq. 5.3-1", f"L = {span_ft:g} ft; x = {x_txt}; not more than 1.0")]
    if "RB" in st:
        steps += [L("le", st["le"], "in", "NDS Table 3.3.3, note 1", f"lu = {lu_ft * 12:g} in"),
                  L("RB = sqrt(le d / b^2)", st["RB"], "", "NDS Eq. 3.3-5"),
                  L("Ey min'", Emin_adj, "psi", f"{ref['source']}; NDS 5.2.7"),
                  L("FbE = 1.20 Ey min' / RB^2", st["FbE"], "psi", "NDS 3.3.3.8"),
                  L("Fb*", gb["Fb_star"], "psi", "NDS 3.3.3.8"),
                  L("CL", gb["CL"], "", "NDS Eq. 3.3-6")]
    else:
        steps.append(L("CL", 1.0, "", "NDS 3.3.3", st["why"]))
    steps += [L("Fbx' = Fbx CD CM x (lesser of CV and CL)", gb["Fb_adj"], "psi", "NDS Table 5.3.1, 5.3.6"),
              L("fb = M / S", gb["fb"], "psi", "NDS Eq. 3.3-1", f"M = {gb['M'] / 12:,.0f} lb-ft, {gb['cb'].name}"),
              L("Fvx' = Fvx CD CM Cvr", gv["Fv_adj"], "psi", "NDS Table 5.3.1", f"Fvx = {ref['Fv']:g} psi; Cvr = 1.0; {fac_txt(gv)}"),
              L("fv = 3V / (2 b d)", gv["fv"], "psi", "NDS Eq. 3.4-2", f"V = {gv['V']:,.0f} lb, {gv['cb'].name}"),
              L("Fc_perp' = Fc_perp CM Cb", Fperp, "psi", "NDS Table 5.3.1", f"Fc_perp x = {ref['Fc_perp']:g} psi"),
              L("Ex' = Ex CM", E_adj, "psi", "NDS Table 5.3.1, 5.2.7", f"Ex = {ref['E']:,.0f} psi")]
    info = [("Member", f"{b:g} in x {d:g} in glued laminated timber, stress class {stress_class}" + (", Southern Pine" if southern_pine and not ref["sp_only"] else "")),
            ("Span", f"{span_ft:g} ft, simply supported; bearing length {bearing_in:g} in at each support"
             + (f"; members at {spacing_in:g} in on centre" if spacing_in else "")),
            ("Bracing", "compression edge supported throughout its length" if lu_ft <= 0 else
             f"compression edge braced at {lu_ft:g} ft; ends held against rotation"),
            ("Conditions", ("wet service, moisture content 16 percent or more" if wet else "dry service")
             + "; straight, constant section, tension laminations at the bottom")]
    load_lines = []
    for ld in loads:
        if ld["kind"] == "uniform":
            where = f"{ld.get('x1_ft', 0):g} to {ld.get('x2_ft', span_ft):g} ft"
            if "area" in ld:
                load_lines.append(f"{ld['case']:<3} area    {ld['area']:>9.1f} psf x {spacing_in:g} in = {ld['w']:.1f} plf   {where:<14} {ld.get('label', '')}")
            else:
                load_lines.append(f"{ld['case']:<3} uniform {ld['w']:>9.1f} plf   {where:<16} {ld.get('label', '')}")
        else:
            load_lines.append(f"{ld['case']:<3} point   {ld['P']:>9.0f} lb    at {ld['x_ft']:g} ft{'':<8} {ld.get('label', '')}")
    assumptions = ["Allowable stress design, 2018 NDS Chapter 5. Temperature factor Ct = 1.0 (NDS 2.3.3, sustained temperature to 100 F).",
                   "Shear is taken at the face of the support with no reduction for loads near the support (NDS 3.4.3.1). "
                   "Shear reduction factor Cvr = 1.0: the member is not notched and is not subject to impact or cyclic loading "
                   "(NDS 5.3.10).",
                   f"Self-weight {sw:.1f} plf (unit weight {unit_weight_pcf:g} pcf) added to load case {self_weight_case}."
                   if sw is not None else "Self-weight is not added separately."]
    sheet = SimpleSheet(
        mark, "Glulam Beam", "Member", "ASD", info, load_lines, [(c.name, c.source) for c in combos],
        f"Governing Calculation ({gb['cb'].name})", steps, rows, assumptions,
        ["shear at connections, with Cvr = 0.72 (NDS 5.3.10)", "notches, taper and holes (NDS 5.4, 3.2.3)",
         "lateral support at the ends against rotation (NDS 3.3.3.4)", "connections and hangers", "bearing on the supporting member"],
        picture=("wood_beam", dict(b=b, d=d, plies=1, span=span_ft, size=f"{b:g}x{d:g}", kind="glulam", lams=max(int(round(d / 1.5)), 2), loads=[dict(case=x["case"], kind=x["kind"], w=x.get("w"), P=x.get("P"), x_ft=x.get("x_ft"), **({"x1_ft": x["x1_ft"], "x2_ft": x["x2_ft"]} if "x1_ft" in x else {})) for x in loads])), governing=gb["cb"].name)
    sheet.reactions = {o["cb"].name: o["reactions"] for o in out}
    sheet.diagram = _diagram_data(gb)
    return sheet
