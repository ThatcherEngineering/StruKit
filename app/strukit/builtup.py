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


def beam_check(p, Fy, Lb, Cb=1.0, method="ASD", E=E_STEEL, compression=None):
    """Major-axis flexure and shear of a three-plate I (AISC 360-22 Ch. F, G2.1(b) without stiffeners). compression: "top" (positive
    moment), "bottom" (negative moment), or None = a singly symmetric section checked with each flange in compression and the lower strength
    used (for callers that do not know the sign). Returns steel_beam.SteelBeamResult."""
    from .steel_beam import SteelBeamResult, Line as SLine, SteelInputError
    if method not in ("ASD", "LRFD"):
        raise SteelInputError("steel beam: method must be ASD or LRFD")
    h, tw = p["h"], p["tw"]
    lim = 0.40 * E / Fy                                 # F13.2, no transverse stiffeners (a/h over 1.5)
    if h / tw > lim:
        raise SteelInputError(f"built-up section: h/tw = {h / tw:.0f} exceeds 0.40 E/Fy = {lim:.0f} for a web without stiffeners (AISC 360-22 Eq. F13-4); "
                              "stiffened girders are not built")
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
    kv = 5.34                                            # G2.1(b)(2)(ii), no transverse stiffeners
    lim_v = 1.10 * math.sqrt(kv * E / Fy)
    Cv1 = 1.0 if h / tw <= lim_v else lim_v / (h / tw)
    Aw = p["d"] * tw
    Vn = 0.6 * Fy * Aw * Cv1
    V_avail = 0.90 * Vn if method == "LRFD" else Vn / 1.67
    vsrc = "Sect. G2.1(b), Eq. G2-3" if Cv1 == 1.0 else "Sect. G2.1(b), Eq. G2-4"
    L.append(Line("Vn = 0.6 Fy Aw Cv1", Vn, "kip", "Eq. G2-1", f"Aw = d tw = {Aw:.2f} in2, kv = 5.34, Cv1 = {Cv1:.3f} ({vsrc})"))
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
