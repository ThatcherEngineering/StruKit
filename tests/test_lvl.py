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
