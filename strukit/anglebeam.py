"""Single angle in bending, AISC 360-22 Sect. F10 (yielding, lateral-torsional buckling, leg local buckling), Sect. G3 (shear) and Sect. H2
(biaxial bending about the principal axes), as worked in AISC Design Examples v16.0, Examples F.11A, F.11B and F.11C.

Orientation: one leg vertical (its toe up or down), the other horizontal, pointing to +x from the heel. Vertical loads act downward when
positive. Sideways loads are positive when they act from the toe of the horizontal leg toward the heel (-x). Simple span, both ends braced.

Two routes, as Sect. F10 allows:
  geometric axis (x-x) design: an equal-leg angle with vertical loads only (Sect. F10.2(2), no restraint or restraint at the point of largest
  moment only), or any angle with continuous lateral-torsional restraint (then lateral-torsional buckling does not apply);
  principal axis design otherwise: the moments resolved on the major (w) and minor (z) principal axes, Eq. F10-4 for the w axis, yielding and
  leg local buckling for both, and Eq. H2-1 checked at the toes and the heel with the sign of each term by whether it compresses that point.

Section properties from the AISC Shapes Database v16.0 (single-angle table, which carries the principal-axis values; points A short-leg toe,
B heel, C long-leg toe). Signs of the principal coordinates come from the angle's geometry (two rectangles, fillets left out)."""
import math

E = 29000.0

# beta_w, AISC 360-22 Commentary Table C-F10.1, by (long leg, short leg) in inches; positive with the short leg in compression
BETA_W = {(8, 6): 3.31, (8, 4): 5.48, (7, 4): 4.37, (6, 4): 3.14, (6, 3.5): 3.69, (5, 3.5): 2.40, (5, 3): 2.99, (4, 3.5): 0.87, (4, 3): 1.65,
          (3.5, 3): 0.87, (3.5, 2.5): 1.62, (3, 2.5): 0.86, (3, 2): 1.56, (2.5, 2): 0.85, (2.5, 1.5): 1.49}


class AngleBeamError(ValueError):
    pass


def cb_f1(Ms):
    """AISC 360-22 Eq. F1-1 from the absolute moments at the ends, quarter points and maximum of a segment: Ms = (Mmax, MA, MB, MC)."""
    Mmax, MA, MB, MC = Ms
    return 12.5 * Mmax / (2.5 * Mmax + 3 * MA + 4 * MB + 3 * MC) if Mmax > 0 else 1.0


def leg_local(Fy, b, t, Sc):
    """Sect. F10.3 for a leg whose toe is in compression; Table B4.1b Case 12 limits. Returns (Mn or None if compact, text)."""
    lam, lp, lr = b / t, 0.54 * math.sqrt(E / Fy), 0.91 * math.sqrt(E / Fy)
    if lam <= lp:
        return None, f"b / t = {lam:.1f} not over lambda_p = {lp:.1f}: compact"
    if lam <= lr:
        return Fy * Sc * (2.43 - 1.72 * lam * math.sqrt(Fy / E)), f"b / t = {lam:.1f}, lambda_p = {lp:.1f}, lambda_r = {lr:.1f}: noncompact, Eq. F10-6"
    return 0.71 * E / lam ** 2 * Sc, f"b / t = {lam:.1f} over lambda_r = {lr:.1f}: slender, Eq. F10-7, F10-8"


def ltb(My, Mcr):
    """Eq. F10-2 / F10-3."""
    if My / Mcr <= 1.0:
        return min((1.92 - 1.17 * math.sqrt(My / Mcr)) * My, 1.5 * My), "Eq. F10-2"
    return (0.92 - 0.17 * Mcr / My) * Mcr, "Eq. F10-3"


