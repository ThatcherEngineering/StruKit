"""Steel column worksheet against AISC Design Examples v16.0, Example E.1.

E.1: W14 column, 30 ft, pinned top and bottom, PD = 140 kips, PL = 420 kips.
Pu = 1.2(140) + 1.6(420) = 840 kips; Pa = 140 + 420 = 560 kips.
E.1C (W14x132, unbraced 30 ft both axes): phi Pn = 892 kips, Pn/Omega = 598 kips.
E.1D (W14x90, braced at mid-height about y): phi Pn = 927 kips, Pn/Omega = 617 kips.
"""
import pytest

from strukit.ws_steel_beam import Combo, WorksheetError
from strukit.ws_steel_column import run

LOADS = [dict(case="D", P=140.0), dict(case="L", P=420.0)]
LRFD = [Combo("1.4D", {"D": 1.4}, "given"), Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "given")]
ASD = [Combo("D + L", {"D": 1, "L": 1}, "given")]


def test_E1C_lrfd_and_asd():
    s = run("C1", "W14x132", 50, 30, LOADS, LRFD, 1.0, 1.0, "pinned ends", "LRFD", False)
    r = s.rows[0]
    assert s.governing == "1.2D + 1.6L" and r.demand == pytest.approx(840)
    assert r.capacity == pytest.approx(892, rel=5e-3) and r.status == "OK"
    s = run("C1", "W14x132", 50, 30, LOADS, ASD, 1.0, 1.0, "pinned ends", "ASD", False)
    assert s.rows[0].demand == pytest.approx(560) and s.rows[0].capacity == pytest.approx(598, rel=1e-2)


def test_E1D_braced_at_mid_height_about_y():
    s = run("C2", "W14x90", 50, 30, LOADS, LRFD, 1.0, 1.0, "pinned ends", "LRFD", False, Ly_ft=15)
    assert s.rows[0].capacity == pytest.approx(927, rel=5e-3) and "about x" in s.rows[0].source


def test_self_weight_added_to_dead():
    s = run("C1", "W14x132", 50, 30, LOADS, ASD, 1.0, 1.0, "pinned ends", "ASD", True)
    assert s.rows[0].demand == pytest.approx(560 + 0.132 * 30)


def test_missing_inputs_stop():
    with pytest.raises(WorksheetError):
        run("C1", "W14x132", 50, 30, LOADS, [], 1.0, 1.0, "pinned", "ASD", False)
    with pytest.raises(WorksheetError):
        run("C1", "W14x132", 50, 30, LOADS, ASD, 1.0, 1.0, "", "ASD", False)
    with pytest.raises(WorksheetError):
        run("C1", "W14x132", 50, 30, LOADS, ASD, None, 1.0, "pinned", "ASD", False)


# ---- columns with sideways load: AISC Design Examples v16.0, Example H.4 ----
# W10x33, 14 ft, pinned ends, no sidesway. P: 5 kips dead, 15 kips live. Uniform loads
# giving first-order moments MxD = 15, MxL = 45, MyD = 2, MyL = 6 kip-ft.
# Printed: Pe1x = 1,730, Pe1y = 371 kips; B1x = 1.02, B1y = 1.09; Cb = 1.14;
# Mcx = 137 (LRFD) / 91.0 (ASD) kip-ft; Mcy = 52.5 / 34.9 kip-ft; Pc = 253 / 168 kips;
# H1-1b = 0.979 (LRFD), 0.982 (ASD).

def _w(M):
    return M * 8 / 14.0 ** 2


H4_LAT = [dict(case="D", bending="x", kind="uniform", w=_w(15)), dict(case="L", bending="x", kind="uniform", w=_w(45)),
          dict(case="D", bending="y", kind="uniform", w=_w(2)), dict(case="L", bending="y", kind="uniform", w=_w(6))]
H4_P = [dict(case="D", P=5.0), dict(case="L", P=15.0)]


def _row(s, name):
    return next(r for r in s.rows if r.check.startswith(name))


def test_H4_lrfd():
    s = run("C3", "W10x33", 50, 14, H4_P, [LRFD[1]], 1.0, 1.0, "pinned ends", "LRFD", False, lateral=H4_LAT)
    v = {ln.label.split(" ")[0]: ln.value for ln in s.steps}
    assert v["Pe1x"] == pytest.approx(1730, rel=5e-3) and v["Pe1y"] == pytest.approx(371, rel=5e-3)
    assert v["B1x"] == pytest.approx(1.02, abs=0.005) and v["B1y"] == pytest.approx(1.09, abs=0.005)
    assert _row(s, "axial").capacity == pytest.approx(253, rel=5e-3)
    # The example rounds Cb to 1.14 (exact 1.136), Mn to 1,820 kip-in and then to
    # 152 kip-ft before applying phi, so Mcx is compared at 1 % (StruKit: 136.2 kip-ft).
    assert _row(s, "bending about x").capacity == pytest.approx(137, rel=1e-2)
    assert _row(s, "bending about y").capacity == pytest.approx(52.5, rel=5e-3)
    c = _row(s, "combined")
    assert "H1-1b" in c.source and c.demand == pytest.approx(0.979, abs=0.006) and c.status == "OK"


def test_H4_asd():
    s = run("C3", "W10x33", 50, 14, H4_P, ASD, 1.0, 1.0, "pinned ends", "ASD", False, lateral=H4_LAT)
    assert _row(s, "bending about x").capacity == pytest.approx(91.0, rel=1e-2)
    assert _row(s, "bending about y").capacity == pytest.approx(34.9, rel=5e-3)
    assert _row(s, "combined").demand == pytest.approx(0.982, abs=0.006)
    # shear from the uniform loads: w L / 2
    assert _row(s, "shear, strong").demand == pytest.approx(_w(60) * 7)
    assert _row(s, "shear, weak").demand == pytest.approx(_w(8) * 7)


def test_H1B_interaction_equation():
    # Example H.1B (W14x99): Pu 400 / Pc 1,130; Mux 250 / 642; Muy 80.0 / 311 -> 0.929 (H1-1a)
    from strukit.steel_beamcol import interaction
    v, eq = interaction(400, 1130, 250, 642, 80.0, 311)
    assert eq == "Eq. H1-1a" and v == pytest.approx(0.929, abs=0.001)


def test_weak_axis_shear_by_hand():
    from strukit import shapes
    from strukit.steel_beamcol import weak_axis_shear
    p = shapes.get("W10x33")
    r = weak_axis_shear(p, 50, "LRFD")                   # bf/2tf = 9.15 < 1.10 sqrt(1.2 E/Fy) = 29.0
    assert r.nominal == pytest.approx(2 * 0.6 * 50 * p["bf"] * p["tf"]) and r.available == pytest.approx(0.9 * r.nominal)


def test_unstable_column_stops():
    from strukit.steel_beam import SteelInputError
    with pytest.raises(SteelInputError):
        run("C4", "W10x33", 50, 14, [dict(case="L", P=400.0)], ASD, 1.0, 1.0, "pinned", "ASD", False,
            lateral=[dict(case="L", bending="y", kind="uniform", w=0.1)])
