"""Load combinations of ASCE/SEI 7-22, Chapter 2.

Read from the standard: Sect. 2.3.1 (strength design, combinations 1a to 5a) and
Sect. 2.4.1 (allowable stress design, combinations 1a to 7a). Each "(A or B or C)" in the
standard is written out as separate combinations. In ASCE/SEI 7-22 the snow load S is a
strength-level load: it carries 1.0 as the principal load in strength design and 0.7 in
allowable stress design.

Written as the standard gives them, with the full live load factor in strength
combinations 3a and 4a (Exception 1 to Sect. 2.3.1 permits 0.5 for some occupancies; it is
not applied here).

Seismic (function seismic): Sect. 2.3.6 combinations 6 and 7 and Sect. 2.4.5 combinations 8
to 10 (pdf pp. 69-70, confirmed against the page images), with Eh = rho QE (Eq. 12.4-3) and
Ev = 0.2 SDS D (Eq. 12.4-4a, pdf pp. 182-183) written into the dead load factor:
  6.  (1.2 + 0.2 SDS) D + rho QE + L + 0.15 S        7.  (0.9 - 0.2 SDS) D + rho QE
  8.  (1.0 + 0.14 SDS) D + 0.7 rho QE
  9.  (1.0 + 0.105 SDS) D + 0.525 rho QE + 0.75 L + 0.1 S
  10. (0.6 - 0.14 SDS) D + 0.7 rho QE
Load case E holds QE, the effect of the horizontal seismic forces; enter it with both signs
where the force reverses. Ev may be taken as zero in Seismic Design Category B
(Sect. 12.4.2.2, exception 2a): ev=False. The full live load factor is kept in combination 6
(Exception 1 to Sect. 2.3.6 permits 0.5 for some occupancies; not applied).

Not included: flood (2.3.2, 2.4.2), atmospheric ice (2.3.3, 2.4.3), self-straining forces
(2.3.4, 2.4.4), seismic load effects with overstrength, tornado loads WT, fluid loads F and
lateral earth pressure H.

Load case names: D dead, L live, Lr roof live, S snow, R rain, W wind, E horizontal seismic (QE).
"""

STANDARD = "ASCE/SEI 7-22"


def _src(sect, no):
    return f"{STANDARD} Sect. {sect}, combination {no}"


def _expand(sect, items):
    return [dict(expr=e, source=_src(sect, no)) for no, exprs in items for e in exprs]


LRFD = _expand("2.3.1", [
    ("1a", ["1.4D"]),
    ("2a", ["1.2D + 1.6L + 0.5Lr", "1.2D + 1.6L + 0.3S", "1.2D + 1.6L + 0.5R"]),
    ("3a", ["1.2D + 1.6Lr + 1.0L", "1.2D + 1.6Lr + 0.5W", "1.2D + 1.0S + 1.0L", "1.2D + 1.0S + 0.5W",
            "1.2D + 1.6R + 1.0L", "1.2D + 1.6R + 0.5W"]),
    ("4a", ["1.2D + 1.0W + 1.0L + 0.5Lr", "1.2D + 1.0W + 1.0L + 0.3S", "1.2D + 1.0W + 1.0L + 0.5R"]),
    ("5a", ["0.9D + 1.0W"]),
])

# 0.75 x 0.7 S = 0.525 S; 0.75 x 0.6 W = 0.45 W
ASD = _expand("2.4.1", [
    ("1a", ["D"]),
    ("2a", ["D + L"]),
    ("3a", ["D + Lr", "D + 0.7S", "D + R"]),
    ("4a", ["D + 0.75L + 0.75Lr", "D + 0.75L + 0.525S", "D + 0.75L + 0.75R"]),
    ("5a", ["D + 0.6W"]),
    ("6a", ["D + 0.75L + 0.45W + 0.75Lr", "D + 0.75L + 0.45W + 0.525S", "D + 0.75L + 0.45W + 0.75R"]),
    ("7a", ["0.6D + 0.6W"]),
])

SETS = {STANDARD: dict(ASD=ASD, LRFD=LRFD)}


def _n(x):
    t = f"{x:.4f}".rstrip("0")
    return t + "0" if t.endswith(".") else t


def seismic(SDS, rho=1.0, ev=True, omega0=None):
    """The seismic load combinations for a project: dict(ASD=[...], LRFD=[...]) of
    dict(expr, source), with Ev and the redundancy factor written into the factors.
    omega0: the overstrength factor; when given, the combinations with overstrength of
    Sect. 2.3.6 and 2.4.5 are added, with Emh = omega0 QE (Sect. 12.4.3) written into the
    factors on a separate load case, Em. A member designed for overstrength carries its
    horizontal seismic effect QE under load case Em in place of E. The 1.2 allowable stress
    increase permitted by Sect. 2.4.5 is not taken."""
    if SDS is None or SDS < 0:
        raise ValueError("SDS must be zero or more")
    if rho not in (1.0, 1.3):
        raise ValueError("the redundancy factor is 1.0 or 1.3 (Sect. 12.3.4)")
    if omega0 is not None and not 1.0 <= omega0 <= 3.5:
        raise ValueError("the overstrength factor is from 1 to 3.5 (Table 12.2-1)")
    v = 0.2 * SDS if ev else 0.0
    tail = f"; Ev = {'0.2 SDS D' if ev else '0'}, SDS = {_n(SDS)}; Eh = rho QE, rho = {_n(rho)} (Sect. 12.4.2)"
    lrfd = [("6", f"{_n(1.2 + v)}D + {_n(rho)}E + 1.0L + 0.15S"), ("7", f"{_n(0.9 - v)}D + {_n(rho)}E")]
    asd = [("8", f"{_n(1.0 + 0.7 * v)}D + {_n(0.7 * rho)}E"),
           ("9", f"{_n(1.0 + 0.525 * v)}D + {_n(0.525 * rho)}E + 0.75L + 0.1S"),
           ("10", f"{_n(0.6 - 0.7 * v)}D + {_n(0.7 * rho)}E")]
    out = dict(LRFD=[dict(expr=e, source=_src("2.3.6", no) + tail) for no, e in lrfd],
               ASD=[dict(expr=e, source=_src("2.4.5", no) + tail) for no, e in asd])
    if omega0 is not None:
        o = omega0
        tail_o = (f" with overstrength; Ev = {'0.2 SDS D' if ev else '0'}, SDS = {_n(SDS)}; Emh = Omega0 QE, Omega0 = {_n(o)} (Sect. 12.4.3); "
                  "load case Em is QE")
        out["LRFD"] += [dict(expr=e, source=_src("2.3.6", no) + tail_o) for no, e in
                        (("6", f"{_n(1.2 + v)}D + {_n(o)}Em + 1.0L + 0.15S"), ("7", f"{_n(0.9 - v)}D + {_n(o)}Em"))]
        out["ASD"] += [dict(expr=e, source=_src("2.4.5", no) + tail_o) for no, e in
                       (("8", f"{_n(1.0 + 0.7 * v)}D + {_n(0.7 * o)}Em"), ("9", f"{_n(1.0 + 0.525 * v)}D + {_n(0.525 * o)}Em + 0.75L + 0.1S"),
                        ("10", f"{_n(0.6 - 0.7 * v)}D + {_n(0.7 * o)}Em"))]
    return out