def geometry(a, vertical, toe):
    """Legs and geometric properties for the orientation. vertical: 'long' or 'short' leg vertical (either for equal legs); toe: 'up' or 'down'
    (toe of the vertical leg)."""
    bl, bs, t = max(a["b"], a["d"]), min(a["b"], a["d"]), a["t"]
    equal = abs(bl - bs) < 1e-9
    long_v = equal or vertical == "long"
    if not equal and vertical not in ("long", "short"):
        raise AngleBeamError("say whether the long or the short leg is vertical")
    if toe not in ("up", "down"):
        raise AngleBeamError("say whether the toe of the vertical leg points up or down")
    Lv, Lh = (bl, bs) if long_v else (bs, bl)
    Ix, ybar, S_toe = (a["Ix"], a["ybar"], a["Sx"]) if long_v else (a["Iy"], a["xbar"], a["Sy"])   # table Ix is about the axis across the long leg
    S_heel = Ix / ybar                                                     # to the outside face of the horizontal leg
    S_top, S_bot = (S_toe, S_heel) if toe == "up" else (S_heel, S_toe)
    return dict(bl=bl, bs=bs, t=t, equal=equal, Lv=Lv, Lh=Lh, Ix=Ix, ybar=ybar, S_top=S_top, S_bot=S_bot, S_min=min(S_toe, S_heel), toe=toe, long_v=long_v)


def principal_points(a, g):
    """Unit vectors of the major (w) and minor (z) principal axes in the x-y plane and the signed principal coordinates (w, z) of points A, B, C,
    with the magnitudes of the shapes table and the signs from the angle's geometry."""
    t, Lv, Lh = g["t"], g["Lv"], g["Lh"]
    sgn = 1.0 if g["toe"] == "up" else -1.0
    rects = [(0.0, 0.0 if sgn > 0 else -Lv, t, Lv), (t, 0.0 if sgn > 0 else -t, Lh - t, t)]
    A_ = sum(w * h for _, _, w, h in rects)
    xc = sum(w * h * (x + w / 2) for x, y, w, h in rects) / A_
    yc = sum(w * h * (y + h / 2) for x, y, w, h in rects) / A_
    Ix = sum(w * h ** 3 / 12 + w * h * (y + h / 2 - yc) ** 2 for x, y, w, h in rects)
    Iy = sum(h * w ** 3 / 12 + w * h * (x + w / 2 - xc) ** 2 for x, y, w, h in rects)
    Ixy = sum(w * h * (x + w / 2 - xc) * (y + h / 2 - yc) for x, y, w, h in rects)
    th = 0.5 * math.atan2(-2 * Ixy, Ix - Iy)
    u = (math.cos(th), math.sin(th))
    v = (-u[1], u[0])
    Iu = Ix * u[1] ** 2 + Iy * u[0] ** 2 - 2 * Ixy * u[0] * u[1]          # about the axis along u: distances measured across it
    Iv = Ix * v[1] ** 2 + Iy * v[0] ** 2 - 2 * Ixy * v[0] * v[1]
    w_hat, z_hat = (u, v) if Iu >= Iv else (v, u)
    vtoe, htoe, heel = (t / 2, sgn * Lv), (Lh, sgn * t / 2), (0.0, 0.0)
    short_toe, long_toe = (htoe, vtoe) if g["long_v"] else (vtoe, htoe)
    pts = {}
    for name, p, key in (("A", short_toe, "A"), ("B", heel, "B"), ("C", long_toe, "C")):
        dx, dy = p[0] - xc, p[1] - yc
        pw, pz = dx * w_hat[0] + dy * w_hat[1], dx * z_hat[0] + dy * z_hat[1]
        W, Z = a.get("w" + key, 0.0), a.get("z" + key, 0.0)
        pts[name] = (math.copysign(W, pw) if W else 0.0, math.copysign(Z, pz) if Z else 0.0)
    return w_hat, z_hat, pts


def beta_w(g):
    """|beta_w| (in.): AISC 360-22 Commentary Table C-F10.1 for the sizes it lists; otherwise by the table's footnote,
    beta_w = (1 / Iw) integral over A of z (w^2 + z^2) dA - 2 z0, with the angle as two rectangles (fillets left out) and the shear center at the
    intersection of the leg mid-lines (within 1.2 percent of the table's values for every size it lists, tests/test_angle_beam.py)."""
    if g["equal"]:
        return 0.0
    key = (round(g["bl"], 3), round(g["bs"], 3))
    if key in BETA_W:
        return BETA_W[key]
    return beta_w_formula(g["bl"], g["bs"], g["t"])


def beta_w_source(g):
    if g["equal"]:
        return "equal legs"
    return ("AISC 360-22 Commentary Table C-F10.1" if (round(g["bl"], 3), round(g["bs"], 3)) in BETA_W else
            "AISC 360-22 Commentary Table C-F10.1 footnote [a], fillets neglected")


