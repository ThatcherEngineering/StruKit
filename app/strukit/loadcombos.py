"""Load combinations of ASCE/SEI 7-22, Chapter 2.

Read from the standard: Sect. 2.3.1 (strength design, combinations 1a to 5a) and
Sect. 2.4.1 (allowable stress design, combinations 1a to 7a). Each "(A or B or C)" in the
standard is written out as separate combinations. In ASCE/SEI 7-22 the snow load S is a
strength-level load: it carries 1.0 as the principal load in strength design and 0.7 in
allowable stress design.

Written as the standard gives them, with the full live load factor in strength
combinations 3a and 4a (Exception 1 to Sect. 2.3.1 permits 0.5 for some occupancies; it is
not applied here).

Not included: flood (2.3.2, 2.4.2), atmospheric ice (2.3.3, 2.4.3), self-straining forces
(2.3.4, 2.4.4), seismic load effects (2.3.6, 2.4.5), tornado loads WT, fluid loads F and
lateral earth pressure H.

Load case names: D dead, L live, Lr roof live, S snow, R rain, W wind.
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
