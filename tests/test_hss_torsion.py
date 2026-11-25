"""HSS torsion: AISC Design Examples v16.0 Examples H.5A (HSS6x4x1/4: Tc 273 / 181 kip-in), H.5B (HSS5.000x0.250, 14 ft: 215 / 143 kip-in)
and H.5C (HSS6x4x1/4, 8 ft simple span, torsionally fixed ends, 0.46 / 1.38 kip/ft at 6 in. from the shear center: Tr 66.2 / 44.2 kip-in;
Eq. H3-6 = 0.166 / 0.168 at the support and 0.333 / 0.340 where Tr = 0.2 Tc)."""
import pytest
from strukit import hss, shapes
from strukit.gui import calc

P = dict(job="t", name="t", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")])
V = dict(mark="B1", shape="HSS6X4X1/4", Fy="50", span="8", bracing="at points", brace_pts="8", self_weight="no", defl=[],
         loads=[dict(case="D", kind="uniform", mag="0.46", x1="", x2="", dir="", e="6", label=""),
                dict(case="L", kind="uniform", mag="1.38", x1="", x2="", dir="", e="6", label="")])


@pytest.mark.parametrize("method, rect, rnd", [("LRFD", 273, 215), ("ASD", 181, 143)])
def test_examples_h5a_h5b(method, rect, rnd):
    assert hss.torsion(shapes.hss("HSS6X4X1/4"), 50, 96, method).available == pytest.approx(rect, rel=0.005)
    assert hss.torsion(shapes.hss("HSS5.000X0.250"), 50, 14 * 12, method).available == pytest.approx(rnd, rel=0.005)


@pytest.mark.parametrize("method, Tr, inter", [("LRFD", 66.2, 0.333), ("ASD", 44.2, 0.340)])
def test_example_h5c(method, Tr, inter):
    r = {x.check: x for x in calc.build("steel_beam", V, dict(P, method=method))[0].rows}
    assert r["torsion"].demand == pytest.approx(Tr, rel=0.002)
    # the example finds x where Tr = 0.2 Tc from rounded values (0.700 / 0.725 ft); StruKit scans the span: within 1 percent
    assert r["torsion with shear and flexure"].demand == pytest.approx(inter, rel=0.01)


def test_torsion_refused_where_not_covered():
    for extra in (dict(shape="W12X26"), dict(more_spans="6")):
        with pytest.raises(Exception, match="shear center"):
            calc.build("steel_beam", dict(V, **extra), dict(P, method="LRFD"))
    # rectangular HSS walls: Eq. H3-4 between 2.45 and 3.07 (E / Fy)^0.5, by hand on a typed section
    p = dict(shapes.hss("HSS6X4X1/4"), h_t=65.0, b_t=40.0)
    assert hss.torsion(p, 50, 96, "LRFD").nominal == pytest.approx(0.6 * 50 * 2.45 * (29000 / 50) ** 0.5 / 65.0 * p["C"])
