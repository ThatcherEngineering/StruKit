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


def check(d, bf, N, B, Fy_plate, fc, A2, Pr, method="ASD"):
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
