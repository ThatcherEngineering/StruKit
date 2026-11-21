"""Steel columns: rolled doubly symmetric I-shapes in axial compression.

Source on file: ANSI/AISC 360-22. Covered: E1 (phi, Omega), E2 (effective length
Lc = KL, supplied by the caller), E3 (flexural buckling), E4(a) (torsional buckling of
doubly symmetric members), Table B4.1a Cases 1 and 5.
Not covered (the run stops and says so): slender elements (E7), singly symmetric and
built-up members, single angles.

Units: kip, inch, ksi.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import E_STEEL, Line, SteelInputError

G_STEEL = 11200.0            # ksi, AISC 360-22 Sect. E4
REQUIRED = ["A", "rx", "ry", "h_tw"]


@dataclass
class SteelColumnResult:
    Pn: float
    P_avail: float
    Fn: float
    governs: str
    slenderness: float
    lines: list = field(default_factory=list)


def check(props, Fy, Lcx, Lcy, Lcz=None, method="ASD", E=E_STEEL):
    """Nominal and available compressive strength. Lcx, Lcy, Lcz are effective lengths
    (KL) in inches for x-axis, y-axis and torsional buckling. Lcz=None means the
    torsional length does not exceed the lateral lengths, so E4 is not checked."""
    p = props
    missing = [k for k in REQUIRED if p.get(k) in (None, "")]
    if not p.get("bf_2tf") and not (p.get("bf") and p.get("tf")):
        missing.append("bf_2tf")
    if missing:
        raise SteelInputError("steel column: missing section properties: " + ", ".join(missing))
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("steel column: method must be ASD or LRFD")
    if Fy <= 0 or Lcx <= 0 or Lcy <= 0:
        raise SteelInputError("steel column: Fy, Lcx and Lcy must be positive")

    L = []
    rt = math.sqrt(E / Fy)
    lam_f = p["bf_2tf"] if p.get("bf_2tf") else p["bf"] / (2 * p["tf"])
    lam_w = p["h_tw"]
    lim_f, lim_w = 0.56 * rt, 1.49 * rt
    L.append(Line("flange bf/2tf", lam_f, "", "Table B4.1a Case 1", f"nonslender limit {lim_f:.1f}"))
    L.append(Line("web h/tw", lam_w, "", "Table B4.1a Case 5", f"nonslender limit {lim_w:.1f}"))
    if lam_f > lim_f or lam_w > lim_w:
        which = "flange" if lam_f > lim_f else "web"
        raise SteelInputError(
            f"steel column: the {which} is a slender element (Table B4.1a). "
            "Section E7 is not built yet.")

    sx, sy = Lcx / p["rx"], Lcy / p["ry"]
    L.append(Line("Lcx / rx", sx, "", "Sect. E2"))
    L.append(Line("Lcy / ry", sy, "", "Sect. E2"))
    modes = {"flexural buckling about x (E3)": math.pi ** 2 * E / sx ** 2,
             "flexural buckling about y (E3)": math.pi ** 2 * E / sy ** 2}
    if Lcz is not None:
        need = [k for k in ("Cw", "J", "Ix", "Iy") if p.get(k) in (None, "")]
        if need:
            raise SteelInputError("steel column: torsional buckling needs " + ", ".join(need))
        modes["torsional buckling (E4)"] = (
            (math.pi ** 2 * E * p["Cw"] / Lcz ** 2 + G_STEEL * p["J"]) / (p["Ix"] + p["Iy"]))
        L.append(Line("Fe, torsional", modes["torsional buckling (E4)"], "ksi", "Eq. E4-2",
                      f"Lcz = {Lcz:.1f} in"))
    governs = min(modes, key=modes.get)
    Fe = modes[governs]
    L.append(Line("Fe", Fe, "ksi", "Eq. E3-4" if "E3" in governs else "Eq. E4-2", f"governs: {governs}"))
    if Fy / Fe <= 2.25:
        Fn, src = 0.658 ** (Fy / Fe) * Fy, "Eq. E3-2"
    else:
        Fn, src = 0.877 * Fe, "Eq. E3-3"
    L.append(Line("Fn", Fn, "ksi", src, f"Fy/Fe = {Fy / Fe:.3f}"))
    Pn = Fn * p["A"]
    L.append(Line("Pn = Fn Ag", Pn, "kip", "Eq. E3-1" if "E3" in governs else "Eq. E4-1"))
    P_avail = 0.90 * Pn if method == "LRFD" else Pn / 1.67
    L.append(Line("phi_c Pn" if method == "LRFD" else "Pn / Omega_c", P_avail, "kip",
                  "Sect. E1: phi_c = 0.90, Omega_c = 1.67"))
    slender = max(sx, sy)
    if slender > 200:
        L.append(Line("Lc / r", slender, "", "Sect. E2 User Note",
                      "exceeds 200, the preferred maximum (a recommendation, not a limit)"))
    return SteelColumnResult(Pn, P_avail, Fn, governs, slender, L)
