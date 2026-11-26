"""Built-up (welded three-plate) I-shaped members: section properties from the plates, flexure about the major axis (AISC 360-22 Sect. F2 to
F5 with the built-up limits of Table B4.1b), shear without stiffeners (Sect. G2.1(b)), compression (Sect. E3, E4, E7 with Table B4.1a Case 2).

Designation (typed in any shape box): "BU top flange / web / bottom flange", each plate as width x thickness in inches, fractions allowed,
for example "BU 14x2 / 62x1/2 / 14x2" (AISC Design Example F.14). The web size is its clear height between the flanges. Doubly symmetric
when the two flanges are the same; otherwise singly symmetric about the vertical axis.

Validated against AISC Design Examples v16.0: F.14 (plate girder, Sect. F4), E.2 (slender web, E7), E.3 (slender flanges, Table B4.1a Case 2),
E.12 (singly symmetric, flexural-torsional buckling, Eq. E4-3). Units: kip, inch, ksi.
"""
import math
from fractions import Fraction

E_STEEL, G_STEEL = 29000.0, 11200.0
SOURCE = "built-up section, properties from the plates"


class BuiltUpError(ValueError):
    pass


def _num(t):
    t = t.strip().replace('"', "")
    if not t:
        raise BuiltUpError("a plate size is blank")
    if "-" in t[1:] and "/" in t:                       # 1-1/2
        a, b = t.split("-", 1)
        return float(a) + float(Fraction(b))
    if " " in t and "/" in t:                           # 1 1/2
        a, b = t.split(" ", 1)
        return float(a) + float(Fraction(b))
    return float(Fraction(t))


def is_builtup(name):
    return isinstance(name, str) and name.strip().upper().startswith("BU")


def parse(name):
    """(bft, tft, h, tw, bfb, tfb) from a designation "BU bf x tf / h x tw / bf x tf"."""
    s = name.strip()[2:].strip().lower().replace("×", "x").replace("pl", "")
    plates = [p.strip() for p in s.split(" / ")] if " / " in s else None
    if plates is None or len(plates) != 3:
        raise BuiltUpError(f"built-up section '{name}': write it as BU top flange / web / bottom flange, each width x thickness in inches, "
                           "plates separated by ' / ' with spaces, for example BU 14x2 / 62x1/2 / 14x2")
    out = []
    for p in plates:
        if "x" not in p:
            raise BuiltUpError(f"built-up section '{name}': plate '{p}' needs width x thickness")
        a, b = p.split("x", 1)
        out += [_num(a), _num(b)]
    bft, tft, h, tw, bfb, tfb = out
    if min(out) <= 0:
        raise BuiltUpError(f"built-up section '{name}': plate sizes must be positive")
    if tw >= min(bft, bfb):
        raise BuiltUpError(f"built-up section '{name}': the web must be thinner than the flanges are wide")
    return bft, tft, h, tw, bfb, tfb


def props(name):
    """Section properties of a three-plate I (in., in.2, in.4, in.6). Top flange "t", bottom "b"; y measured up from the bottom."""
    bft, tft, h, tw, bfb, tfb = parse(name)
    d = tfb + h + tft
    parts = [(bfb, tfb, tfb / 2), (tw, h, tfb + h / 2), (bft, tft, tfb + h + tft / 2)]       # (width, height, centroid y)
    A = sum(b * t for b, t, _ in parts)
    yb = sum(b * t * y for b, t, y in parts) / A
    Ix = sum(b * t ** 3 / 12 + b * t * (y - yb) ** 2 for b, t, y in parts)
    Iyt, Iyb = tft * bft ** 3 / 12, tfb * bfb ** 3 / 12
    Iy = Iyt + Iyb + h * tw ** 3 / 12
    # plastic neutral axis: equal areas above and below
    half = A / 2
    if bfb * tfb >= half:
        yp = half / bfb
    elif bfb * tfb + tw * h >= half:
        yp = tfb + (half - bfb * tfb) / tw
    else:
        yp = d - half / bft
    def first_moment(y0):                               # sum of |area x distance| about y0
        Z = 0.0
        for b, t, yc in parts:
            lo, hi = yc - t / 2, yc + t / 2
            if hi <= y0 or lo >= y0:
                Z += b * t * abs(yc - y0)
            else:
                Z += b * ((y0 - lo) ** 2 + (hi - y0) ** 2) / 2
        return Z
    Zx = first_moment(yp)
    ho = h + tft / 2 + tfb / 2
    J = (bft * tft ** 3 + h * tw ** 3 + bfb * tfb ** 3) / 3                                   # AISC Design Guide 9 Eq. 3.4
    Cw = ho ** 2 * Iyt * Iyb / (Iyt + Iyb)                                                    # Design Guide 9 (singly symmetric I); Iy ho^2 / 4 when equal
    e_sc = ho * Iyb / (Iyt + Iyb)                       # shear centre below the top flange centroid
    y_sc = (d - tft / 2) - e_sc
    W = A * 490.0 / 144.0
    p = dict(type="BU", label=name.strip(), source=SOURCE, A=A, d=d, bf=max(bft, bfb), tf=max(tft, tfb), tw=tw, h=h,
             bft=bft, tft=tft, bfb=bfb, tfb=tfb, yb=yb, Ix=Ix, Iy=Iy, Iyt=Iyt, Iyb=Iyb, Sx=Ix / max(yb, d - yb),
             Sx_top=Ix / (d - yb), Sx_bot=Ix / yb, Zx=Zx, yp=yp, rx=math.sqrt(Ix / A), ry=math.sqrt(Iy / A), J=J, Cw=Cw, ho=ho,
             h_tw=h / tw, bf_2tf=max(bft / (2 * tft), bfb / (2 * tfb)), Sy=Iy / (max(bft, bfb) / 2), y_sc=y_sc, W=W,
             kdes=max(tft, tfb), k1=tw / 2, symmetric=abs(bft - bfb) < 1e-9 and abs(tft - tfb) < 1e-9)
    p["Zy"] = (tft * bft ** 2 + tfb * bfb ** 2 + h * tw ** 2) / 4
    if p["symmetric"]:
        p["rts"] = math.sqrt(math.sqrt(Iy * Cw) / p["Sx"])
    return p


