"""Two-bolt flush unstiffened end-plate moment connection: AISC Design Guide 39 Example 5.2-1 (W18x35 beam to the top of a W12x35 column, 7 x 9/16 in.
Grade 50 end plate, 3/4 in. A325-N bolts, g = 3-1/2, pfi = 1-1/2; 1/4 in. flange and 3/16 in. web fillets; cap plate 1/2 x 6-1/2 with a 1/2 in. fillet to
the flange and 1/4 in. fillets to the web; Mu 800 kip-in., Tu 3.30 kips, Vu 25.8 kips; Ma 533, Ta 2.20, Va 17.2)."""
import pytest
from strukit.gui import calc

V = dict(mark="FEP1", beam="W18X35", beam_Fy="50", beam_Fu="65", column="W12X35", col_Fy="50", col_Fu="65", steel_source="ASTM A992", bp="7", tp="0.5625", plate_Fy="50", plate_Fu="65",
         plate_source="ASTM A572 Grade 50", d="0.75", group="A325", threads="N", g="3.5", pfi="1.5", w_flange="0.25", w_web="0.1875", below="0.25", tcap="0.5", bcp="6.5",
         w_cap_flange="0.5", w_cap_web="0.25", FEXX="70")
PROJ = dict(job="t", name="t", combos_lrfd=[dict(expr="1.0D", source="t")], combos_asd=[dict(expr="1.0D", source="t")])
L = lambda M, T, Vv: [dict(case="D", M=str(M / 12), T=str(T), V=str(Vv), label="")]


@pytest.mark.parametrize("method, loads, Meq, treq, phiVn, Tcalc, Tf, Rwf, Tyw, Twd, Rwt, Rwv, Rvr, Rcf, Rcw, Rcr, Mcf, Pfl, Rwy, Rwc, Rpz", [
    ("LRFD", L(800, 3.30, 25.8), 829, 0.519, 35.9, 48.0, 76.5, 87.8, 102, 67.8, 93.8, 70.4, 74.0, 83.3, 128, 101, 1110, 46.3, 99.9, 101, 102),
    ("ASD", L(533, 2.20, 17.2), 552, 0.520, 23.9, 32.0, 51.0, 58.5, 67.7, 45.2, 62.5, 47.0, 49.3, 55.5, 85.0, 67.0, 737, 30.9, 66.6, 67.5, 67.7)])
def test_design_guide_39_example_5_2_1(method, loads, Meq, treq, phiVn, Tcalc, Tf, Rwf, Tyw, Twd, Rwt, Rwv, Rvr, Rcf, Rcw, Rcr, Mcf, Pfl, Rwy, Rwc, Rpz):
    s, kind, _ = calc.build("flush_end_plate", dict(V, loads=loads), dict(PROJ, method=method))
    e = s.ep
    A = pytest.approx
    lr = method == "LRFD"
    av = lambda x, phi, om: phi * x if lr else x / om
    assert e["h1"] == A(15.6, abs=0.05) and e["Meq"] == A(Meq, rel=0.002) and e["d_req"] == A(0.708, abs=0.003)
    assert e["s"] == A(2.47, abs=0.005) and e["Yp"] == A(93.9, rel=0.004) and e["t_req"] == A(treq, abs=0.002)
    assert e["Rbt"] == A(23.9, abs=0.06) and e["Rbrg"] == A(60.8, abs=0.1) and av(e["Vn"], 0.75, 2.0) == A(phiVn, abs=0.15)
    assert e["Tcalc"] == A(Tcalc, abs=0.1) and e["Tyf"] == A(128, rel=0.005) and e["Tf"] == A(Tf, abs=0.1)
    assert e["lwf"] == A(10.5) and e["Rwf"] == A(Rwf, rel=0.006) and e["lwt"] == A(7.5) and av(e["Tyw"], 0.9, 1.67) == A(Tyw, rel=0.008) and e["Twd"] == A(Twd, rel=0.006)
    assert e["Rwt"] == A(Rwt, rel=0.006) and e["lwv"] == A(8.43, abs=0.006) and e["Rwv"] == A(Rwv, rel=0.006) and e["Rvr"] == A(Rvr, rel=0.006)
    assert e["Rcf"] == A(Rcf, rel=0.006) and e["Rcw"] == A(Rcw, rel=0.006) and e["Rcr"] == A(Rcr, rel=0.008)
    assert e["pcp"] == A(1.43, abs=0.006) and e["sc"] == A(2.40, abs=0.006) and e["Yc"] == A(91.2, rel=0.006) and e["Mcf"] == A(Mcf, rel=0.008)
    assert e["Pfl"] == A(Pfl, abs=0.1) and e["lb"] == A(1.74, abs=0.005) and e["Rwy"] == A(Rwy, rel=0.004) and e["Rwc"] == A(Rwc, rel=0.008) and e["Rpz"] == A(Rpz, rel=0.008)
    assert s.ok and len(s.rows) == 16


