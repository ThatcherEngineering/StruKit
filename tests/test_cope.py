"""Coped beam end against AISC Design Examples v16.0, Example II.A-6 (W21x62, 8 in. deep by 9 in. long top cope)."""
import pytest
from strukit import cope, shapes


def test_example_IIA6():
    b = shapes.get("W21X62")
    r = cope.top_cope(b["d"], b["tw"], b["bf"], b["tf"], 50, 65, 8.0, 9.0, 9.5)
    assert r["hc"] == pytest.approx(13.0) and r["f"] == pytest.approx(0.858, abs=0.002) and r["k"] == pytest.approx(4.04, abs=0.01)
    assert r["Sc"] == pytest.approx(17.8, rel=0.01) and r["Zc"] == pytest.approx(32.2, rel=0.01)       # Manual Tables 9-2a, 9-2b
    assert r["lam"] == pytest.approx(32.5) and r["lam_p"] == pytest.approx(21.3, abs=0.1)
    assert r["Mn"] == pytest.approx(1230, rel=0.01) and r["R_flex"] == pytest.approx(129, rel=0.01)
    assert 0.9 * r["R_flex"] == pytest.approx(116, rel=0.01) and r["R_flex"] / 1.67 == pytest.approx(77.2, rel=0.01)
    assert r["R_vy"] == pytest.approx(156, rel=0.005) and r["R_vr"] == pytest.approx(203, rel=0.005)


def test_branches_and_limits():
    b = shapes.get("W21X62")
    a = (b["d"], b["tw"], b["bf"], b["tf"], 50, 65)
    short = cope.top_cope(*a, 2.0, 1.5, 2.0)
    assert short["Mn"] == pytest.approx(short["Mp"])                    # stocky: plastic moment
    long_ = cope.top_cope(*a, 8.0, 30.0, 30.5)
    assert long_["f"] == pytest.approx(1 + 30 / b["d"]) and long_["k"] == pytest.approx(2.2 * 13 / 30) and long_["k1"] >= 1.61
    with pytest.raises(cope.CopeError):
        cope.top_cope(*a, 11.0, 9.0, 9.5)
    bs = cope.web_block_shear(0.4, 50, 65, 3, 3, 1.5, 1.75, 0.875)
    assert bs["Agv"] == pytest.approx(3.0) and bs["Anv"] == pytest.approx(3.0 - 2.5 * 0.875 * 0.4) and bs["Ant"] == pytest.approx((1.75 - 0.4375) * 0.4)


def test_example_IIA7_double_cope():
    """W16x40, 3-1/2 in. top and 2 in. bottom copes 9-1/2 in. long, e = 10 in.: Cb 1.94, Lb d / t^2 1,070, Mn 421 kip-in., 37.9 / 25.2 kips."""
    b = shapes.get("W16X40")
    r = cope.double_cope(b["d"], b["tw"], 50, 65, 3.5, 2.0, 9.5, 10.0)
    assert r["hc"] == pytest.approx(10.5) and r["Cb"] == pytest.approx(1.94, abs=0.01) and r["lam"] == pytest.approx(1070, rel=0.01)
    assert r["Sc"] == pytest.approx(5.60, rel=0.01) and r["Zc"] == pytest.approx(8.41, rel=0.01) and r["Mn"] == pytest.approx(421, rel=0.01)
    assert 0.9 * r["R_flex"] == pytest.approx(37.9, rel=0.01) and r["R_flex"] / 1.67 == pytest.approx(25.2, rel=0.01)


def test_tee_flexure_design_example_F10():
    """AISC Design Examples v16.0 Example F.10: WT5x6, A992, stem in tension, continuously braced (Manual Table 1-8: Sx 1.22, Zx 2.20, Ix 4.35,
    y 1.36 in.; bf / 2tf 9.43).  Published: My 61.0 kip-in., Fy Zx 110 kip-in. capped at 1.6 My = 97.6 kip-in.; lambda_pf 9.15, lambda_rf 24.1,
    noncompact flange, F9-14 gives 110 > 97.6, so Mn = 97.6 kip-in. = 8.13 kip-ft; 7.32 / 4.87 kip-ft available."""
    r = cope.tee_flexure(50, 1.22, 4.35 / 1.36, 2.20, 3.96, 0.210)
    assert r["My"] == pytest.approx(61.0) and r["Mp"] == pytest.approx(97.6) and r["Mp_raw"] == pytest.approx(110)
    assert r["lam_f"] == pytest.approx(9.43, abs=0.01) and r["lam_pf"] == pytest.approx(9.15, abs=0.01) and r["lam_rf"] == pytest.approx(24.1, abs=0.05)
    flb = dict((n, v) for n, v, _ in r["limits"])["flange local buckling"]
    assert flb == pytest.approx(97.6)                                                        # F9-14 capped at 1.6 My
    assert r["Mn"] / 12 == pytest.approx(8.13, abs=0.005) and 0.9 * r["Mn"] / 12 == pytest.approx(7.32, abs=0.01) and r["Mn"] / 12 / 1.67 == pytest.approx(4.87, abs=0.01)


