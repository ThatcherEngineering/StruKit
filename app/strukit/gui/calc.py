"""Worksheet screens: the forms, and the bridge from what is typed to the calculations.

Each worksheet kind has a form description (fields and tables) that the screen draws,
and a function that turns the typed values into the same worksheet objects the tests
exercise. Nothing typed is defaulted here: a blank required box comes back as a message
naming the box, and all such messages come back together.
"""
import re

from .. import calcsheet, shapes, ws_conn, ws_footing, ws_frame, ws_more, ws_steel_beam, ws_steel_column
from ..footing import FootingInputError
from ..steel_beam import SteelInputError
from ..ws_steel_beam import Combo, DeflCheck, WorksheetError


class Missing(Exception):
    def __init__(self, items):
        super().__init__("; ".join(items))
        self.items = items


def F(key, label, kind="number", unit="", options=None, required=True, help=""):
    return dict(key=key, label=label, type=kind, unit=unit, options=options, required=required, help=help)


def T(key, label, columns, help=""):
    return dict(key=key, label=label, columns=columns, help=help)


CASE = F("case", "Case", "text", help="D, L, Lr, S, W, E ...")
FORMS = {
    "steel_beam": dict(
        title="Steel Beam", code="AISC 360-22", mark="B",
        fields=[F("shape", "Section", "shape"), F("Fy", "Fy", unit="ksi"), F("span", "Span", unit="ft"),
                F("bracing", "Compression flange braced", "select", options=["continuous", "at points"]),
                F("brace_pts", "Brace points", "text", "ft", required=False,
                  help="distances from the left end, separated by commas; the ends are always braced"),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["uniform", "point"]),
                                     F("mag", "Load", unit="k/ft or k"),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "steel_column": dict(
        title="Steel Column", code="AISC 360-22", mark="C",
        fields=[F("shape", "Section", "shape"), F("Fy", "Fy", unit="ksi"), F("height", "Height", unit="ft"),
                F("ends", "Top of column", "select",
                  options=["held sideways (braced)", "free about x (cantilever, strong axis)",
                           "free about y (cantilever, weak axis)", "free both ways (cantilever)"]),
                F("Lx", "Unbraced length, x axis", unit="ft", required=False, help="blank = full height"),
                F("Ly", "Unbraced length, y axis", unit="ft", required=False, help="blank = full height"),
                F("Kx", "Kx"), F("Ky", "Ky"), F("k_source", "K comes from", "text"),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("loads", "Axial loads", [CASE, F("P", "P", unit="kip"), F("label", "Note", "text", required=False)]),
                T("lateral", "Sideways loads", [CASE, F("bending", "Bends about", "select", options=["x", "y"]),
                                                F("kind", "Type", "select", options=["uniform", "point"]),
                                                F("mag", "Load", unit="k/ft or k"),
                                                F("x", "Height", unit="ft", required=False, help="point loads: height above the base"),
                                                F("label", "Note", "text", required=False)]),
                T("leaning", "Loads leaning on this column (cantilever only)", [CASE, F("P", "P", unit="kip")]),
                T("drift", "Drift limits at the top (cantilever only)",
                  [F("label", "Name", "text"), F("expr", "Loads", "text"), F("ratio", "Height /"), F("source", "Source", "text")])]),
    "footing_iso": dict(
        title="Isolated Footing", code="ACI 318-19", mark="F",
        fields=[F("B", "Width, x", unit="ft"), F("L", "Length, y", unit="ft"), F("h", "Thickness", unit="in"),
                F("fc", "f'c", unit="psi"), F("fy", "fy", unit="psi"), F("conc_pcf", "Concrete weight", unit="pcf"),
                F("col_x", "Column, x", unit="in"), F("col_y", "Column, y", unit="in"),
                F("supported", "Column is", "select", options=["steel", "wood", "concrete"]),
                F("plate_x", "Base plate, x", unit="in", required=False), F("plate_y", "Base plate, y", unit="in", required=False),
                F("bar", "Bar size #"), F("n_x", "Bars in x"), F("n_y", "Bars in y"), F("cover", "Clear cover", unit="in"),
                F("bottom", "Lowest bars run in", "select", options=["x", "y"]),
                F("P_service", "Service load", unit="lb"), F("service_combo", "Service combination", "text"),
                F("Pu", "Factored load", unit="lb"), F("strength_combo", "Strength combination", "text"),
                F("q_allow", "Allowable soil bearing", unit="psf"), F("soil_source", "Soil bearing source", "text"),
                F("soil_depth", "Soil over footing", unit="ft", required=False), F("soil_pcf", "Soil weight", unit="pcf", required=False),
                F("loads_from", "Loads come from", "text", required=False, help="printed on the sheet")],
        tables=[]),
    "footing_cont": dict(
        title="Continuous Footing", code="ACI 318-19", mark="CF",
        fields=[F("W", "Width", unit="ft"), F("h", "Thickness", unit="in"), F("fc", "f'c", unit="psi"), F("fy", "fy", unit="psi"),
                F("conc_pcf", "Concrete weight", unit="pcf"), F("wall", "Wall thickness", unit="in"),
                F("wall_kind", "Wall is", "select", options=["concrete", "masonry"]),
                F("stem_h", "Stem wall height", unit="in", required=False), F("stem_pcf", "Stem wall weight", unit="pcf", required=False),
                F("bar_t", "Bars across, size #"), F("spacing_t", "Bars across, spacing", unit="in"),
                F("bar_l", "Bars lengthwise, size #"), F("n_l", "Bars lengthwise, number"), F("cover", "Clear cover", unit="in"),
                F("P_service", "Service wall load", unit="lb/ft"), F("service_combo", "Service combination", "text"),
                F("Pu", "Factored wall load", unit="lb/ft"), F("strength_combo", "Strength combination", "text"),
                F("dead_factor", "Dead-load factor of that combination", help="applied to the stem wall weight"),
                F("q_allow", "Allowable soil bearing", unit="psf"), F("soil_source", "Soil bearing source", "text"),
                F("soil_depth", "Soil over footing", unit="ft", required=False), F("soil_pcf", "Soil weight", unit="pcf", required=False)],
        tables=[]),
    "frame": dict(
        title="Moment Frame", code="AISC 360-22", mark="FR",
        fields=[F("bays", "Bay widths", "text", "ft", help="left to right, separated by commas"),
                F("stories", "Story heights", "text", "ft", help="bottom to top (to the eave for a sloped roof)"),
                F("base", "Column bases", "select", options=["pin", "fixed"]),
                F("roof", "Roof", "select", options=["flat", "gable", "mono"]),
                F("rise", "Roof rise", unit="ft", required=False),
                F("col_shape", "Columns", "shape"), F("beam_shape", "Beams", "shape"),
                F("rafter_shape", "Rafters", "shape", required=False), F("Fy", "Fy", unit="ksi"),
                F("lb_col", "Columns braced out of plane at", unit="ft"), F("lb_beam", "Beams braced at", unit="ft"),
                F("lb_rafter", "Rafters braced at", unit="ft", required=False),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("shape_of", "Section for one member (optional)", [F("member", "Member", "text"), F("shape", "Section", "shape")]),
                T("loads", "Loads", [CASE, F("where", "On", "text", help="beams, rafters, columns, level:1, a member name; "
                                                                             "joint N1-1; or lateral level:1"),
                                     F("kind", "Type", "select", options=["gravity per ft of member", "gravity per ft horizontal",
                                                                          "sideways per ft of member", "joint load", "lateral at level"]),
                                     F("mag", "Load", unit="k/ft or k"), F("Fx", "Joint Fx", unit="kip", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("leaning", "Loads on columns outside the frame", [CASE, F("level", "Level"), F("P", "P", unit="kip")]),
                T("drift", "Story drift limits", [F("label", "Name", "text"), F("expr", "Loads", "text"),
                                                  F("ratio", "Story height /"), F("source", "Source", "text")])]),
    "weld": dict(
        title="Fillet Weld", code="AISC 360-22", mark="W",
        fields=[F("size", "Weld size (leg)", unit="in"), F("length", "Length of each weld", unit="in"),
                F("n_lines", "Number of welds"), F("FEXX", "Electrode FEXX", unit="ksi"),
                F("theta", "Angle of load to weld axis", unit="deg", help="0 = load along the weld, 90 = across it"),
                F("directional", "Use the directional increase", "select", options=["yes", "no"], help="Eq. J2-5"),
                F("end_loaded", "End loaded", "select", options=["yes", "no"], help="J2.2b(d): long welds loaded from one end"),
                F("t_thinner", "Thinner part joined", unit="in", required=False, help="turns on the minimum size check"),
                F("t_edge", "Thickness at the welded edge", unit="in", required=False, help="turns on the maximum size check"),
                F("base_t", "Base metal thickness", unit="in", required=False),
                F("base_Fu", "Base metal Fu", unit="ksi", required=False)],
        tables=[T("loads", "Force on the weld group", [CASE, F("P", "Force", unit="kip"), F("label", "Note", "text", required=False)])]),
    "bolts": dict(
        title="Bolt Line", code="AISC 360-22", mark="BG",
        fields=[F("d", "Bolt diameter", unit="in"), F("group", "Bolt type", "select", options=["A325", "A490", "A307", "F3148"]),
                F("n", "Number of bolts"), F("spacing", "Spacing", unit="in"),
                F("edge", "Edge distance", unit="in", help="bolt centre to the edge the load pushes toward"),
                F("threads", "Threads", "select", options=["N", "X"], help="N = in the shear plane, X = excluded"),
                F("planes", "Shear planes"),
                F("deformation", "Hole deformation is a design consideration", "select", options=["yes", "no"])],
        tables=[T("plies", "Connected parts", [F("t", "Thickness", unit="in"), F("Fu", "Fu", unit="ksi"),
                                               F("has_edge", "Edge in load direction", "select", options=["yes", "no"]),
                                               F("count", "How many", required=False, help="2 for a pair of angles")]),
                T("loads", "Force along the bolt line", [CASE, F("P", "Force", unit="kip"), F("label", "Note", "text", required=False)])]),
    "base_plate": dict(
        title="Base Plate", code="AISC 360-22", mark="BP",
        fields=[F("shape", "Column", "shape"), F("N", "Plate length (along column depth)", unit="in"),
                F("B", "Plate width", unit="in"), F("t", "Plate thickness", unit="in"), F("Fy", "Plate Fy", unit="ksi"),
                F("fc", "Concrete f'c", unit="psi"),
                F("full", "Plate covers the whole support", "select", options=["yes", "no"]),
                F("sup_N", "Support length (parallel to plate length)", unit="in", required=False),
                F("sup_B", "Support width", unit="in", required=False)],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="kip"), F("label", "Note", "text", required=False)])]),
    "footing_moment": dict(
        title="Footing with Moment", code="ACI 318-19", mark="FM",
        fields=[F("B", "Width, in the direction of the moment", unit="ft"), F("L", "Length", unit="ft"), F("h", "Thickness", unit="in"),
                F("fc", "f'c", unit="psi"), F("fy", "fy", unit="psi"), F("conc_pcf", "Concrete weight", unit="pcf"),
                F("col_x", "Column, in the direction of the moment", unit="in"), F("col_y", "Column, other way", unit="in"),
                F("supported", "Column is", "select", options=["steel", "wood", "concrete"]),
                F("plate_x", "Base plate, x", unit="in", required=False), F("plate_y", "Base plate, y", unit="in", required=False),
                F("bar", "Bar size #"), F("n_x", "Bars in x"), F("n_y", "Bars in y"), F("cover", "Clear cover", unit="in"),
                F("bottom", "Lowest bars run in", "select", options=["x", "y"]),
                F("q_allow", "Allowable soil bearing", unit="psf"), F("soil_source", "Soil bearing source", "text"),
                F("soil_depth", "Soil over footing", unit="ft", required=False), F("soil_pcf", "Soil weight", unit="pcf", required=False),
                F("ot_required", "Required safety factor, overturning", required=False),
                F("slide_mu", "Friction coefficient, footing on soil", required=False),
                F("slide_required", "Required safety factor, sliding", required=False),
                F("limits_source", "Source of those limits", "text", required=False),
                F("loads_from", "Loads come from", "text", required=False, help="printed on the sheet")],
        tables=[T("service", "Service load cases (at the top of the footing)",
                  [F("name", "Combination", "text"), F("P", "P", unit="lb"), F("M", "M", unit="lb-ft"), F("V", "V", unit="lb")]),
                T("strength", "Factored load cases",
                  [F("name", "Combination", "text"), F("P", "Pu", unit="lb"), F("M", "Mu", unit="lb-ft"), F("V", "Vu", unit="lb"),
                   F("wt_factor", "Dead-load factor", help="applied to the footing and soil weight")])]),
}


