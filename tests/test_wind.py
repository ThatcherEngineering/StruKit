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