def beta_w_formula(L, S, t, n=400):
    """|beta_w| by the footnote of Commentary Table C-F10.1, numerically over the two legs (long leg L, short leg S, thickness t, in.)."""
    pts = []
    for x0, y0, w_, h_, nx, ny in ((0.0, 0.0, t, L, 8, n), (t, 0.0, S - t, t, n, 8)):
        dA = w_ * h_ / (nx * ny)
        pts += [(x0 + (i + 0.5) * w_ / nx, y0 + (j + 0.5) * h_ / ny, dA) for i in range(nx) for j in range(ny)]
    A = sum(p[2] for p in pts)
    xc, yc = sum(p[0] * p[2] for p in pts) / A, sum(p[1] * p[2] for p in pts) / A
    Ix = sum((p[1] - yc) ** 2 * p[2] for p in pts)
    Iy = sum((p[0] - xc) ** 2 * p[2] for p in pts)
    Ixy = sum((p[0] - xc) * (p[1] - yc) * p[2] for p in pts)
    th = 0.5 * math.atan2(-2 * Ixy, Ix - Iy)
    best = None
    for ang in (th, th + math.pi / 2):
        u = (math.cos(ang), math.sin(ang)); v = (-u[1], u[0])
        Iw = sum(((p[0] - xc) * v[0] + (p[1] - yc) * v[1]) ** 2 * p[2] for p in pts)
        if best is None or Iw > best[0]:
            best = (Iw, u, v)
    Iw, u, v = best
    z0 = (t / 2 - xc) * v[0] + (t / 2 - yc) * v[1]
    I3 = 0.0
    for x, y, dA in pts:
        dx, dy = x - xc, y - yc
        w_, z_ = dx * u[0] + dy * u[1], dx * v[0] + dy * v[1]
        I3 += z_ * (w_ * w_ + z_ * z_) * dA
    return abs(I3 / Iw - 2 * z0)


def geometric_strength(a, g, Fy, restraint, Lb, Cb):
    """Geometric axis Mn (kip-in.) under downward load (top in compression). restraint: 'none', 'max' (at the point of largest moment only) or
    'continuous'."""
    t = g["t"]
    lims = [("yielding", 1.5 * Fy * g["S_min"], "Mn = 1.5 My = 1.5 Fy S (Eq. F10-1)")]
    out = dict(My_yield=Fy * g["S_min"])
    toe_comp = g["toe"] == "up"
    b_c = g["Lv"] if toe_comp else g["Lh"]                       # leg whose toe is at the compression side
    Sc = g["S_top"] * (1.0 if restraint == "continuous" else 0.8)
    out.update(Sc=Sc, b_c=b_c)
    if restraint != "continuous":
        b = g["bl"]
        root = math.sqrt(1 + 0.88 * (Lb * t / b ** 2) ** 2)
        Mcr = 0.58 * E * b ** 4 * t * Cb / Lb ** 2 * (root - 1 if toe_comp else root + 1)
        My = (0.8 if restraint == "none" else 1.0) * Fy * g["S_min"]
        if restraint == "max":
            Mcr *= 1.25
        Mn, eq = ltb(My, Mcr)
        out.update(Mcr=Mcr, My=My, eq_ltb=("Eq. F10-5a" if toe_comp else "Eq. F10-5b") + (" x 1.25" if restraint == "max" else ""))
        lims.append(("lateral-torsional buckling", Mn, f"My = {My:.1f} kip-in., Mcr = {Mcr:.1f} kip-in. ({out['eq_ltb']}); {eq}"))
    Mll, txt = leg_local(Fy, b_c, t, Sc)
    out["llb_text"] = txt
    if Mll is not None:
        lims.append(("leg local buckling", Mll, f"Sc = {Sc:.3f} in3; {txt}"))
    gov = min(lims, key=lambda x: x[1])
    out.update(limits=lims, Mn=gov[1], governs=gov[0], text=gov[2])
    return out


