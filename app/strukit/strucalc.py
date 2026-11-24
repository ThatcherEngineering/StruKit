"""Read a StruCalc project file (.vtx, the XML StruCalc Pro saves) and turn its members into StruKit members.

What comes across: steel floor beams of W, M, S, HP shapes, channels and HSS (simple or continuous spans, uniform and point loads in the
strong direction, bracing of the top flange, deflection limits, self-weight) and HSS or pipe columns with axial load and end moments.
Each member also carries StruCalc's own results (demand and strength of every check it printed), so the two programs can be put side by side.
Anything not carried across is listed in the notes, never dropped silently."""
import re
import xml.etree.ElementTree as ET
from fractions import Fraction

from . import loadcombos, shapes

CASE = {"Dead": "D", "Live": "L", "RoofLive": "Lr", "roofLive": "Lr", "Snow": "S", "Wind": "W", "wind": "W", "Seismic": "E", "seismic": "E", "Rain": "R"}


class StruCalcError(ValueError):
    pass


def _shape(grade):
    """'W8x15' -> 'W8X15'; 'HSS6x6x.375' -> 'HSS6X6X3/8'; 'HSS2-1/2x2-1/2x.250' -> 'HSS2-1/2X2-1/2X1/4'."""
    s = grade.strip().upper().replace(" ", "")
    if s.startswith("HSS"):
        parts = s[3:].split("X")
        if re.fullmatch(r"0?\.\d+", parts[-1]) and len(parts) == 3:
            f = Fraction(float(parts[-1])).limit_denominator(16)
            parts[-1] = f"{f.numerator}/{f.denominator}"
        s = "HSS" + "X".join(parts)
    return s


def _fy(steel_grade):
    m = re.search(r"-(\d+(?:\.\d+)?)\s*$", steel_grade or "")
    if not m:
        raise StruCalcError(f"cannot read the yield stress in steel grade '{steel_grade}'")
    return float(m.group(1))


def _num(e, tag, default=0.0):
    t = (e.findtext(tag) or "").strip()
    return float(t) if t else default


def _f(x):
    return f"{x:.6g}"


