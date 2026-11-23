"""Wind velocity pressure, ASCE/SEI 7-22 Chapter 26.

References: Table 26.10-1 and Table 26.9-1 as printed (the Ke formula is checked against
the table's own values), the table's note 1 formula with the Exposure C constants
(alpha 9.8, zg 2,460 ft) as a cross-check of the tabulated Kz, and a hand calculation.
"""
import math

import pytest

from strukit import wind


def test_kz_table_and_interpolation():
    assert wind.kz("B", 10) == 0.57 and wind.kz("C", 15) == 0.85 and wind.kz("D", 500) == 1.89
    assert wind.kz("C", 30) == 0.98 and wind.kz("B", 180) == 1.11 and wind.kz("D", 100) == 1.43
    assert wind.kz("C", 35) == pytest.approx((0.98 + 1.04) / 2) and wind.kz("B", 22.5) == pytest.approx(0.64)
    assert wind.kz("B", 20, chapter_28=True) == 0.70 and wind.kz("B", 30, chapter_28=True) == 0.70 and wind.kz("C", 20, chapter_28=True) == 0.90
    with pytest.raises(wind.WindError):
        wind.kz("A", 20)
    with pytest.raises(wind.WindError):
        wind.kz("C", 600)


def test_ke_formula_matches_table_26_9_1():
    for z, k in ((0, 1.00), (1000, 0.96), (2000, 0.93), (3000, 0.90), (4000, 0.86), (5000, 0.83), (6000, 0.80)):
        assert wind.ke(z) == pytest.approx(k, abs=0.006)


def test_tabulated_kz_agrees_with_the_note_1_formula_for_exposure_c():
    for z in (15, 30, 60, 100, 200):
        assert wind.kz("C", z) == pytest.approx(2.41 * (z / 2460) ** (2 / 9.8), abs=0.011)


def test_velocity_pressure_by_hand():
    # V = 115 mi/h, Exposure C, h = 30 ft, Kzt = 1.0, Ke = 1.0: 0.00256 x 0.98 x 115^2 = 33.18 psf
    q, k = wind.velocity_pressure(115, "C", 30)
    assert k == 0.98 and q == pytest.approx(33.18, abs=0.01)
    # at 6,200 ft above sea level: Ke = e^(-0.2244) = 0.799 -> 26.51 psf
    q2, _ = wind.velocity_pressure(115, "C", 30, Ke=wind.ke(6200))
    assert q2 == pytest.approx(33.18 * math.exp(-0.0000362 * 6200), abs=0.01) and q2 == pytest.approx(26.51, abs=0.02)
    with pytest.raises(wind.WindError):
        wind.velocity_pressure(115, "C", 30, Kzt=0.9)


def test_figure_27_3_1_data_as_read():
    assert wind.wall_cp_leeward(0.5) == -0.5 and wind.wall_cp_leeward(2) == -0.3 and wind.wall_cp_leeward(6) == -0.2
    assert wind.wall_cp_leeward(1.5) == pytest.approx(-0.4) and wind.wall_cp_leeward(3) == pytest.approx(-0.25)
    assert wind.ROOF_WINDWARD[0.5][20] == (-0.4, 0.0) and wind.ROOF_WINDWARD[1.0][10] == (-1.3, -0.18) and wind.ROOF_WINDWARD[0.25][35] == (0.0, 0.4)
    assert wind.ROOF_LEEWARD[0.25][10] == -0.3 and wind.ROOF_LEEWARD[1.0][15] == -0.6 and wind.GCPI["partially enclosed"] == 0.55
    assert wind.ROOF_PARALLEL[0.5][2] == ("h to 2h", -0.5)


def test_roof_cp_interpolation_by_hand():
    # 22.5 degrees, h/L 0.375: rows 0.25 -> (-0.25, 0.25), 0.5 -> (-0.35, 0.10); halfway between
    a, b = wind.roof_cp_windward(22.5, 0.375)
    assert a == pytest.approx(-0.30) and b == pytest.approx(0.175)
    # no value of that sign in the figure: none, and 0.0 is used when interpolating to a row that has one (note 3)
    assert wind.roof_cp_windward(40, 0.25) == (None, pytest.approx(0.4))
    assert wind.roof_cp_windward(40, 0.4)[0] == pytest.approx(-0.06)
    assert wind.roof_cp_windward(70, 0.3) == (None, pytest.approx(0.7)) and wind.roof_cp_windward(85, 0.3) == (None, 0.8)
    assert wind.roof_cp_windward(10, 2.0) == (-1.3, -0.18) and wind.roof_cp_windward(10, 0.1) == (-0.7, -0.18)
    assert wind.roof_cp_leeward(12.5, 0.75) == pytest.approx(-0.575) and wind.roof_cp_leeward(30, 0.3) == -0.6
    z = wind.roof_cp_parallel(0.75)
    assert [round(v[3], 3) for v in z] == [-1.1, -0.8, -0.6, -0.5]
    assert [v[3] for v in wind.roof_cp_parallel(0.2)] == [-0.9, -0.9, -0.5, -0.3] and [v[3] for v in wind.roof_cp_parallel(3)] == [-1.3, -0.7, -0.7, -0.7]