def test_flush_end_plate_flags_and_stops():
    P = dict(PROJ, method="LRFD")
    thin = calc.build("flush_end_plate", dict(V, tp="0.5", loads=L(800, 3.3, 25.8)), P)[0]
    assert next(r for r in thin.rows if r.check == "End plate thickness").status == "FLAG"
    small = calc.build("flush_end_plate", dict(V, d="0.625", loads=L(800, 3.3, 25.8)), P)[0]
    assert next(r for r in small.rows if r.check == "Bolt diameter").status == "FLAG"
    with pytest.raises(Exception, match="gage"):
        calc.build("flush_end_plate", dict(V, g="6.5", loads=L(800, 3.3, 25.8)), P)
    with pytest.raises(Exception, match="shallower than the column"):
        calc.build("flush_end_plate", dict(V, beam="W10X33", loads=L(300, 0, 10)), P)


def test_flush_end_plate_takes_runs_and_a_frame_beam_end_gives_them():
    runs = [dict(name="run A", M=str(800 / 12), T="3.30", V="25.8")]
    s = calc.build("flush_end_plate", dict(V, loads=[], runs=runs, loads_from="forces at the left end of beam BM"), dict(PROJ, method="LRFD"))[0]
    assert s.ep["Meq"] == pytest.approx(829, rel=0.002) and s.ok and "left end of beam BM" in s.combo_lines[0][0]
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import test_model
    proj, ms = test_model._portal(base="fixed")
    got = calc.frame_beam_end(proj, ms, "BM")
    assert got["method"] == "LRFD" and set(got["ends"]) == {"left", "right"} and got["ends"]["left"]
    run = calc.model_frame_sway(proj, ms)
    b = run["beams"][0]
    col = {c["mark"]: c for c in run["columns"]}
    top = max(max(r["M"] for r in got["ends"]["left"]), max(r["M"] for r in got["ends"]["right"]))
    assert top == pytest.approx(max(col["CL"]["Ms"], col["CR"]["Ms"]) / 12, rel=0.02)          # the beam end moment is the column top moment at a two-member joint
    assert max(r["V"] for r in got["ends"]["left"]) == pytest.approx(b["V"], rel=0.05)


V4 = dict(mark="FEP2", beam="W18X35", beam_Fy="50", beam_Fu="65", n_rows="2", pb="3", col_side="beam side only", steel_source="ASTM A992", bp="6", tp="0.75", plate_Fy="50", plate_Fu="65",
          plate_source="ASTM A572 Grade 50", d="0.75", group="A325", threads="N", g="3", pfi="1.5", w_flange="0.3125", w_web="0.1875", below="0.25", FEXX="70")


@pytest.mark.parametrize("method, M, Vv, treq, Tf, Rwf, Tyw, Twd, Rwt, Rwv, Rvr", [
    ("LRFD", 1500, 25.8, 0.634, 86.8, 110, 142, 94.8, 131, 53.0, 55.7), ("ASD", 1000, 17.2, 0.635, 57.9, 73.0, 94.6, 63.2, 87.5, 35.4, 37.2)])
