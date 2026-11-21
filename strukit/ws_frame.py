"""Steel moment frame worksheet: a plane frame of any shape, from loads to member checks.

Layouts (one bay or many, one story or many, flat, gable or single-slope roof) are
starting points that build the joints and members; the analysis underneath is the
general engine in frame2d.py, so every shape gets the same calculation.

Stability by the direct analysis method, AISC 360-22 Chapter C:
  C2.1    second-order analysis with P-Delta and P-delta effects (frame2d.py);
  C2.1(d) for ASD the analysis runs at 1.6 times the loads, results divided by 1.6;
  C2.2b   notional loads 0.002 alpha Y at each level: in both directions for
          gravity-only combinations; added to the lateral load when the second-order
          drift exceeds 1.7 times the first-order drift;
  C2.3    all stiffness x 0.8, and x tau_b on the bending stiffness of any member with
          alpha Pr / Pns over 0.5;
  C3      effective length = unbraced length (K = 1).
Member checks: compression E3, tension yielding D2, bending F2 / F3, shear G2.1,
combined H1-1. Members are I-shapes with their webs in the plane of the frame.

Units at this level: feet, kips, kip/ft, ksi. Moments reported in kip-ft.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from . import frame2d, shapes, steel_beam, steel_beamcol, steel_column
from .ws_steel_beam import Row, WorksheetError

E = steel_beam.E_STEEL
NOT_CHECKED = ["connections (beam-to-column moment connections, base plates, anchor rods)",
               "column panel zones and stiffeners (AISC 360-22 J10)",
               "tension rupture at connections (D2(b))", "footings",
               "loads and bending out of the plane of the frame",
               "seismic detailing (AISC 341)"]


@dataclass
class FMember:
    name: str
    role: str                    # column, beam, rafter
    i: str
    j: str
    shape: str
    level: int                   # level the member belongs to (columns: level at their top)
    length_ft: float = 0.0


@dataclass
class Layout:
    nodes: dict                  # name -> (x_ft, y_ft)
    members: list
    supports: dict               # node -> pin / fixed
    levels: dict                 # level -> list of node names on column lines at that level
    description: str = ""

    def names(self, on):
        """Member names for a load target: a member name, a list, "beams", "rafters",
        "columns", or "level:2" (beams and rafters at level 2)."""
        if isinstance(on, (list, tuple)):
            return list(on)
        if on in ("beams", "rafters", "columns"):
            role = on[:-1]
            out = [m.name for m in self.members if m.role == role]
        elif isinstance(on, str) and on.startswith("level:"):
            lv = int(on.split(":")[1])
            out = [m.name for m in self.members if m.role != "column" and m.level == lv]
        else:
            out = [m.name for m in self.members if m.name == on]
        if not out:
            raise WorksheetError(f"frame: no members match '{on}'")
        return out


def layout(bays_ft, stories_ft, base, col_shape, beam_shape, roof="flat", rise_ft=0.0,
           rafter_shape=None, shape_of=None):
    """Build a frame. bays_ft: bay widths left to right. stories_ft: story heights
    bottom to top (to the eave for a sloped roof). base: "pin" or "fixed".
    roof: "flat", "gable" (ridge at mid-width, rise_ft above the eave) or "mono"
    (rising rise_ft from the left eave to the right eave); the roof shape applies to
    the top level. shape_of: member name -> shape, to override a member's section.
    Names: joints N<line>-<level>, columns C<line>-<story>, floor beams B<bay>-<level>,
    rafters R<n> left to right."""
    if base not in ("pin", "fixed"):
        raise WorksheetError("frame: base must be pin or fixed")
    if roof not in ("flat", "gable", "mono"):
        raise WorksheetError("frame: roof must be flat, gable or mono")
    if roof != "flat" and rise_ft <= 0:
        raise WorksheetError("frame: a sloped roof needs rise_ft")
    if not bays_ft or not stories_ft or min(bays_ft) <= 0 or min(stories_ft) <= 0:
        raise WorksheetError("frame: give at least one bay width and one story height")
    shape_of = shape_of or {}
    xs = [0.0]
    for b in bays_ft:
        xs.append(xs[-1] + b)
    W, top = xs[-1], len(stories_ft)
    ys = [0.0]
    for h in stories_ft:
        ys.append(ys[-1] + h)

    def roof_y(x):
        if roof == "gable":
            return ys[-1] + rise_ft * (1 - abs(x - W / 2) / (W / 2))
        if roof == "mono":
            return ys[-1] + rise_ft * x / W
        return ys[-1]

    nodes, members, levels = {}, [], {}
    for k, x in enumerate(xs, 1):
        for lv in range(top + 1):
            nodes[f"N{k}-{lv}"] = (x, roof_y(x) if lv == top else ys[lv])
            levels.setdefault(lv, []).append(f"N{k}-{lv}")
    for k in range(1, len(xs) + 1):
        for lv in range(1, top + 1):
            nm = f"C{k}-{lv}"
            members.append(FMember(nm, "column", f"N{k}-{lv - 1}", f"N{k}-{lv}", shape_of.get(nm, col_shape), lv))
    for lv in range(1, top):
        for b in range(1, len(xs)):
            nm = f"B{b}-{lv}"
            members.append(FMember(nm, "beam", f"N{b}-{lv}", f"N{b + 1}-{lv}", shape_of.get(nm, beam_shape), lv))
    # top level: beams, or rafters broken at the ridge
    pts = [(f"N{k}-{top}", x) for k, x in enumerate(xs, 1)]
    if roof == "gable" and not any(abs(x - W / 2) < 1e-9 for x in xs):
        nodes["RIDGE"] = (W / 2, roof_y(W / 2))
        pts = sorted(pts + [("RIDGE", W / 2)], key=lambda t: t[1])
    for n, (a, b) in enumerate(zip(pts[:-1], pts[1:]), 1):
        if roof == "flat":
            nm, role, shp = f"B{n}-{top}", "beam", beam_shape
        else:
            nm, role, shp = f"R{n}", "rafter", rafter_shape or beam_shape
        members.append(FMember(nm, role, a[0], b[0], shape_of.get(nm, shp), top))
    for m in members:
        (x1, y1), (x2, y2) = nodes[m.i], nodes[m.j]
        m.length_ft = math.hypot(x2 - x1, y2 - y1)
    desc = (f"{len(bays_ft)} bay{'s' if len(bays_ft) > 1 else ''} ({', '.join(f'{b:g}' for b in bays_ft)} ft), "
            f"{top} stor{'ies' if top > 1 else 'y'} ({', '.join(f'{h:g}' for h in stories_ft)} ft), "
            + {"flat": "flat roof", "gable": f"gable roof rising {rise_ft:g} ft to the ridge",
               "mono": f"single-slope roof rising {rise_ft:g} ft"}[roof] + f", {base}ned bases".replace("fixedned", "fixed"))
    return Layout(nodes, members, {f"N{k}-0": base for k in range(1, len(xs) + 1)}, levels, desc)


@dataclass
class FrameSheet:
    mark: str
    lay: Layout
    Fy: float
    method: str
    loads: list
    leaning: list
    combos: list
    member_rows: list = field(default_factory=list)   # one dict per member (worst combination)
    rows: list = field(default_factory=list)          # frame-level checks (drift)
    steps: list = field(default_factory=list)         # detailed lines for the governing member
    governing: dict = field(default_factory=dict)     # member, combo
    diagram: dict = field(default_factory=dict)       # member -> (s, M) for the governing combination
    reactions: dict = field(default_factory=dict)     # combo -> node -> (Rx, Ry, Mz), at design level
    assumptions: list = field(default_factory=list)
    not_checked: list = field(default_factory=lambda: list(NOT_CHECKED))
    brace: dict = field(default_factory=dict)

    @property
    def ok(self):
        return all(r["status"] == "OK" for r in self.member_rows) and all(r.status == "OK" for r in self.rows)


def _cb_arrays(s, M, a, b):
    """Eq. F1-1 on the unbraced segment a..b of a member's moment diagram."""
    q = [abs(float(np.interp(a + (b - a) * k, s, M))) for k in (0.25, 0.5, 0.75)]
    seg = (s >= a - 1e-9) & (s <= b + 1e-9)
    Mmax = float(np.max(np.abs(M[seg]))) if seg.any() else 0.0
    return steel_beam.cb_factor(Mmax, *q), Mmax


