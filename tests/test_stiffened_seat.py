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


def test_stiffened_seat_on_an_hss_face_by_hand(tmp_path):
    """The Example II.A-14 seat (W21x68, PL 5/8 x 7 x 15 stiffener, 5/16 fillets) welded to the face of an HSS12x12x5/8 (t design 0.581 in.,
    Fy 50, Fu 62 ksi), AISC Design Guide 24 (2nd Ed.) Sect. 5.2.6; no published example, checked by hand. LRFD R = 1.2 (21) + 1.6 (62.5) =
    125.2 kips at 0.8 W = 5.6 in.: Mr = 701.1 kip-in.
      Face plastification, DG24 Eq. 2-6 (Manual Eq. 9-46): beta = 0.625 / 12 = 0.0521, eta = 15 / 12 = 1.25;
      50 (0.581)^2 (15) [1 / 2.5 + 2 / (1 - 0.0521)^0.5 + 1.25 / (1 - 0.0521)] = 253.2 x 3.7729 = 955.2 kip-in. (Qf = 1 with no column load).
      With 200 kips in the column: U = 200 / (50 x 25.7) = 0.156; Qf = 1 - 0.3 U (1 + U) = 0.946 (Eq. K1-3, longitudinal plate).
      Punching, Manual Eq. 10-10a: 0.75 (62)(0.581)(15)^2 / 5 = 1,215.8 kip-in."""
    from strukit import shapes
    col = shapes.hss("HSS12X12X5/8")
    hss = dict(shape="HSS12X12X5/8", face="B", Fy=50, Fu=62, Fy_source="ASTM A500 Gr. C", P=0.0, M=0.0, source="t")
    s = ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "ASTM A992", 7, 15, 0.625, 50, "ASTM A572 Gr. 50", 0.375, 0.3125, 70, "HSS12X12X5/8 face",
                                     col["tdes"], 62, LOADS, COMB["LRFD"], "LRFD", hss=hss)
    h = s.conn["hss"]
    t = col["tdes"]
    assert t == pytest.approx(0.581)
    assert h["Mr"] == pytest.approx(125.2 * 5.6) and h["Qf"] == 1.0
    assert h["Mn"] == pytest.approx(50 * t ** 2 * 15 * (1 / 2.5 + 2 / (1 - 0.625 / 12) ** 0.5 + 1.25 / (1 - 0.625 / 12)), rel=1e-9)
    assert h["Mn"] == pytest.approx(955.2, abs=0.5) and h["punch"] == pytest.approx(1215.8, abs=0.5)
    r = {x.check: x for x in s.rows}
    assert r["HSS face plastification under the stiffener"].demand == pytest.approx(701.1, abs=0.1)
    s2 = ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "ASTM A992", 7, 15, 0.625, 50, "ASTM A572 Gr. 50", 0.375, 0.3125, 70, "HSS12X12X5/8 face",
                                      t, 62, LOADS, COMB["LRFD"], "LRFD", hss=dict(hss, P=200.0))
    U = 200 / (50 * col["A"])
    assert s2.conn["hss"]["U"] == pytest.approx(U) and s2.conn["hss"]["Qf"] == pytest.approx(1 - 0.3 * U * (1 + U))
    with pytest.raises(Exception):                                    # bolted angles on an HSS face are not covered
        ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "a", 7, 15, 0.625, 50, "s", 0.375, 0.0, 70, "h", t, 62, LOADS, COMB["LRFD"], "LRFD",
                                     bolted=dict(d=0.75, group="A325", threads="N", n=3, s=3, lev=1.5, Fu=58), hss=hss)
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="SS2", beam="W21X68", beam_Fy="50", beam_source="ASTM A992", W="7", L="15", ts="0.625", stiff_Fy="50", stiff_source="ASTM A572 Gr. 50",
             tseat="0.375", weld="0.3125", FEXX="70", support="", t_sup="", Fu_sup="", hss_col="HSS12X12X5/8", hss_Fy="50", hss_Fu="62",
             hss_Fy_source="ASTM A500 Gr. C", hss_P="0", hss_M="0", hss_source="column takedown", top_t="0.25", top_leg="4", top_attach="welded along the toes only",
             loads=[dict(case="D", P="21", label=""), dict(case="L", P="62.5", label="")])
    sc = calc.build("stiffened_seat", v, dict(job="t", name="t", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[]))[0]
    assert sc.conn["hss"]["Mn"] == pytest.approx(h["Mn"]) and sc.conn["tmin"] == pytest.approx(3.09 * 5 / 62, rel=1e-6)
    calcsheet.simple_pdf(sc, str(tmp_path / "ss_hss.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")


def test_bolted_angle_leg_width_to_thickness():
    """All-bolted stiffened seat: the outstanding angle leg W / t against 0.45 (E / Fy)^0.5 (Table B4.1a Case 3): 5 / 0.375 = 13.3 against
    0.45 (29,000 / 36)^0.5 = 12.8, flagged; 4 / 0.375 = 10.7 passes."""
    bo = dict(d=0.75, group="A325", threads="N", n=3, s=3, lev=1.5, Fu=58)
    for W, ok in ((5.0, False), (4.0, True)):
        s = ws_more.stiffened_seat_sheet("SS1", "W21X68", 50, "a", W, 15, 0.375, 36, "s", 0.375, 0.0, 70, "W14X90 flange", 0.71, 65,
                                         [dict(case="D", P=2.0), dict(case="L", P=4.0)], COMB["LRFD"], "LRFD", bolted=bo)
        r = {x.check: x for x in s.rows}["Stiffener angle outstanding leg, W / t"]
        assert r.demand == pytest.approx(W / 0.375) and r.capacity == pytest.approx(0.45 * (29000 / 36) ** 0.5) and (r.status != "FLAG") == ok


def test_two_stiffeners_on_an_hss_face_by_hand(tmp_path):
    """Double stiffeners (AISC Design Guide 24 (2nd Ed.) Sect. 5.2.6: "single or double stiffeners"); no published procedure or example, checked
    by hand. The Example II.A-14 seat and reaction (LRFD R = 125.2 kips, W = 7, L = 15, ts = 5/8 in.) on an HSS16x16x5/8 (t design 0.581 in.,
    Fy 50, Fu 62 ksi), two stiffeners 6 in. centre to centre, no column load (Qf = 1); eta = 15 / 16 = 0.9375.
      Each stiffener R x 0.8 W / 2 = 350.6 kip-in.; Eq. 2-6 with beta = 0.625 / 16: 50 (0.581)^2 (15)[1 / 1.875 + 2 / (0.961)^0.5 + 0.9375 / 0.961]
      = 898.6 kip-in.; punching 0.75 (62)(0.581)(15)^2 / 5 = 1,215.7 kip-in.
      Both together as one plate g + ts = 6.625 in. wide: beta = 0.414; Mn = 1,201.6 kip-in. against R x 0.8 W = 701.1 kip-in.
      Flat = 16 - 4.5 (0.625) = 13.19 in. >= 6.625 in.
      Seat plate spanning 6 in. with R at mid-span: Mu = 125.2 (6) / 4 = 187.8 kip-in.; 0.9 (50)(7)(0.375)^2 / 4 = 11.07 kip-in. (Eq. F11-1): fails,
      as it should for a 3/8 in. plate bridging 6 in. under the whole reaction."""
    from strukit import shapes
    col = shapes.hss("HSS16X16X5/8")
    t = col["tdes"]
    hss = dict(shape="HSS16X16X5/8", face="B", Fy=50, Fu=62, Fy_source="ASTM A500 Gr. C", P=0.0, M=0.0, source="t", n=2, g=6.0)
    s = ws_more.stiffened_seat_sheet("SS3", "W21X68", 50, "ASTM A992", 7, 15, 0.625, 50, "ASTM A572 Gr. 50", 0.375, 0.3125, 70, "HSS16X16X5/8 face",
                                     t, 62, LOADS, COMB["LRFD"], "LRFD", hss=hss)
    h = s.conn["hss"]
    assert h["n"] == 2 and h["Mr1"] == pytest.approx(125.2 * 5.6 / 2) and h["Mn"] == pytest.approx(898.55, abs=0.05)
    assert h["Mn2"] == pytest.approx(1201.58, abs=0.05) and h["beta2"] == pytest.approx(6.625 / 16) and h["punch"] == pytest.approx(1215.74, abs=0.05)
    r = {x.check: x for x in s.rows}
    assert r["HSS face plastification under the stiffeners, each"].demand == pytest.approx(350.56)
    assert r["HSS face plastification, both stiffeners together"].capacity == pytest.approx(1201.58, abs=0.05)
    assert r["Stiffeners on the flat of the HSS face"].demand == pytest.approx(6.625) and r["Stiffeners on the flat of the HSS face"].capacity == pytest.approx(13.1875)
    sp = r["Seat plate bending between the stiffeners"]
    assert sp.demand == pytest.approx(187.8) and sp.capacity == pytest.approx(0.9 * 50 * 7 * 0.375 ** 2 / 4)
    assert r["Stiffener-to-support welds, each stiffener"].demand == pytest.approx(62.6)
    with pytest.raises(Exception):                                    # the pair must fit on the face
        ws_more.stiffened_seat_sheet("SS3", "W21X68", 50, "a", 7, 15, 0.625, 50, "s", 0.375, 0.3125, 70, "h", t, 62, LOADS, COMB["LRFD"], "LRFD",
                                     hss=dict(hss, g=15.5))
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="SS3", beam="W21X68", beam_Fy="50", beam_source="ASTM A992", W="7", L="15", ts="0.625", stiff_Fy="50", stiff_source="ASTM A572 Gr. 50",
             tseat="1.5", weld="0.3125", FEXX="70", hss_col="HSS16X16X5/8", hss_Fy="50", hss_Fu="62", hss_Fy_source="ASTM A500 Gr. C", hss_P="0", hss_M="0",
             hss_source="column takedown", hss_n="two", hss_g="6", top_t="0.25", top_leg="4", top_attach="welded along the toes only",
             loads=[dict(case="D", P="21", label=""), dict(case="L", P="62.5", label="")])
    proj = dict(job="t", name="t", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[])
    sc = calc.build("stiffened_seat", v, proj)[0]
    assert sc.conn["hss"]["n"] == 2 and sc.conn["hss"]["g"] == 6
    with pytest.raises(calc.Missing):
        calc.build("stiffened_seat", dict(v, hss_g=""), proj)
    calcsheet.simple_pdf(sc, str(tmp_path / "ss_hss2.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")
