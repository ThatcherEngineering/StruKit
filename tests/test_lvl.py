"""Versa-Lam LVL beams: ICC-ES ESR-1040 values, 2018 NDS Chapter 8.

Independent references:
  - Boise Cascade Versa-Lam Design Guide LVL-W2000 (Western US), allowable design values
    table: 1-3/4 x 11-7/8 2.1E 2800: shear 3,948 lb, moment 9,608 lb-ft, I 244.2 in4;
    3-1/2 x 11-7/8 2.1E 3100: 7,897 lb, 21,275 lb-ft, 488.4 in4; 1-3/4 x 11-1/4 2.1E 2800:
    3,741 lb, 8,675 lb-ft.
  - Job 2026-011 StruCalc package, Roof Beam A: (2) 1.75 x 11.875 2.1E 2800, 11.25 ft,
    D 320 + self-weight 10.68 plf, L 640 plf, bearing 3 in: bending 2,240.2 psi against
    2,803.3; shear 197.1 against 285; bearing 520.0 against 750; deflection 0.341 in.
    StruCalc's deflection is bending only; ESR-1040 note 11 adds shear deflection.
  - ESR-1040 Table 1 note 11 formula evaluated by hand for that beam: 0.3411 + 0.0405 in.
"""
import pytest

from strukit import scl, ws_wood
from strukit.ws_steel_beam import DeflCheck
from strukit.loadcombos import SETS
from strukit.gui import calc


def _combos():
    proj = dict(method="ASD", combos_asd=[dict(expr=c["expr"], source=c["source"]) for c in SETS["ASCE/SEI 7-22"]["ASD"]], combos_lrfd=[])
    miss = []
    return calc.combos(proj, miss, "ASD")


def test_table_1():
    assert len(scl.GRADES) == 38
    v = scl.values("2.1E 2800")
    assert (v["Fb"], v["Fv"], v["Fc_perp"], v["E"], v["E_app"], v["Fc"], v["Ft"]) == (2800, 285, 750, 2.1e6, 2.0e6, 3000, 1950)
    v = scl.values("1.5E 1800")
    assert (v["Fb"], v["Fv"], v["Fc_perp"], v["E"], v["E_app"]) == (1800, 225, 525, 1.5e6, 1.4e6)
    assert scl.values("2.1E 3100")["Fb"] == 3100
    assert scl.emin(2.0e6) == pytest.approx(2.0e6 * 0.8355 * 1.03 / 1.66)


def test_allowable_moment_and_shear_match_the_boise_design_guide():
    for grade, t, d, V, M, I in (("2.1E 2800", 1.75, 11.875, 3948, 9608, 244.2), ("2.1E 3100", 3.5, 11.875, 7897, 21275, 488.4),
                                 ("2.1E 2800", 1.75, 11.25, 3741, 8675, 207.6)):
        v = scl.values(grade)
        assert v["Fv"] * t * d / 1.5 == pytest.approx(V, abs=1)
        assert v["Fb"] * scl.volume_factor(d, t) * t * d * d / 6 / 12 == pytest.approx(M, abs=2)
        assert t * d ** 3 / 12 == pytest.approx(I, abs=0.1)


def test_roof_beam_a_of_job_2026_011():
    loads = [dict(case="D", kind="uniform", w=320.0), dict(case="D", kind="uniform", w=10.68), dict(case="L", kind="uniform", w=640.0)]
    s = ws_wood.lvl_beam("RB-A", "2.1E 2800", 1.75, 11.875, 2, 11.25, loads, _combos(),
                         [DeflCheck("total", {"D": 1.0, "L": 1.0}, 240, "typed in")], 0.0, 3.0, False)
    r = {x.check: x for x in s.rows}
    assert r["bending"].demand == pytest.approx(2240.2, abs=0.5) and r["bending"].capacity == pytest.approx(2803.3, abs=0.2)
    assert r["shear"].demand == pytest.approx(197.1, abs=0.1) and r["shear"].capacity == 285
    assert r["bearing at support"].demand == pytest.approx(520.0, abs=0.1) and r["bearing at support"].capacity == 750
    # deflection by ESR-1040 note 11: 270 W L^4 / (E b d^3) + 28.8 W L^2 / (E b d) = 0.3411 + 0.0405
    W, Lf, b, d, E = 970.68, 11.25, 3.5, 11.875, 2.1e6
    hand = 270 * W * Lf ** 4 / (E * b * d ** 3) + 28.8 * W * Lf ** 2 / (E * b * d)
    assert hand == pytest.approx(0.3816, abs=0.0005)
    assert r["deflection, total"].demand == pytest.approx(hand, abs=0.0005)