def principal_strengths(a, g, Fy, pts, Bw, Bz, Lb, Cb, neg_beta=False):
    """Mnw and Mnz (kip-in.) for moments with these signs: Bw > 0 compresses points with z > 0; Bz > 0 compresses points with w > 0.
    neg_beta: the major-axis moment reverses within the unbraced segment; the negative beta_w is used for the whole segment (AISC 360-22
    Commentary Sect. F10.2)."""
    t = g["t"]
    legs = {"A": g["bs"], "C": g["bl"]}
    Sw = {k: a["Iw"] / abs(p[1]) for k, p in pts.items() if p[1]}
    Sz = {k: a["Iz"] / abs(p[0]) for k, p in pts.items() if p[0]}
    # major axis
    Myw = Fy * min(Sw.values())
    lw = [("yielding", 1.5 * Myw, "1.5 Fy Sw (Eq. F10-1)")]
    comp_w = [k for k in ("A", "C") if pts[k][1] and Bw * pts[k][1] > 0]
    bw = beta_w(g)
    sign = -1.0 if neg_beta else (1.0 if ("A" in comp_w and "C" not in comp_w) else -1.0)
    bw_s = sign * bw
    rz = a["rz"]
    Mcr = 9 * E * a["A"] * rz * t * Cb / (8 * Lb) * (math.sqrt(1 + (4.4 * bw_s * rz / (Lb * t)) ** 2) + 4.4 * bw_s * rz / (Lb * t))
    Mn_l, eq = ltb(Myw, Mcr)
    lw.append(("lateral-torsional buckling", Mn_l, f"Mcr = {Mcr:.1f} kip-in. (Eq. F10-4, beta_w = {(f"{bw_s:+.2f} in." if bw_s else "0")}, Cb = {Cb:.2f}); {eq}"))
    for k in comp_w:
        Mll, txt = leg_local(Fy, legs[k], t, Sw[k])
        if Mll is not None:
            lw.append((f"leg local buckling (toe {k})", Mll, f"Sc = Sw{k} = {Sw[k]:.3f} in3; {txt}"))
    # minor axis: no lateral-torsional buckling (User Note, Sect. F10)
    Myz = Fy * min(Sz.values())
    lz = [("yielding", 1.5 * Myz, "1.5 Fy Sz (Eq. F10-1)")]
    for k in ("A", "C"):
        if pts[k][0] and Bz * pts[k][0] > 0:
            Mll, txt = leg_local(Fy, legs[k], t, Sz[k])
            if Mll is not None:
                lz.append((f"leg local buckling (toe {k})", Mll, f"Sc = Sz{k} = {Sz[k]:.3f} in3; {txt}"))
    gw, gz = min(lw, key=lambda x: x[1]), min(lz, key=lambda x: x[1])
    return dict(Mnw=gw[1], gov_w=gw, lim_w=lw, Mnz=gz[1], gov_z=gz, lim_z=lz, Mcr=Mcr, Myw=Myw, Myz=Myz, beta_w=bw_s, Sw=Sw, Sz=Sz)


def interaction(pts, Bw, Bz, cw, cz):
    """Eq. H2-1 with moments: at each point the term is + when the moment compresses the point, - when it puts it in tension, 0 on the axis."""
    out = {}
    for k, (pw, pz) in pts.items():
        tw = 0.0 if not pz else math.copysign(abs(Bw) / cw, Bw * pz)
        tz = 0.0 if not pw else math.copysign(abs(Bz) / cz, Bz * pw)
        out[k] = tw + tz
    return out


def shear(Fy, b, t):
    """Sect. G3: Vn = 0.6 Fy b t Cv2, Cv2 by Sect. G2.2 with h / tw = b / t, kv = 1.2 (kips)."""
    lam, kv = b / t, 1.2
    a_ = 1.10 * math.sqrt(kv * E / Fy)
    c_ = 1.37 * math.sqrt(kv * E / Fy)
    Cv2, eq = (1.0, "G2-9") if lam <= a_ else ((a_ / lam, "G2-10") if lam <= c_ else (1.51 * kv * E / (lam ** 2 * Fy), "G2-11"))
    return 0.6 * Fy * b * t * Cv2, Cv2, eq


