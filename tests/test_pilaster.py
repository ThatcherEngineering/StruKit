"""Pilaster on a footing (strukit.pilaster). No published worked example of a metal building pilaster is on file (logged); the
interaction diagram is checked against an independent strain-compatibility solution written here, the rest by hand."""
import math

import pytest

from strukit import pilaster as pl
from strukit.stemwall import BAR_AREA

A = pytest.approx
FTG = dict(B_ft=7, L_ft=5, h_in=18, bar=5, n_x=7, n_y=9, cover=3, q_allow=2500, soil_depth_ft=1.5, soil_pcf=110, ot_required=1.5)
ST = [("1.2D + 1.6S", 22000.0, 6920.0, 0.0, 1.2)]
SE = [("D + S", 16000.0, 4700.0, 0.0, 1.0)]


def _independent_M_at_zero_P(b, h, fc, fy, lay):
    """Bisection on the neutral axis for zero axial force, Whitney block, bars elastic-plastic, displaced concrete subtracted."""
    b1 = 0.85 if fc <= 4000 else max(0.85 - 0.05 * (fc - 4000) / 1000, 0.65)
    def forces(c):
        a = min(b1 * c, h)
        P, M = 0.85 * fc * a * b, 0.85 * fc * a * b * (h / 2 - a / 2)
        for d, As in lay:
            fs = max(min(0.003 * (c - d) / c * 29e6, fy), -fy) - (0.85 * fc if d <= a else 0.0)
            P += As * fs; M += As * fs * (h / 2 - d)
        return P, M
    lo, hi = 0.01, h
    for _ in range(200):
        mid = (lo + hi) / 2
        if forces(mid)[0] > 0:
            hi = mid
        else:
            lo = mid
    c = (lo + hi) / 2
    dt = max(d for d, _ in lay)
    et = 0.003 * (dt - c) / c
    phi = 0.90 if et >= fy / 29e6 + 0.003 else 0.65 + 0.25 * (et - fy / 29e6) / 0.003
    return phi * forces(c)[1]


def test_interaction_points():
    """16 x 16 in. pier, (6) #6 (two on each face across the bending, one on each side face), #3 ties, 1.5 in. cover, f'c 3,000, fy 60,000.
    Layers: d = 1.5 + 0.375 + 0.375 = 2.25 in. and 13.75 in. (two bars each), 8 in. (two bars). Po = 0.85 x 3,000 (256 - 2.64) + 60,000 x 2.64 =
    804,468 lb; 0.80 Po = 643,574 lb (Table 22.4.2.1(a)); pure tension phi Pn = -0.9 x 60,000 x 2.64 = -142,560 lb."""
    lay = pl.layers(16, 1.5, 0.375, 6, 2, 1)
    assert [round(d, 4) for d, _ in lay] == [2.25, 8.0, 13.75] and sum(a for _, a in lay) == A(6 * 0.44)
    pts, Pmax, Po = pl.interaction(16, 16, 3000, 60000, lay)
    assert Po == A(0.85 * 3000 * (256 - 2.64) + 60000 * 2.64) and Pmax == A(0.8 * Po)
    assert pts[0][1] == A(-0.9 * 60000 * 2.64)
    assert pl.phi_Mn_at(pts, 0.0) == A(_independent_M_at_zero_P(16, 16, 3000, 60000, lay), rel=2e-3)
    assert max(p[1] for p in pts) == A(0.65 * Pmax)
    assert pl.phi_Mn_at(pts, 0.65 * Pmax * 1.01) is None


def test_development_length_other_cases():
    """Table 25.4.2.3, other cases: #5, Grade 60, f'c 3,000: 3 x 60,000 / (50 sqrt 3000) x 0.625 = 41.08 in.; #7: 3 x 60,000 / (40 sqrt 3000)
    x 0.875 = 71.89 in.; at least 12 in."""
    assert pl.ld_other(5, 60000, 3000) == A(3 * 60000 / (50 * math.sqrt(3000)) * 0.625)
    assert pl.ld_other(7, 60000, 3000) == A(3 * 60000 / (40 * math.sqrt(3000)) * 0.875)