def test_mwfrs_pressures_by_hand():
    """115 mi/h, Exposure C, enclosed, 40 ft across the ridge x 60 ft along it, eave 16 ft, h = 20 ft,
    5 on 12 gable (22.62 degrees), wind normal to the ridge. By hand:
    qh = 0.00256(0.90)(115^2) = 30.47 psf; q15 = 0.00256(0.85)(115^2) = 28.78; Kz at 16 ft = 0.86, q16 = 29.12
    Kd G = 0.7225; internal = 30.47(0.85)(0.18) = 4.66 psf
    windward wall at 15 ft: 28.78(0.7225)(0.8) = 16.63; leeward (L/B = 0.667): 30.47(0.7225)(-0.5) = -11.01
    side: 30.47(0.7225)(-0.7) = -15.41
    h/L = 0.5: windward roof -0.4 + 0.1(2.62/5) = -0.3476 and 0.0 + 0.2(2.62/5) = 0.1048; leeward -0.6
    -> -7.65, 2.31, -13.21 psf."""
    import math
    th = math.degrees(math.atan(5 / 12))
    r = wind.mwfrs(115, "C", h=20, eave=16, B=60, L=40, enclosure="enclosed", direction="normal", theta=th)
    assert r["qh"] == pytest.approx(30.47, abs=0.01) and r["L_over_B"] == pytest.approx(0.667, abs=0.001)
    w15, w16 = r["windward"]
    assert w15.external == pytest.approx(16.63, abs=0.01) and w16.q == pytest.approx(29.12, abs=0.01)
    assert w15.p_pos_internal == pytest.approx(16.63 - 4.66, abs=0.01) and w15.p_neg_internal == pytest.approx(16.63 + 4.66, abs=0.01)
    assert r["leeward"].external == pytest.approx(-11.01, abs=0.01) and r["side"].external == pytest.approx(-15.41, abs=0.01)
    assert [round(s.Cp, 4) for s in r["roof"]] == [-0.3476, 0.1048, -0.6]
    assert [round(s.external, 2) for s in r["roof"]] == [-7.65, 2.31, -13.21]
    assert r["walls_together"][0][1] == pytest.approx(16.63 + 11.01, abs=0.01)
    # parallel to the ridge: B = 40, L = 60, h/L = 0.333: zones to 10, 20, 40 and 60 ft
    p = wind.mwfrs(115, "C", h=20, eave=16, B=40, L=60, enclosure="partially enclosed", direction="parallel", theta=th)
    assert [(s.zone[1], s.zone[2], s.Cp) for s in p["roof"][:-1]] == [(0, 10, -0.9), (10, 20, -0.9), (20, 40, -0.5), (40, 60, -0.3)]
    assert p["roof"][-1].Cp == -0.18 and p["leeward"].Cp == pytest.approx(-0.4) and p["GCpi"] == 0.55
    with pytest.raises(wind.WindError):
        wind.mwfrs(115, "C", 20, 16, 40, 60, "open", "normal", th)


