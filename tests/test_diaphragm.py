"""Unblocked wood structural panel diaphragms, SDPWS-2021 Sect. 4.2. Hand calculations and table checks."""
import pytest
from strukit import diaphragm as dp


def test_table_4_2c_as_read():
    assert len(dp.ROWS) == 10 and len(dp.PANELS) == 10
    k, r = dp.row("Sheathing and Single-Floor, 7/16 in, 8d common")
    assert r[2] == (645, 8.5, 6.0, 475, 5.5, 4.0) and r[3] == (715, 7.0, 5.5, 530, 4.5, 3.5)
    assert dp.row("Structural I, 15/32 in, 10d common")[1][3][0] == 895 and dp.row("Sheathing and Single-Floor, 19/32 in, 10d common")[1][2][3] == 600
    # across the table the 3 in. face is higher than the 2 in. face, and Cases 2 to 6 are about three quarters of Case 1
    for r in dp.ROWS.values():
        assert r[3][0] > r[2][0] and r[3][3] > r[2][3]
        for f in (2, 3):
            assert 0.73 <= r[f][3] / r[f][0] <= 0.77
    with pytest.raises(dp.DiaphragmError):
        dp.row("Structural I, 3/4 in, 10d common")


def test_unblocked_diaphragm_by_hand():
    """Roof 40 ft span between wall lines, 24 ft deep, wind 200 plf (ASD), 7/16 sheathing, 8d, 2 in. face, Case 1, OSB, G = 0.42 (SPF):
    v = 200(40)/(2 x 24) = 166.7 plf; vn = 645(0.92) = 593.4; ASD wind 593.4/2.0 = 296.7 plf; chord 200(40^2)/(8 x 24) = 1,667 lb;
    L/W = 1.67. Deflection with 2-2x6 chords (16.5 in2, E 1.4e6): 5(166.7)(40^3)/(8 x 1.4e6 x 16.5 x 24) = 0.0120 in;
    0.25(166.7)(40)/(1000 x 8.5) = 0.196 in; one splice 10 ft from a support slipping 0.03 in: 10(0.03)/(2 x 24) = 0.0063 in."""
    r = dp.unblocked("Sheathing and Single-Floor, 7/16 in, 8d common", 2, 1, "OSB", 0.42, 40, 24, 200, "wind", "ASD",
                     chord_E=1.4e6, chord_A=16.5, splice=[(10, 0.03)])
    assert r["v"] == pytest.approx(166.7, abs=0.05) and r["vn"] == pytest.approx(593.4) and r["capacity"] == pytest.approx(296.7)
    assert r["chord"] == pytest.approx(1666.7, abs=0.1) and r["ratio"] == pytest.approx(1.667, abs=0.001) and r["reaction"] == 4000
    assert r["defl_bending"] == pytest.approx(0.0120, abs=0.0002) and r["defl_shear"] == pytest.approx(0.196, abs=0.001)
    assert r["defl_splice"] == pytest.approx(0.00625) and r["defl"] == pytest.approx(0.0120 + 0.196 + 0.0063, abs=0.001)
    s = dp.unblocked("Sheathing and Single-Floor, 7/16 in, 8d common", 3, 2, "plywood", 0.50, 40, 24, 200, "seismic", "LRFD")
    assert s["vn_table"] == 530 and s["Ga"] == 3.5 and s["capacity"] == pytest.approx(265.0) and s["defl"] is None
    assert dp.unblocked("Structural I, 3/8 in, 8d common", 2, 1, "OSB", 0.55, 40, 24, 200, "seismic", "ASD")["capacity"] == pytest.approx(670 / 2.8)
    with pytest.raises(dp.DiaphragmError):
        dp.unblocked("Structural I, 3/8 in, 8d common", 4, 1, "OSB", 0.5, 40, 24, 200, "wind", "ASD")


def test_diaphragm_sheet_and_form(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    assert calc.FORMS["diaphragm"]["fields"][0]["options"] == dp.PANELS
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a")])
    v = dict(mark="DI1", panel="Sheathing and Single-Floor, 7/16 in, 8d common", face="2", case="Case 1", panel_type="OSB", G="0.42", G_source="SPF, NDS Table 12.3.3A",
             L="40", W="24", load="wind", w="200", w_source="sheet WM1, 0.6 W", chord_A="16.5", chord_E="1400000", defl_limit="0.5", defl_limit_source="project criteria",
             splices=[dict(x="10", slip="0.03")])
    sheet, kind, _ = calc.build("diaphragm", v, proj)
    assert kind == "simple" and [r.check for r in sheet.rows] == ["Unit shear", "Aspect ratio L/W", "Mid-span deflection"]
    assert sheet.rows[0].demand == pytest.approx(166.7, abs=0.05) and sheet.rows[0].capacity == pytest.approx(296.7) and sheet.rows[2].demand == pytest.approx(0.214, abs=0.002)
    calcsheet._simple_pdf(sheet, str(tmp_path / "d.pdf"), "2026-000", "SDPWS-2021", "2026-11-23")
    long = calc.results("diaphragm", dict(v, L="80"), proj)
    assert long["state"] == "done" and long["status"] == "FLAG"                     # L/W = 3.33 over 3
    with pytest.raises(calc.Missing):
        calc.build("diaphragm", dict(v, w_source=""), proj)
