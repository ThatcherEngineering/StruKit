"""HSS and pipe members, AISC 360-22. Round HSS and pipe: compression (Sect. E3), flexure
(Sect. F8) and shear (Sect. G5). Square and rectangular HSS: compression (E3, slender walls by
E7.1), flexure (F7) and shear (G4): the functions named rect_* below; member() picks by type. Section properties from shapes.hss (design wall thickness tdes). Units: kips, in., ksi.

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


# ---- square and rectangular HSS ------------------------------------------------------------------
C1_HSS, C2_HSS = 0.20, 1.38                               # Table E7.1 case (b), walls of square and rectangular HSS


def _rect(props):
    if props.get("type") != "HSS-RECT":
        raise HSSError("hss: this check is for square and rectangular HSS")
    t = props["tdes"]
    return props["Ht"], props["B"], t, props["Ht"] - 3 * t, props["B"] - 3 * t      # flat widths, Sect. B4.1b(d)


def rect_compression(props, Fy, Lcx, Lcy=None, E=E_STEEL):
    """Sect. E3 with the effective area of Sect. E7.1 where a wall is slender (Table B4.1a
    Case 6, lambda_r = 1.40 (E/Fy)^0.5). Lcx, Lcy: effective lengths about x and y, in."""
    H, B, t, h, b = _rect(props)
    Lcy = Lcx if Lcy is None else Lcy
    if Lcx is None or Lcx <= 0 or Lcy <= 0:
        raise HSSError("hss: the effective lengths must be positive")
    sx, sy = Lcx / props["rx"], Lcy / props["ry"]
    slender = max(sx, sy)
    Fe = math.pi ** 2 * E / slender ** 2
    limit = 4.71 * math.sqrt(E / Fy)
    Fn, eq = (0.658 ** (Fy / Fe) * Fy, "E3-2") if slender <= limit else (0.877 * Fe, "E3-3")
    lr = 1.40 * math.sqrt(E / Fy)
    walls, Ae = [], props["A"]
    for nm, w, lam in (("wide wall", h, props["h_t"]), ("narrow wall", b, props["b_t"])):
        if lam <= lr * math.sqrt(Fy / Fn):
            we, Fel = w, None                             # Eq. E7-2
        else:
            Fel = (C2_HSS * lr / lam) ** 2 * Fy           # Eq. E7-5
            r_ = math.sqrt(Fel / Fn)
            we = w * (1 - C1_HSS * r_) * r_               # Eq. E7-3
        Ae -= 2 * (w - we) * t
        walls.append(dict(name=nm, width=w, lam=lam, effective=we, Fel=Fel))
    return dict(Pn=Fn * Ae, Fcr=Fn, Fe=Fe, Lc_r=slender, Lc_rx=sx, Lc_ry=sy, limit=limit, eq=eq, lam_r=lr, Ae=Ae, walls=walls,
                slender_walls=any(w["lam"] > lr for w in walls))


def rect_flexure(props, Fy, axis="x", Lb=None, Cb=1.0, E=E_STEEL):
    """Sect. F7: yielding, flange and web local buckling, and lateral-torsional buckling for
    major-axis bending of a rectangular (not square) HSS when Lb (in.) is given. A slender
    flange uses the effective section modulus found by taking the ineffective width off both
    flanges (the method of AISC Design Example F.8B)."""
    H, B, t, h, b = _rect(props)
    if axis not in ("x", "y"):
        raise HSSError("hss: the bending axis is x or y")
    if axis == "x":
        Z, S, I, depth, fw, lf, lw = props["Zx"], props["Sx"], props["Ix"], H, b, props["b_t"], props["h_t"]
    else:
        Z, S, I, depth, fw, lf, lw = props["Zy"], props["Sy"], props["Iy"], B, h, props["h_t"], props["b_t"]
    rt = math.sqrt(E / Fy)
    lpf, lrf, lpw, lrw = 1.12 * rt, 1.40 * rt, 2.42 * rt, 5.70 * rt
    Mp = Fy * Z
    out = dict(Mp=Mp, lam_f=lf, lam_w=lw, lam_pf=lpf, lam_rf=lrf, lam_pw=lpw, lam_rw=lrw, states=[("yielding", Mp, "F7-1")])
    if lf <= lpf:
        out["flange"] = "compact"
    elif lf <= lrf:
        out["flange"] = "noncompact"
        out["states"].append(("flange local buckling", min(Mp, Mp - (Mp - Fy * S) * (lf - lpf) / (lrf - lpf)), "F7-2"))
    else:
        out["flange"] = "slender"
        be = min(fw, 1.92 * t * rt * (1 - 0.38 / lf * rt))                                    # Eq. F7-4
        cut = fw - be
        Ieff = I - 2 * (cut * t ** 3 / 12 + cut * t * ((depth - t) / 2) ** 2)
        Se = Ieff / (depth / 2)
        out.update(be=be, Se=Se)
        out["states"].append(("flange local buckling", Fy * Se, "F7-3"))
    if lw <= lpw:
        out["web"] = "compact"
    elif lw <= lrw:
        out["web"] = "noncompact"
        out["states"].append(("web local buckling", min(Mp, Mp - (Mp - Fy * S) * (lw - lpw) / (lrw - lpw)), "F7-6"))
    else:
        raise HSSError("hss: slender webs in flexure are outside what is built (Sect. F7.3(c))")
    if axis == "x" and H > B and Lb:
        k = math.sqrt(props["J"] * props["A"])
        Lp = 0.13 * E * props["ry"] * k / Mp                                                   # Eq. F7-10
        Lr = 2 * E * props["ry"] * k / (0.7 * Fy * props["Sx"])                                # Eq. F7-11
        out.update(Lp=Lp, Lr=Lr, Lb=Lb)
        if Lb > Lr:
            out["states"].append(("lateral-torsional buckling", min(Mp, 2 * E * Cb * k / (Lb / props["ry"])), "F7-9"))
        elif Lb > Lp:
            out["states"].append(("lateral-torsional buckling", min(Mp, Cb * (Mp - (Mp - 0.7 * Fy * props["Sx"]) * (Lb - Lp) / (Lr - Lp))), "F7-8"))
    name, Mn, eq = min(out["states"], key=lambda x: x[1])
    out.update(Mn=Mn, eq=eq, governs=name, cls=out["flange"])
    return out


def rect_shear(props, Fy, axis="x", E=E_STEEL):
    """Sect. G4: Vn = 0.6 Fy Aw Cv2, Aw = 2 h t, Cv2 by Sect. G2.2 with kv = 5. axis "x": shear
    from bending about x (carried by the walls of depth Ht)."""
    H, B, t, h, b = _rect(props)
    hw, lam = (h, props["h_t"]) if axis == "x" else (b, props["b_t"])
    kv = 5.0
    a, c = 1.10 * math.sqrt(kv * E / Fy), 1.37 * math.sqrt(kv * E / Fy)
    Cv2, eq = (1.0, "G2-9") if lam <= a else (a / lam, "G2-10") if lam <= c else (1.51 * kv * E / (lam ** 2 * Fy), "G2-11")
    Aw = 2 * hw * t
    return dict(Vn=0.6 * Fy * Aw * Cv2, Aw=Aw, Cv2=Cv2, eq=eq, lam=lam)


def member(props, Fy, Lcx, Lcy, Lb=None, Lv=None, E=E_STEEL):
    """Compression, flexure about x and y, and shear along both axes of any HSS or pipe:
    dict(kind, comp, fx, fy, vx, vy)."""
    if props.get("type") == "HSS-RECT":
        return dict(kind="rect", comp=rect_compression(props, Fy, Lcx, Lcy, E), fx=rect_flexure(props, Fy, "x", Lb, 1.0, E),
                    fy=rect_flexure(props, Fy, "y", None, 1.0, E), vx=rect_shear(props, Fy, "x", E), vy=rect_shear(props, Fy, "y", E))
    c = compression(props, Fy, max(Lcx, Lcy), E)
    f, v = flexure(props, Fy, E), shear(props, Fy, Lv, E)
    return dict(kind="round", comp=c, fx=f, fy=f, vx=v, vy=v)


def beam_check(props, Fy, Lb, Cb=1.0, method="ASD", E=E_STEEL):
    """Flexure about x and shear of an HSS or pipe beam in the form the steel beam sheet uses
    (steel_beam.SteelBeamResult with its printed lines). Lb in inches."""
    from .steel_beam import Line, SteelBeamResult
    L = []
    if props.get("type") == "HSS-RECT":
        f = rect_flexure(props, Fy, "x", Lb if Lb else None, Cb, E)
        v = rect_shear(props, Fy, "x", E)
        L += [Line("flange b/t", f["lam_f"], "", "Table B4.1b Case 17", f"compact limit {f['lam_pf']:.1f}, noncompact limit {f['lam_rf']:.1f}"),
              Line("web h/t", f["lam_w"], "", "Table B4.1b Case 19", f"compact limit {f['lam_pw']:.1f}"),
              Line("Mp = Fy Zx", f["Mp"], "kip-in", "Eq. F7-1")]
        if "be" in f:
            L += [Line("be", f["be"], "in", "Eq. F7-4"), Line("Se", f["Se"], "in3", "Sect. F7.2(c)", "ineffective width taken off both flanges")]
        if "Lp" in f:
            L += [Line("Lp", f["Lp"], "in", "Eq. F7-10"), Line("Lr", f["Lr"], "in", "Eq. F7-11")]
        for nm, M, eq in f["states"][1:]:
            L.append(Line(f"Mn, {nm}", M, "kip-in", f"Eq. {eq}", f"Lb = {Lb:.1f} in, Cb = {Cb:.3f}" if "lateral" in nm else ""))
        gov = f"{f['governs']} (Eq. {f['eq']})"
        L.append(Line("phi_b Mn" if method == "LRFD" else "Mn / Omega_b", available(f["Mn"], "flexure", method), "kip-in",
                      "Sect. F1(a): phi_b = 0.90, Omega_b = 1.67", f"governs: {gov}"))
        L += [Line("Vn = 0.6 Fy Aw Cv2", v["Vn"], "kip", "Eq. G4-1", f"Aw = 2 h t = {v['Aw']:.2f} in2, Cv2 = {v['Cv2']:.3f} (Eq. {v['eq']})")]
        vsrc = "AISC 360-22 Sect. G4"
    else:
        f = flexure(props, Fy, E)
        v = shear(props, Fy, None, E)
        L += [Line("D/t", f["lam"], "", "Table B4.1b Case 20", f"compact limit {f['lam_p']:.1f}, noncompact limit {f['lam_r']:.1f}"),
              Line("Mp = Fy Z", f["Mp"], "kip-in", "Eq. F8-1")]
        if f["cls"] != "compact":
            L.append(Line("Mn, local buckling", f["Mn"], "kip-in", f"Eq. {f['eq']}"))
        gov = ("yielding" if f["cls"] == "compact" else "local buckling") + f" (Eq. {f['eq']})"
        L.append(Line("phi_b Mn" if method == "LRFD" else "Mn / Omega_b", available(f["Mn"], "flexure", method), "kip-in",
                      "Sect. F1(a): phi_b = 0.90, Omega_b = 1.67", f"governs: {gov}"))
        L += [Line("Vn = Fcr Ag / 2", v["Vn"], "kip", "Eq. G5-1", f"Fcr = {v['Fcr']:.1f} ksi (Eq. G5-2b, not over 0.6 Fy)")]
        vsrc = "AISC 360-22 Sect. G5"
    L.append(Line("phi_v Vn" if method == "LRFD" else "Vn / Omega_v", available(v["Vn"], "shear", method), "kip", "Sect. G1", "phi_v = 0.90, Omega_v = 1.67"))
    r = SteelBeamResult(f["Mn"], available(f["Mn"], "flexure", method), v["Vn"], available(v["Vn"], "shear", method), gov, f["cls"], L)
    r.v_source = vsrc
    r.v_note = "shear carried by the two walls parallel to the load" if props.get("type") == "HSS-RECT" else ""
    return r


HSS_TYPES = ("HSS-RECT", "HSS-ROUND", "PIPE")


def column_check(props, Fy, Lcx, Lcy, method="ASD", E=E_STEEL):
    """Axial compression in the form the steel column sheet uses (steel_column.SteelColumnResult)."""
    from .steel_beam import Line
    from .steel_column import SteelColumnResult
    L = []
    if props.get("type") == "HSS-RECT":
        c = rect_compression(props, Fy, Lcx, Lcy, E)
        L += [Line("wall b/t, h/t", max(props["b_t"], props["h_t"]), "", "Table B4.1a Case 6", f"b/t = {props['b_t']:g}, h/t = {props['h_t']:g}; nonslender limit {c['lam_r']:.1f}"),
              Line("Lcx / rx", c["Lc_rx"], "", "Sect. E2"), Line("Lcy / ry", c["Lc_ry"], "", "Sect. E2"),
              Line("Fe", c["Fe"], "ksi", "Eq. E3-4"), Line("Fn", c["Fcr"], "ksi", f"Eq. {c['eq']}", f"Fy/Fe = {Fy / c['Fe']:.3f}")]
        if c["slender_walls"]:
            for w in c["walls"]:
                if w["Fel"] is not None:
                    L += [Line(f"{w['name']}: Fel", w["Fel"], "ksi", "Eq. E7-5", "c1 = 0.2, c2 = 1.38 (Table E7.1)"),
                          Line(f"{w['name']}: effective width", w["effective"], "in", "Eq. E7-3", f"full width {w['width']:.2f} in")]
            L += [Line("Ae", c["Ae"], "in2", "Sect. E7", f"Ag = {props['A']:g} in2"), Line("Pn = Fn Ae", c["Pn"], "kip", "Eq. E7-1")]
        else:
            L.append(Line("Pn = Fn Ag", c["Pn"], "kip", "Eq. E3-1"))
        gov = "flexural buckling about " + ("x" if c["Lc_rx"] >= c["Lc_ry"] else "y") + " (E3)" + (", slender walls (E7)" if c["slender_walls"] else "")
    else:
        c = compression(props, Fy, max(Lcx, Lcy), E)
        L += [Line("D/t", props["D_t"], "", "Table B4.1a Case 9", f"nonslender limit {c['lam_r']:.1f}"),
              Line("Lc / r", c["Lc_r"], "", "Sect. E2"), Line("Fe", c["Fe"], "ksi", "Eq. E3-4"),
              Line("Fn", c["Fcr"], "ksi", f"Eq. {c['eq']}", f"Fy/Fe = {Fy / c['Fe']:.3f}"), Line("Pn = Fn Ag", c["Pn"], "kip", "Eq. E3-1")]
        gov = "flexural buckling (E3)"
    Pa = available(c["Pn"], "compression", method)
    L.append(Line("phi_c Pn" if method == "LRFD" else "Pn / Omega_c", Pa, "kip", "Sect. E1: phi_c = 0.90, Omega_c = 1.67"))
    if c["Lc_r"] > 200:
        L.append(Line("Lc / r", c["Lc_r"], "", "Sect. E2 User Note", "exceeds 200, the preferred maximum (a recommendation, not a limit)"))
    return SteelColumnResult(c["Pn"], Pa, c["Fcr"], gov, c["Lc_r"], L)


def weak_flexure(props, Fy, method="ASD", E=E_STEEL):
    """Bending about y in the form steel_beamcol.weak_axis_flexure returns."""
    from .steel_beam import Line
    from .steel_beamcol import Strength
    if props.get("type") == "HSS-RECT":
        f = rect_flexure(props, Fy, "y", None, 1.0, E)
        gov, sect = f"{f['governs']} (Eq. {f['eq']})", "AISC 360-22 Sect. F7: "
        L = [Line("Mpy = Fy Zy", f["Mp"], "kip-in", "Eq. F7-1", f"flange {f['flange']}, web {f['web']} for bending about y")]
        L += [Line(f"Mny, {nm}", M, "kip-in", f"Eq. {eq}") for nm, M, eq in f["states"][1:]]
    else:
        f = flexure(props, Fy, E)
        gov, sect = ("yielding" if f["cls"] == "compact" else "local buckling") + f" (Eq. {f['eq']})", "AISC 360-22 Sect. F8: "
        L = [Line("Mny = Mn (round section)", f["Mn"], "kip-in", f"Eq. {f['eq']}")]
    av = available(f["Mn"], "flexure", method)
    L.append(Line("phi_b Mny" if method == "LRFD" else "Mny / Omega_b", av, "kip-in", "Sect. F1(a): phi_b = 0.90, Omega_b = 1.67", f"governs: {gov}"))
    r = Strength(f["Mn"], av, gov, L)
    r.prefix = sect
    return r


def weak_shear(props, Fy, method="ASD", E=E_STEEL):
    from .steel_beam import Line
    from .steel_beamcol import Strength
    if props.get("type") == "HSS-RECT":
        v = rect_shear(props, Fy, "y", E)
        L = [Line("Vny = 0.6 Fy Aw Cv2", v["Vn"], "kip", "Eq. G4-1", f"Aw = 2 b t = {v['Aw']:.2f} in2, Cv2 = {v['Cv2']:.3f}")]
        src, note = "AISC 360-22 Sect. G4", "shear carried by the two walls parallel to the load"
    else:
        v = shear(props, Fy, None, E)
        L = [Line("Vny = Fcr Ag / 2", v["Vn"], "kip", "Eq. G5-1", f"Fcr = {v['Fcr']:.1f} ksi")]
        src, note = "AISC 360-22 Sect. G5", ""
    av = available(v["Vn"], "shear", method)
    L.append(Line("phi_v Vny" if method == "LRFD" else "Vny / Omega_v", av, "kip", "Sect. G1: phi_v = 0.90, Omega_v = 1.67"))
    r = Strength(v["Vn"], av, "shear (" + src[-2:] + ")", L)
    r.source, r.note = src, note
    return r
