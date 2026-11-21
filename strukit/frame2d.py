"""Plane frame analysis: any arrangement of straight members in a vertical plane
(one bay or many, one story or many, sloped rafters, leaning columns).

Pure mechanics (direct stiffness method, Euler-Bernoulli members with axial
deformation). No design code is involved here; the stability rules of AISC 360-22
Chapter C (reduced stiffness, notional loads, load level) are applied by the caller.

First-order analysis, or second-order analysis that includes both the effect of
joints moving sideways (P-Delta) and of members bowing between their ends (P-delta):
each member is divided into several elements and the geometric stiffness is built
from the member axial forces, repeating until the axial forces stop changing.
Validated in tests/test_frame2d.py against the AISC 360-22 Commentary benchmark
problems and AISC Design Example C.1A.

Units are the caller's, kept consistent (for example kips and inches).
Global axes: x to the right, y up. Loads are forces in +x / +y (gravity is negative
y); moments and rotations are counter-clockwise positive.
Member results use the member's own axis from end i to end j: N is axial force
(tension positive), V is shear, M is bending moment (positive when it puts the fibre on
the member's right-hand side, looking from i to j, in tension).
"""
from dataclasses import dataclass, field

import numpy as np


class FrameError(ValueError):
    pass


@dataclass
class Member:
    name: str
    i: str                       # node names
    j: str
    E: float
    A: float
    I: float
    pin_i: bool = False          # moment release (pin) at the i / j end
    pin_j: bool = False


@dataclass
class MemberResult:
    s: np.ndarray                # distance from end i
    N: np.ndarray
    V: np.ndarray
    M: np.ndarray
    length: float

    @property
    def M_abs_max(self):
        return float(np.max(np.abs(self.M)))

    @property
    def V_abs_max(self):
        return float(np.max(np.abs(self.V)))

    @property
    def N_min(self):             # largest compression (negative)
        return float(np.min(self.N))


@dataclass
class FrameResult:
    disp: dict                   # node -> (ux, uy, rz)
    reactions: dict              # supported node -> (Rx, Ry, Mz)
    members: dict                # member name -> MemberResult
    iterations: int = 1


