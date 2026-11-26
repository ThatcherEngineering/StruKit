"""Rods of a base plate all able to take tension (uplift, biaxial moment): ACI 318-19 17.6 by load case. Validated against AISC Design
Guide 1 (3rd Ed.) Example 4.7-3 (four 7/8 in. headed rods at 4 x 4 in., hef 15 in., f'c 4,000 psi, away from edges, 70 kips uplift)."""
import pytest

from strukit import anchorage as an, anchor_rods as ar, ws_more

A = dict(hef=15.0, ha=30.0, nt=9.0, fya=36.0, ductile=True, Abrg=ar.size(0.875)[1], head="heavy hex nut", cracked=True, supplementary=False,
         sdc="A or B", fc=4000.0)


def test_design_guide_1_example_4_7_3():
    runs = [("uplift", {(i, j): 17.5 for i in (0, 1) for j in (0, 1)})]
    deep = an.tension_grid(0.875, 9, 58, 36, True, 15, A["Abrg"], 4000, 30, 2, 4, 2, 4, 100, 100, 100, 100, True, False, runs, deep_eq_for_groups=True)
    r = {row[0]: row for row in deep["rows"]}
    assert r["rod steel, tension"][3] == pytest.approx(20.1, rel=0.005)            # phi Nsa
    assert r["pullout"][3] == pytest.approx(26.7, rel=0.005)                       # Table 4-2 value the example uses
    assert r["breakout, tension"][3] == pytest.approx(76.3, rel=0.005)             # 0.70 x 109 kips, Eq. 17.6.2.2.3 as the example
    assert r["breakout, tension"][2] == pytest.approx(70.0)
    # StruKit's ruling for groups (2026-11-23): kc = 24 (Eq. 17.6.2.2.1), the lower value
    low = an.tension_grid(0.875, 9, 58, 36, True, 15, A["Abrg"], 4000, 30, 2, 4, 2, 4, 100, 100, 100, 100, True, False, runs)
    Nb = 24 * 4000 ** 0.5 * 15 ** 1.5 / 1000
    assert {row[0]: row for row in low["rows"]}["breakout, tension"][3] == pytest.approx(0.70 * (49.0 ** 2 / (9 * 225)) * Nb, rel=1e-6)


def test_uplift_sheet_carries_the_anchorage():
    s = ws_more.base_plate_uplift_sheet("BPU1", "W10X45", 50, 14, 12, 1.0, 50, 0.875, 58, "ASTM F1554 Grade 36", 4.0, 4.0, 0.1875, 70,
                                        [dict(name="1.2D + 1.0W", T=70.0)], "LRFD", anchorage=dict(A))
    rows = {x.check: x for x in s.rows}
    assert rows["ACI breakout, tension"].demand == pytest.approx(70.0) and rows["ACI pullout"].demand == pytest.approx(17.5)
    assert not any("anchorage of the rods in the concrete" in t for t in s.not_checked)
    # near an edge: side blowout appears (hef 15 > 2.5 x 4.5 in.), and breakout drops
    e = ws_more.base_plate_uplift_sheet("BPU1", "W10X45", 50, 14, 12, 1.0, 50, 0.875, 58, "ASTM F1554 Grade 36", 4.0, 4.0, 0.1875, 70,
                                        [dict(name="1.2D + 1.0W", T=70.0)], "LRFD", anchorage=dict(A), support=(13.0, 40.0))
    er = {x.check: x for x in e.rows}
    assert any(k.startswith("ACI side blowout") for k in er) and er["ACI breakout, tension"].capacity < rows["ACI breakout, tension"].capacity


def test_biaxial_rod_tension_by_statics_and_corner_rods():
    q = 0.65 * 0.85 * 4.0 * 2 * 14.0                                          # kip/in. of bearing along 14 in.
    T = ws_more.bearing_rod_tension(90.0, 700.0, 14.0, 5.5, q)
    Y = (T + 90.0) / q
    assert q * Y * (7.0 - Y / 2) + T * 5.5 == pytest.approx(700.0, rel=1e-9)      # moment about the plate centre
    assert ws_more.bearing_rod_tension(90.0, 50.0, 14.0, 5.5, q) == 0.0           # small moment: no rod tension
    s = ws_more.base_plate_biaxial_sheet("BPX", "W8X48", 14, 14, 1.75, 50, 4000, 4.0, 0.625, 75, "ASTM F1554 Grade 55", 1.5, 1.5,
                                         [dict(name="LRFD", P=90.0, Mx=700 / 12, My=450 / 12)], "LRFD",
                                         anchorage=dict(A, hef=12.0, nt=11.0, Abrg=ar.size(0.625)[1], fya=55.0))
    rows = {x.check: x for x in s.rows}
    Tx = ws_more.bearing_rod_tension(90.0, 700.0, 14, 5.5, 0.65 * min(0.85 * 4 * 2, 1.7 * 4) * 14)
    Ty = ws_more.bearing_rod_tension(90.0, 450.0, 14, 5.5, 0.65 * min(0.85 * 4 * 2, 1.7 * 4) * 14)
    assert rows["ACI rod steel, tension"].demand == pytest.approx(Tx / 2 + Ty / 2, rel=1e-6)
    assert rows["ACI breakout, tension"].demand == pytest.approx(Tx + Ty, rel=1e-6)
