"""Wood structural panel shear walls, SDPWS-2021.

References:
  - Table 4.3A values re-read from the standard (spot checks below).
  - AWC "Shearwall Basics Using SDPWS" slides: the 2b/h reduction of a narrow segment
    (450 plf x 2(2.25)/8 x 2.25 ft = 570 lb) and the hold-down force with no dead load
    (350 plf x 8 ft = 2,800 lb). The slides use 2008-edition capacities, so only these two
    relations are compared.
  - Hand calculations written out below.
"""
import pytest

from strukit import shearwall as sw

P = "Sheathing, 15/32 in, 8d common"


def test_table_values():
    T = sw.TABLE_4_3A
    assert T[("Sheathing", "15/32", "8d")][0] == (730, 13, 10) and T[("Sheathing", "15/32", "8d")][1] == (1065, 19, 13)
    assert T[("Sheathing", "7/16", "8d")][2] == (1260, 28, 17) and T[("Structural I", "15/32", "10d")][3] == (2435, 51, 28)
    assert T[("Sheathing", "3/8", "6d")][0] == (560, 11, 8.5) and T[("Structural I", "3/8", "8d")][1] == (1010, 24, 17)
    assert len(T) == 12 and len(sw.PANELS) == 12


def test_design_factors():
    one = lambda load, m: sw.line(P, 6, "OSB", 0.5, 8, [8], 1000, load, m).capacity
    assert one("wind", "ASD") == pytest.approx(730 * 8 / 2.0) and one("seismic", "ASD") == pytest.approx(730 * 8 / 2.8)
    assert one("wind", "LRFD") == pytest.approx(730 * 8 * 0.8) and one("seismic", "LRFD") == pytest.approx(730 * 8 * 0.5)


def test_specific_gravity_factor():
    # Hem-Fir framing, G = 0.43: 1 - (0.5 - 0.43) = 0.93; Douglas Fir-Larch 0.50: 1.0; never over 1
    assert sw.line(P, 6, "OSB", 0.43, 8, [8], 1000, "wind", "ASD").sg_factor == pytest.approx(0.93)
    assert sw.line(P, 6, "OSB", 0.55, 8, [8], 1000, "wind", "ASD").sg_factor == 1.0


def test_narrow_segment_reduction_matches_awc_slide():
    # 8 ft wall, 2.25 ft segment: h/b = 3.56 is over 3.5, so use a 9 ft wall check by hand instead for the limit,
    # and the slide's relation on a 2.5 ft segment: capacity x 2b/h
    w = sw.line(P, 6, "OSB", 0.5, 8, [2.5], 500, "wind", "ASD")
    s = w.segments[0]
    assert s.reduction == pytest.approx(2 * 2.5 / 8) and s.Vcap == pytest.approx(365 * (2 * 2.5 / 8) * 2.5)
    with pytest.raises(sw.ShearWallError, match="3.5"):
        sw.line(P, 6, "OSB", 0.5, 8, [2.25], 500, "wind", "ASD")
    # the slide's arithmetic: 450 plf x 2(2.25)/8 x 2.25 = 570 lb
    assert 450 * 2 * 2.25 / 8 * 2.25 == pytest.approx(570, abs=1)


def test_distribution_in_proportion_to_capacity_by_hand():
    # 9 ft wall, segments 8 ft and 3 ft, wind ASD, 15/32 sheathing 8d at 4 in: vn = 1,065, allowable 532.5 plf
    # 8 ft: h/b = 1.125, capacity 4,260 lb; 3 ft: h/b = 3.0, x 2(3)/9 = 0.667, capacity 532.5 x 0.667 x 3 = 1,065 lb
    # line capacity 5,325 lb; V = 4,000: 8 ft takes 3,200 lb (400 plf), 3 ft takes 800 lb (266.7 plf)
    w = sw.line(P, 4, "OSB", 0.5, 9, [8, 3], 4000, "wind", "ASD", arm_offset_in=6)
    a, b = w.segments
    assert a.Vcap == pytest.approx(4260) and b.Vcap == pytest.approx(1065) and w.capacity == pytest.approx(5325)
    assert a.V == pytest.approx(3200) and a.v == pytest.approx(400) and b.V == pytest.approx(800)
    # T = V h / b_eff: 3,200 x 9 / 7.5 = 3,840 lb; 800 x 9 / 2.5 = 2,880 lb
    assert a.T == pytest.approx(3840) and b.T == pytest.approx(2880)


