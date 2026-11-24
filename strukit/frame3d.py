"""Space frame analysis: straight members in any direction, six degrees of freedom at each joint.

Pure mechanics (direct stiffness method, Euler-Bernoulli members with axial and torsional deformation; shear deformation is not
included). First-order (linear) analysis. No design code is involved here.

Units are the caller's, kept consistent (for example kips and inches). Global axes: X and Y in plan, Z up (gravity is negative Z).
Member axes: x from end i to end j; z is the member's "up" (for a member that is not vertical, the local z lies in the vertical plane
through the member, on the +Z side; for a vertical member local z is global X unless `up` is given); y completes the right-handed set.
Iy is the moment of inertia for bending about local y (the strong axis of a beam with its web vertical), Iz about local z.

Member end forces are returned in member axes at each end, as the forces the joint puts on the member end: (Fx, Fy, Fz, Mx, My, Mz).
Validated in tests/test_frame3d.py against closed-form solutions, against the plane-frame engine (frame2d.py, itself checked against
the AISC benchmark problems) for frames lying in a vertical plane, and for rotation of the whole structure in space.
"""
from dataclasses import dataclass, field

import numpy as np


class Frame3DError(ValueError):
    pass


@dataclass
class Member3D:
    name: str
    i: str
    j: str
    E: float
    G: float
    A: float
    Iy: float
    Iz: float
    J: float
    up: tuple = None             # a vector that, with the member axis, fixes local z; None = the default described above
    release_i: tuple = ()        # local rotations released at the end: any of "my", "mz", "mx"
    release_j: tuple = ()


@dataclass
class Result3D:
    disp: dict                   # node -> (ux, uy, uz, rx, ry, rz), global
    reactions: dict              # supported node -> (Fx, Fy, Fz, Mx, My, Mz), global
    ends: dict                   # member -> (forces at i, forces at j), member axes
    axes: dict = field(default_factory=dict)   # member -> 3x3 matrix, rows = local x, y, z in global components


SUPPORTS = {"fixed": (1, 1, 1, 1, 1, 1), "pin": (1, 1, 1, 0, 0, 0), "roller_z": (0, 0, 1, 0, 0, 0)}