def test_unbraced_beam_takes_the_lesser_of_cv_and_cl():
    loads = [dict(case="D", kind="uniform", w=100.0), dict(case="L", kind="uniform", w=200.0)]
    braced = ws_wood.lvl_beam("B", "2.1E 2800", 1.75, 14, 1, 16, loads, _combos(), [], 0.0, 3.0, False)
    free = ws_wood.lvl_beam("B", "2.1E 2800", 1.75, 14, 1, 16, loads, _combos(), [], 16.0, 3.0, False)
    cv = (12 / 14) ** (1 / 9)
    assert braced.rows[0].capacity == pytest.approx(2800 * cv)
    # 1.75 x 14 unbraced 16 ft: lu/d = 13.7, le = 1.63 lu + 3d = 354.96 in; RB = sqrt(354.96 x 14 / 1.75^2) = 40.28
    # FbE = 1.2 x 1,036,825 / 40.28^2 = 766.8 psi; Fb* = 2,800; CL by Eq. 3.3-6 = 0.2725 < CV
    FbE, Fs = 1.2 * scl.emin(2.0e6) / (354.96 * 14 / 1.75 ** 2), 2800.0
    a = (1 + FbE / Fs) / 1.9
    CL = a - (a * a - FbE / Fs / 0.95) ** 0.5
    assert free.rows[0].capacity == pytest.approx(2800 * CL, rel=1e-3) and CL < cv


def test_limits():
    with pytest.raises(Exception, match="not in ESR-1040"):
        ws_wood.lvl_beam("B", "9.9E 9999", 1.75, 14, 1, 16, [dict(case="D", kind="uniform", w=1)], _combos(), [], 0, 3, False)
    with pytest.raises(Exception, match="7 in"):
        ws_wood.lvl_beam("B", "2.1E 2800", 3.5, 14, 3, 16, [dict(case="D", kind="uniform", w=1)], _combos(), [], 0, 3, False) if False else scl.volume_factor(14, 7.5)


# ---- columns ----------------------------------------------------------------------------
# Independent reference: Boise Cascade LVL-W2000, "Versa-Lam 1.8E 2650 Column Tables"
# (2018 NDS, Ke = 1.0, eccentricity of 1/6 of the thickness or width, worst case). The
# guide's Emin uses a 1.05 factor where NDS Eq. D-4 has 1.03 (design property note 8), so
# the table is reproduced here with the guide's Emin; StruKit itself uses Eq. D-4 as
# ESR-1040 note 6 says, which gives about 1 percent less.
from strukit import wood


def _table_load(b, d, L_ft, CD, emin):
    d1, d2, le = max(b, d), min(b, d), L_ft * 12.0
    v = scl.values("1.8E 2650")
    Fcs = v["Fc"] * CD
    CP, st = wood.column_stability(Fcs, emin, le, d1, le, d2, c=0.9)
    FcE1, FcE2 = 0.822 * emin / (le / d1) ** 2, 0.822 * emin / (le / d2) ** 2
    Fb = v["Fb_plank"] * CD
    lo, hi = 0.0, Fcs * CP * d1 * d2
    for _ in range(60):
        P = (lo + hi) / 2
        r = scl.eccentric_column(P / (d1 * d2), Fcs * CP, d1, d2, 0.0, d2 / 6, Fb, Fb * scl.plank_volume_factor(d2), FcE1, FcE2)[0]
        lo, hi = (P, hi) if r < 1 else (lo, P)
    return lo


def test_column_table_of_the_boise_design_guide():
    guide_emin = 1.7e6 * (1 - 1.645 * 0.10) * 1.05 / 1.66
    for b, d, L, CD, tab in ((3.5, 3.5, 8, 1.0, 6930), (3.5, 3.5, 4, 1.0, 14700), (3.5, 5.25, 10, 1.15, 7715),
                             (5.25, 5.25, 12, 1.0, 15590), (7, 7, 20, 1.25, 20910), (3.5, 7, 6, 1.0, 20195), (5.25, 7, 16, 1.0, 13525)):
        assert _table_load(b, d, L, CD, guide_emin) == pytest.approx(tab, rel=0.004)
        assert _table_load(b, d, L, CD, scl.emin(1.7e6)) < tab            # StruKit's Emin is the lower one


