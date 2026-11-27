"""Foundation anchor bolts and plate washers on the shear wall screens (shearwall.anchor_bolts, ws_more.add_anchor_bolts)."""
import pytest

from strukit import shearwall as sw
from strukit.gui import calc

# NDS 2018 Table 12E (bolts, sawn lumber to concrete, 6 in. embedment), Z parallel to grain, lb: (G, side thickness, D, Z)
TABLE_12E = [(0.50, 1.5, 0.5, 650), (0.50, 1.5, 0.625, 930), (0.50, 1.5, 0.75, 1270), (0.50, 2.5, 0.625, 1180), (0.55, 3.5, 0.75, 1770),
             (0.43, 1.5, 0.625, 860), (0.42, 1.5, 0.5, 590), (0.49, 1.75, 0.75, 1310), (0.67, 1.5, 1.0, 2410), (0.46, 2.5, 0.875, 1860)]


@pytest.mark.parametrize("G,ts,D,Z", TABLE_12E)
def test_bolt_in_the_plate_matches_nds_table_12e(G, ts, D, Z):
    """The yield limit equations with Fe 7,500 psi concrete and 6 in. embedment reproduce NDS Table 12E (rounded there to 10 lb)."""
    a = sw.anchor_bolts(100.0, D, ts, G, "wind", "ASD")
    assert a["Z"] == pytest.approx(Z, abs=6)


def test_spacing_adjustments_and_plate_washer_by_hand():
    """5/8 in. bolt, 2x4 DF-L plate (G 0.50): Z = 928 lb (Table 12E 930). ASD wind: Z' = 1.6 x 928 = 1,485 lb; at 300 plf the
    largest spacing is 1,485 / 300 x 12 = 59.4 in. LRFD: Z' = 3.32 x 0.65 x 928 = 2,003 lb. Plate washer 3 x 3 centred on a 3.5 in.
    plate: 0.25 in. from the sheathed edge (1/2 in. limit, SDPWS 4.3.6.4.3, nominal shear over 400 plf); on a 5.5 in. plate 1.25 in.,
    a FLAG, unless the bolt is moved to 2 in. from the sheathed edge (0.5 in.)."""
    a = sw.anchor_bolts(300.0, 0.625, 1.5, 0.5, "wind", "ASD", 48, vn_side=670)
    assert a["Zp"] == pytest.approx(1.6 * a["Z"]) and a["s_max"] == pytest.approx(1.6 * a["Z"] / 300 * 12)
    assert a["rows"][0][1] == pytest.approx(1200) and a["gap"] == pytest.approx(0.25)
    assert sw.anchor_bolts(300.0, 0.625, 1.5, 0.5, "wind", "LRFD")["Zp"] == pytest.approx(3.32 * 0.65 * a["Z"])
    wide = sw.anchor_bolts(300.0, 0.625, 1.5, 0.5, "wind", "ASD", plate_w=5.5, vn_side=670)
    edge = [r for r in wide["rows"] if r[0].startswith("plate washer to")][0]
    assert edge[1] == pytest.approx(1.25) and edge[1] > edge[2]
    assert sw.anchor_bolts(300.0, 0.625, 1.5, 0.5, "wind", "ASD", plate_w=5.5, offset_in=2.0, vn_side=670)["gap"] == pytest.approx(0.5)
    low = sw.anchor_bolts(300.0, 0.625, 1.5, 0.5, "wind", "ASD", plate_w=5.5, vn_side=380)
    assert not any(r[0].startswith("plate washer to") for r in low["rows"])          # 400 plf or less: no edge limit
    thin = sw.anchor_bolts(300.0, 0.625, 1.5, 0.5, "wind", "ASD", washer_t=0.1875)
    assert [r for r in thin["rows"] if r[0] == "plate washer thickness"][0][2] == 0.1875
    with pytest.raises(sw.ShearWallError):
        sw.anchor_bolts(300.0, 0.6, 1.5, 0.5, "wind", "ASD")


BASE = dict(panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", G="0.5", G_source="DF-L, NDS Table 12.3.3A",
            load="wind", v_source="x", ab_d="5/8", ab_s="48", ab_sill_t="1.5", ab_sill_w="3.5")
PROJ = dict(job="t", name="t", method="ASD")


