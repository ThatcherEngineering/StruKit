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
    v = dict(mark="DI1", panel="Sheathing and Single-Floor, 7/16 in, 8d common", face="2", edges="unblocked", case="Case 1", panel_type="OSB", G="0.42", G_source="SPF, NDS Table 12.3.3A",
             L="40", W="24", load="wind", w="200", w_source="sheet WM1, 0.6 W", chord_A="16.5", chord_E="1400000", defl_limit="0.5", defl_limit_source="project criteria",
             splices=[dict(x="10", slip="0.03")])
    sheet, kind, _ = calc.build("diaphragm", v, proj)
    assert kind == "simple" and [r.check for r in sheet.rows] == ["Unit shear", "Aspect ratio L/W", "Mid-span deflection"]
    assert sheet.rows[0].demand == pytest.approx(166.7, abs=0.05) and sheet.rows[0].capacity == pytest.approx(296.7) and sheet.rows[2].demand == pytest.approx(0.214, abs=0.002)
    calcsheet._simple_pdf(sheet, str(tmp_path / "d.pdf"), "2026-000", "SDPWS-2021", "2026-11-23")
    from strukit.gui import server
    assert server.api("/api/diaphragm_reaction", dict(values=v, project=proj)) == dict(reaction=4000.0, load="wind", W="24")
    assert "error" in server.api("/api/diaphragm_reaction", dict(values=dict(v, w=""), project=proj))
    long = calc.results("diaphragm", dict(v, L="80"), proj)
    assert long["state"] == "done" and long["status"] == "FLAG"                     # L/W = 3.33 over 3
    with pytest.raises(calc.Missing):
        calc.build("diaphragm", dict(v, w_source=""), proj)


