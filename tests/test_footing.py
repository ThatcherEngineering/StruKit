"""Isolated footing checks against ACI 318-19 and a real job.

Reference job: Thatcher Engineering 2026-011 (Humbargar Residence addition), sealed calc
package of April 2026, "Footing A" page, produced with StruCalc Pro. The numbers below
are the values printed on that page.

STATUS: partly validated. Soil pressure, factored moment and bearing match StruCalc
exactly. The shear checks do NOT match StruCalc and are not expected to: see the two
tests named "..._differs_from_strucalc". Those differences are waiting on the
engineer's ruling (recorded in STRUKIT-RULINGS.md when made).
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
