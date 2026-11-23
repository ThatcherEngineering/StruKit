"""Round HSS and pipe members, AISC 360-22: compression (Sect. E3), flexure (Sect. F8) and shear
(Sect. G5). Section properties from shapes.hss (design wall thickness tdes). Units: kips, in., ksi.

    Table B4.1a Case 9:   compression, slender where D/t > 0.11 E/Fy
    Table B4.1b Case 20:  flexure, compact to 0.07 E/Fy, noncompact to 0.31 E/Fy
    F8:  Mn = Fy Z;  noncompact Mn = (0.021 E/(D/t) + Fy) S;  slender Mn = 0.33 E/(D/t) S;  D/t under 0.45 E/Fy
    E3:  Fe = pi^2 E/(Lc/r)^2;  Fcr = 0.658^(Fy/Fe) Fy  for Lc/r <= 4.71 (E/Fy)^0.5, else 0.877 Fe
    G5:  Vn = Fcr Ag/2;  Fcr the larger of 1.60 E/((Lv/D)^0.5 (D/t)^1.25) and 0.78 E/(D/t)^1.5, not over 0.6 Fy
"""
import math

E_STEEL = 29000.0
PHI = {"compression": 0.90, "flexure": 0.90, "shear": 0.90}        # Sect. E1, F1, G1
OMEGA = {"compression": 1.67, "flexure": 1.67, "shear": 1.67}
GRADES = {"ASTM A500 Grade C round": (46.0, 62.0)}        # Fy, Fu ksi: Manual Table 2-4 as quoted in Design Guide 34 Example 10.1.7


class HSSError(ValueError):
    pass


def _round(props):
    if props.get("type") not in ("HSS-ROUND", "PIPE"):
        raise HSSError("hss: this check is for round HSS and pipe")
    return props["OD"], props["tdes"], props["D_t"]


def available(Rn, kind, method):
    if method not in ("ASD", "LRFD"):
        raise HSSError("hss: the method is ASD or LRFD")
    return Rn / OMEGA[kind] if method == "ASD" else PHI[kind] * Rn


def flexure(props, Fy, E=E_STEEL):
    D, t, dt = _round(props)
    lp, lr, lmax = 0.07 * E / Fy, 0.31 * E / Fy, 0.45 * E / Fy
    if dt >= lmax:
        raise HSSError(f"hss: D/t = {dt:g} is not less than 0.45 E/Fy = {lmax:.1f}; outside Sect. F8")
    Mp = Fy * props["Zx"]
    if dt <= lp:
        cls, Mn, eq = "compact", Mp, "F8-1"
    elif dt <= lr:
        cls, Mn, eq = "noncompact", min(Mp, (0.021 * E / dt + Fy) * props["Sx"]), "F8-2"
    else:
        cls, Mn, eq = "slender", min(Mp, 0.33 * E / dt * props["Sx"]), "F8-3"
    return dict(Mn=Mn, Mp=Mp, cls=cls, eq=eq, lam=dt, lam_p=lp, lam_r=lr)


def compression(props, Fy, Lc, E=E_STEEL):
    D, t, dt = _round(props)
    lr = 0.11 * E / Fy
    if dt > lr:
        raise HSSError(f"hss: D/t = {dt:g} is over 0.11 E/Fy = {lr:.1f}: slender in compression (Sect. E7), not built")
    if Lc is None or Lc <= 0:
        raise HSSError("hss: the effective length must be positive")
    slender = Lc / props["rx"]
    Fe = math.pi ** 2 * E / slender ** 2
    limit = 4.71 * math.sqrt(E / Fy)
    Fcr, eq = (0.658 ** (Fy / Fe) * Fy, "E3-2") if slender <= limit else (0.877 * Fe, "E3-3")
    return dict(Pn=Fcr * props["A"], Fcr=Fcr, Fe=Fe, Lc_r=slender, limit=limit, eq=eq, lam=dt, lam_r=lr)


def shear(props, Fy, Lv=None, E=E_STEEL):
    """Lv: distance from maximum to zero shear, in.; None = Eq. G5-2a left out (G5-2b alone is
    the smaller buckling stress, so the result is not unconservative)."""
    D, t, dt = _round(props)
    b = 0.78 * E / dt ** 1.5
    a = 1.60 * E / (math.sqrt(Lv / D) * dt ** 1.25) if Lv else None
    Fcr = min(max(b, a) if a is not None else b, 0.6 * Fy)
    return dict(Vn=Fcr * props["A"] / 2.0, Fcr=Fcr, Fcr_a=a, Fcr_b=b, yield_governs=Fcr >= 0.6 * Fy - 1e-9)
