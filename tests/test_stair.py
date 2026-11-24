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
