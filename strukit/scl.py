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

Beams: joist orientation only (load on the narrow face). Columns: one piece. Veneers lie
parallel to the wide face, so bending about the strong axis is joist orientation and
bending about the weak axis is plank orientation; a square section takes the plank values
about both axes (the lower ones).
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
                                   Fb=float(_r["Fb_joist"]), Fb_plank=float(_r["Fb_plank"]), Fv_plank=float(_r["Fv_plank"]), Ft=float(_r["Ft"]), Fc=float(_r["Fc"]),
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


def eccentric_column(fc, Fc_adj, d1, d2, e1, e2, Fb1_adj, Fb2_adj, FcE1, FcE2, FbE=None, fb1=0.0, fb2=0.0):
    """NDS Eq. 15.4-1 (value to be not more than 1.0) and Eq. 15.4-2 (same) for a column
    with an axial load at eccentricity e1 (parallel to the wide face d1) and e2 (parallel
    to the narrow face d2), and side-load bending stresses fb1 (edgewise, load on the
    narrow face) and fb2 (flatwise). With no side load these are Eq. 15.4-3 and 15.4-4.
    FbE is None when lateral buckling does not apply."""
    if fc >= FcE1 or fc >= FcE2:
        return float("inf"), float("inf")
    m1 = fb1 + fc * 6 * e1 / d1
    t = (m1 / FbE) ** 2 if FbE else 0.0
    v = (fc / Fc_adj) ** 2
    if m1:
        v += (fb1 + fc * (6 * e1 / d1) * (1 + 0.234 * fc / FcE1)) / (Fb1_adj * (1 - fc / FcE1))
    if e2 or fb2:
        den = 1 - fc / FcE2 - t
        if den <= 0:
            return float("inf"), fc / FcE2 + t
        v += (fb2 + fc * (6 * e2 / d2) * (1 + 0.234 * fc / FcE2 + 0.234 * t)) / (Fb2_adj * den)
    return v, fc / FcE2 + t


# ---- Weyerhaeuser Microllam LVL, Parallam PSL, TimberStrand LSL: ICC-ES ESR-1387 --------
# Read from the report (reissued February 2025, revised July 2026), Table 1, joist / beam
# orientation (values typed from the table into data/esr1387_table1.csv):
#   note 1   dry use, moisture content under 16 percent
#   note 5   deflection must include shear: 270 W L^4 / (E b d^3) + 28.8 W L^2 / (E b d)
#   note 6   Emin is tabulated
#   note 7   CV, joist / beam orientation: Microllam (12/d)^0.136 <= 1.18;
#            Parallam (12/d)^0.111 <= 1.15; TimberStrand (12/d)^0.092 <= 1.12
#   note 8   Parallam: Fb x 0.93 when the thickness is under 2.69 in.
#   note 11  Microllam: Fv = 260 psi for depths over 24 in.
#   note 15  TimberStrand 1.3E not labeled Rim Board: Fc_perp = 670 psi (in the data file)
#   note 21  TimberStrand 1.6E thinner than 2.5 in.: Fc_perp = 900 psi
# Not taken: the higher Fc_perp of notes 19 and 20 for single-species production.
# Sizes (Sect. 3): Microllam 0.75 to 3.5 in. thick; Parallam up to 11 in.; TimberStrand
# 1.25 to 5.5 in.
WEY = {}
with open(Path(__file__).parent / "data" / "esr1387_table1.csv", newline="") as _f:
    for _r in csv.DictReader(_f):
        WEY.setdefault(_r["product"], {})[_r["grade"]] = dict(
            E=float(_r["E_e6"]) * 1e6, Emin=float(_r["Emin_e6"]) * 1e6, Fb=float(_r["Fb_joist"]), Fv=float(_r["Fv_joist"]),
            Fc_perp=float(_r["Fc_perp_joist"]), Fb_plank=float(_r["Fb_plank"]), Fc=float(_r["Fc"]))