def test_design_guide_39_example_5_2_2_four_bolt_flush(method, M, Vv, treq, Tf, Rwf, Tyw, Twd, Rwt, Rwv, Rvr):
    """AISC Design Guide 39 Example 5.2-2: W18x35, 6 x 3/4 in. end plate, four 3/4 in. A325 tension bolts (g = 3, pfi = 1-1/2, pb = 3), 5/16 in. flange
    and 3/16 in. web fillets; Mu 1,500 kip-in., Vu 25.8 kips; beam side only."""
    s = calc.build("flush_end_plate", dict(V4, loads=L(M, 0, Vv)), dict(PROJ, method=method))[0]
    e, A = s.ep, pytest.approx
    av = lambda x, phi, om: phi * x if method == "LRFD" else x / om
    assert e["h1"] == A(15.6, abs=0.05) and e["h2"] == A(12.6, abs=0.05) and e["d_req"] == A(0.708, abs=0.004)
    assert e["s"] == A(2.12, abs=0.005) and e["Yp"] == A(114, rel=0.006) and e["t_req"] == A(treq, abs=0.003)
    assert e["Tf"] == A(Tf, abs=0.1) and e["Rwf"] == A(Rwf, rel=0.008) and e["lwt"] == A(10.5) and av(e["Tyw"], 0.9, 1.67) == A(Tyw, rel=0.008)
    assert e["Twd"] == A(Twd, rel=0.006) and e["Rwt"] == A(Rwt, rel=0.008) and e["lwv"] == A(6.35, abs=0.006) and e["Rwv"] == A(Rwv, rel=0.006) and e["Rvr"] == A(Rvr, rel=0.006)
    assert s.ok and len(s.rows) == 8 and s.title.startswith("Four-Bolt")
    with pytest.raises(Exception, match="two-bolt connection"):
        calc.build("flush_end_plate", dict(V, n_rows="2", pb="3", loads=L(800, 0, 20)), dict(PROJ, method=method))


@pytest.mark.parametrize("method, M, T, Vv, Meq, treq, Vp, Rpy, Rpr, phiVn, Tf, Rwf, Tw, Tyw, Twd, Rwt, Rwv, Rvr", [
    ("LRFD", 2510, 11.0, 33.8, 2640, 0.589, 55.9, 150, 114, 71.7, 112, 132, 56.0, 87.2, 58.1, 96.8, 96.8, 84.8),
    ("ASD", 1670, 7.30, 22.5, 1760, 0.590, 37.2, 100, 76.0, 47.8, 74.3, 88.0, 37.2, 58.0, 38.8, 64.5, 64.5, 56.5)])
