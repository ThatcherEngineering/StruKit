"""Concrete stem wall (foundation wall): checked with or without a footing under it.

Source on file: ACI 318-19. Every check names the section or table it comes from:
  Table 21.2.2      phi for moment by the net tensile strain (tension controlled, transition, compression controlled)
  22.2.2.4.1        equivalent rectangular stress block; Table 22.2.2.4.3 beta1; 20.2.2.2 Es = 29,000,000 psi
  Table 22.5.5.1, 22.5.5.1.1, 22.5.5.1.3    Vc (with Av >= Av,min: Eq. (a); without: Eq. (c) with the size effect factor)
  22.5.1.2          Vu <= phi (Vc + 8 sqrt(f'c) bw d)
  22.5.8.5.3        Vs = Av fyt d / s
  9.6.1.2           As,min for beams; 9.6.3.1 / Table 9.6.3.1 where Av,min is required; Table 9.6.3.4 Av,min
  Table 9.7.6.2.2   maximum spacing of stirrup legs along the beam
  Table 9.3.1.1, 9.3.1.1.1   minimum beam depth for which deflections need not be calculated
  9.7.2.3           skin reinforcement where h exceeds 36 in.
  9.2.3.1           spacing of lateral bracing not over 50 times the least width of the compression face
  Table 24.3.2, 24.3.2.1    spacing of bars closest to the tension face (fs = 2/3 fy)
  Table 11.6.1, 11.7.2.1    minimum wall reinforcement and spacing of wall bars
  Table 20.5.1.3.1  specified concrete cover
  14.5.1.7, 14.5.2.1, Table 14.5.5.1, Table 21.2.1   plain concrete wall in flexure and shear (phi = 0.60)

Three ways the wall is supported along its length:
  "footing"  on a continuous footing (the footing is checked on its own sheet; the line load at its base is reported)
  "soil"     bearing directly on soil, no footing: the wall's bottom is its own bearing width
  "spans"    spanning between footings or piers with voids (or soft or no soil) below: a continuous grade beam

Out of plane: unbalanced backfill (an equivalent fluid pressure from the soils source, plus a lateral surcharge pressure)
on a wall braced at its top by a floor or slab; the wall spans vertically from its base to the brace, pinned at both.

Units: inches, pounds, psi unless a name says ft, plf, pcf or psf.
"""
import math
from dataclasses import dataclass, field

from . import beam as bm
from . import contbeam

BAR_DIA = {3: 0.375, 4: 0.500, 5: 0.625, 6: 0.750, 7: 0.875, 8: 1.000, 9: 1.128, 10: 1.270, 11: 1.410}    # ASTM A615
BAR_AREA = {3: 0.11, 4: 0.20, 5: 0.31, 6: 0.44, 7: 0.60, 8: 0.79, 9: 1.00, 10: 1.27, 11: 1.56}
ES = 29_000_000.0                                   # ACI 318-19 20.2.2.2
MODES = ("footing", "soil", "spans")


class StemWallError(ValueError):
    pass


@dataclass
class Check:
    name: str
    demand: float
    capacity: float
    unit: str
    combo: str
    source: str
    note: str = ""

    @property
    def ok(self):
        return self.demand <= self.capacity + 1e-9


@dataclass
class Result:
    checks: list
    lines: list                                      # (text, value, unit, source, note) calculation lines
    values: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def beta1(fc):
    """ACI 318-19 Table 22.2.2.4.3."""
    return 0.85 if fc <= 4000 else max(0.85 - 0.05 * (fc - 4000) / 1000, 0.65)


def phi_flexure(eps_t, fy):
    """ACI 318-19 Table 21.2.2, transverse reinforcement 'other'."""
    ety = fy / ES
    if eps_t >= ety + 0.003:
        return 0.90, "tension controlled"
    if eps_t <= ety:
        return 0.65, "compression controlled"
    return 0.65 + 0.25 * (eps_t - ety) / 0.003, "transition"


