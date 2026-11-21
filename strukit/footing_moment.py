"""Isolated footing with moment about one axis (a column base that carries moment, such
as a cantilevered column or a fixed-base frame column).

The moment acts in the x direction (soil pressure varies along the width B). Several
service and factored load cases can be given; each check reports its worst case.

Soil pressure is plain statics: a rigid footing on soil that takes no tension, so the
pressure is a straight line, a trapezoid when the resultant is inside the middle third and
a triangle over part of the footing when it is outside. The concrete checks are
ACI 318-19 (on file), as for the centred footing in footing.py, with the soil pressure
integrated where it is not uniform, and with the moment transferred by shear in the
two-way shear check:
  13.2.6.3   strength from the soil pressure caused by the factored loads (the factored
             weight of the footing and soil is included in locating the pressure and then
             taken off, since it loads the footing from above);
  13.3.3.1   two-way isolated footings follow Chapters 7 and 8;
  8.4.2.2.2  gamma_f; 8.4.4.2.2 gamma_v = 1 - gamma_f; 8.4.4.2.3 with R8.4.4.2.3 for Jc.

Not covered: moment about both axes, top reinforcement where part of the footing lifts
off the soil, development and anchorage of the column into the footing, sliding and
overturning unless their limits are entered.

Validation: reduces exactly to footing.check when the moment is zero; soil pressures,
shears and moments checked against hand statics in tests/test_footing_moment.py. No
published worked example of a footing with moment is on file.

Units: lb, lb-ft for moments in the arguments, inches and psi inside.
"""
import math

import numpy as np

from . import footing
from .footing import Check, FootingInputError, FootingResult

NOT_CHECKED = ["moment about the other axis (biaxial)", "bar development length (ACI 318-19 13.2.8, 25.4)",
               "bar spacing limits (ACI 318-19 8.7.2)",
               "anchorage of the column to the footing for the moment (dowels, anchor rods)"]


def pressure(P, M, B, L):
    """Soil pressure under a rigid footing B x L carrying P at eccentricity e = M / P along
    B, no tension. Returns (function q(x) with x from the centre, e, bearing length).
    Units follow the arguments (force / length^2)."""
    if P <= 0:
        raise FootingInputError("footing: no downward load on the soil (uplift)")
    e = M / P
    if abs(e) >= B / 2:
        raise FootingInputError("footing: the resultant falls outside the footing (it overturns)")
    s = 1.0 if e >= 0 else -1.0
    if abs(e) <= B / 6:
        def q(x):
            return P / (B * L) * (1 + 12 * e * np.asarray(x, float) / B ** 2)
        return q, e, B
    a = 3 * (B / 2 - abs(e))
    qmax = 2 * P / (L * a)

    def q(x):
        t = (s * np.asarray(x, float) - (B / 2 - a)) / a          # 0 at the end of bearing, 1 at the toe
        return qmax * np.clip(t, 0.0, None)
    return q, e, a


