"""Crane loads on a runway beam, ASCE/SEI 7-22 Sect. 4.9 (read from the standard: 4.9.1 to 4.9.5), and the moving-load effects of a pair (or
row) of wheels on a simply supported runway beam by statics.

  Maximum wheel load: from the crane maker (bridge weight plus rated capacity plus trolley, trolley placed for the largest effect, 4.9.2).
  Vertical impact (4.9.3): powered monorail 25%; bridge crane service class D, E or F 25%; service class A, B or C 10%; hand-geared bridge,
  trolley and hoist 0%.
  Lateral force (4.9.4), electrically powered trolleys only: 20% of (rated capacity + hoist and trolley), at the traction surface, either
  direction, distributed with regard to the lateral stiffness of the runway beams and supporting structure (the share to this runway is
  entered with its basis), divided equally among the wheels on this runway.
  Longitudinal force (4.9.5), except hand-geared bridges: 10% of the maximum wheel loads, at the traction surface, either direction."""
import math


IMPACT = {"bridge crane, service class A, B or C": (0.10, "bridge crane service class A, B or C"),
          "bridge crane, service class D, E or F": (0.25, "bridge crane service class D, E or F"),
          "monorail crane (powered)": (0.25, "monorail cranes (powered)"),
          "hand-geared bridge, trolley and hoist": (0.0, "cranes with hand-geared bridge, trolley and hoist")}


class CraneError(ValueError):
    pass


def loads(kind, capacity, trolley, wheel, n, powered, share):
    """Per-wheel loads on this runway (kips). kind: a key of IMPACT; n: wheels on this runway (one end truck); powered: electrically powered
    trolley; share: fraction of the lateral force taken by this runway."""
    if kind not in IMPACT:
        raise CraneError("crane: choose the crane type for the impact factor")
    if min(capacity, wheel) <= 0 or trolley < 0 or n < 1:
        raise CraneError("crane: the rated capacity, wheel load and number of wheels must be positive")
    if not 0 < share <= 1:
        raise CraneError("crane: the share of the lateral force taken by this runway is between 0 and 1")
    imp, imp_txt = IMPACT[kind]
    H_total = 0.20 * (capacity + trolley) if powered else 0.0
    hand = kind.startswith("hand")
    return dict(impact=imp, impact_txt=imp_txt, P=wheel, P_imp=wheel * (1 + imp), H_total=H_total, H_runway=H_total * share,
                H=H_total * share / n, LF=0.0 if hand else 0.10 * wheel * n, n=n, share=share)


def moving(L, P, spacing, n, w=0.0, step=None):
    """Simply supported span L (ft) with n equal wheel loads P (kips) at a spacing (ft), moving across, plus a uniform load w (kip/ft).
    Returns the largest moment (kip-ft) with the wheel positions and the section, the largest end reaction (kips) with the wheels' moment and
    reaction at the same positions. Moments are checked under every wheel and at midspan for every position."""
    if L <= 0 or n < 1 or (n > 1 and spacing <= 0):
        raise CraneError("crane: span, wheels and wheel spacing must be positive")
    span_w = (n - 1) * spacing
    step = step or L / 1200.0
    best = (0.0, None, None)
    k, x0 = 0, -span_w
    while x0 <= L + 1e-9:
        xs = [x0 + i * spacing for i in range(n)]
        on = [x for x in xs if 0 <= x <= L]
        for xc in on + [L / 2]:
            M = sum(P * ((L - a) * xc / L if xc <= a else a * (L - xc) / L) for a in on) + w * xc * (L - xc) / 2
            if M > best[0]:
                best = (M, xc, tuple(on))
        k += 1
        x0 = -span_w + k * step
    on_r = [x for x in (i * spacing for i in range(n)) if x <= L]           # first wheel at the support
    R = sum(P * (L - a) / L for a in on_r) + w * L / 2
    return dict(M=best[0], x=best[1], wheels=best[2], R=R, wheels_R=tuple(on_r))


def two_wheel_closed_form(L, P, a):
    """Two equal moving loads P at spacing a on a simple span: the larger of (P / 2L)(L - a/2)^2 (one wheel a/4 from midspan) and P L / 4 (one
    wheel at midspan, the other off the span or past it)."""
    return max(P / (2 * L) * (L - a / 2) ** 2, P * L / 4)


def deflection_mid(L, EI, loads_at):
    """Midspan deflection (in.) of a simple span L (ft) under point loads (kips at ft), EI in kip-in2: P a (3 L^2 - 4 a^2) / 48 EI with a
    measured from the nearer support."""
    Li = L * 12
    d = 0.0
    for P, x in loads_at:
        a = min(x, L - x) * 12
        d += P * a * (3 * Li ** 2 - 4 * a ** 2) / (48 * EI)
    return d


_UNIT = {}


