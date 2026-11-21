"""Plane frame analysis against independent references.

(1) Closed-form portal frame formulas (first-order).
(2) AISC 360-22 Commentary benchmark problems, Figs. C-C2.2 and C-C2.3 (second-order).
(3) AISC Design Examples v16.0, Example C.1A: one-bay moment frame, W12x65 columns 20 ft
    with pinned bases, W18x40 beam 30 ft, a leaning column, direct analysis method.
    Printed LRFD results (Figs. C.1A-3 and C.1A-4):
      first-order : drift 0.181 in; column-top moments 113 and 124 kip-ft;
                    base shears 5.64 and 6.21 kips; vertical reactions 71.6 and 72.4 kips
      second-order: drift 0.290 in; moments 109 and 127 kip-ft;
                    base shears 5.52 and 6.26 kips; vertical reactions 71.4 and 72.6 kips
"""
import numpy as np
import pytest

from strukit import shapes
from strukit.frame2d import Frame, FrameError

E = 29000.0


def portal(h, L, Ic, Ib, A=1e4, base="pin"):
    f = Frame()
    f.node("A", 0, 0); f.node("B", 0, h); f.node("C", L, h); f.node("D", L, 0)
    f.member("col1", "A", "B", E, A, Ic); f.member("beam", "B", "C", E, A, Ib)
    f.member("col2", "D", "C", E, A, Ic)
    f.support("A", base); f.support("D", base)
    return f


def test_portal_lateral_load_pinned_bases():
    # antisymmetric: each base takes H/2 and each corner moment is H h / 2
    f = portal(240, 360, 533, 612)
    r = f.solve({"B": (10.0, 0, 0)})
    assert r.reactions["A"][0] == pytest.approx(-5.0, rel=1e-3) and r.reactions["D"][0] == pytest.approx(-5.0, rel=1e-3)
    assert abs(r.members["col1"].M[-1]) == pytest.approx(10 * 240 / 2, rel=1e-3)
    assert r.reactions["D"][1] == pytest.approx(10 * 240 / 360, rel=1e-3)        # overturning couple


def test_portal_uniform_load_pinned_bases():
    # Kleinlogel: H = w L^2 / (4 h (2k + 3)), k = (Ib / Ic)(h / L); corner moment = H h
    h, L, Ic, Ib, w = 240.0, 360.0, 533.0, 612.0, 0.2
    k = (Ib / Ic) * (h / L)
    H = w * L ** 2 / (4 * h * (2 * k + 3))
    r = portal(h, L, Ic, Ib).solve(member_loads=[("beam", 0, -w, "length")])
    assert r.reactions["A"][0] == pytest.approx(H, rel=2e-3) and r.reactions["A"][1] == pytest.approx(w * L / 2, rel=1e-6)
    assert abs(r.members["beam"].M[0]) == pytest.approx(H * h, rel=2e-3)
    mid = len(r.members["beam"].M) // 2
    assert abs(r.members["beam"].M[mid]) == pytest.approx(w * L ** 2 / 8 - H * h, rel=2e-3)


def test_projected_load_on_a_sloped_rafter():
    f = Frame()
    f.node("A", 0, 0); f.node("B", 120, 50)
    f.member("r", "A", "B", E, 10, 100)
    f.support("A", "pin"); f.support("B", "roller")
    r = f.solve(member_loads=[("r", 0, -0.1, "projected")])
    assert r.reactions["A"][1] + r.reactions["B"][1] == pytest.approx(0.1 * 120, rel=1e-9)


@pytest.mark.parametrize("P,M,D", [(0, 336, 0.901), (100, 469, 1.33), (150, 598, 1.75), (200, 848, 2.56)])
def test_aisc_benchmark_case_2_as_a_frame(P, M, D):
    f = Frame()
    f.node("A", 0, 0); f.node("B", 0, 336)
    f.member("c", "A", "B", E, 14.1, 484); f.support("A", "fixed")
    r = f.solve({"B": (1.0, -float(P), 0)}, second_order=True, n_sub=16)
    assert abs(r.members["c"].M[0]) == pytest.approx(M, rel=0.01)
    assert r.disp["B"][0] == pytest.approx(D, rel=0.01)