def _flip(p):
    """The same section upside down (the bottom flange on top): for negative bending of a singly symmetric section."""
    q = dict(p)
    q.update(bft=p["bfb"], tft=p["tfb"], bfb=p["bft"], tfb=p["tft"], Iyt=p["Iyb"], Iyb=p["Iyt"], yb=p["d"] - p["yb"], yp=p["d"] - p["yp"],
             Sx_top=p["Sx_bot"], Sx_bot=p["Sx_top"], y_sc=p["d"] - p["y_sc"])
    return q


class Line:
    def __init__(self, label, value, unit, source, note=""):
        self.label, self.value, self.unit, self.source, self.note = label, value, unit, source, note


def _flexure_one(p, Fy, Lb, Cb, E, L, tag):
    """Nominal major-axis flexural strength with the top flange in compression. Returns (Mn, governs)."""
    rt_ = math.sqrt(E / Fy)
    bfc, tfc, bft_, tft_ = p["bft"], p["tft"], p["bfb"], p["tfb"]
    Sxc, Sxt = p["Sx_top"], p["Sx_bot"]
    h, tw = p["h"], p["tw"]
    hc = 2 * (p["d"] - p["tft"] - p["yb"])              # twice the centroid to the inside face of the compression flange
    hp = 2 * (p["d"] - p["tft"] - p["yp"])
    hp = max(hp, 1e-6)
    Mp = min(Fy * p["Zx"], 1.6 * Fy * Sxc)              # F4-9: Mp = Fy Zx not over 1.6 Fy Sxc
    sym = p["symmetric"]
    Iyc = tfc * bfc ** 3 / 12
    kc = min(max(4 / math.sqrt(h / tw), 0.35), 0.76)
    lam_f = bfc / (2 * tfc)
    lam_pf = 0.38 * rt_
    FL_case11 = 0.7 * Fy if (Sxt / Sxc >= 0.7) else max(Fy * Sxt / Sxc, 0.5 * Fy)
    lam_rf = 0.95 * math.sqrt(kc * E / FL_case11)
    lam_w = hc / tw
    My = Fy * min(Sxc, Sxt)
    if sym:
        lam_pw = 3.76 * rt_
    else:
        lam_pw = min((hc / hp) * rt_ / (0.54 * Mp / My - 0.09) ** 2, 5.70 * rt_)
    lam_rw = 5.70 * rt_
    L.append(Line(f"{tag}compression flange bf/2tf", lam_f, "", "Table B4.1b Case 11",
                  f"compact {lam_pf:.2f}, noncompact {lam_rf:.2f} (kc = {kc:.3f}, FL = {FL_case11:.1f} ksi)"))
    L.append(Line(f"{tag}web hc/tw", lam_w, "", "Table B4.1b Case 15" if sym else "Table B4.1b Case 16", f"compact {lam_pw:.1f}, noncompact {lam_rw:.1f}"))
    flange = "compact" if lam_f <= lam_pf else "noncompact" if lam_f <= lam_rf else "slender"
    web = "compact" if lam_w <= lam_pw else "noncompact" if lam_w <= lam_rw else "slender"
    cands = {}
    if sym and web == "compact":
        # Sect. F2 / F3 (doubly symmetric, compact web)
        Sx = p["Sx"]
        rts = p["rts"]
        Lp = 1.76 * p["ry"] * rt_
        jc = p["J"] / (Sx * p["ho"])
        Lr = 1.95 * rts * (E / (0.7 * Fy)) * math.sqrt(jc + math.sqrt(jc ** 2 + 6.76 * (0.7 * Fy / E) ** 2))
        L.append(Line(f"{tag}Lp", Lp, "in", "Eq. F2-5"))
        L.append(Line(f"{tag}Lr", Lr, "in", "Eq. F2-6", f"rts = {rts:.2f} in."))
        Mp2 = Fy * p["Zx"]
        cands["yielding (F2.1)"] = Mp2
        if Lb <= Lp:
            pass
        elif Lb <= Lr:
            cands["lateral-torsional buckling (F2.2)"] = min(Cb * (Mp2 - (Mp2 - 0.7 * Fy * Sx) * (Lb - Lp) / (Lr - Lp)), Mp2)
        else:
            Fcr = Cb * math.pi ** 2 * E / (Lb / rts) ** 2 * math.sqrt(1 + 0.078 * jc * (Lb / rts) ** 2)
            cands["lateral-torsional buckling (F2.2)"] = min(Fcr * Sx, Mp2)
        if flange == "noncompact":
            cands["flange local buckling (F3.2)"] = Mp2 - (Mp2 - 0.7 * Fy * Sx) * (lam_f - lam_pf) / (lam_rf - lam_pf)
        elif flange == "slender":
            cands["flange local buckling (F3.2)"] = 0.9 * E * kc * Sx / lam_f ** 2
        sect = "F2" if flange == "compact" else "F3"
    elif web != "slender":
        # Sect. F4
        Myc = Fy * Sxc
        if Iyc / p["Iy"] > 0.23:
            Rpc = Mp / Myc if lam_w <= lam_pw else min(Mp / Myc - (Mp / Myc - 1) * (lam_w - lam_pw) / (lam_rw - lam_pw), Mp / Myc)
            Jx = p["J"]
        else:
            Rpc, Jx = 1.0, 0.0
        aw = hc * tw / (bfc * tfc)
        rt = bfc / math.sqrt(12 * (1 + aw / 6))
        FL = 0.7 * Fy if Sxt / Sxc >= 0.7 else max(Fy * Sxt / Sxc, 0.5 * Fy)
        Lp = 1.1 * rt * rt_
        jj = Jx / (Sxc * p["ho"])
        Lr = 1.95 * rt * E / FL * math.sqrt(jj + math.sqrt(jj ** 2 + 6.76 * (FL / E) ** 2))
        L.append(Line(f"{tag}Myc = Fy Sxc", Myc, "kip-in", "Eq. F4-4", f"Mp = {Mp:,.0f} kip-in. (not over 1.6 Fy Sx)"))
        L.append(Line(f"{tag}Rpc", Rpc, "", "Eq. F4-9a" if lam_w <= lam_pw else "Eq. F4-9b", f"Iyc/Iy = {Iyc / p['Iy']:.3f}"))
        L.append(Line(f"{tag}rt", rt, "in", "Eq. F4-11", f"aw = {aw:.2f} (Eq. F4-12)"))
        L.append(Line(f"{tag}Lp", Lp, "in", "Eq. F4-7"))
        L.append(Line(f"{tag}Lr", Lr, "in", "Eq. F4-8", f"FL = {FL:.1f} ksi (Eq. F4-6)"))
        cands["compression flange yielding (F4.1)"] = Rpc * Myc
        if Lb > Lp:
            if Lb <= Lr:
                M = Cb * (Rpc * Myc - (Rpc * Myc - FL * Sxc) * (Lb - Lp) / (Lr - Lp))
            else:
                Fcr = Cb * math.pi ** 2 * E / (Lb / rt) ** 2 * math.sqrt(1 + 0.078 * jj * (Lb / rt) ** 2)
                M = Fcr * Sxc
            cands["lateral-torsional buckling (F4.2)"] = min(M, Rpc * Myc)
        if flange == "noncompact":
            cands["compression flange local buckling (F4.3)"] = Rpc * Myc - (Rpc * Myc - FL * Sxc) * (lam_f - lam_pf) / (lam_rf - lam_pf)
        elif flange == "slender":
            cands["compression flange local buckling (F4.3)"] = 0.9 * E * kc * Sxc / lam_f ** 2
        if Sxt < Sxc:
            Myt = Fy * Sxt
            Mpt = min(Fy * p["Zx"], 1.6 * Fy * Sxt)       # F4-15: Mp not over 1.6 Fy Sxt
            if Iyc / p["Iy"] > 0.23:
                Rpt = Mpt / Myt if lam_w <= lam_pw else min(Mpt / Myt - (Mpt / Myt - 1) * (lam_w - lam_pw) / (lam_rw - lam_pw), Mpt / Myt)
            else:
                Rpt = 1.0
            cands["tension flange yielding (F4.4)"] = Rpt * Myt
        sect = "F4"
    else:
        # Sect. F5
        aw = min(hc * tw / (bfc * tfc), 10.0)
        Rpg = min(1 - aw / (1200 + 300 * aw) * (lam_w - 5.7 * rt_), 1.0)
        rt = bfc / math.sqrt(12 * (1 + aw / 6))
        Lp = 1.1 * rt * rt_
        Lr = math.pi * rt * math.sqrt(E / (0.7 * Fy))
        L.append(Line(f"{tag}Rpg", Rpg, "", "Eq. F5-6", f"aw = {aw:.2f}"))
        L.append(Line(f"{tag}rt", rt, "in", "Eq. F4-11"))
        L.append(Line(f"{tag}Lp", Lp, "in", "Eq. F4-7"))
        L.append(Line(f"{tag}Lr", Lr, "in", "Eq. F5-5"))
        cands["compression flange yielding (F5.1)"] = Rpg * Fy * Sxc
        if Lb > Lp:
            Fcr = min(Cb * (Fy - 0.3 * Fy * (Lb - Lp) / (Lr - Lp)), Fy) if Lb <= Lr else min(Cb * math.pi ** 2 * E / (Lb / rt) ** 2, Fy)
            cands["lateral-torsional buckling (F5.2)"] = Rpg * Fcr * Sxc
        if flange != "compact":
            lam_rf5 = 0.95 * math.sqrt(kc * E / (0.7 * Fy))
            Fcr = Fy - 0.3 * Fy * (lam_f - lam_pf) / (lam_rf5 - lam_pf) if lam_f <= lam_rf5 else 0.9 * E * kc / lam_f ** 2
            cands["compression flange local buckling (F5.3)"] = Rpg * Fcr * Sxc
        if Sxt < Sxc:
            cands["tension flange yielding (F5.4)"] = Fy * Sxt
        sect = "F5"
    governs = min(cands, key=cands.get)
    for k, v in cands.items():
        L.append(Line(f"{tag}Mn, {k}", v, "kip-in", "AISC 360-22 Sect. " + sect))
    return cands[governs], governs, sect, web, flange