class Frame3D:
    def __init__(self):
        self.nodes, self.members, self.supports = {}, [], {}

    def node(self, name, x, y, z):
        self.nodes[name] = (float(x), float(y), float(z))

    def member(self, name, i, j, E, G, A, Iy, Iz, J, up=None, release_i=(), release_j=()):
        for n in (i, j):
            if n not in self.nodes:
                raise Frame3DError(f"frame: member {name} uses joint {n}, which is not defined")
        if any(m.name == name for m in self.members):
            raise Frame3DError(f"frame: two members are named {name}")
        if min(E, G, A, Iy, Iz, J) <= 0:
            raise Frame3DError(f"frame: member {name} needs positive E, G, A, Iy, Iz and J")
        self.members.append(Member3D(name, i, j, E, G, A, Iy, Iz, J, up, tuple(release_i), tuple(release_j)))

    def support(self, node, kind):
        """kind: "fixed", "pin", "roller_z", or six 0/1 flags (ux, uy, uz, rx, ry, rz), 1 = held."""
        if node not in self.nodes:
            raise Frame3DError(f"frame: support at joint {node}, which is not defined")
        flags = SUPPORTS.get(kind) if isinstance(kind, str) else tuple(int(bool(f)) for f in kind)
        if flags is None or len(flags) != 6:
            raise Frame3DError("frame: a support is fixed, pin, roller_z, or six 0/1 flags")
        self.supports[node] = flags

    # ---- member geometry and stiffness
    def _axes(self, m):
        a, b = np.array(self.nodes[m.i]), np.array(self.nodes[m.j])
        d = b - a
        L = float(np.linalg.norm(d))
        if L < 1e-9:
            raise Frame3DError(f"frame: member {m.name} has no length")
        x = d / L
        if m.up is not None:
            ref = np.array(m.up, dtype=float)
        elif abs(x[2]) > 1 - 1e-9:
            ref = np.array([1.0, 0.0, 0.0])                  # vertical member: local z is global X
        else:
            ref = np.array([0.0, 0.0, 1.0])
        z = ref - np.dot(ref, x) * x
        nz = np.linalg.norm(z)
        if nz < 1e-9:
            raise Frame3DError(f"frame: member {m.name}: its 'up' direction is along the member")
        z = z / nz
        y = np.cross(z, x)
        return L, np.vstack([x, y, z])

    @staticmethod
    def _k_local(m, L):
        k = np.zeros((12, 12))
        EA, GJ, EIy, EIz = m.E * m.A / L, m.G * m.J / L, m.E * m.Iy, m.E * m.Iz
        k[0, 0] = k[6, 6] = EA; k[0, 6] = k[6, 0] = -EA
        k[3, 3] = k[9, 9] = GJ; k[3, 9] = k[9, 3] = -GJ
        # bending about local z (deflection in y): dofs uy (1, 7), rz (5, 11)
        a, b_, c, d = 12 * EIz / L ** 3, 6 * EIz / L ** 2, 4 * EIz / L, 2 * EIz / L
        for (p, q, val) in ((1, 1, a), (1, 5, b_), (1, 7, -a), (1, 11, b_), (5, 5, c), (5, 7, -b_), (5, 11, d), (7, 7, a), (7, 11, -b_), (11, 11, c)):
            k[p, q] = k[q, p] = val
        # bending about local y (deflection in z): dofs uz (2, 8), ry (4, 10); the sign of the coupling terms is opposite
        a, b_, c, d = 12 * EIy / L ** 3, 6 * EIy / L ** 2, 4 * EIy / L, 2 * EIy / L
        for (p, q, val) in ((2, 2, a), (2, 4, -b_), (2, 8, -a), (2, 10, -b_), (4, 4, c), (4, 8, b_), (4, 10, d), (8, 8, a), (8, 10, b_), (10, 10, c)):
            k[p, q] = k[q, p] = val
        return k

    @staticmethod
    def _condense(k, f, released):
        """Static condensation of released (zero-moment) local dofs: returns the stiffness and fixed-end forces with those dofs removed
        (rows and columns zeroed), so the element carries no moment there."""
        if not released:
            return k, f
        r = sorted(released)
        keep = [i for i in range(12) if i not in r]
        krr = k[np.ix_(r, r)]
        try:
            inv = np.linalg.inv(krr)
        except np.linalg.LinAlgError:
            raise Frame3DError("frame: a member's releases leave it a mechanism")
        kk = k[np.ix_(keep, keep)] - k[np.ix_(keep, r)] @ inv @ k[np.ix_(r, keep)]
        ff = f[keep] - k[np.ix_(keep, r)] @ inv @ f[r]
        K2, F2 = np.zeros((12, 12)), np.zeros(12)
        K2[np.ix_(keep, keep)] = kk
        F2[keep] = ff
        return K2, F2

    REL = {"mx": 3, "my": 4, "mz": 5}

    def solve(self, node_loads=None, member_loads=()):
        """node_loads: {node: (Fx, Fy, Fz, Mx, My, Mz)} global. member_loads: (member, "global" or "local", (wx, wy, wz)) uniform load per
        unit length over the whole member. Returns Result3D."""
        names = list(self.nodes)
        idx = {n: 6 * i for i, n in enumerate(names)}
        n = 6 * len(names)
        K, F = np.zeros((n, n)), np.zeros(n)
        for nd, load in (node_loads or {}).items():
            if nd not in idx:
                raise Frame3DError(f"frame: load at joint {nd}, which is not defined")
            F[idx[nd]:idx[nd] + 6] += np.array(load, dtype=float)
        by_name = {m.name: m for m in self.members}
        fef = {m.name: np.zeros(12) for m in self.members}          # fixed-end forces, local
        geo = {}
        for m in self.members:
            L, R = self._axes(m)
            T = np.zeros((12, 12))
            for b in range(4):
                T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
            geo[m.name] = (L, R, T)
        for name, frame, w in member_loads:
            if name not in by_name:
                raise Frame3DError(f"frame: load on member {name}, which is not defined")
            L, R, T = geo[name]
            wl = np.array(w, dtype=float) if frame == "local" else R @ np.array(w, dtype=float)
            wx, wy, wz = wl
            f = np.zeros(12)
            f[0] = f[6] = -wx * L / 2
            f[1] = f[7] = -wy * L / 2; f[5] = -wy * L ** 2 / 12; f[11] = wy * L ** 2 / 12
            f[2] = f[8] = -wz * L / 2; f[4] = wz * L ** 2 / 12; f[10] = -wz * L ** 2 / 12
            fef[name] += f
        store = {}
        for m in self.members:
            L, R, T = geo[m.name]
            rel = [self.REL[r] for r in m.release_i] + [6 + self.REL[r] for r in m.release_j]
            k, f = self._condense(self._k_local(m, L), fef[m.name], rel)
            store[m.name] = (k, f, T)
            dofs = list(range(idx[m.i], idx[m.i] + 6)) + list(range(idx[m.j], idx[m.j] + 6))
            K[np.ix_(dofs, dofs)] += T.T @ k @ T
            F[dofs] -= T.T @ f
        held = [idx[nd] + q for nd, flags in self.supports.items() for q in range(6) if flags[q]]
        free = [i for i in range(n) if i not in set(held)]
        if not held:
            raise Frame3DError("frame: no supports")
        U = np.zeros(n)
        if free:
            Kff = K[np.ix_(free, free)]
            scale = np.max(np.abs(np.diag(K))) or 1.0
            if np.min(np.abs(np.diag(Kff))) < 1e-12 * scale:
                raise Frame3DError("frame: a joint is free to move or turn with nothing holding it (check supports and releases)")
            try:
                cond = np.linalg.cond(Kff)
                if not np.isfinite(cond) or cond > 1e14:
                    raise np.linalg.LinAlgError
                U[free] = np.linalg.solve(Kff, F[free])
            except np.linalg.LinAlgError:
                raise Frame3DError("frame: the frame is not stable (it can move without resistance); check supports and releases")
        Rf = K @ U - F
        disp = {nd: tuple(U[idx[nd]:idx[nd] + 6]) for nd in names}
        reactions = {nd: tuple(Rf[idx[nd] + q] if self.supports[nd][q] else 0.0 for q in range(6)) for nd in self.supports}
        ends, axes = {}, {}
        for m in self.members:
            k, f, T = store[m.name]
            dofs = list(range(idx[m.i], idx[m.i] + 6)) + list(range(idx[m.j], idx[m.j] + 6))
            q = k @ (T @ U[dofs]) + f
            ends[m.name] = (tuple(q[:6]), tuple(q[6:]))
            axes[m.name] = geo[m.name][1]
        return Result3D(disp, reactions, ends, axes)
