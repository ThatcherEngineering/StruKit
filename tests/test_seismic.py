"""Seismic base shear, ASCE/SEI 7-22 Sect. 12.8. Hand calculations (no published worked example to this
edition is on file)."""
import pytest
from strukit import seismic


def test_period_and_cu_tables():
    Ta, Ct, x = seismic.ta("all other structural systems", 30)
    assert (Ct, x) == (0.02, 0.75) and Ta == pytest.approx(0.02 * 30 ** 0.75) and Ta == pytest.approx(0.2564, abs=0.0001)
    assert seismic.ta("steel moment-resisting frame", 40)[0] == pytest.approx(0.028 * 40 ** 0.8)
    assert seismic.ta("concrete moment-resisting frame", 40)[1:] == (0.016, 0.9)
    assert [seismic.cu(s) for s in (0.5, 0.4, 0.3, 0.25, 0.2, 0.17, 0.15, 0.12, 0.1, 0.05)] == [1.4, 1.4, 1.4, 1.4, 1.5, 1.5, 1.6, 1.6, 1.7, 1.7]
    assert seismic.k_exponent(0.3) == 1.0 and seismic.k_exponent(3) == 2.0 and seismic.k_exponent(1.5) == pytest.approx(1.5)
    with pytest.raises(seismic.SeismicError):
        seismic.ta("wood", 30)


def test_elf_two_story_by_hand():
    """SDS = 0.40, SD1 = 0.12, S1 = 0.08, TL = 4 s, R = 6.5, Ie = 1.0, wood shear walls (all other systems), hn = 20 ft.
    Ta = 0.02(20^0.75) = 0.189 s; Cs = 0.40/6.5 = 0.0615; cap 0.12/(0.189 x 6.5) = 0.0976; minimum 0.044(0.40) = 0.0176.
    Roof 60 kips at 20 ft, floor 90 kips at 10 ft: W = 150, V = 9.23 kips; k = 1; w h = 1,200 and 900;
    F = 9.23(1200/2100) = 5.27 and 3.96 kips; story shears 5.27 and 9.23; base overturning 5.27(20) + 3.96(10) = 145.1 kip-ft."""
    r = seismic.elf(0.40, 0.12, 0.08, 4, 6.5, 1.0, "all other structural systems", 20, [("Floor", 90, 10), ("Roof", 60, 20)])
    assert r["Ta"] == pytest.approx(0.189, abs=0.001) and r["Cs"] == pytest.approx(0.0615, abs=0.0001) and r["governs"] == "Eq. 12.8-3"
    assert r["Cs_cap"] == pytest.approx(0.0976, abs=0.0002) and r["Cs_min"] == pytest.approx(0.0176)
    assert r["V"] == pytest.approx(9.23, abs=0.01) and [x["name"] for x in r["rows"]] == ["Roof", "Floor"]
    assert [round(x["F"], 2) for x in r["rows"]] == [5.27, 3.96] and [round(x["V"], 2) for x in r["rows"]] == [5.27, 9.23]
    assert r["M_base"] == pytest.approx(145.1, abs=0.1) and r["rows"][1]["M"] == pytest.approx(5.27 * 10, abs=0.05)


