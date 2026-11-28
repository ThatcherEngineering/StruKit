"""Concrete pilaster (pier) on a spread footing carrying a metal building column: the pier, the frame thrust, the footing.

Source on file: ACI 318-19. Every check names its section or table:
  22.2.2.4.1, 22.2.1.2, Table 22.2.2.4.3, Table 21.2.2      flexure with axial load by strain compatibility, phi by the net tensile strain
  22.4.2.1, Table 22.4.2.1 (a), Eq. (22.4.2.2)              maximum axial strength 0.80 Po (ties)
  10.6.1.1                                                  longitudinal bars 0.01 to 0.08 Ag
  Table 22.5.5.1 (a), (c), 22.5.5.1.1 to .3, 22.5.8.5.3     shear of the pier with its axial force, the ties as shear reinforcement
  25.7.2.1, 25.7.2.2                                        tie spacing and size
  10.7.6.1.5                                                ties enclosing the anchor rods within 5 in. of the top: two No. 4 or three No. 3
  6.2.5.1                                                   slenderness may be neglected: k lu / r <= 22 (sway), k = 2.0 (the pier cantilevers from the footing)
  Table 25.4.2.3 ("other cases"), 25.4.2.1(b), Table 25.4.2.5  development length of hairpins and tie beam bars
The frame thrust is taken by one of:
  "soil"      friction under the footing and passive pressure on the footing, the pier below grade and any stem wall counted with it,
              at service loads against a required safety factor (values from the soils source)
  "hairpin"   hairpin bars into the floor slab: steel 0.90 As fy (Table 21.2.1) and their development into the slab
  "tie beam"  a tie beam to the pilaster across the building: steel 0.90 As fy and the bars' development into the pilaster
The footing: bearing, overturning and flexure by footing_moment.check_eccentric with the pier's moment and shear at its base.

Units: inches, pounds, psi; loads in the case tables in kips and kip-ft (converted here).
"""
import math

from . import footing_moment as fm
from .stemwall import BAR_AREA, BAR_DIA, ES, beta1, phi_flexure, Check, StemWallError


class PilasterError(ValueError):
    pass


THRUST = ("soil", "hairpin", "tie beam")


def layers(h, cover, tie_db, bar, n_face, n_side):
    """Bar layers along h: (depth from the compression face, area) for n_face bars on each face across the bending direction and
    n_side bars on each side face between them."""
    db, Ab = BAR_DIA[bar], BAR_AREA[bar]
    d1 = cover + tie_db + db / 2
    out = [(d1, n_face * Ab), (h - d1, n_face * Ab)]
    for k in range(1, n_side + 1):
        out.append((d1 + k * (h - 2 * d1) / (n_side + 1), 2 * Ab))
    return sorted(out)


def interaction(b, h, fc, fy, lay):
    """Points (c, phi Pn, phi Mn, phi, eps_t) of the P-M interaction about the centroid, compression positive (lb, lb-in)."""
    b1 = beta1(fc)
    Ast = sum(a for _, a in lay)
    Po = 0.85 * fc * (b * h - Ast) + fy * Ast                          # 22.4.2.2
    Pmax = 0.80 * Po                                                     # Table 22.4.2.1(a)
    dt = max(d for d, _ in lay)
    pts = []
    cs = [h * k / 400.0 for k in range(1, 401)] + [h * (1 + k / 20.0) for k in range(1, 200)]
    for c in cs:
        a = min(b1 * c, h)
        P = 0.85 * fc * a * b
        M = P * (h / 2 - a / 2)
        for d, As in lay:
            eps = 0.003 * (c - d) / c
            fs = max(min(eps * ES, fy), -fy)
            if d <= a:
                fs -= 0.85 * fc                                          # concrete displaced by the bar
            P += As * fs
            M += As * fs * (h / 2 - d)
        et = 0.003 * (dt - c) / c
        ph, _ = phi_flexure(et, fy)
        pts.append((c, ph * min(P, Pmax), ph * M, ph, et))
    # pure tension
    pts.insert(0, (0.0, -0.90 * fy * Ast, 0.0, 0.90, 1.0))
    return pts, Pmax, Po


