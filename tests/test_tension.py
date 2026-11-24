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


def test_single_angle_example_d2_with_the_shear_lag_helper():
    """AISC Design Examples v16 Example D.2: L4x4x1/2, A572 Gr. 50, one line of four 3/4 in. bolts, l = 9 in., D = 20 kips, L = 60 kips: U = 0.869 (Case 2
    over Case 8's 0.80), An = 3.31 in2, Ae = 2.88 in2, yielding 169 / 113 kips, rupture 140 / 93.5 kips; L/r limit at 300 rz = 19.4 ft."""
    from strukit import shapes
    from strukit.ws_more import angle_shear_lag
    loads = [dict(case="D", P=20.0), dict(case="L", P=60.0)]
    for method, cb, py, pr in (("LRFD", Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t"), 169, 140), ("ASD", Combo("D + L", {"D": 1, "L": 1}, "t"), 112.5, 93.5)):
        s = tension_member_sheet("TM2", "L4X4X1/2", 50, 65, "A572 Gr. 50", 19.4, 1, 0.75, 0.5, None, "", loads, [cb], method, angle_conn=dict(n=4, l=9.0, leg="long"))
        o = s.tension
        assert o["U"] == pytest.approx(0.869, abs=0.001) and o["An"] == pytest.approx(3.31, abs=0.005) and o["Ae"] == pytest.approx(2.88, abs=0.005)
        assert o["Pyc"] == pytest.approx(py, abs=0.6) and o["Prc"] == pytest.approx(pr, abs=0.6) and o["slen"] == pytest.approx(300, abs=0.5)
    a = shapes.angle("L6X4X1/2")
    assert angle_shear_lag(a, 3, 6.0, "long")[0] == pytest.approx(max(1 - 0.981 / 6, 0.60, 6 * 0.5 / 4.75))
    assert angle_shear_lag(a, 3, 6.0, "short")[0] == pytest.approx(max(1 - 1.98 / 6, 0.60, 4 * 0.5 / 4.75))
    assert angle_shear_lag(a, 2, 3.0, "short")[0] == pytest.approx(max(1 - 1.98 / 3, 4 * 0.5 / 4.75))
    with pytest.raises(WorksheetError):
        tension_member_sheet("TM2", "W8X21", 50, 65, "A992", 20, 0, None, None, None, "", loads, [Combo("D + L", {"D": 1, "L": 1}, "t")], "ASD", angle_conn=dict(n=4, l=9.0))
    v = dict(mark="TM2", shape="L4X4X1/2", Fy="50", Fu="65", steel_source="A572", length="15", n_holes="1", bolt_d="0.75", hole_t="0.5", U="", U_source="", angle_n="4", angle_l="9", angle_leg="long",
             loads=[dict(case="D", P="20", label=""), dict(case="L", P="60", label="")])
    proj = dict(name="T", number="1", address="", method="ASD", date="2026-11-23", combos=[dict(expr="D + L", source="typed")])
    sh, _, _ = calc.build("tension_member", v, proj)
    assert sh.tension["U"] == pytest.approx(0.869, abs=0.001) and sh.ok
    assert calc.results("tension_member", dict(v, angle_n="", angle_l=""), proj)["state"] == "incomplete"


def test_threaded_rod_hanger():
    """3/4 in. A36 rod (36 / 58 ksi), D = 2 kips, L = 5 kips.  By hand: Ab = 0.4418 in2; yielding 36 x 0.4418 = 15.90 kips -> 9.52 ASD, 14.31 LRFD;
    threads 0.75 x 58 x 0.4418 = 19.22 kips -> 9.61 ASD, 14.41 LRFD.  A 7/8 in. Gr. 36 rod gives 19.6 / 13.1 kips at the threads, the value on the base plate sheets."""
    from strukit.ws_more import tension_rod_sheet
    loads = [dict(case="D", P=2.0), dict(case="L", P=5.0)]
    a = tension_rod_sheet("R1", 0.75, 36, 58, "ASTM A36", 8.0, loads, [Combo("D + L", {"D": 1, "L": 1}, "t")], "ASD")
    assert a.tension["T"] == 7.0 and a.tension["Pyc"] == pytest.approx(9.52, abs=0.01) and a.tension["Rc"] == pytest.approx(9.61, abs=0.01) and a.ok and len(a.rows) == 2
    l = tension_rod_sheet("R1", 0.75, 36, 58, "ASTM A36", 8.0, loads, [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t")], "LRFD")
    assert l.tension["T"] == pytest.approx(10.4) and l.tension["Pyc"] == pytest.approx(14.31, abs=0.01) and l.tension["Rc"] == pytest.approx(14.41, abs=0.01)
    assert tension_rod_sheet("R1", 0.875, 36, 58, "F1554 Gr. 36", 8.0, loads, [Combo("D + L", {"D": 1, "L": 1}, "t")], "ASD").tension["Rc"] == pytest.approx(13.1, abs=0.05)
    v = dict(mark="R1", shape="", rod_d="0.75", Fy="36", Fu="58", steel_source="A36", length="8", n_holes="", bolt_d="", hole_t="", U="", U_source="", angle_n="", angle_l="", angle_leg="",
             loads=[dict(case="D", P="2", label=""), dict(case="L", P="5", label="")])
    proj = dict(name="T", number="1", address="", method="ASD", date="2026-11-23", combos=[dict(expr="D + L", source="typed")])
    s, kind, _ = calc.build("tension_member", v, proj)
    assert kind == "simple" and s.title == "Steel Tension Rod" and s.ok
    assert calc.results("tension_member", dict(v, shape="W8X21"), proj)["state"] == "incomplete"
    assert calc.results("tension_member", dict(v, rod_d=""), proj)["state"] == "incomplete"
