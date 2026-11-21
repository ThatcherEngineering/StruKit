"""Independent validation: AISC Design Examples v16.0 (Companion to the Steel
Construction Manual, Volume 1), Part I, Chapters F and G.

Each test reproduces a published example. Reference values are the numbers printed in
the example (three significant figures), so the tolerance is 0.5 % unless noted.
Section properties come from the AISC Shapes Database v16.0.
"""
import pytest

from strukit import shapes
from strukit.steel_beam import cb_factor, check

FY = 50.0          # ASTM A992
TOL = 5e-3


def near(a, b, tol=TOL):
    return a == pytest.approx(b, rel=tol)


def test_shapes_database_values_used_by_the_examples():
    w = shapes.get("W18x50")
    # Example F.1-1B / F.1-2B, "From AISC Manual Table 1-1"
    assert (w["Zx"], w["Sx"], w["ry"], w["J"], w["rts"], w["ho"]) == (101, 88.9, 1.65, 1.24, 1.98, 17.4)
    assert shapes.get("W21X48")["bf_2tf"] == 9.47                      # Example F.3B
    assert (shapes.get("W24x62")["d"], shapes.get("W24x62")["tw"]) == (23.7, 0.43)   # G.1B
    with pytest.raises(shapes.ShapeError):
        shapes.get("W18x51")


def test_example_F_1_1B_continuously_braced():
    # W18x50: Mn = 5,050 kip-in.; phi Mn = 379 kip-ft; Mn/Omega = 252 kip-ft
    r = check(shapes.get("W18x50"), FY, Lb=0)
    assert near(r.Mn, 5050)
    assert near(check(shapes.get("W18x50"), FY, Lb=0, method="LRFD").M_avail / 12, 379)
    assert near(r.M_avail / 12, 252)
    assert r.governs.startswith("yielding")


def test_example_F_1_2B_braced_at_third_points():
    # Lb = 11.7 ft, Cb = 1.01: Lp = 69.9 in., Lr = 203 in., Mn = 4,060 kip-in.,
    # phi Mn = 304 kip-ft, Mn/Omega = 202 kip-ft
    assert near(cb_factor(1.00, 0.972, 1.00, 0.972), 1.01)
    assert near(cb_factor(0.889, 0.306, 0.556, 0.750), 1.46)
    r = check(shapes.get("W18x50"), FY, Lb=11.7 * 12, Cb=1.01)
    lines = {x.label: x.value for x in r.lines}
    assert near(lines["Lp"], 69.9) and near(lines["Lr"], 203)
    assert near(r.Mn, 4060)
    assert near(r.M_avail / 12, 202)
    assert near(check(shapes.get("W18x50"), FY, Lb=11.7 * 12, Cb=1.01, method="LRFD").M_avail / 12, 304)


def test_example_F_1_3B_braced_at_midspan():
    # Lb = 17.5 ft, Cb = 1.30: Fcr = 43.2 ksi, Mn = 3,840 kip-in.,
    # phi Mn = 288 kip-ft, Mn/Omega = 192 kip-ft
    assert near(cb_factor(1.00, 0.438, 0.750, 0.938), 1.30)
    r = check(shapes.get("W18x50"), FY, Lb=17.5 * 12, Cb=1.30)
    lines = {x.label: x.value for x in r.lines}
    assert near(lines["Fcr"], 43.2)
    assert near(r.Mn, 3840)
    assert near(r.M_avail / 12, 192)
    assert near(check(shapes.get("W18x50"), FY, Lb=17.5 * 12, Cb=1.30, method="LRFD").M_avail / 12, 288)


def test_example_F_3B_noncompact_flange():
    # W21x48, continuously braced: lambda = 9.47, limits 9.15 / 24.1, Mp = 5,350 kip-in.,
    # Mn = 5,310 kip-in., phi Mn = 398 kip-ft, Mn/Omega = 265 kip-ft
    r = check(shapes.get("W21x48"), FY, Lb=0)
    assert r.flange == "noncompact" and r.governs.startswith("compression flange")
    assert near(r.Mn, 5310)
    assert near(r.M_avail / 12, 265)
    assert near(check(shapes.get("W21x48"), FY, Lb=0, method="LRFD").M_avail / 12, 398)


def test_example_G_1B_shear():
    # W24x62: Vn = 306 kips; phi Vn = 306 kips; Vn/Omega = 204 kips
    r = check(shapes.get("W24x62"), FY, Lb=0)
    assert near(r.Vn, 306)
    assert near(r.V_avail, 204)
    assert near(check(shapes.get("W24x62"), FY, Lb=0, method="LRFD").V_avail, 306)
