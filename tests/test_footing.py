"""Isolated footing checks against ACI 318-19 and a real job.

Reference job: Thatcher Engineering 2026-011 (Humbargar Residence addition), sealed calc
package of April 2026, "Footing A" page, produced with StruCalc Pro. The numbers below
are the values printed on that page.

STATUS: soil pressure, factored moment and bearing match StruCalc exactly. The shear
checks do NOT match StruCalc and are not meant to: see the two tests named
"..._differs_from_strucalc".
RULING (Zach Thatcher, 2026-11-20 18:08): follow ACI 318-19 as written, not StruCalc's
method, for footing shear. Recorded in STRUKIT-RULINGS.md.
"""
import math

import pytest

from strukit.footing import FootingInputError, check


def footing_a(**kw):
    args = dict(B_ft=2.5, L_ft=2.5, h_in=10, fc=3000, fy=60000, col_x_in=4, col_y_in=4,
                bar=5, n_x=3, n_y=3, cover_in=3, P_service=7600, service_combo="D+L",
                Pu=1.6 * 7600, strength_combo="1.2D+1.6L+0.5Lr", q_allow_psf=1500,
                conc_pcf=145, plate_x_in=6, plate_y_in=6)
    args.update(kw)
    return check(**args)


def near(a, b, tol=1e-3):
    return a == pytest.approx(b, rel=tol)


# ---- matches StruCalc (2026-011 Footing A) ----

def test_soil_bearing_matches_strucalc():
    c = footing_a().get("soil bearing pressure")
    assert near(c.demand, 1336.8, 1e-4) and c.capacity == 1500        # StruCalc: 1336.8 / 1500.0
    assert near(footing_a().values["W_ftg"], 755.21, 1e-4)            # StruCalc footing weight


def test_factored_moment_matches_strucalc():
    r = footing_a()
    assert near(r.get("flexure, x direction").demand, 2638.9, 1e-4)   # StruCalc Moment X
    assert near(r.get("flexure, y direction").demand, 2638.9, 1e-4)   # StruCalc Moment Y


def test_bearing_on_footing_matches_strucalc():
    c = footing_a().get("bearing on footing")
    assert near(c.demand, 12160.0, 1e-6) and near(c.capacity, 119340.0, 1e-6)   # "Crushing"


def test_moment_capacity_within_one_percent_of_strucalc():
    # StruCalc prints 26,198.6 lb-ft, which back-calculates to d = 6.625 in. With #5 bars
    # and 3 in cover the lower layer is d = 10 - 3 - 0.625/2 = 6.6875 in, giving 26,461.
    c = footing_a().get("flexure, x direction")
    a = 0.93 * 60000 / (0.85 * 3000 * 30)
    assert near(c.capacity, 0.9 * 0.93 * 60000 * (6.6875 - a / 2) / 12, 1e-6)
    assert near(c.capacity, 26198.6, 1.1e-2)


# ---- differs from StruCalc, by the text of ACI 318-19 ----

def test_one_way_shear_differs_from_strucalc():
    # StruCalc: demand 3,711.3 lb, capacity 19,718.0 lb.
    #  - Its demand matches a section d/2 from the critical section. ACI 318-19 13.2.7.2
    #    with 7.4.3.2 puts the one-way section at d, which gives 2,356 lb.
    #  - Its capacity equals 0.75 x 2 sqrt(fc') x 30 x 8.0. ACI 318-19 Table 22.5.5.1(c)
    #    (no shear reinforcement) gives 0.75 x 8 rho^(1/3) sqrt(fc') b d = 10,993 lb.
    c = footing_a().get("one-way shear, x direction")
    qu = 12160 / 900.0
    assert near(c.demand, qu * 30 * (15 - 2.5 - 6.6875))
    rho = 0.93 / (30 * 6.6875)
    assert near(c.capacity, 0.75 * 8 * rho ** (1 / 3) * math.sqrt(3000) * 30 * 6.6875)
    assert c.capacity < 19718.0 and c.demand < 3711.3
    assert near(0.75 * 2 * math.sqrt(3000) * 30 * 8.0, 19718.0, 1e-4)   # how StruCalc got its value


def test_two_way_shear_differs_from_strucalc():
    # StruCalc: demand 10,314.4, capacity 61,454.5. Its perimeter uses d = 6.6875 in and its
    # capacity uses a depth of 8.0 in: 0.75 x 4 sqrt(fc') x 46.75 x 8.0 = 61,454.
    # ACI 318-19 22.6.2.1 takes d as the average of the two layers (6.375 in) throughout.
    c = footing_a().get("two-way shear")
    d = 6.375
    b = 5 + d
    assert near(c.demand, 12160 - 12160 / 900.0 * b * b)
    assert near(c.capacity, 0.75 * 4 * math.sqrt(3000) * 4 * b * d)
    assert c.capacity < 61454.5
    assert near(0.75 * 4 * math.sqrt(3000) * 46.75 * 8.0, 61454.5, 1e-4)


# ---- equation-level checks ----

def test_minimum_reinforcement():
    c = footing_a().get("minimum reinforcement, x direction")
    assert near(c.demand, 0.0018 * 30 * 10) and near(c.capacity, 0.93)        # 8.6.1.1
    assert not footing_a(n_x=1).get("minimum reinforcement, x direction").ok