def test_mwfrs_sheet_and_form(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WM1", V="115", V_source="ASCE 7 Hazard Tool, Risk Category II", exposure="C", exposure_basis="open terrain, Sect. 26.7.3",
             enclosure="enclosed", enclosure_basis="Sect. 26.12", across="40", along="60", eave="16", h="20", theta="22.62",
             Kzt="1.0", Kzt_source="no hill, ridge or escarpment, Sect. 26.8.1", elevation="6200", elevation_source="site survey")
    sheet, kind, _ = calc.build("wind_mwfrs", v, dict(job="2026-000", name="Test", method="ASD"))
    assert kind == "simple" and len(sheet.blocks) == 3 and sheet.blocks[0]["picture"][0] == "wind_mwfrs" and sheet.wind["qh"] == pytest.approx(30.47 * wind.ke(6200), abs=0.01)
    assert any("windward roof" in t for t in sheet.blocks[1]["lines"]) and any("0 to h/2 (0.0 to 10.0 ft)" in t for t in sheet.blocks[2]["lines"])
    out = tmp_path / "w.pdf"
    calcsheet._simple_pdf(sheet, str(out), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    assert out.stat().st_size > 2000
    flat, _, _ = calc.build("wind_mwfrs", dict(v, theta="0", h="16"), dict(job="2026-000", name="Test", method="ASD"))
    calcsheet._simple_pdf(flat, str(tmp_path / "f.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    assert "zones" in flat.blocks[0]["picture"][1]["panels"][0]
    v2 = dict(v, enclosure_basis="")
    with pytest.raises(calc.Missing):
        calc.build("wind_mwfrs", v2, dict(job="2026-000", name="Test", method="ASD"))


def test_mwfrs_total_force_and_monoslope_by_hand():
    """Same gable building as above (Ke = 1), wind normal to the ridge, B = 60 ft:
    windward wall 16.6335(60)(15) + 16.8292(60)(1) = 15,980 lb; leeward 11.0074(960) = 10,567 lb; walls 26,547 lb
    rise = 20 tan(22.62) = 8.333 ft; roof horizontal = (windward - leeward)(60)(8.333):
    (-7.653 + 13.209)(500) = 2,778 lb and (2.306 + 13.209)(500) = 7,758 lb; total 34,305 lb
    minimum 16(960) + 8(500) = 19,360 lb.
    Wind parallel: gable end wall area 40(16) + 40(8.333)/2 = 806.7 ft2; no roof term.
    Monoslope, 3 on 12 (14.04 degrees), 40 ft across: rise 10.0 ft. Toward the low eave: the windward roof values
    -0.9 + 0.2(4.04/5) = -0.738 and -0.18 on the whole roof; leeward wall 26 ft high: 11.0074(60)(26.0) = 17,173 lb;
    roof suction pulls upwind, so the total is the walls alone. Toward the high eave: the leeward value -0.5 on the
    whole roof, +11.0074(60)(10.0) = 6,606 lb; no roof area in the minimum (it is behind the high wall)."""
    import math
    th = math.degrees(math.atan(5 / 12))
    r = wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal", th)
    assert r["F_windward"] == pytest.approx(15980, abs=2) and r["F_leeward"] == pytest.approx(10567, abs=2)
    assert [round(x) for x in r["F_roof"]] == pytest.approx([2778, 7758], abs=2) and r["F_total"] == pytest.approx(34305, abs=3)
    assert r["F_min"] == pytest.approx(19360) and r["F_design"] == r["F_total"]
    p = wind.mwfrs(115, "C", 20, 16, 40, 60, "enclosed", "parallel", th)
    assert p["A_wall"] == pytest.approx(806.67, abs=0.01) and p["F_roof"] == [0.0] and p["F_min"] == pytest.approx(16 * 806.67, abs=1)
    assert p["windward"][-1].z == pytest.approx(24.333, abs=0.001)
    tm = math.degrees(math.atan(3 / 12))
    lo = wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal_low", tm, roof="monoslope")
    assert [round(s.Cp, 3) for s in lo["roof"]] == [-0.739, -0.18] or [round(s.Cp, 3) for s in lo["roof"]] == [-0.738, -0.18]
    assert lo["F_leeward"] == pytest.approx(11.0074 * 60 * 26.0, abs=2) and lo["F_total"] == lo["F_walls"] and lo["A_roof"] == pytest.approx(600)
    hi = wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal_high", tm, roof="monoslope")
    assert [s.Cp for s in hi["roof"]] == [-0.5] and hi["F_roof"][0] == pytest.approx(6604, abs=3) and hi["A_roof"] == 0.0
    assert hi["A_wall"] == pytest.approx(60 * 26.0) and hi["F_total"] == pytest.approx(hi["F_walls"] + hi["F_roof"][0])
    low = wind.mwfrs(60, "B", 20, 16, 60, 40, "enclosed", "normal", th)      # a low wind speed: the minimum governs
    assert low["F_design"] == low["F_min"] > low["F_total"]
    with pytest.raises(wind.WindError):
        wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal", tm, roof="monoslope")


def test_mwfrs_monoslope_sheet(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WM2", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="partially enclosed",
             enclosure_basis="Sect. 26.12", across="40", along="60", eave="16", h="21", theta="14.04", roof="monoslope",
             Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_mwfrs", v, dict(job="2026-000", name="Test", method="ASD"))
    assert len(sheet.blocks) == 4 and [p["shape"] for p in sheet.blocks[0]["picture"][1]["panels"]] == ["mono", "mono", "flat"]
    assert any("design horizontal force" in t for t in sheet.blocks[1]["lines"])
    calcsheet._simple_pdf(sheet, str(tmp_path / "m.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    from strukit.ws_steel_beam import WorksheetError
    with pytest.raises(WorksheetError):
        calc.build("wind_mwfrs", dict(v, theta="0"), dict(job="2026-000", name="Test", method="ASD"))