def test_design_guide_39_example_5_3_1_four_bolt_extended_beam_side(method, M, T, Vv, Meq, treq, Vp, Rpy, Rpr, phiVn, Tf, Rwf, Tw, Tyw, Twd, Rwt, Rwv, Rvr):
    """AISC Design Guide 39 Example 5.3-1, beam side: built-up rafter d 24, bf 8, tf 3/8, tw 1/4 in.; 8 x 5/8 in. Grade 50 end plate; 3/4 in. A325-N bolts,
    g = 3, pfi = 1-3/4, pfo = 2-1/2 in.; 1/4 in. flange and 3/16 in. web fillets; four bolts at the compression flange for shear."""
    from strukit import ws_more
    s = ws_more.flush_end_plate_sheet("FEP3", dict(d=24.0, bf=8.0, tf=0.375, tw=0.25, name="built-up rafter"), 50, 65, "", None, None, "ASTM A572 Grade 50", 8, 0.625, 50, 65,
                                      "ASTM A572 Grade 50", 0.75, "A325", "N", 3, 1.75, 0.25, 0.1875, 0.25, None, None, None, None, 70, [], [], method,
                                      runs=[dict(name="example", M=M / 12, T=T, V=Vv)], col_side=False, extended=True, pfo=2.5, n_shear=4)
    e, A = s.ep, pytest.approx
    av = lambda x, phi, om: phi * x if method == "LRFD" else x / om
    assert e["h1"] == A(26.3, abs=0.02) and e["h2"] == A(21.7, abs=0.02) and e["Meq"] == A(Meq, rel=0.003) and e["d_req"] == A(0.720, abs=0.003)
    assert e["s"] == A(2.45, abs=0.005) and e["Yp"] == A(186, rel=0.004) and e["t_req"] == A(treq, abs=0.003)
    assert e["Vp"] == A(Vp, abs=0.15) and e["Rpy"] == A(Rpy, rel=0.004) and e["Rpr"] == A(Rpr, rel=0.008) and av(e["Vn"], 0.75, 2.0) == A(phiVn, abs=0.25)
    assert e["Tf"] == A(Tf, rel=0.006) and e["Rwf"] == A(Rwf, rel=0.01) and e["Tw"] == A(Tw, rel=0.006) and av(e["Tyw"], 0.9, 1.67) == A(Tyw, rel=0.006) and e["Twd"] == A(Twd, rel=0.006)
    assert e["lwt"] == A(7.75) and e["Rwt"] == A(Rwt, rel=0.008) and e["lwv"] == A(11.6, abs=0.03) and e["Rwv"] == A(Rwv, rel=0.008) and e["Rvr"] == A(Rvr, rel=0.008)
    assert s.ok and len(s.rows) == 10 and s.title.startswith("Four-Bolt Extended")


def test_extended_end_plate_on_the_screen():
    v = dict(V4, mark="FEP4", config="extended, four bolts (two outside and two inside the tension flange; beam side only)", n_rows="", pb="", pfo="1.5", n_shear="2", tp="0.625")
    s = calc.build("flush_end_plate", dict(v, loads=L(1500, 0, 25.8)), dict(PROJ, method="LRFD"))[0]
    assert s.title.startswith("Four-Bolt Extended") and any(r.check == "Extended plate, shear rupture" for r in s.rows)
    with pytest.raises(calc.Missing):
        calc.build("flush_end_plate", dict(v, pfo="", loads=L(1500, 0, 25.8)), dict(PROJ, method="LRFD"))


