"""Bolted flange plate: AISC Design Examples v16.0 Example II.B-1 (W18x50 beam, 3/4 x 7 in. Grade 50 plates, 7/8 in. Group 120 bolts, threads
included, two rows of four at 3 in., 4 in. gage, 1-1/2 in. plate end distance, 1-1/4 in. beam end distance; MD 42, ML 126 kip-ft)."""
import pytest
from strukit import ws_more


@pytest.mark.parametrize("method, M, Pb, Pp, bolts, ty, tr, bs1, bs3, bsb, f13, comp", [
    ("LRFD", 252.0, 168, 161, 194, 237, 183, 381, 300, 294, 318, 237),
    ("ASD", 168.0, 112, 108, 130, 157, 122, 254, 200, 197, 211, 157)])
def test_design_example_ii_b_1(method, M, Pb, Pp, bolts, ty, tr, bs1, bs3, bsb, f13, comp):
    r = ws_more.flange_plate_bolted(M * 12, M * 12, "W18X50", 50, 65, 7, 0.75, 50, 65, 0.875, "A325", "N", 4, 3, 4, 1.5, 1.25, 2.0, method,
                                    weld=0.375)
    assert r["Pb"] == pytest.approx(Pb, rel=0.005) and r["Pp"] == pytest.approx(Pp, rel=0.005)
    assert r["R_bolts"] == pytest.approx(bolts, rel=0.006)
    assert r["An"] == pytest.approx(3.75) and r["R_ty"] == pytest.approx(ty, rel=0.006) and r["R_tr"] == pytest.approx(tr, rel=0.006)
    assert r["bs1"] == pytest.approx(bs1, rel=0.006) and r["bs3"] == pytest.approx(bs3, rel=0.006) and r["bsb"] == pytest.approx(bsb, rel=0.006)
    assert r["f13"] and r["Afn"] == pytest.approx(3.14, abs=0.01) and r["R_f13"] / 12 == pytest.approx(f13, rel=0.006)
    assert r["Lc_r"] == pytest.approx(8.99, abs=0.02) and r["R_c"] == pytest.approx(comp, rel=0.006)
    # the example's required weld: 5.51 / 5.54 sixteenths for 161 / 108 kips; a 3/8 in. weld gives 6/5.51 x 161 kips (LRFD)
    if method == "LRFD":
        assert r["R_w"] == pytest.approx(161 * 6 / 5.51, rel=0.006)
    else:
        assert r["R_w"] == pytest.approx(108 * 6 / 5.54, rel=0.006)
