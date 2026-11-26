"""Single-angle compression member against AISC Design Examples v16.0, Example E.14A (L5x3x1/2, 5 ft, Fy 50, long leg attached)."""
import pytest
from strukit.ws_more import angle_strut_sheet
from strukit.ws_steel_beam import Combo, WorksheetError


def _run(method, shape="L5X3X1/2", L=5.0, att="long", Fy=50):
    cb = [Combo("1.2D", {"D": 1.2}, "test")] if method == "LRFD" else [Combo("D", {"D": 1.0}, "test")]
    return angle_strut_sheet("AS", shape, Fy, "x", L, att, [dict(case="D", P=10.0)], cb, method).strut


def test_example_E14A():
    r = _run("LRFD")
    assert r["L_ra"] == pytest.approx(72.8, abs=0.1) and r["Lc_r"] == pytest.approx(127, abs=0.5) and r["Fe"] == pytest.approx(17.7, abs=0.2)
    assert r["Fn"] == pytest.approx(15.5, abs=0.2) and r["Pn"] == pytest.approx(58.1, rel=0.013) and r["Pc"] == pytest.approx(52.3, rel=0.013)
    assert _run("ASD")["Pc"] == pytest.approx(34.8, rel=0.013)


def test_other_branches():
    eq = _run("ASD", "L3X3X1/4", 5.0, "", 36)            # equal legs, L / rx = 64.5: Eq. E5-1
    assert eq["Lc_r"] == pytest.approx(72 + 0.75 * 60 / 0.926, abs=0.2)
    long_ = _run("ASD", "L3X3X1/4", 8.0, "", 36)          # L / rx over 80: Eq. E5-2
    assert long_["Lc_r"] == pytest.approx(32 + 1.25 * 96 / 0.926, abs=0.3)
    sh = _run("ASD", "L5X3X1/2", 5.0, "short")
    assert sh["Lc_r"] == pytest.approx(max(72 + 0.75 * 60 / 1.58 + 4 * ((5 / 3) ** 2 - 1), 0.95 * 60 / 0.642), abs=0.2)
    with pytest.raises(WorksheetError, match="over 200"):
        _run("ASD", "L3X3X1/4", 13.0, "", 36)


@pytest.mark.parametrize("method, Pav, Pc, Mcw, Mcz", [("LRFD", 85.9, 168, 375, 123), ("ASD", 56.4, 112, 250, 82.0)])
def test_example_E14B_eccentric(method, Pav, Pc, Mcw, Mcz, tmp_path):
    """AISC Design Examples v16.0 Example E.14B: L8x4x1/2, Fy 50, 5 ft, long leg attached, load at 0.75 t outside it: ew 1.44, ez 0.889 in.,
    Pn 187 kips (slender long leg, Ae 5.34 in2), Mnw 417 (lateral-torsional buckling, beta_w negative), Mnz 137 kip-in., Pe1w 3,260, Pe1z 343
    kips; the H2-1 limit at point B, Pu 85.9 / Pa 56.4 kips (Manual Table 4-12: 86.1 / 56.5)."""
    from strukit import shapes, anglebeam as ab, calcsheet
    a = shapes.angle("L8X4X1/2")
    r = ab.eccentric_compression(a, 50, 60, "long", 0.375, 50, method)
    assert abs(r["ew"]) == pytest.approx(1.44, abs=0.005) and abs(r["ez"]) == pytest.approx(0.889, abs=0.005)
    assert r["comp"]["Ae"] == pytest.approx(5.34, abs=0.01) and r["comp"]["Pn"] == pytest.approx(187, rel=0.005) and r["Pc"] == pytest.approx(Pc, rel=0.006)
    assert r["flex"]["Mnw"] == pytest.approx(417, rel=0.003) and r["flex"]["Mnz"] == pytest.approx(137, rel=0.003)
    assert r["Mcw"] == pytest.approx(Mcw, rel=0.005) and r["Mcz"] == pytest.approx(Mcz, rel=0.005)
    assert r["Pe1w"] == pytest.approx(3260, rel=0.003) and r["Pe1z"] == pytest.approx(343, rel=0.003)
    assert ab.eccentric_capacity(a, 50, 60, "long", 0.375, method) == pytest.approx(Pav, rel=0.005)
    assert ab.eccentric_compression(a, 50, 60, "long", 0.375, Pav, method)["gov"] == "B"
    cb = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t")] if method == "LRFD" else [Combo("D + L", {"D": 1.0, "L": 1.0}, "t")]
    s = angle_strut_sheet("AS", "L8X4X1/2", 50, "A572 Gr. 50", 5, "long", [dict(case="D", P=20.0), dict(case="L", P=30.0)], cb, method, e_off=0.375)
    assert s.title.endswith("(eccentric load)") and any(x.check.startswith("Axial load and bending") for x in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "e14b.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")