def flexure(b, d, As, fc, fy):
    """Singly reinforced rectangular section (compression bars neglected): (phi Mn lb-in, a, c, eps_t, phi, class)."""
    a = As * fy / (0.85 * fc * b)                    # 22.2.2.4.1
    c = a / beta1(fc)
    eps_t = 0.003 * (d - c) / c                       # 22.2.1.2
    phi, cls = phi_flexure(eps_t, fy)
    return phi * As * fy * (d - a / 2), a, c, eps_t, phi, cls


def vc_without_stirrups(b, d, As, fc, lam=1.0):
    """Table 22.5.5.1(c) with 22.5.5.1.1 and 22.5.5.1.3, no axial force: (Vc lb, rho_w, lambda_s)."""
    rho = As / (b * d)
    lam_s = min(math.sqrt(2.0 / (1.0 + d / 10.0)), 1.0)
    v = 8 * lam_s * lam * rho ** (1 / 3) * math.sqrt(fc) * b * d
    return min(v, 5 * lam * math.sqrt(fc) * b * d), rho, lam_s


def min_depth_factor(fy):
    """9.3.1.1.1."""
    return 1.0 if abs(fy - 60000) < 1e-6 else 0.4 + fy / 100000.0


def cover_required(exposure, bar):
    """Table 20.5.1.3.1 for walls: 'earth' cast against and permanently in contact with ground; 'weather' exposed to weather or in
    contact with ground; 'interior' not exposed."""
    if exposure == "earth":
        return 3.0
    if exposure == "weather":
        return 2.0 if bar >= 6 else 1.5
    return 1.5 if bar >= 14 else 0.75


def _bar(n, what):
    if n not in BAR_DIA:
        raise StemWallError(f"stem wall: {what} bar size #{n} is not in the bar table (#3 to #11)")
    return BAR_DIA[n], BAR_AREA[n]