def shear_panel(p, Fy, a=None, tfa=False, E=E_STEEL):
    """Nominal shear strength of a web panel of a three-plate I (AISC 360-22 Sect. G2): a = clear distance between transverse stiffeners (in.;
    None = no stiffeners, kv = 5.34); tfa: an interior panel with a / h not over 3 considering tension field action (Sect. G2.2, Eq. G2-6 to
    G2-11); otherwise Sect. G2.1 (Eq. G2-1 to G2-5). Returns dict(Vn, kv, Cv, eq, Vn2 = 0.6 Fy Aw Cv2 (the Vc2 basis of Eq. G2-17))."""
    h, tw, d = p["h"], p["tw"], p["d"]
    Aw = d * tw
    ah = (a / h) if a else None
    kv = 5.34 if (ah is None or ah > 3.0) else 5 + 5 / ah ** 2               # Eq. G2-5
    r = math.sqrt(kv * E / Fy)
    lam = h / tw
    Cv1 = 1.0 if lam <= 1.10 * r else 1.10 * r / lam                        # Eq. G2-3, G2-4
    Cv2 = 1.0 if lam <= 1.10 * r else (1.10 * r / lam if lam <= 1.37 * r else 1.51 * kv * E / (lam ** 2 * Fy))   # Eq. G2-9 to G2-11
    Vn2 = 0.6 * Fy * Aw * Cv2
    if tfa and ah is not None and ah <= 3.0:
        if lam <= 1.10 * r:
            return dict(Vn=0.6 * Fy * Aw, kv=kv, Cv=1.0, eq="Eq. G2-6", Vn2=Vn2, Cv2=Cv2, ah=ah)
        Afc, Aft = p["bft"] * p["tft"], p["bfb"] * p["tfb"]
        if 2 * Aw / (Afc + Aft) <= 2.5 and h / p["bft"] <= 6.0 and h / p["bfb"] <= 6.0:
            Vt = 0.6 * Fy * Aw * (Cv2 + (1 - Cv2) / (1.15 * math.sqrt(1 + ah ** 2)))          # Eq. G2-7
            eq = "Eq. G2-7"
        else:
            Vt = 0.6 * Fy * Aw * (Cv2 + (1 - Cv2) / (1.15 * (ah + math.sqrt(1 + ah ** 2))))   # Eq. G2-8
            eq = "Eq. G2-8"
        V1 = 0.6 * Fy * Aw * Cv1
        if V1 > Vt:                                                         # Sect. G2.2: the larger of G2.1 and G2.2 is permitted
            return dict(Vn=V1, kv=kv, Cv=Cv1, eq="Eq. G2-1 (Sect. G2.1, larger than G2.2)", Vn2=Vn2, Cv2=Cv2, ah=ah)
        return dict(Vn=Vt, kv=kv, Cv=Cv2, eq=eq, Vn2=Vn2, Cv2=Cv2, ah=ah)
    return dict(Vn=0.6 * Fy * Aw * Cv1, kv=kv, Cv=Cv1, eq="Eq. G2-1, " + ("G2-3" if Cv1 == 1.0 else "G2-4"), Vn2=Vn2, Cv2=Cv2, ah=ah)


