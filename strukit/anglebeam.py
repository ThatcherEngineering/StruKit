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
    if g["equal"]:
        return 0.0
    key = (round(g["bl"], 3), round(g["bs"], 3))
    if key not in BETA_W:
        raise AngleBeamError(f"no beta_w for an L{g['bl']:g}x{g['bs']:g} in AISC 360-22 Commentary Table C-F10.1; this angle is outside the check")
    return BETA_W[key]


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


def principal_strengths(a, g, Fy, pts, Bw, Bz, Lb, Cb):
    """Mnw and Mnz (kip-in.) for moments with these signs: Bw > 0 compresses points with z > 0; Bz > 0 compresses points with w > 0."""
    t = g["t"]
    legs = {"A": g["bs"], "C": g["bl"]}
    Sw = {k: a["Iw"] / abs(p[1]) for k, p in pts.items() if p[1]}
    Sz = {k: a["Iz"] / abs(p[0]) for k, p in pts.items() if p[0]}
    # major axis
    Myw = Fy * min(Sw.values())
    lw = [("yielding", 1.5 * Myw, "1.5 Fy Sw (Eq. F10-1)")]
    comp_w = [k for k in ("A", "C") if pts[k][1] and Bw * pts[k][1] > 0]
    bw = beta_w(g)
    sign = 1.0 if ("A" in comp_w and "C" not in comp_w) else -1.0
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