def test_lvl_column_sheet():
    s = ws_wood.lvl_post("LC1", "1.8E 2650", 3.5, 3.5, 8, [dict(case="D", P=2000.0), dict(case="L", P=4500.0)], _combos(), 1.0, 1.0,
                         "pinned top and bottom", e2_in=3.5 / 6)
    r = {x.check: x for x in s.rows}
    # 6,500 lb is under the guide's 6,930 lb and over the 6,853 lb StruKit allows? no: 6,500 < 6,853, so it passes
    assert r["compression with eccentric load"].demand < 1.0 and r["compression"].demand == pytest.approx(6500 / 12.25)
    # hand: Emin = 880,949; le/d = 27.43; FcE = 962.5; Fc* = 3,000; CP by Eq. 3.7-1 with c = 0.9
    FcE = 0.822 * scl.emin(1.7e6) / (96 / 3.5) ** 2
    a = FcE / 3000
    CP = (1 + a) / 1.8 - ((1 + a) ** 2 / 3.24 - a / 0.9) ** 0.5
    assert r["compression"].capacity == pytest.approx(3000 * CP, rel=1e-6)
    s2 = ws_wood.lvl_post("LC1", "1.8E 2650", 3.5, 3.5, 8, [dict(case="D", P=2000.0), dict(case="L", P=5000.0)], _combos(), 1.0, 1.0,
                          "pinned top and bottom", e2_in=3.5 / 6)
    assert {x.check: x for x in s2.rows}["compression with eccentric load"].demand > 1.0


# ---- Weyerhaeuser products, ESR-1387 ----------------------------------------------------
# References: the CV table printed under ESR-1387 Table 1 note 7 (values at each depth),
# the deflection formula of note 5, and hand calculations. No manufacturer load table is
# on file for these products yet.
def test_esr_1387_values_and_notes():
    assert len(scl.WEY["Microllam LVL"]) == 20 and len(scl.WEY["Parallam PSL"]) == 10 and len(scl.WEY["TimberStrand LSL"]) == 17
    m = scl.beam_spec("Microllam LVL", "2.0E-2900Fb WS", 1.75, 2, 11.875)
    assert (m["Fb"], m["Fv"], m["Fc_perp"], m["E"]) == (2900, 285, 750, 2.0e6) and m["Emin"] == pytest.approx(1.017e6)
    assert scl.beam_spec("Microllam LVL", "2.0E-2900Fb WS", 1.75, 2, 30)["Fv"] == 260                       # note 11
    p = scl.beam_spec("Parallam PSL", "2.2E WS", 3.5, 1, 11.875)
    assert (p["Fb"], p["Fv"], p["Fc_perp"]) == (2900, 290, 625) and p["Emin"] == pytest.approx(1.118e6)
    assert scl.beam_spec("Parallam PSL", "2.2E WS", 1.75, 2, 11.875)["Fb"] == pytest.approx(2900 * 0.93)   # note 8
    t = scl.beam_spec("TimberStrand LSL", "1.55E", 3.5, 1, 9.25)
    assert (t["Fb"], t["Fv"], t["Fc_perp"], t["E"]) == (2325, 525, 900, 1.55e6)
    assert scl.beam_spec("TimberStrand LSL", "1.6E", 1.75, 1, 9.25)["Fc_perp"] == 900                       # note 21
    assert scl.beam_spec("TimberStrand LSL", "1.3E", 1.75, 1, 9.25)["Fc_perp"] == 670                       # note 15
    with pytest.raises(scl.SclError):
        scl.beam_spec("Microllam LVL", "2.0E-2900Fb WS", 5.25, 1, 12)


