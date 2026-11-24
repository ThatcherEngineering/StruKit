"""Steel stair stringer, horizontal plane method.

Reference: AISC Design Guide 34, Example 10.1.2: C12x20.7, ASTM A36, 9 ft 8 in. run, 7 in. risers, 11 in. treads, slope ratio 1.19; wD = 0.109 kip/ft
(35 psf x 3.67 ft / 2, self-weight x 1.19, 20 lb/ft guard), wL = 0.183 kip/ft; RD = 0.527 kip, RL = 0.885 kip; Mu = 4.96 kip-ft, Ma = 3.41 kip-ft;
0.90 Mn = 69.1 kip-ft, Mn/1.67 = 46.0 kip-ft; Vu = 2.05 kips, Va = 1.41 kips; 0.90 Vn = 65.8 kips, Vn/1.67 = 43.8 kips; live deflection
0.00967 in. x 1.40 against 9.67 ft / 360 = 0.322 in.  Stair live loads as printed in ASCE/SEI 7-22 Table 4.3-1."""
import pytest

from strukit import calcsheet, ws_more
from strukit.gui import calc

V = dict(mark="ST1", shape="C12X20.7", Fy="36", run="9.6667", riser="7", tread="11", trib="1.835", dead="35", dead_note="pans, concrete fill and finishes", extra="20",
         extra_note="guard and handrail", occupancy="stairs and exit ways", braced="yes", defl=[dict(label="live", expr="L", ratio="360", source="AISC Design Guide 34 Table 10-1")])
