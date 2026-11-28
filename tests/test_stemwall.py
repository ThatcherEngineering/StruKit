"""Stem wall (strukit.stemwall): checked by hand against ACI 318-19. No published worked example of a stem wall or grade beam over
voids is on file (logged); every value below is worked by hand from the provisions named."""
import math

import pytest

from strukit import stemwall as sw

A = pytest.approx
ST = [("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "ASCE/SEI 7-22 2.3.1"), ("1.4D", {"D": 1.4}, "ASCE/SEI 7-22 2.3.1"),
      ("0.9D + 1.6H", {"D": 0.9, "H": 1.6}, "ASCE/SEI 7-22 2.3.6")]
SE = [("D + L", {"D": 1.0, "L": 1.0}, "ASCE/SEI 7-22 2.4.1")]
WALL = dict(bar_v=4, s_v=16, bar_h=4, s_h=12)


def rows(r):
    return {c.name: c for c in r.checks}


def test_grade_beam_simple_span_by_hand():
    """8 x 36 in. wall, 20 ft simply supported between piers, f'c 3,000, fy 60,000, 150 pcf (300 plf self-weight), D 500 plf, L 400 plf.
    wu = 1.2(800) + 1.6(400) = 1,600 plf; Mu = 1,600 x 20^2 / 8 = 80,000 lb-ft; Vu = 16,000 lb.
    (2) #5 bottom, 3 in. bottom cover, no stirrups: d = 36 - 3 - 0.3125 = 32.6875 in.; a = 0.62(60,000) / (0.85 x 3,000 x 8) = 1.8235 in.;
    phi Mn = 0.9 x 0.62 x 60,000 (32.6875 - 0.9118) / 12 = 88,655 lb-ft. Table 9.3.1.1: 240 / 16 = 15 in.
    Vc (Table 22.5.5.1(c)): rho = 0.62 / (8 x 32.6875) = 0.002371; lambda_s = sqrt(2 / (1 + 3.26875)) = 0.68459;
    8 x 0.68459 x 0.002371^(1/3) x sqrt(3000) x 8 x 32.6875 = 10,459 lb; phi Vc = 7,844 lb.
    9.6.1.2: 200 / 60,000 x 8 x 32.6875 = 0.8717 in2; As by analysis 0.5579 in2 (Mu / 0.9 = As fy (d - As fy / (1.7 f'c b))), 4/3 of it 0.7438 < 0.8717 -> 9.6.1.3 governs."""
    r = sw.check("spans", 8, 36, 3000, 60000, 150, 1.5, "weather", loads=[dict(case="D", kind="uniform", w=500), dict(case="L", kind="uniform", w=400)],
                 strength=ST, service=SE, span_ft=20, n_bot=2, bar_bot=5, n_top=2, bar_top=5, cover_bot=3.0, **WALL)
    c = rows(r)
    assert r.values["Mpos"] / 12 == A(80000, rel=1e-4) and r.values["Vu"] == A(16000, rel=1e-4)
    d = 36 - 3 - 0.3125
    a = 0.62 * 60000 / (0.85 * 3000 * 8)
    assert c["flexure, positive moment (bottom bars)"].capacity == A(0.9 * 0.62 * 60000 * (d - a / 2) / 12, rel=1e-9)
    assert c["flexure, positive moment (bottom bars)"].capacity == A(88655, abs=1)
    rho = 0.62 / (8 * d)
    ls = math.sqrt(2 / (1 + d / 10))
    assert c["shear, no stirrups"].capacity == A(0.75 * 8 * ls * rho ** (1 / 3) * math.sqrt(3000) * 8 * d, rel=1e-9)
    assert c["shear, no stirrups"].capacity == A(7844, abs=1) and not c["shear, no stirrups"].ok
    assert c["depth for deflections not calculated"].demand == A(15.0)
    m = c["minimum flexural reinforcement, bottom"]
    k = 60000 / (1.7 * 3000 * 8)
    Areq = (d - math.sqrt(d * d - 4 * k * 80000 * 12 / 0.9 / 60000)) / (2 * k)
    assert Areq == A(0.5579, abs=2e-4) and m.demand == A(4 / 3 * Areq) and "9.6.1.3" in m.source


def test_grade_beam_two_spans_and_stirrups_by_hand():
    """Two equal 10 ft spans, w = 1,000 plf total (D 800 plf + 200 plf self-weight of an 8 x 24 in. wall), combination 1.0D.
    Mneg = wL^2/8 = 12,500 lb-ft; interior reaction 1.25 wL = 12,500 lb; end reactions 0.375 wL = 3,750 lb; max shear 0.625 wL = 6,250 lb.
    #3 stirrups, 2 legs at 10 in.: d = 24 - 1.5 - 0.375 - 0.3125 = 21.8125 in.; Vc = 2 sqrt(3000) x 8 x 21.8125 = 19,115 lb;
    Vs = 0.22 x 60,000 x 21.8125 / 10 = 28,793 lb; Av,min = max(0.75 sqrt(3000) 8 x 10 / 60,000, 50 x 8 x 10 / 60,000) = 0.0667 in2;
    spacing limit d/2 = 10.906 in."""
    st = [("1.0D", {"D": 1.0}, "test")]
    r = sw.check("spans", 8, 24, 3000, 60000, 150, 1.5, "weather", loads=[dict(case="D", kind="uniform", w=800)], strength=st, service=[],
                 spans=[10, 10], n_bot=2, bar_bot=5, n_top=2, bar_top=5, st_bar=3, st_legs=2, st_s=10, cover_bot=1.5, **WALL)
    c = rows(r)
    assert r.values["Mneg"] / 12 == A(12500, rel=1e-3) and r.values["Vu"] == A(6250, rel=1e-3)
    re = r.values["reactions"][("factored", "1.0D")]
    assert re[0] == A(3750, rel=1e-3) and re[1] == A(12500, rel=1e-3) and re[2] == A(3750, rel=1e-3)
    d = 24 - 1.5 - 0.375 - 0.3125
    assert c["shear"].capacity == A(0.75 * (2 * math.sqrt(3000) * 8 * d + 0.22 * 60000 * d / 10), rel=1e-9)
    assert c["stirrup area, Av,min"].demand == A(max(0.75 * math.sqrt(3000) * 8 * 10 / 60000, 50 * 8 * 10 / 60000))
    assert c["stirrup spacing"].capacity == A(d / 2)
    assert c["depth for deflections not calculated"].demand == A(120 / 18.5)        # one end continuous
    # clear spacing of (2) #5 in an 8 in. wall with 1.5 in. side cover and #3 stirrups: 8 - 2(1.875) - 2(0.625) = 3.0 in.
    assert c["clear spacing of bottom bars"].capacity == A(3.0) and c["clear spacing of bottom bars"].demand == A(1.0)


def test_backfill_on_a_braced_wall_by_hand():
    """36 in. wall braced at the top, 3 ft of backfill at 60 pcf: triangular load, 180 psf at the base, on a 3 ft simple span.
    Mmax = w0 L^2 / (9 sqrt 3) = 180 x 9 / 15.588 = 103.92 lb-ft per ft; base shear w0 L / 3 = 180 lb. Factored by 1.6H: 166.3 lb-ft, 288 lb.
    #4 at 16 in. at the center: As = 0.15 in2/ft, d = 4 in.; a = 0.15 x 60,000 / (0.85 x 3,000 x 12) = 0.2941 in.;
    phi Mn = 0.9 x 0.15 x 60,000 (4 - 0.1471) / 12 = 2,600.7 lb-ft. Plain wall cast against soil: h = 6 in., Sm = 72 in3,
    phi Mn = 0.60 x 5 sqrt(3000) x 72 / 12 = 985.9 lb-ft; phi Vn = 0.60 x 4/3 sqrt(3000) x 12 x 6 = 3,155 lb."""
    r = sw.check("footing", 8, 36, 3000, 60000, 150, 1.5, "weather", loads=[], strength=ST, service=SE, hb=3, efp=60, **WALL)
    c = rows(r)
    assert c["out-of-plane flexure"].demand == A(1.6 * 180 * 9 / (9 * math.sqrt(3)), rel=1e-3)
    assert c["out-of-plane shear"].demand == A(1.6 * 180, rel=1e-3)
    assert c["out-of-plane flexure"].capacity == A(0.9 * 0.15 * 60000 * (4 - 0.15 * 60000 / (0.85 * 3000 * 12) / 2) / 12, rel=1e-9)
    p = sw.check("footing", 8, 36, 3000, 60000, 150, 1.5, "earth", loads=[], strength=ST, service=SE, hb=3, efp=60, plain=True, cast_against_soil=True)
    c = rows(p)
    assert c["out-of-plane flexure, plain wall"].capacity == A(0.6 * 5 * math.sqrt(3000) * 72 / 12, rel=1e-9)
    assert c["out-of-plane shear, plain wall"].capacity == A(0.6 * 4 / 3 * math.sqrt(3000) * 12 * 6, rel=1e-9)
    with pytest.raises(sw.StemWallError, match="cantilever retaining wall"):
        sw.check("footing", 8, 36, 3000, 60000, 150, 1.5, "weather", strength=ST, service=SE, hb=3, efp=60, braced=False, **WALL)


def test_wall_bearing_on_soil_by_hand():
    """8 x 36 in. wall on soil, no footing: D 450 + L 600 plf + 300 plf self-weight = 1,350 plf over 8/12 ft = 2,025 psf.
    Table 11.6.1: #4 vertical at 16 in. in an 8 in. wall: 0.20 x 12 / 16 = 0.150 in2/ft >= 0.0012 x 8 x 12 = 0.1152; horizontal #4 at 12 in.
    0.200 in2/ft >= 0.0020 x 96 = 0.192."""
    r = sw.check("soil", 8, 36, 3000, 60000, 150, 1.5, "weather", loads=[dict(case="D", kind="uniform", w=450), dict(case="L", kind="uniform", w=600)],
                 strength=ST, service=SE, q_allow=2500, cover_bot=3.0, **WALL)
    c = rows(r)
    assert c["soil bearing under the wall"].demand == A(2025.0)
    assert c["minimum vertical wall reinforcement"].demand == A(0.1152) and c["minimum vertical wall reinforcement"].capacity == A(0.15)
    assert c["minimum horizontal wall reinforcement"].demand == A(0.192) and c["minimum horizontal wall reinforcement"].capacity == A(0.2)
    with pytest.raises(sw.StemWallError, match="point load"):
        sw.check("soil", 8, 36, 3000, 60000, 150, 1.5, "weather", loads=[dict(case="D", kind="point", P=1000, x_ft=5)],
                 strength=ST, service=SE, q_allow=2500, **WALL)


def test_phi_transition_and_cover_table():
    """Table 21.2.2 (other): eps_ty = 60,000 / 29,000,000 = 0.002069; at eps_t = 0.004 phi = 0.65 + 0.25 (0.004 - 0.002069) / 0.003 = 0.8109.
    Table 20.5.1.3.1: against ground 3 in.; weather #5 1.5 in., #6 2 in."""
    assert sw.phi_flexure(0.004, 60000)[0] == A(0.65 + 0.25 * (0.004 - 60000 / 29e6) / 0.003)
    assert sw.phi_flexure(0.006, 60000) == (0.90, "tension controlled") and sw.phi_flexure(0.001, 60000)[0] == 0.65
    assert sw.cover_required("earth", 4) == 3.0 and sw.cover_required("weather", 5) == 1.5 and sw.cover_required("weather", 6) == 2.0


def test_stem_wall_screen_and_sheet(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="T", name="T", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 2.3.1"), dict(expr="0.9D + 1.6H", source="2.3.6")],
                combos_asd=[dict(expr="D + L", source="ASCE/SEI 7-22 2.4.1")])
    v = dict(mark="FW1", support="spanning between footings or piers (voids below)", t="8", H="36", fc="3000", fy="60000", conc_pcf="150", cover="1.5",
             cover_bot="3", exposure="exposed to weather or in contact with ground", plain="reinforced", bar_v="4", s_v="16", v_at="center of the wall",
             bar_h="4", s_h="12", span="12", more_spans="12", n_bot="2", bar_bot="5", n_top="2", bar_top="5", st_bar="3", st_legs="2", st_s="12",
             hb="2", efp="60", efp_source="soils report", loads=[dict(case="D", kind="uniform", mag="450", x1=None, x2=None, label=""),
                                                                 dict(case="L", kind="point", mag="2000", x1="6", x2=None, label="pilaster")])
    sheet, _, _ = calc.build("stem_wall", v, proj)
    assert sheet.ok and sheet.diagram and len(sheet.stem.values["layout"].supports) == 3
    calcsheet.simple_pdf(sheet, str(tmp_path / "fw.pdf"), "T", "ACI 318-19", "Nov 28, 2026")
    for sup in ("bearing on soil, no footing", "on a continuous footing"):
        v2 = dict(v, support=sup, q_allow="2500", soil_source="soils report", loads=v["loads"][:1])
        s2, _, _ = calc.build("stem_wall", v2, proj)
        calcsheet.simple_pdf(s2, str(tmp_path / "fw2.pdf"), "T", "ACI 318-19", "Nov 28, 2026")
