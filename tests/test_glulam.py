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