def test_hold_down_force_matches_awc_slide():
    # 350 plf on an 8 ft wall with no dead load and the full length as the arm: 350 x 8 = 2,800 lb
    w = sw.line(P, 6, "OSB", 0.5, 8, [10], 3500, "wind", "ASD")
    assert w.segments[0].v == pytest.approx(350) and w.segments[0].T == pytest.approx(2800)


def test_deflection_by_hand():
    # v = 400 plf, h = 9 ft, b = 8 ft, chord (2) 2x6 A = 16.5 in2, E = 1,600,000, Ga = 19, slip 0.125 in
    # 8 x 400 x 729 / (1.6e6 x 16.5 x 8) = 0.01105; 400 x 9 / 19,000 = 0.18947; 9 x 0.125 / 8 = 0.14063; total 0.3411
    w = sw.line(P, 4, "OSB", 0.5, 9, [8], 3200, "wind", "ASD", chord_E=1.6e6, chord_A=16.5, anchor_slip_in=0.125)
    assert w.segments[0].defl == pytest.approx(0.3411, abs=0.0005)


def test_ten_penny_nail_note():
    p = "Sheathing, 15/32 in, 10d common"
    with pytest.raises(sw.ShearWallError, match="note 10"):
        sw.line(p, 6, "OSB", 0.5, 8, [8], 1000, "wind", "ASD")
    assert sw.line(p, 6, "OSB", 0.5, 8, [8], 1000, "wind", "ASD", holddown_inside=True).capacity == pytest.approx(870 * 0.92 * 8 / 2)
    assert sw.line(p, 6, "OSB", 0.5, 8, [8], 1000, "wind", "ASD", holddown_inside=False).capacity == pytest.approx(870 * 8 / 2)


def test_two_sided_wall_is_twice_one_side():
    one = sw.line(P, 4, "OSB", 0.5, 9, [8], 4000, "wind", "ASD", chord_E=1.6e6, chord_A=16.5, anchor_slip_in=0.1)
    two = sw.line(P, 4, "OSB", 0.5, 9, [8], 4000, "wind", "ASD", chord_E=1.6e6, chord_A=16.5, anchor_slip_in=0.1, sides=2)
    assert two.capacity == pytest.approx(2 * one.capacity) and two.Ga == 2 * one.Ga
    # deflection: only the sheathing term halves: 8vh^3/(EAb) + vh/(1000 x 38) + h da / b
    v = 500.0
    assert two.segments[0].defl == pytest.approx(8 * v * 729 / (1.6e6 * 16.5 * 8) + v * 9 / 38000 + 9 * 0.1 / 8, abs=1e-4)


def test_unblocked_wall_by_hand():
    # 15/32 sheathing 8d at 6 in: vn(b) = 730; studs at 16, intermediate nails at 12: C(ub) = 0.6; wind ASD: 730 x 0.6 / 2 = 219 plf
    w = sw.line(P, 6, "OSB", 0.5, 8, [8, 4], 2000, "wind", "ASD", blocked=False, stud_spacing=16, field_nails=12,
                chord_E=1.6e6, chord_A=16.5, anchor_slip_in=0.1)
    assert w.cub == 0.6 and w.capacity == pytest.approx(219 * 12)
    # equal unit shear 166.7 plf; deflection of the 8 ft segment uses v / C(ub) = 277.8 plf and Ga = 13
    vd = 2000 / 12 / 0.6
    assert w.segments[0].defl == pytest.approx(8 * vd * 512 / (1.6e6 * 16.5 * 8) + vd * 8 / 13000 + 8 * 0.1 / 8, abs=1e-4)
    assert sw.line(P, 6, "OSB", 0.5, 8, [8], 500, "wind", "ASD", blocked=False, stud_spacing=24, field_nails=6).cub == 0.5
    for kw, msg in ((dict(spacing=4), "6 in"), (dict(h=17), "16 ft"), (dict(lengths=[3.5]), "2 limit")):
        a = dict(spacing=6, h=8, lengths=[8]); a.update(kw)
        with pytest.raises(sw.ShearWallError, match=msg):
            sw.line(P, a["spacing"], "OSB", 0.5, a["h"], a["lengths"], 500, "wind", "ASD", blocked=False, stud_spacing=16, field_nails=12)