def check_eccentric(B_ft, L_ft, h_in, fc, fy, col_x_in, col_y_in, bar, n_x, n_y, cover_in,
                    q_allow_psf, conc_pcf, service, strength, plate_x_in=None, plate_y_in=None,
                    bottom_layer="x", soil_depth_ft=0.0, soil_pcf=0.0, lam=1.0,
                    ot_required=None, slide_mu=None, slide_required=None):
    """service: list of dict(name, P, M, V); strength: list of dict(name, P, M, V, wt_factor).
    P is the column load (lb, downward), M the moment at the top of the footing (lb-ft,
    about the axis parallel to L), V the horizontal force at the top of the footing (lb, in
    the direction that adds to M). wt_factor is the dead-load factor of that combination,
    applied to the footing and soil weight. ot_required and slide_required are the required
    safety factors against overturning and sliding (from the building code or the soils
    report); slide_mu is the friction coefficient between footing and soil."""
    if not service or not strength:
        raise FootingInputError("footing: give at least one service case and one factored case")
    for c in service:
        for k in ("name", "P", "M", "V"):
            if c.get(k) is None:
                raise FootingInputError(f"footing: a service case is missing '{k}'")
    for c in strength:
        for k in ("name", "P", "M", "V", "wt_factor"):
            if c.get(k) is None:
                raise FootingInputError(f"footing: a factored case is missing '{k}'")
    if (slide_mu is None) != (slide_required is None):
        raise FootingInputError("footing: sliding needs both the friction coefficient and the required safety factor")
    # the centred check supplies the section data, capacities, minimum steel and bearing
    Pmax_s = max(c["P"] for c in service)
    worst_u = max(strength, key=lambda c: c["P"])
    base = footing.check(B_ft, L_ft, h_in, fc, fy, col_x_in, col_y_in, bar, n_x, n_y, cover_in,
                         Pmax_s, "-", worst_u["P"], worst_u["name"], q_allow_psf, conc_pcf,
                         plate_x_in, plate_y_in, bottom_layer, soil_depth_ft, soil_pcf, lam)
    v = dict(base.values)
    B, L = B_ft * 12, L_ft * 12
    d = {"x": v["d_x"], "y": v["d_y"]}
    d_avg = v["d_avg"]
    if plate_x_in:
        half = {"x": (col_x_in + plate_x_in) / 4, "y": (col_y_in + plate_y_in) / 4}
        load_x, load_y = plate_x_in, plate_y_in
    else:
        half = {"x": col_x_in / 2, "y": col_y_in / 2}
        load_x, load_y = col_x_in, col_y_in
    W = v["W_ftg"] + v["W_soil"]                                    # lb
    checks, notes, not_checked = [], [], list(NOT_CHECKED)

    # ---- service: soil pressure, overturning, sliding ----
    worst = None
    ot = sl = None
    for c in service:
        Pt = c["P"] + W
        Mb = abs(c["M"]) * 12 + abs(c["V"]) * h_in                  # lb-in at the underside
        q, e, a = pressure(Pt, Mb, B, L)
        qmax = float(q(B / 2)) * 144
        if worst is None or qmax > worst[0]:
            worst = (qmax, c, e, a, float(q(-B / 2)) * 144)
        if Mb > 0:
            r = Pt * B / 2 / Mb
            if ot is None or r < ot[0]:
                ot = (r, c)
        if abs(c["V"]) > 0 and slide_mu is not None:
            r = slide_mu * Pt / abs(c["V"])
            if sl is None or r < sl[0]:
                sl = (r, c)
    qmax, c, e, a, qmin = worst
    kern = abs(e) <= B / 6 + 1e-12
    checks.append(Check("soil bearing pressure, maximum", qmax, q_allow_psf, "psf", c["name"],
                        "statics, linear pressure with no tension; ACI 318-19 13.3.1.1; allowable from the soils source",
                        f"column {c['P']:.0f} lb + footing and soil {W:.0f} lb; eccentricity {abs(e):.2f} in "
                        + (f"(inside the middle third, B/6 = {B / 6:.2f} in); minimum pressure {qmin:.0f} psf" if kern else
                           f"(outside the middle third, B/6 = {B / 6:.2f} in); soil bears on {a:.1f} in of the {B:.0f} in width")))
    v.update(q_max_psf=qmax, q_min_psf=qmin, e_service_in=abs(e), bearing_in=a)
    if not kern:
        notes.append("Under service load the resultant is outside the middle third: part of the footing "
                     "lifts off the soil. Many soils reports and codes limit this.")
    if ot is not None:
        if ot_required is not None:
            checks.append(Check("overturning", ot_required, ot[0], "", ot[1]["name"],
                                "statics; required safety factor as entered",
                                "demand is the required safety factor, capacity is the one provided "
                                "(resisting moment about the toe / overturning moment)"))
        else:
            notes.append(f"Safety factor against overturning is {ot[0]:.2f} ({ot[1]['name']}); no required value was "
                         "entered, so it is not checked.")
            not_checked.append("overturning (no required safety factor entered)")
    if sl is not None:
        checks.append(Check("sliding", slide_required, sl[0], "", sl[1]["name"],
                            f"statics; friction coefficient {slide_mu:g} and required safety factor as entered",
                            "demand is the required safety factor, capacity is the one provided; passive soil "
                            "pressure on the footing edge is not counted"))
    elif any(abs(c["V"]) > 0 for c in service):
        not_checked.append("sliding (no friction coefficient entered)")

    # ---- strength: integrate the net factored pressure ----
    xs = np.linspace(-B / 2, B / 2, 4001)
    trap = getattr(np, "trapezoid", None) or np.trapz
    res = {"v1x": None, "mx": None, "v1y": None, "my": None, "v2": None}
    lift = False
    for c in strength:
        Wf = c["wt_factor"] * W
        Pt = c["P"] + Wf
        Mb = abs(c["M"]) * 12 + abs(c["V"]) * h_in
        q, eu, au = pressure(Pt, Mb, B, L)
        net = q(xs) - Wf / (B * L)                                  # psi, upward on the footing
        lift = lift or bool(np.min(net) < -1e-9)

        def integ(a0, b0, arm_from=None):
            m = (xs >= a0 - 1e-9) & (xs <= b0 + 1e-9)
            y = net[m] if arm_from is None else net[m] * np.abs(xs[m] - arm_from)
            return float(trap(y, xs[m]))

        xs_, xc = half["x"] + d["x"], half["x"]
        v1x = L * max(abs(integ(xs_, B / 2)), abs(integ(-B / 2, -xs_))) if xs_ < B / 2 else 0.0
        mx = L * max(integ(xc, B / 2, xc), integ(-B / 2, -xc, -xc))            # lb-in, bottom in tension
        tot = integ(-B / 2, B / 2)                                             # lb per inch of length
        ys_, yc = half["y"] + d["y"], half["y"]
        v1y = max(L / 2 - ys_, 0.0) * tot
        my = (L / 2 - yc) ** 2 / 2 * tot
        b1, b2 = 2 * half["x"] + d_avg, 2 * half["y"] + d_avg
        two = None
        if b1 < B and b2 < L:
            bo = 2 * (b1 + b2)
            Vu = c["P"] - b2 * integ(-b1 / 2, b1 / 2)
            gf = 1 / (1 + (2 / 3) * math.sqrt(b1 / b2))
            gv = 1 - gf
            Jc = d_avg * b1 ** 3 / 6 + b1 * d_avg ** 3 / 6 + d_avg * b2 * b1 ** 2 / 2
            vu = Vu / (bo * d_avg) + gv * Mb * (b1 / 2) / Jc
            two = (vu, c, dict(Vu=Vu, gv=gv, Jc=Jc, bo=bo, b1=b1, b2=b2, Msc=Mb))
        for key, val in (("v1x", v1x), ("mx", mx), ("v1y", v1y), ("my", my)):
            if res[key] is None or val > res[key][0]:
                res[key] = (val, c, abs(eu), au)
        if two and (res["v2"] is None or two[0] > res["v2"][0]):
            res["v2"] = two
    if lift:
        notes.append("Under at least one factored case part of the footing lifts off the soil; the weight of "
                     "the footing and soil there bends it the other way.")
        not_checked.append("top reinforcement for the part of the footing that lifts off the soil")

    def cap(name):
        return base.get(name).capacity

    for ax, kv, km in (("x", "v1x", "mx"), ("y", "v1y", "my")):
        val, c, eu, au = res[kv]
        checks.append(Check(f"one-way shear, {ax} direction", val, cap(f"one-way shear, {ax} direction"), "lb", c["name"],
                            "ACI 318-19 Table 22.5.5.1(c), 22.5.5.1.1; phi = 0.75 (Table 21.2.1)",
                            f"section at d = {d[ax]:.2f} in from the critical section (Table 13.2.7.1); soil pressure "
                            f"from the factored loads, eccentricity {eu:.2f} in; size effect neglected per 13.2.6.2"))
        val, c, eu, au = res[km]
        checks.append(Check(f"flexure, {ax} direction", val / 12, cap(f"flexure, {ax} direction"), "lb-ft", c["name"],
                            "ACI 318-19 13.2.7.1, 22.2.2.4.1; phi = 0.90 (Table 21.2.2)",
                            "moment at the critical section from the factored soil pressure"
                            + (", heavier side" if ax == "x" else ", total across the width")))
        checks.append(base.get(f"minimum reinforcement, {ax} direction"))
    if res["v2"] is None:
        notes.append("two-way shear: the critical perimeter falls outside the footing, so punching does not apply")
    else:
        vu, c, t = res["v2"]
        beta = max(load_x, load_y) / min(load_x, load_y)
        vc = min(4, 2 + 4 / beta, 2 + 40 * d_avg / t["bo"]) * lam * math.sqrt(fc)
        checks.append(Check("two-way shear with moment transfer", vu, 0.75 * vc, "psi", c["name"],
                            "ACI 318-19 8.4.4.2, Eq. 8.4.2.2.2, 8.4.4.2.2, R8.4.4.2.3; Table 22.6.5.2; phi = 0.75",
                            f"Vu = {t['Vu']:.0f} lb on bo d = {t['bo']:.1f} x {d_avg:.3f} in; gamma_v = {t['gv']:.3f}; "
                            f"Msc = {t['Msc'] / 12:.0f} lb-ft (the full moment at the underside); Jc = {t['Jc']:.0f} in^4; "
                            f"vc = {vc:.1f} psi"))
    b = base.get("bearing on footing")
    checks.append(Check(b.name, b.demand, b.capacity, b.unit, b.combo, b.source,
                        b.note + "; axial load only, the moment is not included in this check"))
    return FootingResult(checks, v, notes, not_checked)