def moving_continuous(spans, P, spacing, n, EI, w=0.0, H_ratio=0.0, fD=1.0, fL=1.0, Mc=None, Mcy=None, steps=240):
    """A runway beam continuous over several spans (ft), with n equal wheel loads P (kips) at a spacing (ft) moving across as a group, and a
    uniform dead load w (kip/ft). Exact for each position (beam.solve, the stiffness method on one mesh, superposed unit loads). For each wheel
    position the moments are factored (fD on the dead load, fL on the wheels) and, when Mc and Mcy are given, Eq. H1-1b is evaluated at every
    station with the lateral moment H_ratio x the wheels' moment. Returns the envelopes (kip-ft, kips, in.) and the governing positions."""
    import numpy as np
    from . import beam as bm
    if not spans or any(s <= 0 for s in spans) or n < 1 or (n > 1 and spacing <= 0):
        raise CraneError("crane: spans, wheels and wheel spacing must be positive")
    total = sum(spans)
    sup = [0.0]
    for s in spans:
        sup.append(sup[-1] + s)
    if n > 1:
        k = max(1, round(spacing / (total / steps)))
        step = spacing / k
    else:
        step = total / steps
    grid = [i * step for i in range(int(round(total / step)) + 1) if i * step <= total + 1e-9]
    nodes = [bm.PointLoad(x * 12.0, 0.0) for x in grid]
    supin = [x * 12.0 for x in sup]
    key = (tuple(spans), round(step, 9), EI)
    unit = _UNIT.get(key)
    if unit is None:
        unit = [bm.solve(total * 12.0, supin, EI, nodes + [bm.PointLoad(x * 12.0, 1.0)], n=200) for x in grid]
        _UNIT.clear()
        _UNIT[key] = unit
    xs = unit[0].x
    rD = bm.solve(total * 12.0, supin, EI, list(nodes), [bm.DistLoad(0.0, total * 12.0, w / 12.0, w / 12.0)], n=200) if w else None
    MD = rD.M / 12.0 if rD is not None else np.zeros_like(xs)               # kip-ft
    VD = rD.V if rD is not None else np.zeros_like(xs)
    RD = rD.reactions if rD is not None else {s_: 0.0 for s_ in supin}
    span_w = (n - 1) * spacing
    k_sp = int(round(spacing / step)) if n > 1 else 0
    out = dict(Mpos=0.0, Mneg=0.0, R=0.0, V=0.0, ratio=0.0, defl=0.0, pos=None, x_pos=None, x_neg=None, gov=None)
    for i0 in range(-k_sp * (n - 1), len(grid)):
        idx = [i0 + j * k_sp for j in range(n)]
        on = [i for i in idx if 0 <= i < len(grid)]
        if not on:
            continue
        Mw = sum(unit[i].M for i in on) * P / 12.0
        Vw = sum(unit[i].V for i in on) * P
        dw = sum(unit[i].defl for i in on) * P
        Rw = {s_: sum(unit[i].reactions[s_] for i in on) * P for s_ in supin}
        M = fD * MD + fL * Mw
        jp, jn = int(np.argmax(M)), int(np.argmin(M))
        if M[jp] > out["Mpos"]:
            out.update(Mpos=float(M[jp]), x_pos=float(xs[jp] / 12.0), pos=[grid[i] for i in on])
        if M[jn] < out["Mneg"]:
            out.update(Mneg=float(M[jn]), x_neg=float(xs[jn] / 12.0), pos_neg=[grid[i] for i in on])
        out["R"] = max(out["R"], max(fD * RD[s_] + fL * Rw[s_] for s_ in supin))
        out["V"] = max(out["V"], float(np.max(np.abs(fD * VD + fL * Vw))))
        out["defl"] = max(out["defl"], float(np.max(dw)))                 # wheels alone, without the factors (the caller passes P without impact for deflection)
        if Mc and Mcy:
            rr = np.abs(M) / Mc + np.abs(fL * Mw * H_ratio) / Mcy
            j = int(np.argmax(rr))
            if rr[j] > out["ratio"]:
                out.update(ratio=float(rr[j]), gov=dict(x=float(xs[j] / 12.0), Mx=float(M[j]), My=float(fL * Mw[j] * H_ratio), wheels=[grid[i] for i in on]))
    out["supports"] = sup
    return out


def web_under_wheel(p, Fy, lb, at_end=True):
    """Nominal web local yielding and crippling strengths (kips) of a W-shape under a concentrated load on its top flange, AISC 360-22
    Sect. J10.2 and J10.3 (Qf = 1.0): at_end, the load within d (yielding) or d / 2 (crippling) of the member end (Eq. J10-3, J10-5a / J10-5b);
    otherwise Eq. J10-2 and J10-4. p: shape dict (d, tw, tf, kdes); lb: bearing length (in.)."""
    E = 29000.0
    d, tw, tf, k = p["d"], p["tw"], p["tf"], p["kdes"]
    Ry = Fy * tw * ((2.5 if at_end else 5.0) * k + lb)
    root = math.sqrt(E * Fy * tf / tw)
    if not at_end:
        Rc, eq = 0.80 * tw ** 2 * (1 + 3 * (lb / d) * (tw / tf) ** 1.5) * root, "Eq. J10-4"
    elif lb / d <= 0.2:
        Rc, eq = 0.40 * tw ** 2 * (1 + 3 * (lb / d) * (tw / tf) ** 1.5) * root, "Eq. J10-5a"
    else:
        Rc, eq = 0.40 * tw ** 2 * (1 + (4 * lb / d - 0.2) * (tw / tf) ** 1.5) * root, "Eq. J10-5b"
    return dict(Ry=Ry, Rc=Rc, eq_y="Eq. J10-3" if at_end else "Eq. J10-2", eq_c=eq)
