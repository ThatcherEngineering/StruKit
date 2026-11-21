"""Steel beam worksheet against AISC Design Examples v16.0, Examples F.1-1A and F.1-3A/B.

F.1-1A: W18x50, 35 ft simple span, wD = 0.45, wL = 0.75 kip/ft, continuously braced,
live-load deflection limit L/360. Printed: Mu = 266, Ma = 184 kip-ft; phi Mn = 379,
Mn/Omega = 252 kip-ft; Delta max allowed = 1.17 in.
F.1-3: same beam braced at ends and midspan: Cb = 1.30, Mn/Omega = 192, phi Mn = 288.
"""
import pytest

from strukit.ws_steel_beam import Combo, DeflCheck, WorksheetError, run

LOADS = [dict(case="D", kind="uniform", w=0.45), dict(case="L", kind="uniform", w=0.75)]
ASD = [Combo("D + L", {"D": 1, "L": 1}, "ASCE/SEI 7 Ch. 2 (as used in AISC Example F.1-1A)")]
LRFD = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "ASCE/SEI 7 Ch. 2 (as used in AISC Example F.1-1A)")]
DEFL = [DeflCheck("live", {"L": 1}, 360, "limit given in AISC Example F.1-1A")]


def near(a, b, tol=5e-3):
    return a == pytest.approx(b, rel=tol)


def row(sheet, name):
    return next(r for r in sheet.rows if r.check == name)


def test_example_F_1_1A_asd_and_lrfd():
    a = run("B1", "W18x50", 50, 35, LOADS, ASD, DEFL, "continuous", "ASD", False)
    l = run("B1", "W18x50", 50, 35, LOADS, LRFD, DEFL, "continuous", "LRFD", False)
    assert near(row(a, "flexure").demand, 184) and near(row(a, "flexure").capacity, 252)
    assert near(row(l, "flexure").demand, 266) and near(row(l, "flexure").capacity, 379)
    assert near(row(a, "shear").demand, 1.20 * 35 / 2)
    d = row(a, "deflection, live")
    assert near(d.capacity, 1.17)
    assert near(d.demand, 5 * 0.75 / 12 * 420 ** 4 / (384 * 29000 * 800), 2e-3)   # 1.09 in
    assert a.ok and a.reactions["D + L"][0] == pytest.approx(21.0, rel=1e-3)


def test_example_F_1_3_braced_at_midspan():
    a = run("B1", "W18x50", 50, 35, LOADS, ASD, DEFL, [17.5], "ASD", False)
    l = run("B1", "W18x50", 50, 35, LOADS, LRFD, DEFL, [17.5], "LRFD", False)
    assert "Cb = 1.30" in row(a, "flexure").note
    assert near(row(a, "flexure").capacity, 192) and near(row(l, "flexure").capacity, 288)
    assert row(a, "flexure").status == "OK"           # 184 < 192


def test_unbraced_beam_is_flagged_and_self_weight_is_stated():
    a = run("B1", "W18x50", 50, 35, LOADS, ASD, DEFL, [], "ASD", True)
    assert row(a, "flexure").status == "FLAG" and not a.ok
    assert any("self-weight (50 lb/ft" in s for s in a.assumptions)
    assert near(row(a, "shear").demand, (1.20 + 0.050) * 35 / 2)
    b = run("B1", "W18x50", 50, 35, LOADS, ASD, [], "continuous", "ASD", False)
    assert any("NOT added" in s for s in b.assumptions)
    assert any("deflection is not checked" in s for s in b.assumptions)


def test_missing_inputs_stop():
    with pytest.raises(WorksheetError, match="no load combinations"):
        run("B1", "W18x50", 50, 35, LOADS, [], DEFL, "continuous", "ASD", False)
    with pytest.raises(WorksheetError, match="self-weight"):
        run("B1", "W18x50", 50, 35, LOADS, ASD, DEFL, "continuous", "ASD", None)
