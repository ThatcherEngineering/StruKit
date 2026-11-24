"""Round HSS members, AISC 360-22 Sect. E3, F8, G5.

Reference: AISC Design Guide 34, Example 10.1.7, guard top rail HSS1.900x0.145, ASTM A500 Grade C (Fy 46 ksi), 4 ft long:
D/t 14.1 nonslender (limit 69.3), Lc/r = 76.7, Fcr = 31.0 ksi, Pn = 23.2 kips; shear Fcr = 27.6 ksi, Vn = 10.3 kips, Vn/1.67 = 6.17 kips;
flexure (Manual Table 3-14) phi Mn = 1.45 kip-ft, Mn/1.67 = 0.966 kip-ft.  Limits as printed in AISC 360-22 Table B4.1a Case 9 and B4.1b Case 20."""
import pytest

from strukit import hss, shapes


def test_guard_rail_of_design_guide_34():
    p = shapes.hss("HSS1.900x0.145")
    c = hss.compression(p, 46.0, 48.0)
    assert c["lam_r"] == pytest.approx(69.3, abs=0.05) and c["Lc_r"] == pytest.approx(76.7, abs=0.05) and c["limit"] == pytest.approx(118, abs=0.5)
    assert c["Fcr"] == pytest.approx(31.0, abs=0.05) and c["Pn"] == pytest.approx(23.2, abs=0.05) and c["eq"] == "E3-2"
    v = hss.shear(p, 46.0, Lv=24.0)
    assert v["Fcr"] == pytest.approx(27.6) and v["yield_governs"] and v["Vn"] == pytest.approx(10.3, abs=0.05)
    assert hss.available(v["Vn"], "shear", "ASD") == pytest.approx(6.17, abs=0.03)
    f = hss.flexure(p, 46.0)
    assert f["cls"] == "compact" and hss.available(f["Mn"], "flexure", "LRFD") / 12 == pytest.approx(1.45, abs=0.005)
    assert hss.available(f["Mn"], "flexure", "ASD") / 12 == pytest.approx(0.966, abs=0.001)


def test_round_hss_limit_states_by_hand():
    """Hand checks: a D/t 60 pipe at Fy 35: lambda_p = 0.07(29000)/35 = 58.0, so noncompact: Mn = (0.021(29000)/60 + 35) S = 45.15 S.
    Long column, Lc/r = 200 > 4.71 (29000/46)^0.5 = 118.3: Fcr = 0.877 pi^2 (29000)/200^2 = 6.275 ksi."""
    fake = dict(type="PIPE", OD=12.0, tdes=0.2, D_t=60.0, Zx=30.0, Sx=22.0, rx=4.0, A=7.4)
    f = hss.flexure(fake, 35.0)
    assert f["cls"] == "noncompact" and f["Mn"] == pytest.approx(45.15 * 22.0)
    assert hss.flexure(dict(fake, D_t=300.0), 35.0)["cls"] == "slender"
    with pytest.raises(hss.HSSError):
        hss.flexure(dict(fake, D_t=400.0), 35.0)
    with pytest.raises(hss.HSSError):
        hss.compression(dict(fake, D_t=100.0), 35.0, 100.0)
    p = shapes.hss("HSS1.900x0.145")
    c = hss.compression(p, 46.0, 200 * p["rx"])
    assert c["eq"] == "E3-3" and c["Fcr"] == pytest.approx(6.275, abs=0.002)
    with pytest.raises(hss.HSSError):
        hss.flexure(shapes.hss("HSS6x4x1/4"), 46.0)
    assert hss.shear(p, 46.0)["Fcr"] == pytest.approx(27.6)


