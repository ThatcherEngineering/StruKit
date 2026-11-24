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
    assert kind == "simple" and len(sheet.blocks) == 4 and sheet.blocks[0]["picture"][0] == "wind_mwfrs" and sheet.wind["qh"] == pytest.approx(30.47 * wind.ke(6200), abs=0.01)
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
    assert len(sheet.blocks) == 5 and [p["shape"] for p in sheet.blocks[0]["picture"][1]["panels"]] == ["mono", "mono", "flat"]
    assert any("design horizontal force" in t for t in sheet.blocks[1]["lines"])
    calcsheet._simple_pdf(sheet, str(tmp_path / "m.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    from strukit.ws_steel_beam import WorksheetError
    with pytest.raises(WorksheetError):
        calc.build("wind_mwfrs", dict(v, theta="0"), dict(job="2026-000", name="Test", method="ASD"))


def test_cc_walls_by_hand(tmp_path):
    """Figure 30.3-1 end values, and by hand at 100 ft2: f = (2 - 1)/(log 500 - 1) = 0.5886;
    positive 1.0 - 0.3(0.5886) = 0.823; zone 4 -1.1 + 0.3(0.5886) = -0.923; zone 5 -1.4 + 0.6(0.5886) = -1.047.
    115 mi/h, Exposure C, h = 20 ft: qh = 30.47 psf; enclosed: p+ = 30.47(0.85)(0.823 + 0.18) = 25.99 psf;
    zone 4: 30.47(0.85)(-0.923 - 0.18) = -28.58; zone 5: 30.47(0.85)(-1.047 - 0.18) = -31.78.
    a for a 40 ft least dimension, h = 20 ft: min(4, 8) = 4 ft."""
    assert wind.cc_wall_gcp(5, "positive", 20) == 1.0 and wind.cc_wall_gcp(10, 5, 20) == -1.4 and wind.cc_wall_gcp(10, 4, 20) == -1.1
    assert wind.cc_wall_gcp(500, 5, 20) == pytest.approx(-0.8) and wind.cc_wall_gcp(2000, 4, 20) == pytest.approx(-0.8)
    assert wind.cc_wall_gcp(700, "positive", 20) == pytest.approx(0.7) and wind.cc_wall_gcp(10, 5, 10) == pytest.approx(-1.26)
    r = wind.cc_walls(115, "C", 20, 40, "enclosed", [100, 10], theta=22.6)
    assert r["a"] == 4.0 and [x["area"] for x in r["rows"]] == [10, 100]
    x = r["rows"][1]
    assert x["gcp"]["positive"] == pytest.approx(0.823, abs=0.001) and x["gcp"][4] == pytest.approx(-0.923, abs=0.001) and x["gcp"][5] == pytest.approx(-1.047, abs=0.001)
    assert x["design"]["positive"] == pytest.approx(25.99, abs=0.03) and x["design"][4] == pytest.approx(-28.58, abs=0.03) and x["design"][5] == pytest.approx(-31.78, abs=0.03)
    assert wind.cc_a(200, 15) == 8.0 and wind.cc_a(20, 30) == 3.0 and wind.cc_a(400, 20, 5) == 16.0 and wind.cc_a(400, 12, 20) == 16.0
    low = wind.cc_walls(70, "B", 15, 40, "enclosed", [500])["rows"][0]            # the 16 psf minimum governs
    assert low["design"] == {"positive": 16.0, 4: -16.0, 5: -16.0} and abs(low["p"][4]) < 16
    with pytest.raises(wind.WindError):
        wind.cc_walls(115, "C", 70, 40, "enclosed", [10])
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WC1", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
             enclosure_basis="Sect. 26.12", h="20", least="40", theta="22.6", areas="10, 20, 50, 100, 200, 500", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, kind, _ = calc.build("wind_cc_walls", v, dict(job="2026-000", name="Test", method="ASD"))
    assert kind == "simple" and len(sheet.blocks[1]["lines"]) == 8
    calcsheet._simple_pdf(sheet, str(tmp_path / "c.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")


def test_cc_roof_low_slope_by_hand(tmp_path):
    """Figure 30.3-2A end values, and by hand at 100 ft2: f = 1/(log 500 - 1) = 0.5886:
    zone 1 -1.7 + 0.7(0.5886) = -1.288; zone 2 -2.3 + 0.9(0.5886) = -1.770; zone 3 -3.2 + 1.8(0.5886) = -2.141;
    zone 1' -0.9; positive 0.2. At 300 ft2 zone 1': -0.9 + 0.5 log(3) = -0.661.
    115 mi/h, Exposure C, h = 20 ft, enclosed: qh Kd = 30.47(0.85) = 25.90; zone 3 at 100 ft2: 25.90(-2.141 - 0.18) = -60.1 psf;
    positive: 25.90(0.2 + 0.18) = 9.8 -> 16 psf minimum."""
    g = wind.cc_roof_gcp
    assert g(10, "3") == -3.2 and g(1, "2") == -2.3 and g(10, "1") == -1.7 and g(50, "1'") == -0.9 and g(5, "positive") == 0.3
    assert g(500, "3") == pytest.approx(-1.4) and g(500, "2") == pytest.approx(-1.4) and g(900, "1") == pytest.approx(-1.0)
    assert g(1000, "1'") == pytest.approx(-0.4) and g(100, "positive") == pytest.approx(0.2) and g(300, "1'") == pytest.approx(-0.661, abs=0.001)
    assert g(100, "1") == pytest.approx(-1.288, abs=0.001) and g(100, "2") == pytest.approx(-1.770, abs=0.001) and g(100, "3") == pytest.approx(-2.141, abs=0.001)
    r = wind.cc_roof(115, "C", 20, "enclosed", [100])
    x = r["rows"][0]
    assert x["design"]["3"] == pytest.approx(-60.1, abs=0.1) and x["design"]["positive"] == 16.0 and x["p"]["positive"] == pytest.approx(9.84, abs=0.02)
    assert r["edge"] == 12.0 and r["corner"] == 4.0
    with pytest.raises(wind.WindError):
        wind.cc_roof(115, "C", 20, "enclosed", [100], theta=15)          # the least horizontal dimension is needed
    with pytest.raises(wind.WindError):
        wind.cc_roof(115, "C", 20, "enclosed", [100], theta=50, least_dim=40)
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WR1", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
             enclosure_basis="Sect. 26.12", h="20", theta="1.2", areas="10, 20, 50, 100, 200, 500, 1000", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, kind, _ = calc.build("wind_cc_roof", v, dict(job="2026-000", name="Test", method="ASD"))
    assert kind == "simple" and len(sheet.blocks[1]["lines"]) == 8
    calcsheet._simple_pdf(sheet, str(tmp_path / "r.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")


def test_cc_roof_gable_figures_by_hand(tmp_path):
    """Figures 30.3-2B, 2C, 2D end values as read, and by hand at 50 ft2 on a roof at 18 degrees (Figure 30.3-2B):
    zone 3: -3.6 + 1.8 log(5)/1 = -2.342; zone 2: -2.7 + 1.7 log(5)/log(20) = -1.787; zone 1: -2.0 + 1.5 log(5)/log(30) = -1.290;
    positive: 0.6 - 0.3 log(5)/log(20) = 0.439."""
    g, F = wind.cc_roof_gcp, wind.cc_roof_figure
    assert [F(t) for t in (0, 7, 7.1, 20, 20.5, 27, 27.5, 45)] == ["30.3-2A"] * 2 + ["30.3-2B"] * 2 + ["30.3-2C"] * 2 + ["30.3-2D"] * 2
    ends = {15: {"positive": (0.6, 200, 0.3), "1": (-2.0, 300, -0.5), "2": (-2.7, 200, -1.0), "3": (-3.6, 100, -1.8)},
            25: {"positive": (0.6, 200, 0.3), "1": (-1.5, 200, -0.8), "2": (-2.5, 100, -1.2), "3": (-3.0, 100, -1.4)},
            35: {"positive": (0.9, 200, 0.5), "1": (-1.8, 100, -0.8), "2": (-2.0, 200, -1.0), "3": (-2.5, 200, -1.0)}}
    for th, zs in ends.items():
        for z, (v10, A2, v2) in zs.items():
            assert g(10, z, th) == v10 and g(3, z, th) == v10 and g(A2, z, th) == pytest.approx(v2) and g(1000, z, th) == pytest.approx(v2)
    assert g(50, "3", 18) == pytest.approx(-2.342, abs=0.001) and g(50, "2", 18) == pytest.approx(-1.787, abs=0.001)
    assert g(50, "1", 18) == pytest.approx(-1.290, abs=0.001) and g(50, "positive", 18) == pytest.approx(0.439, abs=0.001)
    with pytest.raises(wind.WindError):
        g(50, "1'", 18)
    r = wind.cc_roof(115, "C", 20, "enclosed", [50], theta=18, least_dim=40)
    assert r["a"] == 4.0 and r["zones"] == ("1", "2", "3") and r["figure"] == "30.3-2B"
    assert r["rows"][0]["design"]["3"] == pytest.approx(30.4704 * 0.85 * (-2.342 - 0.18), abs=0.05)
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WR2", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
             enclosure_basis="Sect. 26.12", h="20", theta="22.62", least="40", areas="10, 50, 100", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, kind, _ = calc.build("wind_cc_roof", v, dict(job="2026-000", name="Test", method="ASD"))
    assert sheet.wind["figure"] == "30.3-2C" and len(sheet.blocks[1]["lines"]) == 4
    calcsheet._simple_pdf(sheet, str(tmp_path / "r.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("wind_cc_roof", dict(v, least=""), dict(job="2026-000", name="Test", method="ASD"))


def test_cc_roof_monoslope(tmp_path):
    """Figures 30.3-5A and 5B end values as read (every line runs from 10 to 100 ft2), and by hand at 30 ft2 on a
    roof at 14 degrees (5B): zone 3: -2.9 + 0.9 log(3) = -2.471; zone 2: -1.6 + 0.4 log(3) = -1.409."""
    g, F = wind.cc_roof_gcp, wind.cc_roof_figure
    assert [F(t, "monoslope") for t in (0, 3, 3.5, 10, 10.5, 30)] == ["30.3-2A"] * 2 + ["30.3-5A"] * 2 + ["30.3-5B"] * 2
    ends = {5: {"positive": (0.3, 0.2), "1": (-1.1, -1.1), "2": (-1.3, -1.2), "2'": (-1.6, -1.5), "3": (-1.8, -1.2), "3'": (-2.6, -1.6)},
            20: {"positive": (0.4, 0.3), "1": (-1.3, -1.1), "2": (-1.6, -1.2), "3": (-2.9, -2.0)}}
    for th, zs in ends.items():
        for z, (v10, v100) in zs.items():
            assert g(4, z, th, "monoslope") == v10 and g(100, z, th, "monoslope") == pytest.approx(v100) and g(900, z, th, "monoslope") == pytest.approx(v100)
    assert g(30, "3", 14, "monoslope") == pytest.approx(-2.471, abs=0.001) and g(30, "2", 14, "monoslope") == pytest.approx(-1.409, abs=0.001)
    with pytest.raises(wind.WindError):
        F(35, "monoslope")
    r = wind.cc_roof(115, "C", 20, "enclosed", [30], theta=2, roof="monoslope")
    assert r["figure"] == "30.3-2A" and "edge" in r
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WR3", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
             enclosure_basis="Sect. 26.12", h="21", theta="14.04", roof="monoslope", least="40", areas="10, 30, 100", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    for th, fig, kind in (("14.04", "30.3-5B", "mono_b"), ("6", "30.3-5A", "mono_a")):
        sheet, _, _ = calc.build("wind_cc_roof", dict(v, theta=th), dict(job="2026-000", name="Test", method="ASD"))
        assert sheet.wind["figure"] == fig and sheet.blocks[0]["picture"][1]["kind"] == kind
        calcsheet._simple_pdf(sheet, str(tmp_path / f"{kind}.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("wind_cc_roof", dict(v, theta="6", least=""), dict(job="2026-000", name="Test", method="ASD"))


def test_cc_roof_overhang_by_hand(tmp_path):
    """Sect. 30.7, gable roof at 18 degrees, 50 ft2: roof zone 3 -2.342, zone 2 -1.787, zone 1 -1.290 (test above);
    wall positive at 50 ft2: 1.0 - 0.3 log(5)/log(50) = 0.877; overhang (GCp) = -3.219, -2.664, -2.167;
    115 mi/h, Exposure C, h = 20 ft, enclosed: zone 3: 30.47(0.85)(-3.219 - 0.18) = -88.0 psf."""
    r = wind.cc_roof(115, "C", 20, "enclosed", [50], theta=18, least_dim=40, overhang=True)
    x = r["rows"][0]
    assert x["overhang_wall"] == pytest.approx(0.877, abs=0.001)
    assert [round(x["overhang_gcp"][z], 3) for z in ("3", "2", "1")] == pytest.approx([-3.219, -2.664, -2.167], abs=0.002)
    assert x["overhang"]["3"] == pytest.approx(-88.0, abs=0.1)
    # Figure 30.3-2A overhang chart: values at the break points, and zone 3 at 100 ft2: -3.2 + 2.1/log(50) = -1.964
    f = wind.cc_roof(115, "C", 20, "enclosed", [5, 10, 100, 500, 2000], theta=5, overhang=True)["rows"]
    assert [x["overhang_gcp"]["1"] for x in f] == pytest.approx([-1.7, -1.7, -1.6, -1.1, -1.1])
    assert [x["overhang_gcp"]["2"] for x in f] == pytest.approx([-2.3, -2.3, -1.6, -1.1, -1.1]) and f[0]["overhang_gcp"]["1'"] == -1.7
    assert [round(x["overhang_gcp"]["3"], 3) for x in f] == pytest.approx([-3.2, -3.2, -1.964, -1.1, -1.1]) and f[0]["overhang_wall"] is None
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WR4", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
             enclosure_basis="Sect. 26.12", h="20", theta="18", least="40", overhang="yes", areas="10, 50, 100", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_cc_roof", v, dict(job="2026-000", name="Test", method="ASD"))
    assert len(sheet.blocks) == 3 and "downward pressure on roof overhangs" in sheet.not_checked
    flat, _, _ = calc.build("wind_cc_roof", dict(v, theta="2", least=""), dict(job="2026-000", name="Test", method="ASD"))
    assert len(flat.blocks) == 3 and "wall +" not in flat.blocks[2]["lines"][0]
    calcsheet._simple_pdf(flat, str(tmp_path / "of.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    calcsheet._simple_pdf(sheet, str(tmp_path / "o.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")


def test_cc_parapet_and_note_5_by_hand(tmp_path):
    """Flat roof, eave 20 ft, top of parapet 24 ft, 115 mi/h, Exposure C, 10 ft2. Wall values carry the 10 percent
    reduction of Figure 30.3-1 note 5 (roof at 10 degrees or less): +0.9, zone 4 -0.99, zone 5 -1.26; roof zone 2 -2.3,
    zone 3 -3.2. Kz at 24 ft = 0.90 + 0.04(4/5) = 0.932; qp = 0.00256(0.932)(115^2) = 31.55 psf; qp Kd = 26.82.
    Case A edge: 26.82(0.9 + 2.3) = 85.8 psf; corner: 26.82(0.9 + 3.2) = 110.0; Case B edge: 26.82(0.9 + 0.99) = 50.7;
    corner: 26.82(0.9 + 1.26) = 57.9."""
    r = wind.cc_parapet(115, "C", 24, 20, 40, [10])
    x = r["rows"][0]
    assert r["qp"] == pytest.approx(31.55, abs=0.01) and r["a"] == 4.0 and r["edge"] == 12.0
    assert x["p"]["A_edge"] == pytest.approx(85.8, abs=0.1) and x["p"]["A_corner"] == pytest.approx(110.0, abs=0.1)
    assert x["p"]["B_edge"] == pytest.approx(50.7, abs=0.1) and x["p"]["B_corner"] == pytest.approx(57.9, abs=0.1)
    for bad in (dict(hp_top=20), dict(theta=12)):
        with pytest.raises(wind.WindError):
            wind.cc_parapet(**dict(dict(V=115, exposure="C", hp_top=24, h=20, least_dim=40, areas=[10]), **bad))
    # Figure 30.3-2A note 5 on the roof sheet: zone 3 = zone 2; positive in zones 2 and 3 from the wall chart
    n = wind.cc_roof(115, "C", 20, "enclosed", [10], parapet=True)["rows"][0]
    assert n["gcp"]["3"] == -2.3 and n["design"]["3"] == n["design"]["2"] and n["edge_positive_gcp"] == pytest.approx(0.9)
    assert n["edge_positive"] == pytest.approx(30.4704 * 0.85 * (0.9 + 0.18), abs=0.02)
    with pytest.raises(wind.WindError):
        wind.cc_roof(115, "C", 20, "enclosed", [10], theta=18, least_dim=40, parapet=True)
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WP1", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", hp="24", h="20", least="40", theta="0",
             areas="10, 50, 100", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, kind, _ = calc.build("wind_cc_parapet", v, dict(job="2026-000", name="Test", method="ASD"))
    assert kind == "simple" and len(sheet.blocks[0]["lines"]) == 5
    calcsheet._simple_pdf(sheet, str(tmp_path / "p.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    v2 = dict(mark="WR5", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
              enclosure_basis="Sect. 26.12", h="20", theta="0", parapet="yes", areas="10, 50, 100", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet2, _, _ = calc.build("wind_cc_roof", v2, dict(job="2026-000", name="Test", method="ASD"))
    assert "+ (2, 3)" in sheet2.blocks[1]["lines"][0] and "the parapets themselves (Sect. 30.6)" in sheet2.not_checked
    calcsheet._simple_pdf(sheet2, str(tmp_path / "r5.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")


def test_mwfrs_parapets_by_hand():
    """Flat roof, eave 20 ft, 3 ft parapets, 115 mi/h, Exposure C, B = 60 ft, L = 40 ft. Kz at 23 ft = 0.90 + 0.04(3/5) = 0.924;
    qp = 0.00256(0.924)(115^2) = 31.28 psf; windward 31.28(0.85)(1.5) = +39.9 psf; leeward 31.28(0.85)(-1.0) = -26.6 psf;
    force (39.88 + 26.59)(60)(3) = 11,965 lb; minimum wall area 60(20) + 60(3) = 1,380 ft2."""
    r = wind.mwfrs(115, "C", 20, 20, 60, 40, "enclosed", "normal", 0.0, parapet=3)
    n = wind.mwfrs(115, "C", 20, 20, 60, 40, "enclosed", "normal", 0.0)
    p = r["parapet"]
    assert p["q_windward"] == pytest.approx(31.28, abs=0.01) and p["p_windward"] == pytest.approx(39.9, abs=0.05) and p["p_leeward"] == pytest.approx(-26.6, abs=0.05)
    assert p["F"] == pytest.approx(11965, abs=10) and r["F_walls"] == pytest.approx(n["F_walls"] + p["F"]) and r["A_wall"] == 1380 and n["parapet"] is None
    from strukit.gui import calc
    v = dict(mark="WM3", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed", enclosure_basis="Sect. 26.12",
             across="40", along="60", eave="20", h="20", theta="0", parapet="3", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_mwfrs", v, dict(job="2026-000", name="Test", method="ASD"))
    assert any("parapets, 3 ft high" in t for t in sheet.blocks[1]["lines"]) and "roof overhangs (Sect. 27.3.3)" in sheet.not_checked


def test_wind_load_cases_by_hand():
    """Fx = 10,000 lb on walls 60 ft wide, Fy = 6,000 lb on walls 40 ft wide: Case 2 x: 7,500 lb with 7,500(9) = 67,500 lb-ft;
    Case 2 y: 4,500 lb with 4,500(6) = 27,000 lb-ft; Case 3: 7,500 and 4,500; Case 4: 5,630 and 3,378 with
    0.563(10,000)(9) + 0.563(6,000)(6) = 70,938 lb-ft."""
    c = {k: (fx, fy, m) for k, fx, fy, m in wind.load_cases(10000, 60, 6000, 40)}
    assert c["Case 1, x"] == (10000, 0, 0) and c["Case 2, x"] == pytest.approx((7500, 0, 67500)) and c["Case 2, y"] == pytest.approx((0, 4500, 27000))
    assert c["Case 3"] == pytest.approx((7500, 4500, 0)) and c["Case 4"] == pytest.approx((5630, 3378, 70938))
    from strukit.gui import calc
    v = dict(mark="WM4", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed", enclosure_basis="Sect. 26.12",
             across="40", along="60", eave="16", h="20", theta="22.62", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_mwfrs", v, dict(job="2026-000", name="Test", method="ASD"))
    lc = sheet.wind["load_cases"]
    assert lc[0][1] == pytest.approx(sheet.wind["normal"]["F_walls"]) and lc[2][3] == pytest.approx(0.75 * lc[0][1] * 0.15 * 60)
    assert sheet.blocks[-1]["title"].startswith("Design Wind Load Cases") and len(sheet.blocks[-1]["lines"]) == 7


def test_wind_line_load_to_a_diaphragm_by_hand():
    """Gable building of the tests above, wind normal to the ridge (B = 60 ft, eave 16 ft, Ke = 1): windward 16.63 psf to 15 ft and
    16.83 psf from 15 to 16 ft; leeward 11.01 psf. Roof diaphragm taking the wall from 8 ft to the eave:
    windward 16.63(7) + 16.83(1) = 133.3 plf; leeward 11.01(8) = 88.1 plf; roof horizontal 7,758/60 = 129.3 plf; total 350.7 plf.
    Minimum 16(8) + 8(8.333) = 194.7 plf. Floor diaphragm from 0 to 8 ft: (16.63 + 11.01)(8) = 221.1 plf, no roof term.
    Wind parallel to the ridge (B = 40 ft), 8 ft to the ridge at 24.33 ft: wall area 40(8) + 40(8.333)/2 = 486.7 ft2, 12.17 ft average."""
    import math
    th = math.degrees(math.atan(5 / 12))
    r = wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal", th)
    a = wind.line_load(r, 8, 16)
    assert a["windward"] == pytest.approx(133.3, abs=0.1) and a["leeward"] == pytest.approx(88.1, abs=0.1) and a["roof"] == pytest.approx(129.3, abs=0.1)
    assert a["w"] == pytest.approx(350.7, abs=0.2) and a["w_min"] == pytest.approx(194.7, abs=0.1) and a["at_top"]
    f = wind.line_load(r, 0, 8)
    assert f["w"] == pytest.approx(221.1, abs=0.1) and f["roof"] == 0.0 and not f["at_top"]
    assert a["w_pressures"] * 60 + f["w_pressures"] * 60 == pytest.approx(r["F_walls"] + max(r["F_roof"]), rel=1e-9)     # the two diaphragms take the whole force
    p = wind.mwfrs(115, "C", 20, 16, 40, 60, "enclosed", "parallel", th)
    g = wind.line_load(p, 8, 16 + 20 * math.tan(math.radians(th)))
    assert g["w_min"] == pytest.approx(16 * 486.67 / 40, abs=0.1) and g["leeward"] == pytest.approx(-p["leeward"].external * 486.67 / 40, abs=0.1)
    low = wind.mwfrs(60, "B", 20, 16, 60, 40, "enclosed", "normal", th)
    assert wind.line_load(low, 8, 16)["governs"] == "the minimum of Sect. 27.1.5"
    with pytest.raises(wind.WindError):
        wind.line_load(r, 8, 30)


def test_wind_line_api():
    from strukit.gui import server
    v = dict(mark="WM5", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed", enclosure_basis="Sect. 26.12",
             across="40", along="60", eave="16", h="20", theta="22.62", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    got = server.api("/api/wind_line", dict(values=v, project={}, z1="8", z2="16"))
    d = got["directions"]
    assert [x["title"] for x in d] == ["Wind Normal to the Ridge", "Wind Parallel to the Ridge"] and d[0]["w"] == pytest.approx(350.7, abs=0.3) and d[0]["B"] == 60
    assert "error" in server.api("/api/wind_line", dict(values=v, project={}, z1="", z2="16"))
    assert d[1]["to"] == pytest.approx(24.33, abs=0.01) and d[0]["to"] == 16 and d[1]["w"] > 0
    assert "error" in server.api("/api/wind_line", dict(values=v, project={}, z1="20", z2="12"))
    assert "error" in server.api("/api/wind_line", dict(values=dict(v, V=""), project={}, z1="8", z2="16"))


def test_mwfrs_hip_roof_by_hand(tmp_path):
    """40 ft across x 60 ft along, eave 16 ft, h 20 ft, all slopes 5 on 12 (22.62 degrees), 115 mi/h, Exposure C, enclosed.
    rise 8.333 ft, hip run 20 ft, ridge 20 ft. Wind normal to the ridge (B 60, L 40): walls to the eave 26,547 lb as the gable;
    facing plane projected (60 + 20)/2 x 8.333 = 333.3 ft2; Cp -0.3476 / 0.1048 windward, -0.6 leeward:
    (-7.653 + 13.209)(333.3) = 1,852 lb; (2.306 + 13.209)(333.3) = 5,172 lb; total 31,719 lb. Side slopes by zones.
    Wind parallel (B 40, L 60, h/L 0.333): windward Cp at 22.62 degrees between the h/L rows: -0.2809 / 0.2032; projected 40(8.333)/2 = 166.7 ft2."""
    import math
    th = math.degrees(math.atan(5 / 12))
    n = wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal", th, roof="hip", theta_hip=th)
    assert n["ridge"] == pytest.approx(20) and n["A_roof"] == pytest.approx(333.33, abs=0.01) and n["F_walls"] == pytest.approx(26547, abs=3)
    assert [round(x) for x in n["F_roof"]] == pytest.approx([1852, 5172], abs=2) and n["F_total"] == pytest.approx(31719, abs=4)
    names = [s.name for s in n["roof"]]
    assert names[:3] == ["windward roof", "windward roof", "leeward roof"] and names[-1] == "sides, all zones" and n["roof"][3].zone[0] == "0 to h/2"
    p = wind.mwfrs(115, "C", 20, 16, 40, 60, "enclosed", "parallel", th, roof="hip", theta_hip=th)
    assert [round(s.Cp, 4) for s in p["roof"][:3]] == pytest.approx([-0.2809, 0.2032, -0.6], abs=0.0002) and p["A_roof"] == pytest.approx(166.67, abs=0.01)
    assert p["top_w"] == 16 and p["taper"] == 0.0 and p["F_min"] == pytest.approx(16 * 40 * 16 + 8 * 166.67, abs=1)
    low = wind.mwfrs(115, "C", 20, 16, 60, 40, "enclosed", "normal", 8.0, roof="hip", theta_hip=30.0)       # facing slope under 10 degrees: zones only
    assert not low["sloped"] and low["F_roof"] == [0.0] and all(s.name.startswith("roof") for s in low["roof"])
    with pytest.raises(wind.WindError):
        wind.mwfrs(115, "C", 20, 16, 40, 60, "enclosed", "parallel", th, roof="hip", theta_hip=10.0)     # hip run 47 ft: the ends meet
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WM6", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed", enclosure_basis="Sect. 26.12",
             across="40", along="60", eave="16", h="20", theta="22.62", roof="hip", theta_hip="22.62", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_mwfrs", v, dict(job="2026-000", name="Test", method="ASD"))
    pans = sheet.blocks[0]["picture"][1]["panels"]
    assert [x["shape"] for x in pans] == ["gable", "gable"] and pans[0]["top"] == 0.0 and pans[1]["top"] == pytest.approx(20, abs=0.05)
    assert any("Hip roof:" in t for t in sheet.assumptions) and any("sides, 0 to h/2" in t for t in sheet.blocks[1]["lines"])
    calcsheet._simple_pdf(sheet, str(tmp_path / "h.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("wind_mwfrs", dict(v, theta_hip=""), dict(job="2026-000", name="Test", method="ASD"))


def test_cc_roof_hip(tmp_path):
    """Figures 30.3-2E, 2F, 2G end values as read, and note 6 by hand at 36 degrees (halfway), 10 ft2: zone 3 (-2.0 - 2.4)/2 = -2.2;
    zone 1 (-1.4 - 1.5)/2 = -1.45; at 100 ft2 zone 2 (-1.0 - 0.8)/2 = -0.9. 2E zone 3 at 50 ft2: -2.6 + 1.2 log(5)/log(20) = -2.6 + 1.2(0.5372) = -1.955."""
    g, F = wind.cc_roof_gcp, wind.cc_roof_figure
    assert [F(t, "hip") for t in (5, 7, 15, 20, 24, 27, 30, 45)] == ["30.3-2A"] * 2 + ["30.3-2E"] * 2 + ["30.3-2F"] * 2 + ["30.3-2F and 30.3-2G", "30.3-2G"]
    ends = {15: {"positive": (0.7, 100, 0.3), "1": (-1.8, 200, -0.8), "2": (-2.4, 200, -1.3), "3": (-2.6, 200, -1.4)},
            25: {"positive": (0.7, 100, 0.3), "1": (-1.4, 100, -0.8), "2": (-2.0, 100, -1.0), "3": (-2.0, 100, -1.0)},
            45: {"positive": (0.7, 100, 0.3), "1": (-1.5, 100, -0.7), "2": (-1.8, 100, -0.8), "3": (-2.4, 100, -1.0)}}
    for th, zs in ends.items():
        for z, (v10, A2, v2) in zs.items():
            assert g(10, z, th, "hip") == v10 and g(2, z, th, "hip") == v10 and g(A2, z, th, "hip") == pytest.approx(v2) and g(1000, z, th, "hip") == pytest.approx(v2)
    assert g(10, "3", 36, "hip") == pytest.approx(-2.2) and g(10, "1", 36, "hip") == pytest.approx(-1.45) and g(100, "2", 36, "hip") == pytest.approx(-0.9)
    assert g(50, "3", 15, "hip") == pytest.approx(-1.955, abs=0.001) and g(10, "3", 27.0001, "hip") == pytest.approx(-2.0, abs=0.001)
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="WR6", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed",
             enclosure_basis="Sect. 26.12", h="20", theta="30", roof="hip", least="40", areas="10, 50, 100", overhang="yes", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_cc_roof", v, dict(job="2026-000", name="Test", method="ASD"))
    assert sheet.wind["figure"] == "30.3-2F and 30.3-2G" and sheet.blocks[0]["picture"][1]["kind"] == "hip" and any("note 6" in t for t in sheet.assumptions)
    calcsheet._simple_pdf(sheet, str(tmp_path / "h.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    low, _, _ = calc.build("wind_cc_roof", dict(v, theta="5", overhang="no"), dict(job="2026-000", name="Test", method="ASD"))
    assert low.wind["figure"] == "30.3-2A"


def test_mwfrs_overhang_by_hand():
    """Sect. 27.3.3. Gable 26.57 degrees, h = 20 ft, 115 mi/h, Exposure C: qh = 30.47 psf; qh Kd G = 30.47(0.85)(0.85) = 22.015 psf;
    bottom 22.015(0.8) = 17.61 psf up; top, Cp -0.2686: -5.91 psf; net -23.53 psf; on a 2 ft projection 47.1 lb/ft uplift.
    Flat roof, h = 16 ft: Kh = 0.86, qh = 29.116 psf; bottom 21.036(0.8) = 16.83; top Cp -0.9: -18.93; net -35.76 psf."""
    o = wind.mwfrs_overhang(wind.mwfrs(115, "C", 20, 15, 60, 40, "enclosed", "normal", 26.57), 2)
    assert o["bottom"] == pytest.approx(17.61, abs=0.01) and o["net"] == pytest.approx(-23.53, abs=0.01) and o["w"] == pytest.approx(-47.05, abs=0.02) and len(o["values"]) == 2
    f = wind.mwfrs_overhang(wind.mwfrs(115, "C", 16, 16, 60, 40, "enclosed", "normal", 0), 2)
    assert f["bottom"] == pytest.approx(16.83, abs=0.01) and f["net"] == pytest.approx(-35.76, abs=0.01) and [v["Cp"] for v in f["values"]] == [-0.9, -0.18]
    for rf, d, kw in (("monoslope", "normal_low", {}), ("monoslope", "normal_high", {}), ("hip", "parallel", dict(theta_hip=30))):
        assert wind.mwfrs_overhang(wind.mwfrs(115, "C", 20, 15, 60, 40, "enclosed", d, 20, roof=rf, **kw), 1.5)["net"] < 0
    with pytest.raises(wind.WindError):
        wind.mwfrs_overhang(wind.mwfrs(115, "C", 16, 16, 60, 40, "enclosed", "normal", 0), 0)
    from strukit.gui import calc
    v = dict(mark="WM4", V="115", V_source="ASCE 7 Hazard Tool", exposure="C", exposure_basis="Sect. 26.7.3", enclosure="enclosed", enclosure_basis="Sect. 26.12",
             across="40", along="60", eave="15", h="20", theta="26.57", overhang="2", Kzt="1.0", Kzt_source="Sect. 26.8.1")
    sheet, _, _ = calc.build("wind_mwfrs", v, dict(job="2026-000", name="Test", method="ASD"))
    assert any("governing uplift 23.5 psf = 47 lb per ft" in t for t in sheet.blocks[1]["lines"]) and "parapets (Sect. 27.3.4)" in sheet.not_checked
    assert any("Sect. 27.3.3" in t for t in sheet.assumptions)


def test_mwfrs_against_the_published_three_story_example():
    """Wind Design Manual Based on the 2018 IBC and ASCE/SEI 7-16 (SEAOC/ICC), Design Example 8A,
    Tables 8A-1, 8A-2 and 8A-4: 145 mph, Exposure C, h = 45 ft, flat roof, 74'-8" by 146'-8",
    enclosed, 3 ft parapet.  The example rounds Kh to 1.07 from the ASCE 7-16 formula; ASCE 7-22
    gives 1.065, so pressures agree to within 1 percent."""
    book = {"normal": dict(lee_cp=-0.50, lee=(-29.6, -12.0), roof=((-0.98, -49.6, -32.0), (-0.86, -44.6, -27.0), (-0.54, -31.3, -13.7))),
            "parallel": dict(lee_cp=-0.31, lee=None, roof=((-0.90, None, None), (-0.90, None, None), (-0.50, None, None), (-0.30, None, None)))}
    for d, B, L in (("normal", 146.667, 74.667), ("parallel", 74.667, 146.667)):
        r = wind.mwfrs(145, "C", 45, 45, B, L, "enclosed", d, theta=0.0, parapet=3.0)
        assert r["qh"] * wind.KD_MWFRS == pytest.approx(49.0, rel=0.01)
        top = r["windward"][-1]
        assert (top.p_pos_internal, top.p_neg_internal) == pytest.approx((24.5, 42.1), rel=0.01)
        assert (r["side"].p_pos_internal, r["side"].p_neg_internal) == pytest.approx((-38.0, -20.3), rel=0.01)
        assert r["leeward"].Cp == pytest.approx(book[d]["lee_cp"], abs=0.005)
        if book[d]["lee"]:
            assert (r["leeward"].p_pos_internal, r["leeward"].p_neg_internal) == pytest.approx(book[d]["lee"], rel=0.01)
        zones = [s for s in r["roof"] if s.zone]
        assert len(zones) == len(book[d]["roof"])
        for s, (cp, p1, p2) in zip(zones, book[d]["roof"]):
            assert s.Cp == pytest.approx(cp, abs=0.005)
            if p1 is not None:
                assert (s.p_pos_internal, s.p_neg_internal) == pytest.approx((p1, p2), rel=0.01)
        other = [s for s in r["roof"] if not s.zone][0]
        assert (other.p_pos_internal, other.p_neg_internal) == pytest.approx((-16.3, 1.3), abs=0.15)
        assert r["parapet"]["p_windward"] == pytest.approx(73.5, rel=0.01)
        assert r["parapet"]["p_leeward"] == pytest.approx(-49.0, rel=0.01)


def test_cladding_against_the_published_three_story_example():
    """Wind Design Manual Based on the 2018 IBC and ASCE/SEI 7-16 (SEAOC/ICC), Design Example 8B,
    Tables 8B-2, 8B-3, 8B-5, 8B-6 and 8B-7 (same building as Example 8A; parapet over 3 ft).
    Coefficients agree to the two decimals printed; pressures to within 1 percent (Kh 1.07 against 1.065)."""
    w = wind.cc_walls(145, "C", 45, 74.667, "enclosed", [75, 114, 10, 17], theta=0.0)
    assert w["a"] == pytest.approx(7.5, abs=0.05)
    rows = {r["area"]: r for r in w["rows"]}
    book = {75: (0.76, -0.85, -0.98), 114: (0.73, -0.82, -0.92), 10: (0.90, -0.99, -1.26), 17: (0.86, -0.95, -1.19)}
    for area, (pos, z4, z5) in book.items():
        g = rows[area]["gcp"]
        assert (g["positive"], g[4], g[5]) == pytest.approx((pos, z4, z5), abs=0.005)
    assert (rows[75]["p"]["positive"], rows[75]["p"][4], rows[75]["p"][5]) == pytest.approx((46.1, -50.5, -56.9), rel=0.01)
    assert (rows[114]["p"]["positive"], rows[114]["p"][4], rows[114]["p"][5]) == pytest.approx((44.6, -49.0, -54.0), rel=0.01)

    c = wind.cc_roof(145, "C", 45, "enclosed", [192, 10], theta=0.0, least_dim=74.667, parapet=True)
    assert (c["edge"], c["corner"]) == pytest.approx((27.0, 9.0))
    rows = {r["area"]: r for r in c["rows"]}
    g = rows[192]["gcp"]
    assert (g["positive"], g["1'"], g["1"], g["2"], g["3"]) == pytest.approx((0.20, -0.76, -1.17, -1.62, -1.62), abs=0.005)
    assert rows[192]["edge_positive_gcp"] == pytest.approx(0.70, abs=0.005)
    g = rows[10]["gcp"]
    assert (g["positive"], g["1'"], g["1"], g["2"], g["3"]) == pytest.approx((0.30, -0.90, -1.70, -2.30, -2.30), abs=0.005)
    p = rows[192]["p"]
    assert (p["positive"], p["1'"], p["1"], p["2"]) == pytest.approx((18.6, -46.1, -66.2, -88.2), rel=0.01)
    assert rows[192]["edge_positive"] == pytest.approx(43.1, rel=0.01)


def test_topographic_factor_against_the_published_examples():
    """Wind Design Manual (SEAOC/ICC), Design Example 2: 2a escarpment, Exposure D, H = 266 ft, Lh = 320 ft, site 100 ft
    downwind, z = 33 ft: K1 = 0.475, K2 = 0.95, K3 = 0.85, Kzt = 1.93.  2b/2c hill, H = 660 ft, Lh = 2,100 ft, at the crest,
    z = 33 ft, K1 = 1.05(0.314) = 0.33, K3 = 0.94, Kzt = 1.72.  Parameters as printed in ASCE/SEI 7-22 Figure 26.8-1."""
    assert wind.TOPO["2D ridge"] == ({"B": 1.30, "C": 1.45, "D": 1.55}, 3.0, 1.5, 1.5)
    assert wind.TOPO["2D escarpment"] == ({"B": 0.75, "C": 0.85, "D": 0.95}, 2.5, 1.5, 4.0)
    assert wind.TOPO["3D axisymmetrical hill"] == ({"B": 0.95, "C": 1.05, "D": 1.15}, 4.0, 1.5, 1.5)
    a = wind.kzt("2D escarpment", "D", 266, 320, 100, 33, downwind=True)
    assert a["steep"] and a["L_used"] == 532 and a["K1"] == pytest.approx(0.475)
    assert a["K2"] == pytest.approx(0.953, abs=0.001) and a["K3"] == pytest.approx(0.856, abs=0.001) and a["Kzt"] == pytest.approx(1.93, abs=0.01)
    b = wind.kzt("3D axisymmetrical hill", "C", 660, 2100, 0, 33, downwind=False)
    assert b["K1"] == pytest.approx(0.33, abs=0.001) and b["K2"] == 1.0 and b["K3"] == pytest.approx(0.94, abs=0.002) and b["Kzt"] == pytest.approx(1.72, abs=0.01)
    # the figure's table (Exposure C multipliers): ridge H/Lh 0.30 -> K1 0.43; x/Lh 1.0 escarpment downwind -> K2 0.75; z/Lh 0.20 ridge -> K3 0.55
    t = wind.kzt("2D ridge", "C", 30, 100, 0, 20, downwind=False)
    assert t["K1"] == pytest.approx(0.43, abs=0.006) and t["K3"] == pytest.approx(0.55, abs=0.005)
    assert wind.kzt("2D escarpment", "C", 30, 100, 100, 0, downwind=True)["K2"] == pytest.approx(0.75)
    assert wind.kzt("2D ridge", "B", 80, 300, 0, 0, False)["k1_ratio"] == 1.45          # not less than the Exposure C multiplier
    assert wind.kzt("2D ridge", "C", 800, 1000, 2500, 0, True)["K2"] == 0.0
    for kw, word in ((dict(H=10, Lh=40), "condition 3"), (dict(H=30, Lh=200), "condition 2"), (dict(H=30, Lh=100, located=False), "condition 1")):
        r = wind.kzt("2D ridge", "C", kw["H"], kw["Lh"], 0, 15, False, located=kw.get("located", True))
        assert not r["applies"] and r["Kzt"] == 1.0 and word in r["why"] and r["Kzt_feature"] > 1.0
    assert not wind.kzt("2D ridge", "B", 50, 150, 0, 15, False)["applies"] and wind.kzt("2D ridge", "B", 60, 150, 0, 15, False)["applies"]


def test_topographic_factor_screen_and_sheet(tmp_path):
    from strukit import calcsheet
    from strukit.gui import calc
    v = dict(mark="WT1", shape="2D escarpment", exposure="D", exposure_basis="open water upwind", H="266", Lh="320", geometry_source="topographic section",
             x="100", side="downwind of the crest", located="yes", heights="0, 33")
    s, kind, _ = calc.build("wind_kzt", v, {})
    rows = dict(s.kzt["rows"])
    assert kind == "simple" and rows[33.0]["Kzt"] == pytest.approx(1.93, abs=0.01) and rows[0.0]["Kzt"] > rows[33.0]["Kzt"]
    calcsheet.simple_pdf(s, str(tmp_path / "k.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    for extra in (dict(shape="3D axisymmetrical hill", x="0"), dict(shape="2D ridge", side="upwind of the crest"), dict(located="no"), dict(H="10", Lh="200")):
        t, _, _ = calc.build("wind_kzt", dict(v, **extra), {})
        calcsheet.simple_pdf(t, str(tmp_path / "k2.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    flat, _, _ = calc.build("wind_kzt", dict(v, located="no"), {})
    assert not flat.kzt["applies"] and all(r["Kzt"] == 1.0 for _, r in flat.kzt["rows"])
    assert calc.results("wind_kzt", dict(v, Lh=""), {})["state"] == "incomplete"
    assert calc.results("wind_kzt", dict(v, heights=""), {})["state"] == "incomplete"


def test_kzt_api_for_the_wind_screens():
    from strukit.gui import server
    v = dict(mark="WT1", shape="2D escarpment", exposure="D", exposure_basis="open water", H="266", Lh="320", geometry_source="topo", x="100",
             side="downwind of the crest", located="yes", heights="0, 33")
    got = server.api("/api/kzt", dict(values=v, project={}))
    assert got["applies"] and got["rows"] == [dict(z=0.0, Kzt=pytest.approx(2.11, abs=0.005)), dict(z=33.0, Kzt=pytest.approx(1.926, abs=0.002))]
    assert not server.api("/api/kzt", dict(values=dict(v, located="no"), project={}))["applies"]
    assert "not complete" in server.api("/api/kzt", dict(values=dict(v, H=""), project={}))["error"]


def test_monoslope_free_roof_against_the_published_carport_example():
    """Wind Design Manual (SEAOC/ICC) Design Example 16, Tables 16-1 and 16-2: monoslope carport at 10 degrees, clear flow, V = 100 mph, Kh = 0.875
    (Exposure C at 17.5 ft), qh with Kd = 19.1 psf, G = 0.85: CN -0.70 / -1.10 and -1.57 / 0.0 for gamma = 0, 1.03 / 1.53 and 1.67 / 0.40 for gamma = 180;
    pressures -11.4 / -17.8, -25.4 / 0.0, 16.8 / 24.9, 27.0 / 6.5 psf.  Figure 27.3-4 and 27.3-7 values as read from the ASCE/SEI 7-22 page images."""
    cn = wind.free_mono_cn(10.0)
    assert cn[0]["A"] == pytest.approx((-0.70, -1.10), abs=0.005) and cn[0]["B"] == pytest.approx((-1.567, 0.0), abs=0.005)
    assert cn[180]["A"] == pytest.approx((1.033, 1.533), abs=0.005) and cn[180]["B"] == pytest.approx((1.667, 0.40), abs=0.005)
    r = wind.free_roof_monoslope(100, "C", 17.5, 10.0, 26.0)
    assert r["Kh"] == pytest.approx(0.875) and r["qh"] * 0.85 == pytest.approx(19.1, rel=0.005)
    got = {(x["gamma"], x["case"]): (x["pW"], x["pL"]) for x in r["across"]}
    for key, book in (((0, "A"), (-11.4, -17.8)), ((0, "B"), (-25.4, 0.0)), ((180, "A"), (16.8, 24.9)), ((180, "B"), (27.0, 6.5))):
        assert got[key] == pytest.approx(book, rel=0.01, abs=0.05)
    assert wind.free_mono_cn(5.0)[0]["A"] == (1.2, 0.3) and wind.free_mono_cn(45.0, True)[180]["B"] == (2.1, 0.4)
    assert wind.free_mono_cn(7.5)[0]["A"] == pytest.approx((-0.6, -1.0)) and wind.free_mono_cn(26.25)[0]["A"] == pytest.approx((-1.65, -1.7))
    assert [(z["A"], z["B"]) for z in r["parallel"]] == [(-0.8, 0.8), (-0.6, 0.5), (-0.3, 0.3)]
    assert [(z["A"], z["B"]) for z in wind.free_roof_monoslope(100, "C", 17.5, 10.0, 26.0, obstructed=True)["parallel"]] == [(-1.2, 0.5), (-0.9, 0.5), (-0.6, 0.3)]
    assert wind.free_roof_monoslope(100, "C", 10.0, 3.0, 60.0)["across"] is None                # h/L 0.17 under 5 degrees: Figure 27.3-7 only (note 4)
    with pytest.raises(wind.WindError):
        wind.free_roof_monoslope(100, "C", 10.0, 10.0, 60.0)
    with pytest.raises(wind.WindError):
        wind.free_mono_cn(50.0)


def test_open_building_screen(tmp_path):
    from strukit import calcsheet
    from strukit.gui import calc
    v = dict(mark="WO1", V="100", V_source="Hazard Tool", exposure="C", exposure_basis="open terrain", h="17.5", roof="monoslope", theta="10", L="26", flow="clear", flow_basis="vehicles only",
             Kzt="1.0", Kzt_source="flat site", elevation="", elevation_source="")
    s, kind, _ = calc.build("wind_free_roof", v, {})
    got = {(x["gamma"], x["case"]): (x["pW"], x["pL"]) for x in s.free_roof["across"]}
    assert kind == "simple" and got[(180, "A")] == pytest.approx((16.8, 24.9), rel=0.01)                 # Wind Design Manual Table 16-2
    calcsheet.simple_pdf(s, str(tmp_path / "o.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    ob, _, _ = calc.build("wind_free_roof", dict(v, flow="obstructed", theta="30"), {})
    assert ob.free_roof["across"][0]["CNW"] == -1.5 and ob.free_roof["parallel"][0]["A"] == -1.2
    low, _, _ = calc.build("wind_free_roof", dict(v, h="10", theta="3", L="60"), {})
    assert low.free_roof["across"] is None
    calcsheet.simple_pdf(low, str(tmp_path / "l.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    assert calc.results("wind_free_roof", dict(v, h="10", L="60"), {})["state"] == "stopped"
    assert calc.results("wind_free_roof", dict(v, flow_basis=""), {})["state"] == "incomplete"


def test_pitched_free_roof(tmp_path):
    """ASCE/SEI 7-22 Figure 27.3-5 as read from the page image (pdf p. 349); note 3: straight-line interpolation between 7.5 and 45 degrees, the
    Figure 27.3-4 values under 7.5 degrees.  By hand at 18.75 degrees, clear flow, Case A: CNW = 1.1, CNL = (-0.4 + 0.1)/2 = -0.15."""
    from strukit import calcsheet
    from strukit.gui import calc
    assert wind.FREE_PITCHED[7.5] == {"A": ((1.1, -0.3), (-1.6, -1.0)), "B": ((0.2, -1.2), (-0.9, -1.7))}
    assert wind.FREE_PITCHED[45.0] == {"A": ((1.1, 0.9), (-0.5, -0.5)), "B": ((-0.3, -0.5), (-0.3, -0.7))}
    cn = wind.free_pitched_cn(18.75)
    assert cn["A"] == pytest.approx((1.1, -0.15)) and cn["B"] == pytest.approx((0.0, -0.95))
    assert wind.free_pitched_cn(30.0, True) == {"A": (-0.7, -0.7), "B": (-0.2, -1.1)} and wind.free_pitched_cn(4.0) == {"A": (1.2, 0.3), "B": (-1.1, -0.1)}
    r = wind.free_roof(115, "C", 14.0, 18.75, 30.0, roof="pitched")
    k = r["qh"] * 0.85 * 0.85
    assert [(x["case"], x["pW"], x["pL"]) for x in r["across"]] == [("A", pytest.approx(1.1 * k), pytest.approx(-0.15 * k)), ("B", pytest.approx(0.0, abs=1e-9), pytest.approx(-0.95 * k))]
    v = dict(mark="WO2", V="115", V_source="Hazard Tool", exposure="C", exposure_basis="open terrain", h="14", roof="pitched (gable)", theta="18.75", L="30", flow="clear",
             flow_basis="open below", Kzt="1.0", Kzt_source="flat site", elevation="", elevation_source="")
    s, _, _ = calc.build("wind_free_roof", v, {})
    assert "Pitched" in s.title and len(s.free_roof["across"]) == 2
    calcsheet.simple_pdf(s, str(tmp_path / "p.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    assert calc.results("wind_free_roof", dict(v, roof=""), {})["state"] == "incomplete"


def test_free_roof_total_forces_by_hand(tmp_path):
    """Monoslope, 10 degrees, L = 20 ft, B = 30 ft: each half 300 ft2 in plan.  For net pressures pW, pL (psf): vertical (pW + pL)(300) lb;
    horizontal (pW + pL)(300) tan 10, against the wind for gamma = 0 (the top surface faces downwind), with it for gamma = 180.  Minimum
    16 psf x Af, Af = 30 x 20 tan 10 = 105.8 ft2 (Sect. 27.1.5 as printed).  Pitched, L = 30, B = 40: horizontal (pW - pL)(600) tan theta."""
    import math
    from strukit import calcsheet
    from strukit.gui import calc
    r = wind.free_roof(115, "C", 12.0, 10.0, 20.0)
    t = wind.free_roof_totals(r, 10.0, 20.0, 30.0)
    a = r["across"][0]                                           # gamma 0, case A
    assert t["rows"][0]["V"] == pytest.approx((a["pW"] + a["pL"]) * 300) and t["rows"][0]["H"] == pytest.approx(-(a["pW"] + a["pL"]) * 300 * math.tan(math.radians(10)))
    assert t["rows"][0]["V"] < 0 < t["rows"][0]["H"] and t["rows"][2]["H"] > 0 and t["rows"][2]["V"] > 0
    assert t["Af"] == pytest.approx(105.8, abs=0.05) and t["F_min"] == pytest.approx(16 * 105.8, abs=1)
    rp = wind.free_roof(115, "C", 14.0, 18.75, 30.0, roof="pitched")
    tp = wind.free_roof_totals(rp, 18.75, 30.0, 40.0, "pitched")
    b = rp["across"][0]
    assert tp["rows"][0]["H"] == pytest.approx((b["pW"] - b["pL"]) * 600 * math.tan(math.radians(18.75))) and tp["Af"] == pytest.approx(40 * 15 * math.tan(math.radians(18.75)))
    v = dict(mark="WO1", V="115", V_source="Hazard Tool", exposure="C", exposure_basis="open terrain", h="12", roof="monoslope", theta="10", L="20", width="30", flow="clear",
             flow_basis="open below", Kzt="1.0", Kzt_source="flat site", elevation="", elevation_source="")
    s, _, _ = calc.build("wind_free_roof", v, {})
    assert s.free_roof["totals"]["F_min"] == pytest.approx(t["F_min"]) and not any("minimum design wind force" in x for x in s.not_checked)
    calcsheet.simple_pdf(s, str(tmp_path / "t.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    n, _, _ = calc.build("wind_free_roof", dict(v, width=""), {})
    assert n.free_roof["totals"] is None and any("27.1.5" in x for x in n.not_checked)


def test_troughed_free_roof(tmp_path):
    """ASCE/SEI 7-22 Figure 27.3-6 as read from the page image (pdf p. 350).  By hand at 11.25 degrees, clear flow: Case A CNW -1.1, CNL 0.35;
    Case B CNW -0.05, CNL 1.15.  Total force along the wind (pL - pW)(L/2) B tan theta."""
    import math
    from strukit import calcsheet
    from strukit.gui import calc
    assert wind.FREE_TROUGHED[7.5] == {"A": ((-1.1, 0.3), (-1.6, -0.5)), "B": ((-0.2, 1.2), (-0.9, -0.8))}
    assert wind.FREE_TROUGHED[45.0] == {"A": ((-1.1, -0.9), (-1.2, -0.3)), "B": ((0.3, 0.5), (-0.3, -0.4))}
    cn = wind.free_pitched_cn(11.25, table=wind.FREE_TROUGHED)
    assert cn["A"] == pytest.approx((-1.1, 0.35)) and cn["B"] == pytest.approx((-0.05, 1.15))
    r = wind.free_roof(115, "C", 14.0, 11.25, 30.0, roof="troughed")
    t = wind.free_roof_totals(r, 11.25, 30.0, 40.0, "troughed")
    a = r["across"][0]
    assert t["rows"][0]["H"] == pytest.approx((a["pL"] - a["pW"]) * 600 * math.tan(math.radians(11.25))) and t["rows"][0]["H"] > 0
    v = dict(mark="WO3", V="115", V_source="Hazard Tool", exposure="C", exposure_basis="open terrain", h="14", roof="troughed", theta="11.25", L="30", width="40", flow="obstructed",
             flow_basis="stored material below", Kzt="1.0", Kzt_source="flat site", elevation="", elevation_source="")
    s, _, _ = calc.build("wind_free_roof", v, {})
    assert "Troughed" in s.title and s.free_roof["across"][0]["CNW"] == pytest.approx(-1.4)
    calcsheet.simple_pdf(s, str(tmp_path / "t.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
