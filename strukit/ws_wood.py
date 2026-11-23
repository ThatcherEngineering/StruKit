"""Wood beam worksheet: a simply supported sawn lumber beam, 2018 NDS, ASD.
Loads in plf and lb, span in ft. See wood.py for the provisions used."""
import math

from . import beam as bm, wood
from .steel_beam import Line
from .ws_more import SimpleSheet
from .ws_steel_beam import Row, WorksheetError

footing_line = Line


def beam(mark, species, grade, size, plies, span_ft, loads, combos, defl_checks, lu_ft, bearing_in, wet, incised,
         repetitive, unit_weight_pcf=None, self_weight_case="D"):
    """species, grade: as listed in 2018 NDS Supplement Table 4A. size: nominal, "2x10".
    plies: number of pieces side by side, fastened to act together. lu_ft: unbraced length
    of the compression edge (0 when it is supported throughout). bearing_in: bearing
    length at each support. unit_weight_pcf: wood unit weight for self-weight, or None to
    leave self-weight out. loads: dict(case, kind "uniform"|"point", w plf or P lb, x1_ft,
    x2_ft or x_ft, label). defl_checks: ws_steel_beam.DeflCheck."""
    if not combos:
        raise WorksheetError(f"{mark}: no ASD load combinations given")
    if plies not in (1, 2, 3, 4, 5, 6):
        raise WorksheetError(f"{mark}: the number of plies must be 1 to 6")
    if span_ft is None or span_ft <= 0 or bearing_in is None or bearing_in <= 0:
        raise WorksheetError(f"{mark}: span and bearing length must be positive")
    try:
        ref, CF, grade_note = wood.values(species, grade, size)
    except wood.WoodError as e:
        raise WorksheetError(f"{mark}: {e}")
    b1, d = wood.SIZES[size]
    b = b1 * plies
    A, S, I = b * d, b * d * d / 6, b * d ** 3 / 12
    Lin = span_ft * 12.0
    f = wood.factors(ref["Fb"], CF, wet, incised, repetitive)
    E_adj, Emin_adj = ref["E"] * f.CM_E * f.Ci_E, ref["Emin"] * f.CM_E * f.Ci_E
    loads = [dict(x) for x in loads]
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
        out.append(dict(cb=cb, CD=CD, cd_case=cd_case, cd_dur=cd_dur, CL=CL, st=st, Fb_star=Fb_star, Fb_adj=Fb_adj,
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
             L("Fb", ref["Fb"], "psi", SUPP_T4A), L("CD", gb["CD"], "", "NDS Table 2.3.2", f"{gb['cd_case']}, {gb['cd_dur']}"),
             L("CM", f.CM_b, "", "Table 4A adjustment factors", "wet service" if wet else "dry service"),
             L("CF", CF, "", "Table 4A adjustment factors", f"{size}, {grade}"),
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
    info = [("Member", f"({plies}) {size} {sp} {grade}" + (f" ({grade_note})" if grade_note else "")),
            ("Size", f"{b:g} in x {d:g} in dressed" + (f" ({plies} plies of {b1:g} in)" if plies > 1 else "")),
            ("Span", f"{span_ft:g} ft, simply supported; bearing length {bearing_in:g} in at each support"),
            ("Bracing", "compression edge supported throughout its length" if lu_ft <= 0 else
             f"compression edge braced at {lu_ft:g} ft; ends held against rotation"),
            ("Conditions", ("wet service" if wet else "dry service") + "; " + ("incised" if incised else "not incised") + "; "
             + ("repetitive member" if repetitive else "not a repetitive member"))]
    load_lines = []
    for ld in loads:
        if ld["kind"] == "uniform":
            where = f"{ld.get('x1_ft', 0):g} to {ld.get('x2_ft', span_ft):g} ft"
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
        picture=("wood_beam", dict(b=b, d=d, plies=plies, span=span_ft, size=size)), governing=gb["cb"].name)
    sheet.not_checked = [x for x in sheet.not_checked if x]
    sheet.reactions = {o["cb"].name: o["reactions"] for o in out}
    return sheet


SUPP_T1B = "2018 NDS Supplement Table 1B"
SUPP_T4A = "2018 NDS Supplement Table 4A"