def test_extended_column_side_design_guide_39_example_5_3_2():
    """Column side of a four-bolt extended end plate on a continuous W14x99, AISC Design Guide 39 Example 5.3-2 (W24x84 beam, g 5-3/4 in.,
    pfo 2-3/4, pfi 2, tp 1 in., Mu 7,620 kip-in., Tu 20.4 kips; partial-depth 1/2 x 6 in. stiffeners, 6-1/2 in. long, 1-3/8 in. clip, 3/8 in.
    fillets to the flange, 1/4 in. to the web; 3/8 in. doubler). Published: Ycu 202 in., Rn,cu 263 (phi 237) against 1.10 x 337 = 371 kips;
    Ycs 321 in. (bcf,eff 13.5 in.), Rn,cs 418 (phi 376); Tu,stiff 100 kips; Anet 4.63 in2, Pn 232 (phi 209); flange welds 309 (phi 232);
    web welds 152 (phi 114); panel zone 366 (phi 329) kips. The beam-side end plate of the example is stiffened (4ES); the beam side here is
    the unstiffened 4E, so only the column side is compared."""
    from strukit.ws_more import flush_end_plate_sheet
    from strukit.ws_steel_beam import Combo
    lr = [Combo("LRFD", {"M": 1.0}, "t")]
    stiff = dict(ts=0.5, bs=6.0, clip=1.375, ls=6.5, w_f=0.375, w_w=0.25, Fy=50.0)
    s = flush_end_plate_sheet("EP", "W24X84", 50, 65, "W14X99", 50, 65, "ASTM A992", 9.0, 1.0, 50, 65, "A572 Gr. 50", 1.125, "A490", "N", 5.75, 2.0,
                              0.5, 0.25, 1.5, None, None, None, None, 70, [], lr, "LRFD", runs=[dict(name="LRFD", M=7620 / 12, T=20.4, V=45.8)],
                              extended=True, pfo=2.75, col_side=True, col_cfg="stiffened", stiff=stiff, tdp=0.375, Vc=19.6)
    c = s.ep["col"]
    assert c["Ff"] == pytest.approx(337, abs=0.5) and c["Ycu"] == pytest.approx(202, rel=0.003) and c["Rcu"] == pytest.approx(237, rel=0.005)
    assert c["bcf_eff"] == pytest.approx(13.5, abs=0.02) and c["Ycs"] == pytest.approx(321, rel=0.004) and c["Rcs"] == pytest.approx(376, rel=0.005)
    assert c["T_st"] == pytest.approx(100, abs=1.0)
    assert c["Anet"] == pytest.approx(4.63, abs=0.01) and 0.9 * c["Pst"] == pytest.approx(209, rel=0.005)
    assert c["Rwsf"] == pytest.approx(232, rel=0.005) and c["Rwsw"] == pytest.approx(114, rel=0.005)
    assert c["Rpz"] == pytest.approx(329, rel=0.005)
    rows = {r.check: r for r in s.rows}
    assert rows["Column flange flexure (stiffened)"].demand == pytest.approx(1.10 * c["Ff"]) and rows["Column flange flexure (stiffened)"].status == "OK"
    # web yielding at the tension flange: Eq. 3-46 with lb = tbf + 2w + 2tp (the example's flanges are not fillet welded: lb = tbf + 2tp, 268 kips)
    assert c["Rwy_t"] == pytest.approx((6 * 1.38 + 0.77 + 2 * 0.5 + 2.0) * 50 * 0.485, rel=1e-3)
    # unstiffened, the same column fails flange flexure (237 < 371): flagged, and stiffeners are listed as not checked
    u = flush_end_plate_sheet("EP", "W24X84", 50, 65, "W14X99", 50, 65, "ASTM A992", 9.0, 1.0, 50, 65, "A572 Gr. 50", 1.125, "A490", "N", 5.75, 2.0,
                              0.5, 0.25, 1.5, None, None, None, None, 70, [], lr, "LRFD", runs=[dict(name="LRFD", M=7620 / 12, T=20.4, V=45.8)],
                              extended=True, pfo=2.75, col_side=True, col_cfg="continuous")
    ur = {r.check: r for r in u.rows}
    assert ur["Column flange flexure (unstiffened)"].status != "OK" and any("stiffeners" in t for t in u.not_checked)


