"""Built-up three-plate I-shapes (builtup.py) against AISC Design Examples v16.0: F.14 plate girder (Sect. F4), E.2 built-up column with a
slender web (E7), E.3 slender flanges (Table B4.1a Case 2), E.12 singly symmetric member (flexural-torsional buckling, Eq. E4-3). The
examples round ho and other intermediate values; tolerances are set to that rounding (1 percent or less)."""
import pytest

from strukit import builtup, shapes, steel_beam, steel_column
from strukit.gui import calc
from strukit.ws_steel_beam import WorksheetError


def test_f14_plate_girder():
    p = shapes.get("BU 14x2 / 62x1/2 / 14x2")
    assert p["Ix"] == pytest.approx(67300, rel=0.001) and p["Sx"] == pytest.approx(2040, rel=0.001) and p["Zx"] == pytest.approx(2270, rel=0.002)
    assert p["J"] == pytest.approx(77.3, rel=0.002) and p["ho"] == 64.0 and p["Iy"] == pytest.approx(915, rel=0.001)
    r = steel_beam.check(p, 50, 150, 1.25, "LRFD")                  # Lb = 150 in. (quarter points), Cb 1.25
    assert r.Mn / 12 == pytest.approx(8760, rel=0.002)               # Rpc Myc = 1.03 x 8,500 kip-ft (F4-1); LTB 10,300 > 8,760
    assert r.M_avail / 12 == pytest.approx(7880, rel=0.002)
    assert r.Vn == pytest.approx(489, rel=0.001) and r.V_avail == pytest.approx(440, rel=0.001)
    lines = {l.label: l.value for l in r.lines}
    assert lines["rt"] == pytest.approx(3.71, abs=0.005) and lines["Lp"] == pytest.approx(98.3, rel=0.002) and lines["Lr"] == pytest.approx(369, rel=0.002)
    assert lines["Rpc"] == pytest.approx(1.03, abs=0.005)
    asd = steel_beam.check(p, 50, 150, 1.25, "ASD")
    assert asd.M_avail / 12 == pytest.approx(5250, rel=0.002) and asd.V_avail == pytest.approx(293, rel=0.002)


def test_e2_slender_web_and_e3_slender_flanges():
    p = shapes.get("BU 8x1 / 15x1/4 / 8x1")
    c = steel_column.check(p, 50, 180, 180, method="LRFD")
    assert p["A"] == pytest.approx(19.8, abs=0.06) and p["Iy"] == pytest.approx(85.4, rel=0.001) and p["Cw"] == pytest.approx(5470, rel=0.002)
    assert c.Fn == pytest.approx(28.9, abs=0.05)
    assert c.Pn == pytest.approx(555, rel=0.005) and c.P_avail == pytest.approx(500, rel=0.005)     # Ae 19.2 (web he 12.6 in.)
    q = shapes.get("BU 10-1/2x3/8 / 7-1/4x1/4 / 10-1/2x3/8")
    c = steel_column.check(q, 50, 180, 180, method="LRFD")
    assert q["A"] == pytest.approx(9.69, abs=0.005) and q["J"] == pytest.approx(0.407, abs=0.001) and q["Cw"] == pytest.approx(1050, rel=0.003)
    assert c.Fn == pytest.approx(36.4, abs=0.05) and c.Pn == pytest.approx(353, rel=0.003) and c.P_avail == pytest.approx(318, rel=0.004)
    lam = next(l for l in c.lines if l.label == "flanges b/t")
    assert "13.3" in lam.note or "13.2" in lam.note                  # Table B4.1a Case 2, kc 0.743: slender, but fully effective at Fn


def test_e12_singly_symmetric_column():
    p = shapes.get("BU 8x3/4 / 10-1/2x3/8 / 5x3/4")
    assert not p["symmetric"] and p["A"] == pytest.approx(13.7, abs=0.02) and p["yb"] == pytest.approx(6.91, abs=0.02)
    assert p["Ix"] == pytest.approx(334, rel=0.003) and p["Iy"] == pytest.approx(39.9, rel=0.002) and p["J"] == pytest.approx(2.01, abs=0.005)
    assert p["Cw"] == pytest.approx(802, rel=0.01)                   # the example rounds ho to 11.3 in. (11.25 here)
    c = steel_column.check(p, 50, 168, 168, method="LRFD")
    assert "flexural-torsional" in c.governs and c.Fn == pytest.approx(22.7, rel=0.006)
    assert c.Pn == pytest.approx(311, rel=0.008) and c.P_avail == pytest.approx(280, rel=0.008)


