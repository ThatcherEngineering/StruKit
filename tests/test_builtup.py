"""Built-up three-plate I-shapes (builtup.py) against AISC Design Examples v16.0: F.14 plate girder (Sect. F4), E.2 built-up column with a
slender web (E7), E.3 slender flanges (Table B4.1a Case 2), E.12 singly symmetric member (flexural-torsional buckling, Eq. E4-3). The
examples round ho and other intermediate values; tolerances are set to that rounding (1 percent or less)."""
import pytest

from strukit import builtup, shapes, steel_beam, steel_column
from strukit.gui import calc


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
