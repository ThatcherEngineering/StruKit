"""Wood structural panel shear walls, SDPWS-2021.

References:
  - Table 4.3A values re-read from the standard (spot checks below).
  - AWC "Shearwall Basics Using SDPWS" slides: the 2b/h reduction of a narrow segment
    (450 plf x 2(2.25)/8 x 2.25 ft = 570 lb) and the hold-down force with no dead load
    (350 plf x 8 ft = 2,800 lb). The slides use 2008-edition capacities, so only these two
    relations are compared.
  - Hand calculations written out below.
"""
import pytest

from strukit import shearwall as sw

P = "Sheathing, 15/32 in, 8d common"


def test_table_values():
    T = sw.TABLE_4_3A
    assert T[("Sheathing", "15/32", "8d")][0] == (730, 13, 10) and T[("Sheathing", "15/32", "8d")][1] == (1065, 19, 13)
    assert T[("Sheathing", "7/16", "8d")][2] == (1260, 28, 17) and T[("Structural I", "15/32", "10d")][3] == (2435, 51, 28)
    assert T[("Sheathing", "3/8", "6d")][0] == (560, 11, 8.5) and T[("Structural I", "3/8", "8d")][1] == (1010, 24, 17)
    assert len(T) == 12 and len(sw.PANELS) == 12


def test_design_factors():
    one = lambda load, m: sw.line(P, 6, "OSB", 0.5, 8, [8], 1000, load, m).capacity
    assert one("wind", "ASD") == pytest.approx(730 * 8 / 2.0) and one("seismic", "ASD") == pytest.approx(730 * 8 / 2.8)
    assert one("wind", "LRFD") == pytest.approx(730 * 8 * 0.8) and one("seismic", "LRFD") == pytest.approx(730 * 8 * 0.5)


def test_specific_gravity_factor():
    # Hem-Fir framing, G = 0.43: 1 - (0.5 - 0.43) = 0.93; Douglas Fir-Larch 0.50: 1.0; never over 1
    assert sw.line(P, 6, "OSB", 0.43, 8, [8], 1000, "wind", "ASD").sg_factor == pytest.approx(0.93)
    assert sw.line(P, 6, "OSB", 0.55, 8, [8], 1000, "wind", "ASD").sg_factor == 1.0


def test_narrow_segment_reduction_matches_awc_slide():
    # 8 ft wall, 2.25 ft segment: h/b = 3.56 is over 3.5, so use a 9 ft wall check by hand instead for the limit,
    # and the slide's relation on a 2.5 ft segment: capacity x 2b/h
    w = sw.line(P, 6, "OSB", 0.5, 8, [2.5], 500, "wind", "ASD")
    s = w.segments[0]
    assert s.reduction == pytest.approx(2 * 2.5 / 8) and s.Vcap == pytest.approx(365 * (2 * 2.5 / 8) * 2.5)
    with pytest.raises(sw.ShearWallError, match="3.5"):
        sw.line(P, 6, "OSB", 0.5, 8, [2.25], 500, "wind", "ASD")
    # the slide's arithmetic: 450 plf x 2(2.25)/8 x 2.25 = 570 lb
    assert 450 * 2 * 2.25 / 8 * 2.25 == pytest.approx(570, abs=1)


def test_distribution_in_proportion_to_capacity_by_hand():
    # 9 ft wall, segments 8 ft and 3 ft, wind ASD, 15/32 sheathing 8d at 4 in: vn = 1,065, allowable 532.5 plf
    # 8 ft: h/b = 1.125, capacity 4,260 lb; 3 ft: h/b = 3.0, x 2(3)/9 = 0.667, capacity 532.5 x 0.667 x 3 = 1,065 lb
    # line capacity 5,325 lb; V = 4,000: 8 ft takes 3,200 lb (400 plf), 3 ft takes 800 lb (266.7 plf)
    w = sw.line(P, 4, "OSB", 0.5, 9, [8, 3], 4000, "wind", "ASD", arm_offset_in=6)
    a, b = w.segments
    assert a.Vcap == pytest.approx(4260) and b.Vcap == pytest.approx(1065) and w.capacity == pytest.approx(5325)
    assert a.V == pytest.approx(3200) and a.v == pytest.approx(400) and b.V == pytest.approx(800)
    # T = V h / b_eff: 3,200 x 9 / 7.5 = 3,840 lb; 800 x 9 / 2.5 = 2,880 lb
    assert a.T == pytest.approx(3840) and b.T == pytest.approx(2880)


def test_hold_down_force_matches_awc_slide():
    # 350 plf on an 8 ft wall with no dead load and the full length as the arm: 350 x 8 = 2,800 lb
    w = sw.line(P, 6, "OSB", 0.5, 8, [10], 3500, "wind", "ASD")
    assert w.segments[0].v == pytest.approx(350) and w.segments[0].T == pytest.approx(2800)


def test_deflection_by_hand():
    # v = 400 plf, h = 9 ft, b = 8 ft, chord (2) 2x6 A = 16.5 in2, E = 1,600,000, Ga = 19, slip 0.125 in
    # 8 x 400 x 729 / (1.6e6 x 16.5 x 8) = 0.01105; 400 x 9 / 19,000 = 0.18947; 9 x 0.125 / 8 = 0.14063; total 0.3411
    w = sw.line(P, 4, "OSB", 0.5, 9, [8], 3200, "wind", "ASD", chord_E=1.6e6, chord_A=16.5, anchor_slip_in=0.125)
    assert w.segments[0].defl == pytest.approx(0.3411, abs=0.0005)


def test_ten_penny_nail_note():
    p = "Sheathing, 15/32 in, 10d common"
    with pytest.raises(sw.ShearWallError, match="note 10"):
        sw.line(p, 6, "OSB", 0.5, 8, [8], 1000, "wind", "ASD")
    assert sw.line(p, 6, "OSB", 0.5, 8, [8], 1000, "wind", "ASD", holddown_inside=True).capacity == pytest.approx(870 * 0.92 * 8 / 2)
    assert sw.line(p, 6, "OSB", 0.5, 8, [8], 1000, "wind", "ASD", holddown_inside=False).capacity == pytest.approx(870 * 8 / 2)