def test_extended_column_top_unstiffened_and_with_cap_plate():
    """Four-bolt extended end plate at a column top: Design Guide 39 Table A-2(d) (unstiffened) and A-2(e) (cap plate), Ct = 0.5 in Eq. 3-46
    when the tension flange is within a column depth of the top (Sect. 3.7.6). W24x84 to W14x99 as Example 5.3-2, de = 3 in. No published
    example of these two cases: checked against the table's formulas by hand."""
    import math
    from strukit.ws_more import flush_end_plate_sheet
    from strukit.ws_steel_beam import Combo
    lr = [Combo("LRFD", {"M": 1.0}, "t")]
    run = [dict(name="LRFD", M=300.0, T=0.0, V=40.0)]
    base = ("EP", "W24X84", 50, 65, "W14X99", 50, 65, "ASTM A992", 9.0, 1.0, 50, 65, "A572 Gr. 50", 1.125, "A490", "N", 5.75, 2.0, 0.5, 0.25, 1.5)
    u = flush_end_plate_sheet(*base, None, None, None, None, 70, [], lr, "LRFD", runs=run, extended=True, pfo=2.75, col_side=True, col_cfg="top", de=3.0)
    c = u.ep["col"]
    bcf, g, tbf, db = 14.6, 5.75, 0.77, 24.1
    s = 0.5 * math.sqrt(bcf * g)
    cc = 2.75 + tbf + 2.0
    h1, h2 = db - tbf / 2 + 2.75, db - tbf - 2.0 - tbf / 2
    Yd = bcf / 2 * (h2 / s - 0.5) + 2 / g * (h1 * (3.0 + 0.75 * cc) + h2 * (s + 0.25 * cc)) + 0.75 * g
    assert c["Ycu"] == pytest.approx(Yd, rel=2e-3) and c["Ct_t"] == 0.5
    assert c["Rwy_t"] == pytest.approx((6 * 0.5 * 1.38 + tbf + 2 * 0.5 + 2 * 1.0) * 50 * 0.485, rel=1e-3)
    k = flush_end_plate_sheet(*base, 0.75, 14.6, 0.375, 0.3125, 70, [], lr, "LRFD", runs=run, extended=True, pfo=2.75, col_side=True, col_cfg="top_cap", de=3.0)
    ck = k.ep["col"]
    pcp = min(3.0 - 0.75, s)
    Ye = bcf / 2 * (h1 / pcp + h2 / s) + 2 / g * (h1 * (pcp + 0.75 * cc) + h2 * (s + 0.25 * cc)) + g / 2
    assert ck["Yce"] == pytest.approx(Ye, rel=2e-3) and ck["Yce"] > c["Ycu"]
    assert ck["T_cap"] == pytest.approx(max(ck["Ff"] - min(ck["Rcu"], ck["Rwy_t"]), 0.0))
    assert {r.check for r in k.rows} >= {"Column flange flexure (cap plate)", "Cap plate yielding (as a stiffener)", "Cap plate to column flange weld"}


def test_extended_column_top_stiffened_between_the_bolts(tmp_path):
    """Four-bolt extended end plate at a column top with stiffeners at the beam flanges: Design Guide 39 Table A-2(f) (h1 (de + pso) in the
    second term, the column top de above the outer bolts), Ct = 0.5. No published example: by hand against the table's formula, and the
    stiffened top is stronger than the unstiffened top (A-2(d))."""
    import math
    from strukit.ws_more import flush_end_plate_sheet
    from strukit.ws_steel_beam import Combo
    from strukit import calcsheet
    lr = [Combo("LRFD", {"M": 1.0}, "t")]
    run = [dict(name="LRFD", M=300.0, T=0.0, V=40.0)]
    base = ("EP", "W24X84", 50, 65, "W14X99", 50, 65, "ASTM A992", 9.0, 1.0, 50, 65, "A572 Gr. 50", 1.125, "A490", "N", 5.75, 2.0, 0.5, 0.25, 1.5)
    stiff = dict(ts=0.5, bs=6.0, clip=1.375, ls=6.5, w_f=0.375, w_w=0.25, Fy=50.0)
    t = flush_end_plate_sheet(*base, None, None, None, None, 70, [], lr, "LRFD", runs=run, extended=True, pfo=2.75, col_side=True, col_cfg="top_stiff",
                              stiff=stiff, de=3.0)
    u = flush_end_plate_sheet(*base, None, None, None, None, 70, [], lr, "LRFD", runs=run, extended=True, pfo=2.75, col_side=True, col_cfg="top", de=3.0)
    c = t.ep["col"]
    g, tbf, db = 5.75, 0.77, 24.1
    bce = c["bcf_eff"]
    s = 0.5 * math.sqrt(bce * g)
    pso, psi = min(2.75, s), min(2.0, s)
    h1, h2 = db - tbf / 2 + 2.75, db - tbf - 2.0 - tbf / 2
    Yf = bce / 2 * (h1 / pso + h2 * (1 / psi + 1 / s) - 0.5) + 2 / g * (h1 * (3.0 + pso) + h2 * (s + psi)) + g / 4
    assert c["Ycs"] == pytest.approx(Yf, rel=2e-3) and c["Ycs"] > u.ep["col"]["Ycu"] and c["Ct_t"] == 0.5
    assert any("Table A-2(f)" in r.source for r in t.rows)
    calcsheet.simple_pdf(t, str(tmp_path / "ts.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")