def test_dead_load_reduces_uplift():
    # 8 ft segment, 9 ft high, V = 3,200 lb, b_eff = 7.5 ft: V h / b_eff = 3,840 lb
    # dead 250 plf x 0.6 x 8 / 2 = 600 lb -> T = 3,240 lb; compression stays 3,840 lb
    w = sw.line(P, 4, "OSB", 0.5, 9, [8], 3200, "wind", "ASD", arm_offset_in=6, dead_plf=250, dead_factor=0.6)
    s = w.segments[0]
    assert s.C == pytest.approx(3840) and s.T_dead == pytest.approx(600) and s.T == pytest.approx(3240)
    big = sw.line(P, 4, "OSB", 0.5, 9, [8], 400, "wind", "ASD", dead_plf=1000, dead_factor=0.6)
    assert big.segments[0].T == 0.0
    with pytest.raises(sw.ShearWallError, match="factor"):
        sw.line(P, 4, "OSB", 0.5, 9, [8], 400, "wind", "ASD", dead_plf=100)


# ---- SDPWS-2021 Commentary examples (published) -----------------------------------------
def test_commentary_example_c4_3_5_5_1_1_deflection_of_sw1():
    # SW1: 8 ft x 8 ft, vn = 730 plf (15/32 sheathing, 8d at 6 in., OSB, Ga = 13), seismic ASD 260.7 plf,
    # EA = 16,800,000 lb, anchorage slip 0.079 in: deflection = 0.008 + 0.16 + 0.079 = 0.248 in.; T = 2,224.8 lb
    w = sw.line(P, 6, "OSB", 0.5, 8, [8], 260.7 * 8, "seismic", "ASD", arm_offset_in=6, chord_E=1.6e6, chord_A=10.5, anchor_slip_in=0.079)
    s = w.segments[0]
    assert w.capacity == pytest.approx(2085.6, abs=0.3) and w.Ga == 13
    assert s.defl == pytest.approx(0.248, abs=0.001) and s.T == pytest.approx(2224.8, abs=0.5)
    # SW2 of the same example: 2.3 ft long at 110.6 plf, slip 0.048 in: 0.012 + 0.068 + 0.167 = 0.247 in.
    w2 = sw.line(P, 6, "OSB", 0.5, 8, [2.3], 110.6 * 2.3, "seismic", "ASD", chord_E=1.6e6, chord_A=10.5, anchor_slip_in=0.048)
    assert w2.segments[0].defl == pytest.approx(0.247, abs=0.001)


def test_commentary_example_c4_3_5_5_1_2_line_capacity_by_the_exception():
    # 8 ft and 2.3 ft walls, 8 ft high, seismic ASD: 260.7 x 8 + (730 / 2.8 x 2b/h) x 2.3 = 2,085.6 + 341.8 = 2,427 lb
    # (the example rounds 2b/h = 0.575 to 0.57; unrounded the second wall is 344.8 lb)
    w = sw.line(P, 6, "OSB", 0.5, 8, [8, 2.3], 2000, "seismic", "ASD")
    assert w.segments[0].Vcap == pytest.approx(2085.6, abs=0.3) and w.segments[1].Vcap == pytest.approx(341.8, abs=3.5)
    assert w.capacity == pytest.approx(2427, abs=4)