# ------------------------------------------------------------------ reading what was typed
def parse_expr(text):
    """ "1.2D + 1.6L" -> {"D": 1.2, "L": 1.6}."""
    out = {}
    s = (text or "").replace(" ", "")
    if not s:
        raise ValueError("no load combination typed")
    for sign, coef, case in re.findall(r"([+-]?)(\d*\.?\d*)\*?([A-Za-z][A-Za-z0-9]*)", s):
        f = float(coef) if coef else 1.0
        out[case] = out.get(case, 0.0) + (-f if sign == "-" else f)
    rebuilt = re.sub(r"[+\-*0-9.]", "", s)
    if not out or rebuilt != "".join(re.findall(r"[A-Za-z][A-Za-z0-9]*", s)):
        raise ValueError(f"cannot read the combination '{text}'")
    return out


class Reader:
    """Pulls typed values, collecting every blank or unreadable box."""

    def __init__(self, form, values):
        self.form, self.v, self.miss = form, values or {}, []
        self.labels = {f["key"]: f["label"] for f in form["fields"]}

    def num(self, key, required=True, label=None):
        raw = self.v.get(key)
        label = label or self.labels.get(key, key)
        if raw in (None, ""):
            if required:
                self.miss.append(f"{label} is blank")
            return None
        try:
            return float(str(raw).replace(",", ""))
        except ValueError:
            self.miss.append(f"{label}: '{raw}' is not a number")
            return None

    def text(self, key, required=True):
        raw = (self.v.get(key) or "").strip() if isinstance(self.v.get(key), str) else self.v.get(key)
        if raw in (None, ""):
            if required:
                self.miss.append(f"{self.labels.get(key, key)} is blank")
            return None
        return raw

    def nums(self, key):
        raw = self.text(key)
        if raw is None:
            return None
        try:
            return [float(x) for x in str(raw).replace(";", ",").split(",") if x.strip()]
        except ValueError:
            self.miss.append(f"{self.labels[key]}: '{raw}' is not a list of numbers")
            return None

    def rows(self, key):
        t = next(t for t in self.form["tables"] if t["key"] == key)
        out = []
        for n, row in enumerate(self.v.get(key) or [], 1):
            if not any(str(v).strip() for v in row.values() if v is not None):
                continue                                           # an empty row is not a row
            r = {}
            for col in t["columns"]:
                raw = row.get(col["key"])
                blank = raw in (None, "")
                if blank and col["required"]:
                    self.miss.append(f"{t['label']}, row {n}: {col['label']} is blank")
                if col["type"] == "number" and not blank:
                    try:
                        raw = float(str(raw).replace(",", ""))
                    except ValueError:
                        self.miss.append(f"{t['label']}, row {n}: {col['label']} '{raw}' is not a number")
                        raw = None
                r[col["key"]] = None if blank else raw
            out.append(r)
        return out

    def done(self):
        if self.miss:
            raise Missing(self.miss)