@pytest.mark.parametrize("P,M", [(150, 269), (450, 375)])
def test_aisc_benchmark_case_1_as_a_frame(P, M):
    f = Frame()
    f.node("A", 0, 0); f.node("B", 0, 336)
    f.member("c", "A", "B", E, 14.1, 484); f.support("A", "pin")
    f.supports["B"] = (True, False, False)                           # held sideways, free to shorten
    r = f.solve({"B": (0, -float(P), 0)}, member_loads=[("c", 0.2 / 12, 0, "length")], second_order=True, n_sub=16)
    assert r.members["c"].M_abs_max == pytest.approx(M, rel=0.01)


def c1a():
    col, bm = shapes.get("W12x65"), shapes.get("W18x40")
    f = Frame()
    f.node("B0", 0, 0); f.node("B1", 0, 240); f.node("C1", 360, 240); f.node("C0", 360, 0)
    f.node("L0", 720, 0); f.node("L1", 720, 240)
    f.member("colB", "B0", "B1", E, col["A"], col["Ix"]); f.member("colC", "C0", "C1", E, col["A"], col["Ix"])
    f.member("beam", "B1", "C1", E, bm["A"], bm["Ix"])
    f.member("lean", "L0", "L1", E, col["A"], col["Ix"], pin_i=True, pin_j=True)
    f.member("link", "C1", "L1", E, 100.0, 1.0, pin_i=True, pin_j=True)
    for n in ("B0", "C0", "L0"):
        f.support(n, "pin")
    loads = {"B1": (0.576, -36.0, 0), "C1": (0, -36.0, 0), "L1": (0, -144.0, 0)}
    return f, loads, [("beam", 0, -2.40 / 12, "length")]


def test_aisc_example_C1A_first_order():
    f, nl, ml = c1a()
    r = f.solve(nl, ml, stiffness_factor=0.8)
    drift = (r.disp["B1"][0] + r.disp["C1"][0]) / 2
    assert drift == pytest.approx(0.181, rel=0.02)
    assert abs(r.members["colB"].M[-1]) / 12 == pytest.approx(113, rel=0.01)
    assert abs(r.members["colC"].M[-1]) / 12 == pytest.approx(124, rel=0.01)
    assert abs(r.reactions["B0"][0]) == pytest.approx(5.64, rel=0.01) and abs(r.reactions["C0"][0]) == pytest.approx(6.21, rel=0.01)
    assert r.reactions["B0"][1] == pytest.approx(71.6, rel=0.005) and r.reactions["C0"][1] == pytest.approx(72.4, rel=0.005)


def test_aisc_example_C1A_second_order():
    f, nl, ml = c1a()
    r = f.solve(nl, ml, stiffness_factor=0.8, second_order=True)
    drift = (r.disp["B1"][0] + r.disp["C1"][0]) / 2
    assert drift == pytest.approx(0.290, rel=0.03)
    assert abs(r.members["colB"].M[-1]) / 12 == pytest.approx(109, rel=0.015)
    assert abs(r.members["colC"].M[-1]) / 12 == pytest.approx(127, rel=0.015)
    assert abs(r.reactions["B0"][0]) == pytest.approx(5.52, rel=0.015) and abs(r.reactions["C0"][0]) == pytest.approx(6.26, rel=0.015)
    assert r.reactions["B0"][1] == pytest.approx(71.4, rel=0.005) and r.reactions["C0"][1] == pytest.approx(72.6, rel=0.005)
    assert -r.members["colC"].N_min == pytest.approx(72.6, rel=0.01)


def test_unstable_frames_are_reported():
    f = portal(240, 360, 533, 612)
    f.members[1].pin_i = f.members[1].pin_j = True                   # pinned beam on pinned bases: a mechanism
    with pytest.raises(FrameError):
        f.solve({"B": (1.0, 0, 0)})
    g, nl, ml = c1a()
    nl["L1"] = (0, -3000.0, 0)                                       # far past the buckling load
    with pytest.raises(FrameError):
        g.solve(nl, ml, stiffness_factor=0.8, second_order=True)
