"""Space frame engine: closed-form solutions, the plane-frame engine for frames in a vertical plane, and rotation of the structure in space."""
import math
import numpy as np
import pytest
from strukit.frame2d import Frame
from strukit.frame3d import Frame3D, Frame3DError

E, G = 29000.0, 11200.0
SEC = dict(A=10.0, Iy=300.0, Iz=50.0, J=2.0)


def test_cantilever_closed_form():
    L = 120.0
    f = Frame3D(); f.node("a", 0, 0, 0); f.node("b", L, 0, 0); f.member("m", "a", "b", E, G, **SEC); f.support("a", "fixed")
    r = f.solve({"b": (5.0, 2.0, -3.0, 40.0, 0, 0)})
    ux, uy, uz, rx, ry, rz = r.disp["b"]
    assert ux == pytest.approx(5 * L / (E * 10)) and uz == pytest.approx(-3 * L ** 3 / (3 * E * 300)) and uy == pytest.approx(2 * L ** 3 / (3 * E * 50))
    assert rx == pytest.approx(40 * L / (G * 2)) and ry == pytest.approx(3 * L ** 2 / (2 * E * 300)) and rz == pytest.approx(2 * L ** 2 / (2 * E * 50))
    R = r.reactions["a"]
    assert R[:3] == pytest.approx((-5, -2, 3)) and R[3] == pytest.approx(-40) and R[4] == pytest.approx(-3 * L) and R[5] == pytest.approx(-2 * L)


def test_uniform_load_fixed_and_pinned():
    L, w = 240.0, 0.1
    f = Frame3D(); f.node("a", 0, 0, 0); f.node("b", L, 0, 0); f.member("m", "a", "b", E, G, **SEC); f.support("a", "fixed"); f.support("b", "fixed")
    r = f.solve(member_loads=[("m", "global", (0, 0, -w))])
    assert r.reactions["a"][2] == pytest.approx(w * L / 2) and abs(r.reactions["a"][4]) == pytest.approx(w * L ** 2 / 12)
    g = Frame3D(); g.node("a", 0, 0, 0); g.node("c", L / 2, 0, 0); g.node("b", L, 0, 0)
    g.member("m1", "a", "c", E, G, **SEC); g.member("m2", "c", "b", E, G, **SEC)
    g.support("a", (1, 1, 1, 1, 0, 0)); g.support("b", (0, 1, 1, 0, 0, 0))
    r = g.solve(member_loads=[("m1", "global", (0, 0, -w)), ("m2", "global", (0, 0, -w))])
    assert r.disp["c"][2] == pytest.approx(-5 * w * L ** 4 / (384 * E * 300)) and r.reactions["a"][2] == pytest.approx(w * L / 2)
    assert abs(r.ends["m1"][1][4]) == pytest.approx(w * L ** 2 / 8)                       # mid-span moment about the strong axis


def test_release_makes_a_propped_cantilever():
    L, w = 200.0, 0.05
    f = Frame3D(); f.node("a", 0, 0, 0); f.node("b", L, 0, 0); f.member("m", "a", "b", E, G, release_j=("my",), **SEC); f.support("a", "fixed"); f.support("b", "fixed")
    r = f.solve(member_loads=[("m", "global", (0, 0, -w))])
    assert r.reactions["b"][2] == pytest.approx(3 * w * L / 8) and r.reactions["a"][2] == pytest.approx(5 * w * L / 8)
    assert abs(r.reactions["a"][4]) == pytest.approx(w * L ** 2 / 8) and abs(r.ends["m"][1][4]) < 1e-9


def _portal2d():
    f = Frame()
    f.node("a", 0, 0); f.node("b", 0, 144); f.node("c", 240, 144); f.node("d", 240, 0)
    f.member("c1", "a", "b", E, 10.0, 300.0); f.member("bm", "b", "c", E, 12.0, 500.0); f.member("c2", "d", "c", E, 10.0, 300.0)
    f.support("a", "fixed"); f.support("d", "pin")
    return f.solve(node_loads={"b": (8.0, 0.0, 0.0)}, member_loads=[("bm", "uniform", -0.2)] if False else ())


def _portal3d(angle_deg, wload=True):
    """The same portal standing in a vertical plane turned `angle_deg` about Z."""
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    P = lambda x, z: (x * c, x * s, z)
    f = Frame3D()
    for n, (x, z) in dict(a=(0, 0), b=(0, 144), c=(240, 144), d=(240, 0)).items():
        f.node(n, *P(x, z))
    out = (-s, c, 0.0)                                               # out of the frame's plane
    # columns: bending in the plane of the frame is about the axis normal to the plane; give them 'up' = that normal so Iz is the in-plane inertia
    f.member("c1", "a", "b", E, G, A=10.0, Iy=77.0, Iz=300.0, J=3.0, up=out); f.member("c2", "d", "c", E, G, A=10.0, Iy=77.0, Iz=300.0, J=3.0, up=out)
    f.member("bm", "b", "c", E, G, A=12.0, Iy=500.0, Iz=40.0, J=3.0)
    # hold the frame in its plane at the top joints (no out-of-plane load anyway)
    f.support("a", "fixed"); f.support("d", "pin")
    loads = {"b": (8.0 * c, 8.0 * s, 0.0, 0, 0, 0)}
    return f, f.solve(loads, [("bm", "global", (0, 0, -0.2))] if wload else ())


