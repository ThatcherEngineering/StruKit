"""Base plate with moment. AISC Design Guide 1 and any published worked example of a
moment base plate are not on file, so this is checked by equilibrium, by hand numbers and
by its reduction to the axial case (AISC Design Example J.6)."""
import math

import pytest

from strukit import base_plate as bp
from strukit import ws_more
from strukit.steel_beam import SteelInputError


def test_equilibrium_with_rod_tension():
    # N 20, B 16, rods 2 in from the ends (f = 8 in), fp = 2.0 ksi; P = 60 kips, M = 900 kip-in
    c = bp.moment_case("U", 60, 900, 10, 8, 20, 16, 8, 2.0, 36, "LRFD", 2)
    q = 2.0 * 16
    assert c.uplift and q * c.Y - c.T == pytest.approx(60)                       # vertical forces
    assert q * c.Y * (10 - c.Y / 2) + c.T * 8 == pytest.approx(900)              # moments about the plate centre
    # by hand: Y = 18 - sqrt(18^2 - 2 (900 + 480) / 32) = 18 - sqrt(237.75) = 2.5809 in; T = 32 x 2.5809 - 60 = 22.59
    assert c.Y == pytest.approx(2.5809, abs=1e-3) and c.T == pytest.approx(22.59, abs=0.01)


def test_small_eccentricity_has_no_rod_tension():
    # e = 1.5 in < N/2 - P/(2q) = 10 - 200/64 = 6.875 in: Y = N - 2e = 17 in, stress = 200 / (16 x 17)
    c = bp.moment_case("S", 200, 300, 10, 8, 20, 16, 8, 2.0, 36, "LRFD", 2)
    assert not c.uplift and c.T == 0 and c.Y == pytest.approx(17.0) and c.f_bearing == pytest.approx(200 / 272)


def test_zero_moment_matches_example_J6_thickness():
    # W12x96 on 22 x 22, Pu = 690: n = 6.12 in governs, t = 1.54 in (lambda n' is smaller)
    c = bp.moment_case("A", 690, 0, 12.7, 12.2, 22, 22, 8, 99.0, 50, "LRFD", 2)
    assert c.t_req == pytest.approx(1.54, abs=0.006) and c.t_govern.endswith("n")


def test_limits():
    with pytest.raises(SteelInputError):
        bp.moment_case("big", 60, 20000, 10, 8, 20, 16, 8, 2.0, 36, "LRFD", 2)   # plate too small
    with pytest.raises(SteelInputError):
        bp.moment_case("up", -50, 100, 10, 8, 20, 16, 8, 2.0, 36, "LRFD", 2)     # net uplift, little moment
    c = bp.moment_case("up2", -10, 900, 10, 8, 20, 16, 8, 2.0, 36, "LRFD", 2)     # uplift with moment: still balances
    assert 32 * c.Y - c.T == pytest.approx(-10)


def test_worksheet_rows_and_rod_strength():
    cases = [dict(name="D + S", P=13.4, M=0.4, V=0.03), dict(name="D + 0.6W", P=4.4, M=34.5, V=2.4)]
    s = ws_more.base_plate_moment_sheet("BP2", "W8X31", 16, 12, 1.0, 36, 3000, (30, 30), 0.75, 58, "ASTM F1554 Grade 36 (typed)",
                                        2, 1.5, 1.5, 2, cases, "ASD")
    r = {x.check: x for x in s.rows}
    Ab = math.pi * 0.75 ** 2 / 4
    assert r["anchor rod shear"].capacity == pytest.approx(0.45 * 58 * Ab / 2.0)        # Table J3.2, Omega = 2.00
    assert r["anchor rod shear"].demand == pytest.approx(1.2)
    assert r["anchor rod tension"].capacity <= 0.75 * 58 * Ab / 2.0 + 1e-9
    assert r["anchor rod tension"].combo == "D + 0.6W" and r["anchor rod tension"].demand > 0
    assert "concrete bearing stress" in r and "bearing block length" in r and "plate thickness" in r
    assert any("Chapter 17" in n for n in s.not_checked)
    with pytest.raises(Exception):
        ws_more.base_plate_moment_sheet("BP2", "W8X31", 16, 12, 1.0, 36, 3000, (30, 30), 0.75, 58, "", 2, 1.5, 1.5, 2, cases, "ASD")
