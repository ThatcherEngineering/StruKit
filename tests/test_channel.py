"""Channels on the Steel Beam screen, AISC 360-22 Sect. F2 (Eq. F2-8b) and G2.1(b).

Reference: AISC Design Examples v16.0, F.2-1B and F.2-2B (C15x33.9, Fy 50 ksi, 25 ft, D 0.23 and L 0.69 kip/ft: Mu = 108 kip-ft; Mp = 2,540 kip-in.;
Lp = 3.18 ft, Lr = 11.2 ft; braced at fifth points, Lb = 5 ft, Cb = 1.00: Mn = 2,300 kip-in., 0.90 Mn = 173 kip-ft, Mn/1.67 = 115 kip-ft) and
G.2B (Vn = 180 kips, 0.90 Vn = 162 kips, Vn/1.67 = 108 kips)."""
import pytest

from strukit import calcsheet, shapes, steel_beam
from strukit.gui import calc


def test_channel_against_design_examples_f2_and_g2():
    p = shapes.channel("C15x33.9")
    assert (p["type"], p["Zx"], p["Sx"], p["d"], p["tw"]) == ("C", 50.8, 42.0, 15.0, 0.4) and len(shapes.channel_labels()) == 72
    r = steel_beam.check(p, 50.0, 60.0, 1.0, "LRFD")
    by = {l.label: l for l in r.lines}
    assert by["Mp = Fy Zx"].value == pytest.approx(2540) and by["Lp"].value / 12 == pytest.approx(3.18, abs=0.01) and by["Lr"].value / 12 == pytest.approx(11.2, abs=0.05)
    assert r.Mn == pytest.approx(2300, abs=8) and r.M_avail / 12 == pytest.approx(173, abs=0.8)
    assert r.Vn == pytest.approx(180) and r.V_avail == pytest.approx(162)
    a = steel_beam.check(p, 50.0, 0.0, 1.0, "ASD")
    assert a.M_avail / 12 == pytest.approx(127, abs=0.5) and a.V_avail == pytest.approx(108, abs=0.3)
    w = steel_beam.check(shapes.get("W18X50"), 50.0, 0.0, 1.0, "LRFD")           # rolled I-shapes keep phi_v = 1.00
    assert w.V_avail == pytest.approx(w.Vn)


def test_channel_on_the_steel_beam_screen(tmp_path):
    lrfd = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 Sect. 2.3.1, combination 2")])
    v = dict(mark="CB1", shape="C15X33.9", Fy="50", span="25", bracing="at points", brace_pts="5, 10, 15, 20", self_weight="no",
             loads=[dict(case="D", kind="uniform", mag="0.23", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="0.69", x1="", x2="", label="")],
             defl=[dict(label="live", expr="L", ratio="360", source="typed in")])
    s, kind, kw = calc.build("steel_beam", v, lrfd)
    r = {x.check: x for x in s.rows}
    assert r["flexure"].demand == pytest.approx(108, abs=0.5) and r["flexure"].capacity == pytest.approx(173, abs=1.0)
    assert r["deflection, live"].demand == pytest.approx(0.664, abs=0.002) and any("shear center" in a for a in s.assumptions)
    calcsheet.steel_beam_pdf(s, str(tmp_path / "c.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    assert calc.results("steel_column", dict(mark="C1", shape="C15X33.9", Fy="50", height="12", ends="held sideways (braced)", Kx="1", Ky="1", k_source="x",
                                             self_weight="no", loads=[dict(case="D", P="5")], lateral=[], leaning=[], drift=[]), lrfd)["state"] == "stopped"
