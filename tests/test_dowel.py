"""Dowel-type fastener yield limit equations, 2018 NDS Sect. 12.3, checked against the standard's own
published tables: Table 12N (common wire nails, single shear, p = 10D) and Table 12A (bolts, single
shear, sawn lumber). Table values are rounded (nails to 1 lb, bolts to 10 lb)."""
import pytest
from strukit import dowel


@pytest.mark.parametrize("side_t, D, G, Z", [
    (1.5, 0.148, 0.50, 118), (1.5, 0.162, 0.50, 141), (1.5, 0.131, 0.50, 97), (0.75, 0.148, 0.50, 105), (1.5, 0.148, 0.42, 100),
    (1.5, 0.162, 0.42, 120), (0.75, 0.099, 0.67, 73), (1.5, 0.192, 0.55, 185), (1.0, 0.192, 0.50, 159), (0.75, 0.162, 0.36, 80),
    (1.25, 0.128, 0.46, 86), (1.0, 0.162, 0.43, 113)])
def test_nails_against_table_12n(side_t, D, G, Z):
    assert dowel.nail(D, side_t, G, G)["Z"] == pytest.approx(Z, abs=0.75)


@pytest.mark.parametrize("D, ts, tm, G, table", [
    (0.5, 1.5, 1.5, 0.50, (480, 300, 300, 220)), (0.75, 1.5, 2.5, 0.50, (1020, 590, 500, 380)), (1.0, 1.5, 1.5, 0.67, (1290, 740, 740, 470)),
    (0.625, 1.5, 2.5, 0.55, (930, 560, 490, 390)), (0.5, 1.5, 2.5, 0.46, (580, 340, 330, 270)), (0.875, 1.75, 1.75, 0.50, (990, 550, 550, 340))])
def test_bolts_against_table_12a(D, ts, tm, G, table):
    got = [dowel.bolt(D, ts, tm, G, G, a, b)["Z"] for a, b in ((0, 0), (90, 0), (0, 90), (90, 90))]     # Z parallel, Zs perp, Zm perp, Z perp
    for g, t in zip(got, table):
        assert g == pytest.approx(t, abs=7)


def test_dowel_pieces():
    assert dowel.fe(0.50, 0.148) == 4650 and dowel.fe(0.42, 0.131) == 3350 and dowel.fe(0.50, 0.5) == 5600 and dowel.fe(0.50, 0.5, 90) == 3150
    assert dowel.fe(0.67, 1.0, 90) == 3400 and dowel.fe(0.50, 0.75, 90) == 2600                    # Table 12.3.3 values
    assert dowel.rd(0.148, "IV") == 2.2 and dowel.rd(0.192, "Im") == pytest.approx(2.42) and dowel.rd(0.5, "II") == 3.6 and dowel.rd(0.5, "Im", 90) == 5.0
    assert dowel.nail_fyb(0.131) == 100000 and dowel.nail_fyb(0.148) == 90000 and dowel.nail_fyb(0.192) == 80000 and dowel.nail_fyb(0.244) == 70000
    d = dowel.bolt(0.5, 1.5, 3.5, 0.50, 0.50, double=True)
    assert set(d["modes"]) == {"Im", "Is", "IIIs", "IV"} and d["Z"] > dowel.bolt(0.5, 1.5, 3.5, 0.50, 0.50)["Z"]
    short = dowel.nail(0.148, 1.5, 0.5, 0.5, penetration=1.0)                                   # 6.8 D penetration
    assert short["Z"] < 118 and short["lm"] == pytest.approx(0.852)
    with pytest.raises(dowel.DowelError):
        dowel.nail(0.148, 1.5, 0.5, 0.5, penetration=0.8)
    with pytest.raises(dowel.DowelError):
        dowel.bolt(1.25, 1.5, 1.5, 0.5, 0.5)