def check(mode, t, H, fc, fy, conc_pcf, cover, exposure, *, loads=(), strength=(), service=(),
          span_ft=None, spans=None, left=0.0, right=0.0, n_bot=0, bar_bot=None, n_top=0, bar_top=None,
          st_bar=None, st_legs=2, st_s=None, q_allow=None, plain=False, bar_v=None, s_v=None, v_at="center",
          bar_h=None, s_h=None, hb=0.0, efp=0.0, surcharge=0.0, braced=True, lateral_case="H", cast_against_soil=False,
          cover_bot=None, dagg=0.75):
    """t wall thickness (in); H wall height from its bottom to its top (in), also the grade beam depth.
    loads: dict(case, kind 'uniform'|'point', w plf (w2), P lb, x1_ft, x2_ft or x_ft) along the wall.
    strength: [(name, factors, source)] factored (LRFD) combinations; service: the same for the service (ASD) combinations.
    Grade beam ('spans'): span_ft or spans, overhangs left/right (ft), n_bot bars #bar_bot, n_top bars #bar_top, stirrups
    #st_bar with st_legs legs at st_s in. (none: st_s None). 'soil': q_allow psf. Wall bars: vertical #bar_v at s_v in. (at the
    center of the wall or near the tension face), horizontal #bar_h at s_h in.; plain=True for an unreinforced wall.
    Lateral: hb ft of unbalanced backfill at efp pcf plus a surcharge pressure psf, braced at the top (pinned top and base)."""
    if mode not in MODES:
        raise StemWallError("stem wall: the support is 'footing', 'soil' or 'spans'")
    for nm, v in (("wall thickness", t), ("wall height", H), ("f'c", fc), ("fy", fy), ("concrete unit weight", conc_pcf)):
        if v is None or v <= 0:
            raise StemWallError(f"stem wall: the {nm} must be a positive number")
    if cover is None or cover <= 0:
        raise StemWallError("stem wall: the clear cover must be a positive number")
    if not strength:
        raise StemWallError("stem wall: no factored (LRFD) load combinations")
    sq = math.sqrt(fc)
    checks, lines, notes, val = [], [], [], {}
    w_self = conc_pcf * t * H / 144.0                                    # plf
    lines.append(("wall self-weight", w_self, "plf", "", f"{conc_pcf:g} pcf x {t:g} in. x {H:g} in., case D"))
    all_loads = [dict(case="D", kind="uniform", w=w_self, label="wall self-weight")] + [dict(x) for x in loads]

    # ---------------- wall reinforcement (Table 11.6.1, 11.7.2.1) and cover (Table 20.5.1.3.1)
    if not plain:
        if None in (bar_v, s_v, bar_h, s_h):
            raise StemWallError("stem wall: give the vertical and horizontal wall bars and their spacing, or call the wall plain")
        dv, Av_ = _bar(bar_v, "vertical"); dh, Ah_ = _bar(bar_h, "horizontal")
        small = fy >= 60000
        rl_min = 0.0012 if (bar_v <= 5 and small) else 0.0015
        rt_min = 0.0020 if (bar_h <= 5 and small) else 0.0025
        rl, rt = Av_ / (t * s_v), Ah_ / (t * s_h)
        checks.append(Check("minimum vertical wall reinforcement", rl_min * t * 12, Av_ * 12 / s_v, "in2/ft", "-", "ACI 318-19 Table 11.6.1",
                            f"rho_l,min = {rl_min:g}; #{bar_v} at {s_v:g} in. gives rho_l = {rl:.5f}; demand is the minimum area"))
        checks.append(Check("minimum horizontal wall reinforcement", rt_min * t * 12, Ah_ * 12 / s_h, "in2/ft", "-", "ACI 318-19 Table 11.6.1",
                            f"rho_t,min = {rt_min:g}; #{bar_h} at {s_h:g} in. gives rho_t = {rt:.5f}"))
        smax = min(3 * t, 18.0)
        checks.append(Check("spacing of wall bars", max(s_v, s_h), smax, "in", "-", "ACI 318-19 11.7.2.1",
                            f"lesser of 3h = {3 * t:g} in. and 18 in."))
        bars = [b_ for b_ in (bar_v, bar_h, bar_bot if mode == "spans" else None, bar_top if mode == "spans" else None) if b_]
        creq = max(cover_required(exposure, b_) for b_ in bars)
        checks.append(Check("concrete cover, sides and top", creq, cover, "in", "-", "ACI 318-19 Table 20.5.1.3.1",
                            {"earth": "cast against and permanently in contact with ground",
                             "weather": "exposed to weather or in contact with ground",
                             "interior": "not exposed to weather or in contact with ground"}[exposure]
                            + "; demand is the required cover, capacity the cover provided"))
    if mode in ("soil", "spans") and not plain:
        cb_ = cover_bot if cover_bot is not None else cover
        checks.append(Check("concrete cover, bottom", 3.0, cb_, "in", "-", "ACI 318-19 Table 20.5.1.3.1",
                            "cast against and permanently in contact with ground" + (" (on the void form, in contact with the ground once it is gone)"
                                                                                       if mode == "spans" else "")))
    elif mode == "spans":
        raise StemWallError("stem wall: a wall spanning between footings or piers must be reinforced (a plain wall cannot be a grade beam)")

    # ---------------- out of plane: unbalanced backfill on a wall braced at its top
    if hb and hb > 0:
        if efp is None or efp <= 0:
            raise StemWallError("stem wall: give the equivalent fluid pressure of the backfill")
        if hb * 12 > H + 1e-6:
            raise StemWallError("stem wall: the unbalanced backfill is higher than the wall")
        if not braced:
            raise StemWallError("stem wall: a wall not braced at its top is a cantilever retaining wall (sliding, overturning and the "
                                "footing heel and toe), not built yet; brace the wall at its top or check it as a retaining wall")
        Hs = H                                                           # span from the base to the brace at the top
        hbi = hb * 12.0
        # pressure at the base efp*hb (psf) falling to zero at the top of the fill; surcharge uniform over the fill height (lb/in per ft)
        dist = [bm.DistLoad(0.0, min(hbi, Hs), efp * hb / 12.0, efp * (hb - min(hbi, Hs) / 12.0) / 12.0)]
        if surcharge:
            dist.append(bm.DistLoad(0.0, min(hbi, Hs), surcharge / 12.0, surcharge / 12.0))
        r = bm.solve(Hs, [0.0, Hs], 1.0e9, [], dist)
        M1, V1 = float(abs(r.M).max()), float(abs(r.V).max())            # lb-in and lb per ft of wall, service lateral load
        fac = [(nm, f.get(lateral_case, 0.0), src) for nm, f, src in strength if f.get(lateral_case, 0.0)]
        if not fac:
            raise StemWallError(f"stem wall: no factored combination includes the lateral earth pressure case {lateral_case}")
        nm, fH, src = max(fac, key=lambda x: x[1])
        Mu, Vu = fH * M1, fH * V1
        lines.append(("lateral earth pressure at the base", efp * hb + (surcharge or 0.0), "psf", "soils source",
                      f"{efp:g} pcf x {hb:g} ft" + (f" + surcharge {surcharge:g} psf" if surcharge else "")))
        lines.append(("out-of-plane moment, per ft of wall", fH * M1 / 12.0, "lb-ft", "statics, pinned at the base and at the brace",
                      f"span {Hs / 12:g} ft; {nm}: {fH:g} x {M1 / 12:.0f} lb-ft"))
        if plain:
            h_e = t - (2.0 if cast_against_soil else 0.0)                 # 14.5.1.7
            Sm = 12.0 * h_e ** 2 / 6.0
            phiMn = 0.60 * 5 * sq * Sm
            phiVn = 0.60 * 4.0 / 3.0 * sq * 12.0 * h_e
            checks.append(Check("out-of-plane flexure, plain wall", Mu / 12.0, phiMn / 12.0, "lb-ft/ft", nm,
                                "ACI 318-19 Eq. (14.5.2.1a), 14.5.1.7; phi = 0.60 (Table 21.2.1)",
                                f"h = {h_e:g} in." + (" (2 in. less, cast against soil)" if cast_against_soil else "") + f"; Sm = {Sm:.1f} in3/ft"))
            checks.append(Check("out-of-plane shear, plain wall", Vu, phiVn, "lb/ft", nm, "ACI 318-19 Table 14.5.5.1(a); phi = 0.60", ""))
        else:
            dv_ = (t / 2.0) if v_at == "center" else (t - cover - dv / 2.0)
            As = Av_ * 12.0 / s_v
            phiMn, a, c, et, ph, cls = flexure(12.0, dv_, As, fc, fy)
            checks.append(Check("out-of-plane flexure", Mu / 12.0, phiMn / 12.0, "lb-ft/ft", nm,
                                "ACI 318-19 22.2.2.4.1; phi by Table 21.2.2",
                                f"#{bar_v} at {s_v:g} in. ({As:.3f} in2/ft) at d = {dv_:.2f} in.; a = {a:.3f} in.; eps_t = {et:.4f}, {cls}, phi = {ph:.3f}"))
            Vc, rho, ls = vc_without_stirrups(12.0, dv_, As, fc)
            checks.append(Check("out-of-plane shear", Vu, 0.75 * Vc, "lb/ft", nm, "ACI 318-19 Table 22.5.5.1(c), 22.5.5.1.3; phi = 0.75",
                                f"rho_w = {rho:.5f}; lambda_s = {ls:.3f}"))
        val.update(M_lat=M1, V_lat=V1)

    # ---------------- along the wall
    if mode == "soil":
        if q_allow is None or q_allow <= 0:
            raise StemWallError("stem wall: give the allowable soil bearing pressure")
        if any(ld["kind"] == "point" for ld in loads):
            raise StemWallError("stem wall: a point load on a wall bearing directly on soil is not covered (the spread of a point load "
                                "through the wall into the soil is not built); carry it on a pad footing or check the wall spanning between supports")
        if not service:
            raise StemWallError("stem wall: no service (ASD) load combinations for the soil bearing")
        worst = None
        cuts = sorted({0.0} | {ld.get("x1_ft", 0.0) for ld in all_loads} | {ld.get("x2_ft", 1e9) for ld in all_loads})
        for nm, f, src in service:
            for xa, xb in zip(cuts[:-1], cuts[1:]):
                xm = (xa + xb) / 2 if xb < 1e8 else xa + 0.01
                w = 0.0
                for ld in all_loads:
                    a_, b_ = ld.get("x1_ft", 0.0), ld.get("x2_ft", 1e9)
                    if a_ <= xm <= b_:
                        w2 = ld.get("w2", ld["w"])
                        w += f.get(ld["case"], 0.0) * (ld["w"] + (w2 - ld["w"]) * ((xm - a_) / (b_ - a_) if b_ < 1e8 else 0.0))
                if worst is None or w > worst[0]:
                    worst = (w, nm)
        q = worst[0] / (t / 12.0)
        checks.append(Check("soil bearing under the wall", q, q_allow, "psf", worst[1], "allowable from the soils source",
                            f"line load {worst[0]:,.0f} plf with the wall's weight over the {t:g} in. wall bottom"))
        val["w_base"] = worst
    elif mode == "footing":
        out = []
        for nm, f, src in list(service) + list(strength):
            w = sum(f.get(ld["case"], 0.0) * max(ld.get("w", 0.0), ld.get("w2", ld.get("w", 0.0))) for ld in all_loads if ld["kind"] == "uniform")
            out.append((nm, w))
        val["w_base"] = out
        notes.append("The line loads at the base of the wall, with its weight, are carried to the continuous footing (its own sheet).")
    else:
        val.update(_grade_beam(checks, lines, notes, all_loads, strength, t, H, fc, fy, cover, (cover_bot if cover_bot is not None else cover), dagg,
                               span_ft, spans, left, right,
                               n_bot, bar_bot, n_top, bar_top, st_bar, st_legs, st_s, braced, service))
    return Result(checks, lines, val, notes)


