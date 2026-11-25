"""Beam end coped at the top flange: strength of the coped web, AISC Manual Part 9
(Eq. 9-9 to 9-20) as worked in AISC Design Examples v16.0, Example II.A-6, with
AISC 360-22 Sect. J4.2 (shear) and J4.3 (block shear).

Branches the example exercises: c/d <= 1.0 (Eq. 9-20a), c/hc <= 1.0 (Eq. 9-19a) and
lambda_p < lambda <= 2 lambda_p (Eq. 9-11). The other branches (f = 1 + c/d for c/d over
1.0; k = 2.2 hc/c for c/hc over 1.0; Mn = Fcr Sc with Fcr = 0.903 E k1 / lambda^2 beyond
2 lambda_p) are the Manual's as generally published; the Manual itself is not on hand."""
import math

E = 29000.0


class CopeError(ValueError):
    pass


def tee(d, tw, bf, tf, dc):
    """Elastic and plastic moduli of the coped section (bottom flange and web of depth
    hc = d - dc, fillets not counted), about its horizontal axis. Sc is to the top (the
    cut edge)."""
    hc = d - dc
    if hc <= tf + 0.5:
        raise CopeError("cope: the cope leaves no web")
    Af, Aw, hw = bf * tf, (hc - tf) * tw, hc - tf
    A = Af + Aw
    y = (Af * tf / 2 + Aw * (tf + hw / 2)) / A
    I = bf * tf ** 3 / 12 + Af * (y - tf / 2) ** 2 + tw * hw ** 3 / 12 + Aw * (tf + hw / 2 - y) ** 2
    Sc = I / (hc - y)
    if Af >= A / 2:                                   # plastic neutral axis in the flange
        yp = A / 2 / bf
        Zc = bf * yp * yp / 2 + bf * (tf - yp) ** 2 / 2 + Aw * (tf + hw / 2 - yp)
    else:
        yp = tf + (A / 2 - Af) / tw
        Zc = Af * (yp - tf / 2) + tw * (yp - tf) ** 2 / 2 + tw * (hc - yp) ** 2 / 2
    return dict(hc=hc, A=A, y=y, I=I, Sc=Sc, Zc=Zc)


def top_cope(d, tw, bf, tf, Fy, Fu, dc, c, e, holes=0, hole=0.0):
    """Nominal strengths (kips) of a beam end coped at the top flange only. dc: cope depth;
    c: cope length; e: distance from the reaction to the end of the cope (in.). holes, hole:
    number of bolt holes in the vertical line through the web and the hole width deducted
    (dh + 1/16), for shear rupture. Returns a dict with every intermediate value."""
    if dc <= 0 or c <= 0 or e <= 0:
        raise CopeError("cope: the cope depth, cope length and e must be positive")
    if dc > d / 2:
        raise CopeError("cope: a cope deeper than half the beam depth is outside AISC Manual Part 9")
    if c > 2 * d:
        raise CopeError("cope: a cope longer than twice the beam depth is outside AISC Manual Part 9")
    s = tee(d, tw, bf, tf, dc)
    hc = s["hc"]
    f = 2 * c / d if c / d <= 1.0 else 1 + c / d
    k = 2.2 * (hc / c) ** 1.65 if c / hc <= 1.0 else 2.2 * hc / c
    k1 = max(f * k, 1.61)
    Mp, My = Fy * s["Zc"], Fy * s["Sc"]
    lam, lam_p = hc / tw, 0.475 * math.sqrt(k1 * E / Fy)
    if lam <= lam_p:
        Mn, eq = Mp, "Mn = Mp (Manual Eq. 9-10)"
    elif lam <= 2 * lam_p:
        Mn, eq = Mp - (Mp - My) * (lam / lam_p - 1), "Mn = Mp - (Mp - My)(lambda / lambda_p - 1) (Manual Eq. 9-11)"
    else:
        Mn, eq = 0.903 * E * k1 / lam ** 2 * s["Sc"], "Mn = Fcr Sc, Fcr = 0.903 E k1 / lambda^2 (Manual Eq. 9-12, 9-13)"
    Agv = hc * tw
    Anv = Agv - holes * hole * tw
    return dict(s, f=f, k=k, k1=k1, Mp=Mp, My=My, lam=lam, lam_p=lam_p, Mn=Mn, eq=eq, e=e, R_flex=Mn / e,
                Agv=Agv, Anv=Anv, R_vy=0.60 * Fy * Agv, R_vr=0.60 * Fu * Anv)


