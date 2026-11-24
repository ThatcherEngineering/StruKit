"""Single-plate shear connection to an HSS column, against AISC Design Guide 24 (2nd Ed.) Example 5.1 (pp. 103-108): W21x44 to HSS8x8x1/2
(A500 Gr. C, 50 / 62 ksi), 3/8 in. A572 Gr. 50 plate, (5) 3/4 in. Group 120-N bolts at 3 in., lev = 1-1/4, leh = 1-1/2, a = 2 in., SSLT holes in the plate,
1/4 in. fillets, VD = 12.5 kips, VL = 37.5 kips.  Published LRFD / ASD: bolts 85.4 / 56.8, plate bearing 150 / 100, web bearing 154 / 102, shear yielding
163 / 109, shear rupture 111 / 74.0, block shear 122 / 81.0, weld 5/8 tp = 0.234 in., tmin = 0.200 in., punching 455 / 303 kips (as R, e = 2 in.), b/t 14.2 < 33.7."""
import pytest

from strukit import bolts, calcsheet
from strukit.gui import calc
from strukit.ws_more import single_plate_sheet
from strukit.ws_steel_beam import Combo, WorksheetError

ARGS = ("HSS8X8X1/2", 50, 62, "A500 Gr. C", "W21X44", 65, "A992", 0.375, 50, 65, "A572 Gr. 50", 0.75, "A325", "N", 5, 3.0, 1.25, 1.5, 2.0, "SSLT", 0.25, 70)
LOADS = [dict(case="D", P=12.5), dict(case="L", P=37.5)]


def _run(method, **kw):
    cb = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "test")] if method == "LRFD" else [Combo("D + L", {"D": 1.0, "L": 1.0}, "test")]
    a = list(ARGS)
    for k, v in kw.items():
        a[dict(n=14, holes=19, tp=7, a=18, leh=17, weld=20, column=0, col_Fy=1)[k]] = v
    return single_plate_sheet("SP1", *a, LOADS, cb, method)


def test_bolt_group_coefficient_against_published_values():
    """Manual Table 7-6 values quoted in Design Guide 24 Ex. 5.1 and AISC Design Examples v16 (II.A-17 and others)."""
    assert bolts.group_coefficient(5, 3, 1.0) == pytest.approx(4.77, abs=0.01)
    assert bolts.group_coefficient(4, 3, 2.5) == pytest.approx(3.07, abs=0.01)
    assert bolts.group_coefficient(4, 3, 3.8) == pytest.approx(2.45, abs=0.01)
    assert (bolts.group_coefficient(4, 3, 1.0) + bolts.group_coefficient(4, 3, 2.0)) / 2 == pytest.approx(3.54, abs=0.01)   # "interpolating for e = 1.50"
    assert bolts.group_coefficient(4, 3, 0) == 4.0


