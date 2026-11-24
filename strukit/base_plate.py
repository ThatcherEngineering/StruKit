"""Column base plate under centred axial compression.

Sources on file:
  ANSI/AISC 360-22 Sect. J8: bearing on concrete, Eq. J8-1 and J8-2, phi_c = 0.65,
      Omega_c = 2.31.
  AISC Manual Part 14 plate-thickness method, Eq. 14-2 to 14-7, as printed in AISC Design
      Examples v16.0, Example J.6 (the Manual itself is not on file; the equations are
      taken from that example, which also gives the reference values the tests use).

Covered: concrete bearing under the plate; minimum plate thickness for the cantilever
strips m and n and for the yield line between the column flanges (lambda n').
Not covered: moment or uplift at the base, shear transfer, anchor rods, the weld of the
column to the plate, grout.

Units: kips, inches, ksi.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import Line, SteelInputError


@dataclass
class BasePlateResult:
    Pp: float                    # nominal bearing strength
    P_avail: float
    t_min: float
    lines: list = field(default_factory=list)


def similar_area(N, B, support_N, support_B):
    """A2: the largest area of the support that is geometrically similar to and
    concentric with the plate (AISC 360-22 J8)."""
    k = min(support_N / N, support_B / B)
    if k < 1 - 1e-9:
        raise SteelInputError("base plate: the plate is larger than the concrete support")
    return N * B * k * k


def check(d, bf, N, B, Fy_plate, fc, A2, Pr, method="ASD", kind="I"):
    """d, bf: column depth and flange width. N: plate length (parallel to d); B: plate
    width. fc in ksi. A2: similar concentric support area (use N x B for a plate covering
    the whole support, which gives Eq. J8-1). Pr: required axial compression for the
    governing combination (LRFD or ASD level to match method)."""
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("base plate: method must be ASD or LRFD")
    for nm, v in (("d", d), ("bf", bf), ("N", N), ("B", B), ("Fy_plate", Fy_plate), ("fc", fc), ("A2", A2)):
        if v is None or v <= 0:
            raise SteelInputError(f"base plate: {nm} must be a positive number")
    if Pr < 0:
        raise SteelInputError("base plate: the column is in tension (uplift); not covered")
    A1 = N * B
    if A2 < A1 - 1e-9:
        raise SteelInputError("base plate: A2 cannot be smaller than the plate area")
    L = [Line("A1 = N B", A1, "in2", "Sect. J8"), Line("A2", A2, "in2", "Sect. J8")]
    if abs(A2 - A1) < 1e-9:
        Pp, src = 0.85 * fc * A1, "Eq. J8-1"
    else:
        Pp, src = min(0.85 * fc * A1 * math.sqrt(A2 / A1), 1.7 * fc * A1), "Eq. J8-2"
    L.append(Line("Pp", Pp, "kip", src))
    Pc = 0.65 * Pp if method == "LRFD" else Pp / 2.31
    L.append(Line("phi_c Pp" if method == "LRFD" else "Pp / Omega_c", Pc, "kip",
                  "Sect. J8: phi_c = 0.65, Omega_c = 2.31"))
    if kind not in ("I", "rect", "round"):
        raise SteelInputError("base plate: the column is an I-shape, a rectangular HSS or a round HSS or pipe")
    if kind != "I":
        # AISC Design Guide 1, 3rd Ed., Sect. 4.3.1, "Base Plate Yielding Limit (HSS and Pipe)": yield lines at 0.95 times the depth
        # and width of a rectangular HSS, at 0.8 times the diameter of a round HSS or pipe; lambda n' is not used.
        k_ = 0.95 if kind == "rect" else 0.8
        m, n = (N - k_ * d) / 2, (B - k_ * bf) / 2
        ell = max(m, n)
        if ell <= 0:
            raise SteelInputError("base plate: the plate does not extend past the column")
        fp = Pr / A1
        t_min = ell * math.sqrt(2 * fp / (0.90 * Fy_plate)) if method == "LRFD" else ell * math.sqrt(1.67 * 2 * fp / Fy_plate)
        nm = ("0.95 H", "0.95 B") if kind == "rect" else ("0.8 D", "0.8 D")
        L += [Line(f"m = (N - {nm[0]}) / 2", m, "in", "AISC Design Guide 1 Sect. 4.3.1 (HSS and pipe)"),
              Line(f"n = (B - {nm[1]}) / 2", n, "in", "AISC Design Guide 1 Sect. 4.3.1 (HSS and pipe)"),
              Line("l = max(m, n)", ell, "in", "AISC Design Guide 1 Sect. 4.3.1"),
              Line("fp = Pr / (B N)", fp, "ksi", "bearing stress under the plate"),
              Line("t min", t_min, "in", "Manual Eq. 14-7a" if method == "LRFD" else "Manual Eq. 14-7b")]
        return BasePlateResult(Pp, Pc, t_min, L)
    m = (N - 0.95 * d) / 2
    n = (B - 0.8 * bf) / 2
    n1 = math.sqrt(d * bf) / 4
    X = (4 * d * bf / (d + bf) ** 2) * (Pr / Pc) if Pc else 0.0
    lam = 1.0 if X >= 1 else min(2 * math.sqrt(X) / (1 + math.sqrt(1 - X)), 1.0)
    ell = max(m, n, lam * n1)
    fp = Pr / A1
    t_min = ell * math.sqrt(2 * fp / (0.90 * Fy_plate)) if method == "LRFD" else \
        ell * math.sqrt(1.67 * 2 * fp / Fy_plate)
    L += [Line("m = (N - 0.95 d) / 2", m, "in", "Manual Eq. 14-2 (Design Example J.6)"),
          Line("n = (B - 0.8 bf) / 2", n, "in", "Manual Eq. 14-3"),
          Line("n' = sqrt(d bf) / 4", n1, "in", "Manual Eq. 14-4"),
          Line("X", X, "", "Manual Eq. 14-6"),
          Line("lambda", lam, "", "Manual Eq. 14-5", "not more than 1"),
          Line("l = max(m, n, lambda n')", ell, "in", "Manual Part 14"),
          Line("fp = Pr / (B N)", fp, "ksi", "bearing stress under the plate"),
          Line("t min", t_min, "in", "Manual Eq. 14-7a" if method == "LRFD" else "Manual Eq. 14-7b")]
    return BasePlateResult(Pp, Pc, t_min, L)


# ---------------------------------------------------------------- base plate with moment
@dataclass
class MomentCase:
    name: str
    e: float                     # eccentricity M / P, in (inf for no axial load)
    Y: float                     # bearing length, in
    f_bearing: float             # bearing stress used, ksi
    T: float                     # total tension in the rods on the tension side, kips
    t_req: float                 # plate thickness required, in
    t_govern: str
    uplift: bool
    x: float = 0.0               # rod line to the centre of the column flange, in (DG1 Eq. 4-61)
    b_eff: float = 0.0           # plate width resisting the rod tension, in


def moment_case(name, P, M, d, bf, N, B, f_rod, fp_avail, Fy_plate, method, n_rods, tf=0.0):
    """One load case on a base plate with moment: AISC Design Guide 1, 3rd Ed. (2024),
    Sect. 4.3.7.

    The concrete bears on the plate at a uniform stress over a length Y from the
    compression edge (Fig. 4-7, 4-8). Low moment, e = M/P <= e_crit = N/2 - P/(2 q_max)
    (Eq. 4-40): Y = N - 2e (Eq. 4-42), stress P/(B Y) (Eq. 4-44), no rod tension. Large
    moment: the stress is fp_avail (AISC 360-22 J8), and with the rods at f_rod from the
    plate centre
        q_max Y (f + N/2 - Y/2) - P (e + f) = 0      (Eq. 4-56; solved by Eq. 4-58)
        T = q_max Y - P                               (Eq. 4-55)
    No real solution (Eq. 4-59 not met) means the plate is too small.
    P is compression positive (kips), M in kip-in.
    Plate bending per unit width, Mn = Fy t^2 / 4 (Eq. 4-49; phi 0.90, Omega 1.67):
      bearing side: cantilevers m and n (Eq. 4-10, 4-11): fp m^2/2 for Y >= m, else
        fp Y (m - Y/2) (Eq. 4-47, 4-48); n used in place of m with fp n^2/2 (note to
        Eq. 4-52);
      tension side: Mpl = T x / b, x = f - d/2 + tf/2 (Eq. 4-60, 4-61). Eq. 4-60 uses the
        full plate width B. Here b is the lesser of B and the width from a 45 degree
        distribution from each rod to the flange (2x per rod), which Sect. 4.3.2 (item 4)
        and Appendix B give as the conservative effective width.
    A case with no axial compression and with moment is solved by the same two equations
    (the guide's Sect. 4.3.6); net uplift with too little moment to bear is not covered."""
    M = abs(M)
    q = fp_avail * B                                    # kip/in at the available bearing stress
    arm = f_rod + N / 2
    drive = M + P * f_rod                               # moment of the loads about the rod line
    if drive <= 0:
        raise SteelInputError(f"base plate: case {name}: the base is in net uplift with too little moment to "
                              "bear on the concrete; all rods in tension is not covered")
    uplift = False
    if P > 0 and M / P <= N / 2 - P / (2 * q):          # bearing alone balances the load
        e = M / P
        Y = N - 2 * e
        fb, T = P / (B * Y), 0.0
    else:
        disc = arm ** 2 - 2 * drive / q
        if disc < 0:
            raise SteelInputError(f"base plate: case {name}: the plate is too small; the concrete cannot "
                                  "balance the moment even with the rods in tension")
        Y = arm - math.sqrt(disc)
        fb, T = fp_avail, q * Y - P
        e = M / P if P > 0 else float("inf")
        uplift = True
    # plate bending, per inch of width
    m, n = (N - 0.95 * d) / 2, (B - 0.8 * bf) / 2
    cands = []
    if m > 0:
        Mb = fb * m * m / 2 if Y >= m else fb * Y * (m - Y / 2)
        cands.append((Mb, "bearing side, cantilever m"))
    if n > 0:
        cands.append((fb * n * n / 2, "bearing side, cantilever n"))
    x = f_rod - d / 2 + tf / 2                            # DG1 Eq. 4-61
    width = B
    if T > 0 and x > 0:
        width = min(B, n_rods * 2 * x)                    # 45 degree distribution, DG1 Sect. 4.3.2 item 4
        cands.append((T * x / width, "tension side, rods to column flange"))
    Mpl, gov = max(cands) if cands else (0.0, "none")
    k = 0.90 if method == "LRFD" else 1 / 1.67
    t_req = math.sqrt(4 * Mpl / (k * Fy_plate))
    return MomentCase(name, e, Y, fb, T, t_req, gov, uplift, x, width)
