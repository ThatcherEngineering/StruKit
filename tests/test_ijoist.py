"""I-joists: Boise BCI (ESR-1336) and Weyerhaeuser TJI (ESR-1153), 2018 NDS Chapter 7.

Independent references:
  - Boise West Specifier Guide MTP-W7000, "BCI Joist Design Properties": every BCI row in
    the data file (read from ESR-1336 by tools/parse_ijoists.py) is compared with the guide.
  - The same guide's allowable uniform load table, live load at L/480 without composite
    action, BCI 5000-1.7 9-1/2 in.: 12 ft 91 plf, 14 ft 59 plf, 16 ft 40 plf.
  - ESR-1153 Table 3 note 2 deflection formula, by hand.
"""
import pytest

from strukit import ijoist as ij, ws_ijoist
from strukit.ws_steel_beam import DeflCheck
from tests.test_lvl import _combos

GUIDE = {  # series: depth: (moment, EI e6, K e6, shear, end 1.5 no WS, WS, end 3.5 no WS, WS)
    "5000-1.7": {9.5: (2460, 160, 5, 1475, 950, 1125, 1125, 1275), 11.875: (3150, 265, 6, 1625, 950, 1425, 1425, 1475),
                 14: (3735, 390, 8, 1825, 950, 1525, 1475, 1725)},
    "6000-1.8": {9.5: (3165, 190, 5, 1575, 1175, 1375, 1375, 1425), 11.875: (4060, 320, 6, 1675, 1175, 1425, 1425, 1475),
                 14: (4815, 470, 8, 1925, 1175, 1525, 1525, 1725), 16: (5495, 635, 9, 2175, 1175, 1625, 1550, 1975)},
    "6500-1.8": {9.5: (3505, 210, 5, 1575, 1175, 1375, 1375, 1425), 11.875: (4495, 350, 7, 1675, 1175, 1425, 1425, 1475),
                 14: (5330, 515, 8, 1925, 1175, 1525, 1525, 1725), 16: (6085, 695, 9, 2175, 1175, 1625, 1550, 1975)},
    "60-2.0": {11.875: (6235, 430, 7, 1675, 1175, 1425, 1425, 1475), 14: (7440, 635, 8, 1925, 1175, 1525, 1525, 1725),
               16: (8520, 860, 9, 2175, 1175, 1625, 1550, 1975)},
    "90-2.0": {11.875: (9550, 645, 7, 2150, 1425, 1850, 1800, 1950), 14: (11390, 940, 8, 2350, 1450, 1950, 1850, 2150),
               16: (13050, 1275, 9, 2550, 1475, 2150, 1900, 2350), 18: (14690, 1660, 10, 2750, None, 2300, None, 2550),
               20: (16310, 2100, 11, 2850, None, 2500, None, 2650)},
}


def test_bci_data_matches_the_boise_guide():
    n = 0
    for ser, rows in GUIDE.items():
        for d, g in rows.items():
            j = ij.joist(f"BCI {ser}", d)
            assert (j["M"], j["EI"] / 1e6, j["K"] / 1e6, j["V"], j["Re_short"], j["Re_short_ws"], j["Re_35"], j["Re_35_ws"]) == g, (ser, d)
            n += 1
    assert n == 19 and sum(1 for k in ij.JOISTS if k[0] == "BCI") == 19


def test_tji_data():
    assert sum(1 for k in ij.JOISTS if k[0] == "TJI") == 35
    j = ij.joist("TJI 210", 11.875)
    assert (j["M"], j["V"], j["EI"], j["weight"], j["Re_short"], j["Re_short_ws"], j["Re_35"], j["Re_35_ws"]) == (3795, 1655, 315e6, 2.8, 1005, 1365, 1460, 1655)
    assert j["K"] == pytest.approx(4.5 * 11.875 * 1e5)
    j = ij.joist("TJI 360", 11.875)
    assert (j["M"], j["V"], j["EI"]) == (6180, 1705, 419e6)
    j = ij.joist("TJI 560D", 24)
    assert (j["M"], j["V"], j["Re_short"], j["Re_35_ws"]) == (19700, 3400, None, 2830)
    with pytest.raises(ij.IJoistError, match="web stiffeners"):
        ij.end_reaction(j, 3.5, False)
    assert ij.end_reaction(ij.joist("TJI 210", 11.875), 2.625, False)[0] == pytest.approx((1005 + 1460) / 2)      # note 4
    assert ij.end_reaction(ij.joist("BCI 6000-1.8", 11.875), 2.5, False)[0] == 1175


def _live_at_l480(span):
    lo, hi = 20.0, 120.0
    for _ in range(9):
        w = (lo + hi) / 2
        s = ws_ijoist.joist("J", "BCI 5000-1.7", 9.5, span, None, [dict(case="L", kind="uniform", w=w)], _combos(),
                            [DeflCheck("live", {"L": 1.0}, 480, "guide")], 1.5, False, True)
        r = [x for x in s.rows if x.check.startswith("deflection")][0]
        lo, hi = (w, hi) if r.demand < r.capacity else (lo, w)
    return lo