def stiffener_check(p, Fy, a, ts, bs, Fyst, rho_w, E=E_STEEL):
    """Transverse stiffener pair (one plate each side of the web, bs wide, ts thick) by AISC 360-22 Sect. G2.4: (b / t)st not over
    0.56 (E / Fyst)^0.5 (Eq. G2-16) and Ist at least Ist2 + (Ist1 - Ist2) rho_w (Eq. G2-17 to G2-19), Ist about the web centre."""
    h, tw = p["h"], p["tw"]
    bt, bt_lim = bs / ts, 0.56 * math.sqrt(E / Fyst)
    rho_st = max(Fy / Fyst, 1.0)
    Ist = ts * (2 * bs + tw) ** 3 / 12.0
    Ist1 = h ** 4 * rho_st ** 1.3 / 40.0 * (Fy / E) ** 1.5                  # Eq. G2-18
    bp = min(a, h)
    Ist2 = max((2.5 / (a / h) ** 2 - 2) * bp * tw ** 3, 0.5 * bp * tw ** 3)   # Eq. G2-19
    need = Ist2 + (Ist1 - Ist2) * max(rho_w, 0.0)
    return dict(bt=bt, bt_lim=bt_lim, Ist=Ist, Ist1=Ist1, Ist2=Ist2, need=need, rho_st=rho_st)