def test_guard_screen_against_design_guide_34(tmp_path):
    """Design Guide 34 Example 10.1.7 (ASD): rail HSS1.900x0.145 at 4 ft: Ma = 0.205 kip-ft and Va = 0.205 kip under the 200 lb load,
    0.105 kip-ft and 0.105 kip under 50 lb/ft; Mn/1.67 = 0.966 kip-ft. LRFD: Mu = 0.327 kip-ft, phi Mn = 1.45 kip-ft.
    Post, by hand: 200 lb x 3.5 ft = 700 lb-ft; 50 lb/ft x 4 ft x 3.5 ft = 700 lb-ft. Loads as printed in ASCE/SEI 7-22 Sect. 4.5.1."""
    from strukit import calcsheet, ws_more
    from strukit.gui import calc
    assert (ws_more.GUARD_P, ws_more.GUARD_W, ws_more.GUARD_INFILL) == (200.0, 50.0, 50.0)
    v = dict(mark="GD1", rail="HSS1.900x0.145", rail_Fy="46", rail_Fy_source="ASTM A500 Grade C", post="HSS1.900x0.145", post_Fy="46", post_Fy_source="ASTM A500 Grade C",
             spacing="4", height="3.5", uniform="applies")
    s, kind, _ = calc.build("guard", v, dict(method="ASD"))
    r = {x.check: x for x in s.rows}
    assert kind == "simple" and r["Top rail bending"].demand == pytest.approx(205.4, abs=0.1) and r["Top rail bending"].capacity == pytest.approx(966, abs=1)
    assert r["Top rail shear"].demand == pytest.approx(205.4, abs=0.1) and r["Post bending"].demand == pytest.approx(700.0)
    uni = [c for c in s.guard["cases"] if c[0] == "50 lb/ft"][0]
    assert uni[1] == pytest.approx(105.4, abs=0.1) and uni[2] == pytest.approx(105.4, abs=0.1)
    calcsheet.simple_pdf(s, str(tmp_path / "g.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")
    l, _, _ = calc.build("guard", v, dict(method="LRFD"))
    rl = {x.check: x for x in l.rows}
    assert rl["Top rail bending"].demand == pytest.approx(327, abs=1) and rl["Top rail bending"].capacity == pytest.approx(1450, abs=5)
    e, _, _ = calc.build("guard", dict(v, uniform="exception", uniform_basis="one- and two-family dwelling", spacing="6"), dict(method="ASD"))
    assert len(e.guard["cases"]) == 1 and {x.check: x for x in e.rows}["Post bending"].demand == pytest.approx(700.0)
    assert calc.results("guard", dict(v, uniform="exception"), dict(method="ASD"))["state"] == "incomplete"
    assert calc.results("guard", v, {})["state"] == "incomplete"
    bad = calc.results("guard", dict(v, post="HSS6x4x1/4"), dict(method="ASD"))
    assert bad["state"] != "ok" if "state" in bad else True


def test_rectangular_hss_against_the_aisc_design_examples():
    """AISC Design Examples v16.0, Fy = 50 ksi: E.9 HSS12x10x3/8, Lc = 0.8(20 ft): Pn = 618 kips.  E.10 HSS12x8x3/16, Lc = 24 ft,
    all walls slender: Pn = 168 kips.  F.6 HSS3-1/2x3-1/2x1/8: 0.90 Mn = 7.20 kip-ft.  F.7 HSS10x6x3/16, noncompact flange:
    0.90 Mn = 59.7 kip-ft.  F.8B HSS8x8x3/16, slender flange: be = 6.33 in., Se = 12.1 in3, Mn = 50.4 kip-ft.  G.4 HSS6x4x3/8: Vn = 104 kips."""
    c = hss.rect_compression(shapes.hss("HSS12x10x3/8"), 50.0, 0.8 * 240)
    assert not c["slender_walls"] and c["Pn"] == pytest.approx(618, abs=1.5)
    s = hss.rect_compression(shapes.hss("HSS12x8x3/16"), 50.0, 288.0)
    assert s["slender_walls"] and s["Pn"] == pytest.approx(168, abs=1.0) and s["walls"][1]["effective"] == pytest.approx(s["walls"][1]["width"])
    assert s["walls"][0]["Fel"] == pytest.approx(24.8, abs=0.1)
    f6 = hss.rect_flexure(shapes.hss("HSS3-1/2x3-1/2x1/8"), 50.0)
    # b/t = 27.2 against 1.12 (E/Fy)^0.5 = 26.97 at 50 ksi: just noncompact, which is what brings 7.24 down to the Manual's 7.20
    assert f6["flange"] == "noncompact" and 0.9 * f6["Mn"] / 12 == pytest.approx(7.20, abs=0.005)
    f7 = hss.rect_flexure(shapes.hss("HSS10x6x3/16"), 50.0)
    assert f7["flange"] == "noncompact" and f7["eq"] == "F7-2" and 0.9 * f7["Mn"] / 12 == pytest.approx(59.7, abs=0.15)
    f8 = hss.rect_flexure(shapes.hss("HSS8x8x3/16"), 50.0)
    assert f8["flange"] == "slender" and f8["be"] == pytest.approx(6.33, abs=0.01) and f8["Se"] == pytest.approx(12.1, abs=0.05)
    assert f8["Mn"] / 12 == pytest.approx(50.4, abs=0.2)
    v = hss.rect_shear(shapes.hss("HSS6x4x3/8"), 50.0)
    assert v["Cv2"] == 1.0 and v["Vn"] == pytest.approx(104, abs=0.6)


def test_pipe_and_round_hss_against_the_aisc_design_examples():
    """E.11 Pipe 10 Std, Fy 35 ksi, Lc = 30 ft: Pn = 246 kips.  F.9 Pipe 8 x-Strong: 0.90 Mn = 81.4 kip-ft.
    G.5 HSS16.000x0.375, Fy 50 ksi, 32 ft span: Vn = 258 kips."""
    assert hss.compression(shapes.hss("Pipe10STD"), 35.0, 360.0)["Pn"] == pytest.approx(246, abs=1.0)
    assert 0.9 * hss.flexure(shapes.hss("Pipe8XS"), 35.0)["Mn"] / 12 == pytest.approx(81.4, abs=0.15)
    assert hss.shear(shapes.hss("HSS16.000x0.375"), 50.0, Lv=192.0)["Vn"] == pytest.approx(258, abs=1.0)


def test_rectangular_hss_lateral_torsional_buckling_by_hand():
    """HSS10x6x3/16 about x, by hand from Eq. F7-10 and F7-11 with the section's own properties; a very long unbraced length
    brings Eq. F7-8 or F7-9 below the local buckling value; bending about y and square sections take no such reduction."""
    p = shapes.hss("HSS10x6x3/16")
    import math
    k = math.sqrt(p["J"] * p["A"])
    f = hss.rect_flexure(p, 50.0, Lb=12.0)
    assert f["Lp"] == pytest.approx(0.13 * 29000 * p["ry"] * k / (50 * p["Zx"])) and f["Lr"] == pytest.approx(2 * 29000 * p["ry"] * k / (35 * p["Sx"]))
    assert f["governs"] == "flange local buckling"
    long = hss.rect_flexure(p, 50.0, Lb=f["Lr"] * 1.5)
    assert long["governs"] == "lateral-torsional buckling" and long["eq"] == "F7-9" and long["Mn"] == pytest.approx(2 * 29000 * k / (1.5 * f["Lr"] / p["ry"]))
    assert "Lp" not in hss.rect_flexure(p, 50.0, axis="y", Lb=5000.0) and "Lp" not in hss.rect_flexure(shapes.hss("HSS8x8x3/16"), 50.0, Lb=5000.0)


def test_hss_column_screen(tmp_path):
    """AISC Design Example E.9 through the screen: HSS12x10x3/8, 20 ft, K = 0.8, Pu = 510 kips, 0.90 Pn = 556 kips; E.10: HSS12x8x3/16,
    24 ft, Pn / 1.67 = 101 kips.  Beam-column by hand: HSS6x6x1/4 (A 5.24, I 28.6, Z 11.2, r 2.34), Fy 50, 12 ft, LRFD, Pu = 1.2(20 + 0.228) + 1.6(45)
    = 96.27 kips, Mu = 1.2(2.5) + 1.6(5.6) = 11.96 kip-ft: 0.90 Pn = 178.8 kips; 0.90 Mn = 0.9(50)(11.2)/12 = 42.0 kip-ft; Pe1 = pi^2 (29000)(28.6)/144^2
    = 394.8 kips; B1 = 1/(1 - 96.27/394.8) = 1.323; H1-1a = 0.539 + (8/9)(15.82/42.0) = 0.873."""
    from strukit import calcsheet
    from strukit.gui import calc
    lrfd = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 Sect. 2.3.1, combination 2")])
    asd = dict(method="ASD", combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 2")])
    v = dict(mark="HC1", shape="HSS12x10x3/8", Fy="50", Fy_source="ASTM A500 Grade C", height="20", Kx="0.8", Ky="0.8", k_source="fixed base, pinned top", self_weight="no",
             loads=[dict(case="D", P="85"), dict(case="L", P="255")], moments=[])
    s, kind, _ = calc.build("hss_column", v, lrfd)
    assert kind == "simple" and len(s.rows) == 1 and s.rows[0].demand == pytest.approx(510) and s.rows[0].capacity == pytest.approx(556, abs=1)
    e10, _, _ = calc.build("hss_column", dict(v, shape="HSS12x8x3/16", height="24", Kx="1", Ky="1", loads=[dict(case="D", P="50")]), asd)
    assert e10.rows[0].capacity == pytest.approx(101, abs=0.7)
    calcsheet.simple_pdf(e10, str(tmp_path / "e10.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")
    bc = dict(v, shape="HSS6x6x1/4", height="12", Kx="1", Ky="1", self_weight="yes", loads=[dict(case="D", P="20"), dict(case="L", P="45")],
              moments=[dict(case="D", Mx="2.5"), dict(case="L", Mx="5.6")])
    b, _, _ = calc.build("hss_column", bc, lrfd)
    r = {x.check: x for x in b.rows}
    assert r["Axial compression"].demand == pytest.approx(96.27, abs=0.01) and r["Axial compression"].capacity == pytest.approx(178.8, abs=0.2)
    o = b.hss["res"][0]
    assert o["Pe1x"] == pytest.approx(394.8, abs=0.5) and o["B1x"] == pytest.approx(1.323, abs=0.001) and r["Compression and bending"].demand == pytest.approx(0.873, abs=0.002)
    calcsheet.simple_pdf(b, str(tmp_path / "b.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")
    pipe, _, _ = calc.build("hss_column", dict(bc, shape="Pipe 6 STD", Fy="35", moments=[dict(case="D", Mx="2.5", My="1"), dict(case="L", Mx="5.6")]), lrfd)
    assert {x.check: x for x in pipe.rows}["Compression and bending"].demand > 1.0
    calcsheet.simple_pdf(pipe, str(tmp_path / "p.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")
    assert calc.results("hss_column", dict(bc, shape="Pipe 4 STD", Fy="35"), lrfd)["state"] == "stopped"          # Pu reaches Pe1
    assert calc.results("hss_column", dict(bc, loads=[dict(case="D", P="-5")], self_weight="no", moments=[]), lrfd)["state"] == "stopped"
    assert calc.results("hss_column", dict(bc, Fy_source=""), lrfd)["state"] == "incomplete"
    assert calc.results("hss_column", dict(bc, moments=[dict(case="W", Mx="3")]), lrfd)["state"] == "incomplete"


def test_steel_beam_screen_takes_hss_and_pipe(tmp_path):
    """AISC Design Example F.7A through the Steel Beam screen: HSS10x6x3/16, 21 ft, wu = 1.2(0.15) + 1.6(0.4) = 0.82 kip/ft, Mu = 45.2 kip-ft,
    0.90 Mn = 59.7 kip-ft.  F.9A: Pipe 8 x-Strong, 16 ft, 0.90 Mn = 81.4 kip-ft, Mn / 1.67 = 54.1 kip-ft."""
    from strukit import calcsheet
    from strukit.gui import calc
    lrfd = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 Sect. 2.3.1, combination 2")])
    asd = dict(method="ASD", combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 2")])
    v = dict(mark="HB1", shape="HSS10x6x3/16", Fy="50", span="21", bracing="continuous", brace_pts="", self_weight="no",
             loads=[dict(case="D", kind="uniform", mag="0.15", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="0.4", x1="", x2="", label="")],
             defl=[dict(label="live", expr="L", ratio="240", source="typed in")])
    s, kind, kw = calc.build("steel_beam", v, lrfd)
    r = {x.check: x for x in s.rows}
    assert kind == "steel_beam" and r["flexure"].demand == pytest.approx(45.2, abs=0.05) and r["flexure"].capacity == pytest.approx(59.7, abs=0.15)
    assert r["shear"].source == "AISC 360-22 Sect. G4"
    calcsheet.steel_beam_pdf(s, str(tmp_path / "b.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    p, _, kw = calc.build("steel_beam", dict(v, shape="Pipe 8 XS", Fy="35", span="16"), asd)
    rp = {x.check: x for x in p.rows}
    assert rp["flexure"].capacity == pytest.approx(54.1, abs=0.1) and rp["shear"].source == "AISC 360-22 Sect. G5"
    calcsheet.steel_beam_pdf(p, str(tmp_path / "p.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    w, _, _ = calc.build("steel_beam", dict(v, shape="W18X50"), lrfd)                    # I-shapes unchanged
    assert {x.check: x for x in w.rows}["shear"].source == "AISC 360-22 Sect. G2.1"
    assert calc.results("steel_beam", dict(v, shape="HSS99x9"), lrfd)["state"] == "stopped"
    assert calc.results("steel_column", dict(mark="C1", shape="HSS6x6x1/4", Fy="50", height="12", ends="held sideways (braced)", Kx="1", Ky="1", k_source="x",
                                             self_weight="no", loads=[dict(case="D", P="5")], lateral=[], leaning=[], drift=[]), lrfd)["state"] == "stopped"


def test_guard_of_square_hss_by_hand():
    """HSS2x2x1/8 rail and HSS2x2x3/16 posts, Fy 50 ksi, 5 ft spacing, 3.5 ft high, ASD.  Rail: Mn = Fy Z (compact), Mc = Mn / 1.67 about each
    axis; for a load in any direction Mc = Mcx / 2^0.5 for a square section.  Post: 50 lb/ft x 5 ft x 3.5 ft = 875 lb-ft governs over 200 x 3.5 = 700."""
    from strukit.gui import calc
    v = dict(mark="GD2", rail="HSS2x2x1/8", rail_Fy="50", rail_Fy_source="A500 C", post="HSS2x2x3/16", post_Fy="50", post_Fy_source="A500 C", spacing="5", height="3.5", uniform="applies")
    s, _, _ = calc.build("guard", v, dict(method="ASD"))
    r = {x.check: x for x in s.rows}
    zr, zp = shapes.hss("HSS2x2x1/8")["Zx"], shapes.hss("HSS2x2x3/16")["Zx"]
    assert r["Top rail bending"].capacity == pytest.approx(50 * zr / 1.67 / 2 ** 0.5 * 1000 / 12, rel=1e-6)
    assert r["Post bending"].capacity == pytest.approx(50 * zp / 1.67 / 2 ** 0.5 * 1000 / 12, rel=1e-6) and r["Post bending"].demand == pytest.approx(875.0)
    assert r["Post bending"].source == "AISC 360-22 Sect. F7, H1" and dict(s.info)["Post base"].startswith("M = 875 lb-ft, V = 250 lb")
    mixed, _, _ = calc.build("guard", dict(v, rail="HSS1.900x0.145", rail_Fy="46"), dict(method="LRFD"))
    assert {x.check: x for x in mixed.rows}["Top rail bending"].source == "AISC 360-22 Sect. F8"
