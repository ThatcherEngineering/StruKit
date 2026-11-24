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
    assert s.ok and len(s.rows) == 10
    calcsheet.simple_pdf(s, str(tmp_path / "sp.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")


def test_limits_and_flags():
    with pytest.raises(WorksheetError, match="2 to 5"):
        _run("ASD", n=6)
    with pytest.raises(WorksheetError, match="3-1/2"):
        _run("ASD", a=4.0)
    with pytest.raises(WorksheetError, match="2 bolt diameters"):
        _run("ASD", leh=1.25)
    std = _run("ASD", holes="STD")                      # 3/8 plate and 0.35 web against 3/4 / 2 + 1/16 = 0.4375 in.
    assert len(std.rows) == 11 and std.rows[-1].status == "OK"
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
