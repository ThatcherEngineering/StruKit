"""Beam over HSS column, cap plate moment connection: AISC Design Guide 24 (2nd Ed.) Example 6.1 (W18x40 over HSS8x8x1/4, 1/2 in. cap plate 9 in.
wide, four 3/4 in. Group 120 bolts at s = 11 in., g = 3-1/2 in., 1/8 in. fillet; PD 7.5, PL 22.5 kips; MD 4.5, ML 13.5 kip-ft)."""
import pytest
from strukit.gui import calc

V = dict(mark="CP1", beam="W18X40", beam_Fy="50", beam_Fu="65", beam_source="ASTM A992", column="HSS8X8X1/4", col_Fy="50", col_source="ASTM A500 Grade C",
         tp="0.5", bp="9", plate_Fy="50", plate_Fu="65", plate_source="ASTM A572 Grade 50", d="0.75", group="A325", s="11", g="3.5", weld="0.125", FEXX="70",
         loads=[dict(case="D", P="7.5", M="4.5", label=""), dict(case="L", P="22.5", M="13.5", label="")])
PROJ = dict(job="t", name="t", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")])


@pytest.mark.parametrize("method, T, tf, tc, rt, C, Ry, Rc, Rwy, Rwc, w, Rw", [
    ("LRFD", 7.60, 0.338, 0.366, 29.8, 60.2, 116, 113, 78.6, 79.5, 2.17, 1.392 * 2),
    ("ASD", 5.05, 0.337, 0.366, 19.9, 40.1, 77.3, 75.0, 52.4, 53.0, 1.44, 0.928 * 2)])
def test_design_guide_24_example_6_1(method, T, tf, tc, rt, C, Ry, Rc, Rwy, Rwc, w, Rw):
    s, kind, _ = calc.build("cap_plate", V, dict(PROJ, method=method))
    c = s.cap
    assert c["T"] == pytest.approx(T, abs=0.03) and c["C"] == pytest.approx(C, abs=0.1)
    assert c["bf"] == pytest.approx(1.59, abs=0.005) and c["bf1"] == pytest.approx(1.22, abs=0.005) and c["pf"] == pytest.approx(5.56, abs=0.02)
    assert c["bc"] == pytest.approx(1.50) and c["bc1"] == pytest.approx(1.13, abs=0.006) and c["le"] == pytest.approx(2.75) and c["pc"] == pytest.approx(4.38, abs=0.006)
    assert c["t_f"] == pytest.approx(tf, abs=0.002) and c["t_c"] == pytest.approx(tc, abs=0.002) and c["rt"] == pytest.approx(rt, abs=0.1)
    assert c["lb"] == pytest.approx(2.73, abs=0.005) and c["Ry"] == pytest.approx(Ry, rel=0.006) and c["Rc"] == pytest.approx(Rc, rel=0.008)
    assert c["N"] == pytest.approx(4.25, abs=0.005) and c["width"] == pytest.approx(6.75, abs=0.005) and c["Rwy"] == pytest.approx(Rwy, rel=0.004) and c["Rwc"] == pytest.approx(Rwc, rel=0.008)
    assert c["per_in"] == pytest.approx(w, abs=0.01) and c["Rw"] == pytest.approx(Rw, rel=0.002)          # a 1/8 in. fillet is two sixteenths
    assert s.ok and len(s.rows) == 9


def test_cap_plate_flags_and_stops():
    thin = calc.build("cap_plate", dict(V, tp="0.3125"), dict(PROJ, method="LRFD"))[0]
    assert next(r for r in thin.rows if r.check.startswith("Cap plate")).status == "FLAG"
    with pytest.raises(Exception, match="outside the HSS walls"):
        calc.build("cap_plate", dict(V, s="8"), dict(PROJ, method="LRFD"))
    with pytest.raises(Exception, match="square HSS"):
        calc.build("cap_plate", dict(V, column="HSS10X6X3/8"), dict(PROJ, method="LRFD"))
    # compression large enough that no bolt is in tension
    none = calc.build("cap_plate", dict(V, loads=[dict(case="D", P="60", M="5", label="")]), dict(PROJ, method="LRFD"))[0]
    assert none.cap["T"] == 0 and none.cap["C"] == pytest.approx(1.2 * 60)
