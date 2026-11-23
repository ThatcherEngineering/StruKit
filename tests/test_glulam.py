"""Glulam beams, 2018 NDS Chapter 5 and Supplement Table 5A.

Independent reference: Boise Glulam Specifier Guide GLM-5000, "24F-V4 Design Values"
(allowable shear, and allowable positive moment with the volume factor at a 21 ft span):
  3-1/8 x 12:  shear 6,625 lb, moment 15,000 lb-ft
  5-1/2 x 18:  shear 17,490 lb, moment 56,638 lb-ft
  5-1/2 x 22-1/2: shear 21,863 lb, moment 86,544 lb-ft
  5-1/2 x 12: moment 26,214 lb-ft (12 in. deep: 5.5 x 144 / 6 = 132 in3)
and its note: multiply the moment by (21 / span)^(1/10) for longer spans.
"""
import pytest

from strukit import glulam, ws_wood
from strukit.ws_steel_beam import DeflCheck
from tests.test_lvl import _combos


def test_table_5a():
    v = glulam.values("24F-1.8E")
    assert (v["Fb"], v["Fb_neg"], v["Fc_perp"], v["Fv"], v["E"], v["Ey_min"]) == (2400, 1450, 650, 265, 1.8e6, 0.85e6)
    v = glulam.values("16F-1.3E")
    assert (v["Fb"], v["Fc_perp"], v["Fv"], v["E"], v["Ey_min"]) == (1600, 315, 195, 1.3e6, 0.58e6)
    assert glulam.values("24F-V4 DF/DF")["Fb_neg"] == 1850 and glulam.values("30F-2.1E SP")["sp_only"]


def test_allowable_moment_and_shear_match_the_boise_guide():
    v = glulam.values("24F-V4 DF/DF")
    for b, d, V, M in ((3.125, 12, 6625, 15000), (5.5, 18, 17490, 56638), (5.5, 22.5, 21863, 86544), (5.5, 12, None, 26214)):
        if V:
            assert v["Fv"] * b * d / 1.5 == pytest.approx(V, abs=1)
        assert v["Fb"] * glulam.volume_factor(21, d, b, False) * b * d * d / 6 / 12 == pytest.approx(M, abs=3)
    assert glulam.volume_factor(32, 18, 5.5, False) == pytest.approx(glulam.volume_factor(21, 18, 5.5, False) * (21 / 32) ** 0.1)
    assert glulam.volume_factor(21, 12, 3.125, False) == 1.0
    assert glulam.volume_factor(40, 24, 6.75, True) == pytest.approx((21 / 40 * 12 / 24 * 5.125 / 6.75) ** 0.05)


def test_beam_sheet_by_hand():
    # 5.5 x 18 24F-V4, 24 ft, D 300 + L 600 plf, braced, bearing 4 in, dry
    # M = 900 x 576 / 8 = 64,800 lb-ft; S = 297 in3; fb = 2,618.2 psi
    # CV = (21/24 x 12/18 x 5.125/5.5)^0.1 = 0.9409; Fb' = 2,258.1 psi  -> over
    # V = 10,800 lb; fv = 1.5 x 10,800 / 99 = 163.6 psi against 265
    # bearing 10,800 / (5.5 x 4) = 490.9 against 650
    # deflection D+L: 5 x 75 x 288^4 / (384 x 1.8e6 x 2,673) = 1.396 in
    loads = [dict(case="D", kind="uniform", w=300.0), dict(case="L", kind="uniform", w=600.0)]
    s = ws_wood.glulam_beam("GB1", "24F-V4 DF/DF", False, 5.5, 18, 24, loads, _combos(), [DeflCheck("total", {"D": 1, "L": 1}, 240, "typed")],
                            0.0, 4.0, False)
    r = {x.check: x for x in s.rows}
    assert r["bending"].demand == pytest.approx(2618.2, abs=0.1) and r["bending"].capacity == pytest.approx(2258.1, abs=0.5)
    assert r["bending"].status == "FLAG"
    assert r["shear"].demand == pytest.approx(163.6, abs=0.1) and r["bearing at support"].demand == pytest.approx(490.9, abs=0.1)
    assert r["deflection, total"].demand == pytest.approx(1.396, abs=0.002)
    wet = ws_wood.glulam_beam("GB1", "24F-V4 DF/DF", False, 5.5, 18, 24, loads, _combos(), [], 0.0, 4.0, True)
    rw = {x.check: x for x in wet.rows}
    assert rw["bending"].capacity == pytest.approx(2258.1 * 0.8, abs=0.5) and rw["shear"].capacity == pytest.approx(265 * 0.875)
    assert rw["bearing at support"].capacity == pytest.approx(650 * 0.53)


def test_unbraced_uses_ey_min_and_the_lesser_factor():
    loads = [dict(case="D", kind="uniform", w=100.0), dict(case="L", kind="uniform", w=200.0)]
    s = ws_wood.glulam_beam("GB2", "24F-V4 DF/DF", False, 3.125, 18, 24, loads, _combos(), [], 24.0, 4.0, False)
    # lu/d = 16 > 14.3: le = 1.84 lu = 529.9 in; RB = sqrt(529.9 x 18 / 3.125^2) = 31.25; FbE = 1.2 x 850,000 / 976.7 = 1,044.3
    FbE = 1.2 * 0.85e6 / (1.84 * 288 * 18 / 3.125 ** 2)
    a = (1 + FbE / 2400) / 1.9
    CL = a - (a * a - FbE / 2400 / 0.95) ** 0.5
    assert s.rows[0].capacity == pytest.approx(2400 * CL, rel=1e-3)
    with pytest.raises(Exception, match="Southern Pine"):
        ws_wood.glulam_beam("GB2", "30F-2.1E SP", False, 5, 18, 24, loads, _combos(), [], 0, 4.0, False)


