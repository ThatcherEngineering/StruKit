"""Steel beam checks against AISC 360-22.

STATUS: equation-level checks only. These confirm the code follows the Specification
text on file (hand arithmetic, the Specification's own equivalent Mcr expression in the
F2 User Note, and continuity between equations). They are NOT yet the independent
validation the brief requires: that needs the AISC Design Examples and the AISC Shapes
Database on file. The section properties below were typed by hand for testing and must
be replaced by Shapes Database values before any job use.
"""
import math

import pytest

from strukit.steel_beam import SteelInputError, cb_factor, check, rts_from

E, G = 29000.0, 11200.0
SHAPE = dict(d=18.0, tw=0.355, bf=7.50, tf=0.570, h_tw=45.2, Zx=101.0, Sx=88.9,
             ry=1.65, J=1.24, ho=17.4, Iy=40.1, Cw=3040.0)        # test section, hand-typed
FY = 50.0


def near(a, b, tol=1e-3):
    return a == pytest.approx(b, rel=tol)


def test_yielding_governs_when_fully_braced():
    r = check(SHAPE, FY, Lb=0)
    assert near(r.Mn, 50 * 101.0)                               # Eq. F2-1 by hand: 5050 kip-in
    assert r.governs.startswith("yielding") and r.flange == "compact"
    assert near(r.M_avail, 5050 / 1.67)
    assert near(check(SHAPE, FY, Lb=0, method="LRFD").M_avail, 0.9 * 5050)


def test_lp_by_hand():
    r = check(SHAPE, FY, Lb=0)
    lp = next(x for x in r.lines if x.label == "Lp")
    assert near(lp.value, 1.76 * 1.65 * math.sqrt(29000 / 50))  # Eq. F2-5: 69.94 in
    assert lp.source == "Eq. F2-5"


def test_inelastic_and_elastic_ltb_meet_at_lr():
    # At Lb = Lr, Eq. F2-2 (Cb = 1) gives 0.7 Fy Sx; Eq. F2-3/F2-4 must give the same.
    lr = next(x for x in check(SHAPE, FY, Lb=0).lines if x.label == "Lr").value
    just_in = check(SHAPE, FY, Lb=lr * 0.999999).Mn
    just_out = check(SHAPE, FY, Lb=lr * 1.000001).Mn
    assert near(just_in, 0.7 * FY * SHAPE["Sx"], 1e-4)
    # 0.078 (F2-4) and 6.76 (F2-6) are rounded in the Specification, so the two
    # equations meet within about 0.15 %, not exactly.
    assert near(just_out, 0.7 * FY * SHAPE["Sx"], 2e-3)


def test_elastic_ltb_equals_the_user_note_expression():
    # F2 User Note: Mcr = Cb (pi/Lb) sqrt(E Iy G J + (pi E / Lb)^2 Iy Cw), identical to
    # Eq. F2-3 / F2-4 with rts from Eq. F2-7 and c = 1. The 0.078 in F2-4 stands for
    # G/(E pi^2) rounded, so agreement is within about 0.3 %.
    Lb, Cb = 360.0, 1.14
    r = check(SHAPE, FY, Lb=Lb, Cb=Cb)
    Mcr = Cb * (math.pi / Lb) * math.sqrt(
        E * SHAPE["Iy"] * G * SHAPE["J"] + (math.pi * E / Lb) ** 2 * SHAPE["Iy"] * SHAPE["Cw"])
    assert r.governs.startswith("lateral-torsional")
    assert near(r.Mn, Mcr, 4e-3)


def test_inelastic_ltb_by_hand_and_cb_cap():
    lines = {x.label: x.value for x in check(SHAPE, FY, Lb=0).lines}
    Lp, Lr, Mp = lines["Lp"], lines["Lr"], 5050.0
    Lb = 120.0
    assert Lp < Lb < Lr
    by_hand = Mp - (Mp - 0.7 * 50 * 88.9) * (Lb - Lp) / (Lr - Lp)      # Eq. F2-2, Cb = 1
    assert near(check(SHAPE, FY, Lb=Lb).Mn, by_hand)
    assert near(check(SHAPE, FY, Lb=Lb, Cb=2.0).Mn, Mp)               # capped at Mp


def test_noncompact_and_slender_flange():
    s = dict(SHAPE, tf=0.38)                    # bf/2tf = 9.87 > 0.38 sqrt(E/Fy) = 9.15
    r = check(s, FY, Lb=0)
    lam, lp, lr = 7.5 / 0.76, 0.38 * math.sqrt(580), math.sqrt(580)
    assert r.flange == "noncompact"
    assert near(r.Mn, 5050 - (5050 - 0.7 * 50 * 88.9) * (lam - lp) / (lr - lp))   # Eq. F3-1
    s = dict(SHAPE, tf=0.15)                    # bf/2tf = 25 > 24.08
    r = check(s, FY, Lb=0)
    kc = min(max(4 / math.sqrt(45.2), 0.35), 0.76)
    assert r.flange == "slender" and near(r.Mn, 0.9 * E * kc * 88.9 / 25.0 ** 2)   # Eq. F3-2


def test_shear_rolled_shape():
    r = check(SHAPE, FY, Lb=0)
    assert near(r.Vn, 0.6 * 50 * 18.0 * 0.355)                  # Eq. G2-1, Cv1 = 1: 191.7 kip
    assert near(r.V_avail, 191.7 / 1.50)                        # G2.1(a): Omega_v = 1.50
    assert near(check(SHAPE, FY, Lb=0, method="LRFD").V_avail, 191.7)
    thin = dict(SHAPE, h_tw=60.0)                               # > 2.24 sqrt(E/Fy) = 53.9
    r = check(thin, FY, Lb=0)
    lim = 1.10 * math.sqrt(5.34 * 580)                          # 61.2: Cv1 still 1.0
    assert 60.0 < lim and near(r.V_avail, 191.7 / 1.67)         # G2.1(b): Omega_v = 1.67


def test_cb_user_note_cases():
    # F1 User Note: 1.0 uniform moment; 1.67 one end moment zero; 2.27 reverse curvature.
    assert near(cb_factor(1, 1, 1, 1), 1.0)
    assert near(cb_factor(1, 0.25, 0.5, 0.75), 1.67, 3e-3)
    assert near(cb_factor(1, 0.5, 0, 0.5), 2.27, 3e-3)


def test_rts_equation():
    assert near(rts_from(40.1, 3040.0, 88.9), math.sqrt(math.sqrt(40.1 * 3040.0) / 88.9))


def test_out_of_scope_and_missing_inputs_stop_with_a_message():
    with pytest.raises(SteelInputError, match="F4 / F5 are not built"):
        check(dict(SHAPE, h_tw=120.0), FY, Lb=0)
    with pytest.raises(SteelInputError, match="missing section properties: Zx"):
        check({k: v for k, v in SHAPE.items() if k != "Zx"}, FY, Lb=0)