def test_awc_slide_factor_tables():
    for G, f in ((0.55, 1.00), (0.50, 1.00), (0.43, 0.93), (0.42, 0.92), (0.36, 0.86)):
        assert sw.line(P, 6, "OSB", G, 8, [8], 100, "wind", "ASD").sg_factor == pytest.approx(f)
    for b, f in ((4, 1.00), (3.2, 0.80), (2.7, 0.67), (2.3, 0.57)):
        assert sw.line(P, 6, "OSB", 0.5, 8, [b], 100, "wind", "ASD").segments[0].reduction == pytest.approx(f, abs=0.006)


# ---- perforated shear walls -----------------------------------------------------------
def test_co_matches_table_4_3_5_6():
    # Table 4.3.5.6 (percent full-height sheathing, percent openings) -> Co
    table = {(10, 30): 1.00, (10, 40): 0.77, (10, 90): 0.36, (20, 30): 0.91, (20, 50): 0.59, (30, 40): 0.67, (40, 60): 0.45,
             (50, 20): 0.91, (50, 30): 0.71, (50, 50): 0.50, (60, 20): 0.83, (70, 30): 0.63, (80, 10): 0.91, (90, 10): 0.83, (100, 0): 1.00}
    for (fhs, ao), co in table.items():
        # a 100 ft x 10 ft wall with one opening placed to give these percentages (the rest is sheathing above and below)
        assert min(1000 / (3 * ao * 10 + fhs * 10), 1.0) == pytest.approx(co, abs=0.006)


def test_perforated_wall_by_hand():
    # 8 ft high, 24 ft long, openings: 4 ft wide x 4 ft high at 6 ft, and 3 ft wide x 6.67 ft at 16 ft
    # segments: 6 ft, 6 ft (10 to 16), 5 ft (19 to 24): all 2:1 or less -> sum b = 17 ft
    # A_wall = 192; A_o = 16 + 20 = 36.0; A_fhs = 136; Co = 192 / (108.03 + 136) = 0.7868
    # 15/32 sheathing 8d at 4 in: vn = 1,065; wind ASD: 1,065 x 0.7868 x 17 / 2 = 7,122 lb
    w = sw.perforated(P, 4, "OSB", 0.5, 8, 24, [(6, 4, 4), (16, 3, 6.67)], 5000, "wind", "ASD", chord_E=1.6e6, chord_A=16.5, anchor_slip_in=0.1)
    Co = 192 / (3 * (16 + 3 * 6.67) + 136)
    assert [round(s[1], 3) for s in w.segments] == [6, 6, 5] and w.sum_b == pytest.approx(17)
    assert w.Co == pytest.approx(Co) and w.capacity == pytest.approx(1065 * Co * 17 / 2)
    assert w.v_max == pytest.approx(5000 / (Co * 17)) and w.T == pytest.approx(5000 * 8 / (Co * 17))
    v = w.v_max
    assert w.defl == pytest.approx(8 * v * 512 / (1.6e6 * 16.5 * 17) + v * 8 / 19000 + 8 * 0.1 / 17, abs=1e-4)


def test_perforated_wall_rules():
    # a narrow pier between openings: 2 ft at 8 ft high is 4:1, not counted, but still full-height sheathing in A_fhs
    w = sw.perforated(P, 4, "OSB", 0.5, 8, 20, [(6, 3, 4), (11, 3, 4)], 1000, "wind", "ASD")
    assert w.segments[1][3] == 0.0 and w.sum_b == pytest.approx(12) and w.A_fhs == pytest.approx(14 * 8)
    # a 3 ft end segment at 8 ft (2.67:1) counts as 3 x 2(3)/8 = 2.25 ft
    w = sw.perforated(P, 4, "OSB", 0.5, 8, 16, [(3, 4, 4)], 1000, "wind", "ASD")
    assert w.segments[0][3] == pytest.approx(2.25)
    # the 2,435 plf limit: Structural I 15/32 10d at 2 in on both sides
    w = sw.perforated("Structural I, 15/32 in, 10d common", 2, "OSB", 0.5, 8, 16, [(6, 4, 4)], 1000, "wind", "ASD", holddown_inside=False, sides=2)
    assert w.vn == 2435
    for kw, msg in ((dict(openings=[(0, 4, 4)]), "each end"), (dict(openings=[(12, 4, 4)]), "each end"), (dict(h=21), "20 ft"),
                    (dict(openings=[(6, 4, 4), (8, 4, 4)]), "overlap"), (dict(openings=[(2, 4, 4)]), "3.5")):
        a = dict(h=8, openings=[(6, 4, 4)]); a.update(kw)
        with pytest.raises(sw.ShearWallError, match=msg):
            sw.perforated(P, 4, "OSB", 0.5, a["h"], 16, a["openings"], 1000, "wind", "ASD")