def test_singly_symmetric_beam_uses_the_flange_in_compression():
    p = shapes.get("BU 10x1 / 30x3/8 / 6x3/4")
    top = steel_beam.check(p, 50, 180, 1.0, "LRFD", compression="top")
    bot = steel_beam.check(p, 50, 180, 1.0, "LRFD", compression="bottom")
    both = steel_beam.check(p, 50, 180, 1.0, "LRFD")
    assert bot.M_avail < top.M_avail and both.M_avail == pytest.approx(bot.M_avail)
    assert "(top flange in compression)" in top.governs and "(bottom flange in compression)" in bot.governs
    # F4-9: Rpc = Mp / Myc with Mp = Fy Zx not over 1.6 Fy Sxc (the large top flange makes Zx < Sxc, so Rpc < 1)
    rpc = next(l.value for l in top.lines if l.label == "Rpc")
    assert rpc == pytest.approx(min(p["Zx"], 1.6 * p["Sx_top"]) / p["Sx_top"])


def test_limits_and_designations():
    with pytest.raises(shapes.ShapeError):
        shapes.get("BU 14x2 62x1/2 14x2")
    with pytest.raises(steel_beam.SteelInputError):                  # h/tw = 300 over 0.40 E/Fy = 232 (no stiffeners)
        steel_beam.check(shapes.get("BU 14x2 / 75x1/4 / 14x2"), 50, 100, 1.0, "LRFD")
    assert builtup.parse("BU 14 x 2 / 62 x 1/2 / 14 x 2") == (14, 2, 62, 0.5, 14, 2)


def test_screens_and_frame_take_built_up_sections():
    proj = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")], name="t", number="t", date="2026-11-25",
                model=dict(levels=[dict(name="Base", elev="0"), dict(name="Roof", elev="20")], grids_x=[], grids_y=[]))
    bm = dict(kind="steel_beam", values=dict(mark="BM", shape="BU 8x1/2 / 17x5/16 / 8x1/2", Fy="50", span="30", more_spans="", oh_left="", oh_right="", bracing="continuous",
              brace_pts="", self_weight="yes", loads=[dict(case="D", kind="uniform", mag="0.4", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="1.2", x1="", x2="", label="")],
              defl=[], at_level="Roof", at_x1="0", at_y1="0", at_x2="30", at_y2="0", at_fix_i="moment", at_fix_j="moment"))
    col = lambda mark, x: dict(kind="steel_column", values=dict(mark=mark, shape="BU 12x3/4 / 11x1/2 / 12x3/4", Fy="50", at_level="Roof", at_base="Base", at_x1=str(x), at_y1="0",
                                                                at_base_fix="fixed", self_weight="no", loads=[]))
    r = calc.results("steel_beam", bm["values"], proj)
    assert r["state"] == "done" and any("self-weight" in a and "built-up section" in a for a in r["assumptions"])
    out = calc.model_frame_sway(proj, [bm, col("CL", 0), col("CR", 30)])
    assert out["problems"] == [] and out["beams"] and out["columns"]
    p = shapes.get("BU 12x3/4 / 11x1/2 / 12x3/4")
    c = next(c for c in out["columns"] if c["mark"] == "CL")
    assert c["cap"]["Pc"] == pytest.approx(steel_column.check(p, 50, 240, 240, method="LRFD").P_avail)


