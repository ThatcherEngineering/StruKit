"""Beam statics against closed-form solutions (standard beam formulas).

Reference values are computed from the textbook formulas written beside each test,
not from the solver.
"""
import math

import pytest

from strukit.beam import DistLoad, PointLoad, solve

L, w, P, EI = 20.0, 0.35, 4.0, 3.2e5        # ft, kip/ft, kip, kip-ft^2
TOL = 2e-3                                   # 0.2 %


def near(a, b, tol=TOL):
    return a == pytest.approx(b, rel=tol, abs=1e-9)


def test_simple_span_uniform():
    r = solve(L, [0, L], EI, dist_loads=[DistLoad(0, L, w, w)])
    assert near(r.reactions[0.0], w * L / 2) and near(r.reactions[L], w * L / 2)
    assert near(r.M_max()[0], w * L ** 2 / 8) and near(r.M_max()[1], L / 2, 0.01)
    assert near(r.V_abs_max()[0], w * L / 2)
    assert near(r.defl_max()[0], 5 * w * L ** 4 / (384 * EI))


def test_simple_span_point_at_midspan():
    r = solve(L, [0, L], EI, point_loads=[PointLoad(L / 2, P)])
    assert near(r.M_max()[0], P * L / 4)
    assert near(r.defl_max()[0], P * L ** 3 / (48 * EI))
    assert near(r.reactions[0.0], P / 2)


def test_simple_span_point_off_centre():
    a, b = 6.0, 14.0
    r = solve(L, [0, L], EI, point_loads=[PointLoad(a, P)])
    assert near(r.reactions[0.0], P * b / L) and near(r.reactions[L], P * a / L)
    assert near(r.M_max()[0], P * a * b / L)
    # the max-deflection formula is written for the longer segment as "a": swap them
    g, s = max(a, b), min(a, b)
    dmax = P * g * s * (g + 2 * s) * math.sqrt(3 * g * (g + 2 * s)) / (27 * EI * L)
    assert near(r.defl_max()[0], dmax)


def test_simple_span_triangular_load():
    # load rising from 0 to w; W = wL/2; Mmax = 2WL/(9*sqrt(3)) at x = L/sqrt(3)
    r = solve(L, [0, L], EI, dist_loads=[DistLoad(0, L, 0, w)])
    W = w * L / 2
    assert near(r.reactions[0.0], W / 3) and near(r.reactions[L], 2 * W / 3)
    assert near(r.M_max()[0], 2 * W * L / (9 * math.sqrt(3)))
    assert near(r.defl_max()[0], 0.01304 * W * L ** 3 / EI, 3e-3)


def test_cantilever_uniform_and_end_point():
    r = solve(L, [], EI, fixed=[0.0], dist_loads=[DistLoad(0, L, w, w)])
    assert near(r.M_min()[0], -w * L ** 2 / 2)
    assert near(r.defl_max()[0], w * L ** 4 / (8 * EI))
    assert near(r.reactions[0.0], w * L)
    r = solve(L, [], EI, fixed=[0.0], point_loads=[PointLoad(L, P)])
    assert near(r.M_min()[0], -P * L)
    assert near(r.defl_max()[0], P * L ** 3 / (3 * EI))


def test_two_equal_spans_uniform():
    # each span L: end reactions 3wL/8, middle 10wL/8, M over support -wL^2/8, +M 9wL^2/128
    r = solve(2 * L, [0, L, 2 * L], EI, dist_loads=[DistLoad(0, 2 * L, w, w)])
    assert near(r.reactions[0.0], 3 * w * L / 8)
    assert near(r.reactions[L], 10 * w * L / 8)
    assert near(r.M_min()[0], -w * L ** 2 / 8)
    assert near(r.M_max()[0], 9 * w * L ** 2 / 128)
    assert near(r.defl_max()[0], w * L ** 4 / (185 * EI), 5e-3)


def test_propped_cantilever_uniform():
    # fixed at 0, roller at L: R_roller 3wL/8, M_fixed -wL^2/8, +M 9wL^2/128
    r = solve(L, [L], EI, fixed=[0.0], dist_loads=[DistLoad(0, L, w, w)])
    assert near(r.reactions[L], 3 * w * L / 8) and near(r.reactions[0.0], 5 * w * L / 8)
    assert near(r.M_min()[0], -w * L ** 2 / 8)
    assert near(r.M_max()[0], 9 * w * L ** 2 / 128)


def test_overhang_uniform():
    # span L with overhang a past the right support, uniform w over all
    a = 5.0
    r = solve(L + a, [0, L], EI, dist_loads=[DistLoad(0, L + a, w, w)])
    assert near(r.reactions[0.0], w * (L ** 2 - a ** 2) / (2 * L))
    assert near(r.reactions[L], w * (L + a) ** 2 / (2 * L))
    assert near(r.M_min()[0], -w * a ** 2 / 2)
    assert near(r.M_max()[0], w * (L + a) ** 2 * (L - a) ** 2 / (8 * L ** 2))


def test_partial_uniform_load_and_equilibrium():
    r = solve(L, [0, L], EI, dist_loads=[DistLoad(4, 10, w, w)], point_loads=[PointLoad(15, P)])
    total = w * 6 + P
    assert near(sum(r.reactions.values()), total)
    assert near(r.reactions[L], (w * 6 * 7 + P * 15) / L)          # moments about x = 0


def test_bad_input_is_refused_with_a_plain_message():
    with pytest.raises(ValueError, match="unstable"):
        solve(L, [0], EI)
    with pytest.raises(ValueError, match="off the beam"):
        solve(L, [0, L], EI, point_loads=[PointLoad(25, P)])
