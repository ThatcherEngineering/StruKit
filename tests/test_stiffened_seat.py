"""Stiffened seated connection: AISC Design Examples v16.0 Example II.A-14 (W21x68 beam on a W14x90 column flange, PL 5/8 x 7 x 15 in. Grade 50
stiffener, 3/8 in. seat plate, 5/16 in. fillets: AISC Manual Table 10-8 gives 139 / 93.0 kips; Wmin 6.93 / 6.96 in. for crippling and 3.59 /
3.61 in. for yielding; least stiffener thickness 0.469 in.; least support thickness 0.238 in. for Fu = 65 ksi)."""
import pytest
from strukit import ws_more
from strukit.ws_steel_beam import Combo

COMB = {"LRFD": [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t")], "ASD": [Combo("D + L", {"D": 1.0, "L": 1.0}, "t")]}
LOADS = [dict(case="D", P=21.0), dict(case="L", P=62.5)]


@pytest.mark.parametrize("method, weld, Wc, Wy, R1, R5", [("LRFD", 139, 6.93, 3.59, 64.0, 75.9), ("ASD", 93.0, 6.96, 3.61, 42.6, 50.6)])
def test_example_ii_a_14(method, weld, Wc, Wy, R1, R5):
    s = ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "ASTM A992", 7, 15, 0.625, 50, "ASTM A572 Gr. 50", 0.375, 0.3125, 70, "W14X90 flange",
                                     0.710, 65, LOADS, COMB[method], method)
    c = s.conn
    assert c["Rw"] == pytest.approx(weld, rel=0.005) and c["R1"] == pytest.approx(R1, rel=0.005) and c["R5"] == pytest.approx(R5, rel=0.005)
    assert c["Wc"] == pytest.approx(Wc, rel=0.005) and c["Wy"] == pytest.approx(Wy, rel=0.005)
    assert c["ts_min"] == pytest.approx(0.469, abs=0.001) and c["tmin"] == pytest.approx(0.238, abs=0.001) and s.ok


def test_thin_support_reduces_the_weld_and_stops():
    s = ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "ASTM A992", 7, 15, 0.625, 50, "s", 0.375, 0.3125, 70, "W14X90 web", 0.440, 65, LOADS,
                                     COMB["LRFD"], "LRFD", both_sides=True)
    assert s.conn["tmin"] == pytest.approx(2 * 0.2377, abs=0.001) and s.conn["Rw"] == pytest.approx(s.conn["Rw0"] * 0.440 / s.conn["tmin"], rel=1e-6)
    with pytest.raises(Exception):
        ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "", 7, 15, 0.625, 50, "s", 0.375, 0.3125, 70, "c", 0.7, 65, LOADS, COMB["LRFD"], "LRFD")
    thin = ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "a", 7, 15, 0.375, 36, "s", 0.3125, 0.3125, 70, "c", 0.7, 65, LOADS, COMB["LRFD"], "LRFD")
    assert thin.conn["ts_min"] == pytest.approx(max(0.430 * 50 / 36, 0.625)) and not thin.ok