@pytest.mark.parametrize("method, end, interior, Vu", [("LRFD", 217, 185, 210), ("ASD", 144, 123, 140)])
def test_g8_stiffened_girder_tension_field_action(method, end, interior, Vu, tmp_path):
    """AISC Design Examples v16.0 Examples G.8A and G.8B: girder 36 in. deep, 16 x 1-1/2 flanges, 5/16 in. web, Fy 50, 56 ft span, 1.25 + 3.75
    kip/ft. Unstiffened Vn 196 kips (Cv1 0.577); end panel a = 42 in.: kv 8.09, Cv1 0.710, Vn 241 (217 / 144); second panel a = 90 in. with
    tension field action: kv 5.67, Cv2 0.442, Eq. G2-7, Vn 206 (185 / 123) kips. On the beam sheet the end panel is the shear row and the first
    interior panel is checked at a from each support (here one spacing for every panel, 42 in.)."""
    from strukit import calcsheet
    p = builtup.props("BU 16x1-1/2 / 33x5/16 / 16x1-1/2")
    assert builtup.shear_panel(p, 50)["Vn"] == pytest.approx(196, rel=0.003)
    e = builtup.shear_panel(p, 50, 42.0)
    assert e["kv"] == pytest.approx(8.09, abs=0.01) and e["Cv"] == pytest.approx(0.710, abs=0.005) and e["Vn"] == pytest.approx(241, rel=0.003)
    t = builtup.shear_panel(p, 50, 90.0, True)
    assert t["kv"] == pytest.approx(5.67, abs=0.01) and t["Cv2"] == pytest.approx(0.442, abs=0.004) and t["eq"] == "Eq. G2-7" and t["Vn"] == pytest.approx(206, rel=0.003)
    f = 0.9 if method == "LRFD" else 1 / 1.67
    assert f * e["Vn"] == pytest.approx(end, rel=0.005) and f * t["Vn"] == pytest.approx(interior, rel=0.006)
    proj = dict(method=method, combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")], name="t", number="t", date="2026-11-26")
    v = dict(mark="G1", shape="BU 16x1-1/2 / 33x5/16 / 16x1-1/2", Fy="50", span="56", more_spans="", oh_left="", oh_right="", bracing="continuous", brace_pts="",
             self_weight="no", loads=[dict(case="D", kind="uniform", mag="1.25", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="3.75", x1="", x2="", label="")],
             defl=[], bu_a="42", bu_tfa="yes", bu_ts="0.3125", bu_bs="4", bu_Fyst="50")
    s = calc.build("steel_beam", v, proj)[0]
    r = {x.check: x for x in s.rows}
    assert r["shear"].demand == pytest.approx(Vu, rel=1e-3) and r["shear"].capacity == pytest.approx(end, rel=0.005)
    w = 7.5 if method == "LRFD" else 5.0
    assert r["shear, first interior panel (tension field action)"].demand == pytest.approx(Vu - w * 42 / 12, rel=2e-3)
    assert r["transverse stiffener width-to-thickness, (b / t)st"].demand == pytest.approx(4 / 0.3125)
    ist = r["transverse stiffener moment of inertia, Ist"]
    assert ist.capacity == pytest.approx(0.3125 * (8 + 0.3125) ** 3 / 12)


def test_stiffened_girder_sheet_prints(tmp_path):
    from strukit import calcsheet
    proj = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")], name="t", number="t", date="2026-11-26")
    v = dict(mark="G1", shape="BU 16x1-1/2 / 33x5/16 / 16x1-1/2", Fy="50", span="56", more_spans="", oh_left="", oh_right="", bracing="continuous", brace_pts="",
             self_weight="no", loads=[dict(case="D", kind="uniform", mag="1.25", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="3.75", x1="", x2="", label="")],
             defl=[], bu_a="42", bu_tfa="yes", bu_ts="0.3125", bu_bs="4", bu_Fyst="50")
    s, _, extra = calc.build("steel_beam", v, proj)
    calcsheet.steel_beam_pdf(s, str(tmp_path / "g8.pdf"), "Job", "AISC 360-22", "Nov 26, 2026", combos=extra["combos"])


@pytest.mark.parametrize("method, end, second, unst, Vu", [("LRFD", 217, 185, 176, 210), ("ASD", 144, 123, 117, 140)])
def test_g8_panel_by_panel(method, end, second, unst, Vu):
    """AISC Design Examples v16.0 Examples G.8A and G.8B, panel by panel: end panel 42 in. (no tension field action, 217 / 144 kips against
    210 / 140), second panel 90 in. with tension field action (185 / 123 against 184 / 123 at its start, 42 in. from the support), and the web
    beyond 132 in. unstiffened (176 / 117 kips against 128 / 85.0 at 132 in.)."""
    proj = dict(method=method, combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")], name="t", number="t", date="2026-11-26")
    v = dict(mark="G1", shape="BU 16x1-1/2 / 33x5/16 / 16x1-1/2", Fy="50", span="56", more_spans="", oh_left="", oh_right="", bracing="continuous", brace_pts="",
             self_weight="no", loads=[dict(case="D", kind="uniform", mag="1.25", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="3.75", x1="", x2="", label="")],
             defl=[], bu_a="42, 90", bu_tfa="yes", bu_ts="0.3125", bu_bs="4", bu_Fyst="50")
    s = calc.build("steel_beam", v, proj)[0]
    r = {x.check: x for x in s.rows}
    assert r["shear"].demand == pytest.approx(Vu, rel=1e-3) and r["shear"].capacity == pytest.approx(end, rel=0.005)
    p2 = r["shear, panel 2 (42 to 132 in. from each support)"]
    w = 7.5 if method == "LRFD" else 5.0
    assert p2.demand == pytest.approx(Vu - w * 42 / 12, rel=2e-3) and p2.capacity == pytest.approx(second, rel=0.006) and "G2-7" in p2.source
    u = r["shear, web beyond the last stiffener (132 in. from each support)"]
    assert u.demand == pytest.approx(Vu - w * 132 / 12, rel=2e-3) and u.capacity == pytest.approx(unst, rel=0.006)
    assert "42, 90" in " ".join(s.assumptions)


def test_bearing_at_supports_by_hand():
    """Example G.8A girder (16 x 1-1/2 flanges, 33 x 5/16 web, Fy 50, 56 ft, LRFD Vu = 210 kips) on 6 in. of bearing; checked by hand.
      Eq. J10-3: 50 (0.3125)(2.5 x 1.5 + 6) = 152.3 kips (phi 1.0). Eq. J10-5a (lb / d = 0.167): 0.40 (0.3125)^2 [1 + 3 (0.167)(0.3125 / 1.5)^1.5]
      (29,000 x 50 x 1.5 / 0.3125)^0.5 = 108.0 kips; 0.75 x = 81.0. Both under 210: bearing stiffeners needed.
      Pair 7 x 3/4 in., 1 in. clips: Apb = 2 (6)(0.75) = 9.0 in2, Eq. J7-1 1.8 (50)(9.0) = 810, 0.75 x = 607.5 kips. Column: A = 2 (7)(0.75)
      + 12 (0.3125)^2 = 11.67 in2, I = 0.75 (14.3125)^3 / 12 = 183.2 in4, r = 3.96 in., 0.75 h / r = 24.75 / 3.96 = 6.25 not over 25: Pn = 50 (11.67)
      = 583.6, 0.9 x = 525.2 kips. bs / ts = 9.33 against 0.56 (29,000 / 50)^0.5 = 13.49."""
    proj = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")], name="t", number="t", date="2026-11-26")
    v = dict(mark="G1", shape="BU 16x1-1/2 / 33x5/16 / 16x1-1/2", Fy="50", span="56", more_spans="", oh_left="", oh_right="", bracing="continuous", brace_pts="",
             self_weight="no", loads=[dict(case="D", kind="uniform", mag="1.25", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="3.75", x1="", x2="", label="")],
             defl=[], bu_a="42, 90", bu_tfa="yes", bu_ts="0.3125", bu_bs="4", bu_Fyst="50", bu_lb="6")
    r = {x.check: x for x in calc.build("steel_beam", v, proj)[0].rows}
    assert r["web local yielding at the supports"].capacity == pytest.approx(152.3, abs=0.05) and r["web local yielding at the supports"].demand == pytest.approx(210)
    assert r["web local crippling at the supports"].capacity == pytest.approx(81.0, abs=0.1)
    r = {x.check: x for x in calc.build("steel_beam", dict(v, bu_brg_ts="0.75", bu_brg_bs="7", bu_brg_clip="1"), proj)[0].rows}
    assert "web local yielding at the supports" not in r
    assert r["bearing stiffeners, bearing on the ends"].capacity == pytest.approx(607.5)
    assert r["bearing stiffeners as a column"].capacity == pytest.approx(0.9 * 50 * (10.5 + 12 * 0.3125 ** 2), rel=1e-6)
    assert r["bearing stiffener width-to-thickness, bs / ts"].capacity == pytest.approx(13.49, abs=0.01)
    with pytest.raises(calc.Missing):
        calc.build("steel_beam", dict(v, bu_brg_ts="0.75"), proj)
    with pytest.raises(WorksheetError):                                  # continuous beams: not covered
        calc.build("steel_beam", dict(v, more_spans="40"), proj)