def combos(project, miss, which=None):
    """The project's load combinations for a design method. A project carries two lists,
    ASD (also the service combinations for soil bearing) and LRFD (also the factored
    combinations for concrete). An older project file has one list, for its own method."""
    which = which or project.get("method")
    if which not in ("ASD", "LRFD"):
        return []                                           # the method message covers this
    rows = project.get("combos_asd" if which == "ASD" else "combos_lrfd")
    if rows is None and (project.get("_file_method") or project.get("method")) == which:
        rows = project.get("combos")                        # older file: one list, for the method it was saved with
    out = []
    for n, c in enumerate(rows or [], 1):
        if not (c.get("expr") or "").strip():
            continue
        try:
            fac = parse_expr(c["expr"])
        except ValueError as e:
            miss.append(f"{which} load combinations, row {n}: {e}")
            continue
        if not (c.get("source") or "").strip():
            miss.append(f"{which} load combinations, row {n}: the source is blank")
            continue
        out.append(Combo(c["expr"].strip(), fac, c["source"].strip()))
    if not out:
        miss.append(f"No {which} load combinations are entered for the project (Project page)")
    return out


def checks(rows, miss, what):
    out = []
    for n, r in enumerate(rows, 1):
        try:
            out.append(DeflCheck(r["label"], parse_expr(r["expr"]), r["ratio"], r["source"]))
        except (ValueError, TypeError) as e:
            miss.append(f"{what}, row {n}: {e}")
    return out