def test_different_sheathing_on_the_two_sides(tmp_path):
    """SDPWS-2021 4.3.5.4.2. Side 1: Sheathing 7/16 in., 8d at 4 in. (vn 980 plf, Ga 22 OSB); side 2: Sheathing 3/8 in., 8d at 6 in. (vn 615 plf,
    Ga 17 OSB). Two times the smaller, 1,230 plf, exceeds the larger: vn(c) = 1,230 plf, Ga(c) = 2(17) = 34 kips/in. 8 ft wall, seismic, ASD:
    1,230(8)/2.8 = 3,514 lb. With side 1 at 2 in. (1,640 plf, Ga 42): the larger governs: vn(c) = 1,640 plf, Ga(c) = 42; 1,640(8)/2.8 = 4,686 lb."""
    from strukit import shearwall as sw, calcsheet
    from strukit.gui import calc
    oth = dict(panel="Sheathing, 3/8 in, 8d common", spacing=6, panel_type="OSB")
    w = sw.line("Sheathing, 7/16 in, 8d common", 4, "OSB", 0.5, 9, [8], 3000, "seismic", "ASD", other=oth)
    assert w.capacity == pytest.approx(1230 * 8 / 2.8) and w.Ga == 34
    w = sw.line("Sheathing, 7/16 in, 8d common", 2, "OSB", 0.5, 9, [8], 3000, "seismic", "ASD", other=oth)
    assert w.capacity == pytest.approx(1640 * 8 / 2.8) and w.Ga == 42
    same = sw.line("Sheathing, 7/16 in, 8d common", 4, "OSB", 0.5, 9, [8], 3000, "seismic", "ASD", sides=2)
    twin = sw.line("Sheathing, 7/16 in, 8d common", 4, "OSB", 0.5, 9, [8], 3000, "seismic", "ASD", other=dict(panel="Sheathing, 7/16 in, 8d common", spacing=4, panel_type="OSB"))
    assert twin.capacity == pytest.approx(same.capacity) and twin.Ga == same.Ga          # identical sides agree with 4.3.5.4.1
    for kw in (dict(lengths=[8, 4]), dict(blocked=False, stud_spacing=16, field_nails=12), dict(sides=2)):
        a = dict(lengths=[8]); a.update(kw)
        with pytest.raises(sw.ShearWallError):
            sw.line("Sheathing, 7/16 in, 8d common", 6 if "blocked" in kw else 4, "OSB", 0.5, 9, a.pop("lengths"), 3000, "seismic", "ASD", other=oth, **a)
    proj = dict(job="2026-000", name="Test", method="ASD")
    v = dict(mark="SW7", panel="Sheathing, 7/16 in, 8d common", spacing="4", panel_type="OSB", sides="both sides (different panels or nailing)",
             panel2="Sheathing, 3/8 in, 8d common", spacing2="6", panel_type2="OSB", blocking="blocked", G="0.50", G_source="DF-L, NDS Table 12.3.3A",
             h="9", lengths="8, 8", load="seismic", V="6000", v_source="seismic sheet SE1")
    sheet, _, _ = calc.build("shear_wall", v, proj)
    assert sheet.rows[0].capacity == pytest.approx(2 * 1230 * 8 / 2.8) and dict(sheet.info)["Side 2"].startswith("wood structural panels, Sheathing, 3/8 in")
    calcsheet._simple_pdf(sheet, str(tmp_path / "w.pdf"), "2026-000", "SDPWS-2021", "2026-11-23")
    assert calc.results("shear_wall", dict(v, panel2=""), proj)["state"] == "incomplete"
