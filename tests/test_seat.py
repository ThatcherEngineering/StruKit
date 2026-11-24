"""Unstiffened seated connection against AISC Design Examples v16.0: Example II.A-13 (W21x62 on an L8x4x5/8 seat 8 in. long, 5/16 in. welds) and
Example II.A-12A (W16x50; its tabulated bolt strength, 107 / 71.6 kips, is six 3/4 in. Group 120-N bolts in single shear), whose seat and weld strengths are the Manual Table 10-5 / 10-6 values."""
import pytest
from strukit.ws_more import seat_sheet
from strukit.ws_steel_beam import Combo

LOADS = [dict(case="D", P=9.0), dict(case="L", P=27.5)]


def _cb(method):
    return [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t")] if method == "LRFD" else [Combo("D + L", {"D": 1.0, "L": 1.0}, "t")]


def test_example_IIA13_welded():
    for method, R, seat, weld in (("LRFD", 54.8, 113, 66.7), ("ASD", 36.5, 74.9, 44.5)):
        s = seat_sheet("SE", "W21X62", 50, "x", 0.625, 8.0, 4.0, 8.0, 50, "x", "welded", LOADS, _cb(method), method, weld=0.3125, FEXX=70).seat
        assert s["R"] == pytest.approx(R, abs=0.05) and s["N"] == pytest.approx(1.12)                 # yielding and crippling lengths negative: k governs
        assert s["Rf"] == pytest.approx(seat, rel=0.01) and s["weld"] == pytest.approx(weld, rel=0.01)


def test_example_IIA12A_bolted():
    for method, bolts_ in (("LRFD", 107), ("ASD", 71.6)):
        s = seat_sheet("SE", "W16X50", 50, "x", 0.625, 8.0, 4.0, 6.0, 50, "x", "bolted", LOADS, _cb(method), method, n_bolts=6, d=0.75, group="A325", threads="N").seat
        assert s["bolts"] == pytest.approx(bolts_, rel=0.01)