def test_on_the_three_wall_screens(tmp_path):
    sw_ = calc.build("shear_wall", dict(BASE, mark="SW1", blocking="blocked", h="9", lengths="8", V="2400"), PROJ)[0]
    r = {x.check: x for x in sw_.rows}
    assert r["anchor bolts, shear per bolt"].demand == pytest.approx(300 * 4)
    assert not any("anchor bolts and plate washers" in t for t in sw_.not_checked) and any("ACI 318-19 Chapter 17" in t for t in sw_.not_checked)
    ft = calc.build("ftao_wall", dict(BASE, mark="FT1", h="9", L1="4", Lo="5", L2="4", ho="4", sill="3", V="2000"), PROJ)[0]
    assert [x for x in ft.rows if x.check == "anchor bolts, shear per bolt"][0].demand == pytest.approx(ft.wall["vh"] * 4)
    pw = calc.build("perforated_wall", dict(BASE, mark="PW1", h="8", length="20", V="2000", openings=[dict(x="6", w="4", h="4", sill="3")]), PROJ)[0]
    assert [x for x in pw.rows if x.check == "anchor bolts, shear per bolt"][0].demand == pytest.approx(pw.wall.v_max * 4)
    assert any("4.3.6.4.2.1" in t for t in pw.not_checked)
    two = calc.build("shear_wall", dict(BASE, mark="SW2", blocking="blocked", h="9", lengths="8", V="2400", ab_sill_w="5.5", ab_washer="3 x 3 x 0.229"), PROJ)[0]
    assert [x for x in two.rows if x.check.startswith("plate washer to")][0].status == "FLAG"
    with pytest.raises(calc.Missing):
        calc.build("shear_wall", dict(BASE, mark="SW3", blocking="blocked", h="9", lengths="8", V="2400", ab_sill_t=""), PROJ)
    for k_, s_ in (("sw", sw_), ("ft", ft), ("pw", pw)):
        from strukit import calcsheet
        calcsheet.simple_pdf(s_, str(tmp_path / f"{k_}.pdf"), "Job", "SDPWS-2021", "Nov 26, 2026")


def test_anchor_bolt_in_the_concrete_by_hand():
    """5/8 in. F1554 Grade 36 headed bolt, hef 7 in., f'c 2,500 psi, centred in an 8 in. stem wall 24 in. deep, bolts at 48 in.
    (ACI 318-19 Chapter 17; no published sill-bolt example on file, checked by hand):
      Ase = pi/4 (0.625 - 0.9743/11)^2 = 0.2260 in2; phi Vsa = 0.65 x 0.6 x 0.2260 x 58,000 = 5,112 lb.
      Shear along the edge, ca1 = 4: AVco = 4.5 (4)^2 = 72, AVc = (6 + 6)(6) = 72 in2; le = min(7, 8 x 0.625) = 5 in.;
      Vb = min(7 (5/0.625)^0.2 (0.625)^0.5 (2500)^0.5 (4)^1.5, 9 (2500)^0.5 (4)^1.5) = min(3,355, 3,600) = 3,355 lb;
      Vcb = 2 x 3,355 = 6,710 (17.7.2.1(c)); phi = 0.70: 4,697 lb.
      Pryout: ANc = (10.5 + 10.5)(4 + 4) = 168, ANco = 9 (7)^2 = 441 in2; psi_ed,N = 0.7 + 0.3 x 4 / 10.5 = 0.8143;
      Nb = 24 (2500)^0.5 (7)^1.5 = 22,224 lb; Ncb = 6,894 lb; Vcp = 2 Ncb = 13,789; phi 0.70: 9,652 lb.
      ASD wind 300 plf at 48 in.: Vua = 300 x 4 / 0.6 = 2,000 lb."""
    from strukit import anchorage as A
    r = A.sill_anchor(0.625, "ASTM F1554 Grade 36", 7.0, 2500.0, 4.0, 8.0, 24.0, 48.0, 2000.0)
    m = {x[0]: x for x in r["modes"]}
    assert m["anchor bolt steel, shear"][2] == pytest.approx(0.65 * 0.6 * 0.2260 * 58000, rel=1e-3)
    assert r["Vcb"] == pytest.approx(6710, rel=2e-3) and m["anchor bolt concrete breakout, shear along the edge"][2] == pytest.approx(4697, rel=2e-3)
    assert r["Ncb"] == pytest.approx(6894, rel=2e-3) and m["anchor bolt pryout"][2] == pytest.approx(9652, rel=2e-3)
    h = A.sill_anchor(0.625, "ASTM F1554 Grade 36", 7.0, 2500.0, 4.0, 8.0, 24.0, 48.0, 2000.0, Nu=1000.0, hooked=True, eh=2.5)
    assert h["Np"] == pytest.approx(0.9 * 2500 * 2.5 * 0.625)                 # Eq. 17.6.3.2.2b
    with pytest.raises(A.AnchorageError):
        A.sill_anchor(0.625, "ASTM F1554 Grade 36", 7.0, 2500.0, 4.0, 8.0, 24.0, 48.0, 2000.0, Nu=1.0, hooked=True, eh=1.0)


