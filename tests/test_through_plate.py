"""Through-plate flange-plated moment connection, AISC Design Guide 24 (2nd Ed.) Example 6.4: W18x71 beams each side of an HSS20x12x1/2
(H = 20 in. along the beams), PL 1/2 x 14 through plates, (8) 1 in. Group 120-N bolts each side (two lines of four at 3 in., gage 3-1/2 in.),
3 in. from the HSS face to the first bolt, 1-3/4 in. plate end, 2 in. beam end; 1/2 in. E70 fillets to the HSS."""
import pytest

from strukit.gui import calc
from strukit.ws_more import through_plate_sheet

GEOM = ("W18X71", 50, 65, "ASTM A992", "HSS20X12X1/2", 62, "ASTM A500 Gr. C", "H", 14, 0.5, 50, 65, "ASTM A572 Gr. 50", 1.0, "A325", "N", 4, 3, 3.5, 3, 1.75, 2, 0.5, 70)


def test_example_6_4_lrfd_and_asd():
    s = through_plate_sheet("TP", *GEOM, [], [], "LRFD", runs=[dict(name="LRFD", ML=72, VL=9.6, MR=360, VR=48, P=288)])
    t = s.tp
    assert t["R"] == pytest.approx(227, abs=0.5) and t["Rr"] == pytest.approx(284, rel=0.004) and t["KLr"] == pytest.approx(20.8, abs=0.05)
    assert t["Rb"] == pytest.approx(254, rel=0.003) and all(p[2] == "shear" for p in t["per"])                 # bolt shear governs every bolt
    assert t["Ant"] == pytest.approx(1.16, abs=0.005) and t["Rbs_p"] == pytest.approx(334, rel=0.006)          # the example rounds Agv to 10.8 in2
    assert t["Rbs_f"] == pytest.approx(588, rel=0.002)
    assert t["Pc"] == pytest.approx(346, abs=0.5) and t["Mc"] == pytest.approx(160, abs=0.1)
    assert t["q"] == pytest.approx(10.6, abs=0.07) and t["rw"] == pytest.approx(1.392 * 8, rel=1e-3) and t["tmin"] == pytest.approx(0.399, abs=0.001)
    a = through_plate_sheet("TP", *GEOM, [], [], "ASD", runs=[dict(name="ASD", ML=60, VL=8, MR=240, VR=32, P=192)]).tp
    assert a["R"] == pytest.approx(152, abs=0.5) and a["Rr"] == pytest.approx(189, rel=0.003) and a["Rb"] == pytest.approx(170, rel=0.003)
    assert a["Pc"] == pytest.approx(232) and a["Mc"] == pytest.approx(100) and a["q"] == pytest.approx(6.84, abs=0.01) and a["rw"] == pytest.approx(0.928 * 8, rel=1e-3)


def test_screen_and_tearout():
    v = dict(mark="TP1", beam="W18X71", beam_Fy="50", beam_Fu="65", beam_source="ASTM A992", column="HSS20X12X1/2", col_Fu="62", col_source="ASTM A500 Gr. C",
             along="depth H (the first dimension)", bp="14", tp="0.5", plate_Fy="50", plate_Fu="65", plate_source="ASTM A572 Gr. 50", d="1", group="A325", threads="N",
             n="4", s="3", g="3.5", L1="3", le_p="1.75", le_f="2", weld="0.5", FEXX="70",
             loads=[dict(case="D", ML="60", VL="8", MR="60", VR="8", P="48", label=""), dict(case="L", ML="0", VL="0", MR="180", VR="24", P="144", label="")])
    proj = dict(name="t", number="t", date="2026-11-26", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")])
    r = calc.results("through_plate", v, proj)
    assert r["state"] == "done" and r["status"] == "OK"
    # a thin plate with a short end distance: plate tearout governs the end bolt
    s = through_plate_sheet("TP", *GEOM[:9], 0.25, *GEOM[10:20], 1.25, *GEOM[21:], [], [], "LRFD", runs=[dict(name="x", ML=72, VL=9.6, MR=360, VR=48, P=288)])
    assert s.tp["per"][-1][2] == "plate_tearout" and s.tp["per"][-1][1] == pytest.approx(1.2 * (1.25 - 1.125 / 2) * 0.25 * 65)


def test_cut_out_plate_example_6_2():
    """External diaphragm (cut-out) plate, Design Guide 24 Example 6.2: W18x35 beams, HSS10x10x1/2, PL 3/4 with ws = 4 in. each side,
    (10) 3/4 in. Group 120-N bolts each side, s 3, g 3-1/2, plate end 1-1/4, beam end 3-1/2 in. The example designs for the beam's
    nominal strength at the holes, Mn = 2,660 kip-in. (F13.1), as the required moment."""
    G = ("W18X35", 50, 65, "ASTM A992", "HSS10X10X1/2", 62, "ASTM A500 Gr. C", "H", 0, 0.75, 50, 65, "ASTM A572 Gr. 50", 0.75, "A325", "N", 5, 3, 3.5, 5.5, 1.25, 3.5, 0.3125, 70)
    t = through_plate_sheet("CO", *G, [], [], "LRFD", runs=[dict(name="LRFD", ML=2660 / 12, VL=0, MR=2660 / 12, VR=0, P=0)], ws=4.0).tp
    assert t["Mn_b"] == pytest.approx(2660, rel=0.004) and t["Mb"] == pytest.approx(199, rel=0.004)      # Eq. F13-1, phi Mn 2,390 kip-in.
    assert t["R"] == pytest.approx(144, abs=0.5) and t["Rc"] == pytest.approx(135) and t["Rb"] == pytest.approx(179, rel=0.002)
    assert t["lw"] == pytest.approx(17.4, abs=0.05) and t["Ry"] == pytest.approx(270) and t["Rr"] == pytest.approx(293, rel=0.003)
    bs = t["bs_cases"]
    assert bs["2, tension between the bolt lines"] == pytest.approx(674, rel=0.003) and bs["3, one line, tension to the far edge"] == pytest.approx(733, rel=0.002)
    assert t["Rbs_f"] == pytest.approx(429, rel=0.003) and t["Runb"] == 0
    a = through_plate_sheet("CO", *G, [], [], "ASD", runs=[dict(name="ASD", ML=1590 / 12, VL=0, MR=1590 / 12, VR=0, P=0)], ws=4.0).tp
    assert a["R"] == pytest.approx(86.2, abs=0.1) and a["Rc"] == pytest.approx(89.8, abs=0.1) and a["Rb"] == pytest.approx(119, rel=0.003)
    assert a["Mb"] == pytest.approx(133, rel=0.005)
