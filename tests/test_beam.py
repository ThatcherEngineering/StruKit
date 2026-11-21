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


# ---- second-order analysis: AISC 360-22 Commentary benchmark problems ----
# Figures C-C2.2 and C-C2.3 (W14x48, major axis, Ix = 484 in^4, E = 29,000 ksi, 28 ft).
# Bracketed values (shear deformation excluded) are used, since this solver is an
# Euler-Bernoulli beam. The Commentary asks for agreement within 3 % on moment and
# 5 % on deflection.
import numpy as np
import pytest as _pt

_EI = 29000.0 * 484.0            # kip-in^2
_L = 28 * 12.0


@_pt.mark.parametrize("P,M,D", [(0, 235, 0.197), (150, 269, 0.224), (300, 313, 0.261), (450, 375, 0.311)])
def test_aisc_benchmark_case_1_simply_supported(P, M, D):
    r = solve(_L, [0.0, _L], _EI, dist_loads=[DistLoad(0, _L, 0.2 / 12, 0.2 / 12)], axial=P)
    mid = int(np.argmin(np.abs(r.x - _L / 2)))
    assert r.M[mid] == _pt.approx(M, rel=0.01) and r.defl[mid] == _pt.approx(D, rel=0.01)


@_pt.mark.parametrize("P,M,D", [(0, 336, 0.901), (100, 469, 1.33), (150, 598, 1.75), (200, 848, 2.56)])
def test_aisc_benchmark_case_2_cantilever(P, M, D):
    r = solve(_L, [], _EI, point_loads=[PointLoad(_L, 1.0)], fixed=[0.0], axial=P)
    assert abs(r.M[0]) == _pt.approx(M, rel=0.01) and abs(r.defl[-1]) == _pt.approx(D, rel=0.01)


def test_buckling_load_stops_the_analysis():
    Pe = np.pi ** 2 * _EI / (2 * _L) ** 2                 # cantilever Euler load
    solve(_L, [], _EI, point_loads=[PointLoad(_L, 1.0)], fixed=[0.0], axial=0.98 * Pe)
    with _pt.raises(ValueError):
        solve(_L, [], _EI, point_loads=[PointLoad(_L, 1.0)], fixed=[0.0], axial=1.02 * Pe)


def test_leaning_load_equals_axial_on_a_rigid_link():
    # a load leaning on the tip through a pinned link adds P_lean x (tip drift) / L of
    # sideways push; closed form for tip load H: drift = H / (3EI/L^3 - P_lean/L)
    r = solve(_L, [], _EI, point_loads=[PointLoad(_L, 1.0)], fixed=[0.0], springs=[(_L, -100.0 / _L)])
    assert abs(r.defl[-1]) == _pt.approx(1.0 / (3 * _EI / _L ** 3 - 100.0 / _L), rel=1e-6)