# ---- columns ------------------------------------------------------------------------------
# References: Boise Glulam Specifier Guide GLM-5000, "BOISE GLULAM Column Tables", Combination 3
# (2024 NDS, Ke = 1.0, eccentricity 0.167 x the column dimension). The 2018 NDS calculation
# with e = d/6 about the weak axis reproduces the table for 3-1/8 in. columns and 5-1/8 x 6
# at 12 ft; for other sizes the table is lower and, by Zach's ruling of 2026-11-23, governs.
def _calc_load(b, d, L, CD=1.0):
    from strukit import scl, wood
    v = glulam.column_values("3 (DF L2D)", 4)
    le, d1, d2 = L * 12.0, max(b, d), min(b, d)
    Fcs = v["Fc"] * CD
    CP, _ = wood.column_stability(Fcs, v["Emin"], le, d1, le, d2, c=0.9)
    F1, F2 = 0.822 * v["Emin"] / (le / d1) ** 2, 0.822 * v["Emin"] / (le / d2) ** 2
    lo, hi = 0.0, Fcs * CP * b * d
    for _ in range(50):
        P = (lo + hi) / 2
        r = scl.eccentric_column(P / (b * d), Fcs * CP, d1, d2, 0.0, d2 / 6, v["Fbx"] * CD, v["Fby"] * CD, F1, F2)[0]
        lo, hi = (P, hi) if r < 1 else (lo, P)
    return lo


def test_table_5b_and_boise_table_data():
    v = glulam.column_values("3 (DF L2D)", 4)
    assert (v["Fc"], v["Fby"], v["Fbx"], v["Emin"]) == (2300, 2100, 2000, 1.0e6)
    assert glulam.column_values("3 (DF L2D)", 3)["Fc"] == 1900 and glulam.column_values("3 (DF L2D)", 2)["Fby"] == 1550
    assert glulam.column_values("14 (HF L3)", 5)["Fc"] == 1100
    T = glulam._boise()
    assert len(T) == 537
    assert T[(3.125, 6.0, 8, "100%")] == 9460 and T[(5.125, 7.5, 12, "115%")] == 20160 and T[(8.75, 9.0, 30, "125%")] == 25780
    assert T[(5.5, 7.5, 8, "100%")] == 40390 and (5.5, 7.5, 7, "100%") not in T and T[(3.5, 7.5, 13, "115%")] == 7890


def test_calculation_reproduces_the_boise_table_where_it_can():
    for b, d, L, tab in ((3.125, 6, 10, 6750), (3.125, 7.5, 10, 8440), (3.125, 6, 8, 9460), (5.125, 6, 12, 17350)):
        assert _calc_load(b, d, L) == pytest.approx(tab, rel=0.012)
    assert _calc_load(5.125, 7.5, 12) > 19400 * 1.05                       # the table is lower here; it governs


def test_column_sheet_takes_the_table_where_it_is_lower():
    # 5-1/8 x 7-1/2, 12 ft, D 6,000 + L 14,000 = 20,000 lb at CD 1.0: over the table's 19,400 lb, under the calculation
    loads = [dict(case="D", P=6000.0), dict(case="L", P=14000.0)]
    s = ws_wood.glulam_post("GC1", "3 (DF L2D)", 5.125, 7.5, 5, 12, loads, _combos(), 1.0, 1.0, "pinned", e_b_in=5.125 / 6)
    r = {x.check: x for x in s.rows}
    assert r["axial load, column table"].capacity == 19400 and r["axial load, column table"].status == "FLAG"
    assert r["compression with eccentric load"].demand < 1.0 and r["compression"].status == "OK"
    # dead load only uses 0.9 x the 100 percent value; a 12.5 ft effective length reads the 13 ft row
    s2 = ws_wood.glulam_post("GC1", "3 (DF L2D)", 5.125, 7.5, 5, 12.5, [dict(case="D", P=6000.0)], _combos(), 1.0, 1.0, "pinned")
    r2 = {x.check: x for x in s2.rows}
    assert r2["axial load, column table"].capacity == pytest.approx(0.9 * 17420)
    # other combinations and sizes not in the table: no table row
    s3 = ws_wood.glulam_post("GC2", "2 (DF L2)", 5.125, 7.5, 5, 12, loads, _combos(), 1.0, 1.0, "pinned")
    assert all("table" not in x.check for x in s3.rows)
    s4 = ws_wood.glulam_post("GC3", "3 (DF L2D)", 6.75, 9, 6, 12, loads, _combos(), 1.0, 1.0, "pinned")
    assert all("table" not in x.check for x in s4.rows)
    # concentric check by hand: 5-1/8 x 7-1/2, 12 ft: le/d = 28.10; FcE = 0.822e6 / 789.5 = 1,041.2; Fc* = 2,300
    a = 0.822e6 / (144 / 5.125) ** 2 / 2300
    CP = (1 + a) / 1.8 - ((1 + a) ** 2 / 3.24 - a / 0.9) ** 0.5
    assert r["compression"].capacity == pytest.approx(2300 * CP, rel=1e-6)