def cases_used(cases, cb, miss):
    """A load whose case is in no combination would be left out without a word."""
    known = set().union(*[set(c.factors) for c in cb]) if cb else set()
    for c in sorted({str(x) for x in cases if x} - known):
        if cb:
            miss.append(f"Load case {c} is not in any load combination, so its loads would be left out")


def method(project, miss):
    m = project.get("method")
    if m not in ("ASD", "LRFD"):
        miss.append("Design method (ASD or LRFD) is not chosen on the Project page")
    return m


def yes(v):
    return {"yes": True, "no": False}.get(v)


# ------------------------------------------------------------------ building each worksheet
def build(kind, values, project):
    """Returns (sheet, pdf kind, keyword arguments for the calc sheet)."""
    form = FORMS[kind]
    r = Reader(form, values)
    mark = (values.get("mark") or "").strip()
    if not mark:
        r.miss.append("Mark is blank")
    if kind == "steel_beam":
        cb, m = combos(project, r.miss), method(project, r.miss)
        shape, Fy, span = r.text("shape"), r.num("Fy"), r.num("span")
        br, sw = r.text("bracing"), yes(r.text("self_weight"))
        pts = []
        if br == "at points":
            pts = r.nums("brace_pts") or []
        loads = []
        for ld in r.rows("loads"):
            if ld["kind"] == "uniform":
                d = dict(case=ld["case"], kind="uniform", w=ld["mag"])
                if ld["x1"] is not None or ld["x2"] is not None:
                    d.update(x1_ft=ld["x1"] or 0.0, x2_ft=ld["x2"] if ld["x2"] is not None else span)
            else:
                if ld["x1"] is None:
                    r.miss.append("Loads: a point load needs its location (From / at)")
                d = dict(case=ld["case"], kind="point", P=ld["mag"], x_ft=ld["x1"])
            if ld["label"]:
                d["label"] = ld["label"]
            loads.append(d)
        if not loads and sw is False:
            r.miss.append("No loads are entered")
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used([ld["case"] for ld in loads], cb, r.miss)
        r.done()
        s = ws_steel_beam.run(mark, shape, Fy, span, loads, cb, dc, "continuous" if br == "continuous" else pts, m, sw)
        return s, "steel_beam", dict(combos=cb)
    if kind == "steel_column":
        cb, m = combos(project, r.miss), method(project, r.miss)
        shape, Fy, H = r.text("shape"), r.num("Fy"), r.num("height")
        ends = r.text("ends") or ""
        sway = () if ends.startswith("held") else ("x",) if "about x" in ends else ("y",) if "about y" in ends else ("x", "y")
        Lx, Ly = r.num("Lx", False), r.num("Ly", False)
        Kx, Ky, ks, sw = r.num("Kx"), r.num("Ky"), r.text("k_source"), yes(r.text("self_weight"))
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        lat = []
        for x in r.rows("lateral"):
            d = dict(case=x["case"], bending=x["bending"], kind=x["kind"])
            if x["kind"] == "uniform":
                d["w"] = x["mag"]
            else:
                if x["x"] is None:
                    r.miss.append("Sideways loads: a point load needs its height")
                d.update(P=x["mag"], x_ft=x["x"])
            if x["label"]:
                d["label"] = x["label"]
            lat.append(d)
        lean = [dict(case=x["case"], P=x["P"]) for x in r.rows("leaning")]
        dc = checks(r.rows("drift"), r.miss, "Drift limits")
        cases_used([x["case"] for x in loads + lat + lean], cb, r.miss)
        r.done()
        s = ws_steel_column.run(mark, shape, Fy, H, loads, cb, Kx, Ky, ks, m, sw, Lx_ft=Lx, Ly_ft=Ly,
                                lateral=lat, sway=sway, leaning=lean, drift_checks=dc)
        return s, "steel_column", dict(combos=cb)
    if kind == "footing_iso":
        a = dict(B_ft=r.num("B"), L_ft=r.num("L"), h_in=r.num("h"), fc=r.num("fc"), fy=r.num("fy"),
                 col_x_in=r.num("col_x"), col_y_in=r.num("col_y"), bar=r.num("bar"), n_x=r.num("n_x"), n_y=r.num("n_y"),
                 cover_in=r.num("cover"), P_service=r.num("P_service"), service_combo=r.text("service_combo"),
                 Pu=r.num("Pu"), strength_combo=r.text("strength_combo"), q_allow_psf=r.num("q_allow"),
                 conc_pcf=r.num("conc_pcf"), plate_x_in=r.num("plate_x", False), plate_y_in=r.num("plate_y", False),
                 bottom_layer=r.text("bottom"), soil_depth_ft=r.num("soil_depth", False) or 0.0,
                 soil_pcf=r.num("soil_pcf", False) or 0.0)
        src, sup = r.text("soil_source"), r.text("supported")
        if a["soil_depth_ft"] and not a["soil_pcf"]:
            r.miss.append("Soil weight is blank (soil over the footing was entered)")
        r.done()
        for k in ("bar", "n_x", "n_y"):
            a[k] = int(a[k])
        fs = ws_footing.isolated(mark, src, sup, **a)
        if r.text("loads_from", False):
            fs.result.notes.append("Loads: " + r.text("loads_from", False) + ".")
        return fs, "footing", {}
    if kind == "footing_cont":
        a = dict(W_ft=r.num("W"), h_in=r.num("h"), fc=r.num("fc"), fy=r.num("fy"), wall_in=r.num("wall"),
                 bar_t=r.num("bar_t"), spacing_t_in=r.num("spacing_t"), bar_l=r.num("bar_l"), n_l=r.num("n_l"),
                 cover_in=r.num("cover"), P_service_plf=r.num("P_service"), service_combo=r.text("service_combo"),
                 Pu_plf=r.num("Pu"), strength_combo=r.text("strength_combo"), dead_factor=r.num("dead_factor"),
                 q_allow_psf=r.num("q_allow"), conc_pcf=r.num("conc_pcf"), wall_kind=r.text("wall_kind"),
                 stem_h_in=r.num("stem_h", False) or 0.0, stem_pcf=r.num("stem_pcf", False),
                 soil_depth_ft=r.num("soil_depth", False) or 0.0, soil_pcf=r.num("soil_pcf", False) or 0.0)
        src = r.text("soil_source")
        if a["stem_h_in"] and a["stem_pcf"] is None:
            r.miss.append("Stem wall weight is blank (a stem wall height was entered)")
        r.done()
        for k in ("bar_t", "bar_l", "n_l"):
            a[k] = int(a[k])
        return ws_footing.continuous(mark, src, **a), "footing", {}
    if kind == "frame":
        cb, m = combos(project, r.miss), method(project, r.miss)
        bays, stories = r.nums("bays"), r.nums("stories")
        base, roof, rise = r.text("base"), r.text("roof"), r.num("rise", False)
        cs, bs, rs, Fy = r.text("col_shape"), r.text("beam_shape"), r.text("rafter_shape", False), r.num("Fy")
        ub = {"columns": r.num("lb_col"), "beams": r.num("lb_beam")}
        lr = r.num("lb_rafter", False)
        if roof in ("gable", "mono"):
            if lr is None:
                r.miss.append("Rafters braced at is blank")
            if rise is None:
                r.miss.append("Roof rise is blank")
            ub["rafters"] = lr
        sw = yes(r.text("self_weight"))
        loads = []
        for x in r.rows("loads"):
            k, where = x["kind"], (x["where"] or "").strip()
            if k == "joint load":
                loads.append(dict(case=x["case"], node=where.replace("joint", "").strip(), Fx=x["Fx"] or 0.0, Fy=-x["mag"]))
            elif k == "lateral at level":
                try:
                    lv = int(where.lower().replace("lateral", "").replace("level:", "").replace("level", "").strip())
                except ValueError:
                    r.miss.append(f"Loads: '{where}' is not a level (type level:1)")
                    continue
                loads.append(dict(case=x["case"], level=lv, Fx=x["mag"]))
            else:
                d = dict(case=x["case"], on=where, w=x["mag"],
                         kind="projected" if "horizontal" in k else "length")
                if k.startswith("sideways"):
                    d["dir"] = "x"
                loads.append(d)
            if x["label"]:
                loads[-1]["label"] = x["label"]
        lean = [dict(case=x["case"], level=int(x["level"]), P=x["P"]) for x in r.rows("leaning") if x["level"] is not None]
        dc = checks(r.rows("drift"), r.miss, "Story drift limits")
        over = {x["member"]: x["shape"] for x in r.rows("shape_of") if x["member"] and x["shape"]}
        cases_used([x["case"] for x in loads + lean], cb, r.miss)
        r.done()
        lay = ws_frame.layout(bays, stories, base, cs, bs, roof=roof, rise_ft=rise or 0.0, rafter_shape=rs, shape_of=over)
        s = ws_frame.run(mark, lay, Fy, loads, cb, m, sw, ub, leaning=lean, drift_checks=dc)
        return s, "frame", {}
    if kind in ("weld", "bolts"):
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No force is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        if kind == "weld":
            a = dict(size=r.num("size"), length=r.num("length"), n_lines=r.num("n_lines"), FEXX=r.num("FEXX"),
                     theta_deg=r.num("theta"), directional=yes(r.text("directional")), end_loaded=yes(r.text("end_loaded")),
                     t_thinner=r.num("t_thinner", False), t_edge=r.num("t_edge", False),
                     base_t=r.num("base_t", False), base_Fu=r.num("base_Fu", False))
            if (a["base_t"] is None) != (a["base_Fu"] is None):
                r.miss.append("Base metal: give both the thickness and Fu, or neither")
            r.done()
            return ws_conn.fillet_weld(mark, loads, cb, m, **a), "conn", dict(combos=cb)
        plies = []
        for x in r.rows("plies"):
            ply = (x["t"], x["Fu"], yes(x["has_edge"]))
            plies.append(ply + ((int(x["count"]),) if x["count"] else ()))
        if not plies:
            r.miss.append("No connected parts are entered")
        a = dict(d=r.num("d"), group=r.text("group"), n=r.num("n"), spacing=r.num("spacing"), edge=r.num("edge"),
                 threads=r.text("threads"), planes=r.num("planes"), deformation=yes(r.text("deformation")))
        r.done()
        return ws_conn.bolt_line(mark, loads, cb, m, plies=plies, **a), "conn", dict(combos=cb)
    if kind == "base_plate":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        shape, N, B, t, Fy, fc = r.text("shape"), r.num("N"), r.num("B"), r.num("t"), r.num("Fy"), r.num("fc")
        full = yes(r.text("full"))
        sup = "full"
        if full is False:
            sup = (r.num("sup_N", label="Support length"), r.num("sup_B", label="Support width"))
        r.done()
        return ws_more.base_plate_sheet(mark, shape, N, B, t, Fy, fc, sup, loads, cb, m), "simple", {}
    if kind == "footing_moment":
        a = dict(B_ft=r.num("B"), L_ft=r.num("L"), h_in=r.num("h"), fc=r.num("fc"), fy=r.num("fy"),
                 col_x_in=r.num("col_x"), col_y_in=r.num("col_y"), bar=r.num("bar"), n_x=r.num("n_x"), n_y=r.num("n_y"),
                 cover_in=r.num("cover"), q_allow_psf=r.num("q_allow"), conc_pcf=r.num("conc_pcf"),
                 plate_x_in=r.num("plate_x", False), plate_y_in=r.num("plate_y", False), bottom_layer=r.text("bottom"),
                 soil_depth_ft=r.num("soil_depth", False) or 0.0, soil_pcf=r.num("soil_pcf", False) or 0.0,
                 ot_required=r.num("ot_required", False), slide_mu=r.num("slide_mu", False),
                 slide_required=r.num("slide_required", False))
        src, sup, lim = r.text("soil_source"), r.text("supported"), r.text("limits_source", False)
        a["service"], a["strength"] = r.rows("service"), r.rows("strength")
        if not a["service"]:
            r.miss.append("No service load case is entered")
        if not a["strength"]:
            r.miss.append("No factored load case is entered")
        if a["soil_depth_ft"] and not a["soil_pcf"]:
            r.miss.append("Soil weight is blank (soil over the footing was entered)")
        if (a["slide_mu"] is None) != (a["slide_required"] is None):
            r.miss.append("Sliding needs both the friction coefficient and the required safety factor")
        if any(a[k] is not None for k in ("ot_required", "slide_mu", "slide_required")) and not lim:
            r.miss.append("Source of those limits is blank (a stability limit was entered)")
        r.done()
        for k in ("bar", "n_x", "n_y"):
            a[k] = int(a[k])
        ss = ws_more.footing_moment_sheet(mark, src, sup, lim or "", **a)
        if r.text("loads_from", False):
            ss.assumptions.insert(0, "Loads: " + r.text("loads_from", False) + ".")
        return ss, "simple", {}
    raise WorksheetError(f"unknown worksheet '{kind}'")