@pytest.mark.parametrize("method, R, bolt, bp, bw, vy, vr, bs, punch", [("LRFD", 75.0, 85.4, 150, 154, 163, 111, 122, 455), ("ASD", 50.0, 56.8, 100, 102, 109, 74.0, 81.0, 303)])
def test_design_guide_24_example_5_1(method, R, bolt, bp, bw, vy, vr, bs, punch, tmp_path):
    s = _run(method)
    o = s.single_plate
    assert o["R"] == pytest.approx(R) and o["e"] == 1.0
    assert o["C"] * o["rn"] == pytest.approx(bolt, rel=0.005)
    assert o["brg_p"] == pytest.approx(bp, rel=0.006) and o["brg_w"] == pytest.approx(bw, rel=0.006)
    assert o["Vy"] == pytest.approx(vy, rel=0.005) and o["Vr"] == pytest.approx(vr, rel=0.006) and o["Rbs"] == pytest.approx(bs, rel=0.006)
    assert o["punch"] / 2.0 == pytest.approx(punch, rel=0.005) and o["t_min"] == pytest.approx(0.200, abs=0.001)
    assert o["L"] == 14.5 and o["lam"] == 14.2 and o["lam_r"] == pytest.approx(33.7, abs=0.05)
    assert s.ok and len(s.rows) == 12
    tl = {r.check: r for r in s.rows}
    assert tl["Plate length, not less than T / 2"].demand == pytest.approx(9.19, abs=0.005) and tl["Plate length, not over T"].capacity == 18.375     # T = 18-3/8 in., lmin 9.19 in. in the example
    calcsheet.simple_pdf(s, str(tmp_path / "sp.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")


def test_limits_and_flags():
    with pytest.raises(WorksheetError, match="2 to 12"):
        _run("ASD", n=13)
    with pytest.raises(WorksheetError, match="3-1/2"):
        _run("ASD", a=4.0)
    with pytest.raises(WorksheetError, match="2 bolt diameters"):
        _run("ASD", leh=1.25)
    std = _run("ASD", holes="STD")                      # 3/8 plate and 0.35 web against 3/4 / 2 + 1/16 = 0.4375 in.
    assert len(std.rows) == 13 and std.rows[-1].status == "OK"
    assert _run("ASD", holes="STD", tp=0.5).rows[-1].status == "OK"      # the web, 0.35 in., still satisfies it
    assert [r.check for r in _run("ASD", weld=0.1875).rows if r.status != "OK"] == ["Fillet weld size, each side"]
    thin = _run("ASD", column="HSS8X8X1/8")
    assert {r.check for r in thin.rows if r.status != "OK"} >= {"Column wall thickness at the weld", "Column wall slenderness b / t"}
    rnd = _run("ASD", column="HSS8.625X0.500")
    assert rnd.rows[9].check == "Column wall slenderness D / t" and rnd.rows[9].capacity == pytest.approx(0.11 * 29000 / 50)


def test_screen():
    v = dict(mark="SP1", column="HSS8X8X1/2", col_Fy="50", col_Fu="62", col_source="A500 Gr. C", beam="W21X44", beam_Fu="65", beam_source="A992", tp="0.375", plate_Fy="50", plate_Fu="65",
             plate_source="A572 Gr. 50", d="0.75", group="A325", threads="N", n="5", spacing="3", lev="1.25", leh="1.5", a="2", holes="SSLT", weld="0.25", FEXX="70",
             loads=[dict(case="D", P="12.5", label=""), dict(case="L", P="37.5", label="")])
    proj = dict(name="Test", number="1", address="", method="ASD", date="2026-11-23", combos=[dict(expr="D + L", source="typed")])
    s, kind, _ = calc.build("single_plate", v, proj)
    assert kind == "simple" and s.ok and s.single_plate["R"] == 50.0
    assert calc.results("single_plate", dict(v, col_source=""), proj)["state"] == "incomplete"


@pytest.mark.parametrize("method, cb, R, vy, vr, bs", [("LRFD", Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t"), 49.6, 86.4, 58.5, 65.3), ("ASD", Combo("D + L", {"D": 1, "L": 1}, "t"), 33.0, 57.6, 39.0, 43.6)])
def test_design_example_ii_a_17a_plate_to_column_flange(method, cb, R, vy, vr, bs, tmp_path):
    """AISC Design Examples v16 Example II.A-17A: W16x50 to a W14x90 column flange (tf = 0.710 in.), 1/4 in. plate, (4) 3/4 in. Group 120-N bolts at 3 in.,
    standard holes, a = 3 in., lev = 1-1/4, leh = 1-1/2, 3/16 in. fillets, D = 8 kips, L = 25 kips.  Published: e = 1.50 in., C = 3.54 (table interpolation),
    shear yielding 86.4 / 57.6, rupture 58.5 / 39.0, block shear Rn 87.1 kips, 5/8 tp = 0.156 in., support tmin 0.143 in., thickness limit 0.438 in."""
    s = single_plate_sheet("SP2", "", None, None, "", "W16X50", 65, "A992", 0.25, 50, 65, "A572 Gr. 50", 0.75, "A325", "N", 4, 3.0, 1.25, 1.5, 3.0, "STD", 0.1875, 70,
                           [dict(case="D", P=8.0), dict(case="L", P=25.0)], [cb], method, support=dict(name="W14x90 column flange", t=0.710, Fu=65))
    o = s.single_plate
    assert o["R"] == pytest.approx(R) and o["e"] == 1.5 and o["C"] == pytest.approx(3.54, abs=0.02) and o["L"] == 11.5
    assert o["Vy"] == pytest.approx(vy, rel=0.005) and o["Vr"] == pytest.approx(vr, rel=0.006) and o["Rbs"] == pytest.approx(bs, rel=0.006)
    assert o["t_min"] == pytest.approx(0.143, abs=0.001) and o["punch"] is None
    names = [r.check for r in s.rows]
    assert "Support thickness at the weld" in names and names[-1] == "Plate or beam web thickness, rotational ductility" and s.rows[-1].capacity == pytest.approx(0.4375) and s.ok
    assert {r.check: r for r in s.rows}["Plate length, not less than T / 2"].demand == pytest.approx(13.625 / 2)
    calcsheet.simple_pdf(s, str(tmp_path / "s.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")


def test_screen_needs_one_support():
    v = dict(mark="SP1", column="", col_Fy="", col_Fu="", col_source="", support_name="", support_t="", support_Fu="", beam="W21X44", beam_Fu="65", beam_source="A992", tp="0.375", plate_Fy="50",
             plate_Fu="65", plate_source="A572", d="0.75", group="A325", threads="N", n="5", spacing="3", lev="1.25", leh="1.5", a="2", holes="SSLT", weld="0.25", FEXX="70",
             loads=[dict(case="D", P="12.5", label="")])
    proj = dict(name="T", number="1", address="", method="ASD", date="2026-11-23", combos=[dict(expr="D + L", source="typed")])
    assert calc.results("single_plate", v, proj)["state"] == "incomplete"
    s, _, _ = calc.build("single_plate", dict(v, support_name="W14x90 flange", support_t="0.71", support_Fu="65"), proj)
    assert s.title == "Single-Plate Shear Connection" and s.ok


def test_six_or_more_bolts():
    """AISC Manual Table 10-9 (15th Ed.): 6 to 12 bolts, e = a with standard holes and a / 2 with short slots; thickness limit d/2 - 1/16 and d/2 + 1/16."""
    std = _run("ASD", n=6, holes="STD", tp=0.25)
    sl = _run("ASD", n=6, holes="SSLT", tp=0.25)
    assert std.single_plate["e"] == 2.0 and sl.single_plate["e"] == 1.0
    assert std.single_plate["C"] == pytest.approx(bolts.group_coefficient(6, 3.0, 2.0)) and std.single_plate["C"] == pytest.approx(5.45, abs=0.03)   # Manual Table 7-6
    lim = lambda sh: [r for r in sh.rows if r.check.startswith("Plate or beam web thickness")][0].capacity
    assert lim(std) == pytest.approx(0.75 / 2 - 1 / 16) and lim(sl) == pytest.approx(0.75 / 2 + 1 / 16)


def test_through_plate_DG24_example_5_3():
    """AISC Design Guide 24 (2nd Ed.) Example 5.3: W21x44 to HSS10x4x1/4 (slender wall), 3/8 in. through plate, 3/16 in. fillets, a = 2 in., B = 4 in."""
    from strukit.ws_steel_beam import Combo as C
    a = list(ARGS); a[0] = "HSS10X4X1/4"; a[20] = 0.1875
    for method, R, Vf, vy, vr in (("LRFD", 75.0, 113, 203, 188), ("ASD", 50.0, 75.0, 135, 125.5)):
        cb = [C("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "test")] if method == "LRFD" else [C("D + L", {"D": 1.0, "L": 1.0}, "test")]
        t = single_plate_sheet("SP", *a, LOADS, cb, method, through=4.0).single_plate["through"]
        assert t["Vf"] == pytest.approx(Vf, rel=0.01) and t["vy"] == pytest.approx(vy, rel=0.01) and t["vr"] == pytest.approx(vr, rel=0.01)
        assert t["weld"] == pytest.approx((1.392 if method == "LRFD" else 0.928) * 3 * 14.5 * 2, rel=0.005)      # Manual Eq. 8-2 form used in the example


def test_coped_both_flanges_on_the_sheet():
    cb = [Combo("D + L", {"D": 1.0, "L": 1.0}, "test")]
    a = list(ARGS); a[0] = ""; a[14] = 3
    sup = dict(name="W21x62 girder web", t=0.4, Fu=65)
    one = single_plate_sheet("SP", *a, LOADS[:1], cb, "ASD", support=sup, cope=dict(dc=2.0, c=5.0, setback=0.5, lev=1.5, leh=1.75, Fy=50))
    two = single_plate_sheet("SP", *a, LOADS[:1], cb, "ASD", support=sup, cope=dict(dc=2.0, dcb=2.0, c=5.0, setback=0.5, lev=1.5, leh=1.75, Fy=50))
    f = lambda sh: [r for r in sh.rows if r.check.startswith("Coped beam web flexure")][0]
    assert "F11" in f(two).source and "F11" not in f(one).source and f(two).capacity < f(one).capacity
    assert two.single_plate["cope"]["hc"] == pytest.approx(20.7 - 4.0)
