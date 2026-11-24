"""Beam statics: reactions, shear, moment and deflection for a straight beam.

Pure mechanics (Euler-Bernoulli beam, direct stiffness method). No design code is
involved here; code checks use these demands. Validated against closed-form
solutions in tests/test_beam.py.

Units are the caller's, kept consistent: length L, force F, distributed load F/L,
EI in F*L^2. Sign convention: loads positive DOWN, reactions positive UP,
moment positive when it puts the bottom fibre in tension (sagging),
shear positive when the left part pushes up, deflection positive DOWN.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class PointLoad:
    x: float
    P: float


@dataclass
class DistLoad:
    """Linearly varying load from w1 at x1 to w2 at x2 (uniform when w1 == w2)."""
    x1: float
    x2: float
    w1: float
    w2: float


@dataclass
class BeamResult:
    x: np.ndarray            # stations
    V: np.ndarray            # shear just right of each station
    M: np.ndarray
    defl: np.ndarray         # down positive
    reactions: dict          # support x -> upward force
    fixed_moments: dict      # fixed support x -> moment reaction

    def _ext(self, arr, kind):
        i = int(np.argmax(arr) if kind == "max" else np.argmin(arr))
        return float(arr[i]), float(self.x[i])

    def M_max(self):
        return self._ext(self.M, "max")

    def M_min(self):
        return self._ext(self.M, "min")

    def V_abs_max(self):
        i = int(np.argmax(np.abs(self.V)))
        return float(abs(self.V[i])), float(self.x[i])

    def defl_max(self):
        return self._ext(self.defl, "max")

    def defl_min(self):
        return self._ext(self.defl, "min")


def _w_at(load, x):
    if load.x2 == load.x1:
        return 0.0
    return load.w1 + (load.w2 - load.w1) * (x - load.x1) / (load.x2 - load.x1)


def solve(length, supports, EI, point_loads=(), dist_loads=(), fixed=(), n=400,
          axial=0.0, springs=()):
    """Solve a beam of `length` with pin/roller `supports` (list of x) and optional
    `fixed` supports (list of x, rotation also restrained). A cantilever is
    supports=[], fixed=[0.0]. Overhangs are allowed. `n` = target element count.

    axial: a constant compression force along the member (positive = compression).
    When given, the solution is second-order: the axial force acts on the deflected
    shape, both between the ends (P-delta) and through any movement of one end
    relative to the other (P-Delta), by the geometric stiffness method with the
    member divided into many elements. Moments returned are the true internal
    bending moments. Raises ValueError when the axial force reaches the buckling load.
    springs: (x, k) pairs, a transverse spring of stiffness k at x. A negative k
    models load that leans on the member for stability (k = -P_leaning / height).
    """
    if length <= 0 or EI <= 0:
        raise ValueError("beam: length and EI must be positive")
    # a load or support entered a hair past the end (span lengths typed to four places, 3 x 9.0833 ft against 27.25 ft) is taken at the end
    import dataclasses as _dc
    tol = 0.05                                                          # in.
    snap = lambda x: float(length) if 0 < x - length <= tol else x
    supports = [snap(x) for x in supports]
    fixed = [snap(x) for x in fixed]
    point_loads = [_dc.replace(p_, x=snap(p_.x)) if _dc.is_dataclass(p_) else p_ for p_ in point_loads]
    dist_loads = [_dc.replace(d_, x2=snap(d_.x2)) if _dc.is_dataclass(d_) else d_ for d_ in dist_loads]
    pts = {0.0, float(length)}
    for s in list(supports) + list(fixed):
        if not 0 <= s <= length:
            raise ValueError(f"beam: support at {s} is off the beam (0 to {length})")
        pts.add(float(s))
    for p in point_loads:
        if not 0 <= p.x <= length:
            raise ValueError(f"beam: point load at {p.x} is off the beam")
        pts.add(float(p.x))
    for d in dist_loads:
        if not (0 <= d.x1 < d.x2 <= length):
            raise ValueError(f"beam: distributed load {d.x1} to {d.x2} is not on the beam")
        pts.update((float(d.x1), float(d.x2)))
    if len(set(supports)) + 2 * len(set(fixed)) < 2:
        raise ValueError("beam: not enough supports (unstable)")

    keys = sorted(pts)
    xs = []
    for a, b in zip(keys[:-1], keys[1:]):                 # mesh each segment evenly
        k = max(1, int(round(n * (b - a) / length)))
        xs.extend(np.linspace(a, b, k, endpoint=False))
    xs.append(keys[-1])
    xs = np.array(xs)
    nn = len(xs)
    K = np.zeros((2 * nn, 2 * nn))
    F = np.zeros(2 * nn)
    fef = []                                              # fixed-end forces per element

    for e in range(nn - 1):
        h = xs[e + 1] - xs[e]
        c = EI / h ** 3
        ke = c * np.array([[12, 6 * h, -12, 6 * h],
                           [6 * h, 4 * h * h, -6 * h, 2 * h * h],
                           [-12, -6 * h, 12, -6 * h],
                           [6 * h, 2 * h * h, -6 * h, 4 * h * h]])
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += ke
        if axial:
            kg = axial / (30 * h) * np.array([[36, 3 * h, -36, 3 * h],
                                              [3 * h, 4 * h * h, -3 * h, -h * h],
                                              [-36, -3 * h, 36, -3 * h],
                                              [3 * h, -h * h, -3 * h, 4 * h * h]])
            K[np.ix_(idx, idx)] -= kg
        # consistent nodal loads for a linearly varying load qa..qb (down = +deflection)
        mid = 0.5 * (xs[e] + xs[e + 1])
        qa = sum(_w_at(d, xs[e]) for d in dist_loads if d.x1 <= mid <= d.x2)
        qb = sum(_w_at(d, xs[e + 1]) for d in dist_loads if d.x1 <= mid <= d.x2)
        fe = np.array([h * (7 * qa + 3 * qb) / 20, h * h * (3 * qa + 2 * qb) / 60,
                       h * (3 * qa + 7 * qb) / 20, -h * h * (2 * qa + 3 * qb) / 60])
        F[idx] += fe
        fef.append((ke, fe, idx, qa, qb, h))

    for p in point_loads:
        F[2 * int(np.argmin(np.abs(xs - p.x)))] += p.P

    node = lambda s: int(np.argmin(np.abs(xs - s)))
    for sx, k in springs:
        K[2 * node(sx), 2 * node(sx)] += k
    restrained = sorted({2 * node(s) for s in list(supports) + list(fixed)}
                        | {2 * node(s) + 1 for s in fixed})
    free = [i for i in range(2 * nn) if i not in restrained]
    u = np.zeros(2 * nn)
    if axial or springs:
        try:                                              # stable only while the stiffness matrix is positive definite
            np.linalg.cholesky(K[np.ix_(free, free)])
        except np.linalg.LinAlgError:
            raise ValueError("beam: the axial load reaches or exceeds the buckling load (unstable)")
    try:
        u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    except np.linalg.LinAlgError:
        raise ValueError("beam: the supports do not hold the beam (unstable)")
    R = K @ u - F                                         # forces at restrained dofs (down +)

    V = np.zeros(nn)
    M = np.zeros(nn)
    for e, (ke, fe, idx, qa, qb, h) in enumerate(fef):
        s = ke @ u[idx] - fe                              # element end forces in dof directions
        V[e] = -s[0]                                      # shear just right of node e
        M[e] = s[1]
        if e == nn - 2:
            V[e + 1] = s[2]
            M[e + 1] = -s[3]
    return BeamResult(
        x=xs, V=V, M=M, defl=u[0::2],
        reactions={float(s): float(-R[2 * node(s)]) for s in list(supports) + list(fixed)},
        fixed_moments={float(s): float(R[2 * node(s) + 1]) for s in fixed})