def reactions(kind, values, project):
    """Base reactions of a steel column or a frame for every ASD combination (service) and
    every LRFD combination (factored), so a footing or base plate can take them without
    retyping. Each list is the member run with that list of combinations; for a cantilevered
    column or a frame that is a second-order analysis at that load level. Units: lb, lb-ft."""
    if kind not in ("steel_column", "frame"):
        return dict(error="Loads can be taken from a steel column or a moment frame.")
    out = dict(bases=[], service=[], strength=[], messages=[])
    for which, key in (("ASD", "service"), ("LRFD", "strength")):
        try:
            sheet, pk, kw = build(kind, values, dict(project, method=which, _file_method=project.get("method")))
        except Missing as e:
            out["messages"].append(f"{which} combinations: " + "; ".join(e.items))
            continue
        except (WorksheetError, SteelInputError, ValueError, KeyError) as e:
            out["messages"].append(f"{which} combinations: {e}")
            continue
        fac = {c.name: c.factors for c in (kw.get("combos") or getattr(sheet, "combos", []))}
        if pk == "frame":
            best = {}
            for label, per_node in sheet.reactions.items():
                name = label.split(" (")[0]
                for node, (rx, ry, mz) in per_node.items():
                    cur = best.get((name, node))
                    if cur is None or abs(mz) > abs(cur[2]) or (abs(mz) == abs(cur[2]) and abs(rx) > abs(cur[0])):
                        best[(name, node)] = (rx, ry, mz)
            for (name, node), (rx, ry, mz) in best.items():
                out[key].append(dict(base=node, name=name, P=ry * 1000, M=abs(mz) / 12 * 1000, V=abs(rx) * 1000,
                                     wt_factor=fac.get(name, {}).get("D")))
            out["bases"] = sorted({r["base"] for r in out[key]} | set(out["bases"]))
        else:
            for name, b in sheet.base.items():
                if b["Mx"] and b["My"]:
                    out["messages"].append(f"{name}: the column has moment about both axes; a footing with moment "
                                           "about one axis cannot take it")
                ax = "y" if b["My"] > b["Mx"] else "x"
                out[key].append(dict(base="base", name=name, P=b["P"] * 1000, M=b["M" + ax] * 1000,
                                     V=max(b["Vx"], b["Vy"]) * 1000, wt_factor=fac.get(name, {}).get("D")))
            out["bases"] = ["base"]
    return out


