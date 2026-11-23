"""Structural composite lumber: Versa-Lam LVL (Boise Cascade), ICC-ES ESR-1040, designed by
the 2018 NDS Chapter 8.

Read from the report (reissued September 2025):
  Table 1    reference design values, dry use (moisture content under 16 percent); 38 grades
             (data/esr1040_table1.csv, read by tools/parse_esr1040.py)
  note 2     adjust by NDS 8.3
  note 3     Fb is for a 12 in. depth; for other depths, thickness 7 in. or less,
             CV = (12/d)^(1/9)
  note 6     Emin from the apparent E by NDS Appendix D with COV_E = 0.10:
             Emin = E [1 - 1.645 (0.10)] (1.03) / 1.66          (NDS Eq. D-4)
  note 11    deflection of a uniformly loaded simple span, with the true E:
             270 W L^4 / (E b d^3) + 28.8 W L^2 / (E b d)   (bending + shear).
             With M = W L^2 / 8 (lb-ft) = 1.5 W L^2 (lb-in) the shear term is
             19.2 M / (E b d), M in lb-in; that form is used for other loads on a simple
             span (shear deflection of a simple span is proportional to the moment).
Read from the 2018 NDS:
  8.3.6.1    when CV is 1.0 or less it does not apply together with CL; the lesser applies.
             When CV is over 1.0 both apply.
  8.3.7      repetitive member factor Cr = 1.04
  Table 8.3.1  Fv' = Fv CD; Fc_perp' = Fc_perp; E and Emin unadjusted in dry use

  3.7.1.5    c = 0.9 in the column stability factor for structural composite lumber
  15.4.1(b)  column with an eccentric axial load, Eq. 15.4-3 and 15.4-4

Beams: joist orientation only (load on the narrow face). Columns: one piece; bending from
eccentricity uses the plank-orientation Fb about either axis (the lower tabulated value),
with the plank volume factor (7/d)^(1/5) for depths over 7 in. (Table 1 note 4), because
the veneer direction in a column section is not an input.
"""
import csv
from pathlib import Path


class SclError(ValueError):
    pass


SOURCE = "ICC-ES ESR-1040 Table 1"
GRADES = {}
with open(Path(__file__).parent / "data" / "esr1040_table1.csv", newline="") as _f:
    for _r in csv.DictReader(_f):
        GRADES[_r["grade"]] = dict(E=float(_r["E_true_e6"]) * 1e6, E_app=float(_r["E_apparent_e6"]) * 1e6,
                                   Fb=float(_r["Fb_joist"]), Fb_plank=float(_r["Fb_plank"]), Ft=float(_r["Ft"]), Fc=float(_r["Fc"]),
                                   Fc_perp=float(_r["Fc_perp_joist"]), Fv=float(_r["Fv_joist"]))


def values(grade):
    if grade not in GRADES:
        raise SclError(f"LVL: grade '{grade}' is not in ESR-1040 Table 1")
    return GRADES[grade]


def emin(E_apparent, cov=0.10):
    return E_apparent * (1 - 1.645 * cov) * 1.03 / 1.66


def volume_factor(d, thickness):
    if thickness > 7.0:
        raise SclError("LVL: thickness over 7 in. is not covered (ESR-1040 Table 1 note 3)")
    if d <= 0 or d > 48:
        raise SclError("LVL: the depth must be more than 0 and not more than 48 in. (ESR-1040 Sect. 3.0)")
    return (12.0 / d) ** (1 / 9)


def shear_deflection(M_lb_in, E_true, b, d):
    """ESR-1040 Table 1 note 11 shear term, written in terms of the moment (see above)."""
    return 19.2 * M_lb_in / (E_true * b * d)


def plank_volume_factor(d):
    """ESR-1040 Table 1 note 4."""
    return (7.0 / d) ** 0.2 if d > 7.0 else 1.0


def eccentric_column(fc, Fc_adj, d1, d2, e1, e2, Fb1_adj, Fb2_adj, FcE1, FcE2, FbE=None):
    """NDS Eq. 15.4-3 (value to be not more than 1.0) and Eq. 15.4-4 (same) for a column
    with an axial load at eccentricity e1 (parallel to the wide face d1) and e2 (parallel
    to the narrow face d2). FbE is None when lateral buckling does not apply."""
    if fc >= FcE1 or fc >= FcE2:
        return float("inf"), float("inf")
    m1 = fc * 6 * e1 / d1
    t = (m1 / FbE) ** 2 if FbE else 0.0
    v = (fc / Fc_adj) ** 2
    if e1:
        v += m1 * (1 + 0.234 * fc / FcE1) / (Fb1_adj * (1 - fc / FcE1))
    if e2:
        den = 1 - fc / FcE2 - t
        if den <= 0:
            return float("inf"), fc / FcE2 + t
        v += fc * (6 * e2 / d2) * (1 + 0.234 * fc / FcE2 + 0.234 * t) / (Fb2_adj * den)
    return v, fc / FcE2 + t
