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
