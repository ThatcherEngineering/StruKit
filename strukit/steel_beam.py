"""Steel beams: rolled doubly symmetric I-shapes bent about the major axis.

Source on file: ANSI/AISC 360-22, Specification for Structural Steel Buildings
(August 1, 2022). Every result line names the section or equation it comes from.

Covered: F2 (yielding, lateral-torsional buckling), F3 (compression flange local
buckling), G2.1 (web shear, no transverse stiffeners), Table B4.1b Cases 10 and 15.
Not covered (the run stops and says so): noncompact or slender webs (F4, F5),
channels, minor-axis bending, built-up sections, tension field action.

Units: kip, inch, ksi. Moments in kip-in.
"""
import math
from dataclasses import dataclass, field

E_STEEL = 29000.0            # ksi, AISC 360-22 Sect. F2 (definition of E)
REQUIRED = ["d", "tw", "bf", "tf", "h_tw", "Zx", "Sx", "ry", "J", "ho"]


class SteelInputError(ValueError):
    pass


@dataclass
class Line:
    label: str
    value: float
    unit: str
    source: str
    note: str = ""


@dataclass
class SteelBeamResult:
    Mn: float
    M_avail: float
    Vn: float
    V_avail: float
    governs: str
    flange: str
    lines: list = field(default_factory=list)


def cb_factor(M_max, M_A, M_B, M_C):
    """Lateral-torsional buckling modification factor. AISC 360-22 Eq. F1-1."""
    m, a, b, c = (abs(v) for v in (M_max, M_A, M_B, M_C))
    if m == 0:
        return 1.0
    return 12.5 * m / (2.5 * m + 3 * a + 4 * b + 3 * c)


def rts_from(Iy, Cw, Sx):
    """Effective radius of gyration. AISC 360-22 Eq. F2-7."""
    return math.sqrt(math.sqrt(Iy * Cw) / Sx)


