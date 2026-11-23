"""Wind velocity pressure, ASCE/SEI 7-22 Chapter 26.

References: Table 26.10-1 and Table 26.9-1 as printed (the Ke formula is checked against
the table's own values), the table's note 1 formula with the Exposure C constants
(alpha 9.8, zg 2,460 ft) as a cross-check of the tabulated Kz, and a hand calculation.
"""
import math

import pytest

from strukit import wind


def test_kz_table_and_interpolation():
    assert wind.kz("B", 10) == 0.57 and wind.kz("C", 15) == 0.85 and wind.kz("D", 500) == 1.89
    assert wind.kz("C", 30) == 0.98 and wind.kz("B", 180) == 1.11 and wind.kz("D", 100) == 1.43
    assert wind.kz("C", 35) == pytest.approx((0.98 + 1.04) / 2) and wind.kz("B", 22.5) == pytest.approx(0.64)
    assert wind.kz("B", 20, chapter_28=True) == 0.70 and wind.kz("B", 30, chapter_28=True) == 0.70 and wind.kz("C", 20, chapter_28=True) == 0.90
    with pytest.raises(wind.WindError):
        wind.kz("A", 20)
    with pytest.raises(wind.WindError):
        wind.kz("C", 600)


def test_ke_formula_matches_table_26_9_1():
    for z, k in ((0, 1.00), (1000, 0.96), (2000, 0.93), (3000, 0.90), (4000, 0.86), (5000, 0.83), (6000, 0.80)):
        assert wind.ke(z) == pytest.approx(k, abs=0.006)


def test_tabulated_kz_agrees_with_the_note_1_formula_for_exposure_c():
    for z in (15, 30, 60, 100, 200):
        assert wind.kz("C", z) == pytest.approx(2.41 * (z / 2460) ** (2 / 9.8), abs=0.011)


def test_velocity_pressure_by_hand():
    # V = 115 mi/h, Exposure C, h = 30 ft, Kzt = 1.0, Ke = 1.0: 0.00256 x 0.98 x 115^2 = 33.18 psf
    q, k = wind.velocity_pressure(115, "C", 30)
    assert k == 0.98 and q == pytest.approx(33.18, abs=0.01)
    # at 6,200 ft above sea level: Ke = e^(-0.2244) = 0.799 -> 26.51 psf
    q2, _ = wind.velocity_pressure(115, "C", 30, Ke=wind.ke(6200))
    assert q2 == pytest.approx(33.18 * math.exp(-0.0000362 * 6200), abs=0.01) and q2 == pytest.approx(26.51, abs=0.02)
    with pytest.raises(wind.WindError):
        wind.velocity_pressure(115, "C", 30, Kzt=0.9)