def beam_check(p, Fy, Lb, Cb=1.0, method="ASD", E=E_STEEL, compression=None):
    """Major-axis flexure and shear of a three-plate I (AISC 360-22 Ch. F, G2.1(b) without stiffeners). compression: "top" (positive
    moment), "bottom" (negative moment), or None = a singly symmetric section checked with each flange in compression and the lower strength
    used (for callers that do not know the sign). Returns steel_beam.SteelBeamResult."""
    from .steel_beam import SteelBeamResult, Line as SLine, SteelInputError
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("steel beam: method must be ASD or LRFD")
    h, tw = p["h"], p["tw"]
    st = p.get("stiff")
    if st and st["a"] / h <= 1.5:
        lim, ltxt = 12.0 * math.sqrt(E / Fy), "12.0 (E/Fy)^0.5 with stiffeners at a/h not over 1.5 (AISC 360-22 Eq. F13-3)"
    else:
        lim, ltxt = 0.40 * E / Fy, "0.40 E/Fy (AISC 360-22 Eq. F13-4)"
    if h / tw > lim:
        raise SteelInputError(f"built-up section: h/tw = {h / tw:.0f} exceeds {lim:.0f}, {ltxt}")
    L = []
    for q, tag in ((p, ""), (_flip(p), "bottom flange in compression: ")) if not p["symmetric"] else ((p, ""),):
        aw = 2 * (q["d"] - q["tft"] - q["yb"]) * tw / (q["bft"] * q["tft"])
        if aw > 10:
            raise SteelInputError(f"built-up section: hc tw / (bfc tfc) = {aw:.1f} exceeds 10 (AISC 360-22 Sect. F13.2)")
        r = q["Iyt"] / q["Iy"]
        if not 0.1 <= r <= 0.9:
            raise SteelInputError(f"built-up section: Iyc/Iy = {r:.2f} is outside 0.1 to 0.9 (AISC 360-22 Sect. F13.2)")
    res = []
    if p["symmetric"] or compression in (None, "top"):
        res.append((_flexure_one(p, Fy, Lb, Cb, E, L, "" if p["symmetric"] or compression else "top flange in compression: "), "top"))
    if not p["symmetric"] and compression in (None, "bottom"):
        res.append((_flexure_one(_flip(p), Fy, Lb, Cb, E, L, "" if compression else "bottom flange in compression: "), "bottom"))
    (Mn, governs, sect, web, flange), side = min(res, key=lambda t: t[0][0])
    if not p["symmetric"]:
        governs += f" ({side} flange in compression)"
    M_avail = 0.90 * Mn if method == "LRFD" else Mn / 1.67
    L.append(Line("phi_b Mn" if method == "LRFD" else "Mn / Omega_b", M_avail, "kip-in", "Sect. F1(a): phi_b = 0.90, Omega_b = 1.67", f"governs: {governs}"))
    sp = shear_panel(p, Fy, st["a"] if st else None, False, E)              # the end panel: Sect. G2.1 (no tension field action)
    kv, Cv1, Vn = sp["kv"], sp["Cv"], sp["Vn"]
    Aw = p["d"] * tw
    V_avail = 0.90 * Vn if method == "LRFD" else Vn / 1.67
    vsrc = "Sect. G2.1(b), Eq. G2-3" if Cv1 == 1.0 else "Sect. G2.1(b), Eq. G2-4"
    L.append(Line("Vn = 0.6 Fy Aw Cv1" + (", end panel" if st else ""), Vn, "kip", "Eq. G2-1", f"Aw = d tw = {Aw:.2f} in2, kv = {kv:.2f}"
                  + (f" (Eq. G2-5, a = {st['a']:g} in., a / h = {sp['ah']:.2f})" if st and sp["ah"] <= 3 else "") + f", Cv1 = {Cv1:.3f} ({vsrc})"))
    L.append(Line("phi_v Vn" if method == "LRFD" else "Vn / Omega_v", V_avail, "kip", vsrc, "phi_v = 0.90, Omega_v = 1.67"))
    lines = [SLine(l.label, l.value, l.unit, l.source, l.note) for l in L]
    return SteelBeamResult(Mn, M_avail, Vn, V_avail, governs, flange, lines)