def test_nailed_connection_sheet(tmp_path):
    """8 - 16d common (0.162 x 3.5 in.) through a 1-1/2 in. side member into a 3-1/2 in. main member, Douglas Fir-Larch, dry:
    penetration 2.0 in. (12.3 D), Z = 141 lb (Table 12N). Wind 1,500 lb, D + 0.6W: 900 lb; CD = 1.6: 8(141)(1.6) = 1,804 lb."""
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a"),
                                                                        dict(expr="D", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 1a")])
    v = dict(mark="NC1", nail="16d common", n="8", side_t="1.5", G_side="0.50", G_side_source="Douglas Fir-Larch, NDS Table 12.3.3A",
             main_t="3.5", G_main="0.50", G_main_source="Douglas Fir-Larch, NDS Table 12.3.3A", service="dry", loads=[dict(case="W", P="1500")])
    sheet, kind, _ = calc.build("nailed_connection", v, proj)
    c = sheet.connection
    assert kind == "simple" and c["Z"] == pytest.approx(141, abs=0.75) and sheet.rows[0].demand == pytest.approx(900) and sheet.rows[0].capacity == pytest.approx(8 * 141 * 1.6, abs=8)
    calcsheet._simple_pdf(sheet, str(tmp_path / "n.pdf"), "2026-000", "NDS 2018", "2026-11-23")
    wet, _, _ = calc.build("nailed_connection", dict(v, service="wet in service", end_grain="yes", diaphragm="yes", loads=[dict(case="D", P="400")]), proj)
    assert wet.rows[0].capacity == pytest.approx(8 * c["Z"] * 0.9 * 0.7 * 0.67 * 1.1, rel=1e-6) and wet.rows[0].combo in ("D", "D + 0.6W")
    from strukit.ws_steel_beam import WorksheetError
    assert calc.FORMS["nailed_connection"]["fields"][0]["options"][:-1] == list(dowel.NAILS) and len(dowel.NAILS) == 30
    assert dowel.NAILS["16d common"] == (3.5, 0.162) and dowel.NAILS["8d box"] == (2.5, 0.113) and dowel.NAILS["16d sinker"] == (3.25, 0.148) and dowel.NAILS["60d sinker"] == (5.75, 0.244)
    other, _, _ = calc.build("nailed_connection", dict(v, nail="other (type the size)", nail_name="0.148 x 3 in. gun nail", D="0.148", length="3"), proj)
    assert other.connection["p"] == 1.5 and other.connection["Z"] == pytest.approx(118, abs=0.75)
    with pytest.raises(calc.Missing):
        calc.build("nailed_connection", dict(v, nail="other (type the size)"), proj)
    with pytest.raises(WorksheetError):
        calc.build("nailed_connection", dict(v, nail="6d common"), proj)              # 2 in. nail: 0.5 in. penetration, under 6 D
    with pytest.raises(calc.Missing):
        calc.build("nailed_connection", dict(v, loads=[]), proj)


@pytest.mark.parametrize("ratio, As, n, Cg", [(0.5, 5, 2, 0.98), (0.5, 5, 8, 0.55), (0.5, 12, 6, 0.81), (0.5, 64, 12, 0.82), (0.5, 28, 5, 0.93),
                                              (1.0, 5, 4, 0.91), (1.0, 5, 12, 0.45), (1.0, 20, 9, 0.82), (1.0, 40, 10, 0.87), (1.0, 64, 7, 0.96)])
def test_group_action_against_table_11_3_6a(ratio, As, n, Cg):
    """NDS Table 11.3.6A: D = 1 in., s = 4 in., E = 1,400,000 psi, wood side members."""
    E = 1.4e6
    assert dowel.group_action(1.0, n, 4.0, E * As, E * As / ratio) == pytest.approx(Cg, abs=0.006)


def test_group_action_edges():
    assert dowel.group_action(0.148, 12, 3, 1e7, 1e7) == 1.0 and dowel.group_action(0.75, 1, 3, 1e7, 1e7) == 1.0
    assert dowel.group_action(0.75, 6, 3, 1.4e6 * 12, 1.4e6 * 24, metal=True) < dowel.group_action(0.75, 6, 3, 1.4e6 * 12, 1.4e6 * 24)


def test_bolted_connection_by_hand(tmp_path):
    """Tension splice, Douglas Fir-Larch (G 0.50, E 1.6e6): 2x6 side members each side of a 4x6 main member (double shear), 2 rows of 3
    3/4 in. bolts at 3 in. in a row, rows 2.5 in. apart, end distance 5.25 in., edge 1.5 in., dry.
    Z per bolt by the double shear yield equations (checked against Table 12F in the test below).
    C-delta: end 5.25 / (7 x 0.75) = 1.0; spacing 3 / (4 x 0.75) = 1.0. Edge minimum: l/D = min(3.5, 3.0)/0.75 = 4 -> 1.5 D = 1.125 in.
    Cg with As = 2(8.25) = 16.5 in2, Am = 19.25 in2, n = 3, s = 3 in."""
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.7S", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 3a")])
    v = dict(mark="BC1", D="3/4", shear="double", rows="2", n_row="3", spacing="3", row_spacing="2.5", end="5.25", edge="1.5", sense="tension", wood_type="softwood",
             side_t="1.5", side_w="5.5", G_side="0.50", E_side="1600000", side_source="DF-L No. 2", main_t="3.5", main_w="5.5", G_main="0.50", E_main="1600000",
             main_source="DF-L No. 2", service="dry", loads=[dict(case="D", P="2000"), dict(case="S", P="9000")])
    sheet, kind, _ = calc.build("bolted_connection", v, proj)
    c = sheet.connection
    z = dowel.bolt(0.75, 1.5, 3.5, 0.5, 0.5, double=True)
    Cg = dowel.group_action(0.75, 3, 3.0, 1.6e6 * 16.5, 1.6e6 * 19.25)
    assert c["Z"] == z["Z"] and c["Cdelta"] == 1.0 and c["Cg"] == pytest.approx(Cg) and 0.9 < Cg < 1.0 and c["edge_min"] == pytest.approx(1.125)
    assert sheet.rows[0].demand == pytest.approx(2000 + 6300) and sheet.rows[0].capacity == pytest.approx(6 * z["Z"] * 1.15 * Cg)
    assert [r.check for r in sheet.rows] == ["Load on the bolts", "Edge distance", "Spacing between rows", "Distance between outer rows"]
    calcsheet._simple_pdf(sheet, str(tmp_path / "b.pdf"), "2026-000", "NDS 2018", "2026-11-23")
    short, _, _ = calc.build("bolted_connection", dict(v, end="3.5", spacing="2.5"), proj)
    assert short.connection["Cdelta"] == pytest.approx(min(3.5 / 5.25, 2.5 / 3.0))
    from strukit.ws_steel_beam import WorksheetError
    with pytest.raises(WorksheetError):
        calc.build("bolted_connection", dict(v, end="2"), proj)                    # under 3.5 D
    with pytest.raises(WorksheetError):
        calc.build("bolted_connection", dict(v, spacing="2"), proj)                # under 3 D
    with pytest.raises(calc.Missing):
        calc.build("bolted_connection", dict(v, row_spacing=""), proj)
    with pytest.raises(WorksheetError):
        calc.build("bolted_connection", dict(v, edge="2"), proj)                   # 2 + 2.5 + 2 = 6.5 in. does not fit in 5.5 in.
    one, _, _ = calc.build("bolted_connection", dict(v, rows="1", row_spacing="", service="wet at fabrication, dry in service"), proj)
    assert one.connection["CM"] == 1.0 and len(one.rows) == 2
    two, _, _ = calc.build("bolted_connection", dict(v, service="wet at fabrication, dry in service"), proj)
    assert two.connection["CM"] == 0.4


@pytest.mark.parametrize("D, tm, G, table", [(0.5, 1.5, 0.50, (1050, 730, 470)), (0.75, 2.5, 0.50, (2400, 1170, 980)), (1.0, 1.5, 0.67, (2810, 2040, 1020)),
                                             (0.875, 2.5, 0.55, (3360, 1440, 1200)), (0.625, 2.5, 0.46, (1660, 940, 780))])
def test_double_shear_bolts_against_table_12f(D, tm, G, table):
    """NDS Table 12F: double shear, sawn lumber, 1-1/2 in. side members: Z parallel, Zs perpendicular, Zm perpendicular."""
    got = [dowel.bolt(D, 1.5, tm, G, G, a, b, double=True)["Z"] for a, b in ((0, 0), (90, 0), (0, 90))]
    for g, t in zip(got, table):
        assert g == pytest.approx(t, abs=8)


