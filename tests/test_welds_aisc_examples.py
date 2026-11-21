"""Independent validation: AISC Design Examples v16.0, Part I, Chapter J (welds).

Reference values are the numbers printed in each example (three significant figures).
"""
import pytest

from strukit.steel_beam import SteelInputError
from strukit.welds import fillet, max_fillet_size, min_fillet_size


def near(a, b, tol=5e-3):
    return a == pytest.approx(b, rel=tol)


def test_example_J_1_fillet_weld_in_longitudinal_shear():
    # 1/4 in plate lapped on a 3/8 in plate, two 3/16 in fillets, 27 in long each, E70,
    # end loaded. Printed: max size 3/16 in, min size 1/8 in, 5.57 kip/in, beta = 0.912,
    # Rn = 274 kips, phi Rn = 206 kips, Rn/Omega = 137 kips.
    # Base metal (Fu = 65 ksi, 1/4 in): Rn = 527 kips, 395 / 264 kips.
    assert max_fillet_size(0.25) == pytest.approx(3 / 16)
    assert min_fillet_size(0.25) == pytest.approx(1 / 8)
    r = fillet(3 / 16, 27, 2, 70, theta_deg=0, end_loaded=True, t_thinner=0.25, t_edge=0.25)
    lines = {x.label: x.value for x in r.lines}
    assert near(lines["Rn per inch, one line"], 5.57)
    assert near(lines["beta"], 0.912)
    assert near(r.Rn, 274) and near(r.R_avail, 137)
    assert near(fillet(3 / 16, 27, 2, 70, end_loaded=True, method="LRFD").R_avail, 206)
    assert r.flags == []
    bm = fillet(3 / 16, 27, 2, 70, end_loaded=True, base_t=0.25, base_Fu=65)
    assert near(next(x.value for x in bm.lines if x.label == "Rn, base metal"), 527)
    assert "weld metal" in bm.governs


def test_example_J_2A_fillet_weld_loaded_at_60_degrees():
    # 5/16 in fillets both sides, E70, theta = 60 deg. Printed: kds = 1.40,
    # Rn = 13.0 kip/in per side; phi Rn = 19.5 kip/in and Rn/Omega = 13.0 kip/in for two
    # sides; required length 15.4 in for 300 kips (LRFD) / 200 kips (ASD).
    r = fillet(5 / 16, 16, 2, 70, theta_deg=60)                  # the 16 in weld chosen
    lines = {x.label: x.value for x in r.lines}
    assert near(lines["kds"], 1.40)
    assert near(lines["Rn per inch, one line"], 13.0)
    lrfd = fillet(5 / 16, 16, 2, 70, theta_deg=60, method="LRFD")
    asd = fillet(5 / 16, 16, 2, 70, theta_deg=60)
    assert near(lrfd.R_avail / 16, 19.5) and near(asd.R_avail / 16, 13.0)
    assert near(300 / (lrfd.R_avail / 16), 15.4) and near(200 / (asd.R_avail / 16), 15.4)
    assert lrfd.R_avail > 300 and asd.R_avail > 200              # l = 16 in works


def test_size_limits_and_short_welds_are_flagged():
    assert min_fillet_size(0.5) == 3 / 16 and min_fillet_size(0.75) == 1 / 4
    assert min_fillet_size(1.0) == 5 / 16                        # Table J2.4
    assert max_fillet_size(0.1875) == 0.1875 and max_fillet_size(0.5) == 0.4375   # J2.2b(b)
    r = fillet(1 / 8, 6, 1, 70, t_thinner=0.625, t_edge=0.25)
    assert any("Table J2.4" in f for f in r.flags)
    assert any("J2.2b(b)" in f for f in fillet(1 / 4, 6, 1, 70, t_edge=0.25).flags)
    short = fillet(1 / 4, 0.8, 1, 70)                            # shorter than 4w = 1 in
    assert any("J2.2b(c)" in f for f in short.flags)
    assert short.Rn == pytest.approx(0.60 * 70 * (0.2 / 2 ** 0.5) * 0.8)


def test_very_long_end_loaded_weld_and_bad_input():
    r = fillet(1 / 4, 100, 1, 70, end_loaded=True)               # l/w = 400 > 300
    assert r.Rn == pytest.approx(0.60 * 70 * (0.25 / 2 ** 0.5) * 180 * 0.25)
    with pytest.raises(SteelInputError, match="theta"):
        fillet(1 / 4, 6, 1, 70, theta_deg=120)
    with pytest.raises(SteelInputError, match="both base_t and base_Fu"):
        fillet(1 / 4, 6, 1, 70, base_t=0.25)