def column_check(p, Fy, Lcx, Lcy, Lcz=None, method="ASD", E=E_STEEL):
    """Axial compression of a three-plate I: E3 flexural buckling, E4 torsional (doubly symmetric, Eq. E4-2) or flexural-torsional (singly
    symmetric about the vertical axis, Eq. E4-3), E7 slender elements with Table B4.1a Case 2 for the flanges. Lcz None = Lcy."""
    from .steel_column import SteelColumnResult
    from .steel_beam import Line as SLine, SteelInputError
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("steel column: method must be ASD or LRFD")
    if Fy <= 0 or Lcx <= 0 or Lcy <= 0:
        raise SteelInputError("steel column: Fy, Lcx and Lcy must be positive")
    Lcz = Lcy if Lcz is None else Lcz
    L = []
    rt_ = math.sqrt(E / Fy)
    h, tw = p["h"], p["tw"]
    kc = min(max(4 / math.sqrt(h / tw), 0.35), 0.76)
    lam_rf = 0.64 * math.sqrt(kc * E / Fy)
    lam_rw = 1.49 * rt_
    L.append(SLine("flanges b/t", p["bf_2tf"], "", "Table B4.1a Case 2", f"kc = {kc:.3f}; nonslender limit {lam_rf:.2f}"))
    L.append(SLine("web h/tw", h / tw, "", "Table B4.1a Case 5", f"nonslender limit {lam_rw:.1f}"))
    sx, sy = Lcx / p["rx"], Lcy / p["ry"]
    Fex, Fey = math.pi ** 2 * E / sx ** 2, math.pi ** 2 * E / sy ** 2
    L.append(SLine("Lcx / rx, Lcy / ry", max(sx, sy), "", "Sect. E2", f"{sx:.1f} and {sy:.1f}"))
    Fez0 = math.pi ** 2 * E * p["Cw"] / Lcz ** 2 + G_STEEL * p["J"]
    modes = {"flexural buckling about x (E3)": Fex, "flexural buckling about y (E3)": Fey}
    if p["symmetric"]:
        modes["torsional buckling (E4)"] = Fez0 / (p["Ix"] + p["Iy"])
        L.append(SLine("Fe, torsional", modes["torsional buckling (E4)"], "ksi", "Eq. E4-2", f"Lcz = {Lcz:.1f} in., Cw = {p['Cw']:,.0f} in6, J = {p['J']:.2f} in4"))
    else:
        yo = p["y_sc"] - p["yb"]
        ro2 = yo ** 2 + (p["Ix"] + p["Iy"]) / p["A"]
        H = 1 - yo ** 2 / ro2
        Fez = Fez0 / (p["A"] * ro2)
        # the axis of symmetry is the vertical (y) axis: Eq. E4-3 with Fey
        Fe = (Fey + Fez) / (2 * H) * (1 - math.sqrt(1 - 4 * Fey * Fez * H / (Fey + Fez) ** 2))
        modes["flexural-torsional buckling (E4)"] = Fe
        L.append(SLine("yo, ro^2, H", yo, "in", "Eq. E4-9, E4-8", f"ro^2 = {ro2:.1f} in2, H = {H:.3f}"))
        L.append(SLine("Fez", Fez, "ksi", "Eq. E4-7", f"Lcz = {Lcz:.1f} in., Cw = {p['Cw']:,.0f} in6, J = {p['J']:.2f} in4"))
        L.append(SLine("Fe, flexural-torsional", Fe, "ksi", "Eq. E4-3", f"Fey = {Fey:.1f} ksi"))
    governs = min(modes, key=modes.get)
    Fe = modes[governs]
    L.append(SLine("Fe", Fe, "ksi", "Sect. E3 / E4", f"governs: {governs}"))
    Fn = 0.658 ** (Fy / Fe) * Fy if Fy / Fe <= 2.25 else 0.877 * Fe
    L.append(SLine("Fn", Fn, "ksi", "Eq. E3-2" if Fy / Fe <= 2.25 else "Eq. E3-3", f"Fy/Fe = {Fy / Fe:.3f}"))
    Ae = p["A"]
    for nm, lam, lr, c1, c2, b, t, count in (("web", h / tw, lam_rw, 0.18, 1.31, h, tw, 1),
                                             ("top flange", p["bft"] / (2 * p["tft"]), lam_rf, 0.22, 1.49, p["bft"] / 2, p["tft"], 2),
                                             ("bottom flange", p["bfb"] / (2 * p["tfb"]), lam_rf, 0.22, 1.49, p["bfb"] / 2, p["tfb"], 2)):
        if lam <= lr * math.sqrt(Fy / Fn):
            continue
        Fel = (c2 * lr / lam) ** 2 * Fy
        be = b * (1 - c1 * math.sqrt(Fel / Fn)) * math.sqrt(Fel / Fn)
        Ae -= count * (b - be) * t
        L.append(SLine(f"{nm}: effective width", be, "in", "Eq. E7-3, E7-5", f"Fel = {Fel:.1f} ksi; full width {b:.2f} in."))
    Pn = Fn * Ae
    L.append(SLine("Pn = Fn Ae" if Ae < p["A"] else "Pn = Fn Ag", Pn, "kip", "Eq. E7-1" if Ae < p["A"] else "Eq. E3-1",
                   f"Ae = {Ae:.2f} in2" if Ae < p["A"] else ""))
    P_avail = 0.90 * Pn if method == "LRFD" else Pn / 1.67
    L.append(SLine("phi_c Pn" if method == "LRFD" else "Pn / Omega_c", P_avail, "kip", "Sect. E1: phi_c = 0.90, Omega_c = 1.67"))
    return SteelColumnResult(Pn, P_avail, Fn, governs, max(sx, sy), L)