def run(mark, lay, Fy, loads, combos, method, include_self_weight, unbraced_ft, leaning=(),
        drift_checks=(), self_weight_case="D"):
    """loads: dicts, one of
         dict(case, on=<target>, w=<kip/ft>, kind="projected"|"length", dir="gravity"|"x")
         dict(case, node=<joint>, Fx=<kips>, Fy=<kips>)        (Fy negative is downward)
         dict(case, level=<n>, Fx=<kips>)                      (lateral load at a level)
    leaning: dict(case, level, P) - gravity load on columns that are not part of the frame
       but depend on it to stay upright, entered at the level where it is applied.
    unbraced_ft: member name, or "columns" / "beams" / "rafters", -> spacing of bracing
       out of the plane of the frame (used for weak-axis buckling and lateral-torsional
       buckling). Every member must be covered; nothing is assumed.
    drift_checks: DeflCheck(label, factors, ratio, source): story drift under service
       loads, limit story height / ratio."""
    if method not in ("ASD", "LRFD"):
        raise WorksheetError("method must be ASD or LRFD")
    if not combos:
        raise WorksheetError(f"{mark}: no load combinations given")
    if include_self_weight not in (True, False):
        raise WorksheetError(f"{mark}: say whether self-weight is included (True or False)")
    alpha = 1.0 if method == "LRFD" else 1.6
    props = {m.name: shapes.get(m.shape) for m in lay.members}
    brace = {}
    for m in lay.members:
        v = unbraced_ft.get(m.name, unbraced_ft.get(m.role + "s"))
        if v is None or v <= 0:
            raise WorksheetError(f"{mark}: no out-of-plane unbraced length given for {m.name} "
                                 f"(give it by name or for all {m.role}s)")
        brace[m.name] = min(v, m.length_ft)
    loads = list(loads)
    assumptions = ["Members are I-shapes with their webs in the plane of the frame (in-plane bending "
                   "is about the strong axis). Beam-to-column joints are rigid; "
                   + ("column bases are pinned." if "pin" in lay.supports.values() else "column bases are fixed.")]
    if include_self_weight:
        for m in lay.members:
            loads.append(dict(case=self_weight_case, on=m.name, w=props[m.name]["W"] / 1000.0, kind="length",
                              auto=True))
        assumptions.append(f"Member self-weight ({shapes.SOURCE}) added to load case {self_weight_case}.")
    else:
        assumptions.append("Member self-weight is NOT added separately; it is taken as included in the loads entered.")
    top = max(lay.levels)
    level_of_node = {n: lv for lv, ns in lay.levels.items() for n in ns}
    if "RIDGE" in lay.nodes:
        level_of_node["RIDGE"] = top
    mem = {m.name: m for m in lay.members}

    # ---- the analysis model (inches, kips) ----
    def model(extra_lean):
        f = frame2d.Frame()
        for n, (x, y) in lay.nodes.items():
            f.node(n, x * 12, y * 12)
        for m in lay.members:
            p = props[m.name]
            f.member(m.name, m.i, m.j, E, p["A"], p["Ix"])
        for n, kind in lay.supports.items():
            f.support(n, kind)
        if extra_lean:                                   # one stack of pinned leaning columns
            xr = max(x for x, _ in lay.nodes.values()) * 12 + 120.0
            f.node("LEAN-0", xr, 0.0); f.support("LEAN-0", "pin")
            for lv in range(1, top + 1):
                y = lay.nodes[lay.levels[lv][-1]][1] * 12
                f.node(f"LEAN-{lv}", xr, y)
                f.member(f"LEANCOL-{lv}", f"LEAN-{lv - 1}", f"LEAN-{lv}", E, 1.0e3, 1.0e3, pin_i=True, pin_j=True)
                f.member(f"LEANLINK-{lv}", lay.levels[lv][-1], f"LEAN-{lv}", E, 1.0e3, 1.0, pin_i=True, pin_j=True)
        return f

    has_lean = bool(leaning)
    fr = model(has_lean)

    def build(factors, scale):
        """Joint and member loads for a combination, and the gravity load at each level."""
        nl, ml, Y, lateral = {}, [], {lv: 0.0 for lv in range(1, top + 1)}, False

        def add(n, fx, fy):
            a = nl.get(n, (0.0, 0.0, 0.0))
            nl[n] = (a[0] + fx, a[1] + fy, 0.0)

        for ld in loads:
            f = factors.get(ld["case"], 0.0) * scale
            if f == 0:
                continue
            if "on" in ld:
                for name in lay.names(ld["on"]):
                    m = mem[name]
                    w = f * ld["w"] / 12.0
                    kind = ld.get("kind", "length")
                    if ld.get("dir", "gravity") == "x":
                        ml.append((name, w, 0.0, "length")); lateral = True
                    else:
                        ml.append((name, 0.0, -w, kind))
                        (x1, y1), (x2, y2) = lay.nodes[m.i], lay.nodes[m.j]
                        run_ft = abs(x2 - x1) if kind == "projected" else m.length_ft
                        Y[m.level] += f * ld["w"] * run_ft
            elif "node" in ld:
                if ld["node"] not in lay.nodes:
                    raise WorksheetError(f"{mark}: load on joint {ld['node']}, which is not in the frame")
                add(ld["node"], f * ld.get("Fx", 0.0), f * ld.get("Fy", 0.0))
                lateral = lateral or bool(ld.get("Fx"))
                lv = level_of_node.get(ld["node"], top)
                if lv:
                    Y[lv] += -f * ld.get("Fy", 0.0)
            elif "level" in ld:
                add(lay.levels[ld["level"]][0], f * ld["Fx"], 0.0); lateral = True
            else:
                raise WorksheetError(f"{mark}: a load needs 'on', 'node' or 'level'")
        for ld in leaning:
            f = factors.get(ld["case"], 0.0) * scale
            if f:
                add(f"LEAN-{ld['level']}", 0.0, -f * ld["P"])
                Y[ld["level"]] += f * ld["P"]
        return nl, ml, Y, lateral

    def with_notional(nl, Y, sign):
        out = dict(nl)
        for lv, y in Y.items():
            n = lay.levels[lv][0]
            a = out.get(n, (0.0, 0.0, 0.0))
            out[n] = (a[0] + sign * 0.002 * y, a[1], a[2])        # Y already carries alpha
        return out

    def drift(res):
        d = {0: 0.0}
        for lv in range(1, top + 1):
            d[lv] = float(np.mean([res.disp[n][0] for n in lay.levels[lv]]))
        return {lv: d[lv] - d[lv - 1] for lv in range(1, top + 1)}

    def analyse(nl, ml, tau):
        try:
            r1 = fr.solve(nl, ml, stiffness_factor=0.8, flexural_factors=tau)
            r2 = fr.solve(nl, ml, stiffness_factor=0.8, flexural_factors=tau, second_order=True)
        except frame2d.FrameError as e:
            raise WorksheetError(f"{mark}: {e}")
        d1, d2 = drift(r1), drift(r2)
        ratio = {lv: (abs(d2[lv] / d1[lv]) if abs(d1[lv]) > 1e-9 else 1.0) for lv in d1}
        return r1, r2, ratio

    cases, notes_ratio = [], {}
    for cb in combos:
        nl, ml, Y, lateral = build(cb.factors, alpha)
        if not nl and not ml:
            raise WorksheetError(f"{mark}: combination {cb.name} has no load")
        variants = [(+1, "notional load to the right"), (-1, "notional load to the left")] if not lateral \
            else [(0, "")]
        for sign, label in variants:
            tau = {}
            for _ in range(4):                                     # settle tau_b (C2.3(b))
                nlv = with_notional(nl, Y, sign) if sign else nl
                r1, r2, ratio = analyse(nlv, ml, tau)
                if lateral and max(ratio.values()) > 1.7 and sign == 0:
                    tot = sum(v[0] for v in nl.values()) + sum(w[1] for w in ml)
                    sign, label = (1 if tot >= 0 else -1), "notional load added to the lateral load (drift ratio over 1.7)"
                    continue
                new = {}
                for m in lay.members:
                    Pr = max(0.0, -r2.members[m.name].N_min)       # at alpha level already
                    rr = Pr / (Fy * props[m.name]["A"])
                    if rr > 0.5:
                        new[m.name] = 4 * rr * (1 - rr)
                if all(abs(new.get(k, 1.0) - tau.get(k, 1.0)) < 1e-3 for k in set(new) | set(tau)):
                    break
                tau = new
            cases.append(dict(combo=cb.name, label=label, r1=r1, r2=r2, ratio=ratio, tau=tau, Y=Y,
                              notional=bool(sign)))

    sheet = FrameSheet(mark, lay, Fy, method, loads, list(leaning), list(combos), brace=brace,
                       assumptions=assumptions)
    # ---- member checks: worst combination for each member ----
    worst_overall = None
    for m in lay.members:
        p = props[m.name]
        L_in = m.length_ft * 12
        Lb = brace[m.name]
        col = steel_column.check(p, Fy, L_in, Lb * 12, method=method)           # K = 1 (C3)
        Pt = (0.90 if method == "LRFD" else 1 / 1.67) * Fy * p["A"]              # D2-1
        best = None
        for cs in cases:
            mr = cs["r2"].members[m.name]
            s_ft, M = mr.s / 12.0, mr.M / alpha / 12.0                           # kip-ft
            N = mr.N / alpha
            Pc_c, Pt_r = max(0.0, -float(np.min(N))), max(0.0, float(np.max(N)))
            nseg = max(1, int(math.ceil(m.length_ft / Lb - 1e-9)))
            cand = []
            for k in range(nseg):
                a, b = k * Lb, min((k + 1) * Lb, m.length_ft)
                Cb, Mseg = _cb_arrays(s_ft, M, a, b)
                fl = steel_beam.check(p, Fy, (b - a) * 12, Cb, method)
                cand.append((Mseg * 12 / fl.M_avail, Mseg, fl, Cb, b - a))
            _, Mr, fl, Cb, Lseg = max(cand, key=lambda t: t[0])
            if Pc_c >= Pt_r:
                val, eq = steel_beamcol.interaction(Pc_c, col.P_avail, Mr * 12, fl.M_avail)
                Pr, Pc, kind = Pc_c, col.P_avail, "compression"
            else:
                val, eq = steel_beamcol.interaction(Pt_r, Pt, Mr * 12, fl.M_avail)
                Pr, Pc, kind = Pt_r, Pt, "tension"
            Vr = mr.V_abs_max / alpha
            one = dict(member=m.name, role=m.role, shape=shapes.normalize(m.shape), combo=cs["combo"],
                       label=cs["label"], Pr=Pr, Pc=Pc, axial=kind, Mr=Mr, Mc=fl.M_avail / 12, Vr=Vr,
                       Vc=fl.V_avail, ratio=max(val, Vr / fl.V_avail), combined=val, eq=eq, Cb=Cb, Lb=Lseg,
                       fl=fl, col=col, case=cs, tau=cs["tau"].get(m.name, 1.0), length_ft=m.length_ft)
            if best is None or one["ratio"] > best["ratio"]:
                best = one
        best["status"] = "OK" if best["ratio"] <= 1.0 else "FLAG"
        sheet.member_rows.append(best)
        if worst_overall is None or best["ratio"] > worst_overall["ratio"]:
            worst_overall = best
    g = worst_overall
    sheet.governing = dict(member=g["member"], combo=g["combo"], label=g["label"])
    cs = g["case"]
    sheet.diagram = {m.name: (cs["r2"].members[m.name].s / 12.0, cs["r2"].members[m.name].M / alpha / 12.0)
                     for m in lay.members}
    for c in cases:
        key = c["combo"] + (f" ({c['label']})" if c["label"] else "")
        sheet.reactions[key] = {n: tuple(v / alpha for v in c["r2"].reactions[n]) for n in lay.supports}
    # ---- frame-level rows ----
    for lv in range(1, top + 1):
        c = max(cases, key=lambda t: t["ratio"][lv])
        sheet.rows.append(Row(f"drift amplification, story {lv}", c["combo"], c["ratio"][lv], 2.5, "",
                              "AISC 360-22 Commentary C1 (recommended limit, not a requirement)",
                              "second-order story drift divided by first-order; stiffness x 0.8, loads x "
                              f"{alpha:g}" + (f"; {c['label']}" if c["label"] else "")))
    for dc in drift_checks:
        nl, ml, _, _ = build(dc.factors, 1.0)
        if not nl and not ml:
            continue
        r = fr.solve(nl, ml)
        d = drift(r)
        for lv in range(1, top + 1):
            h = (lay.nodes[lay.levels[lv][0]][1] - lay.nodes[lay.levels[lv - 1][0]][1]) * 12
            sheet.rows.append(Row(f"story drift, {dc.label}, story {lv}", "+".join(
                (f"{f:g}" if f != 1 else "") + cc for cc, f in dc.factors.items()), abs(d[lv]), h / dc.ratio,
                "in", dc.source, f"limit story height / {dc.ratio:g}; first-order, full stiffness"))
    if not drift_checks:
        sheet.not_checked.append("story drift under service load (no limit entered)")
    # ---- detailed lines for the governing member ----
    L = sheet.steps
    Line = steel_beam.Line
    L.append(Line(f"member {g['member']} ({g['shape']}), length", g["length_ft"], "ft", "layout",
                  f"combination {g['combo']}" + (f", {g['label']}" if g["label"] else "")))
    L.append(Line("tau_b", g["tau"], "", "Eq. C2-2a" if g["tau"] == 1.0 else "Eq. C2-2b",
                  "analysis stiffness = 0.8 tau_b E I (Sect. C2.3)"))
    if g["axial"] == "compression":
        L += g["col"].lines
    else:
        L.append(Line("Pt = Fy Ag, available", g["Pc"], "kip", "Eq. D2-1; phi_t = 0.90, Omega_t = 1.67"))
    L.append(Line(f"Pr, axial {g['axial']}", g["Pr"], "kip", "second-order analysis"))
    L += [ln for ln in g["fl"].lines if ln.label[:2] in ("Mp", "Lp", "Lr", "Mn")]
    L.append(Line("Mr, second-order", g["Mr"], "kip-ft", "Sect. C2.1(b), C2.1(d)",
                  f"Lb = {g['Lb']:g} ft, Cb = {g['Cb']:.2f}"))
    L.append(Line("Vr", g["Vr"], "kip", "second-order analysis", f"available {g['Vc']:.1f} kip (Sect. G2.1)"))
    L.append(Line("combined ratio", g["combined"], "", g["eq"], "limit 1.0"))
    sheet.assumptions.append(
        "Stability by the direct analysis method (AISC 360-22 Chapter C): second-order analysis "
        "including P-Delta and P-delta effects; all stiffness x 0.8 (C2.3); notional loads 0.002 Y at "
        "each level, both directions, in combinations without lateral load (C2.2b), applied at the "
        "left joint of the level; K = 1.0 (C3)."
        + (" For ASD the analysis is run at 1.6 times the loads and the results divided by 1.6 "
           "(C2.1(d))." if method == "ASD" else ""))
    return sheet
