"""Independent validation: AISC Design Examples v16.0, Part I, Chapter E.

Reference values are the numbers printed in each example (three significant figures).
"""
import math

import pytest

from strukit import shapes
from strukit.steel_beam import SteelInputError
from strukit.steel_column import check

FY = 50.0


def near(a, b, tol=5e-3):
    return a == pytest.approx(b, rel=tol)


def test_example_E_1C_W14x132_30ft_both_axes():
    # Ag = 38.8, ry = 3.76: Lc/r = 95.7; phi Pn = 892 kips; Pn/Omega = 598 kips.
    # The example takes phi Fn = 23.0 and Fn/Omega = 15.4 ksi by interpolating Manual
    # Table 4-14. Direct calculation gives Fn/Omega = 15.3 ksi, so the ASD value is
    # compared at 1 %.
    w = shapes.get("W14x132")
    assert (w["A"], w["rx"], w["ry"]) == (38.8, 6.28, 3.76)
    r = check(w, FY, Lcx=360, Lcy=360)
    assert near(r.slenderness, 95.7) and "about y" in r.governs
    assert near(check(w, FY, 360, 360, method="LRFD").P_avail, 892)
    assert near(r.P_avail, 598, 1e-2)


def test_example_E_1D_W14x90_x_30ft_y_15ft():
    # Ag = 26.5, rx = 6.14, ry = 3.70: Lcx/rx = 58.6 governs (Lcy/ry = 48.6);
    # Fe = 83.3 ksi; Fn = 38.9 ksi; Pn = 1,030 kips; phi Pn = 927; Pn/Omega = 617.
    w = shapes.get("W14x90")
    r = check(w, FY, Lcx=360, Lcy=180)
    lines = {x.label: x.value for x in r.lines}
    assert near(lines["Lcx / rx"], 58.6) and near(lines["Lcy / ry"], 48.6)
    assert "about x" in r.governs
    assert near(lines["Fe"], 83.3) and near(r.Fn, 38.9)
    assert near(r.Pn, 1030)
    assert near(check(w, FY, 360, 180, method="LRFD").P_avail, 927)
    assert near(r.P_avail, 617)


def test_elastic_range_uses_E3_3():
    # hand check of the long-column branch: Lc/r > 4.71 sqrt(E/Fy) = 113
    w = shapes.get("W8x31")
    Lc = 150 * w["ry"]
    r = check(w, FY, Lcx=Lc, Lcy=Lc)
    Fe = math.pi ** 2 * 29000 / 150 ** 2
    assert near(r.Fn, 0.877 * Fe, 1e-6)
    assert any(x.source == "Eq. E3-3" for x in r.lines)


def test_torsional_buckling_by_hand():
    # Eq. E4-2 by hand for a long torsional length on a W14x90
    w = shapes.get("W14x90")
    Lcz = 480.0
    Fez = (math.pi ** 2 * 29000 * w["Cw"] / Lcz ** 2 + 11200 * w["J"]) / (w["Ix"] + w["Iy"])
    r = check(w, FY, Lcx=120, Lcy=120, Lcz=Lcz)
    assert "torsional" in r.governs
    assert near(r.Fn, 0.658 ** (FY / Fez) * FY, 1e-6)


def test_slender_and_missing_inputs_stop():
    with pytest.raises(SteelInputError, match="slender element"):
        check(dict(shapes.get("W14x90"), h_tw=60.0), FY, 120, 120)
    with pytest.raises(SteelInputError, match="missing section properties: A"):
        check({k: v for k, v in shapes.get("W14x90").items() if k != "A"}, FY, 120, 120)
