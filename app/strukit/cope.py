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