def test_soil_thrust_pier_and_footing_by_hand():
    """Sliding: passive 250 pcf, top 1 ft neglected, footing bottom 4 ft below grade, 18 in. footing 5 ft wide, pier 16 in. wide 18 in. below
    grade above it: footing face 0.5 x 250 (4^2 - 2.5^2) x 5 = 6,093.75 lb; pier face from 1 ft (neglected above) to 2.5 ft:
    0.5 x 250 (2.5^2 - 1^2) x 16/12 = 875 lb; Pp = 6,968.75 lb. Weights: pier 16 x 16 x 36 / 1728 x 150 = 800 lb; footing 7 x 5 x 1.5 x 150 =
    7,875 lb; soil (35 - 256/144) x 1.5 x 110 = 5,481.7 lb; N = 16,000 + 14,156.7 = 30,156.7 lb; (0.35 N + Pp) / 4,700 = 3.728.
    Pier shear: Vu 6,920 lb, Av = 0.22 >= Av,min = max(0.75 sqrt(3000) 16 x 8 / 60,000, 50 x 16 x 8 / 60,000) = 0.1067: Table 22.5.5.1(a) with
    Nu / 6Ag = 22,000 / 1,536 = 14.32 psi; d = 16 - 1.5 - 0.375 - 0.375 = 13.75 in.; Vc = (2 sqrt 3000 + 14.32) 16 x 13.75 = 27,252 lb;
    Vs = 0.22 x 60,000 x 13.75 / 8 = 22,688 lb; phi Vn = 37,455 lb."""
    soil = dict(passive_pcf=250, mu=0.35, sf=1.5, neglect_ft=1.0, depth_ft=4.0)
    r = pl.check(16, 16, 36, 18, 3000, 60000, 150, 1.5, 6, 2, 1, 3, 8, 3, 3, FTG, ST, SE, thrust="soil", soil=soil)
    c = {x.name: x for x in r["checks"]}
    Pp = 0.5 * 250 * (16 - 6.25) * 5 + 0.5 * 250 * (6.25 - 1) * 16 / 12
    N = 16000 + 800 + 7875 + (35 - 256 / 144) * 1.5 * 110
    assert c["sliding, friction and passive pressure"].capacity == A((0.35 * N + Pp) / 4700)
    d = 13.75
    Vc = (2 * math.sqrt(3000) + 22000 / (6 * 256)) * 16 * d
    assert c["pier shear"].capacity == A(0.75 * (Vc + 0.22 * 60000 * d / 8))
    assert c["pier, moment with axial load"].demand == A(6920 * 36 / 12)
    assert r["footing"] is not None and all(x.ok for x in r["footing"].checks)
    assert c["ties around the anchor rods, within 5 in. of the top"].ok and c["slenderness may be neglected, k lu / r"].demand == A(2 * 36 / 4.8)


def test_hairpin_tie_beam_and_uplift():
    """Hairpins (2) #5: 4 legs x 0.31 x 60,000 x 0.9 = 66,960 lb; leg 60 in. >= ld 41.08 in. Tie beam (2) #6 into the pilaster 30 in. < ld
    3 x 60,000 / (50 sqrt 3000) x 0.75 = 49.30 in.: flagged. Net uplift 3,000 lb at 0.6D: weights 0.6 x 14,156.7 = 8,494 lb resist it."""
    st = ST + [("0.9D + 1.0W", -5000.0, 4500.0, 0.0, 0.9)]
    se = SE + [("0.6D + 0.6W", -3000.0, 2700.0, 0.0, 0.6)]
    r = pl.check(16, 16, 36, 18, 3000, 60000, 150, 1.5, 6, 2, 1, 3, 8, 3, 3, FTG, st, se, thrust="hairpin", hairpin=dict(n=2, bar=5, leg_in=60, e_in=4))
    c = {x.name: x for x in r["checks"]}
    assert c["hairpin bars in tension"].capacity == A(0.9 * 4 * 0.31 * 60000) and c["hairpin bar development"].ok
    assert c["uplift resisted by weight"].demand == A(3000) and c["uplift resisted by weight"].capacity == A(0.6 * (800 + 7875 + (35 - 256 / 144) * 165))
    t = pl.check(16, 16, 36, 18, 3000, 60000, 150, 1.5, 6, 2, 1, 3, 8, 3, 3, FTG, ST, SE, thrust="tie beam", tie=dict(n=2, bar=6, embed_in=30))
    c = {x.name: x for x in t["checks"]}
    assert c["tie beam bar development"].demand == A(3 * 60000 / (50 * math.sqrt(3000)) * 0.75) and not c["tie beam bar development"].ok


def test_pilaster_screen(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="T", name="T", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6S", source="ASCE/SEI 7-22 2.3.1")],
                combos_asd=[dict(expr="D + S", source="ASCE/SEI 7-22 2.4.1")])
    v = dict(mark="PC1", kind="free-standing on its footing", bx="16", by="16", hp="36", below="18", fc="3000", fy="60000", conc_pcf="150", cover="1.5",
             bar="6", n_face="2", n_side="1", tie_bar="3", tie_s="8", top_ties="3", top_tie_bar="3", B="7", L="5", hf="18", f_bar="5", n_x="7", n_y="9",
             f_cover="3", q_allow="2500", soil_source="soils report", soil_depth="1.5", soil_pcf="110", ot_required="1.5",
             thrust="soil (friction and passive)", passive="250", mu="0.35", sf="1.5", neglect="1", depth="4", passive_source="soils report",
             reactions=[dict(case="D", P="6", V="1.5", M=None, label=""), dict(case="S", P="10", V="3.2", M=None, label="")])
    sheet, _, _ = calc.build("pilaster", v, proj)
    assert sheet.ok
    calcsheet.simple_pdf(sheet, str(tmp_path / "pc.pdf"), "T", "ACI 318-19", "Nov 28, 2026")
