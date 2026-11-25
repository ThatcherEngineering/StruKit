"""Crane loads on a runway beam, ASCE/SEI 7-22 Sect. 4.9 (read from the standard: 4.9.1 to 4.9.5), and the moving-load effects of a pair (or
row) of wheels on a simply supported runway beam by statics.

  Maximum wheel load: from the crane maker (bridge weight plus rated capacity plus trolley, trolley placed for the largest effect, 4.9.2).
  Vertical impact (4.9.3): powered monorail 25%; bridge crane service class D, E or F 25%; service class A, B or C 10%; hand-geared bridge,
  trolley and hoist 0%.
  Lateral force (4.9.4), electrically powered trolleys only: 20% of (rated capacity + hoist and trolley), at the traction surface, either
  direction, distributed with regard to the lateral stiffness of the runway beams and supporting structure (the share to this runway is
  entered with its basis), divided equally among the wheels on this runway.
  Longitudinal force (4.9.5), except hand-geared bridges: 10% of the maximum wheel loads, at the traction surface, either direction."""

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