_WEY_CV = {"Microllam LVL": (0.136, 1.18), "Parallam PSL": (0.111, 1.15), "TimberStrand LSL": (0.092, 1.12)}
_WEY_T = {"Microllam LVL": (0.75, 3.5), "Parallam PSL": (1.75, 11.0), "TimberStrand LSL": (1.25, 5.5)}
PRODUCTS = ["Versa-Lam LVL"] + list(WEY)


def grades(product):
    return list(GRADES) if product == "Versa-Lam LVL" else list(WEY.get(product, {}))


def beam_spec(product, grade, ply_thickness, plies, depth):
    """Everything a joist-orientation beam calculation needs for one product and grade."""
    b = ply_thickness * plies
    if product == "Versa-Lam LVL":
        v = values(grade)
        return dict(name=product, report="ICC-ES ESR-1040", source=SOURCE, Fb=v["Fb"], Fv=v["Fv"], Fc_perp=v["Fc_perp"], E=v["E"],
                    Emin=emin(v["E_app"]), emin_label="Emin = E [1 - 1.645 (0.10)] (1.03) / 1.66",
                    emin_src="ESR-1040 Table 1 note 6; NDS Eq. D-4", emin_note=f"apparent E = {v['E_app']:,.0f} psi",
                    CV=volume_factor(depth, b), cv_label="CV = (12 / d)^(1/9)", cv_src="ESR-1040 Table 1 note 3", cv_note="",
                    fb_note="joist orientation, 12 in. depth", defl_src="ESR-1040 Table 1 note 11", notes=[])
    if product not in WEY:
        raise SclError(f"structural composite lumber: product '{product}' is not on file")
    if grade not in WEY[product]:
        raise SclError(f"{product}: grade '{grade}' is not in ESR-1387 Table 1")
    v = dict(WEY[product][grade])
    lo, hi = _WEY_T[product]
    if not lo <= ply_thickness <= hi:
        raise SclError(f"{product}: thickness must be {lo:g} to {hi:g} in. (ESR-1387)")
    if depth <= 0 or depth > 54:
        raise SclError(f"{product}: the depth is out of range (ESR-1387)")
    x, cap = _WEY_CV[product]
    notes, fb_note = [], "joist / beam orientation, 12 in. depth"
    if product == "Parallam PSL" and ply_thickness < 2.69:
        v["Fb"] *= 0.93
        fb_note += "; x 0.93 for thickness under 2.69 in. (note 8)"
    if product == "Microllam LVL" and depth > 24:
        v["Fv"] = 260.0
    if product == "TimberStrand LSL" and grade == "1.6E" and ply_thickness < 2.5:
        v["Fc_perp"] = 900.0
    return dict(name=product, report="ICC-ES ESR-1387", source="ICC-ES ESR-1387 Table 1", Fb=v["Fb"], Fv=v["Fv"], Fc_perp=v["Fc_perp"],
                E=v["E"], Emin=v["Emin"], emin_label="Emin", emin_src="ESR-1387 Table 1", emin_note="",
                CV=min((12.0 / depth) ** x, cap), cv_label=f"CV = (12 / d)^{x:g}", cv_src="ESR-1387 Table 1 note 7",
                cv_note=f"not more than {cap:g}", fb_note=fb_note, defl_src="ESR-1387 Table 1 note 5", notes=notes)