def test_column_without_plate_uses_face_of_column():
    r = footing_a(plate_x_in=None, plate_y_in=None)
    qu = 12160 / 900.0
    assert near(r.get("flexure, x direction").demand, qu * 30 * 13.0 ** 2 / 2 / 12)
    c = r.get("bearing on footing")                                    # A1 = 16, sqrt(A2/A1) capped at 2
    assert near(c.capacity, 0.65 * 2 * 0.85 * 3000 * 16)


def test_soil_over_footing_counts_toward_bearing():
    r = footing_a(soil_depth_ft=2.0, soil_pcf=110)
    assert near(r.values["W_soil"], (6.25 - 36 / 144) * 2.0 * 110)
    assert r.get("soil bearing pressure").demand > 1336.8


def test_bad_input_stops_with_a_message():
    with pytest.raises(FootingInputError, match="bar size"):
        footing_a(bar=11)
    with pytest.raises(FootingInputError, match="both base plate"):
        footing_a(plate_y_in=None)
    with pytest.raises(FootingInputError, match="q_allow_psf"):
        footing_a(q_allow_psf=None)


def test_result_lists_what_is_not_checked():
    assert any("development" in s for s in footing_a().not_checked)


# ---- continuous footing: 2026-011 "Continuous Footing" page (StruCalc Pro) ----

from strukit.footing import check_continuous  # noqa: E402

D_PLF = 112 + 315 + 315 + 298      # Floor Dead, Wall Dead LL, Wall Dead ML, Roof Dead
L_PLF = 297 + 595                  # Floor Live, Roof Live (entered in StruCalc as type Live)


def cont(dead_factor, **kw):
    args = dict(W_ft=2, h_in=10, fc=3000, fy=60000, wall_in=8, bar_t=5, spacing_t_in=12,
                bar_l=5, n_l=2, cover_in=3, P_service_plf=D_PLF + L_PLF, service_combo="D+L",
                Pu_plf=1.2 * D_PLF + 1.6 * L_PLF, strength_combo="1.2D+1.6L+0.5Lr",
                dead_factor=dead_factor, q_allow_psf=1500, conc_pcf=145, stem_h_in=36,
                stem_pcf=145, soil_depth_ft=3.5, soil_pcf=110)
    args.update(kw)
    return check_continuous(**args)


def test_continuous_soil_bearing_matches_strucalc():
    r = cont(1.2)
    assert near(r.get("soil bearing pressure").demand, 1488.5, 1e-4)      # StruCalc 1488.5 / 1500
    assert near(r.values["W_ftg"], 241.6667, 1e-5)                        # StruCalc footing weight
    assert near(r.values["W_stem"], 290.0) and near(r.values["W_soil"], 513.33, 1e-4)


def test_continuous_moment_matches_strucalc_when_stem_weight_is_left_out():
    # StruCalc prints Mu = 297.2 lb-ft, which is the factored wall load alone
    # (2,675.2 lb/ft). It does not add the stem wall's own 290 lb/ft.
    assert near(cont(0).get("flexure").demand, 297.2, 1e-3)


def test_continuous_moment_with_stem_weight_is_higher():
    # StruKit adds 1.2 x 290 lb/ft: the stem wall bears on the footing, so it is part of
    # the factored load (ACI 318-19 13.2.6.3). Mu = 3,023.2/2 psf x (8 in)^2 / 2.
    r = cont(1.2)
    assert near(r.values["Pu_plf"], 2675.2 + 348.0)
    assert near(r.get("flexure").demand, (3023.2 / 2) * (8 / 12) ** 2 / 2)
    assert r.get("flexure").demand > 297.2


def test_continuous_moment_capacity_within_one_percent_of_strucalc():
    # StruCalc 8,816.2 lb-ft (d = 6.625 in back-calculated); d = 10 - 3 - 0.3125 = 6.6875.
    c = cont(1.2).get("flexure")
    a = 0.31 * 60000 / (0.85 * 3000 * 12)
    assert near(c.capacity, 0.9 * 0.31 * 60000 * (6.6875 - a / 2) / 12, 1e-6)
    assert near(c.capacity, 8816.2, 1.1e-2)


def test_continuous_shear_follows_aci_not_strucalc():
    # StruCalc: demand 519.0 (section at d/2), capacity 15,774.4 = 0.75 x 2 sqrt(fc') x 24 x 8.
    # By ruling (2026-11-20): ACI 318-19 Table 22.5.5.1(c), section at d.
    c = cont(0).get("one-way shear")
    assert near(c.demand, 1337.6 / 144 * 12 * (8 - 6.6875))
    rho = 0.31 / (12 * 6.6875)
    assert near(c.capacity, 0.75 * 8 * rho ** (1 / 3) * math.sqrt(3000) * 12 * 6.6875)
    assert near(0.75 * 2 * math.sqrt(3000) * 24 * 8.0, 15774.4, 1e-4)


def test_continuous_minimum_steel_and_masonry_wall():
    r = cont(1.2)
    assert near(r.get("minimum reinforcement, transverse").demand, 0.0018 * 12 * 10)
    assert near(r.get("minimum reinforcement, longitudinal").demand, 0.0018 * 24 * 10)
    assert r.get("minimum reinforcement, longitudinal").ok
    m = cont(1.2, wall_kind="masonry")            # critical section at wall_in / 4 from center
    assert near(m.get("flexure").demand, (3023.2 / 2) * (10 / 12) ** 2 / 2)


def test_continuous_requires_the_dead_factor_and_stem_weight():
    with pytest.raises(FootingInputError, match="dead_factor"):
        cont(None)
    with pytest.raises(FootingInputError, match="stem_pcf"):
        cont(1.2, stem_pcf=None)
