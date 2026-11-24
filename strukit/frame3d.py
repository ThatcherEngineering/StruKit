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

    @staticmethod
    def _kg_local(N, L):
        """Geometric stiffness for axial force N (tension positive): bending terms about both axes (axial and torsional terms left out)."""
        k = np.zeros((12, 12))
        a, b_, c, d = 6.0 / 5, L / 10, 2 * L ** 2 / 15, -L ** 2 / 30
        for (p, q, val) in ((1, 1, a), (1, 5, b_), (1, 7, -a), (1, 11, b_), (5, 5, c), (5, 7, -b_), (5, 11, d), (7, 7, a), (7, 11, -b_), (11, 11, c)):
            k[p, q] = k[q, p] = val
        for (p, q, val) in ((2, 2, a), (2, 4, -b_), (2, 8, -a), (2, 10, -b_), (4, 4, c), (4, 8, b_), (4, 10, d), (8, 8, a), (8, 10, b_), (10, 10, c)):
            k[p, q] = k[q, p] = val
        return k * N / L

    def solve(self, node_loads=None, member_loads=(), second_order=False, n_sub=8, stiffness_factor=1.0, tol=1e-6, max_iter=40):
        """node_loads: {node: (Fx, Fy, Fz, Mx, My, Mz)} global. member_loads: (member, "global" or "local", (wx, wy, wz)) uniform load per
        unit length over the whole member. second_order: includes the effect of joints moving (P-Delta) and of members bowing between
        their ends (P-delta): each member is divided into n_sub elements and the geometric stiffness is built from the member axial
        forces, repeating until they stop changing. stiffness_factor multiplies every stiffness (0.8 for AISC 360-22 C2.3(a)).
        Returns Result3D; with second_order, Result3D.stations holds the forces along each member."""
        if not self.supports:
            raise Frame3DError("frame: no supports")
        nsub = max(1, int(n_sub)) if second_order else 1
        names = list(self.nodes)
        coords = [np.array(self.nodes[nm]) for nm in names]
        idx = {nm: 6 * i for i, nm in enumerate(names)}
        for nd in (node_loads or {}):
            if nd not in idx:
                raise Frame3DError(f"frame: load at joint {nd}, which is not defined")
        by_name = {m.name: m for m in self.members}
        wloc = {m.name: np.zeros(3) for m in self.members}
        geo = {}
        for m in self.members:
            geo[m.name] = self._axes(m)
        for name, frame, w in member_loads:
            if name not in by_name:
                raise Frame3DError(f"frame: load on member {name}, which is not defined")
            R = geo[name][1]
            wloc[name] += np.array(w, dtype=float) if frame == "local" else R @ np.array(w, dtype=float)
        # elements: (member name, k index, dof list, length, T, released local dofs)
        elems, n_nodes = [], len(names)
        for m in self.members:
            L, R = geo[m.name]
            T = np.zeros((12, 12))
            for b in range(4):
                T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
            chain = [idx[m.i]] + [6 * (n_nodes + q) for q in range(nsub - 1)] + [idx[m.j]]
            n_nodes += nsub - 1
            for k in range(nsub):
                rel = ([self.REL[r] for r in m.release_i] if k == 0 else []) + ([6 + self.REL[r] for r in m.release_j] if k == nsub - 1 else [])
                dofs = list(range(chain[k], chain[k] + 6)) + list(range(chain[k + 1], chain[k + 1] + 6))
                elems.append((m.name, k, dofs, L / nsub, T, rel))
        n = 6 * n_nodes
        F0 = np.zeros(n)
        for nd, load in (node_loads or {}).items():
            F0[idx[nd]:idx[nd] + 6] += np.array(load, dtype=float)
        held = [idx[nd] + q for nd, flags in self.supports.items() for q in range(6) if flags[q]]
        hs = set(held)
        free = [i for i in range(n) if i not in hs]

        def fef(name, Le):
            wx, wy, wz = wloc[name]
            f = np.zeros(12)
            f[0] = f[6] = -wx * Le / 2
            f[1] = f[7] = -wy * Le / 2; f[5] = -wy * Le ** 2 / 12; f[11] = wy * Le ** 2 / 12
            f[2] = f[8] = -wz * Le / 2; f[4] = wz * Le ** 2 / 12; f[10] = -wz * Le ** 2 / 12
            return f

        N = {(e[0], e[1]): 0.0 for e in elems}
        U, Kfull, Ffull, store = np.zeros(n), None, None, None
        for it in range(max_iter if second_order else 1):
            K, F, store = np.zeros((n, n)), F0.copy(), []
            for name, k, dofs, Le, T, rel in elems:
                m = by_name[name]
                ke = self._k_local(m, Le) * stiffness_factor
                if second_order:
                    ke = ke + self._kg_local(N[(name, k)], Le)
                ke, fe = self._condense(ke, fef(name, Le), rel)
                store.append((ke, fe))
                K[np.ix_(dofs, dofs)] += T.T @ ke @ T
                F[dofs] -= T.T @ fe
            U = np.zeros(n)
            if free:
                Kff = K[np.ix_(free, free)]
                scale = np.max(np.abs(np.diag(K))) or 1.0
                if np.min(np.abs(np.diag(Kff))) < 1e-12 * scale:
                    raise Frame3DError("frame: a joint is free to move or turn with nothing holding it (check supports and releases)")
                try:
                    if second_order:
                        np.linalg.cholesky(Kff)              # not positive definite: the loads are at or past the buckling load
                    else:
                        cond = np.linalg.cond(Kff)
                        if not np.isfinite(cond) or cond > 1e14:
                            raise np.linalg.LinAlgError
                    U[free] = np.linalg.solve(Kff, F[free])
                except np.linalg.LinAlgError:
                    raise Frame3DError("frame: the frame is not stable under these loads (it buckles or sways without limit)" if second_order else
                                       "frame: the frame is not stable (it can move without resistance); check supports and releases")
            Kfull, Ffull = K, F
            newN, change = {}, 0.0
            for (name, k, dofs, Le, T, rel), (ke, fe) in zip(elems, store):
                q = ke @ (T @ U[dofs]) + fe
                newN[(name, k)] = float(q[6])                # tension positive
                change = max(change, abs(newN[(name, k)] - N[(name, k)]))
            ref = max([abs(v) for v in newN.values()] + [1e-9])
            N = newN
            if not second_order or change <= tol * ref:
                break
        else:
            raise Frame3DError("frame: the second-order analysis did not settle; the frame is close to buckling")
        Rf = Kfull @ U - Ffull
        disp = {nd: tuple(U[idx[nd]:idx[nd] + 6]) for nd in names}
        reactions = {nd: tuple(Rf[idx[nd] + q] if self.supports[nd][q] else 0.0 for q in range(6)) for nd in self.supports}
        ends, axes, stations = {}, {}, {}
        for (name, k, dofs, Le, T, rel), (ke, fe) in zip(elems, store):
            q = ke @ (T @ U[dofs]) + fe
            stations.setdefault(name, []).append((tuple(q[:6]), tuple(q[6:])))
        for m in self.members:
            st_ = stations[m.name]
            ends[m.name] = (st_[0][0], st_[-1][1])
            axes[m.name] = geo[m.name][1]
        res = Result3D(disp, reactions, ends, axes)
        res.stations = stations
        return res