def test_live_load_at_l480_matches_the_boise_load_table():
    for span, plf in ((12, 91), (14, 59), (16, 40)):
        assert _live_at_l480(span) == pytest.approx(plf, abs=1.0)


def test_tji_sheet_by_hand():
    # TJI 210 11-7/8 at 16 in, 15 ft, D 12 psf + L 40 psf: w = 16 + 53.33 + 2.8 = 72.13 plf
    # M = 72.13 x 225 / 8 = 2,028.7 lb-ft against 3,795; V = R = 541.0 lb against 1,655 and 1,005
    # live deflection (note 2): 22.5 x 53.33 x 15^4 / 315e6 + 12 x 53.33 x 225 / (4.5 x 11.875 x 1e5) = 0.1929 + 0.0269
    loads = [dict(case="D", kind="area", q=12.0), dict(case="L", kind="area", q=40.0)]
    s = ws_ijoist.joist("J1", "TJI 210", 11.875, 15, 16, loads, _combos(), [DeflCheck("live", {"L": 1.0}, 480, "typed")], 1.75, False, True)
    r = {x.check: x for x in s.rows}
    assert r["moment"].demand == pytest.approx(2028.7, abs=0.5) and r["moment"].capacity == 3795
    assert r["shear"].demand == pytest.approx(541.0, abs=0.2) and r["shear"].capacity == 1655
    assert r["end reaction"].demand == pytest.approx(541.0, abs=0.2) and r["end reaction"].capacity == 1005
    assert r["deflection, live"].demand == pytest.approx(0.1929 + 0.0269, abs=0.001)
    with pytest.raises(Exception, match="7.3.5"):
        ws_ijoist.joist("J1", "TJI 210", 11.875, 15, 16, loads, _combos(), [], 1.75, False, False)


def test_intermediate_reactions_match_the_boise_guide():
    g = {("5000-1.7", 9.5): (2100, 2350, 2525, 2750), ("6000-1.8", 14): (2600, 3150, 2925, 3200), ("60-2.0", 14): (2750, 3450, 3200, 3650),
         ("90-2.0", 11.875): (3375, 3700, 4000, 4300), ("90-2.0", 18): (None, 4150, None, 4750), ("6500-1.8", 16): (2650, 3350, 2950, 3350)}
    for (ser, d), v in g.items():
        j = ij.joist(f"BCI {ser}", d)
        assert (j["Ri_35"], j["Ri_35_ws"], j["Ri_525"], j["Ri_525_ws"]) == v, (ser, d)
    t = ij.joist("TJI 210", 11.875)
    assert (t["Ri_35"], t["Ri_35_ws"], t["Ri_525"], t["Ri_525_ws"]) == (2145, 2505, 2565, 2925)
    assert ij.intermediate_reaction(t, 4.375, False)[0] == pytest.approx((2145 + 2565) / 2)
    assert ij.joist("TJI 560D", 28)["Ri_35_ws"] is None                 # tabulated only for a longer bearing (note 7)
    with pytest.raises(ij.IJoistError, match="3.5"):
        ij.intermediate_reaction(t, 3.0, False)


def test_two_span_joist_by_hand():
    # BCI 6000-1.8 11-7/8 at 16 in, two 15 ft spans, D 12 psf + L 40 psf: wD = 16 + 2.5 = 18.5 plf, wL = 53.33 plf
    # support moment (all loaded): 71.83 x 225 / 8 = 2,020.3 lb-ft; span moment with live on one span:
    #   9/128 x 18.5 x 225 + 49/512 x 53.33 x 225 = 292.7 + 1,148.4 = 1,441.1 -> the support governs
    # centre reaction 1.25 x 71.83 x 15 = 1,346.9 lb against 2,500 (3.5 in., no stiffeners)
    # end reaction 0.375 x 18.5 x 15 + 0.4375 x 53.33 x 15 = 104.1 + 350.0 = 454.1 lb; shear 0.625 x 71.83 x 15 = 673.4 lb
    loads = [dict(case="D", kind="area", q=12.0), dict(case="L", kind="area", q=40.0)]
    s = ws_ijoist.joist("J2", "BCI 6000-1.8", 11.875, 15, 16, loads, _combos(), [DeflCheck("live", {"L": 1.0}, 480, "typed")], 1.5, False, True,
                        spans=[15, 15], bearing_int_in=3.5)
    r = {x.check: x for x in s.rows}
    assert r["moment"].demand == pytest.approx(2020.3, abs=1.0) and "negative" in r["moment"].note and r["moment"].capacity == 4060
    assert r["intermediate reaction"].demand == pytest.approx(1346.9, abs=0.5) and r["intermediate reaction"].capacity == 2500
    assert r["end reaction"].demand == pytest.approx(454.1, abs=0.5) and r["shear"].demand == pytest.approx(673.4, abs=0.5)
    assert any("4.3.3" in a for a in s.assumptions)