def compression_strength(a, Fy, Lc):
    """Single angle, axial compression about the minor principal axis: AISC 360-22 Sect. E3 with Lc / rz, and Sect. E7 (Table E7.1 case (c),
    c1 = 0.22, c2 = 1.49) for a slender leg. Flexural-torsional buckling (Sect. E4) is not built: legs with b / t over 0.71 (E / Fy)^0.5 are
    refused. Returns dict(Fe, Fn, Ae, Pn, steps)."""
    t = a["t"]
    legs = sorted((a["b"], a["d"]), reverse=True)
    lr, lft = 0.45 * math.sqrt(E / Fy), 0.71 * math.sqrt(E / Fy)
    if legs[0] / t > lft:
        raise AngleBeamError(f"b / t = {legs[0] / t:.1f} is over 0.71 (E / Fy)^0.5 = {lft:.1f}: flexural-torsional buckling (AISC 360-22 Sect. E4) applies and is not built")
    slr = Lc / a["rz"]
    Fe = math.pi ** 2 * E / slr ** 2
    Fn = 0.658 ** (Fy / Fe) * Fy if Fy / Fe <= 2.25 else 0.877 * Fe
    Ae, notes = a["A"], []
    for b in legs:
        lam = b / t
        lim = lr * math.sqrt(Fy / Fn)
        if lam > lim:                                                      # Sect. E7.1(b)
            Fel = (1.49 * lr / lam) ** 2 * Fy                              # Eq. E7-5
            be = b * (1 - 0.22 * math.sqrt(Fel / Fn)) * math.sqrt(Fel / Fn)  # Eq. E7-3
            Ae -= t * (b - be)
            notes.append(dict(b=b, lam=lam, lim=lim, Fel=Fel, be=be))
    return dict(Lc_r=slr, Fe=Fe, Fn=Fn, Ae=Ae, Pn=Fn * Ae, slender=notes, lam_r=lr, lam_ft=lft)


def eccentric_compression(a, Fy, L, attached, e_off, P, method):
    """Single angle loaded in compression through one leg with the load eccentric to the centroid (AISC 360-22 Sect. H2 with the moments of
    the eccentricity on the principal axes, Appendix 8 B1 on each axis with Cm = 1.0), as worked in AISC Design Examples v16.0 Example E.14B.
    The load acts at mid-width of the attached leg, e_off (in.) outside the back of that leg (at the gusset). L: length (in.), the effective
    length for buckling about z and for B1 (K = 1.0). P: required axial compression (kips). Returns the strengths and the H2-1 ratio at A, B, C."""
    lrfd = method == "LRFD"
    g = geometry(a, attached, "up")                                        # the attached leg drawn vertical, its back at x = 0, toe up
    w_hat, z_hat, _ = principal_points(a, g)                               # w_hat, z_hat: the directions in which distances from the w and z axes are measured
    xc, yc = (a["xbar"], a["ybar"]) if g["long_v"] else (a["ybar"], a["xbar"])
    t_ = g["t"]
    vtoe, htoe = (t_ / 2, g["Lv"]), (g["Lh"], t_ / 2)
    short_toe, long_toe = (htoe, vtoe) if g["long_v"] else (vtoe, htoe)
    pts = {}
    for k, p_ in (("A", short_toe), ("B", (0.0, 0.0)), ("C", long_toe)):
        dw = (p_[0] - xc) * w_hat[0] + (p_[1] - yc) * w_hat[1]          # distance from the w axis
        dz = (p_[0] - xc) * z_hat[0] + (p_[1] - yc) * z_hat[1]          # distance from the z axis
        pts[k] = (math.copysign(a.get("w" + k, 0.0), dz) if a.get("w" + k) else 0.0, math.copysign(a.get("z" + k, 0.0), dw) if a.get("z" + k) else 0.0)
    xl, yl = -e_off, g["Lv"] / 2.0
    ew = (xl - xc) * w_hat[0] + (yl - yc) * w_hat[1]                     # the load's distance from the w axis (Example E.14B "ew")
    ez = (xl - xc) * z_hat[0] + (yl - yc) * z_hat[1]                     # and from the z axis ("ez")
    Mw, Mz = P * ew, P * ez                                                # + where it compresses the points on the load's side
    c = compression_strength(a, Fy, L)
    Pc = 0.90 * c["Pn"] if lrfd else c["Pn"] / 1.67
    s = principal_strengths(a, g, Fy, pts, Mw, Mz, L, 1.0)
    Mcw = 0.90 * s["Mnw"] if lrfd else s["Mnw"] / 1.67
    Mcz = 0.90 * s["Mnz"] if lrfd else s["Mnz"] / 1.67
    alpha = 1.0 if lrfd else 1.6
    Pe1w, Pe1z = math.pi ** 2 * E * a["Iw"] / L ** 2, math.pi ** 2 * E * a["Iz"] / L ** 2
    if alpha * P >= min(Pe1w, Pe1z):
        raise AngleBeamError("the axial load is over the elastic buckling load of the angle (B1 unbounded)")
    B1w, B1z = max(1.0, 1.0 / (1 - alpha * P / Pe1w)), max(1.0, 1.0 / (1 - alpha * P / Pe1z))
    terms = interaction(pts, B1w * Mw, B1z * Mz, Mcw, Mcz)
    ratios = {k: P / Pc + v for k, v in terms.items()}
    gov = max(ratios, key=lambda k: ratios[k])
    return dict(ew=ew, ez=ez, Mw=Mw, Mz=Mz, comp=c, Pc=Pc, flex=s, Mcw=Mcw, Mcz=Mcz, Pe1w=Pe1w, Pe1z=Pe1z, B1w=B1w, B1z=B1z,
                ratios=ratios, gov=gov, ratio=ratios[gov], pts=pts, g=g, w_hat=w_hat)


