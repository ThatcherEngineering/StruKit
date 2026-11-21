"""Base plate against AISC Design Examples v16.0, Example J.6.

W12x96 (d = 12.7, bf = 12.2 in) on a 22 x 22 in plate, Fy = 50 ksi, on a 24 x 24 in
pedestal, f'c = 3 ksi; PD = 115, PL = 345 kips. Printed:
  phi_c Pp = 875 kips, Pp/Omega_c = 583 kips; m = 4.97, n = 6.12, n' = 3.11 in;
  X = 0.788 (LRFD) / 0.789 (ASD); t min = 1.54 in (both methods).
The example sets lambda to 1 for simplicity; n governs, so t min is the same either way.
"""
import pytest

from strukit import base_plate
from strukit.steel_beam import SteelInputError


def run(method, Pr):
    A2 = base_plate.similar_area(22, 22, 24, 24)
    assert A2 == pytest.approx(576)
    return base_plate.check(12.7, 12.2, 22, 22, 50, 3.0, A2, Pr, method)


def test_example_J6_lrfd():
    r = run("LRFD", 690)
    v = {ln.label.split(" ")[0]: ln.value for ln in r.lines}
    assert r.P_avail == pytest.approx(875, rel=5e-3)
    assert v["m"] == pytest.approx(4.97, abs=0.006) and v["n"] == pytest.approx(6.12, abs=0.006) and v["n'"] == pytest.approx(3.11, abs=0.006)
    assert v["X"] == pytest.approx(0.788, abs=0.002)
    assert r.t_min == pytest.approx(1.54, abs=0.006)


def test_example_J6_asd():
    r = run("ASD", 460)
    assert r.P_avail == pytest.approx(583, rel=5e-3) and r.t_min == pytest.approx(1.54, abs=0.006)


def test_full_area_uses_J8_1_and_limits():
    r = base_plate.check(12.7, 12.2, 22, 22, 50, 3.0, 484, 400, "LRFD")
    assert r.Pp == pytest.approx(0.85 * 3 * 484)
    big = base_plate.check(12.7, 12.2, 22, 22, 50, 3.0, 484 * 9, 400, "LRFD")       # sqrt(A2/A1) = 3: capped at 1.7 f'c A1
    assert big.Pp == pytest.approx(1.7 * 3 * 484)
    with pytest.raises(SteelInputError):
        base_plate.similar_area(22, 22, 20, 24)
    with pytest.raises(SteelInputError):
        base_plate.check(12.7, 12.2, 22, 22, 50, 3.0, 576, -5, "LRFD")
