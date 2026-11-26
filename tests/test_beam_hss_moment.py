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


def test_bolted_flange_plates_on_the_sheet(tmp_path):
    """Flange plates bolted to the beam flange: the sheet carries the Example II.B-1 checks (tests/test_flange_plate.py) for the largest moment."""
    v = dict(V, beam="W12X26", column="HSS8X8X1/2", col_Fy="46", flanges="flange plates welded to the face", bp="5.5", tp="0.5", plate_Fy="36",
             plate_source="ASTM A36", plate_Fu="58", beam_Fu="65", fd="0.75", fgroup="A325", fthreads="N", fn="3", fs="3", fg="3", flev_p="1.5",
             flev_b="1.5", fa1="2", fweld="0.3125", fFEXX="70", loads=[dict(case="D", M="3", P="4", Mc="6", label=""), dict(case="L", M="9", P="12", Mc="20", label="")])
    s = calc.build("beam_hss_moment", v, dict(PROJ, method="LRFD"))[0]
    names = [r.check for r in s.rows]
    assert names[5:] == ["Bolts, flange plate to beam flange", "Flange plate tensile yielding", "Flange plate tensile rupture",
                         "Flange plate block shear, outer blocks", "Flange plate block shear, through one row", "Beam flange block shear",
                         "Beam flexure at the flange bolt holes", "Compression flange plate", "Fillet welds, flange plate to the HSS face"]
    fp = s.conn["fp"]
    Mu = (1.2 * 3 + 1.6 * 9) * 12
    assert fp["Pb"] == pytest.approx(Mu / 12.2) and fp["Pp"] == pytest.approx(Mu / 12.7)
    # by hand: 3/4 in. A325-N bolt 0.75 x 54 x 0.4418 = 17.9 kips; plate end bolt tearout 0.75 x 1.2 x (1.5 - 0.40625) x 0.5 x 58 = 28.5 kips
    assert fp["rv"] == pytest.approx(0.75 * 54 * 0.4418, rel=0.001) and fp["R_bolts"] == pytest.approx(6 * fp["rv"], rel=0.001)
    assert fp["R_ty"] == pytest.approx(0.9 * 36 * 5.5 * 0.5) and fp["An"] == pytest.approx((5.5 - 2 * 0.875) * 0.5)
    assert "the weld of the flange plate to the HSS face" not in s.not_checked
    with pytest.raises(Exception):                                      # bolts given, a required bolt dimension left blank
        calc.build("beam_hss_moment", dict(v, fg=""), dict(PROJ, method="LRFD"))
    from strukit import calcsheet
    calcsheet.simple_pdf(s, str(tmp_path / "bhm_plates.pdf"), "Job", "AISC 360-22", "Nov 25, 2026")


def test_joint_loads_from_the_frame():
    """The eave portal carport (bent quick start, W12X26 eave beams in bays 3 and 6): the fill takes the beam end moment and the column's load
    and moment at the joint from the same run, and finds the column at that end."""
    import json, os
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "carport_eave_portals.strukit")))
    g = calc.frame_beam_hss(d["project"], d["members"], "E3A", "left")
    assert g["column"] == "C3A" and g["face"] == "B" and g["column_shape"] == "HSS8X8X1/2" and g["rows"]
    top = max(g["rows"], key=lambda r: r["M"])
    assert top["M"] > 5 and top["Mc"] == pytest.approx(top["M"], rel=0.05)     # a corner joint: the column moment balances the beam moment
    assert calc.frame_beam_hss(d["project"], d["members"], "E3B", "right")["column"] == "C4B"
    v = dict(V, beam="W12X26", column=g["column_shape"], face=g["face"], flanges="flange plates welded to the face", bp="5.5", tp="0.5",
             plate_Fy="36", plate_source="ASTM A36", loads=[], runs=[dict(name=r["name"], M=f"{r['M']:.2f}", P=f"{r['P']:.2f}", Mc=f"{r['Mc']:.2f}") for r in g["rows"]])
    s = calc.build("beam_hss_moment", v, d["project"])[0]
    assert s.ok