def eccentric_capacity(a, Fy, L, attached, e_off, method):
    """The axial load at which the H2-1 ratio of eccentric_compression reaches 1.0 (bisection)."""
    lo, hi = 0.0, 0.0
    hi = compression_strength(a, Fy, L)["Pn"]
    for _ in range(80):
        mid = (lo + hi) / 2
        try:
            r = eccentric_compression(a, Fy, L, attached, e_off, mid, method)["ratio"]
        except AngleBeamError:
            r = 2.0
        lo, hi = (mid, hi) if r <= 1.0 else (lo, mid)
    return lo


def _span_defl(L, ld, x):
    """Deflection (times EI) at x of a simple span L under one load: dict(kind 'uniform' w per length | 'point' P at a). Same units."""
    if ld["kind"] == "uniform":
        w = ld["w"]
        return w * x * (L ** 3 - 2 * L * x * x + x ** 3) / 24.0
    P, a_ = ld["P"], ld["x"]
    b_ = L - a_
    if x <= a_:
        return P * b_ * x * (L * L - b_ * b_ - x * x) / (6.0 * L)
    xr = L - x
    return P * a_ * xr * (L * L - a_ * a_ - xr * xr) / (6.0 * L)


def deflection(a, g, L, loads, restraint):
    """Deflection of a simply supported single angle under service loads (in.). L in.; loads: dict(kind 'uniform' (w kip/in.) or
    'point' (P kip at x in.), dir 'down' or 'sideways'). restraint 'continuous': bending about the geometric axis with g["Ix"], vertical only
    (down loads). Otherwise the loads are resolved on the principal axes and each component bends the angle about the other principal axis
    (AISC 360-22 Commentary Sect. F10.2: the angle deflects laterally as well as in the direction of the load; Figure C-F10.2); the
    displacement is the vector sum. Returns dict(x, dv, dh, d) at the station of the largest resultant, and the station grid used."""
    xs = [L * i / 96 for i in range(97)] + [ld["x"] for ld in loads if ld["kind"] == "point"]
    best = dict(x=0.0, dv=0.0, dh=0.0, d=0.0)
    if restraint == "continuous":
        for x in xs:
            dv = sum(_span_defl(L, ld, x) for ld in loads if ld.get("dir", "down") == "down") / (E * g["Ix"])
            if abs(dv) > abs(best["d"]):
                best = dict(x=x, dv=dv, dh=0.0, d=abs(dv))
        return best
    w_hat, z_hat, _ = principal_points(a, g)
    Iw, Iz = a["Iw"], a["Iz"]
    for x in xs:
        ux = uy = 0.0
        for ld in loads:
            F = (0.0, -1.0) if ld.get("dir", "down") == "down" else (-1.0, 0.0)          # unit force direction in x (toward the toe), y (up)
            k = _span_defl(L, ld, x)
            fw, fz = F[0] * w_hat[0] + F[1] * w_hat[1], F[0] * z_hat[0] + F[1] * z_hat[1]
            uw, uz = k * fw / (E * Iz), k * fz / (E * Iw)                                  # along w bends about z (Iz); along z about w (Iw)
            ux += uw * w_hat[0] + uz * z_hat[0]
            uy += uw * w_hat[1] + uz * z_hat[1]
        d = (ux * ux + uy * uy) ** 0.5
        if d > best["d"]:
            best = dict(x=x, dv=-uy, dh=ux, d=d)
    return best