def test_esr_1387_volume_factor_table():
    table = {"Microllam LVL": {3.5: 1.18, 5.5: 1.11, 7.25: 1.07, 9.25: 1.04, 9.5: 1.03, 12: 1.00, 14: 0.98, 16: 0.96, 18: 0.95, 20: 0.93, 24: 0.91, 48: 0.83},
             "Parallam PSL": {3.5: 1.15, 5.5: 1.09, 7.25: 1.06, 9.25: 1.03, 9.5: 1.03, 12: 1.00, 14: 0.98, 16: 0.97, 18: 0.96, 20: 0.94, 24: 0.93, 48: 0.86, 54: 0.85},
             "TimberStrand LSL": {3.5: 1.12, 5.5: 1.07, 7.25: 1.05, 9.25: 1.02, 9.5: 1.02, 12: 1.00, 14: 0.99, 16: 0.97, 18: 0.96, 20: 0.95, 24: 0.94, 48: 0.88}}
    g = {"Microllam LVL": ("1.9E WS", 1.75), "Parallam PSL": ("2.0E WS", 3.5), "TimberStrand LSL": ("1.55E", 3.5)}
    for prod, rows in table.items():
        for d, cv in rows.items():
            assert scl.beam_spec(prod, g[prod][0], g[prod][1], 1, d)["CV"] == pytest.approx(cv, abs=0.0051)


def test_parallam_beam_by_hand():
    # 5.25 x 14 Parallam 2.2E WS, 16 ft, D 400 + L 800 plf, braced, bearing 4.5 in
    # M = 1,200 x 256 / 8 = 38,400 lb-ft; S = 171.5; fb = 2,686.9 psi; CV = (12/14)^0.111 = 0.9830; Fb' = 2,850.8 psi
    # V = 9,600; fv = 1.5 x 9,600 / 73.5 = 195.9 against 290; bearing 9,600 / (5.25 x 4.5) = 406.3 against 625
    # deflection (note 5): 270 x 1,200 x 16^4 / (2.2e6 x 5.25 x 14^3) + 28.8 x 1,200 x 256 / (2.2e6 x 5.25 x 14) = 0.6700 + 0.0547
    loads = [dict(case="D", kind="uniform", w=400.0), dict(case="L", kind="uniform", w=800.0)]
    s = ws_wood.lvl_beam("PB1", "2.2E WS", 5.25, 14, 1, 16, loads, _combos(), [DeflCheck("total", {"D": 1, "L": 1}, 240, "typed")],
                         0.0, 4.5, False, product="Parallam PSL")
    r = {x.check: x for x in s.rows}
    assert r["bending"].demand == pytest.approx(2686.9, abs=0.2) and r["bending"].capacity == pytest.approx(2850.8, abs=0.5)
    assert r["shear"].demand == pytest.approx(195.9, abs=0.1) and r["shear"].capacity == 290
    assert r["bearing at support"].demand == pytest.approx(406.3, abs=0.1) and r["bearing at support"].capacity == 625
    assert r["deflection, total"].demand == pytest.approx(0.6700 + 0.0547, abs=0.001)
    assert s.title == "PSL Beam" and "ESR-1040" not in " ".join(str(x.source) for x in s.steps)


def test_parallam_column_by_hand():
    # 5.25 x 5.25 Parallam 2.2E WS, 10 ft, pinned, D 6,000 + L 14,000 lb, load typed as centred
    # note 13: e2 = 5.25/6 + 5 x 100 / 4608 = 0.875 + 0.1085 = 0.9835 in
    # Emin = 1,118,000; le/d = 22.857; FcE = 0.822 x 1,118,000 / 522.4 = 1,759.0 psi; Fc* = 2,900; c = 0.9
    spec = scl.column_spec("Parallam PSL", "2.2E WS", 5.25, 5.25, 10.0)
    assert spec["e2_min"] == pytest.approx(0.9835, abs=0.0005) and spec["Fc"] == 2900 and spec["Fb2"] == 2650
    assert spec["CV2"] == pytest.approx((12 / 5.25) ** 0.111) and spec["CV2"] < 1.15
    assert scl.column_spec("Parallam PSL", "1.8E WS", 5.25, 5.25, 10.0)["e2_min"] == 0.0            # Fc 2,500: note 13 not flagged
    s = ws_wood.lvl_post("PC1", "2.2E WS", 5.25, 5.25, 10, [dict(case="D", P=6000.0), dict(case="L", P=14000.0)], _combos(), 1.0, 1.0,
                         "pinned top and bottom", product="Parallam PSL")
    r = {x.check: x for x in s.rows}
    FcE = 0.822 * 1.118e6 / (120 / 5.25) ** 2
    a = FcE / 2900
    CP = (1 + a) / 1.8 - ((1 + a) ** 2 / 3.24 - a / 0.9) ** 0.5
    fc = 20000 / 27.5625
    assert r["compression"].demand == pytest.approx(fc) and r["compression"].capacity == pytest.approx(2900 * CP, rel=1e-6)
    Fb2 = 2650 * (12 / 5.25) ** 0.111
    hand = (fc / (2900 * CP)) ** 2 + fc * 6 * 0.98351 / 5.25 * (1 + 0.234 * fc / FcE) / (Fb2 * (1 - fc / FcE))
    assert r["compression with eccentric load"].demand == pytest.approx(hand, rel=1e-4)
    assert s.title == "PSL Column" and any("note 13" in x for x in s.assumptions)
    with pytest.raises(Exception, match="thickness"):
        ws_wood.lvl_post("MC", "2.0E-2900Fb WS", 5.25, 5.25, 10, [dict(case="D", P=1.0)], _combos(), 1, 1, "pinned", product="Microllam LVL")