def test_local_stresses_against_nds_appendix_e_examples():
    """NDS E.7: 2x4 Hem-Fir, one row of 3 - 1/2 in. bolts, hole 0.5625 in., end 3.5 in., spacing 2 in., Ft' 788 psi, Fv' 150 psi:
    ZNT' = 3,470 lb, ZRT' = 1,350 lb. NDS E.6 (rows 1 and 3 of the staggered group, 3 bolts each): 3-1/8 x 12 glulam, 1 in. bolts,
    hole 1.0625 in., spacing 4 in., rows 2.5 in. apart, Ft' 1,250, Fv' 191: ZNT' = 34,424 lb, ZRTi' = 7,163 lb, ZGT' = 18,393 lb."""
    e7 = dowel.local_stresses(788, 150, 1.5, 3.5, 1, 3, 2.0, 3.5, None, 0.5625)
    assert e7["ZNT"] == pytest.approx(3470, abs=3) and e7["ZRT"] == pytest.approx(1350) and e7["governs"] == "row tear-out" and e7["ZGT"] is None
    e6 = dowel.local_stresses(1250, 191, 3.125, 12, 3, 3, 4.0, 7.0, 2.5, 1.0625)
    assert e6["ZNT"] == pytest.approx(34424, abs=2) and e6["ZRTi"] == pytest.approx(7163, abs=1) and e6["ZGT"] == pytest.approx(18393, abs=2)
    assert e6["governs"] == "group tear-out" and e6["s_critical"] == 4.0


def test_bolted_sheet_with_tear_out():
    """The splice of the test above with Ft 575(1.3) = 748 psi and Fv 180 psi (DF-L No. 2, 2x6 and 4x6), CD 1.15, holes 13/16 in.:
    main member 3.5 x 5.5: ZNT' = 860(3.5)(5.5 - 1.625) = 11,664 lb; ZRT' = 2(3)(207)(3.5)(3.0) = 13,041 lb;
    ZGT' = 6,521 + 860(3.5)(2.5 - 0.8125) = 11,600 lb -> group tear-out, 11,600 lb."""
    from strukit.gui import calc
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.7S", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 3a")])
    v = dict(mark="BC2", D="3/4", shear="double", rows="2", n_row="3", spacing="3", row_spacing="2.5", end="5.25", edge="1.5", sense="tension", wood_type="softwood",
             side_t="1.5", side_w="5.5", G_side="0.50", E_side="1600000", side_source="DF-L No. 2", main_t="3.5", main_w="5.5", G_main="0.50", E_main="1600000",
             main_source="DF-L No. 2", service="dry", loads=[dict(case="D", P="2000"), dict(case="S", P="9000")],
             Ft_main="748", Fv_main="180", Ft_side="748", Fv_side="180", local_source="NDS Supplement Table 4A, CF = 1.3")
    sheet, _, _ = calc.build("bolted_connection", v, proj)
    main = [r for r in sheet.rows if r.check.startswith("Main member")][0]
    assert main.check == "Main member: group tear-out" and main.capacity == pytest.approx(11600, abs=25)
    side = [r for r in sheet.rows if r.check.startswith("Side members")][0]
    assert side.capacity == pytest.approx(main.capacity * 3.0 / 3.5, rel=1e-6)
    assert not any("row and group tear-out" in t for t in sheet.not_checked)
    with pytest.raises(calc.Missing):
        calc.build("bolted_connection", dict(v, Fv_side=""), proj)
    plain, _, _ = calc.build("bolted_connection", {k: x for k, x in v.items() if not k.startswith(("Ft_", "Fv_", "local"))}, proj)
    assert any("row and group tear-out" in t for t in plain.not_checked) and len(plain.rows) == 4


def test_toe_nailed_connection_by_hand():
    """3 - 8d common (0.131 x 2.5 in.) toe-nails, stud to plate, Spruce-Pine-Fir (G 0.42), dry: ls = min(1.5, 2.5/3) = 0.833 in.;
    p = 2.5 cos 30 - 2.5/3 = 1.332 in. (10.2 D); lm = 1.332 - 0.131 = 1.201 in.; Z by the yield equations with those lengths;
    Z' = Z (1.6)(0.83) for wind."""
    import math
    from strukit.gui import calc
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a")])
    v = dict(mark="NC3", nail="8d common", n="3", side_t="1.5", G_side="0.42", G_side_source="SPF", main_t="1.5", G_main="0.42", G_main_source="SPF", service="dry",
             toe_nail="yes", loads=[dict(case="W", P="300")])
    sheet, _, _ = calc.build("nailed_connection", v, proj)
    c = sheet.connection
    p = 2.5 * math.cos(math.radians(30)) - 2.5 / 3
    z = dowel.lateral(0.131, 2.5 / 3, p - 0.131, 3350, 3350, 100000)
    assert c["p"] == pytest.approx(1.332, abs=0.001) and c["lm"] == pytest.approx(1.201, abs=0.001) and c["Z"] == pytest.approx(z["Z"])
    assert sheet.rows[0].capacity == pytest.approx(3 * z["Z"] * 1.6 * 0.83) and 60 < z["Z"] < 82          # Table 12N: 82 lb at full side thickness
    assert sheet.blocks[0]["picture"][0] == "toe_nail" and any("Toe-nails driven" in t for t in sheet.assumptions)
    from strukit import calcsheet
    import tempfile, os
    calcsheet._simple_pdf(sheet, os.path.join(tempfile.mkdtemp(), "t.pdf"), "2026-000", "2018 NDS", "2026-11-23")