LRFD = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 Sect. 2.3.1, combination 2")])
ASD = dict(method="ASD", combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 2")])


def test_stringer_of_design_guide_34(tmp_path):
    assert ws_more.STAIR_LIVE == {"stairs and exit ways": 100.0, "one- and two-family dwellings": 40.0} and ws_more.STAIR_TREAD_P == 300.0
    s, kind, kw = calc.build("stair_stringer", V, LRFD)
    r = {x.check: x for x in s.rows}
    assert kind == "steel_beam" and sum(l["w"] for l in s.loads if l["case"] == "D") == pytest.approx(0.109, abs=0.0005)
    assert [l["w"] for l in s.loads if l["case"] == "L"] == [pytest.approx(0.1835)] and s.stair["k"] == pytest.approx(1.19, abs=0.005)
    assert r["flexure"].demand == pytest.approx(4.96, abs=0.01) and r["flexure"].capacity == pytest.approx(69.1, abs=0.05)
    assert r["shear"].demand == pytest.approx(2.05, abs=0.005) and r["shear"].capacity == pytest.approx(65.8, abs=0.05)
    assert r["deflection, live"].demand == pytest.approx(0.00967 * 1.40, abs=0.0003) and r["deflection, live"].capacity == pytest.approx(0.322, abs=0.0005)
    calcsheet.steel_beam_pdf(s, str(tmp_path / "s.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    a, _, _ = calc.build("stair_stringer", V, ASD)
    ra = {x.check: x for x in a.rows}
    assert ra["flexure"].demand == pytest.approx(3.41, abs=0.01) and ra["flexure"].capacity == pytest.approx(46.0, abs=0.05)
    assert ra["shear"].demand == pytest.approx(1.41, abs=0.005) and ra["shear"].capacity == pytest.approx(43.8, abs=0.05)


def test_stringer_other_sections_and_stops(tmp_path):
    h, _, kw = calc.build("stair_stringer", dict(V, shape="HSS12x4x1/4", Fy="50", occupancy="one- and two-family dwellings", extra="", extra_note=""), ASD)
    assert [l["w"] for l in h.loads if l["case"] == "L"] == [pytest.approx(40 * 1.835 / 1000)] and len(h.loads) == 3
    calcsheet.steel_beam_pdf(h, str(tmp_path / "h.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    assert calc.results("stair_stringer", dict(V, braced="no"), ASD)["state"] == "stopped"
    assert calc.results("stair_stringer", dict(V, extra_note=""), ASD)["state"] == "stopped"
    assert calc.results("stair_stringer", dict(V, dead_note=""), ASD)["state"] == "incomplete"
    assert calc.results("stair_stringer", dict(V, shape="L4X4X1/4"), ASD)["state"] == "stopped"


def test_bent_plate_tread_design_guide_34_example_10_2_2(tmp_path):
    """DG 34 Example 10.2.2 (pp. 88-90): 3/16 in. plate, 12 in. wide, 2 in. legs, 3 ft span, Fy = 26.7 ksi, 60 psf or 1 kip.  Published (software section,
    bend radii): A 2.88 in2, Ix 0.711 in4, Sx 0.426 in3, Zx 0.773 in3; ASD Va 0.105 / 1.02 kips, Ma 0.0788 / 0.761 kip-ft, Vn/Omega 7.20 kips,
    Mn/Omega 0.909 kip-ft; LRFD Vu 1.62 kips, Mu 1.21 kip-ft, 10.8 kips, 1.36 kip-ft.  StruKit's square-corner section is within 2 percent."""
    import pytest
    from strukit import calcsheet
    from strukit.gui import calc
    from strukit.ws_more import bent_plate_tread, stair_tread_sheet
    pr = bent_plate_tread(12.0, 0.1875, 2.0)
    assert pr["A"] == pytest.approx(2.88, rel=0.02) and pr["Ix"] == pytest.approx(0.711, rel=0.01) and pr["S"] == pytest.approx(0.426, rel=0.005) and pr["Zx"] == pytest.approx(0.773, rel=0.005)
    a = stair_tread_sheet("TR1", 0.1875, 12.0, 2.0, 3.0, 26.7, "approximate, A786", 60.0, 1000.0, "OSHA industrial stair", "ASD")
    (_, Mu_, Vu_), (_, Mc_, Vc_) = a.tread["cases"]
    assert Vu_ == pytest.approx(105, abs=1) and Mu_ == pytest.approx(78.8, abs=0.5) and Vc_ == pytest.approx(1020, rel=0.005) and Mc_ == pytest.approx(761, abs=1.5)
    assert a.tread["Vc"] == pytest.approx(7200, rel=0.005) and a.tread["Mc"] == pytest.approx(909, rel=0.005) and a.ok
    l = stair_tread_sheet("TR1", 0.1875, 12.0, 2.0, 3.0, 26.7, "approximate, A786", 60.0, 1000.0, "OSHA industrial stair", "LRFD")
    assert l.tread["cases"][1][2] == pytest.approx(1620, rel=0.005) and l.tread["cases"][1][1] == pytest.approx(1210, rel=0.005)
    assert l.tread["Vc"] == pytest.approx(10800, rel=0.005) and l.tread["Mc"] == pytest.approx(1360, rel=0.01)
    v = dict(mark="TR1", t="0.1875", b="12", d="2", span="3", Fy="26.7", Fy_source="approx", live_psf="60", live_P="1000", live_source="OSHA")
    s, kind, _ = calc.build("stair_tread", v, dict(method="ASD"))
    calcsheet.simple_pdf(s, str(tmp_path / "t.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")
    assert calc.results("stair_tread", dict(v, live_source=""), dict(method="ASD"))["state"] == "incomplete"
    assert not stair_tread_sheet("TR1", 0.1875, 12.0, 2.0, 4.0, 26.7, "x", 100.0, 1000.0, "y", "ASD").ok


def test_stringer_refuses_an_angle_with_a_plain_message():
    from strukit.gui import calc
    v = dict(mark="ST9", shape="L4X4X1/2", Fy="36", run="10", riser="7", tread="11", trib="2", dead="20", dead_note="pans", extra="", extra_note="", occupancy="stairs and exit ways", braced="yes", defl=[])
    out = calc.results("stair_stringer", v, dict(name="T", number="1", address="", method="ASD", date="2026-11-23", combos=[dict(expr="D + L", source="typed")]))
    assert out["state"] == "stopped" and "I-shape, channel, HSS or pipe tables" in out["messages"][0]


def test_industrial_stringer_uniform_load_design_guide_34_example_10_2_3():
    """AISC Design Guide 34 Example 10.2.3, uniform live loading: HSS12x2x1/4 (22.42 lb/ft), A500 Gr. C, 14.7 ft run, 7 / 11 stair, treads 10 psf on a
    3 ft stair (1.5 ft to each stringer), guard 20 lb/ft, live 60 psf: wD = 0.0617 kip/ft, wL = 0.0900 kip/ft; wu = 0.218 / wa = 0.152 kip/ft;
    Vu = 1.60 / Va = 1.12 kips; Mu = 5.89 / Ma = 4.11 kip-ft.  (The example's 1 kip point load case is not on this screen; the sheet lists it as not checked.)"""
    v = dict(mark="ST2", shape="HSS12X2X1/4", Fy="50", run="14.7", riser="7", tread="11", trib="1.5", dead="10", dead_note="checkered plate treads", extra="20", extra_note="guard",
             occupancy="other (type the load)", live_psf="60", live_source="OSHA industrial stair, owner's criteria", braced="yes", defl=[])
    for proj, M, Vv in ((LRFD, 5.89, 1.60), (ASD, 4.11, 1.12)):
        s, _, _ = calc.build("stair_stringer", v, proj)
        r = {x.check: x for x in s.rows}
        assert sum(l["w"] for l in s.loads if l["case"] == "D") == pytest.approx(0.0617, abs=0.0003) and [l["w"] for l in s.loads if l["case"] == "L"] == [pytest.approx(0.0900)]
        assert r["flexure"].demand == pytest.approx(M, abs=0.02) and r["shear"].demand == pytest.approx(Vv, abs=0.01)
        assert any("a concentrated live load on the stringer" in a for a in s.assumptions)
    assert calc.results("stair_stringer", dict(v, live_source=""), ASD)["state"] == "incomplete"
    assert not any("concentrated live load on the stringer" in a for a in calc.build("stair_stringer", V, ASD)[0].assumptions)


def test_industrial_stringer_point_load_design_guide_34_example_10_2_3(tmp_path):
    """Same example, point live loading (1 kip anywhere, not with the uniform load): Vu = 2.14 / Va = 1.45 kips; Mu = 7.88 / Ma = 5.34 kip-ft."""
    v = dict(mark="ST2", shape="HSS12X2X1/4", Fy="50", run="14.7", riser="7", tread="11", trib="1.5", dead="10", dead_note="checkered plate treads", extra="20", extra_note="guard",
             occupancy="other (type the load)", live_psf="60", live_P="1000", live_source="OSHA industrial stair, owner's criteria", braced="yes", defl=[])
    for proj, M, Vv in ((LRFD, 7.88, 2.14), (ASD, 5.34, 1.45)):
        s, _, kw = calc.build("stair_stringer", v, proj)
        r = {x.check: x for x in s.rows}
        assert r["flexure, concentrated live load"].demand == pytest.approx(M, abs=0.02) and r["shear, concentrated live load"].demand == pytest.approx(Vv, abs=0.01)
        assert r["flexure, concentrated live load"].capacity == r["flexure"].capacity and r["shear, concentrated live load"].capacity == r["shear"].capacity
        assert r["flexure, concentrated live load"].demand > r["flexure"].demand and s.ok
        assert any("does not act with the uniform live load" in a for a in s.assumptions) and not any("a concentrated live load on the stringer," in a for a in s.assumptions)
        calcsheet.steel_beam_pdf(s, str(tmp_path / "p.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
