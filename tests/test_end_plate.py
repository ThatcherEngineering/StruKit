"""Shear end-plate connection against AISC Design Examples v16.0, Example II.A-11A (W18x50, 1/4 in. plate, three rows of 3/4 in. bolts)."""
import pytest
from strukit import ws_more
from strukit.ws_steel_beam import Combo


def _run(method):
    cb = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "test")] if method == "LRFD" else [Combo("D + L", {"D": 1.0, "L": 1.0}, "test")]
    return ws_more.end_plate_sheet("EP", "W18X50", 50, 65, "x", 0.25, 6.0, 8.5, 50, 65, "x", 0.75, "A325", "N", 3, 3.0, 1.25, 3.5, 0.1875, 70,
                                   [dict(case="D", P=10.0), dict(case="L", P=30.0)], cb, method).end_plate


def test_example_IIA11A():
    L, A = _run("LRFD"), _run("ASD")
    assert L["R"] == pytest.approx(60.0) and A["R"] == pytest.approx(40.0)
    for got, lr, asd in (("Rb", 96.4, 64.1), ("Vy", 128, 85.3), ("Vr", 86.3, 57.5), ("Rbs", 93.8, 62.5), ("Rw", 67.9, 45.2)):
        assert L[got] == pytest.approx(lr, rel=0.01) and A[got] == pytest.approx(asd, rel=0.012), got
    assert L["t_min"] == pytest.approx(0.286, abs=0.001)