def test_blocked_diaphragm_table_and_by_hand(tmp_path):
    """Table 4.2A spot values, patterns across the table, and by hand: 15/32 Structural I, 10d, 3 in. face, nails at 4 in., seismic LRFD,
    G = 0.50: 0.50(1345) = 672.5 plf; 60 ft span, 30 ft deep, 900 plf: v = 900 plf; chord 900(3600)/(240) = 13,500 lb."""
    B = dp.BLOCKED
    assert set(B) == set(dp.ROWS)
    assert B[("Structural I", "6d", "5/16")][2][6] == (520, 15, 12) and B[("Structural I", "10d", "15/32")][3][2] == (2295, 26, 18)
    assert B[("Sheathing and Single-Floor", "8d", "7/16")][2][2.5] == (1415, 12, 9.5) and B[("Sheathing and Single-Floor", "6d", "3/8")][3][4] == (785, 5.5, 5.0)
    assert B[("Sheathing and Single-Floor", "10d", "19/32")][3][2.5] == (2015, 14, 11) and B[("Sheathing and Single-Floor", "8d", "15/32")][3][2] == (1890, 15, 11)
    for k, r in B.items():
        for f in (2, 3):
            v = [r[f][s][0] for s in (6, 4, 2.5, 2)]
            assert v == sorted(v) and 1.32 <= v[1] / v[0] <= 1.35 and 1.95 <= v[2] / v[0] <= 2.03 and 2.2 <= v[3] / v[0] <= 2.3
            assert r[f][6][0] > dp.ROWS[k][f][0]                         # blocked at 6 in. is above unblocked Case 1
        assert all(r[3][s][0] > r[2][s][0] for s in (6, 4, 2.5, 2))
    r = dp.blocked("Structural I, 15/32 in, 10d common", 3, 4, "OSB", 0.50, 60, 30, 900, "seismic", "LRFD")
    assert r["capacity"] == pytest.approx(672.5) and r["v"] == pytest.approx(900) and r["chord"] == pytest.approx(13500) and r["ratio_max"] == 4.0 and r["Ga"] == 12
    with pytest.raises(dp.DiaphragmError):
        dp.blocked("Structural I, 15/32 in, 10d common", 3, 3, "OSB", 0.50, 60, 30, 900, "seismic", "LRFD")
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.0E", source="ASCE/SEI 7-22 Sect. 2.3.6")])
    v = dict(mark="DI2", panel="Structural I, 15/32 in, 10d common", face="3", edges="blocked", spacing="2-1/2", panel_type="OSB", G="0.50", G_source="DF-L",
             L="60", W="30", load="seismic", w="900", w_source="sheet EQ1")
    sheet, _, _ = calc.build("diaphragm", v, proj)
    assert sheet.rows[0].capacity == pytest.approx(0.5 * 2015) and sheet.rows[1].capacity == 4.0 and any("3 in. nominal" in t for t in sheet.assumptions)
    calcsheet._simple_pdf(sheet, str(tmp_path / "b.pdf"), "2026-000", "SDPWS-2021", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("diaphragm", dict(v, spacing=""), proj)
    with pytest.raises(calc.Missing):
        calc.build("diaphragm", dict(v, edges="unblocked"), proj)                 # the layout case is needed


def test_collector_force_by_hand(tmp_path):
    """Line 40 ft long, 8,000 lb: vd = 200 plf. One 10 ft wall at the end: vw = 800 plf; force at the wall end = 200(30) = 6,000 lb.
    Two 8 ft walls at 10 and 30 ft: vw = 500 plf; force 200(10) = 2,000 lb at 10 ft; 2,000 + (200 - 500)(8) = -400 lb at 18 ft;
    -400 + 200(12) = 2,000 lb at 30 ft; -400 lb at 38 ft; 0 at 40 ft. A wall the full length: no collector force."""
    from strukit import diaphragm, calcsheet
    from strukit.gui import calc
    r = diaphragm.collector(40, 8000, [(0, 10)])
    assert r["vd"] == 200 and r["vw"] == 800 and r["Fmax"] == pytest.approx(6000) and r["points"][-1] == (40, 0.0)
    r = diaphragm.collector(40, 8000, [(30, 8), (10, 8)])
    assert [(x, round(F)) for x, F in r["points"]] == [(0.0, 0), (10.0, 2000), (18.0, -400), (30.0, 2000), (38.0, -400), (40, 0)] and r["Fmax"] == 2000
    assert diaphragm.collector(40, 8000, [(0, 40)])["Fmax"] == 0
    for bad in ([], [(35, 10)], [(0, 10), (5, 10)], [(-1, 5)]):
        with pytest.raises(diaphragm.DiaphragmError):
            diaphragm.collector(40, 8000, bad)
    proj = dict(job="2026-000", name="Test", method="ASD")
    v = dict(mark="CL1", line_name="grid A", W="40", R="8000", level="seismic, strength level", R_source="DI1", walls=[dict(start="10", length="8"), dict(start="30", length="8")])
    sheet, kind, _ = calc.build("collector", v, proj)
    assert kind == "simple" and sheet.collector["Fmax"] == 2000 and sheet.blocks[0]["picture"][0] == "collector" and len(sheet.blocks[1]["lines"]) == 7
    calcsheet._simple_pdf(sheet, str(tmp_path / "c.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    assert calc.results("collector", v, proj)["state"] == "done"
    assert calc.results("collector", dict(v, walls=[]), proj)["state"] == "incomplete" and calc.results("collector", dict(v, level=""), proj)["state"] == "incomplete"


def test_diaphragm_reaction_api_gives_the_line_length():
    """The collector screen fills its force and line length from a diaphragm: 200 plf x 40 ft / 2 = 4,000 lb; W = 24 ft."""
    from strukit.gui import server
    proj = dict(job="2026-000", name="Test", method="ASD")
    v = dict(mark="DI1", panel="Sheathing and Single-Floor, 7/16 in, 8d common", face="2", edges="unblocked", case="Case 1", panel_type="OSB", G="0.42",
             G_source="SPF", L="40", W="24", load="wind", w="200", w_source="WM1")
    got = server.api("/api/diaphragm_reaction", dict(values=v, project=proj))
    assert got["reaction"] == pytest.approx(4000) and got["W"] == "24" and got["load"] == "wind"


def test_cantilevered_diaphragm_sdpws_example(tmp_path):
    """SDPWS-2021 Commentary Example C4.2.6.1-2: L' = 32 ft, W' = 136 ft, v = 1.4 x 144 = 201.6 plf, EA = 26,400,000 lb, Ga = 17 kips/in.,
    a chord splice 16 ft from the line with 0.054 in. slip; Eq. 4.2-2: 0.006 + 0.190 + 0.006 = 0.20 in. (Ga 17 is the OSB value of 19/32 in.
    10d, 3 in. face, 6 in. nailing in Table 4.2A; the example's plywood has the same Ga.) Statics: v = w L' / W', T = w L'^2 / (2 W'); limits of
    Sect. 4.2.6.1 for seismic (L'/W' 1.5, 1.0 or 0.67 when torsionally irregular, L' 35 ft; not for L' of 6 ft or less)."""
    from strukit import ws_more, calcsheet
    w = 201.6 * 136 / 32
    r = dp.blocked("Sheathing and Single-Floor, 19/32 in, 10d common", 3, 6, "OSB", 0.5, 32, 136, w, "seismic", "LRFD", 1.6e6, 16.5, [(16, 0.054)],
                   cant=dict(irregular=False, stories=4))
    assert r["Ga"] == 17 and r["v"] == pytest.approx(201.6) and r["chord"] == pytest.approx(w * 32 ** 2 / (2 * 136))
    assert r["defl_bending"] == pytest.approx(0.006, abs=0.0005) and r["defl_shear"] == pytest.approx(0.190, abs=0.0005)
    assert r["defl_splice"] == pytest.approx(0.006, abs=0.0005) and r["defl"] == pytest.approx(0.20, abs=0.005)
    assert r["ratio_max"] == 1.5 and r["length_max"] == 35.0
    irr = dp.blocked("Sheathing and Single-Floor, 19/32 in, 10d common", 3, 6, "OSB", 0.5, 20, 30, 300, "seismic", "ASD", cant=dict(irregular=True, stories=2))
    assert irr["ratio_max"] == 0.67 and irr["ratio"] == pytest.approx(20 / 30)
    one = dp.blocked("Sheathing and Single-Floor, 19/32 in, 10d common", 3, 6, "OSB", 0.5, 20, 30, 300, "seismic", "ASD", cant=dict(irregular=True, stories=1))
    assert one["ratio_max"] == 1.0 and one["rigid_ok"]
    short = dp.unblocked("Sheathing and Single-Floor, 15/32 in, 8d common", 2, 1, "OSB", 0.5, 5, 30, 300, "seismic", "ASD", cant=dict())
    assert short["ratio_max"] == 3.0 and short["length_max"] is None                 # L' of 6 ft or less: Sect. 4.2.6.1 does not apply
    s = ws_more.diaphragm_sheet("D1", "Sheathing and Single-Floor, 19/32 in, 10d common", 3, 1, "OSB", 0.5, "DF-L", 32, 136, w, "ELF", "seismic", "LRFD",
                                1.6e6, 16.5, [(16, 0.054)], blocked=True, spacing=6, cant=dict(irregular=False, stories=4))
    names = [x.check for x in s.rows]
    assert "Aspect ratio L'/W'" in names and "Cantilever length L'" in names
    u = ws_more.diaphragm_sheet("D2", "Sheathing and Single-Floor, 15/32 in, 8d common", 2, 1, "OSB", 0.5, "DF-L", 12, 20, 200, "ELF", "seismic", "ASD", cant=dict())
    assert u.ok and u.diaphragm["v"] == pytest.approx(200 * 12 / 20) and "Aspect ratio L'/W'" in [x.check for x in u.rows]
    calcsheet.simple_pdf(s, str(tmp_path / "cant.pdf"), "Job", "SDPWS-2021", "Nov 26, 2026")


def test_opening_force_transfer_by_hand(tmp_path):
    """One interior opening, force transfer around it (diaphragm.opening): the APA T555 / Diekmann shear wall analysis turned flat. No
    published diaphragm example is on file, so this is checked by hand. Simple span 60 ft, depth 30 ft, 200 plf; opening 8 ft along the
    span x 6 ft across, 12 ft from the support and 10 ft from the chord (d1 = 10, d2 = 14); framing extended 8 ft each side.
      region 4 to 28 ft; V = 200(30 - 4) = 5,200 lb (the larger end); Lr = 24 ft; H = 5,200(24)/30 = 4,160 lb; va = 4,160/16 = 260 plf;
      O = 260(6) = 1,560 lb; F1 = 1,560(10/24) = 650, F2 = 910 lb; strips V/(d1 + d2) = 5,200/24 = 216.7 plf;
      corner zones 216.7 - 650/10 = 151.7 plf (both); F/d = 65 plf; members along the sides |260 - 151.7| x 8 = 866.7 lb
      (also the Vierendeel value V a / (2 (d1 + d2)) = 5,200(8)/48 = 866.7 lb with e1 = e2); chord lines 151.7(16) + 216.7(8) = 4,160 = H."""
    r = dp.opening(60, 30, 200, False, 12, 8, 10, 6, 8, 8)
    assert r["V"] == 5200 and r["Lr"] == 24 and r["H"] == pytest.approx(4160) and r["va"] == pytest.approx(260) and r["O"] == pytest.approx(1560)
    s1, s2 = r["strips"]
    assert (s1["F"], s2["F"]) == pytest.approx((650, 910)) and s1["v"] == pytest.approx(216.67, abs=0.01) and s2["v"] == pytest.approx(s1["v"])
    assert s1["vc"] == pytest.approx(151.67, abs=0.01) and s2["vc"] == pytest.approx(151.67, abs=0.01) and s1["vF"] == pytest.approx(65)
    assert r["N_side"] == pytest.approx(866.67, abs=0.01) and r["F_end"] == pytest.approx(910) and r["v_max"] == pytest.approx(260)
    assert max(abs(c) for c in r["checks"]) < 1e-6
    # unequal extensions: the side member takes |va - vc| x the longer extension; equilibrium still closes
    u = dp.opening(60, 30, 200, False, 12, 8, 10, 6, 6, 10)
    assert u["N_side"] == pytest.approx(abs(u["va"] - u["strips"][0]["vc"]) * 10) and max(abs(c) for c in u["checks"]) < 1e-6
    # cantilever: shear w (L' - x) at the end of the region nearer the line
    cv = dp.opening(20, 30, 150, True, 6, 4, 10, 6, 3, 3)
    assert cv["V"] == pytest.approx(150 * 17)
    for bad in (dict(x0=2), dict(y0=24), dict(e2=50)):                    # framing outside the span; opening at the far chord
        a = dict(x0=12, a=8, y0=10, b=6, e1=8, e2=8); a.update(bad)
        with pytest.raises(dp.DiaphragmError):
            dp.opening(60, 30, 200, False, a["x0"], a["a"], a["y0"], a["b"], a["e1"], a["e2"])
    # on the screen and the printed sheet
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a")])
    v = dict(mark="DI2", panel="Structural I, 15/32 in, 10d common", face="2", edges="blocked", spacing="4", panel_type="OSB", G="0.50", G_source="DF-L, NDS Table 12.3.3A",
             L="60", W="30", load="wind", w="200", w_source="sheet WM1, 0.6 W", op_a="8", op_b="6", op_x0="12", op_y0="10", op_e1="8", op_e2="8")
    sheet, kind, _ = calc.build("diaphragm", v, proj)
    row = [x for x in sheet.rows if x.check == "Unit shear around the opening"][0]
    assert row.demand == pytest.approx(260) and row.capacity == pytest.approx(1190 / 2.0)
    assert not any("openings in the diaphragm" in t for t in sheet.not_checked)
    calcsheet._simple_pdf(sheet, str(tmp_path / "op.pdf"), "2026-000", "SDPWS-2021", "2026-11-26")
    with pytest.raises(calc.Missing):
        calc.build("diaphragm", dict(v, op_e1=""), proj)
    # deflection: the shear term over the region at the largest shear around the opening, 0.5 x 24 x (260 - 5,200/30) / (1000 x 15) = 0.0693 in
    d0 = calc.build("diaphragm", dict(v, op_a="", chord_A="16.5", chord_E="1400000"), proj)[0].diaphragm["defl"]
    d1 = calc.build("diaphragm", dict(v, chord_A="16.5", chord_E="1400000"), proj)[0].diaphragm
    assert d1["defl_opening"] == pytest.approx(0.5 * 24 * (260 - 5200 / 30) / 15000) and d1["defl"] == pytest.approx(d0 + d1["defl_opening"])


def test_openings_in_line_cross_checked_with_t555_wall(tmp_path):
    """Two openings side by side across the depth (diaphragm.openings): the APA T555 several-openings analysis turned flat. No published
    diaphragm example is on file; the result is checked against the T555 shear wall routine (shearwall.ftao_multi, itself checked against
    APA's published 20 ft two-window wall) with the inputs mapped: wall length = diaphragm depth W, wall height = region length Lr, piers =
    strips, opening width = b, clear height = a, sheathing below = e2 (so above = e1). Span 60 ft, depth 30 ft, 200 plf; openings 8 ft along
    the span at 12 ft from the support, 4 ft and 6 ft across at 6 ft and 16 ft from the chord (strips 6, 6, 8 ft); framing 8 ft each side.
      V = 5,200 lb; Lr = 24 ft; H = 4,160 lb; va = 4,160/16 = 260 plf; sum of strip shears x widths = V."""
    from strukit import shearwall as sw
    ops = [dict(x0=12, a=8, y0=6, b=4, e1=8, e2=8), dict(x0=12, a=8, y0=16, b=6, e1=8, e2=8)]
    (r,) = dp.openings(60, 30, 200, False, ops)
    assert r["multi"] and r["piers"] == [6, 6, 8] and r["V"] == 5200 and r["H"] == pytest.approx(4160) and r["va"] == pytest.approx(260)
    assert sum(s["v"] * s["d"] for s in r["strips"]) == pytest.approx(5200) and max(abs(c) for c in r["checks"]) < 1e-6
    wall = sw.ftao_multi("Structural I, 15/32 in, 10d common", 4, "OSB", 0.5, 24, [6, 6, 8],
                         [dict(w=4, ho=8, sill=8), dict(w=6, ho=8, sill=8)], 5200, "wind", "ASD", holddown_inside=False)
    for s, p in zip(r["strips"], wall["piers"]):
        assert s["v"] == pytest.approx(p["v"]) and s["vc"] == pytest.approx(p["vc"]) and s["vF"] == pytest.approx(p["vF"])
    # a single opening through openings() is opening(); separate regions along the span; overlapping regions refused
    one = dp.openings(60, 30, 200, False, ops[:1])[0]
    assert one["va"] == pytest.approx(dp.opening(60, 30, 200, False, 12, 8, 6, 4, 8, 8)["va"]) and not one.get("multi")
    two = dp.openings(60, 30, 200, False, [ops[0], dict(x0=40, a=4, y0=10, b=4, e1=4, e2=4)])
    assert len(two) == 2
    with pytest.raises(dp.DiaphragmError):
        dp.openings(60, 30, 200, False, [ops[0], dict(x0=24, a=4, y0=10, b=4, e1=4, e2=4)])
    with pytest.raises(dp.DiaphragmError):
        dp.openings(60, 30, 200, False, [ops[0], dict(ops[1], y0=8)])
    # screen and sheet
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a")])
    v = dict(mark="DI3", panel="Structural I, 15/32 in, 10d common", face="2", edges="blocked", spacing="4", panel_type="OSB", G="0.50",
             G_source="DF-L, NDS Table 12.3.3A", L="60", W="30", load="wind", w="200", w_source="sheet WM1, 0.6 W",
             op_a="8", op_b="4", op_x0="12", op_y0="6", op_e1="8", op_e2="8",
             more_openings=[dict(a="8", b="6", x0="12", y0="16", e1="8", e2="8"), dict(a="4", b="4", x0="40", y0="10", e1="4", e2="4")])
    sheet, _, _ = calc.build("diaphragm", v, proj)
    rows = [x for x in sheet.rows if x.check.startswith("Unit shear around the opening")]
    assert len(rows) == 2 and rows[0].demand == pytest.approx(max(260, max(s["v"] for s in r["strips"])))
    calcsheet._simple_pdf(sheet, str(tmp_path / "ops.pdf"), "2026-000", "SDPWS-2021", "2026-11-26")