def test_plane_portal_matches_frame2d_at_any_angle():
    f2 = Frame()
    f2.node("a", 0, 0); f2.node("b", 0, 144); f2.node("c", 240, 144); f2.node("d", 240, 0)
    f2.member("c1", "a", "b", E, 10.0, 300.0); f2.member("bm", "b", "c", E, 12.0, 500.0); f2.member("c2", "d", "c", E, 10.0, 300.0)
    f2.support("a", "fixed"); f2.support("d", "pin")
    r2 = f2.solve(node_loads={"b": (8.0, 0.0, 0.0)})
    for ang in (0.0, 37.0, 90.0):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        _, r3 = _portal3d(ang, wload=False)
        for nd in ("b", "c"):
            u = r3.disp[nd]
            assert u[0] * c + u[1] * s == pytest.approx(r2.disp[nd][0], rel=1e-8) and u[2] == pytest.approx(r2.disp[nd][1], rel=1e-8, abs=1e-12)
            assert abs(-u[0] * s + u[1] * c) < 1e-9                                       # nothing moves out of the plane
        for nd in ("a", "d"):
            R = r3.reactions[nd]
            assert R[0] * c + R[1] * s == pytest.approx(r2.reactions[nd][0], rel=1e-8) and R[2] == pytest.approx(r2.reactions[nd][1], rel=1e-8)
        Ma = r3.reactions["a"]
        assert abs(-Ma[3] * s + Ma[4] * c) == pytest.approx(abs(r2.reactions["a"][2]), rel=1e-8)   # base moment about the normal to the plane


def test_equilibrium_of_a_space_frame():
    f = Frame3D()
    pts = dict(a=(0, 0, 0), b=(200, 0, 0), c=(200, 150, 0), d=(0, 150, 0), e=(0, 0, 120), g=(200, 0, 120), h=(200, 150, 120), i=(0, 150, 120))
    for n, p in pts.items():
        f.node(n, *p)
    for k, (i_, j_) in enumerate((("a", "e"), ("b", "g"), ("c", "h"), ("d", "i"))):
        f.member(f"col{k}", i_, j_, E, G, **SEC)
    for k, (i_, j_) in enumerate((("e", "g"), ("g", "h"), ("h", "i"), ("i", "e"))):
        f.member(f"bm{k}", i_, j_, E, G, **SEC)
    for n in "abcd":
        f.support(n, "fixed")
    loads = {"e": (6.0, 0, 0, 0, 0, 0), "h": (0, -4.0, -10.0, 0, 0, 25.0)}
    w = [("bm0", "global", (0, 0, -0.08)), ("bm2", "global", (0, 0.03, -0.05))]
    r = f.solve(loads, w)
    tot = np.zeros(3); mom = np.zeros(3)
    for n, R in r.reactions.items():
        tot += R[:3]; mom += np.array(R[3:]) + np.cross(pts[n], R[:3])
    app = np.zeros(3); mapp = np.zeros(3)
    for n, L in loads.items():
        app += L[:3]; mapp += np.array(L[3:]) + np.cross(pts[n], L[:3])
    for name, _, wv in w:
        m = next(x for x in f.members if x.name == name)
        a, b = np.array(pts[m.i]), np.array(pts[m.j])
        Fw = np.array(wv) * np.linalg.norm(b - a)
        app += Fw; mapp += np.cross((a + b) / 2, Fw)
    assert tot == pytest.approx(-app, abs=1e-8) and mom == pytest.approx(-mapp, abs=1e-6)
    # each member's end forces balance its own load
    q_i, q_j = r.ends["bm0"]
    assert q_i[0] + q_j[0] == pytest.approx(0, abs=1e-9) and q_i[2] + q_j[2] == pytest.approx(0.08 * 200, abs=1e-8)


def test_unstable_and_bad_input():
    f = Frame3D(); f.node("a", 0, 0, 0); f.node("b", 100, 0, 0); f.member("m", "a", "b", E, G, **SEC); f.support("a", "pin")
    with pytest.raises(Frame3DError, match="not stable|free to move"):
        f.solve({"b": (0, 0, -1, 0, 0, 0)})
    with pytest.raises(Frame3DError, match="not defined"):
        f.member("x", "a", "zz", E, G, **SEC)