def convert(path):
    """Returns (data, notes): data is a StruKit project (format strukit-project) and notes lists, member by member, what was not carried across.
    data["strucalc"] maps each mark to StruCalc's own rows: list of dict(name, demand, strength, unit, combo, controls)."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise StruCalcError(f"not a StruCalc project file: {e}")
    d = root.find("Design")
    if d is None:
        raise StruCalcError("not a StruCalc project file: no Design section")
    proj = dict(name=(d.findtext("Name") or "").strip(), number="", address="", date="", method="ASD",
                combos_asd=[dict(c) for c in loadcombos.ASD], combos_lrfd=[dict(c) for c in loadcombos.LRFD])
    members, notes, theirs = [], [], {}
    for m in d.find("DesignModules"):
        mark = (m.findtext("Name") or "").strip()
        o = m.find("DesignModuleObjects/DesignModuleObject")
        kind = (m.findtext("designModuleType") or "").strip()
        mat, species, grade = ((o.findtext(t) or "").strip() for t in ("Material", "Species", "Grade"))
        theirs[mark] = [dict(name=(a.findtext("adequacyName") or "").strip(), demand=abs(_num(a, "adequacyMagnitude")), strength=_num(a, "adequacyStrength"),
                             unit=(a.findtext("adequacyMagnitudeLabel") or "").strip(), combo=(a.findtext("adequacyCombinationLabel") or "").strip(),
                             controls=(a.findtext("isControlling") or "") == "true") for a in m.findall("MyAdequacy/Adequacy")]
        if (m.findtext("calculationType") or "ASD").strip() != "ASD":
            notes.append(f"{mark}: designed by {(m.findtext('calculationType') or '').strip()} in StruCalc; StruKit project method is ASD")
        if mat != "Steel":
            notes.append(f"{mark}: {mat} {species} {grade} ({kind}) is not carried across by this reader yet")
            continue
        name = _shape(grade)
        lookup = None
        for get in (shapes.get, shapes.channel, shapes.hss):
            try:
                get(name); lookup = get; break
            except Exception:
                continue
        if lookup is None:
            notes.append(f"{mark}: section {grade} ({species}) is not a shape StruKit designs as a beam or column (W, M, S, HP, C, MC, HSS, pipe)")
            continue
        try:
            Fy = _fy(o.findtext("steelGrade"))
        except StruCalcError as e:
            notes.append(f"{mark}: {e}"); continue
        loads = m.findall("Loads/Load")
        sw = "yes" if (o.findtext("includeSelfWeight") or "").strip() == "True" else "no"
        if kind == "Column":
            sp = o.find("Spans/Span")
            H = _num(sp, "spanEnd") - _num(sp, "spanStart")
            ux, uy = _num(sp, "unbracedX", H) or H, _num(sp, "unbracedY", H) or H
            if lookup is not shapes.hss:
                notes.append(f"{mark}: steel column {grade}: only HSS and pipe columns are carried across by this reader"); continue
            P, Mo, skipped = [], [], []
            for l in loads:
                typ, case = (l.findtext("loadType") or "").strip(), CASE.get((l.findtext("combinationType") or "").strip())
                mag, ax = _num(l, "leftMag"), (l.findtext("loadAxis") or "").strip()
                if case is None:
                    skipped.append(f"{typ} load of type {(l.findtext('combinationType') or '').strip()}"); continue
                if typ == "Axial":
                    P.append(dict(case=case, P=_f(-mag / 1000.0), label=(l.findtext("loadName") or "").strip()))
                elif typ == "Moment":
                    Mo.append(dict(case=case, Mx=_f(abs(mag) / 1000.0) if ax == "Y" else "", My=_f(abs(mag) / 1000.0) if ax == "X" else "", label="end moment"))
                else:
                    skipped.append(f"{typ} load")
            if skipped:
                notes.append(f"{mark}: not carried across: " + "; ".join(skipped))
            # moments StruCalc holds at one end of the column only: the other end moment is zero, M1 / M2 = 0
            at = {round(_num(l, "loadStart"), 4) for l in loads if (l.findtext("loadType") or "").strip() == "Moment"}
            one_end = len(at) == 1 and (abs(next(iter(at)) - H) < 1e-6 or next(iter(at)) == 0)
            if Mo and not one_end:
                notes.append(f"{mark}: moments at more than one point of the column; entered with Cm = 1.0")
            members.append(dict(kind="hss_column", values=dict(end_ratio="0" if Mo and one_end else "", mark=mark, shape=name, Fy=_f(Fy), Fy_source=(o.findtext("steelGrade") or "").strip() + ", as in the StruCalc file",
                                                               height=_f(H), Kx=_f(ux / H), Ky=_f(uy / H),
                                                               k_source=f"unbraced lengths {ux:g} ft and {uy:g} ft with K = 1.0, as in the StruCalc file", self_weight=sw, loads=P, moments=Mo)))
            continue
        spans = o.findall("Spans/Span")
        ends = [_num(s, "spanEnd") for s in spans]
        lens = [b - a for a, b in zip([0.0] + ends[:-1], ends)]
        top = [_num(s, "unbracedTop") for s in spans]
        rx = sorted(((_num(x, "Location"), (x.findtext("verticalBoundaryCondition") or "0").strip() == "1") for x in m.findall("Reactions/Reaction")), key=lambda t: t[0])
        oh_l = oh_r = 0.0
        if rx and not rx[0][1] and len(lens) > 1:              # a free left end: the first span is an overhang
            oh_l, lens, top = lens[0], lens[1:], top[1:]
        if rx and not rx[-1][1] and len(lens) > 1:             # a free right end
            oh_r, lens, top = lens[-1], lens[:-1], top[:-1]
        out, skipped = [], []
        for l in loads:
            typ, case = (l.findtext("loadType") or "").strip(), CASE.get((l.findtext("combinationType") or "").strip())
            a, b, x1, x2 = _num(l, "leftMag"), _num(l, "rightMag"), _num(l, "loadStart"), _num(l, "loadEnd")
            ax, lab = (l.findtext("loadAxis") or "").strip(), (l.findtext("loadName") or "").strip()
            lab = "" if lab in ("Uniform", "Point") else lab
            if case is None or ax != "Y" or typ not in ("Uniform", "Point") or (typ == "Uniform" and a != b):
                skipped.append(f"{typ} load {a:g} ({(l.findtext('combinationType') or '').strip()}, axis {ax})"); continue
            if typ == "Uniform":
                full = x1 == 0 and abs(x2 - ends[-1]) < 1e-6
                out.append(dict(case=case, kind="uniform", mag=_f(a / 1000.0), x1="" if full else _f(x1), x2="" if full else _f(x2), label=lab))
            else:
                out.append(dict(case=case, kind="point", mag=_f(a / 1000.0), x1=_f(x1), x2="", label=lab))
        if skipped:
            notes.append(f"{mark}: not carried across: " + "; ".join(skipped))
        defl = []
        if _num(o, "liveLoadDeflection"):
            defl.append(dict(label="live", expr="L", ratio=_f(_num(o, "liveLoadDeflection")), source="as in the StruCalc file"))
        if _num(o, "totalLoadDeflection"):
            defl.append(dict(label="total", expr="D + L", ratio=_f(_num(o, "totalLoadDeflection")), source="as in the StruCalc file"))
        v = dict(mark=mark, shape=name, Fy=_f(Fy), span=_f(lens[0]), more_spans=", ".join(_f(x) for x in lens[1:]), oh_left=_f(oh_l) if oh_l else "", oh_right=_f(oh_r) if oh_r else "",
                 bracing="continuous" if all(t == 0 for t in top) else "at points", brace_pts="", self_weight=sw, loads=out, defl=defl)
        if v["bracing"] == "at points" and any(0 < t < ln - 1e-6 for t, ln in zip(top, lens)):
            notes.append(f"{mark}: top flange brace spacing {top} ft in StruCalc; entered as unbraced between supports")
        members.append(dict(kind="steel_beam", values=v))
    return dict(format="strukit-project", version=1, project=proj, members=members, strucalc=theirs), notes