def check(props, Fy, Lb, Cb=1.0, method="ASD", E=E_STEEL):
    """Nominal and available flexural and shear strength of a rolled I-shape.

    props: d, tw, bf, tf, h_tw (h/tw), Zx, Sx, ry, J, ho, and either rts or Iy + Cw.
    Lb in inches. method "ASD" or "LRFD".
    """
    missing = [k for k in REQUIRED if props.get(k) in (None, "")]
    if missing:
        raise SteelInputError("steel beam: missing section properties: " + ", ".join(missing))
    if "rts" not in props and not ("Iy" in props and "Cw" in props):
        raise SteelInputError("steel beam: give rts, or Iy and Cw (Eq. F2-7)")
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("steel beam: method must be ASD or LRFD")
    if Fy <= 0 or Lb < 0 or Cb <= 0:
        raise SteelInputError("steel beam: Fy and Cb must be positive, Lb not negative")

    p = props
    L = []
    rt = math.sqrt(E / Fy)
    channel = p.get("type") in ("C", "MC")

    # --- element slenderness, Table B4.1b ---
    # the tabulated bf/2tf is used when the Shapes Database supplies it
    lam_f = p["bf_2tf"] if p.get("bf_2tf") else p["bf"] / (2 * p["tf"])
    lam_pf, lam_rf = 0.38 * rt, 1.0 * rt
    lam_w = p["h_tw"]
    lam_pw = 3.76 * rt
    L.append(Line("flange b/t" if channel else "flange bf/2tf", lam_f, "", "Table B4.1b Case 10",
                  f"compact limit {lam_pf:.2f}, noncompact limit {lam_rf:.2f}"))
    L.append(Line("web h/tw", lam_w, "", "Table B4.1b Case 15", f"compact limit {lam_pw:.2f}"))
    if lam_w > lam_pw:
        raise SteelInputError(
            f"steel beam: web h/tw = {lam_w:.1f} exceeds the compact limit {lam_pw:.1f} "
            "(Table B4.1b Case 15). Sections F4 / F5 are not built yet.")
    flange = "compact" if lam_f <= lam_pf else ("noncompact" if lam_f <= lam_rf else "slender")
    if channel and flange != "compact":
        raise SteelInputError(f"steel beam: channel flange b/t = {lam_f:.2f} exceeds the compact limit {lam_pf:.2f}; Sect. F2 is for compact channels")

    # --- yielding, F2.1 ---
    Mp = Fy * p["Zx"]
    L.append(Line("Mp = Fy Zx", Mp, "kip-in", "Eq. F2-1"))

    # --- lateral-torsional buckling, F2.2 ---
    rts = p["rts"] if "rts" in p else rts_from(p["Iy"], p["Cw"], p["Sx"])
    if channel:
        if not (p.get("Iy") and p.get("Cw")):
            raise SteelInputError("steel beam: a channel needs Iy and Cw (Eq. F2-8b)")
        c = p["ho"] / 2 * math.sqrt(p["Iy"] / p["Cw"])          # Eq. F2-8b, channels
        L.append(Line("c = (ho / 2) (Iy / Cw)^0.5", c, "", "Eq. F2-8b"))
    else:
        c = 1.0                                                   # Eq. F2-8a, I-shapes
    jc = p["J"] * c / (p["Sx"] * p["ho"])
    Lp = 1.76 * p["ry"] * rt
    Lr = 1.95 * rts * (E / (0.7 * Fy)) * math.sqrt(
        jc + math.sqrt(jc ** 2 + 6.76 * (0.7 * Fy / E) ** 2))
    L.append(Line("Lp", Lp, "in", "Eq. F2-5"))
    L.append(Line("Lr", Lr, "in", "Eq. F2-6"))
    if Lb <= Lp:
        M_ltb, ltb_src = Mp, "F2.2(a): Lb <= Lp, LTB does not apply"
    elif Lb <= Lr:
        M_ltb = min(Cb * (Mp - (Mp - 0.7 * Fy * p["Sx"]) * (Lb - Lp) / (Lr - Lp)), Mp)
        ltb_src = "Eq. F2-2"
    else:
        Fcr = Cb * math.pi ** 2 * E / (Lb / rts) ** 2 * math.sqrt(
            1 + 0.078 * jc * (Lb / rts) ** 2)
        L.append(Line("Fcr", Fcr, "ksi", "Eq. F2-4"))
        M_ltb = min(Fcr * p["Sx"], Mp)
        ltb_src = "Eq. F2-3"
    L.append(Line("Mn, lateral-torsional buckling", M_ltb, "kip-in", ltb_src,
                  f"Lb = {Lb:.1f} in, Cb = {Cb:.3f}"))

    # --- compression flange local buckling, F3.2 ---
    M_flb = None
    if flange == "noncompact":
        M_flb = Mp - (Mp - 0.7 * Fy * p["Sx"]) * (lam_f - lam_pf) / (lam_rf - lam_pf)
        L.append(Line("Mn, flange local buckling", M_flb, "kip-in", "Eq. F3-1"))
    elif flange == "slender":
        kc = min(max(4 / math.sqrt(lam_w), 0.35), 0.76)
        M_flb = 0.9 * E * kc * p["Sx"] / lam_f ** 2
        L.append(Line("Mn, flange local buckling", M_flb, "kip-in", "Eq. F3-2", f"kc = {kc:.3f}"))

    cands = {"yielding (F2.1)": Mp, "lateral-torsional buckling (F2.2)": M_ltb}
    if M_flb is not None:
        cands["compression flange local buckling (F3.2)"] = M_flb
    governs = min(cands, key=lambda k: (cands[k], k != "yielding (F2.1)"))
    Mn = cands[governs]
    M_avail = 0.90 * Mn if method == "LRFD" else Mn / 1.67
    L.append(Line("phi_b Mn" if method == "LRFD" else "Mn / Omega_b", M_avail, "kip-in",
                  "Sect. F1(a): phi_b = 0.90, Omega_b = 1.67", f"governs: {governs}"))

    # --- shear, G2.1 ---
    Aw = p["d"] * p["tw"]
    if lam_w <= 2.24 * rt and not channel:                       # G2.1(a) is for rolled I-shaped members
        Cv1, phi_v, om_v, vsrc = 1.0, 1.00, 1.50, "Sect. G2.1(a), Eq. G2-2"
    else:
        kv = 5.34                                                # G2.1(b)(2)(i), no stiffeners
        lim = 1.10 * math.sqrt(kv * E / Fy)
        Cv1 = 1.0 if lam_w <= lim else lim / lam_w
        phi_v, om_v = 0.90, 1.67
        vsrc = "Sect. G2.1(b), Eq. G2-3" if lam_w <= lim else "Sect. G2.1(b), Eq. G2-4"
    Vn = 0.6 * Fy * Aw * Cv1
    V_avail = phi_v * Vn if method == "LRFD" else Vn / om_v
    L.append(Line("Vn = 0.6 Fy Aw Cv1", Vn, "kip", "Eq. G2-1", f"Cv1 = {Cv1:.3f} ({vsrc})"))
    L.append(Line("phi_v Vn" if method == "LRFD" else "Vn / Omega_v", V_avail, "kip", vsrc,
                  f"phi_v = {phi_v:.2f}, Omega_v = {om_v:.2f}"))
    return SteelBeamResult(Mn, M_avail, Vn, V_avail, governs, flange, L)
