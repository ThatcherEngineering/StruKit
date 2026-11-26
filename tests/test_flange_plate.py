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


@pytest.mark.parametrize("method, M, Pw, Pp, ty, w, cp, bot_w, bot_r", [
    ("LRFD", 252.0, 168, 160, 270, 169, 295, 168, 419),
    ("ASD", 168.0, 112, 107, 180, 113, 196, 112, 279)])
def test_design_example_ii_b_2_welded_flange_plates(method, M, Pw, Pp, ty, w, cp, bot_w, bot_r):
    """AISC Design Examples v16.0 Example II.B-2, W18x50 beam, A572 Gr. 50 plates, 5/16 in. fillets. Top plate PL1 x 6, welds 2 x 8.94 in.
    plus 6 in. across the end (Rn = 225 kips by Eq. J2-6); bottom plate PL3/4 x 8-3/4 (wider than the 7.5 in. flange), 12-1/2 in. welds,
    compression length 1.75 in. (Lc / r = 5.24), beam flange rupture at the welds (Anv = 14.3 in2). The example rounds the weld areas
    (3.95, 1.33 in2) and r (0.217 in.), hence the 0.8 percent on the weld."""
    from strukit.ws_more import flange_plate_welded
    top = flange_plate_welded(M * 12, M * 12, "W18X50", 50, 65, 6.0, 1.0, 50, 65, 5 / 16, 8.94, True, 1.75, method, arm=18.875)
    assert top["Pw"] == pytest.approx(Pw, rel=0.004) and top["Pp"] == pytest.approx(Pp, rel=0.006)
    assert top["R_ty"] == pytest.approx(ty, rel=0.004) and top["R_w"] == pytest.approx(w, rel=0.008)
    assert top["Rnw_b"] == pytest.approx(225, rel=0.005) and top["narrow"]
    bot = flange_plate_welded(M * 12, M * 12, "W18X50", 50, 65, 8.75, 0.75, 50, 65, 5 / 16, 12.5, False, 1.75, method)
    assert not bot["narrow"] and bot["Lc_r"] == pytest.approx(5.24, abs=0.02) and bot["R_c"] == pytest.approx(cp, rel=0.006)
    assert bot["R_w"] >= bot_w and bot["bm_beam"] == pytest.approx(bot_r, rel=0.006)
    with pytest.raises(Exception, match="transverse weld"):
        flange_plate_welded(M * 12, M * 12, "W18X50", 50, 65, 8.75, 0.75, 50, 65, 5 / 16, 12.5, True, 1.75, method)