def test_bolted_connection_perpendicular_to_grain():
    """Beam hung from a post: 2 - 2x10 side members (loaded perpendicular to grain) on a 6x6 post (5.5 in. main member, loaded parallel,
    compression), Douglas Fir-Larch, 2 - 3/4 in. bolts in one row along the load at 3 in., double shear. Z = Zs perpendicular of the
    double shear equations (NDS Table 12F lists 1,170 lb for a 2-1/2 in. main member; here 5.5 in.).
    Row spacing rule by hand: l/D = 3.0/0.75 = 4: (5 x 3.0 + 10 x 0.75)/8 = 2.81 in."""
    from strukit.gui import calc
    from strukit.ws_steel_beam import WorksheetError
    assert dowel.row_spacing_min_perp(0.75, 3.0) == pytest.approx(2.8125) and dowel.row_spacing_min_perp(0.75, 1.5) == pytest.approx(1.875) and dowel.row_spacing_min_perp(0.5, 3.5) == 2.5
    assert dowel.geometry_perp_member(0.75, 1.5) == 0.5 and dowel.geometry_perp_member(0.75, 6) == 1.0
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 2a")])
    v = dict(mark="BC3", D="3/4", shear="double", rows="1", n_row="2", spacing="3", end="6", edge="2.75", sense="compression", wood_type="softwood",
             grain="perpendicular in the side member(s)", p_loaded="4", p_unloaded="2.25", p_end="12",
             side_t="1.5", side_w="9.25", G_side="0.50", E_side="1600000", side_source="DF-L No. 2", main_t="5.5", main_w="5.5", G_main="0.50", E_main="1600000",
             main_source="DF-L No. 1", service="dry", loads=[dict(case="D", P="600"), dict(case="L", P="1400")])
    sheet, _, _ = calc.build("bolted_connection", v, proj)
    c = sheet.connection
    z = dowel.bolt(0.75, 1.5, 5.5, 0.5, 0.5, 90, 0, double=True)
    Cg = dowel.group_action(0.75, 2, 3.0, 1.6e6 * 1.5 * 3.0 * 2, 1.6e6 * 30.25)                 # side area = thickness x group width (3 in.), two members
    assert c["Z"] == z["Z"] and 1100 < z["Z"] < 1250 and c["Cg"] == pytest.approx(Cg) and c["Cdelta"] == 1.0
    assert sheet.rows[0].capacity == pytest.approx(2 * z["Z"] * Cg * 1.0)
    names = [r.check for r in sheet.rows]
    assert names == ["Load on the bolts", "Edge distance, main member", "Loaded edge distance, side members", "Unloaded edge distance, side members",
                     "Distance between outer bolts across the grain, side members"]
    assert sheet.rows[2].demand == 3.0 and sheet.rows[2].capacity == 4 and any("3.4.3.3" in t for t in sheet.not_checked)
    with pytest.raises(calc.Missing):
        calc.build("bolted_connection", dict(v, p_loaded=""), proj)
    with pytest.raises(WorksheetError):
        calc.build("bolted_connection", dict(v, p_loaded="5", p_unloaded="2"), proj)              # 5 + 3 + 2 = 10 in. in a 9.25 in. member


def test_shear_at_connection_by_hand():
    """NDS 3.4.3.3. 2 - 2x10 (b = 3.0 in., d = 9.25 in.), bolts with the nearest 2.25 in. from the unloaded edge: de = 7.0 in.; Fv' = 180 psi.
    12 in. from the end (under 5 d = 46.25 in.): (2/3)(180)(3.0)(7.0)(7.0/9.25)^2 = 1,443 lb; far from the end: (2/3)(180)(3.0)(7.0) = 2,520 lb."""
    v, eq = dowel.shear_at_connection(180, 3.0, 9.25, 7.0, 12)
    assert v == pytest.approx(1443, abs=1) and eq == "Eq. 3.4-6"
    assert dowel.shear_at_connection(180, 3.0, 9.25, 7.0, 60) == (pytest.approx(2520), "Eq. 3.4-7")
    from strukit.gui import calc
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 2a")])
    v = dict(mark="BC4", D="3/4", shear="double", rows="1", n_row="2", spacing="3", end="6", edge="2.75", sense="compression", wood_type="softwood",
             grain="perpendicular in the side member(s)", p_loaded="4", p_unloaded="2.25", p_end="12", p_Fv="180", p_Fv_source="DF-L No. 2, NDS Supplement Table 4A",
             side_t="1.5", side_w="9.25", G_side="0.50", E_side="1600000", side_source="DF-L No. 2", main_t="5.5", main_w="5.5", G_main="0.50", E_main="1600000",
             main_source="DF-L No. 1", service="dry", loads=[dict(case="D", P="600"), dict(case="L", P="1400")])
    sheet, _, _ = calc.build("bolted_connection", v, proj)
    row = [r for r in sheet.rows if r.check.startswith("Shear at the connection")][0]
    assert row.capacity == pytest.approx(1443, abs=1) and row.demand == 2000 and row.status != "OK"            # the beam shear governs: 2,000 lb on 1,443 lb
    assert not any("3.4.3.3" in t for t in sheet.not_checked)
    with pytest.raises(calc.Missing):
        calc.build("bolted_connection", dict(v, p_Fv_source=""), proj)


def test_withdrawal_and_pull_through_against_nds_tables():
    """NDS Table 12.2A (lag screws, lb/in.): G 0.50, 1/2 in. = 378; G 0.42, 3/8 in. = 235; G 0.55, 3/4 in. = 592.
    Table 12.2F (pull-through, lb): G 0.42, DH 0.281, 1-1/2 in. = 75; G 0.50, DH 0.281, 7/16 in. = 67; G 0.42, DH 0.344, 3/4 in. = 99;
    G 0.50, DH 0.500, 1-1/8 in. = 305. Nails, Eq. 12.2-3 by hand: 1380 (0.42^2.5)(0.131) = 1380(0.11432)(0.131) = 20.67 lb/in."""
    assert round(dowel.lag_withdrawal(0.50, 0.5)) == 378 and round(dowel.lag_withdrawal(0.42, 0.375)) == 235 and round(dowel.lag_withdrawal(0.55, 0.75)) == 592
    for DH, G, t, v in ((0.281, 0.42, 1.5, 75), (0.281, 0.50, 7 / 16, 67), (0.344, 0.42, 0.75, 99), (0.5, 0.5, 1.125, 305)):
        assert round(dowel.pull_through(DH, G, t)["WH"]) == v
    assert dowel.nail_withdrawal(0.42, 0.131) == pytest.approx(20.67, abs=0.01) and dowel.NAIL_HEADS["8d common"] == 0.281 and set(dowel.NAIL_HEADS) == set(dowel.NAILS)
    with pytest.raises(dowel.DowelError):
        dowel.nail_withdrawal(0.25, 0.131)