def test_concrete_and_uplift_on_the_screens():
    """On the screens: ASD shear brought to strength level (wind / 0.6); seismic SDC C to F needs the overstrength factor;
    the perforated wall bottom plate uplift (SDPWS 4.3.6.4.2.1) by washer bearing (NDS 3.10.4, Cb = 3.375 / 3) and plate bending
    flatwise between the bolts (t s^2 / 8)."""
    con = dict(ab_fc="2500", ab_grade="ASTM F1554 Grade 36", ab_type="headed (heavy hex nut)", ab_hef="7", ab_edge="4", ab_fwidth="8", ab_fdepth="24")
    s_ = calc.build("shear_wall", dict(BASE, **con, mark="SW1", blocking="blocked", h="9", lengths="8", V="2400"), PROJ)[0]
    r = {x.check: x for x in s_.rows}
    assert r["anchor bolt steel, shear"].demand == pytest.approx(300 * 4 / 0.6)
    assert not any("ACI 318-19 Chapter 17" in t for t in s_.not_checked)
    seis = dict(BASE, **con, mark="SW2", blocking="blocked", h="9", lengths="8", V="2400", load="seismic", ab_sdc="C to F")
    with pytest.raises(Exception):
        calc.build("shear_wall", seis, PROJ)
    s2 = calc.build("shear_wall", dict(seis, ab_omega="3", ab_omega_source="ASCE 7-22 Table 12.2-1, A.15"), PROJ)[0]
    assert [x for x in s2.rows if x.check == "anchor bolt steel, shear"][0].demand == pytest.approx(300 * 4 / 0.7 * 3)
    pw = calc.build("perforated_wall", dict(BASE, **con, mark="PW1", h="8", length="20", V="2000", openings=[dict(x="6", w="4", h="4", sill="3")],
                                            ab_Fc_perp="625", ab_Fb="1485", ab_wood_source="DF-L No. 2, NDS Supplement Table 4A, CF 1.5, Cfu 1.1"), PROJ)[0]
    t = pw.wall.v_max
    r = {x.check: x for x in pw.rows}
    A_ = 9 - 3.141592653589793 * (0.6875) ** 2 / 4
    assert r["bottom plate uplift: washer bearing"].demand == pytest.approx(t * 4) and r["bottom plate uplift: washer bearing"].capacity == pytest.approx(625 * 1.125 * A_)
    assert r["bottom plate uplift: plate bending between bolts"].demand == pytest.approx(t / 12 * 48 ** 2 / 8 / (3.5 * 1.5 ** 2 / 6))
    assert r["anchor bolt steel, tension"].demand == pytest.approx(t * 4 / 0.6)
    assert not any("4.3.6.4.2.1" in x for x in pw.not_checked)


def test_sill_plate_exception_ibc_1905_1_8():
    """IBC 2021 Sect. 1905.1.8, exception 1 to ACI 318-19 17.10.6.2 (Zach 2026-11-27: apply it): 5/8 in. bolt, 7 in. embedment,
    1-3/4 in. from the edge, 15 diameters (9.375 in.) from the concrete end, 2x plate: breakout and pryout in shear are not computed,
    and for SDC C to F 17.10.6.3 is deemed satisfied (no overstrength). The bolt steel is still checked."""
    con = dict(ab_fc="2500", ab_grade="ASTM F1554 Grade 36", ab_type="headed (heavy hex nut)", ab_hef="7", ab_edge="1.75", ab_fwidth="8",
               ab_fdepth="24", ab_end="12")
    s_ = calc.build("shear_wall", dict(BASE, **con, mark="SW1", blocking="blocked", h="9", lengths="8", V="2400"), PROJ)[0]
    names = [x.check for x in s_.rows]
    assert "anchor bolt steel, shear" in names and "anchor bolt pryout" not in names
    assert not any(n.startswith("anchor bolt concrete breakout") for n in names) and all(x.status == "OK" for x in s_.rows)
    seis = calc.build("shear_wall", dict(BASE, **con, mark="SW2", blocking="blocked", h="9", lengths="8", V="2400", load="seismic", ab_sdc="C to F"), PROJ)[0]
    assert [x for x in seis.rows if x.check == "anchor bolt steel, shear"][0].demand == pytest.approx(300 * 4 / 0.7)
    near = calc.build("shear_wall", dict(BASE, **dict(con, ab_end="8"), mark="SW3", blocking="blocked", h="9", lengths="8", V="2400"), PROJ)[0]
    assert "anchor bolt pryout" in [x.check for x in near.rows]            # 8 in. < 15 x 5/8: the exception does not apply
    big = calc.build("shear_wall", dict(BASE, **con, mark="SW4", blocking="blocked", h="9", lengths="8", V="2400", ab_d="3/4"), PROJ)[0]
    assert "anchor bolt pryout" in [x.check for x in big.rows]
