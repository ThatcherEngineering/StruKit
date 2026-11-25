"""Steel beams with sideways (weak-axis) loads: AISC Design Examples v16.0 Example F.5 (W12x58, 15 ft simple span braced at the ends,
0.667 kip/ft dead and 2 kip/ft live about the minor axis), and bending about both axes by AISC 360-22 Eq. H1-1b with Pr = 0, by hand."""
import pytest
from strukit.gui import calc

P = dict(job="t", name="t", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")])
SIDE = "sideways (y axis)"
V = dict(mark="B1", shape="W12X58", Fy="50", span="15", bracing="at points", brace_pts="15", self_weight="no",
         loads=[dict(case="D", kind="uniform", mag="0.667", x1="", x2="", dir=SIDE, label=""),
                dict(case="L", kind="uniform", mag="2", x1="", x2="", dir=SIDE, label="")],
         defl=[dict(label="live", expr="L", ratio="240", source="t")])


def rows(s):
    return {r.check: r for r in s.rows}


@pytest.mark.parametrize("method, M, Mc", [("LRFD", 113, 122), ("ASD", 75.1, 81.4)])
def test_design_example_f_5(method, M, Mc):
    r = rows(calc.build("steel_beam", V, dict(P, method=method))[0])
    assert r["flexure, y axis (sideways loads)"].demand == pytest.approx(M, rel=0.005)
    assert r["flexure, y axis (sideways loads)"].capacity == pytest.approx(Mc, rel=0.005)
    # live load deflection 5 w L^4 / 384 E Iy with Iy = 107 in4; the example requires Iy >= 105 in4 for L / 240
    assert r["deflection, live, sideways"].demand == pytest.approx(0.750 * 105 / 107, rel=0.005)
    assert r["flexure about both axes"].demand == pytest.approx(r["flexure, y axis (sideways loads)"].dc, rel=1e-6)


def test_bending_about_both_axes_by_hand():
    """W12x58, 15 ft, continuously braced: 1 kip/ft down (D) and 0.5 kip/ft sideways (W), LRFD 1.2D + 1.0W.
    Mrx = 1.2 x 15^2 / 8 = 33.75 kip-ft against phi Mp = 0.9 x 50 x 86.4 / 12 = 324 kip-ft; Mry = 0.5 x 15^2 / 8 = 14.06 kip-ft against
    phi Mpy = 0.9 x 50 x 32.5 / 12 = 121.9 kip-ft; Eq. H1-1b: 33.75 / 324 + 14.06 / 121.9 = 0.2195 at midspan."""
    v = dict(V, bracing="continuous", brace_pts="", defl=[], loads=[dict(case="D", kind="uniform", mag="1", x1="", x2="", dir="", label=""),
                                                                   dict(case="W", kind="uniform", mag="0.5", x1="", x2="", dir=SIDE, label="")])
    p = dict(P, method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.0W", source="t")])
    r = rows(calc.build("steel_beam", v, p)[0])
    assert r["flexure"].demand == pytest.approx(33.75) and r["flexure"].capacity == pytest.approx(0.9 * 50 * 86.4 / 12, rel=0.001)
    assert r["flexure, y axis (sideways loads)"].demand == pytest.approx(14.0625)
    assert r["flexure about both axes"].demand == pytest.approx(33.75 / (0.9 * 50 * 86.4 / 12) + 14.0625 / (0.9 * 50 * 32.5 / 12), rel=0.002)
    assert "7.50 ft" in r["flexure about both axes"].note
    # HSS: the same check runs with the HSS weak-axis strength
    h = rows(calc.build("steel_beam", dict(v, shape="HSS10X6X3/8", Fy="50"), p)[0])
    assert h["flexure about both axes"].dc > h["flexure"].dc


def test_sideways_loads_refused_where_not_covered():
    for extra in (dict(more_spans="10"), dict(oh_right="3"), dict(shape="C10X15.3")):
        with pytest.raises(Exception, match="sideways"):
            calc.build("steel_beam", dict(V, **extra), dict(P, method="LRFD"))