def column_spec(product, grade, d1, d2, lu2_ft):
    """Everything a one-piece column calculation needs. d1 >= d2, in.; lu2_ft: unbraced
    length for buckling in the plane of d2 (about the weak axis), ft.
    Versa-Lam (ESR-1040): plank Fb about either axis with the plank volume factor (note 4).
    ESR-1387 products: bending about the strong axis uses the joist Fb and CV of note 7
    (with note 8 for Parallam); bending about the weak axis uses the plank Fb with the
    plank CV of note 7: Microllam (1.75/t)^0.136 <= 1.0, thickness to 3.5 in.; Parallam
    (12/t)^0.111 <= 1.15; TimberStrand 1.0.
    ESR-1387 Table 1 note 13 (Parallam grades with Fc of 2,700 or 2,900 psi): design by
    NDS Chapter 15 with a minimum eccentricity parallel to the narrow face
    e2 = t/6 + 5 L^2 / 4608 (t in., L ft)."""
    if product == "Versa-Lam LVL":
        v = values(grade)
        if d2 < 1.5 or d2 > 7.0 or d1 > 48:
            raise SclError("LVL: the section must be 1.5 to 7 in. thick and not more than 48 in. wide (ESR-1040)")
        square = abs(d1 - d2) < 1e-9
        return dict(name=product, report="ICC-ES ESR-1040", source=SOURCE, Fc=v["Fc"], Emin=emin(v["E_app"]),
                    emin_label="Emin = E [1 - 1.645 (0.10)] (1.03) / 1.66", emin_src="ESR-1040 Table 1 note 6; NDS Eq. D-4",
                    emin_note=f"apparent E = {v['E_app']:,.0f} psi",
                    Fb1=v["Fb_plank"] if square else v["Fb"], CV1=plank_volume_factor(d1) if square else (12.0 / d1) ** (1 / 9),
                    Fb2=v["Fb_plank"], CV2=plank_volume_factor(d2), Fv1=v["Fv_plank"] if square else v["Fv"],
                    fb1_note="plank orientation" if square else "joist orientation", fb2_note="plank orientation",
                    cv_src="ESR-1040 Table 1 notes 3 and 4", e2_min=0.0, e2_src="",
                    assumption=("Bending uses the plank-orientation Fb and Fv about either axis (square section), with the volume "
                                "factor of ESR-1040 Table 1 note 4." if square else
                                "Bending about the strong axis uses the joist-orientation Fb and Fv and bending about the weak axis the "
                                "plank-orientation Fb, each with its volume factor (ESR-1040 Table 1 notes 3 and 4)."))
    if product not in WEY or grade not in WEY[product]:
        raise SclError(f"{product}: grade '{grade}' is not in ESR-1387 Table 1")
    v = WEY[product][grade]
    lo, hi = _WEY_T[product]
    if not lo <= d2 <= hi:
        raise SclError(f"{product}: thickness must be {lo:g} to {hi:g} in. (ESR-1387)")
    x, cap = _WEY_CV[product]
    Fb1, n1 = v["Fb"], "joist / beam orientation"
    if product == "Parallam PSL" and d2 < 2.69:
        Fb1, n1 = Fb1 * 0.93, n1 + "; x 0.93 for thickness under 2.69 in. (note 8)"
    CV2 = {"Microllam LVL": min((1.75 / d2) ** 0.136, 1.0), "Parallam PSL": min((12.0 / d2) ** 0.111, 1.15), "TimberStrand LSL": 1.0}[product]
    e2_min, e2_src = 0.0, ""
    if product == "Parallam PSL" and v["Fc"] >= 2700:
        e2_min, e2_src = d2 / 6.0 + 5.0 * lu2_ft ** 2 / 4608.0, "ESR-1387 Table 1 note 13: e2 = t/6 + 5 L^2 / 4608"
    return dict(name=product, report="ICC-ES ESR-1387", source="ICC-ES ESR-1387 Table 1", Fc=v["Fc"], Emin=v["Emin"], emin_label="Emin",
                emin_src="ESR-1387 Table 1", emin_note="", Fb1=Fb1, CV1=min((12.0 / d1) ** x, cap), Fb2=v["Fb_plank"], CV2=CV2,
                Fv1=260.0 if (product == "Microllam LVL" and d1 > 24) else v["Fv"],
                fb1_note=n1, fb2_note="face / plank orientation", cv_src="ESR-1387 Table 1 note 7", e2_min=e2_min, e2_src=e2_src,
                assumption="Bending about the strong axis uses the joist-orientation Fb and bending about the weak axis the "
                           "plank-orientation Fb, each with its volume factor (ESR-1387 Table 1 note 7).")