def test_welded_flange_plates_on_the_sheet(tmp_path):
    """Flange plates fillet welded to the beam flange (narrower than the flange, welds along both plate edges and across the end): every
    value by hand from AISC 360-22 Eq. J2-4, J2-6 (Sect. J2.4(a) and (b)), J4-1 to J4-4, Table D3.1 Case 4 and Sect. J4.4."""
    v = dict(V, beam="W12X26", column="HSS8X8X1/2", col_Fy="46", flanges="flange plates welded to the face", bp="5.5", tp="0.5", plate_Fy="36",
             plate_source="ASTM A36", plate_Fu="58", beam_Fu="65", fbw="0.25", fLw="11", fend="yes", fwa1="1", fweld="0.3125", fFEXX="70",
             loads=[dict(case="D", M="3", P="4", Mc="6", label=""), dict(case="L", M="9", P="12", Mc="20", label="")])
    s = calc.build("beam_hss_moment", v, dict(PROJ, method="LRFD"))[0]
    fw = s.conn["fw"]
    Mu = (1.2 * 3 + 1.6 * 9) * 12
    assert fw["Pw"] == pytest.approx(Mu / 12.2) and fw["Pp"] == pytest.approx(Mu / 12.7)
    q = 0.6 * 70 * 0.7071 * 0.25                                         # 7.42 kip/in nominal
    Rl, Rt = q * 22, q * 5.5
    assert fw["Rnwl"] == pytest.approx(Rl) and fw["Rnwt"] == pytest.approx(Rt)
    assert fw["R_w"] == pytest.approx(0.75 * max(Rl + Rt, 0.85 * Rl + 1.5 * Rt))
    assert fw["bm_plate"] == pytest.approx(min(1.0 * 0.6 * 36 * 22 * 0.5, 0.75 * 0.6 * 58 * 22 * 0.5))
    assert fw["bm_beam"] == pytest.approx(min(0.6 * 50 * 22 * 0.38, 0.75 * 0.6 * 65 * 22 * 0.38))
    assert fw["U"] == 1.0 and fw["R_tr"] == pytest.approx(0.75 * 58 * 2.75) and fw["R_ty"] == pytest.approx(0.9 * 36 * 2.75)
    assert fw["Lc_r"] == pytest.approx(0.65 * 1 / (0.5 / 12 ** 0.5)) and fw["R_c"] == pytest.approx(0.9 * 36 * 2.75)   # K L / r under 25: Eq. J4-6
    assert fw["narrow"] and fw["wmax"] == pytest.approx(0.4375) and fw["wmin"] == pytest.approx(0.1875)
    names = [r.check for r in s.rows]
    assert "Fillet welds, flange plate to beam flange" in names and "Fillet welds, flange plate to the HSS face" in names
    assert "Flange Welds" in dict(s.info) and not any("bolts or welds to the beam flange" in t for t in s.not_checked)
    # shorter welds lower U (Case 4): l = 9 in., w = 5.5 in., 1.5 w <= l < 2 w gives U = 0.87; no transverse weld
    s2 = calc.build("beam_hss_moment", dict(v, fLw="9", fend="no"), dict(PROJ, method="LRFD"))[0]
    assert s2.conn["fw"]["U"] == 0.87 and s2.conn["fw"]["R_w"] == pytest.approx(0.75 * q * 18)
    with pytest.raises(Exception, match="shorter than the distance"):
        calc.build("beam_hss_moment", dict(v, fLw="5"), dict(PROJ, method="LRFD"))
    with pytest.raises(Exception, match="bolted or welded"):
        calc.build("beam_hss_moment", dict(v, fd="0.75", fgroup="A325", fthreads="N", fn="3", fs="3", fg="3", flev_p="1.5", flev_b="1.5", fa1="2"),
                   dict(PROJ, method="LRFD"))
    from strukit import calcsheet
    calcsheet.simple_pdf(s, str(tmp_path / "bhm_welded.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")
    calcsheet.simple_pdf(s2, str(tmp_path / "bhm_welded2.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")


def test_column_moment_about_the_other_axis():
    """A portal-bay knee: the eave beam frames into one face and the rafter makes the column bend about its other axis. The frame fill takes
    that moment too (same run), and the utilization U of Eq. K1-6 adds it: U = P / (Fc A) + M / (Fc S) + M2 / (Fc S2)."""
    import json, os
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "carport_eave_portals.strukit")))
    g = calc.frame_beam_hss(d["project"], d["members"], "E3A", "left")
    assert all("Mc2" in r for r in g["rows"]) and max(r["Mc2"] for r in g["rows"]) > 1.0
    base = dict(V, loads=[dict(case="D", M="15", P="65", Mc="15", label=""), dict(case="L", M="45", P="195", Mc="45", label="")])
    two = dict(V, loads=[dict(case="D", M="15", P="65", Mc="15", Mc2="5", label=""), dict(case="L", M="45", P="195", Mc="45", Mc2="0", label="")])
    a = calc.build("beam_hss_moment", base, dict(PROJ, method="LRFD"))[0].conn
    b = calc.build("beam_hss_moment", two, dict(PROJ, method="LRFD"))[0].conn
    from strukit import shapes
    S2 = shapes.hss("HSS10X10X1/2")["Sy"]
    assert b["U"] == pytest.approx(a["U"] + 1.2 * 5 * 12 / (50 * S2), rel=1e-6) and b["Qf"] < a["Qf"]