def phi_Mn_at(pts, Pu):
    """phi Mn at the factored axial load Pu (compression positive), by straight-line interpolation along the curve; None when Pu is
    outside it."""
    best = None
    for (c1, P1, M1, *_), (c2, P2, M2, *_) in zip(pts[:-1], pts[1:]):
        lo, hi = min(P1, P2), max(P1, P2)
        if lo - 1e-6 <= Pu <= hi + 1e-6 and hi > lo:
            M = M1 + (M2 - M1) * (Pu - P1) / (P2 - P1)
            best = M if best is None else max(best, M)
    return best


def ld_other(bar, fy, fc, psi_t=1.0, psi_e=1.0):
    """Table 25.4.2.3, 'other cases', normalweight; psi_g by Table 25.4.2.5; not less than 12 in. (25.4.2.1(b))."""
    db = BAR_DIA[bar]
    psi_g = 1.0 if fy <= 60000 else (1.15 if fy <= 80000 else 1.3)
    den = 50.0 if bar <= 6 else 40.0
    return max(3 * fy * psi_t * psi_e * psi_g / (den * math.sqrt(fc)) * db, 12.0)


def check(bx, by, hp, below, fc, fy, conc_pcf, cover, bar, n_face, n_side, tie_bar, tie_s, top_ties, top_tie_bar,
          footing, cases_strength, cases_service, thrust="soil", soil=None, hairpin=None, tie=None, wall_len=0.0, wall_t=0.0,
          wall_depth=0.0, dagg=0.75):
    """bx: pier dimension along the thrust (in), by across it; hp: pier height from the top of the footing to the base plate (in);
    below: pier height below grade (in). Bars: n_face #bar on each face across the thrust, n_side on each side face; ties #tie_bar at
    tie_s; top_ties #top_tie_bar within 5 in. of the top. footing: dict(B_ft along the thrust, L_ft, h_in, bar, n_x, n_y, cover,
    q_allow, soil_depth_ft, soil_pcf, ot_required). cases_strength / cases_service: [(name, P lb down, V lb thrust, M lb-in at the
    base plate, D factor)]. thrust: 'soil' with soil=dict(passive_pcf, mu, sf, neglect_ft, depth_ft (grade to footing bottom));
    'hairpin' with hairpin=dict(n, bar, leg_in); 'tie beam' with tie=dict(n, bar, embed_in, e_in). A pilaster in a stem wall counts
    wall_len (ft) of wall, wall_t thick, wall_depth (in) below grade, in passive pressure."""
    if thrust not in THRUST:
        raise PilasterError("pilaster: the thrust is taken by soil, hairpins or a tie beam")
    for nm, v in (("pier dimension along the thrust", bx), ("pier dimension across it", by), ("pier height", hp), ("f'c", fc), ("fy", fy),
                  ("concrete unit weight", conc_pcf), ("cover", cover)):
        if v is None or v <= 0:
            raise PilasterError(f"pilaster: the {nm} must be a positive number")
    if bar not in BAR_DIA or tie_bar not in BAR_DIA:
        raise PilasterError("pilaster: bar sizes #3 to #11")
    if n_face < 2 or n_side < 0:
        raise PilasterError("pilaster: at least two bars on each face across the thrust")
    if not cases_strength or not cases_service:
        raise PilasterError("pilaster: give the factored and the service base reactions")
    checks, lines, notes = [], [], []
    sq = math.sqrt(fc)
    db, dt_ = BAR_DIA[bar], BAR_DIA[tie_bar]
    lay = layers(bx, cover, dt_, bar, n_face, n_side)
    Ag, Ast = bx * by, sum(a for _, a in lay)
    W_pier = bx * by * hp / 1728.0 * conc_pcf
    lines.append(("pier weight", W_pier, "lb", "", f"{bx:g} x {by:g} x {hp:g} in. at {conc_pcf:g} pcf, case D"))
    # ---- reinforcement and ties
    checks.append(Check("longitudinal bars, at least 0.01 Ag", 0.01 * Ag, Ast, "in2", "-", "ACI 318-19 10.6.1.1",
                        f"{2 * n_face + 2 * n_side} #{bar}; demand is 0.01 Ag"))
    checks.append(Check("longitudinal bars, not over 0.08 Ag", Ast, 0.08 * Ag, "in2", "-", "ACI 318-19 10.6.1.1", ""))
    smax = min(16 * db, 48 * dt_, min(bx, by))
    checks.append(Check("tie spacing", tie_s, smax, "in", "-", "ACI 318-19 25.7.2.1(b)", "least of 16 db, 48 db of the tie and the least pier dimension"))
    checks.append(Check("tie size, bar No.", 3 if bar <= 10 else 4, tie_bar, "", "-", "ACI 318-19 25.7.2.2", "demand is the smallest tie bar size"))
    need = 2 if (top_tie_bar or 0) >= 4 else 3
    checks.append(Check("ties around the anchor rods, within 5 in. of the top", need, top_ties or 0, "ties", "-", "ACI 318-19 10.7.6.1.5",
                        "two No. 4 or three No. 3 ties or hoops enclosing the rods and at least four bars"))
    r_ = 0.3 * min(bx, by)
    checks.append(Check("slenderness may be neglected, k lu / r", 2.0 * hp / r_, 22.0, "", "-", "ACI 318-19 6.2.5.1, 6.2.5.2",
                        f"k = 2.0 (cantilever from the footing), lu = {hp:g} in., r = 0.3 x {min(bx, by):g} in."))
    # ---- pier strength, each factored case
    pts, Pmax, Po = interaction(by, bx, fc, fy, lay)
    e_tie = (tie or {}).get("e_in", 0.0) if thrust == "tie beam" else (hairpin or {}).get("e_in", 0.0) if thrust == "hairpin" else None
    worst_m = worst_v = None
    for nm, P, V, Mb, fD in cases_strength:
        Pu_top = P
        arm = hp if thrust == "soil" else (e_tie or 0.0)
        Mu = abs(Mb) + abs(V) * arm
        cand = []
        for Pq in (P, P + fD * W_pier):                                  # the axial load at the top and at the base, whichever gives less
            m_ = phi_Mn_at(pts, Pq)
            if m_ is None:
                raise PilasterError(f"pilaster: {nm}: the axial load {Pq / 1000:.1f} kips is beyond the pier's axial strength")
            cand.append((m_, Pq))
        phiMn, Pu_top = min(cand)
        r = Mu / phiMn if phiMn > 0 else float("inf")
        if worst_m is None or r > worst_m[0]:
            worst_m = (r, nm, Pu_top, Mu, phiMn)
        d = bx - cover - dt_ - db / 2
        Nu = Pu_top
        nterm = max(min(Nu / (6 * Ag), 0.05 * fc), -1e12)
        Av = 2 * BAR_AREA[tie_bar]
        Avmin = max(0.75 * sq * by * tie_s / fy, 50 * by * tie_s / fy)
        if Av >= Avmin:
            Vc = max((2 * sq + nterm) * by * d, 0.0)
            src = "Table 22.5.5.1(a)"
        else:
            rho = (n_face * BAR_AREA[bar]) / (by * d)
            ls = min(math.sqrt(2 / (1 + d / 10)), 1.0)
            Vc = max((8 * ls * rho ** (1 / 3) * sq + nterm) * by * d, 0.0)
            src = "Table 22.5.5.1(c), 22.5.5.1.3"
        Vc = min(Vc, 5 * sq * by * d)
        Vs = Av * fy * d / tie_s
        cap = 0.75 * (Vc + Vs)
        if worst_v is None or abs(V) / cap > worst_v[0]:
            worst_v = (abs(V) / cap, nm, abs(V), cap, Vc, Vs, src, Nu)
    _, nm, Pu, Mu, phiMn = worst_m
    checks.append(Check("pier, moment with axial load", Mu / 12.0, phiMn / 12.0, "lb-ft", nm,
                        "ACI 318-19 22.2.2.4.1, 22.4.2.1; phi by Table 21.2.2",
                        f"Pu = {Pu:,.0f} lb (top or base of the pier, whichever gives less); Mu = M at the base plate + V x {('hp' if thrust == 'soil' else 'the tie offset')}; "
                        f"phi Pn,max = 0.65 x 0.80 Po = {0.65 * Pmax:,.0f} lb"))
    _, nm, V, cap, Vc, Vs, src, Nu = worst_v
    checks.append(Check("pier shear", V, cap, "lb", nm, f"ACI 318-19 {src}, 22.5.8.5.3; phi = 0.75",
                        f"Vc = {Vc:,.0f} lb with Nu = {Nu:,.0f} lb (22.5.5.1.2); Vs = {Vs:,.0f} lb from #{tie_bar} ties, 2 legs, at {tie_s:g} in."))
    # ---- thrust
    if thrust == "soil":
        if not soil:
            raise PilasterError("pilaster: give the passive pressure, friction coefficient and required safety factor")
        pp, mu, sf = soil["passive_pcf"], soil["mu"], soil["sf"]
        Df = soil["depth_ft"]                                           # grade to the footing bottom
        z0 = soil.get("neglect_ft", 0.0) or 0.0
        hf = footing["h_in"] / 12.0
        L = footing["L_ft"]
        def band(z1, z2, w):                                            # passive force on a face w ft wide from depth z1 to z2 (ft)
            z1, z2 = max(z1, z0), max(z2, z0)
            return 0.5 * pp * (z2 ** 2 - z1 ** 2) * w if z2 > z1 else 0.0
        Pp = band(Df - hf, Df, L) + band(Df - hf - below / 12.0, Df - hf, by / 12.0)
        if wall_len:
            Pp += band(0.0, wall_depth / 12.0, wall_len)
        W_ftg = footing["B_ft"] * L * hf * conc_pcf
        W_soil = (footing["B_ft"] * L - bx * by / 144.0) * (footing.get("soil_depth_ft") or 0.0) * (footing.get("soil_pcf") or 0.0)
        worst = None
        for nm, P, V, Mb, fD in cases_service:
            if abs(V) <= 0:
                continue
            N = P + fD * (W_pier + W_ftg + W_soil)
            F = mu * max(N, 0.0)
            r = (F + Pp) / abs(V)
            if worst is None or r < worst[0]:
                worst = (r, nm, F, abs(V), N)
        lines.append(("passive resistance", Pp, "lb", "soils source", f"{pp:g} pcf on the footing face ({L:g} ft wide, {hf * 12:g} in.), the pier below grade"
                      + (f" and {wall_len:g} ft of stem wall {wall_depth:g} in. deep" if wall_len else "") + (f"; top {z0:g} ft neglected" if z0 else "")))
        if worst:
            r, nm, F, V, N = worst
            checks.append(Check("sliding, friction and passive pressure", sf, r, "", nm,
                                "statics; friction coefficient, passive pressure and required safety factor from the soils source",
                                f"(mu N + Pp) / V = ({mu:g} x {N:,.0f} + {Pp:,.0f}) / {V:,.0f}; the dead loads with the combination's D factor; "
                                "demand is the required safety factor"))
        fV = 1.0
    else:
        Vu = max(abs(V) for _, _, V, _, _ in cases_strength)
        nmV = max(cases_strength, key=lambda x: abs(x[2]))[0]
        dd = hairpin if thrust == "hairpin" else tie
        if not dd:
            raise PilasterError(f"pilaster: give the {thrust} bars")
        n, b_ = dd["n"], dd["bar"]
        legs = 2 * n if thrust == "hairpin" else n
        cap = 0.90 * legs * BAR_AREA[b_] * fy
        checks.append(Check(f"{thrust} bars in tension", Vu, cap, "lb", nmV, "ACI 318-19 22.4.3; phi = 0.90 (Table 21.2.1)",
                            f"{legs} legs of #{b_}" if thrust == "hairpin" else f"({n}) #{b_}"))
        ld = ld_other(b_, fy, fc)
        have = dd["leg_in"] if thrust == "hairpin" else dd["embed_in"]
        checks.append(Check(f"{thrust} bar development", ld, have, "in", "-", "ACI 318-19 Table 25.4.2.3 (other cases), 25.4.2.1(b)",
                            ("each leg into the slab" if thrust == "hairpin" else "into the pilaster") + "; demand is ld"))
        fV = 0.0
    # ---- footing: P, M and V at its top; the pier, footing and soil weights with each combination's D factor
    f = footing
    W_ftg = f["B_ft"] * f["L_ft"] * f["h_in"] / 12.0 * conc_pcf
    W_soil = (f["B_ft"] * f["L_ft"] - bx * by / 144.0) * (f.get("soil_depth_ft") or 0.0) * (f.get("soil_pcf") or 0.0)
    W_all = W_pier + W_ftg + W_soil
    lines.append(("pier, footing and soil weight", W_all, "lb", "", f"pier {W_pier:,.0f}, footing {W_ftg:,.0f}, soil {W_soil:,.0f} lb; "
                  "taken with each combination's D factor"))
    serv, strg = [], []
    up = None
    for nm, P, V, Mb, fD in cases_service:
        Mt = (abs(Mb) + abs(V) * (hp if thrust == "soil" else (e_tie or 0.0))) / 12.0
        if P < 0:
            r = fD * W_all / -P
            if up is None or r < up[0]:
                up = (r, nm, -P, fD * W_all)
        if P + fD * W_all > 0:
            serv.append(dict(name=nm, P=P + fD * W_all, M=Mt, V=fV * abs(V)))
    if up:
        checks.append(Check("uplift resisted by weight", up[2], up[3], "lb", up[1], "statics; the dead weights at the combination's D factor",
                            "pier, footing and soil over it; demand is the net uplift at the base plate"))
    for nm, P, V, Mb, fD in cases_strength:
        Mt = (abs(Mb) + abs(V) * (hp if thrust == "soil" else (e_tie or 0.0))) / 12.0
        if P + fD * W_all > 0:
            strg.append(dict(name=nm, P=P + fD * W_all, M=Mt, V=fV * abs(V), wt_factor=0.0))
    B_in = f["B_ft"] * 12.0
    over = None
    for lst in (serv, strg):
        keep = []
        for c in lst:
            e = (abs(c["M"]) * 12 + abs(c["V"]) * f["h_in"]) / c["P"]
            if e >= B_in / 2:
                if over is None or e > over[0]:
                    over = (e, c["name"])
            else:
                keep.append(c)
        lst[:] = keep
    if over:
        checks.append(Check("footing: resultant within the footing", over[0], B_in / 2, "in", over[1],
                            "statics: eccentricity (M + V h) / P at the footing bottom against B/2",
                            "the footing overturns under this combination (passive pressure not counted against overturning)"))
    if not serv or not strg:
        return dict(checks=checks, lines=lines, notes=notes, footing=None, pts=pts, Pmax=Pmax, layers=lay, W_pier=W_pier)
    try:
        fr = fm.check_eccentric(f["B_ft"], f["L_ft"], f["h_in"], fc, fy, bx, by, f["bar"], f["n_x"], f["n_y"], f["cover"], f["q_allow"], 1e-9,
                                serv, strg, ot_required=f.get("ot_required"))
    except fm.FootingInputError as e:
        raise PilasterError(f"pilaster footing: {e}")
    return dict(checks=checks, lines=lines, notes=notes, footing=fr, pts=pts, Pmax=Pmax, layers=lay, W_pier=W_pier)