def test_lvl_column_with_wind_by_hand():
    # 3.5 x 7.25 Versa-Lam 1.8E 2650 (Versa-Stud size), 12 ft, pinned; strong-axis unbraced 12 ft, weak-axis braced at 4 ft
    # D 3,000 lb axial; W 60 plf on the narrow face. Combination 0.6D + 0.6W: P = 1,800, w = 36 plf (CD 1.6);
    # D + 0.6W: P = 3,000, w = 36.
    # M = 36 x 144 / 8 = 648 lb-ft = 7,776 lb-in; S1 = 3.5 x 7.25^2 / 6 = 30.66; fb1 = 253.6 psi
    spec = scl.column_spec("Versa-Lam LVL", "1.8E 2650", 7.25, 3.5, 4.0)
    assert spec["Fb1"] == 2650 and spec["Fv1"] == 285 and spec["CV1"] == pytest.approx((12 / 7.25) ** (1 / 9))
    sq = scl.column_spec("Versa-Lam LVL", "1.8E 2650", 3.5, 3.5, 8.0)
    assert sq["Fb1"] == 2400 and sq["Fv1"] == 190
    s = ws_wood.lvl_post("LC2", "1.8E 2650", 3.5, 7.25, 12, [dict(case="D", P=3000.0)], _combos(), 1.0, 1.0, "pinned top and bottom",
                         lu2_ft=4.0, lateral=[dict(case="W", kind="uniform", w=60.0)])
    r = {x.check: x for x in s.rows}
    Emin = scl.emin(1.7e6)
    FcE1, FcE2 = 0.822 * Emin / (144 / 7.25) ** 2, 0.822 * Emin / (48 / 3.5) ** 2
    Fcs = 3000 * 1.6
    a = min(FcE1, FcE2) / Fcs
    CP = (1 + a) / 1.8 - ((1 + a) ** 2 / 3.24 - a / 0.9) ** 0.5
    fc, fb1 = 3000 / 25.375, 7776 / (3.5 * 7.25 ** 2 / 6)
    # CL: lu = 48 in, lu/d = 6.62 < 7: le = 2.06 lu = 98.88; RB = sqrt(98.88 x 7.25 / 12.25) = 7.650; FbE = 1.2 Emin / 58.52
    FbE = 1.2 * Emin / (2.06 * 48 * 7.25 / 3.5 ** 2)
    CV = (12 / 7.25) ** (1 / 9)
    Fbs = 2650 * 1.6 * CV
    b_ = (1 + FbE / Fbs) / 1.9
    CL = b_ - (b_ * b_ - FbE / Fbs / 0.95) ** 0.5
    hand = (fc / (Fcs * CP)) ** 2 + fb1 / (Fbs * CL * (1 - fc / FcE1))
    assert r["compression with bending"].demand == pytest.approx(hand, rel=2e-3)
    assert r["shear"].demand == pytest.approx(1.5 * 216 / 25.375, abs=0.05) and r["shear"].capacity == pytest.approx(285 * 1.6)
    assert r["stability under bending"].demand == pytest.approx(fc / FcE2 + (fb1 / FbE) ** 2, rel=2e-3)
