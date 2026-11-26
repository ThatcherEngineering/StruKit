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


@pytest.mark.parametrize("method, Fy, W, t, leg, d, grp, thr, n, bolts_", [
    ("LRFD", 36, 3.5, 0.3125, 83.5, 0.75, "A325", "N", 3, 107), ("ASD", 36, 3.5, 0.3125, 55.7, 0.75, "A325", "N", 3, 71.6),
    ("LRFD", 50, 5.0, 0.75, 430, 0.875, "A325", "X", 4, 245), ("ASD", 50, 5.0, 0.75, 287, 0.875, "A325", "X", 4, 163)])
def test_all_bolted_against_manual_table_10_7(method, Fy, W, t, leg, d, grp, thr, n, bolts_):
    """AISC Manual Table 10-7 (14th Ed. page, the 15th Ed. page as a scan): outstanding angle leg bearing 1.8 Fy Apb with Apb = 2 (W - 3/4) t, and
    bolt shear of two vertical rows of n bolts (Fnv unchanged in AISC 360-22)."""
    s = ws_more.stiffened_seat_sheet("SB1", "W21X68", 50, "ASTM A992", W, 15, t, Fy, "s", 0.375, 0, 70, "W14X90 flange", 0.710, 65, LOADS,
                                     COMB[method], method, bolted=dict(d=d, group=grp, threads=thr, n=n, s=3.0, lev=1.5, Fu=58 if Fy == 36 else 65))
    b = s.conn["bolted"]
    assert b["Rbr"] == pytest.approx(leg, rel=0.005) and 2 * n * b["rv"] == pytest.approx(bolts_, rel=0.005)
    names = [r.check for r in s.rows]
    assert "Stiffener-to-support welds" not in names and "Bolts, stiffener angles to the support" in names
    assert "Bolted" not in dict(s.info) and "Bolts" in dict(s.info)


def test_column_web_limits_and_top_angle(tmp_path):
    """Manual Part 10 simplified column web limits (Sputo and Ellifritt): shapes covered, B by the seat width (Table 10-8 limitations), the
    W12x40 / W14x43 weld limit at W = 4 in., and the top angle at least 1/4 in. with a 4 in. vertical leg."""
    a = ("SS1", "W21X68", 50, "ASTM A992", 7, 15, 0.625, 50, "s", 0.375, 0.3125, 70, "W14X90 web", 0.440, 65, LOADS, COMB["LRFD"], "LRFD")
    s = ws_more.stiffened_seat_sheet(*a, web_col="W14X90", B=3.25, top=dict(t=0.25, leg=4, attach="two bolts through each leg"))
    r = {x.check: x for x in s.rows}
    assert r["Column web punching: seat bolts from the web face, B"].capacity == 3.5 and r["Top angle thickness"].capacity == 0.25
    assert "the top angle" not in s.not_checked
    assert not ws_more.stiffened_seat_sheet(*a, web_col="W14X90", B=3.75).ok                   # B over 3-1/2 in. for W = 7 in.
    a6 = list(a); a6[4] = 6
    assert {x.check: x for x in ws_more.stiffened_seat_sheet(*a6, web_col="W12X50", B=2.0).rows}["Column web punching: seat bolts from the web face, B"].capacity == 3.0
    a4 = list(a); a4[4] = 4
    w = ws_more.stiffened_seat_sheet(*a4, web_col="W14X43", B=2.5)
    assert {x.check: x for x in w.rows}["Column web punching: weld size"].demand == 0.3125 and not w.ok
    with pytest.raises(Exception, match="not covered"):
        ws_more.stiffened_seat_sheet(*a, web_col="W14X30", B=2.5)
    with pytest.raises(Exception, match="item 3"):
        a8 = list(a); a8[4] = 8
        ws_more.stiffened_seat_sheet(*a8, web_col="W14X90", B=3.75)
    with pytest.raises(Exception, match="item 3"):
        ws_more.stiffened_seat_sheet(*a, web_col="W14X43", B=3.25)
    assert not ws_more.stiffened_seat_sheet(*a, top=dict(t=0.1875, leg=4, attach="welded along the toes only")).ok
    from strukit import calcsheet
    calcsheet.simple_pdf(s, str(tmp_path / "ss.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")
