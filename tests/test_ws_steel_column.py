"""Steel column worksheet against AISC Design Examples v16.0, Example E.1.

E.1: W14 column, 30 ft, pinned top and bottom, PD = 140 kips, PL = 420 kips.
Pu = 1.2(140) + 1.6(420) = 840 kips; Pa = 140 + 420 = 560 kips.
E.1C (W14x132, unbraced 30 ft both axes): phi Pn = 892 kips, Pn/Omega = 598 kips.
E.1D (W14x90, braced at mid-height about y): phi Pn = 927 kips, Pn/Omega = 617 kips.
"""
import pytest

from strukit.ws_steel_beam import Combo, WorksheetError
from strukit.ws_steel_column import run

LOADS = [dict(case="D", P=140.0), dict(case="L", P=420.0)]
LRFD = [Combo("1.4D", {"D": 1.4}, "given"), Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "given")]
ASD = [Combo("D + L", {"D": 1, "L": 1}, "given")]


def test_E1C_lrfd_and_asd():
    s = run("C1", "W14x132", 50, 30, LOADS, LRFD, 1.0, 1.0, "pinned ends", "LRFD", False)
    r = s.rows[0]
    assert s.governing == "1.2D + 1.6L" and r.demand == pytest.approx(840)
    assert r.capacity == pytest.approx(892, rel=5e-3) and r.status == "OK"
    s = run("C1", "W14x132", 50, 30, LOADS, ASD, 1.0, 1.0, "pinned ends", "ASD", False)
    assert s.rows[0].demand == pytest.approx(560) and s.rows[0].capacity == pytest.approx(598, rel=1e-2)


def test_E1D_braced_at_mid_height_about_y():
    s = run("C2", "W14x90", 50, 30, LOADS, LRFD, 1.0, 1.0, "pinned ends", "LRFD", False, Ly_ft=15)
    assert s.rows[0].capacity == pytest.approx(927, rel=5e-3) and "about x" in s.rows[0].source


def test_self_weight_added_to_dead():
    s = run("C1", "W14x132", 50, 30, LOADS, ASD, 1.0, 1.0, "pinned ends", "ASD", True)
    assert s.rows[0].demand == pytest.approx(560 + 0.132 * 30)


def test_missing_inputs_stop():
    with pytest.raises(WorksheetError):
        run("C1", "W14x132", 50, 30, LOADS, [], 1.0, 1.0, "pinned", "ASD", False)
    with pytest.raises(WorksheetError):
        run("C1", "W14x132", 50, 30, LOADS, ASD, 1.0, 1.0, "", "ASD", False)
    with pytest.raises(WorksheetError):
        run("C1", "W14x132", 50, 30, LOADS, ASD, None, 1.0, "pinned", "ASD", False)