def _plastic_moment(strips):
    """Plastic moment of a section made of strips [(x0, x1, width, Fy)] along one axis (the depth): the plastic neutral axis where the yield
    forces balance, then M = sum of Fy |x - PNA| dA (kip-in. with in. and ksi)."""
    tot = sum((x1 - x0) * w * F for x0, x1, w, F in strips)
    lo, hi = min(s[0] for s in strips), max(s[1] for s in strips)
    for _ in range(80):
        mid = (lo + hi) / 2
        below = sum(max(0.0, min(x1, mid) - x0) * w * F for x0, x1, w, F in strips)
        lo, hi = (mid, hi) if below < tot / 2 else (lo, mid)
    pna = (lo + hi) / 2
    M = 0.0
    for x0, x1, w, F in strips:
        for a_, b_ in ((x0, min(x1, pna)), (max(x0, pna), x1)):
            if b_ > a_:
                M += F * w * (b_ - a_) * abs((a_ + b_) / 2 - pna)
    return M, pna


def end_panel_tfa(p, Fy, a, ts, bs, Fyst, e_end, E=E_STEEL):
    """End web panel with tension field action, AISC 360-22 Sect. G2.3 (Eq. G2-12 to G2-15), with a pair of end (bearing) stiffeners bs wide,
    ts thick, their inside face e_end from the end of the girder. Flanges of unequal area: Mpf from the smaller flange (Commentary Sect. G2.3).
    Returns dict(Vn, beta_v, de, Mpf, Mpst, Mpm, Cv2, kv, eq)."""
    h, tw, d = p["h"], p["tw"], p["d"]
    Aw = d * tw
    ah = a / h
    if ah > 3.0:
        raise ValueError("a / h over 3: Sect. G2.3 does not apply")
    kv = 5 + 5 / ah ** 2
    r = math.sqrt(kv * E / Fy)
    lam = h / tw
    Cv2 = 1.0 if lam <= 1.10 * r else (1.10 * r / lam if lam <= 1.37 * r else 1.51 * kv * E / (lam ** 2 * Fy))
    de = 35 * tw * (0.8 - Cv2) ** 2 if Cv2 <= 0.8 else 0.0                         # Eq. G2-14, G2-15
    fl = min(((p["bft"], p["tft"]), (p["bfb"], p["tfb"])), key=lambda f: f[0] * f[1])
    Mpf, _ = _plastic_moment([(0.0, fl[1], fl[0], Fy)] + ([(fl[1], fl[1] + de, tw, Fy)] if de > 0 else []))
    e_eff = min(e_end, 0.84 * tw * math.sqrt(E / Fy))
    Lw = de + e_eff                                                                  # web in the end post, measured from the girder end
    x1 = e_eff                                                                       # the stiffener's inside face
    x0 = max(0.0, x1 - ts)
    strips = [(0.0, Lw, tw, Fy)] if Lw > 0 else []
    strips.append((x0, x1, 2 * bs, Fyst))                                            # the two plates beside the web (the web counted above)
    if Lw <= 0:
        strips.append((x0, x1, tw, Fy))
    Mpst, _ = _plastic_moment(strips)
    Mpm = min(Mpf, Mpst)
    if Cv2 >= 1.0:
        return dict(Vn=0.6 * Fy * Aw, beta_v=0.0, de=de, Mpf=Mpf, Mpst=Mpst, Mpm=Mpm, Cv2=Cv2, kv=kv, eq="Eq. G2-12 (Cv2 = 1)")
    beta = min(1.0, 2.8 * (math.sqrt(Mpf + Mpm) + math.sqrt(Mpst + Mpm)) / (h * math.sqrt(Fy * tw * (1 - Cv2))))   # Eq. G2-13
    Vn = 0.6 * Fy * Aw * (Cv2 + beta * (1 - Cv2) / (1.15 * math.sqrt(1 + ah ** 2)))                              # Eq. G2-12
    return dict(Vn=Vn, beta_v=beta, de=de, Mpf=Mpf, Mpst=Mpst, Mpm=Mpm, Cv2=Cv2, kv=kv, eq="Eq. G2-12", e_eff=e_eff, Lw=Lw)