def test_elf_limits():
    lv = [("Roof", 100, 60)]
    # long period: the cap governs. Steel moment frame, hn 60 ft: Ta = 0.028(60^0.8) = 0.741 s; cap 0.2/(0.741 x 8) = 0.0337
    r = seismic.elf(0.6, 0.2, 0.1, 6, 8, 1.0, "steel moment-resisting frame", 60, lv)
    assert r["governs"] == "Eq. 12.8-4" and r["Cs"] == pytest.approx(0.2 / (0.028 * 60 ** 0.8 * 8)) and 1 < r["k"] < 2
    # the minimum governs
    r = seismic.elf(1.0, 0.05, 0.02, 6, 8, 1.0, "steel moment-resisting frame", 60, lv)
    assert r["governs"] == "Eq. 12.8-6" and r["Cs"] == pytest.approx(0.044)
    r = seismic.elf(0.1, 0.02, 0.01, 6, 8, 1.0, "steel moment-resisting frame", 60, lv)
    assert r["Cs"] == 0.01
    # near-fault: 0.5 S1/(R/Ie) = 0.5(0.8)/8 = 0.05 governs
    r = seismic.elf(1.0, 0.2, 0.8, 6, 8, 1.0, "steel moment-resisting frame", 60, lv)
    assert r["governs"] == "Eq. 12.8-7" and r["Cs"] == pytest.approx(0.05)
    # T beyond TL
    r = seismic.elf(1.0, 0.6, 0.3, 0.5, 8, 1.0, "steel moment-resisting frame", 60, lv)
    assert r["cap_eq"] == "Eq. 12.8-5" and r["Cs_cap"] == pytest.approx(0.6 * 0.5 / (r["T"] ** 2 * 8))
    # a period from analysis is limited to Cu Ta
    r = seismic.elf(1.0, 0.2, 0.1, 6, 8, 1.0, "steel moment-resisting frame", 60, lv, T_analysis=2.0)
    assert r["T"] == pytest.approx(1.5 * 0.028 * 60 ** 0.8) and "Cu Ta" in r["T_note"]
    r = seismic.elf(1.0, 0.2, 0.1, 6, 8, 1.0, "steel moment-resisting frame", 60, lv, T_analysis=0.9)
    assert r["T"] == 0.9
    with pytest.raises(seismic.SeismicError):
        seismic.elf(1.0, 0.2, 0.1, 6, 8, 1.0, "steel moment-resisting frame", 60, [("Roof", 100, 70)])
    with pytest.raises(seismic.SeismicError):
        seismic.elf(1.0, 0.2, 0.1, 6, 0, 1.0, "steel moment-resisting frame", 60, lv)