def job_of(project):
    return dict(name=(project.get("name") or "").strip(), number=(project.get("number") or "").strip(),
                address=(project.get("address") or "").strip())


def _row(r):
    return dict(check=r.check, combo=r.combo, demand=r.demand, capacity=r.capacity, unit=r.unit,
                dc=r.dc, status=r.status, source=r.source, note=r.note)


def results(kind, values, project):
    """What the screen shows for one member. Never raises: problems come back as messages."""
    try:
        sheet, pk, kw = build(kind, values, project)
    except Missing as e:
        return dict(state="incomplete", messages=e.items)
    except (WorksheetError, SteelInputError, FootingInputError, ValueError, KeyError) as e:
        return dict(state="stopped", messages=[str(e).strip("'").strip('"')])
    out = dict(state="done", rows=[], members=[], steps=[], assumptions=[], not_checked=[])
    if pk == "frame":
        out["members"] = [dict(member=m["member"], shape=m["shape"], combo=m["combo"] + (" *" if m["label"] else ""),
                               axial=m["Pr"], sense="C" if m["axial"] == "compression" else "T", moment=m["Mr"],
                               shear=m["Vr"], ratio=m["ratio"], status=m["status"]) for m in sheet.member_rows]
        out["rows"] = [_row(r) for r in sheet.rows]
        out["governing"] = sheet.governing
        lay = sheet.lay
        out["frame"] = dict(nodes=lay.nodes, supports=lay.supports,
                            members=[dict(name=m.name, i=m.i, j=m.j, role=m.role) for m in lay.members])
    else:
        out["rows"] = [_row(r) for r in sheet.rows]
    steps = getattr(sheet, "steps", None) or []
    out["steps"] = [dict(label=s.label, value=s.value, unit=s.unit, source=s.source, note=s.note) for s in steps]
    out["assumptions"] = list(getattr(sheet, "assumptions", None) or [])
    res = getattr(sheet, "result", None)
    if res is not None:
        out["assumptions"] += list(res.notes)
        out["not_checked"] = list(res.not_checked)
    else:
        out["not_checked"] = list(getattr(sheet, "not_checked", None) or [])
    ok = all(r["status"] == "OK" for r in out["rows"]) and all(m["status"] == "OK" for m in out["members"])
    out["status"] = "OK" if ok else "FLAG"
    return out