def flange_web_weld(p, V, w, FEXX, Fu, method, l=None, s=None, P=None, lb=None):
    """Flange-to-web fillet welds of a three-plate I (both sides of the web at each flange), as AISC Design Examples v16.0 Example F.14:
    shear flow q = V Q / Ix at the flange with the larger Q (Q of that flange about the elastic neutral axis); weld strength per inch, both
    sides, phi 0.60 FEXX (0.707 w) x 2 (AISC 360-22 Eq. J2-4, kds = 1.0; Manual Eq. 8-2a / 8-2b); web base metal 0.60 Fu tw (Eq. J4-4 per inch,
    Sect. J2 and J4.2); flange base metal 2 x 0.60 Fu tf; minimum size Table J2.4. Intermittent welds of length l at s on centres: strengths x l / s,
    l at least 4 w and 1-1/2 in. (Sect. J2.2b(e)). P, lb: a concentrated load bearing on the top flange without a stiffener, taken by the top
    welds over lb + 5 tf and added to the shear flow as a vector. Returns dict."""
    lrfd = method == "LRFD"
    av = (lambda Rn: 0.75 * Rn) if lrfd else (lambda Rn: Rn / 2.00)
    d, yb, Ix, tw = p["d"], p["yb"], p["Ix"], p["tw"]
    Qt = p["bft"] * p["tft"] * (d - yb - p["tft"] / 2)
    Qb = p["bfb"] * p["tfb"] * (yb - p["tfb"] / 2)
    Q = max(Qt, Qb)
    q = V * Q / Ix
    fv = 0.0
    if P and lb is not None:
        fv = P / (lb + 5 * p["tft"])
    qt = V * Qt / Ix
    q_top = math.hypot(qt, fv)
    demand = max(q, q_top)
    f = (l / s) if (l and s) else 1.0
    R_w = av(0.60 * FEXX * 0.7071 * w) * 2 * f
    R_web = av(0.60 * Fu * tw) * f
    tf_min = min(p["tft"], p["tfb"])
    R_fl = av(0.60 * Fu * tf_min) * 2 * f
    tthin = min(tw, tf_min)
    wmin = 0.125 if tthin <= 0.25 else 0.1875 if tthin <= 0.5 else 0.25 if tthin <= 0.75 else 0.3125     # Table J2.4
    lmin = max(4 * w, 1.5) if (l and s) else None
    return dict(Qt=Qt, Qb=Qb, Q=Q, q=q, fv=fv, q_top=q_top, demand=demand, R_w=R_w, R_web=R_web, R_fl=R_fl, wmin=wmin, f=f, lmin=lmin)