def test_seismic_sheet_and_form(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="EQ1", SDS="0.40", SD1="0.12", S1="0.08", TL="4", ground_source="ASCE 7 Hazard Tool, Site Class D, Risk Category II",
             R="6.5", R_source="light-frame wood walls sheathed with wood structural panels, Table 12.2-1 line A.16", Ie="1.0",
             Ie_source="Risk Category II, Table 1.5-2", structure="all other structural systems", hn="20", risk="II",
             levels=[dict(name="Roof", w="60", h="20"), dict(name="Floor", w="90", h="10")])
    sheet, kind, _ = calc.build("seismic_elf", v, dict(job="2026-000", name="Test", method="ASD"))
    assert kind == "simple" and sheet.seismic["V"] == pytest.approx(9.23, abs=0.01) and len(sheet.blocks[1]["lines"]) == 4 and len(sheet.blocks[2]["lines"]) == 3
    assert sheet.blocks[0]["picture"][0] == "seismic_forces" and sheet.seismic["sdc"] == "C"
    calcsheet._simple_pdf(sheet, str(tmp_path / "e.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("seismic_elf", dict(v, levels=[]), dict(job="2026-000", name="Test", method="ASD"))
    with pytest.raises(calc.Missing):
        calc.build("seismic_elf", dict(v, R_source=""), dict(job="2026-000", name="Test", method="ASD"))


def test_seismic_load_combinations():
    """SDS = 0.5, rho = 1.3: Ev = 0.1 D. 6: 1.3D + 1.3E + L + 0.15S; 7: 0.8D + 1.3E; 8: 1.07D + 0.91E;
    9: 1.0525D + 0.6825E + 0.75L + 0.1S; 10: 0.53D + 0.91E."""
    from strukit import loadcombos
    from strukit.gui import calc, server
    c = loadcombos.seismic(0.5, 1.3)
    assert [x["expr"] for x in c["LRFD"]] == ["1.3D + 1.3E + 1.0L + 0.15S", "0.8D + 1.3E"]
    assert [x["expr"] for x in c["ASD"]] == ["1.07D + 0.91E", "1.0525D + 0.6825E + 0.75L + 0.1S", "0.53D + 0.91E"]
    assert "Sect. 2.3.6, combination 6" in c["LRFD"][0]["source"] and "Sect. 2.4.5, combination 10" in c["ASD"][2]["source"]
    assert calc.parse_expr(c["ASD"][1]["expr"]) == {"D": 1.0525, "E": 0.6825, "L": 0.75, "S": 0.1}
    b = loadcombos.seismic(0.3, 1.0, ev=False)
    assert [x["expr"] for x in b["LRFD"]] == ["1.2D + 1.0E + 1.0L + 0.15S", "0.9D + 1.0E"] and b["ASD"][2]["expr"] == "0.6D + 0.7E"
    with pytest.raises(ValueError):
        loadcombos.seismic(0.5, 1.2)
    assert server.api("/api/seismic_combos", dict(sds="0.5", rho="1.3")) == c
    assert "error" in server.api("/api/seismic_combos", dict(sds="", rho="1.0")) and "error" in server.api("/api/seismic_combos", dict(sds="0.5", rho="2"))


def test_seismic_design_category():
    f = seismic.sdc
    assert [f(s, 0.01, 0.1, "II")[0] for s in (0.1, 0.167, 0.32, 0.33, 0.49, 0.50, 1.2)] == ["A", "B", "B", "C", "C", "D", "D"]
    assert [f(s, 0.01, 0.1, "IV")[0] for s in (0.1, 0.167, 0.33, 0.50)] == ["A", "C", "D", "D"]
    assert [f(0.01, s, 0.1, "III")[0] for s in (0.05, 0.067, 0.133, 0.20)] == ["A", "B", "C", "D"]
    assert [f(0.01, s, 0.1, "IV")[0] for s in (0.05, 0.067, 0.133, 0.20)] == ["A", "C", "D", "D"]
    assert f(0.40, 0.12, 0.08, "II") == ("C", "C", "B", "the more severe of the two tables") and f(0.2, 0.15, 0.1, "I")[0] == "C"
    assert f(1.0, 0.6, 0.75, "II")[0] == "E" and f(1.0, 0.6, 0.80, "IV")[0] == "F"
    with pytest.raises(seismic.SeismicError):
        f(0.4, 0.1, 0.1, "V")


def test_diaphragm_forces_by_hand():
    """Two-story case above (SDS 0.40, Ie 1.0; roof 60 kips, F 5.27; floor 90 kips, F 3.96; V 9.23):
    roof: 5.27/60 x 60 = 5.27 kips; minimum 0.2(0.4)(60) = 4.8; maximum 9.6 -> 5.27 (Eq. 12.10-1)
    floor: 9.23/150 x 90 = 5.54 kips; minimum 0.2(0.4)(90) = 7.2 -> 7.2 (Eq. 12.10-2).
    With a floor diaphragm weight of 70 kips: 9.23/150 x 70 = 4.31; minimum 5.6 -> 5.6."""
    r = seismic.elf(0.40, 0.12, 0.08, 4, 6.5, 1.0, "all other structural systems", 20, [("Floor", 90, 10), ("Roof", 60, 20)])["rows"]
    assert r[0]["Fpx"] == pytest.approx(5.27, abs=0.01) and r[0]["Fpx_by"] == "Eq. 12.10-1" and r[0]["Fpx_max"] == pytest.approx(9.6)
    assert r[1]["Fpx_eq"] == pytest.approx(5.54, abs=0.01) and r[1]["Fpx"] == pytest.approx(7.2) and r[1]["Fpx_by"] == "Eq. 12.10-2"
    r = seismic.elf(0.40, 0.12, 0.08, 4, 6.5, 1.0, "all other structural systems", 20, [("Floor", 90, 10, 70), ("Roof", 60, 20, None)])["rows"]
    assert r[1]["wp"] == 70 and r[1]["Fpx_eq"] == pytest.approx(4.31, abs=0.01) and r[1]["Fpx"] == pytest.approx(5.6)
    # the maximum governs where R is small: R = 1.5, Cs = 0.267: roof 16.0/60 x 60 ... over 0.4(0.4)(60) = 9.6
    r = seismic.elf(0.40, 0.3, 0.08, 4, 1.5, 1.0, "all other structural systems", 20, [("Floor", 90, 10), ("Roof", 60, 20)])["rows"]
    assert r[0]["Fpx"] == pytest.approx(9.6) and r[0]["Fpx_by"] == "Eq. 12.10-3"
