"""Checks against AISC Design Guide 1, 3rd Edition (2024), worked examples and tables.

  Example 4.7-10 (low moment):   W12x96, N = B = 19 in, f'c = 4 ksi, A1 = A2, plate Fy 50
      LRFD Pu 376 kips, Mu 940 kip-in; ASD Pa 260, Ma 650: e = 2.50, Y = 14.0,
      fp = 1.41 / 0.977 ksi, t = 0.868 / 0.888 in (m), 1.16 / 1.18 in (n, controls)
  Example 4.7-11 (large moment): same column, N = 24, B = 22, rods 2.75 in from the edge
      LRFD Pu 376, Mu 3,600: Y = 8.60, Tu = 42.0; ASD Pa 260, Ma 2,500: Y = 9.10, Ta = 33.9
      t = 1.87 in (m), 1.92 in (n, controls); x = 3.35 in; tension side 0.755 / 0.829 in
      rods 18 in deep, 12 in apart: ANc = 3,560, ANco = 2,920, Nb = 125, Ncbg = 152 kips
  Table 4-1: 0.75 Ase Fu for F1554 rods; Table 4-2: 0.70 x 8 Abrg f'c pullout
"""
import math

import pytest

from strukit import anchor_rods, anchorage as A, base_plate as bp

D, BF, TF = 12.7, 12.2, 0.900
FP = {"LRFD": 0.65 * 0.85 * 4.0, "ASD": 0.85 * 4.0 / 2.31}


@pytest.mark.parametrize("method,P,M,fp,tm,tn", [("LRFD", 376, 940, 1.41, 0.868, 1.16), ("ASD", 260, 650, 0.977, 0.888, 1.18)])
def test_example_4_7_10_low_moment(method, P, M, fp, tm, tn):
    c = bp.moment_case("x", P, M, D, BF, 19, 19, 8.0, FP[method], 50, method, 2, TF)
    assert not c.uplift and c.T == 0
    assert c.e == pytest.approx(2.50) and c.Y == pytest.approx(14.0)
    assert c.f_bearing == pytest.approx(fp, abs=0.005)
    assert c.t_req == pytest.approx(tn, abs=0.01) and "cantilever n" in c.t_govern
    # the m cantilever alone, Eq. 4-51
    k = 1.49 if method == "LRFD" else 1.83
    assert k * (19 - 0.95 * D) / 2 * math.sqrt(c.f_bearing / 50) == pytest.approx(tm, abs=0.006)


@pytest.mark.parametrize("method,P,M,Y,T,tt", [("LRFD", 376, 3600, 8.60, 42.0, 0.755), ("ASD", 260, 2500, 9.10, 33.9, 0.829)])
def test_example_4_7_11_large_moment(method, P, M, Y, T, tt):
    c = bp.moment_case("x", P, M, D, BF, 24, 22, 9.25, FP[method], 50, method, 2, TF)
    assert c.uplift
    # the guide rounds q_max, Y and the radical to three figures; T is a small difference of large numbers
    assert c.Y == pytest.approx(Y, abs=0.06)
    assert c.T == pytest.approx(T, abs=1.6)
    assert c.x == pytest.approx(3.35, abs=0.005)
    assert c.t_req == pytest.approx(1.92, abs=0.01) and "cantilever n" in c.t_govern
    # tension side by Eq. 4-62 (full plate width), from the guide's own T
    k = 2.11 if method == "LRFD" else 2.58
    assert k * math.sqrt(T * c.x / (22 * 50)) == pytest.approx(tt, abs=0.003)
    # this module's 45 degree width is narrower than B here, so its tension-side demand is not less
    assert c.b_eff == pytest.approx(min(22, 2 * 2 * c.x))


def test_example_4_7_11_breakout_of_the_tension_rods():
    N, d = A.tension_breakout(18, 4000, 1, 0, 2, 12, 100, 100, 100, 100, 1.0, deep_eq_for_groups=True)
    assert d["ANc"] == pytest.approx(3560, rel=0.002)
    assert d["ANco"] == pytest.approx(2920, rel=0.002)
    assert d["Nb"] / 1000 == pytest.approx(125, abs=0.5)
    assert N / 1000 == pytest.approx(152, abs=1.0)
    # the default (Code wording) keeps Eq. 17.6.2.2.1 for a group and reports the other value
    N1, d1 = A.tension_breakout(18, 4000, 1, 0, 2, 12, 100, 100, 100, 100, 1.0)
    assert N1 < N and d1["alt"] == pytest.approx(N)


def test_table_4_1_rod_strength_and_thread_area():
    for da, grade_name, phiRn in ((0.75, "F1554 Gr. 36", 14.5), (1.0, "F1554 Gr. 36", 26.4), (1.0, "F1554 Gr. 55", 34.1),
                                  (1.5, "F1554 Gr. 105", 132), (2.0, "F1554 Gr. 36", 109)):
        nt, _ = anchor_rods.size(da)
        Fu = anchor_rods.grade(grade_name)[0]
        assert 0.75 * A.ase(da, nt) * Fu == pytest.approx(phiRn, rel=0.006)
    for da, (nt, Ab, Ase, _) in anchor_rods.SIZES.items():
        assert A.ase(da, nt) == pytest.approx(Ase, rel=0.006)
        assert math.pi / 4 * da * da == pytest.approx(Ab, rel=0.006)


def test_table_4_2_pullout():
    for da, fc, phiNp in ((0.75, 3000, 15.3), (1.0, 4000, 33.6), (1.5, 5000, 87.4)):
        assert 0.70 * 8 * anchor_rods.size(da)[1] * fc / 1000 == pytest.approx(phiNp, rel=0.005)