def _grade_beam(checks, lines, notes, loads, strength, b, h, fc, fy, cover, cover_b, dagg, span_ft, spans, left, right,
                n_bot, bar_bot, n_top, bar_top, st_bar, st_legs, st_s, braced, service):
    sq = math.sqrt(fc)
    try:
        lay = contbeam.layout(span_ft, spans, left, right)
    except (ValueError, TypeError) as e:
        raise StemWallError(f"stem wall: {e}")
    if not n_bot or not bar_bot or not n_top or not bar_top:
        raise StemWallError("stem wall: give the bottom and top bars of the wall spanning between supports")
    db_b, Ab_b = _bar(bar_bot, "bottom"); db_t, Ab_t = _bar(bar_top, "top")
    ds_ = BAR_DIA[st_bar] if (st_bar and st_s) else 0.0
    d_b = h - cover_b - ds_ - db_b / 2
    d_t = h - cover - ds_ - db_t / 2
    As_b, As_t = n_bot * Ab_b, n_top * Ab_t
    Ec = 57000 * sq                                                         # 19.2.2.1(b); stiffness only distributes moment
    EI = Ec * b * h ** 3 / 12.0
    by_case = {}
    for ld in loads:
        d = dict(kind=ld["kind"])
        if ld["kind"] == "uniform":
            d.update(w=ld["w"], **({"w2": ld["w2"]} if ld.get("w2") is not None else {}))
            if "x1_ft" in ld:
                d["x1_ft"] = ld["x1_ft"]
            if "x2_ft" in ld:
                d["x2_ft"] = ld["x2_ft"]
        else:
            d.update(P=ld["P"], x_ft=ld["x_ft"])
        by_case.setdefault(ld["case"], []).append(d)
    basis = contbeam.basis_for(lay, EI, by_case)
    envs = []
    for nm, f, src in strength:
        e = contbeam.envelope(lay, EI, by_case, f, True, basis)
        if e is not None:
            envs.append((nm, e))
    if not envs:
        raise StemWallError("stem wall: no factored combination puts load on the wall")
    mp = max(envs, key=lambda x: x[1].Mpos); mn = max(envs, key=lambda x: x[1].Mneg); vv = max(envs, key=lambda x: x[1].V)
    Mpos, Mneg, Vu = mp[1].Mpos, mn[1].Mneg, vv[1].V
    lines.append(("grade beam", lay.describe(), "", "", f"{b:g} x {h:g} in.; supports are the footings or piers, no soil support between them"))
    lines.append(("largest factored moments", f"+{Mpos / 12:,.0f} / -{Mneg / 12:,.0f}", "lb-ft", "statics (continuous beam)",
                  f"{mp[0]} / {mn[0]}; live load on every arrangement of whole spans (ASCE/SEI 7-22 4.3.3)"))
    lines.append(("largest factored shear", Vu, "lb", "statics", f"{vv[0]}, at the support centerline"))
    # flexure
    for nm_, M, As, d, n_, bar, face in (("positive", Mpos, As_b, d_b, n_bot, bar_bot, "bottom"), ("negative", Mneg, As_t, d_t, n_top, bar_top, "top")):
        if M <= 1e-6 * max(Mpos, Mneg, 1.0):
            continue
        phiMn, a, c, et, ph, cls = flexure(b, d, As, fc, fy)
        checks.append(Check(f"flexure, {nm_} moment ({face} bars)", M / 12.0, phiMn / 12.0, "lb-ft", mp[0] if nm_ == "positive" else mn[0],
                            "ACI 318-19 22.2.2.4.1; phi by Table 21.2.2",
                            f"({n_}) #{bar} = {As:.2f} in2 at d = {d:.2f} in.; a = {a:.2f} in.; eps_t = {et:.4f}, {cls}, phi = {ph:.3f}"))
        fyl = min(fy, 80000)
        Amin = max(3 * sq / fyl, 200.0 / fyl) * b * d
        Mreq = M / 0.90                                                       # As required by analysis, tension controlled
        k_ = fy / (1.7 * fc * b)
        disc = d * d - 4 * k_ * Mreq / fy
        Areq = (d - math.sqrt(disc)) / (2 * k_) if disc > 0 else float("inf")
        if 4.0 / 3.0 * Areq < Amin:
            checks.append(Check(f"minimum flexural reinforcement, {face}", 4.0 / 3.0 * Areq, As, "in2", "-", "ACI 318-19 9.6.1.3",
                                f"As by analysis {Areq:.3f} in2; one-third more than that ({4 / 3 * Areq:.3f}) is less than 9.6.1.2 ({Amin:.3f}); demand is 4/3 As by analysis"))
        else:
            checks.append(Check(f"minimum flexural reinforcement, {face}", Amin, As, "in2", "-", "ACI 318-19 9.6.1.2",
                                "larger of 3 sqrt(f'c) bw d / fy and 200 bw d / fy; demand is the minimum area"))
        if n_ >= 2:                                                          # Table 24.3.2
            fs = 2.0 / 3.0 * fy
            cc = (cover_b if face == "bottom" else cover) + ds_
            s_ = (b - 2 * (cover + ds_) - BAR_DIA[bar]) / (n_ - 1)
            smin = max(1.0, BAR_DIA[bar], 4.0 / 3.0 * dagg)
            checks.append(Check(f"clear spacing of {face} bars", smin, s_ - BAR_DIA[bar], "in", "-", "ACI 318-19 25.2.1",
                                f"({n_}) #{bar} across {b:g} in. with {cover:g} in. side cover" + (" and stirrups" if ds_ else "")
                                + f"; at least the greatest of 1 in., db and 4/3 x {dagg:g} in. aggregate; demand is the minimum"))
            smax = min(15 * 40000 / fs - 2.5 * cc, 12 * 40000 / fs)
            checks.append(Check(f"spacing of {face} bars (crack control)", s_, smax, "in", "-", "ACI 318-19 Table 24.3.2, 24.3.2.1",
                                f"fs = 2/3 fy = {fs:,.0f} psi; cc = {cc:g} in."))
    # shear
    d = min(d_b, d_t)
    As_tens = min(As_b, As_t)
    has_st = bool(st_bar and st_s)
    if has_st:
        Av = st_legs * BAR_AREA[st_bar]
        Vc = 2 * sq * b * d                                                   # Table 22.5.5.1(a)
        Vs = Av * fy * d / st_s                                               # 22.5.8.5.3, fyt = fy
        Avmin = max(0.75 * sq * b * st_s / fy, 50 * b * st_s / fy)            # Table 9.6.3.4
        checks.append(Check("shear", Vu, 0.75 * (Vc + Vs), "lb", vv[0], "ACI 318-19 Table 22.5.5.1(a), 22.5.8.5.3; phi = 0.75",
                            f"Vc = 2 sqrt(f'c) bw d = {Vc:,.0f} lb; Vs = {st_legs} x {BAR_AREA[st_bar]:.2f} x {fy:,.0f} x {d:.2f} / {st_s:g} = {Vs:,.0f} lb"))
        checks.append(Check("stirrup area, Av,min", Avmin, Av, "in2", "-", "ACI 318-19 Table 9.6.3.4", f"at s = {st_s:g} in."))
        smax = min(d / 2, 24.0) if Vs <= 4 * sq * b * d else min(d / 4, 12.0)
        checks.append(Check("stirrup spacing", st_s, smax, "in", "-", "ACI 318-19 Table 9.7.6.2.2", ""))
        checks.append(Check("section size for shear", Vu, 0.75 * (Vc + 8 * sq * b * d), "lb", vv[0], "ACI 318-19 Eq. (22.5.1.2)", ""))
    else:
        Vc, rho, ls = vc_without_stirrups(b, d, As_tens, fc)
        checks.append(Check("shear, no stirrups", Vu, 0.75 * Vc, "lb", vv[0], "ACI 318-19 Table 22.5.5.1(c), 22.5.5.1.3; phi = 0.75",
                            f"rho_w = {rho:.5f} (the smaller of the top and bottom bars); lambda_s = {ls:.3f}"))
        if h > 10:                                                            # 9.6.3.1: Av,min where Vu > phi lambda sqrt(f'c) bw d
            checks.append(Check("shear without minimum stirrups", Vu, 0.75 * sq * b * d, "lb", vv[0], "ACI 318-19 9.6.3.1, Table 9.6.3.1",
                                "Av,min is required where Vu exceeds phi lambda sqrt(f'c) bw d (h over 10 in.)"))
    # depth for deflection, skin reinforcement, lateral bracing
    hmin, why = 0.0, ""
    for x0, x1, label, _ in lay.segments:
        L = (x1 - x0) * 12.0
        if "overhang" in label:
            r_ = L / 8.0; w_ = "cantilever, l/8"
        elif len(lay.spans) == 1 and not lay.left and not lay.right:
            r_ = L / 16.0; w_ = "simply supported, l/16"
        else:
            i = lay.segments.index((x0, x1, label, _))
            ends = (i > 0, i < len(lay.segments) - 1)
            r_ = L / (21.0 if all(ends) else 18.5); w_ = "both ends continuous, l/21" if all(ends) else "one end continuous, l/18.5"
        r_ *= min_depth_factor(fy)
        if r_ > hmin:
            hmin, why = r_, f"{label}: {w_}"
    checks.append(Check("depth for deflections not calculated", hmin, h, "in", "-", "ACI 318-19 Table 9.3.1.1, 9.3.1.1.1",
                        why + "; deflections are not calculated on this sheet"))
    if h > 36:
        notes.append("h exceeds 36 in.: skin reinforcement along both side faces is required (ACI 318-19 9.7.2.3) and is not checked here.")
    if braced:
        notes.append("The top of the wall is braced along its length by the floor or slab, and the bottom at each support (ACI 318-19 9.2.3.1).")
    else:
        Lb = max(lay.spans + [lay.left, lay.right]) * 12.0
        checks.append(Check("spacing of lateral bracing", Lb, 50 * b, "in", "-", "ACI 318-19 9.2.3.1(a)",
                            "50 times the wall thickness; braced at the supports only"))
    react = {}
    for kind_, cbs in (("factored", strength), ("service", service)):
        for nm, f, src in cbs:
            e = contbeam.envelope(lay, EI, by_case, f, True, basis)
            if e is not None:
                sup = [s * 12.0 for s in lay.supports]
                react[(kind_, nm)] = [e.reactions[min(e.reactions, key=lambda k: abs(k - x))] for x in sup] + [max(e.R_end, e.R_int)]
    gov = mp[1] if mp[1].Mpos >= mn[1].Mneg else mn[1]
    r = gov.res_pos if gov is mp[1] else gov.res_neg
    return dict(layout=lay, reactions=react, d_bot=d_b, d_top=d_t, Mpos=Mpos, Mneg=Mneg, Vu=Vu,
                diagram=dict(combo=(mp[0] if gov is mp[1] else mn[0]), x=[v / 12.0 for v in r.x.tolist()], V=r.V.tolist(),
                             M=[v / 12.0 for v in r.M.tolist()]))