def test_tee_section_of_a_cut_W_against_the_WT_table():
    """A W10x12 cut at mid-depth is a WT5x6 (Manual Table 1-8: Ix 4.35 in4, y 1.36 in., Zx 2.20, Sx 1.22 in3). StruKit's section leaves out the
    fillets, so it lands within a few percent and on the low side for the moduli."""
    w = shapes.get("W10X12")
    t = cope.tee(w["d"], w["tw"], w["bf"], w["tf"], w["d"] / 2)
    assert t["I"] == pytest.approx(4.35, rel=0.02) and t["y"] == pytest.approx(1.36, rel=0.03) and t["Zc"] == pytest.approx(2.20, rel=0.01)
    assert t["I"] / (t["hc"] - t["y"]) == pytest.approx(1.22, rel=0.01)


def test_tee_lateral_torsional_buckling_by_hand():
    """AISC 360-22 Eq. F9-6 to F9-11, worked by hand for a tee 10 in. deep: flange 4 x 0.25 in., stem 0.20 in., Fy 50."""
    import math
    bf, tf, tw, dd, Fy, E = 4.0, 0.25, 0.20, 10.0, 50.0, 29000.0
    s = cope.tee(dd + 1.0, tw, bf, tf, 1.0)                                  # an 11 in. beam coped 1 in. at the bottom leaves this tee
    Iy = tf * bf ** 3 / 12 + (dd - tf) * tw ** 3 / 12
    J = (bf * tf ** 3 + (dd - tf) * tw ** 3) / 3
    ry = math.sqrt(Iy / s["A"])
    Sx = s["I"] / (dd - s["y"])
    Lp = 1.76 * ry * math.sqrt(E / Fy)
    Lr = 1.95 * E / Fy * math.sqrt(Iy * J) / Sx * math.sqrt(2.36 * Fy / E * dd * Sx / J + 1)
    for Lb in (Lp / 2, (Lp + Lr) / 2, 1.5 * Lr):
        r = cope.tee_flexure(Fy, Sx, s["I"] / s["y"], s["Zc"], bf, tf, ltb=dict(d=dd, Iy=Iy, J=J, ry=ry, Lb=Lb))
        My, Mp = Fy * Sx, min(Fy * s["Zc"], 1.6 * Fy * Sx)
        B = 2.3 * dd / Lb * math.sqrt(Iy / J)
        Mcr = 1.95 * E / Lb * math.sqrt(Iy * J) * (B + math.sqrt(1 + B * B))
        want = Mp if Lb <= Lp else (Mp - (Mp - My) * (Lb - Lp) / (Lr - Lp) if Lb <= Lr else Mcr)
        assert r["Lp"] == pytest.approx(Lp) and r["Lr"] == pytest.approx(Lr)
        assert r["Mn"] == pytest.approx(min(want, Mp))


def test_bottom_cope_W21x62():
    """W21x62 (A992) coped 2 in. deep and 9 in. long at the bottom flange, e = 9.5 in., three 7/8 in. holes in the web line (hand calculation)."""
    b = shapes.get("W21X62")
    r = cope.bottom_cope(b["d"], b["tw"], b["bf"], b["tf"], 50, 65, 2.0, 9.0, 9.5, holes=3, hole=0.875)
    s = cope.tee(b["d"], b["tw"], b["bf"], b["tf"], 2.0)
    assert r["hc"] == pytest.approx(b["d"] - 2.0) and r["Sx"] == pytest.approx(s["I"] / (s["hc"] - s["y"])) and r["Sxc"] == pytest.approx(s["I"] / s["y"])
    assert r["Mn"] == pytest.approx(min(50 * s["Zc"], 1.6 * 50 * r["Sx"])) and r["governs"] == "yielding"     # Lb = 9 in. is under Lp; compact flange
    assert r["R_flex"] == pytest.approx(r["Mn"] / 9.5) and r["R_rup"] == pytest.approx(65 * s["Zc"] / 9.5)
    assert r["R_vy"] == pytest.approx(0.6 * 50 * r["hc"] * b["tw"]) and r["R_vr"] == pytest.approx(0.6 * 65 * (r["hc"] - 3 * 0.875) * b["tw"])
    with pytest.raises(cope.CopeError):
        cope.bottom_cope(b["d"], b["tw"], b["bf"], b["tf"], 50, 65, 11.0, 9.0, 9.5)