@dataclass
class Frame:
    nodes: dict = field(default_factory=dict)        # name -> (x, y)
    members: list = field(default_factory=list)
    supports: dict = field(default_factory=dict)     # node -> (fix_x, fix_y, fix_rotation)

    def node(self, name, x, y):
        self.nodes[name] = (float(x), float(y))

    def member(self, name, i, j, E, A, I, pin_i=False, pin_j=False):
        for n in (i, j):
            if n not in self.nodes:
                raise FrameError(f"frame: member {name} uses node {n}, which is not defined")
        if any(m.name == name for m in self.members):
            raise FrameError(f"frame: two members are named {name}")
        self.members.append(Member(name, i, j, E, A, I, pin_i, pin_j))

    def support(self, node, kind):
        """kind: "pin" (no movement, free to rotate), "fixed", or "roller" (held
        vertically only)."""
        kinds = {"pin": (True, True, False), "fixed": (True, True, True), "roller": (False, True, False)}
        if kind not in kinds:
            raise FrameError("frame: support kind must be pin, fixed or roller")
        if node not in self.nodes:
            raise FrameError(f"frame: support at node {node}, which is not defined")
        self.supports[node] = kinds[kind]

    # ------------------------------------------------------------------ analysis
    def solve(self, node_loads=None, member_loads=(), second_order=False, n_sub=8,
              stiffness_factor=1.0, flexural_factors=None, tol=1e-6, max_iter=30):
        """node_loads: node -> (Fx, Fy, Mz).
        member_loads: (member name, wx, wy, kind) with kind "length" (force per unit
        length of the member) or "projected" (force per unit horizontal length, the
        usual way to give snow on a sloped rafter).
        stiffness_factor multiplies every EA and EI (0.8 for AISC 360-22 C2.3(a));
        flexural_factors: member name -> extra factor on that member's EI (tau_b)."""
        node_loads = node_loads or {}
        flexural_factors = flexural_factors or {}
        if not self.supports:
            raise FrameError("frame: no supports")
        names = list(self.nodes)
        idx = {n: k for k, n in enumerate(names)}
        ndof = 3 * len(names)
        # elements: (member, k, xi, yi, xj, yj, dofs, EA, EI)
        elems, extra = [], []
        coords = []
        for m in self.members:
            (xi, yi), (xj, yj) = self.nodes[m.i], self.nodes[m.j]
            L = float(np.hypot(xj - xi, yj - yi))
            if L <= 0:
                raise FrameError(f"frame: member {m.name} has no length")
            EA = m.E * m.A * stiffness_factor
            EI = m.E * m.I * stiffness_factor * flexural_factors.get(m.name, 1.0)
            # dof triplets along the member
            trip = []
            for k in range(n_sub + 1):
                if k == 0:
                    base = 3 * idx[m.i]
                elif k == n_sub:
                    base = 3 * idx[m.j]
                else:
                    base = ndof; ndof += 3
                t = [base, base + 1, base + 2]
                if (k == 0 and m.pin_i) or (k == n_sub and m.pin_j):
                    t[2] = ndof; ndof += 1                        # private rotation: a pin
                trip.append(t)
            for k in range(n_sub):
                a, b = k / n_sub, (k + 1) / n_sub
                elems.append((m.name, k, xi + a * (xj - xi), yi + a * (yj - yi),
                              xi + b * (xj - xi), yi + b * (yj - yi), trip[k] + trip[k + 1], EA, EI))

        F = np.zeros(ndof)
        for n, (fx, fy, mz) in node_loads.items():
            if n not in idx:
                raise FrameError(f"frame: load on node {n}, which is not defined")
            F[3 * idx[n]:3 * idx[n] + 3] += (fx, fy, mz)
        wmap = {}
        for name, wx, wy, kind in member_loads:
            m = next((mm for mm in self.members if mm.name == name), None)
            if m is None:
                raise FrameError(f"frame: load on member {name}, which is not defined")
            if kind not in ("length", "projected"):
                raise FrameError("frame: member load kind must be length or projected")
            if kind == "projected":
                (xi, yi), (xj, yj) = self.nodes[m.i], self.nodes[m.j]
                f = abs(xj - xi) / float(np.hypot(xj - xi, yj - yi))
                wx, wy = wx * f, wy * f
            a = wmap.get(name, (0.0, 0.0))
            wmap[name] = (a[0] + wx, a[1] + wy)

        def local(e):
            _, _, x1, y1, x2, y2, dofs, EA, EI = e
            L = float(np.hypot(x2 - x1, y2 - y1))
            c, s = (x2 - x1) / L, (y2 - y1) / L
            T = np.zeros((6, 6))
            T[0, 0] = T[1, 1] = T[3, 3] = T[4, 4] = c
            T[0, 1] = T[3, 4] = s
            T[1, 0] = T[4, 3] = -s
            T[2, 2] = T[5, 5] = 1.0
            a, b = EA / L, EI / L ** 3
            ke = np.array([[a, 0, 0, -a, 0, 0],
                           [0, 12 * b, 6 * b * L, 0, -12 * b, 6 * b * L],
                           [0, 6 * b * L, 4 * b * L * L, 0, -6 * b * L, 2 * b * L * L],
                           [-a, 0, 0, a, 0, 0],
                           [0, -12 * b, -6 * b * L, 0, 12 * b, -6 * b * L],
                           [0, 6 * b * L, 2 * b * L * L, 0, -6 * b * L, 4 * b * L * L]])
            return L, c, s, T, ke

        loc = [local(e) for e in elems]
        fef = []
        for e, (L, c, s, T, ke) in zip(elems, loc):
            wx, wy = wmap.get(e[0], (0.0, 0.0))
            qa, qp = wx * c + wy * s, -wx * s + wy * c
            fl = np.array([qa * L / 2, qp * L / 2, qp * L * L / 12, qa * L / 2, qp * L / 2, -qp * L * L / 12])
            fef.append(fl)
            F[e[6]] += T.T @ fl

        fixed = set()
        for n, (fx, fy, fr) in self.supports.items():
            b = 3 * idx[n]
            fixed |= {b + k for k, on in enumerate((fx, fy, fr)) if on}

        def assemble(axial):
            K = np.zeros((ndof, ndof))
            for k, (e, (L, c, s, T, ke)) in enumerate(zip(elems, loc)):
                kl = ke
                if axial is not None and axial[k] != 0.0:
                    N = axial[k]
                    g = N / (30 * L)
                    kg = g * np.array([[0, 0, 0, 0, 0, 0],
                                       [0, 36, 3 * L, 0, -36, 3 * L],
                                       [0, 3 * L, 4 * L * L, 0, -3 * L, -L * L],
                                       [0, 0, 0, 0, 0, 0],
                                       [0, -36, -3 * L, 0, 36, -3 * L],
                                       [0, 3 * L, -L * L, 0, -3 * L, 4 * L * L]])
                    kl = ke + kg
                d = e[6]
                K[np.ix_(d, d)] += T.T @ kl @ T
            return K

        def run(axial):
            K = assemble(axial)
            dead = {i for i in range(ndof) if abs(K[i, i]) < 1e-12}     # rotation with nothing attached
            free = [i for i in range(ndof) if i not in fixed and i not in dead]
            Kff = K[np.ix_(free, free)]
            ev = np.linalg.eigvalsh(Kff)[0]
            if ev <= 1e-9 * float(np.max(np.abs(np.diag(Kff)))):
                raise FrameError("frame: unstable" + (" under this load (the load reaches the "
                                 "buckling load of the frame)" if axial is not None else
                                 " (the supports and joints do not hold it; check for too many pins)"))
            u = np.zeros(ndof)
            u[free] = np.linalg.solve(Kff, F[free])
            return K, u

        def element_forces(u):
            out = []
            for e, (L, c, s, T, ke), fl in zip(elems, loc, fef):
                out.append(ke @ (T @ u[e[6]]) - fl)                 # end forces in local dof directions
            return out

        K, u = run(None)
        its = 1
        if second_order:
            prev = None
            for its in range(2, max_iter + 2):
                axial = np.array([f[3] for f in element_forces(u)])   # tension positive
                if prev is not None and np.max(np.abs(axial - prev)) <= tol * max(1.0, np.max(np.abs(axial))):
                    break
                prev = axial
                K, u = run(axial)
            else:
                raise FrameError("frame: the second-order analysis did not settle")
        ef = element_forces(u)
        R = K @ u - F
        res = FrameResult({n: tuple(float(v) for v in u[3 * idx[n]:3 * idx[n] + 3]) for n in names},
                          {n: tuple(float(R[3 * idx[n] + k]) if on else 0.0 for k, on in enumerate(self.supports[n]))
                           for n in self.supports}, {}, its)
        for m in self.members:
            rows = [(k, f, loc[q][0]) for q, (e, f) in enumerate(zip(elems, ef)) if e[0] == m.name
                    for k in [e[1]]]
            rows.sort(key=lambda r: r[0])
            s_, N_, V_, M_ = [0.0], [], [], []
            for k, f, L in rows:
                N_.append(-f[0]); V_.append(f[1]); M_.append(-f[2])
                s_.append(s_[-1] + L)
            k, f, L = rows[-1]
            N_.append(f[3]); V_.append(-f[4]); M_.append(f[5])
            res.members[m.name] = MemberResult(np.array(s_), np.array(N_), np.array(V_), np.array(M_), s_[-1])
        return res