def web_block_shear(tw, Fy, Fu, n, spacing, lev, leh, hole):
    """Block shear of the coped web at one vertical row of n bolts (AISC 360-22 Eq. J4-5,
    Ubs = 1.0): lev from the cut edge to the first bolt, leh from the bolt line to the beam
    end; hole = dh + 1/16."""
    Agv = (lev + (n - 1) * spacing) * tw
    Anv = Agv - (n - 0.5) * hole * tw
    Ant = (leh - 0.5 * hole) * tw
    return dict(Agv=Agv, Anv=Anv, Ant=Ant, Rn=min(0.60 * Fu * Anv, 0.60 * Fy * Agv) + Fu * Ant)


def double_cope(d, tw, Fy, Fu, dct, dcb, c, e, holes=0, hole=0.0):
    """Beam end coped at both flanges, equal cope lengths c: the remaining web as a rectangular bar, AISC 360-22 Sect. F11 with Lb = c and
    Cb by AISC Manual Eq. 9-21, as worked in AISC Design Examples v16.0 Example II.A-7. dct, dcb: cope depths at the top (compression) and
    bottom flanges."""
    if min(dct, dcb, c, e) <= 0:
        raise CopeError("cope: the cope depths, cope length and e must be positive")
    hc = d - dct - dcb
    if hc <= 1.0:
        raise CopeError("cope: the copes leave no web")
    Cb = max((3 + math.log(c / d)) * (1 - dct / d), 1.84)
    Sc, Zc = tw * hc ** 2 / 6, tw * hc ** 2 / 4
    My, Mp = Fy * Sc, Fy * Zc
    lam = c * hc / tw ** 2
    if lam <= 0.08 * E / Fy:
        Mn, eq = Mp, "Mn = Mp (Eq. F11-1)"
    elif lam <= 1.9 * E / Fy:
        Mn, eq = min(Cb * (1.52 - 0.274 * lam * Fy / E) * My, Mp), "Mn = Cb [1.52 - 0.274 (Lb d / t^2) Fy / E] My, not over Mp (Eq. F11-3)"
    else:
        Mn, eq = min(1.9 * E * Cb / lam * Sc, Mp), "Mn = Fcr Sx, Fcr = 1.9 E Cb / (Lb d / t^2), not over Mp (Eq. F11-4, F11-5)"
    Agv = hc * tw
    Anv = Agv - holes * hole * tw
    return dict(hc=hc, Cb=Cb, Sc=Sc, Zc=Zc, My=My, Mp=Mp, lam=lam, Mn=Mn, eq=eq, e=e, R_flex=Mn / e, Agv=Agv, Anv=Anv, R_vy=0.60 * Fy * Agv, R_vr=0.60 * Fu * Anv)