def sheet_pdf(kind, values, project, path):
    sheet, pk, kw = build(kind, values, project)
    fn = {"steel_beam": calcsheet.steel_beam_pdf, "steel_column": calcsheet.steel_column_pdf,
          "footing": calcsheet.footing_pdf, "frame": calcsheet.frame_pdf, "conn": calcsheet.conn_pdf,
          "simple": calcsheet.simple_pdf}[pk]
    fn(sheet, path, job_of(project), FORMS[kind]["code"], project.get("date") or "", **kw)
    return path


def package_pdf(project, members, path, cover=True):
    """Every member that calculates, in the order listed, behind a cover sheet.
    Returns (sheets, skipped marks)."""
    items, skipped, contents, flag_lines, codes = [], [], [], [], []
    for m in members:
        try:
            sheet, pk, kw = build(m["kind"], m["values"], project)
        except Exception:
            skipped.append((m["values"].get("mark") or "(no mark)"))
            continue
        code = FORMS[m["kind"]]["code"]
        items.append((pk, sheet, code, kw))
        if code not in codes:
            codes.append(code)
        mark = m["values"].get("mark")
        flags = 0
        for r in getattr(sheet, "rows", []):
            if r.status == "FLAG":
                flags += 1
                flag_lines.append(f"{mark}: {r.check}, D/C {r.dc:.2f} ({r.combo})")
        for r in getattr(sheet, "member_rows", []):
            if r["status"] == "FLAG":
                flags += 1
                flag_lines.append(f"{mark}: member {r['member']} ({r['shape']}), ratio {r['ratio']:.2f} ({r['combo']})")
        contents.append(dict(mark=mark, title=FORMS[m["kind"]]["title"], code=code, flags=flags))
    if not items:
        raise WorksheetError("no member is complete yet, so there is nothing to print")
    cov = None
    if cover:
        def lst(key):
            return [(c["expr"].strip(), (c.get("source") or "").strip()) for c in project.get(key) or []
                    if (c.get("expr") or "").strip()]
        asd, lrfd = lst("combos_asd"), lst("combos_lrfd")
        if not asd and not lrfd and project.get("combos"):
            (asd if project.get("method") == "ASD" else lrfd).extend(lst("combos"))
        names = {"AISC 360-22": "ANSI/AISC 360-22, Specification for Structural Steel Buildings",
                 "ACI 318-19": "ACI 318-19, Building Code Requirements for Structural Concrete"}
        basis = [names.get(c, c) for c in codes]
        if "AISC 360-22" in codes:
            basis.append(f"Steel is designed by {project.get('method')}. Section properties are from the AISC Shapes "
                         "Database v16.0.")
        basis.append("Load combinations are entered by the engineer with their source and are listed below. "
                     "Loads on each member are entered by the engineer; each sheet lists them.")
        basis.append("Each sheet states its own assumptions and what it does not check.")
        cov = dict(basis=basis, asd=asd, lrfd=lrfd, contents=contents, flag_lines=flag_lines, skipped=skipped)
    n = calcsheet.package_pdf(items, path, job_of(project), project.get("date") or "", cover=cov)
    return n, skipped
