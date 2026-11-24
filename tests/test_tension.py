"""Steel tension member against AISC Design Examples v16, Example D.1 (pp. D-2 to D-5): W8x21, A992, 25 ft, D = 30 kips, L = 90 kips, four 13/16 in. holes in
0.400 in. flanges, U = 0.908.  Published: yielding 277 / 184 kips, An = 4.76 in2, Ae = 4.32 in2, rupture 211 / 141 kips (LRFD / ASD)."""
import pytest

from strukit import calcsheet
from strukit.gui import calc
from strukit.ws_more import tension_member_sheet
from strukit.ws_steel_beam import Combo, WorksheetError

LOADS = [dict(case="D", P=30.0), dict(case="L", P=90.0)]
A = ("W8X21", 50, 65, "ASTM A992", 25.0, 4, 0.75, 0.400, 0.908, "Table D3.1 Case 2")


@pytest.mark.parametrize("method, cb, T, py, pr", [("LRFD", Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t"), 180, 277, 211), ("ASD", Combo("D + L", {"D": 1, "L": 1}, "t"), 120, 184, 141)])
def test_example_d1(method, cb, T, py, pr, tmp_path):
    s = tension_member_sheet("TM1", *A, LOADS, [cb], method)
    o = s.tension
    assert o["T"] == pytest.approx(T) and o["An"] == pytest.approx(4.76, abs=0.005) and o["Ae"] == pytest.approx(4.32, abs=0.005)
    assert o["Pyc"] == pytest.approx(py, abs=0.6) and o["Prc"] == pytest.approx(pr, abs=0.6)
    assert o["slen"] == pytest.approx(25 * 12 / 1.26) and s.ok
    calcsheet.simple_pdf(s, str(tmp_path / "t.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")


def test_inputs_and_screen():
    cb = [Combo("D + L", {"D": 1, "L": 1}, "t")]
    with pytest.raises(WorksheetError, match="bolt diameter"):
        tension_member_sheet("TM1", "W8X21", 50, 65, "A992", 25.0, 4, None, None, 0.9, "Case 2", LOADS, cb, "ASD")
    w = tension_member_sheet("TM1", "HSS6X4X3/8", 50, 62, "A500 C", 40.0, 0, None, None, 0.85, "Case 6", LOADS, cb, "ASD")
    assert w.tension["An"] == w.tension["Ag"] and [r.check for r in w.rows if r.status != "OK"] == ["Slenderness L / r"]
    with pytest.raises(WorksheetError, match="tension as positive"):
        tension_member_sheet("TM1", *A, [dict(case="D", P=-5.0)], cb, "ASD")
    v = dict(mark="TM1", shape="W8X21", Fy="50", Fu="65", steel_source="A992", length="25", n_holes="4", bolt_d="0.75", hole_t="0.4", U="0.908", U_source="Case 2",
             loads=[dict(case="D", P="30", label=""), dict(case="L", P="90", label="")])
    proj = dict(name="T", number="1", address="", method="ASD", date="2026-11-23", combos=[dict(expr="D + L", source="typed")])
    s, kind, _ = calc.build("tension_member", v, proj)
    assert kind == "simple" and s.ok
    assert calc.results("tension_member", dict(v, U_source=""), proj)["state"] == "incomplete"


def test_single_angle_hanger_design_guide_34_example_10_1_6():
    """AISC Design Guide 34 Example 10.1.6: L3x3x3/16, ASTM A36 (36 / 58 ksi), RD = 0.310 kip, RL = 0.839 kip: Pu = 1.71 / Pa = 1.15 kips;
    yielding 35.3 / 23.5 kips; rupture 35.6 / 23.7 kips (Manual Table 5-2, which takes Ae = 0.75 Ag)."""
    from strukit import shapes
    a = shapes.angle("L3x3x3/16")
    assert a["A"] == 1.09 and a["rz"] == 0.586 and len(shapes.angle_labels()) == 137
    loads = [dict(case="D", P=0.310), dict(case="L", P=0.839)]
    for method, cb, T, py, pr in (("LRFD", Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t"), 1.71, 35.3, 35.6), ("ASD", Combo("D + L", {"D": 1, "L": 1}, "t"), 1.15, 23.5, 23.7)):
        s = tension_member_sheet("H1", "L3X3X3/16", 36, 58, "ASTM A36", 5.83, 0, None, None, 0.75, "Ae = 0.75 Ag", loads, [cb], method)
        o = s.tension
        assert o["T"] == pytest.approx(T, abs=0.01) and o["Pyc"] == pytest.approx(py, abs=0.06) and o["Prc"] == pytest.approx(pr, abs=0.06)
        assert o["slen"] == pytest.approx(5.83 * 12 / 0.586) and s.ok