def tee_flexure(Fy, Sx, Sxc, Zx, bf, tf, ltb=None):
    """Nominal flexural strength (kip-in.) of a tee with its stem in tension, AISC 360-22 Sect. F9: yielding (Eq. F9-1 to F9-3, Mp not
    over 1.6 My), lateral-torsional buckling (Eq. F9-6 to F9-11) when ltb = dict(d, Iy, J, ry, Lb) is given, and flange local buckling
    (Eq. F9-14, F9-15; limits of Table B4.1b Case 10). Sx is to the tip of the stem (the smaller modulus), Sxc to the flange. Returns
    every value, each limit state and the governing one."""
    My = Fy * Sx
    Mp = min(Fy * Zx, 1.6 * My)
    out = dict(My=My, Mp=Mp, Mp_raw=Fy * Zx)
    lims = [("yielding", Mp, "Mn = Mp = Fy Zx, not over 1.6 My (Eq. F9-1, F9-2)")]
    if ltb and ltb.get("Lb", 0) > 0:
        dd, Iy, J, ry, Lb = ltb["d"], ltb["Iy"], ltb["J"], ltb["ry"], ltb["Lb"]
        Lp = 1.76 * ry * math.sqrt(E / Fy)
        Lr = 1.95 * (E / Fy) * math.sqrt(Iy * J) / Sx * math.sqrt(2.36 * (Fy / E) * dd * Sx / J + 1)
        B = 2.3 * (dd / Lb) * math.sqrt(Iy / J)
        Mcr = 1.95 * E / Lb * math.sqrt(Iy * J) * (B + math.sqrt(1 + B * B))
        out.update(Lp=Lp, Lr=Lr, B=B, Mcr=Mcr, Lb=Lb)
        if Lb <= Lp:
            out["ltb"] = "Lb not over Lp: lateral-torsional buckling does not apply (Sect. F9.2(a)(1))"
        elif Lb <= Lr:
            lims.append(("lateral-torsional buckling", Mp - (Mp - My) * (Lb - Lp) / (Lr - Lp), "Mn = Mp - (Mp - My)(Lb - Lp)/(Lr - Lp) (Eq. F9-6)"))
        else:
            lims.append(("lateral-torsional buckling", Mcr, "Mn = Mcr (Eq. F9-7, F9-10)"))
    lam = bf / (2 * tf)
    lpf, lrf = 0.38 * math.sqrt(E / Fy), 1.0 * math.sqrt(E / Fy)
    out.update(lam_f=lam, lam_pf=lpf, lam_rf=lrf)
    if lam > lrf:
        lims.append(("flange local buckling", 0.7 * E * Sxc / lam ** 2, "Mn = 0.7 E Sxc / (bf / 2tf)^2 (Eq. F9-15)"))
    elif lam > lpf:
        lims.append(("flange local buckling", min(Fy * Zx - (Fy * Zx - 0.7 * Fy * Sxc) * (lam - lpf) / (lrf - lpf), 1.6 * My),
                     "Mn = Mp - (Mp - 0.7 Fy Sxc)(lambda - lambda_pf)/(lambda_rf - lambda_pf), not over 1.6 My (Eq. F9-14)"))
    gov = min(lims, key=lambda x: x[1])
    out.update(limits=lims, Mn=gov[1], governs=gov[0], eq=gov[2])
    return out


def bottom_cope(d, tw, bf, tf, Fy, Fu, dc, c, e, holes=0, hole=0.0):
    """Beam end coped at the bottom flange only, the end reaction downward (top flange in compression at the cope). AISC Manual Part 9
    (15th Ed.) gives no local buckling procedure for this case; the remaining tee (top flange and web, fillets not counted) is checked
    as a tee with its stem in tension by AISC 360-22 Sect. F9, with Lb = c (braced at the end of the cope), and for flexural rupture by
    Mn = Fu Znet (Manual Eq. 9-4 in the 15th Ed., 9-8 in the numbering of Design Examples v16.0; no bolt holes at the end of the cope). Shear yielding and rupture of the remaining web (Eq. J4-3, J4-4) are
    returned as well."""
    if dc <= 0 or c <= 0 or e <= 0:
        raise CopeError("cope: the cope depth, cope length and e must be positive")
    if dc > d / 2:
        raise CopeError("cope: a bottom cope deeper than half the beam depth is outside this check")
    if c > 2 * d:
        raise CopeError("cope: a cope longer than twice the beam depth is outside this check")
    s = tee(d, tw, bf, tf, dc)
    hc, y, I = s["hc"], s["y"], s["I"]
    Sx, Sxc = I / max(y, hc - y), I / y
    hw = hc - tf
    Iy = tf * bf ** 3 / 12 + hw * tw ** 3 / 12
    J = (bf * tf ** 3 + hw * tw ** 3) / 3
    ry = math.sqrt(Iy / s["A"])
    fl = tee_flexure(Fy, Sx, Sxc, s["Zc"], bf, tf, ltb=dict(d=hc, Iy=Iy, J=J, ry=ry, Lb=c))
    Agv = hc * tw
    Anv = Agv - holes * hole * tw
    return dict(s, Sx=Sx, Sxc=Sxc, Iy=Iy, J=J, ry=ry, **{k: v for k, v in fl.items()}, e=e, R_flex=fl["Mn"] / e,
                Mr=Fu * s["Zc"], R_rup=Fu * s["Zc"] / e, Agv=Agv, Anv=Anv, R_vy=0.60 * Fy * Agv, R_vr=0.60 * Fu * Anv)
