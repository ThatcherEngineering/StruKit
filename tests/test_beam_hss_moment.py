"""Wide-flange beam to the face of an HSS column, moment connection: AISC Design Guide 24 (2nd Ed.) Example 6.3 (W16x57 directly welded to an
HSS10x10x1/2, Fy 50 ksi; column PD 65, PL 195 kips, MD 15, ML 45 kip-ft)."""
import pytest
from strukit.gui import calc

V = dict(mark="BHM1", beam="W16X57", beam_Fy="50", beam_source="ASTM A992", column="HSS10X10X1/2", col_Fy="50", col_source="ASTM A500 Grade C", face="",
         flanges="beam flanges welded directly to the face",
         loads=[dict(case="D", M="15", P="65", Mc="15", label=""), dict(case="L", M="45", P="195", Mc="45", label="")])
PROJ = dict(job="t", name="t", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")])


@pytest.mark.parametrize("method, fl, sw, U, Qf, yl, ps, cr, M", [
    ("LRFD", 73.1, 195, 0.875, 0.808, 69.4, 112, 307, 90.8),
    ("ASD", 48.7, 130, 0.973, 0.753, 43.1, 74.7, 191, 56.4)])
def test_design_guide_24_example_6_3(method, fl, sw, U, Qf, yl, ps, cr, M, tmp_path):
    s = calc.build("beam_hss_moment", V, dict(PROJ, method=method))[0]
    c = s.conn
    assert c["flat"] == pytest.approx(7.75) and c["Be"] == pytest.approx(2.15, abs=0.01) and c["a"] == pytest.approx(1.44) and c["beta"] == pytest.approx(0.712)
    assert c["R_fl"] == pytest.approx(fl, rel=0.005) and c["R_sw"] == pytest.approx(sw, rel=0.005)
    assert c["U"] == pytest.approx(U, abs=0.002) and c["Qf"] == pytest.approx(Qf, abs=0.002)
    assert c["yl"] == pytest.approx(yl, rel=0.006) and c["ceff"] == pytest.approx(3.31, abs=0.01) and c["R_ps"] == pytest.approx(ps, rel=0.006)
    assert c["cr"] == pytest.approx(cr, rel=0.006) and c["arm"] == pytest.approx(15.7, abs=0.02) and c["M_avail"] == pytest.approx(M, rel=0.006)
    assert len(s.rows) == 5 and s.rows[2].check.startswith("Plastification")
    from strukit import calcsheet
    calcsheet.simple_pdf(s, str(tmp_path / "bhm.pdf"), "Job", "AISC 360-22", "Nov 24, 2026")


def test_flange_plates_and_stops():
    pl = dict(V, flanges="flange plates welded to the face", bp="7", tp="0.75", plate_Fy="50", plate_source="ASTM A572 Grade 50")
    s = calc.build("beam_hss_moment", pl, dict(PROJ, method="LRFD"))[0]
    c = s.conn
    assert c["arm"] == pytest.approx(16.4 + 0.75) and c["a"] == pytest.approx(1.5)                       # plates on the outside of the flanges
    # by hand: Be = (10 / 21.5)(50 x 0.465 / (50 x 0.75)) x 7 = 2.019 in.; 0.95 x 50 x 2.019 x 0.75 = 71.9 kips
    assert c["Be"] == pytest.approx(2.019, abs=0.003) and c["R_fl"] == pytest.approx(71.9, abs=0.15)
    assert any("flange plate in tension" in t for t in s.not_checked)
    with pytest.raises(Exception, match="flat of the HSS face"):
        calc.build("beam_hss_moment", dict(pl, bp="9"), dict(PROJ, method="LRFD"))
    with pytest.raises(Exception):
        calc.build("beam_hss_moment", dict(pl, plate_source=""), dict(PROJ, method="LRFD"))
    with pytest.raises(Exception, match="past its strength"):
        calc.build("beam_hss_moment", dict(V, loads=[dict(case="D", M="15", P="900", Mc="0", label="")]), dict(PROJ, method="LRFD"))
    # Qf has a floor of 0.4 (Eq. K1-4): a heavily loaded column, U = 760 / (50 x 17.2) = 0.884 plus moment
    hv = calc.build("beam_hss_moment", dict(pl, bp="4", loads=[dict(case="D", M="5", P="630", Mc="10", label="")]), dict(PROJ, method="LRFD", combos_lrfd=[dict(expr="1.2D", source="t")]))[0]
    assert hv.conn["Qf"] == pytest.approx(0.4) and hv.conn["U"] > 0.9
    # a rectangular column: the H face is the wider one, with the other dimension as the side walls
    r = calc.build("beam_hss_moment", dict(V, column="HSS12X8X1/2", face="H", beam="W12X26"), dict(PROJ, method="LRFD"))[0]
    assert "connecting face 12 in. wide, side walls 8 in." in dict(r.info)["Column"]