def test_nail_withdrawal_sheet_by_hand(tmp_path):
    """4 - 8d common through 7/16 in. sheathing (G 0.50) into Spruce-Pine-Fir (G 0.42), dry, wind: pt = 2.5 - 0.4375 = 2.0625 in.;
    W pt = 20.67(2.0625) = 42.6 lb; x 1.6 = 68.2 lb per nail. Pull-through WH = 66.6 lb (Table 12.2F: 67); x 1.6 = 106.6 lb.
    Capacity 4(68.2) = 272.8 lb. Toe-nailed 8d, stud to plate: pt = 1.332 in.; 20.67(1.332)(0.67)(1.6) = 29.5 lb per nail; CM does not apply."""
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="0.6D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 7")])
    v = dict(mark="NW1", nail="8d common", n="4", side_t="0.4375", G_side="0.50", G_side_source="NDS Table 12.3.3B", main_t="3.5", G_main="0.42", G_main_source="SPF",
             service="dry", loads=[dict(case="W", P="400"), dict(case="D", P="-50")])
    sheet, kind, _ = calc.build("nail_withdrawal", v, proj)
    assert kind == "simple" and sheet.connection["pt"] == pytest.approx(2.0625) and sheet.rows[0].capacity == pytest.approx(4 * 20.667 * 2.0625 * 1.6, abs=0.1)
    assert sheet.rows[1].capacity == pytest.approx(4 * 66.62 * 1.6, abs=0.1) and sheet.rows[0].demand == pytest.approx(210) and sheet.blocks[0]["picture"][1]["withdrawal"]
    calcsheet._simple_pdf(sheet, str(tmp_path / "w.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    wet, _, _ = calc.build("nail_withdrawal", dict(v, service="wet in service"), proj)
    assert wet.rows[0].capacity == pytest.approx(sheet.rows[0].capacity * 0.25) and wet.rows[1].capacity == pytest.approx(sheet.rows[1].capacity * 0.7)
    toe, _, _ = calc.build("nail_withdrawal", dict(v, side_t="1.5", G_side="0.42", main_t="1.5", toe_nail="yes", service="wet in service"), proj)
    assert len(toe.rows) == 1 and toe.rows[0].capacity == pytest.approx(4 * 20.667 * 1.3317 * 0.67 * 1.6, abs=0.1) and toe.blocks[0]["picture"][0] == "toe_nail"
    calcsheet._simple_pdf(toe, str(tmp_path / "t.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("nail_withdrawal", dict(v, G_main_source=""), proj)


def test_lag_screws_against_nds_table_12j(tmp_path):
    """NDS Table 12J, G = 0.50, penetration 8 D: (side thickness, D): Z parallel, Zs perp, Zm perp, Z perp (table values are rounded to 10 lb).
    Mode IV by hand, 1/2 in. lag (Dr 0.371): 0.371^2 / 3.2 x sqrt(2(5600)(45,000) / (3(2))) = 0.04301(9165) = 394.2 lb.
    Sheet: 3 - 1/2 x 5 in. lags in one row, 2x side on a 4x main: p = 5 - 1.5 - 0.3125 = 3.1875 in.; capacity 3(394.2)(Cg 0.980)(1.15) = 1,333 lb."""
    T = {(1.5, 0.5): (390, 220, 270, 200), (1.5, 0.25): (150, 120, 120, 110), (1.5, 0.75): (770, 440, 510, 380), (3.5, 1.0): (1740, 850, 1060, 740),
         (0.5, 0.375): (150, 100, 110, 90), (2.5, 0.625): (640, 390, 420, 350), (1.5, 0.3125): (200, 140, 140, 130), (0.5, 0.25): (120, 90, 90, 80),
         (1.0, 0.3125): (190, 130, 140, 120)}
    for (ts, D), vals in T.items():
        got = [dowel.lag(D, ts, 0.5, 0.5, 8 * D, a, b)["Z"] for a, b in ((0, 0), (90, 0), (0, 90), (90, 90))]
        for g, v in zip(got, vals):
            assert abs(g - v) <= 6, (ts, D, got, vals)
    assert dowel.lag(0.5, 1.5, 0.5, 0.5, 3.1875)["Z"] == pytest.approx(394.2, abs=0.1)
    assert dowel.lag_thread(0.5, 5) == dict(T=3.0, E=0.3125, S=2.0, Dr=0.371) and dowel.lag_thread(0.25, 1)["T"] == 0.75 and dowel.lag_thread(1.0, 12)["T"] == 6.0
    for bad in ((0.75, 2.0), (0.5, 3.5)):
        with pytest.raises(dowel.DowelError):
            dowel.lag_thread(*bad)
    with pytest.raises(dowel.DowelError):
        dowel.lag(0.5, 1.5, 0.5, 0.5, 1.9)
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + S", source="test combination, not a code combination")])
    v = dict(mark="LC1", D="1/2", L="5", rows="1", n_row="3", spacing="4", end="6", edge="2.75", sense="tension", wood_type="softwood",
             side_t="1.5", side_w="5.5", G_side="0.50", E_side="1600000", side_source="DF-L No. 2", main_t="3.5", main_w="5.5", G_main="0.50", E_main="1600000",
             main_source="DF-L No. 2", service="dry", loads=[dict(case="D", P="300"), dict(case="S", P="700")])
    sheet, kind, _ = calc.build("lag_connection", v, proj)
    c = sheet.connection
    assert kind == "simple" and sheet.title == "Lag Screw Connection" and c["capacity"] == pytest.approx(3 * 394.22 * c["Cg"] * 1.15, abs=0.5) and 0.975 < c["Cg"] < 0.985
    assert sheet.connection_lag["p"] == pytest.approx(3.1875) and [x.check for x in sheet.rows][:2] == ["Load on the lag screws", "Penetration into the main member"]
    assert [b["picture"][0] for b in sheet.blocks] == ["bolted", "lag"] and sheet.blocks[1]["picture"][1]["lateral"]
    assert not any("bolt" in (x.check + x.note).lower() for x in sheet.rows) and not any("bolt" in t.lower() for t in sheet.assumptions)
    calcsheet._simple_pdf(sheet, str(tmp_path / "l.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    with pytest.raises(Exception):
        calc.build("lag_connection", dict(v, L="6"), proj)                 # longer than both members
    w, _, _ = calc.build("lag_connection", dict(v, washer="0.125"), proj)
    assert w.connection_lag["p"] == pytest.approx(3.0625)
    perp, _, _ = calc.build("lag_connection", dict(v, grain="perpendicular in the side member(s)", p_loaded="2.75", p_unloaded="2.75", p_end="12", n_row="1", spacing=""), proj)
    assert perp.connection["Z"] == pytest.approx(dowel.lag(0.5, 1.5, 0.5, 0.5, 3.1875, 90, 0)["Z"])


def test_bolted_connection_one_bolt_blank_spacing():
    """One bolt in a row with the spacing left blank (failed with an internal error in builds before 0.90.0)."""
    from strukit.gui import calc
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + S", source="test combination, not a code combination")])
    v = dict(mark="BC9", D="1/2", shear="single", rows="1", n_row="1", end="6", edge="2.75", sense="tension", wood_type="softwood", side_t="1.5", side_w="5.5",
             G_side="0.50", E_side="1600000", side_source="DF-L", main_t="3.5", main_w="5.5", G_main="0.50", E_main="1600000", main_source="DF-L", service="dry",
             loads=[dict(case="D", P="300")])
    sheet, _, _ = calc.build("bolted_connection", v, proj)
    assert sheet.connection["Cg"] == 1.0 and "spacing in a row" not in dict(sheet.info)["Layout"]


def test_lag_withdrawal_sheet_by_hand(tmp_path):
    """2 - 3/8 x 4 in. lags through a 1/4 in. steel plate into Douglas Fir-Larch (G 0.50), dry, wind: W = 305 lb/in. (Table 12.2A);
    thread T = 2.5 in., tip E = 7/32 in.; length in the main member 3.75 in.; pt = 2.5 - 0.219 = 2.281 in. (Table L2: T - E = 2-9/32);
    W pt = 695.7 lb; capacity 2(695.7)(1.6) = 2,226 lb. A 2 in. screw through 1.5 in.: length in main 0.5 in., pt = 0.5 - 0.219 = 0.281 in."""
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="0.6D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 7")])
    v = dict(mark="LW1", D="3/8", L="4", n="2", side_t="0.25", main_t="5.5", G_main="0.50", G_main_source="DF-L", service="dry", loads=[dict(case="W", P="1500")])
    sheet, kind, _ = calc.build("lag_withdrawal", v, proj)
    c = sheet.connection
    assert kind == "simple" and c["pt"] == pytest.approx(2.28125) and round(c["W"]) == 305 and c["capacity"] == pytest.approx(2226.2, abs=0.2) and len(sheet.rows) == 1
    assert sheet.blocks[0]["picture"][0] == "lag" and sheet.blocks[0]["picture"][1]["pt"] == c["pt"]
    calcsheet._simple_pdf(sheet, str(tmp_path / "l.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    full, _, _ = calc.build("lag_withdrawal", dict(v, service="wet in service", end_grain="yes", edge="1", end="1", spacing="2", steel="1200", steel_source="AISC 360-22 J3, A307"), proj)
    assert full.connection["capacity"] == pytest.approx(2226.2 * 0.7 * 0.75, abs=0.2) and [x.check for x in full.rows] == [
        "Withdrawal of the lag screws", "Tension in the lag screws", "Edge distance", "End distance", "Spacing"]
    assert full.rows[1].capacity == 2400 and full.rows[3].status != "OK" and full.rows[2].status == "OK"
    short, _, _ = calc.build("lag_withdrawal", dict(v, L="2", side_t="1.5"), proj)
    assert short.connection["pt"] == pytest.approx(0.5 - 7 / 32)
    for bad in (dict(L="6", main_t="3.5"), dict(steel="1200"), dict(G_main_source="")):
        with pytest.raises(Exception):
            calc.build("lag_withdrawal", dict(v, **bad), proj)


def test_steel_side_plates_against_nds_tables_12b_and_12k(tmp_path):
    """NDS Table 12B (bolts, 1/4 in. A36 side plate, G 0.50): (tm, D): Z parallel, Z perp = (1.5, 1/2): 580, 310; (3.5, 3/4): 1670, 680;
    (5.5, 1): 2860, 1170; (2.5, 5/8): 1050, 470. Table 12K (lag screws, G 0.50, p = 8 D): 1/4 in. A36: 1/2: 520, 320; 3/4: 1060, 600; 1/4: 210, 150;
    A653 Grade 33: 0.239 in., 1/2: 460, 290; 0.075 in., 1/4: 150, 110; 0.134 in., 3/8: 220, 140."""
    for (tm, D), vals in {(1.5, 0.5): (580, 310), (3.5, 0.75): (1670, 680), (5.5, 1.0): (2860, 1170), (2.5, 0.625): (1050, 470)}.items():
        for th, v in zip((0, 90), vals):
            assert abs(dowel.bolt(D, 0.25, tm, None, 0.5, 0, th, Fes=dowel.STEEL_FE["ASTM A36"])["Z"] - v) <= 6
    for (ts, D, gr), vals in {(0.25, 0.5, "ASTM A36"): (520, 320), (0.25, 0.75, "ASTM A36"): (1060, 600), (0.25, 0.25, "ASTM A36"): (210, 150),
                              (0.239, 0.5, "ASTM A653 Grade 33"): (460, 290), (0.075, 0.25, "ASTM A653 Grade 33"): (150, 110),
                              (0.134, 0.375, "ASTM A653 Grade 33"): (220, 140)}.items():
        for th, v in zip((0, 90), vals):
            assert abs(dowel.lag(D, ts, None, 0.5, 8 * D, 0, th, Fes=dowel.STEEL_FE[gr])["Z"] - v) <= 6
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a")])
    v = dict(mark="BC5", D="3/4", shear="single", rows="1", n_row="3", spacing="3", end="5.25", edge="1.75", sense="tension", wood_type="softwood",
             side_steel="ASTM A36 steel plate", side_t="0.25", side_w="3", main_t="3.5", main_w="3.5", G_main="0.50", E_main="1600000", main_source="DF-L",
             service="dry", loads=[dict(case="W", P="6000")])
    sheet, _, _ = calc.build("bolted_connection", v, proj)
    c = sheet.connection
    assert c["Z"] == pytest.approx(1671.4, abs=0.1) and c["Cg"] == pytest.approx(dowel.group_action(0.75, 3, 3, 29e6 * 0.75, 1.6e6 * 12.25, metal=True))
    assert c["capacity"] == pytest.approx(3 * 1671.38 * c["Cg"] * 1.6, abs=0.5) and dict(sheet.info)["Side Plate"].startswith("0.25 x 3 in. ASTM A36 steel")
    assert "steel side plate" in sheet.not_checked[0] and any("87,000" in t for t in sheet.assumptions)
    calcsheet._simple_pdf(sheet, str(tmp_path / "s.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    tear, _, _ = calc.build("bolted_connection", dict(v, Ft_main="575", Fv_main="180", local_source="NDS Supplement Table 4A"), proj)
    assert sum("Main member:" in x.check for x in tear.rows) == 1 and not any("Side member" in x.check for x in tear.rows)
    lg, _, _ = calc.build("lag_connection", dict(v, D="1/2", L="4", n_row="2", end="4", main_t="5.5"), proj)
    assert lg.connection["Z"] == pytest.approx(517.2, abs=0.1) and lg.connection_lag["p"] == pytest.approx(3.4375)
    with pytest.raises(Exception):
        calc.build("bolted_connection", dict(v, grain="perpendicular in the side member(s)", p_loaded="3", p_unloaded="2", p_end="12"), proj)
    with pytest.raises(calc.Missing):
        calc.build("bolted_connection", dict(v, side_steel="wood"), proj)


def test_lag_combined_lateral_and_withdrawal_by_hand(tmp_path):
    """NDS Eq. 12.4-1. One 1/2 x 5 in. lag, 2x side member on a 4x main, G 0.50, load at 30 degrees to the wood surface, D + S (CD 1.15):
    Z = 394.2 lb; W = 378.4 lb/in.; thread penetration = min(3, 3.5) - 0.3125 = 2.6875 in.; W p = 1,017 lb;
    Z'a = 1.15 (1017)(394.2) / (1017 cos^2 30 + 394.2 sin^2 30) = 1.15 (400,900 / 861.3) = 535.3 lb. At 90 degrees Z'a = W'p; at 0 the sheet is lateral only."""
    import math
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + S", source="test combination, not a code combination")])
    v = dict(mark="LC2", D="1/2", L="5", rows="1", n_row="1", end="6", edge="2.75", sense="tension", wood_type="softwood", alpha="30",
             side_t="1.5", side_w="5.5", G_side="0.50", E_side="1600000", side_source="DF-L No. 2", main_t="3.5", main_w="5.5", G_main="0.50", E_main="1600000",
             main_source="DF-L No. 2", service="dry", loads=[dict(case="D", P="300"), dict(case="S", P="200")])
    sheet, _, _ = calc.build("lag_connection", v, proj)
    assert sheet.connection["capacity"] == pytest.approx(535.3, abs=0.1) and sheet.connection_lag["comb"]["pt"] == pytest.approx(2.6875)
    assert "12.4.1" in sheet.rows[0].source and dict(sheet.info)["Load Angle"].startswith("30 degrees") and not any("combined lateral" in t for t in sheet.not_checked)
    calcsheet._simple_pdf(sheet, str(tmp_path / "c.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    up, _, _ = calc.build("lag_connection", dict(v, alpha="90"), proj)
    assert up.connection["capacity"] == pytest.approx(1.15 * 378.403 * 2.6875, abs=0.1)
    flat, _, _ = calc.build("lag_connection", dict(v, alpha="0"), proj)
    assert flat.connection["capacity"] == pytest.approx(1.15 * 394.22, abs=0.1) and flat.connection_lag["comb"] is None
    with pytest.raises(Exception):
        calc.build("lag_connection", dict(v, alpha="120"), proj)


def test_wood_screws_against_nds_table_12l(tmp_path):
    """NDS Table 12L, G = 0.50, penetration 10 D: (side thickness, screw number): Z = (1/2, #8): 73; (1/2, #10): 90; (1/2, #14): 120;
    (3/4, #10): 107; (1, #6): 72; (1/2, #6): 59; (1/2, #12): 110; (5/8, #9): 91; (3/4, #14): 135.
    Sheet: 4 - #10 x 3 in. screws, 3/4 in. side member on a 3.5 in. main member, D + S: p = 2.25 in. (over 10 D); capacity 4(106.6)(1.15) = 490 lb."""
    T = {(0.5, "#8"): 73, (0.5, "#10"): 90, (0.5, "#14"): 120, (0.75, "#10"): 107, (1.0, "#6"): 72, (0.5, "#6"): 59, (0.5, "#12"): 110, (0.625, "#9"): 91, (0.75, "#14"): 135}
    for (ts, num), v in T.items():
        assert abs(dowel.wood_screw(num, ts, 0.5, 0.5)["Z"] - v) <= 0.6, (ts, num)
    with pytest.raises(dowel.DowelError):
        dowel.wood_screw("#10", 0.75, 0.5, 0.5, penetration=1.0)
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + S", source="test combination, not a code combination")])
    v = dict(mark="WS1", screw="#10", length="3", n="4", side_t="0.75", G_side="0.50", G_side_source="DF-L", main_t="3.5", G_main="0.50", G_main_source="DF-L",
             service="dry", loads=[dict(case="D", P="100"), dict(case="S", P="250")])
    sheet, kind, _ = calc.build("screw_connection", v, proj)
    z = dowel.wood_screw("#10", 0.75, 0.5, 0.5, penetration=2.25)["Z"]
    assert kind == "simple" and sheet.title == "Wood Screw Connection" and sheet.connection["p"] == pytest.approx(2.25) and sheet.rows[0].capacity == pytest.approx(4 * z * 1.15)
    assert 106 < z < 108 and [x.check for x in sheet.rows] == ["Lateral load on the wood screws", "Wood screw penetration"]
    txt = " ".join(sheet.assumptions + sheet.not_checked + [k + v_ for k, v_ in sheet.info]).lower()
    assert "nail" not in txt
    calcsheet._simple_pdf(sheet, str(tmp_path / "s.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    with pytest.raises(Exception):
        calc.build("screw_connection", dict(v, length="1.5"), proj)            # penetration 0.75 in. under 6 D = 1.14 in.


def test_wood_screw_withdrawal_sheet(tmp_path):
    """NDS Table 12.2B (lb/in.): G 0.50, #10 = 135; G 0.42, #8 = 82; G 0.55, #14 = 208; G 0.67, #6 = 176 (the equation gives 208.6 and 176.6).
    Sheet: 4 - #10 x 3 in. screws through a 3/4 in. side member (G 0.50) into G 0.50, dry, wind: T = 2 in.; length in the main member 2.25 in.;
    pt = 2 in.; W pt = 135.375(2) = 270.75 lb; capacity 4(270.75)(1.6) = 1,732.8 lb. Pull-through: DH 0.363 in., tns 0.75 in. not over 2.5 DH:
    690 pi (0.363)(0.25)(0.75) = 147.5 lb; 4(147.5)(1.6) = 944.2 lb, which governs."""
    for G, D, v in ((0.50, 0.190, 135), (0.42, 0.164, 82), (0.55, 0.242, 208), (0.67, 0.138, 176)):
        assert abs(dowel.wood_screw_withdrawal(G, D) - v) <= 0.7
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="0.6D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 7")])
    v = dict(mark="SW1", screw="#10", length="3", n="4", side_t="0.75", G_side="0.50", G_side_source="DF-L", main_t="3.5", G_main="0.50", G_main_source="DF-L",
             service="dry", loads=[dict(case="W", P="1200")])
    sheet, kind, _ = calc.build("screw_withdrawal", v, proj)
    assert kind == "simple" and sheet.rows[0].capacity == pytest.approx(1732.8) and sheet.rows[1].capacity == pytest.approx(944.25, abs=0.05)
    assert sheet.connection["capacity"] == pytest.approx(944.25, abs=0.05) and sheet.connection["pt"] == 2.0
    calcsheet._simple_pdf(sheet, str(tmp_path / "s.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    st, _, _ = calc.build("screw_withdrawal", dict(v, side_kind="steel", side_t="0.125", G_side="", G_side_source="", length="1.5", service="wet in service",
                                                   steel="400", steel_source="manufacturer"), proj)
    assert [x.check for x in st.rows] == ["Withdrawal of the wood screws", "Tension in the wood screws"] and st.connection["pt"] == pytest.approx(1.0)
    assert st.rows[0].capacity == pytest.approx(4 * 135.375 * 1.0 * 0.7 * 1.6)
    for bad in (dict(G_side=""), dict(length="5"), dict(steel="400")):
        with pytest.raises(Exception):
            calc.build("screw_withdrawal", dict(v, **bad), proj)


def test_steel_side_plate_main_member_perpendicular(tmp_path):
    """Hanger plate: 1/4 in. A36 plate on a 4x10 Douglas Fir-Larch beam (3.5 x 9.25 in.), 2 - 3/4 in. bolts in one row along the load at 3 in.,
    load perpendicular to the beam grain. Z = 680 lb (NDS Table 12B, tm 3-1/2 in., 3/4 in., G 0.50, perpendicular); the equations give 681.5 lb.
    Capacity 2(681.5)(Cg 0.9965)(1.0) = 1,358 lb, D + L. Shear at the connection: de = 9.25 - 2.25 = 7 in.; connection 12 in. from the end
    (under 5 d): Vr' = (2/3)(180)(3.5)(7)(7/9.25)^2 = 1,683.7 lb. No end distance, edge distance, load sense or wood type is needed."""
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 2")])
    v = dict(mark="BC6", D="3/4", shear="single", rows="1", n_row="2", spacing="3", side_steel="ASTM A36 steel plate", side_t="0.25", side_w="3",
             grain="perpendicular in the main member", p_loaded="4", p_unloaded="2.25", p_end="12", p_Fv="180", p_Fv_source="NDS Supplement Table 4A",
             main_t="3.5", main_w="9.25", G_main="0.50", E_main="1600000", main_source="DF-L", service="dry", loads=[dict(case="D", P="300"), dict(case="L", P="700")])
    sheet, _, _ = calc.build("bolted_connection", v, proj)
    c = sheet.connection
    assert c["Z"] == pytest.approx(681.5, abs=0.1) and c["Cdelta"] == 1.0 and c["capacity"] == pytest.approx(2 * 681.45 * c["Cg"], abs=0.5) and 0.99 < c["Cg"] < 1.0
    names = [x.check for x in sheet.rows]
    assert names == ["Load on the bolts", "Loaded edge distance, main member", "Unloaded edge distance, main member",
                     "Distance between outer bolts across the grain, main member", "Shear at the connection, main member"]
    assert sheet.rows[-1].capacity == pytest.approx(1683.7, abs=0.2) and [b["title"] for b in sheet.blocks] == ["Layout, Member Loaded Perpendicular to Grain"]
    assert dict(sheet.info)["Layout"] == "spacing in a row 3 in." and "parallel" not in dict(sheet.info)["Conditions"]
    calcsheet._simple_pdf(sheet, str(tmp_path / "h.pdf"), "2026-000", "2018 NDS", "2026-11-23")
    lg, _, _ = calc.build("lag_connection", dict(v, D="1/2", L="3"), proj)
    assert lg.connection["Z"] == pytest.approx(dowel.lag(0.5, 0.25, None, 0.5, 3 - 0.25 - 0.3125, 0, 90, Fes=87000.0)["Z"])
    with pytest.raises(Exception):
        calc.build("bolted_connection", dict(v, spacing="2"), proj)              # under 3 D
    with pytest.raises(calc.Missing):
        calc.build("bolted_connection", dict(v, side_steel="wood", G_side="0.5", E_side="1600000", side_source="DF-L"), proj)   # wood side: end distance needed
