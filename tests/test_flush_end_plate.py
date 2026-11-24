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
