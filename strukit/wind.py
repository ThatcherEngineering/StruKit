"""Wind velocity pressure, ASCE/SEI 7-22 Chapter 26.

Read from the standard (page images; numbers confirmed against the image):
  Eq. 26.10-1    qz = 0.00256 Kz Kzt Ke V^2 (psf; V in mi/h). qh is qz at the mean roof
                 height h. (In ASCE/SEI 7-22 the directionality factor Kd is applied with
                 the pressure coefficients, not in the velocity pressure.)
  Table 26.10-1  Kz and Kh for Exposures B, C and D, 0 to 500 ft; note 3: linear
                 interpolation between heights is acceptable. The 0.70 value for Exposure B
                 below 30 ft is for Chapter 28 only (the envelope procedure).
  Sect. 26.9, Table 26.9-1  Ke = e^(-0.0000362 ze), ze = ground elevation above sea level,
                 ft; Ke = 1.0 is permitted in all cases.
  Sect. 26.8     Kzt is entered by the engineer (1.0 where 26.8.1 does not apply).

Main wind force resisting system, directional procedure (Chapter 27), enclosed, partially
enclosed and partially open rigid buildings with a gable, monoslope or flat roof:
  Eq. 27.3-1     p = q Kd G Cp - qi Kd (GCpi); q = qz on the windward wall, qh on the leeward
                 wall, side walls and roof; qi = qh (permitted in all cases: qh is not less
                 than qz at an opening).
  Table 26.6-1   Kd = 0.85, buildings, main wind force resisting system.
  Sect. 26.11.1  G = 0.85 for a rigid building.
  Table 26.13-1  GCpi; both signs are considered.
  Figure 27.3-1  Cp for walls and roofs; interpolation between values of the same sign, with
                 0.0 taken where the figure gives no value of that sign (notes 2 and 3). The
                 area reduction of the -1.3 value (note b) is not taken.
  Sect. 27.1.5   minimum: 16 psf on the wall area and 8 psf on the roof area projected on a
                 vertical plane normal to the wind, as a separate case.
  Figure 27.3-1, note 6: the total horizontal force is not less than that with the roof
                 forces neglected.

Components and cladding, buildings with h of 60 ft or less (Chapter 30, Part 1), walls:
  Eq. 30.3-1     p = qh Kd [(GCp) - (GCpi)]
  Figure 30.3-1  (GCp) for walls (pdf p. 378, read from the page image): positive, zones 4 and
                 5: +1.0 at 10 ft2 or less to +0.7 at 500 ft2 or more; negative, zone 4: -1.1 to
                 -0.8; zone 5: -1.4 to -0.8; straight lines on the logarithm of the effective
                 wind area between 10 and 500 ft2. Note 5: reduced 10 percent where theta is 10
                 degrees or less. a = the smaller of 10 percent of the least horizontal
                 dimension and 0.4h, not less than 4 percent of that dimension or 3 ft; where
                 theta is 0 to 7 degrees and the least dimension is over 300 ft, not over 0.8h.
  Sect. 30.2.2   net pressure not less than 16 psf in either direction.
  Figure 30.3-2A (GCp) for flat roofs and gable roofs at 7 degrees or less (pdf p. 380, read
                 from the page image): positive, all zones: +0.3 at 10 ft2 or less to +0.2 at
                 100 ft2 or more; negative: zone 1' -0.9 to 100 ft2, then to -0.4 at 1,000 ft2;
                 zone 1 -1.7 at 10 to -1.0 at 500; zone 2 -2.3 to -1.4 at 500; zone 3 -3.2 to
                 -1.4 at 500. Zone 2: within 0.6h of a roof edge; zone 3: at each corner, 0.6h
                 along one edge by 0.2h deep, both ways; zone 1: from 0.6h to 1.2h from an
                 edge; zone 1': the rest. h is the eave height.
  Figures 30.3-2B, 2C, 2D  (GCp) for gable roofs over 7 to 20, over 20 to 27 and over 27 to 45
                 degrees (pdf pp. 381-383, charts read from 330 dpi page images; break points
                 checked by measuring the log scale). Values in ROOF_GCP below. Zones for 2B and
                 2C: zone 2 within a of a gable end and within a of the ridge on each side;
                 zone 3 where those meet at each end of the ridge; zone 1 the rest. For 2D:
                 zone 2 within a of a gable end; zone 3 at each eave corner, a by a; zone 1 the
                 rest. a as for walls; h is the mean roof height (the eave height at 10 degrees
                 or less).
  Figures 30.3-5A, 5B  (GCp) for monoslope roofs over 3 to 10 and over 10 to 30 degrees (pdf
                 pp. 389-390, read from 330 dpi page images; every line runs from 10 to 100 ft2).
                 5A: zones 2' and 3' along the high eave in a strip 2a wide (3' for 4a from each
                 end) and 2' along each sloping edge 2a wide; zone 3 at each low eave corner,
                 2a by 2a; zone 2 along the low eave, a wide; zone 1 the rest. 5B: zones 2 and 3
                 along the high eave in a strip 2a wide (3 for 4a from each end); zone 2 along
                 the other three edges, a wide; zone 1 the rest. At 3 degrees or less Figure
                 30.3-2A applies.
  Sect. 30.7     roof overhangs (pdf p. 396): p = qh Kd [(GCp) - (GCpi)], Eq. 30.7-1, with (GCp)
                 the sum of the top surface (the roof zone's value) and the bottom surface (the
                 adjacent wall's value for the same effective wind area). Built for uplift:
                 the roof's negative value less the wall's positive value. For roofs in the
                 range of Figure 30.3-2A its overhang chart is used (OVERHANG_GCP_7 below).
Not covered: roof components and cladding on hip and other roof shapes, on gable roofs over 45
degrees and monoslope roofs over 30 degrees, the parapet provision of Figure 30.3-2A note 5, roof overhangs
(Sect. 30.7); Parts 2 to 5 of Chapter 30;
hip, mansard and arched roofs; open buildings; flexible buildings;
parapets and roof overhangs; the torsional cases of Figure 27.3-8; Chapters 28 and 30.
"""
import math

HEIGHTS = (15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 250, 300, 350, 400, 450, 500)
KZ = {"B": (0.57, 0.62, 0.66, 0.70, 0.74, 0.79, 0.83, 0.86, 0.90, 0.92, 0.95, 1.00, 1.04, 1.08, 1.11, 1.14, 1.21, 1.27, 1.33, 1.38, 1.42, 1.46),
      "C": (0.85, 0.90, 0.94, 0.98, 1.04, 1.09, 1.13, 1.17, 1.21, 1.24, 1.26, 1.31, 1.34, 1.39, 1.41, 1.44, 1.51, 1.57, 1.62, 1.66, 1.70, 1.74),
      "D": (1.03, 1.08, 1.12, 1.16, 1.22, 1.27, 1.31, 1.34, 1.38, 1.40, 1.43, 1.48, 1.52, 1.55, 1.58, 1.61, 1.68, 1.73, 1.78, 1.82, 1.86, 1.89)}


class WindError(ValueError):
    pass


def kz(exposure, z, chapter_28=False):
    if exposure not in KZ:
        raise WindError("wind: the exposure category must be B, C or D")
    if z is None or z < 0 or z > 500:
        raise WindError("wind: the height must be between 0 and 500 ft")
    t = KZ[exposure]
    if z <= 15:
        v = t[0]
    else:
        i = next(k for k in range(1, len(HEIGHTS)) if z <= HEIGHTS[k])
        v = t[i - 1] + (t[i] - t[i - 1]) * (z - HEIGHTS[i - 1]) / (HEIGHTS[i] - HEIGHTS[i - 1])
    if chapter_28 and exposure == "B" and z < 30:
        v = 0.70
    return v


def ke(elevation_ft):
    return math.exp(-0.0000362 * elevation_ft)


def velocity_pressure(V, exposure, z, Kzt=1.0, Ke=1.0, chapter_28=False):
    if V is None or V <= 0:
        raise WindError("wind: the basic wind speed must be a positive number")
    if Kzt is None or Kzt < 1.0:
        raise WindError("wind: Kzt is 1.0 or more")
    k = kz(exposure, z, chapter_28)
    return 0.00256 * k * Kzt * Ke * V ** 2, k


# ---- Main wind force resisting system, directional procedure: data read so far -----------
# ASCE/SEI 7-22 Figure 27.3-1 (pdf pp. 344-345) and Table 26.13-1 (pdf p. 341), read from
# the page images.
KD_MWFRS = 0.85                                          # Table 26.6-1, buildings, main wind force resisting system
G_RIGID = 0.85                                           # Sect. 26.11.1
MIN_WALL, MIN_ROOF = 16.0, 8.0                           # Sect. 27.1.5, psf
GCPI = {"enclosed": 0.18, "partially enclosed": 0.55, "partially open": 0.18, "open": 0.0}      # Table 26.13-1, plus and minus
WALL_CP_WINDWARD = 0.8                                   # with qz
WALL_CP_SIDE = -0.7                                      # with qh
WALL_CP_LEEWARD = ((1.0, -0.5), (2.0, -0.3), (4.0, -0.2))   # L/B -> Cp, with qh; L/B 0 to 1: -0.5; 4 and over: -0.2
# Roof, wind normal to the ridge, theta 10 degrees and over. Windward: h/L -> {theta: (negative Cp, positive Cp)};
# None where the figure gives no value of that sign. An "a" value (0.0, for interpolation) is entered as 0.0.
ROOF_WINDWARD = {
    0.25: {10: (-0.7, -0.18), 15: (-0.5, 0.0), 20: (-0.3, 0.2), 25: (-0.2, 0.3), 30: (-0.2, 0.3), 35: (0.0, 0.4), 45: (None, 0.4), 60: (None, 0.6)},
    0.5: {10: (-0.9, -0.18), 15: (-0.7, -0.18), 20: (-0.4, 0.0), 25: (-0.3, 0.2), 30: (-0.2, 0.2), 35: (-0.2, 0.3), 45: (0.0, 0.4), 60: (None, 0.6)},
    1.0: {10: (-1.3, -0.18), 15: (-1.0, -0.18), 20: (-0.7, -0.18), 25: (-0.5, 0.0), 30: (-0.3, 0.2), 35: (-0.2, 0.2), 45: (0.0, 0.3), 60: (None, 0.6)},
}
# over 60 to 80 degrees: 0.01 theta; over 80: 0.8. Leeward: h/L -> {theta: Cp} (20 means 20 and over)
ROOF_LEEWARD = {0.25: {10: -0.3, 15: -0.5, 20: -0.6}, 0.5: {10: -0.5, 15: -0.5, 20: -0.6}, 1.0: {10: -0.7, 15: -0.6, 20: -0.6}}
# Roof, wind normal to the ridge with theta under 10 degrees, and wind parallel to the ridge for all theta:
# h/L -> [(distance from the windward edge as a multiple of h, Cp)], each also with -0.18
ROOF_PARALLEL = {0.5: (("0 to h/2", -0.9), ("h/2 to h", -0.9), ("h to 2h", -0.5), ("over 2h", -0.3)),
                 1.0: (("0 to h/2", -1.3), ("over h/2", -0.7))}
ROOF_PARALLEL_OTHER = -0.18
# Monoslope roofs (Figure 27.3-1 diagrams, pdf p. 344, read from the page image): wind normal to
# the ridge blowing toward the low eave wall puts the windward roof Cp on the whole roof; blowing toward the high
# eave wall puts the leeward roof Cp on the whole roof. Wind parallel to the ridge: the same zones as a gable roof.
# note b: the -1.3 value may be reduced with the area it applies to: 100 ft2 or less 1.0; 250 ft2 0.9; 1,000 ft2 or more 0.8


def wall_cp_leeward(L_over_B):
    """Figure 27.3-1, leeward wall, linear interpolation between L/B values (note 2)."""
    if L_over_B is None or L_over_B <= 0:
        raise WindError("wind: L/B must be positive")
    pts = WALL_CP_LEEWARD
    if L_over_B <= pts[0][0]:
        return pts[0][1]
    if L_over_B >= pts[-1][0]:
        return pts[-1][1]
    for (a, ca), (b, cb) in zip(pts[:-1], pts[1:]):
        if L_over_B <= b:
            return ca + (cb - ca) * (L_over_B - a) / (b - a)


def _lin(x, pts):
    """pts: sorted (x, y or None). None at either end of the interval gives None."""
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (a, ya), (b, yb) in zip(pts[:-1], pts[1:]):
        if x <= b:
            if x == a:
                return ya
            if x == b:
                return yb
            if ya is None or yb is None:
                return None
            return ya + (yb - ya) * (x - a) / (b - a)


def _across(hl, by_ratio):
    """Interpolate between the h/L rows; where one row has no value of that sign, 0.0 is used (note 3)."""
    keys = sorted(by_ratio)
    if hl <= keys[0]:
        return by_ratio[keys[0]]
    if hl >= keys[-1]:
        return by_ratio[keys[-1]]
    for a, b in zip(keys[:-1], keys[1:]):
        if hl <= b:
            ya, yb = by_ratio[a], by_ratio[b]
            if ya is None and yb is None:
                return None
            ya, yb = ya or 0.0, yb or 0.0
            return ya + (yb - ya) * (hl - a) / (b - a)


def roof_cp_windward(theta, h_over_L):
    """Figure 27.3-1, windward roof, wind normal to the ridge, theta 10 degrees and over.
    Returns (first value, second value); None where the figure gives none."""
    if theta < 10:
        raise WindError("wind: under 10 degrees the roof is taken by distance from the windward edge")
    if theta > 60:
        return None, (0.8 if theta > 80 else 0.01 * theta)
    out = []
    for i in (0, 1):
        rows = {r: _lin(theta, [(t, v[i]) for t, v in sorted(ROOF_WINDWARD[r].items())]) for r in ROOF_WINDWARD}
        out.append(_across(h_over_L, rows))
    return tuple(out)


def roof_cp_leeward(theta, h_over_L):
    return _across(h_over_L, {r: _lin(theta, sorted(ROOF_LEEWARD[r].items())) for r in ROOF_LEEWARD})


def roof_cp_parallel(h_over_L):
    """Figure 27.3-1, wind parallel to the ridge (all theta) or normal to it with theta under
    10 degrees: [(zone, from as a multiple of h, to (None = the leeward edge), Cp)], each zone
    also with -0.18."""
    lo = {(0.0, 0.5): -0.9, (0.5, 1.0): -0.9, (1.0, 2.0): -0.5, (2.0, None): -0.3}
    hi = {(0.0, 0.5): -1.3, (0.5, 1.0): -0.7, (1.0, 2.0): -0.7, (2.0, None): -0.7}
    names = {(0.0, 0.5): "0 to h/2", (0.5, 1.0): "h/2 to h", (1.0, 2.0): "h to 2h", (2.0, None): "over 2h"}
    return [(names[k], k[0], k[1], _across(h_over_L, {0.5: lo[k], 1.0: hi[k]})) for k in lo]


class Surface:
    def __init__(self, name, q, q_name, Cp, qi, GCpi, zone=None):
        self.name, self.q, self.q_name, self.Cp, self.zone = name, q, q_name, Cp, zone
        self.external = q * KD_MWFRS * G_RIGID * Cp
        self.internal = qi * KD_MWFRS * GCpi
        self.p_pos_internal = self.external - self.internal      # with +GCpi
        self.p_neg_internal = self.external + self.internal      # with -GCpi


def mwfrs(V, exposure, h, eave, B, L, enclosure, direction, theta=0.0, Kzt=1.0, Ke=1.0, roof="gable"):
    """Design pressures (psf, strength level, positive toward the surface) on the main wind
    force resisting system of a rigid building with a gable, monoslope or flat roof, for one
    wind direction, and the total horizontal force in that direction.
    B: plan dimension normal to the wind; L: parallel to the wind; h: mean roof height (the
    eave height where theta is 10 degrees or less); eave: eave height (the low eave of a
    monoslope roof). direction: "normal" or "parallel" to the ridge; for a monoslope roof
    "normal_low" (wind blowing toward the low eave wall), "normal_high" or "parallel"."""
    if enclosure not in GCPI or enclosure == "open":
        raise WindError("wind: the enclosure is enclosed, partially enclosed or partially open (open buildings are not covered)")
    if roof not in ("gable", "monoslope"):
        raise WindError("wind: the roof is gable (or flat) or monoslope")
    ok = ("normal", "parallel") if roof == "gable" else ("normal_low", "normal_high", "parallel")
    if direction not in ok:
        raise WindError("wind: the wind direction is " + ", ".join(ok))
    for nm, v in (("the mean roof height", h), ("the eave height", eave), ("B", B), ("L", L)):
        if v is None or v <= 0:
            raise WindError(f"wind: {nm} must be positive")
    if theta is None or theta < 0 or theta >= 90:
        raise WindError("wind: the roof angle is from 0 to under 90 degrees")
    if eave > h + 1e-9 and theta > 10:
        raise WindError("wind: the eave height is above the mean roof height")
    normal = direction != "parallel"
    across = L if normal else B
    rise = math.tan(math.radians(theta)) * (across / 2 if roof == "gable" else across)
    gc = GCPI[enclosure]
    qh, kh = velocity_pressure(V, exposure, h, Kzt, Ke)
    hl, lb = h / L, L / B
    # wall heights: windward, leeward; a wall under the roof slope (wind parallel to the ridge) runs from the eave up by the rise
    if normal:
        top_w = eave + (rise if direction == "normal_high" else 0.0)
        top_l = eave + (rise if direction == "normal_low" else 0.0)
        taper = 0.0
    else:
        top_w = top_l = eave + rise
        taper = rise
    zs = [z for z in HEIGHTS if z < top_w - 1e-9] + [top_w]
    windward = []
    for z in zs:
        qz, k = velocity_pressure(V, exposure, z, Kzt, Ke)
        s = Surface(f"windward wall at {round(z, 1):g} ft", qz, "qz", WALL_CP_WINDWARD, qh, gc)
        s.z, s.Kz = z, k
        windward.append(s)
    cl = wall_cp_leeward(lb)
    leeward = Surface("leeward wall", qh, "qh", cl, qh, gc)
    side = Surface("side walls", qh, "qh", WALL_CP_SIDE, qh, gc)
    surfaces, roof_h = [], [0.0]            # roof_h: horizontal roof force for each windward roof value, lb
    sloped = normal and theta >= 10
    if sloped and roof == "gable":
        a, b = roof_cp_windward(theta, hl)
        lee = Surface("leeward roof", qh, "qh", roof_cp_leeward(theta, hl), qh, gc)
        ww = [Surface("windward roof", qh, "qh", v, qh, gc) for v in (a, b) if v is not None]
        surfaces = ww + [lee]
        roof_h = [(x.external - lee.external) * B * rise for x in ww]
    elif sloped and direction == "normal_low":
        a, b = roof_cp_windward(theta, hl)
        surfaces = [Surface("roof", qh, "qh", v, qh, gc) for v in (a, b) if v is not None]
        roof_h = [x.external * B * rise for x in surfaces]
    elif sloped:
        surfaces = [Surface("roof", qh, "qh", roof_cp_leeward(theta, hl), qh, gc)]
        roof_h = [-surfaces[0].external * B * rise]
    else:
        for nm, x1, x2, cp in roof_cp_parallel(hl):
            if x1 * h >= L - 1e-9:
                continue
            to = L if x2 is None or x2 * h > L else x2 * h
            surfaces.append(Surface("roof", qh, "qh", cp, qh, gc, zone=(nm, x1 * h, to)))
        surfaces.append(Surface("roof, all zones", qh, "qh", ROOF_PARALLEL_OTHER, qh, gc))
    walls_together = [(s.z, s.external - leeward.external) for s in windward]

    def width(z):                          # wall width normal to the wind at height z
        return B if z <= eave or not taper else B * max(0.0, 1.0 - (z - eave) / taper)

    def area(z1, z2):
        cuts = sorted({z1, z2} | ({eave} if z1 < eave < z2 else set()))
        return sum((width(a_) + width(b_)) / 2 * (b_ - a_) for a_, b_ in zip(cuts[:-1], cuts[1:]))

    F_w, z0 = 0.0, 0.0
    for s in windward:                     # the pressure at the top of each height band over that band
        F_w += s.external * area(z0, s.z)
        z0 = s.z
    A_l = area(0.0, top_l)
    F_l = -leeward.external * A_l
    walls = F_w + F_l
    total = max([walls] + [walls + r for r in roof_h])
    A_wall = area(0.0, top_w)
    A_roof = B * rise if normal and direction != "normal_high" else 0.0    # behind the high wall of a monoslope roof: none
    F_min = MIN_WALL * A_wall + MIN_ROOF * A_roof
    return dict(qh=qh, Kh=kh, h_over_L=hl, L_over_B=lb, GCpi=gc, windward=windward, leeward=leeward, side=side, roof=surfaces,
                walls_together=walls_together, direction=direction, theta=theta, rise=rise, top_w=top_w, top_l=top_l, sloped=sloped,
                F_windward=F_w, F_leeward=F_l, F_walls=walls, F_roof=roof_h, F_total=total, A_wall=A_wall, A_roof=A_roof,
                F_min=F_min, F_design=max(total, F_min))


# ---- Components and cladding, walls, h of 60 ft or less (Figure 30.3-1) ------------------
KD_CC = 0.85                                             # Table 26.6-1, buildings, components and cladding
MIN_CC = 16.0                                            # Sect. 30.2.2, psf
WALL_GCP = {"positive": (1.0, 0.7), 4: (-1.1, -0.8), 5: (-1.4, -0.8)}      # at 10 ft2 or less, at 500 ft2 or more


def cc_wall_gcp(area, zone, theta=0.0):
    """(GCp) for a wall, Figure 30.3-1. zone: "positive", 4 or 5."""
    if area is None or area <= 0:
        raise WindError("wind: the effective wind area must be positive")
    lo, hi = WALL_GCP[zone]
    f = min(1.0, max(0.0, (math.log10(area) - 1.0) / (math.log10(500.0) - 1.0)))
    v = lo + (hi - lo) * f
    return v * (0.9 if theta <= 10 else 1.0)


def cc_a(least_dim, h, theta=0.0):
    """Width a of the wall corner zone, Figure 30.3-1 notation."""
    a = max(min(0.10 * least_dim, 0.4 * h), 0.04 * least_dim, 3.0)
    if theta <= 7 and least_dim > 300:
        a = min(a, 0.8 * h)
    return a


def cc_walls(V, exposure, h, least_dim, enclosure, areas, theta=0.0, Kzt=1.0, Ke=1.0):
    """Wall component and cladding pressures (psf, strength level): for each effective wind
    area, the positive pressure (zones 4 and 5) and the negative pressure in zone 4 and in
    zone 5, each with the internal pressure sign that adds, and not less than 16 psf."""
    if enclosure not in GCPI or enclosure == "open":
        raise WindError("wind: the enclosure is enclosed, partially enclosed or partially open (open buildings are not covered)")
    if h is None or h <= 0 or h > 60:
        raise WindError("wind: this procedure is for a mean roof height of 60 ft or less")
    if least_dim is None or least_dim <= 0:
        raise WindError("wind: the least horizontal dimension must be positive")
    if not areas:
        raise WindError("wind: list at least one effective wind area")
    gc = GCPI[enclosure]
    qh, kh = velocity_pressure(V, exposure, h, Kzt, Ke)
    rows = []
    for A in sorted(set(areas)):
        g = {z: cc_wall_gcp(A, z, theta) for z in ("positive", 4, 5)}
        p = {"positive": qh * KD_CC * (g["positive"] + gc), 4: qh * KD_CC * (g[4] - gc), 5: qh * KD_CC * (g[5] - gc)}
        d = {"positive": max(p["positive"], MIN_CC), 4: min(p[4], -MIN_CC), 5: min(p[5], -MIN_CC)}
        rows.append(dict(area=A, gcp=g, p=p, design=d))
    return dict(qh=qh, Kh=kh, GCpi=gc, a=cc_a(least_dim, h, theta), rows=rows)


# ---- Components and cladding, roofs at 7 degrees or less, h of 60 ft or less (Figure 30.3-2A) ----
ROOF_GCP_7 = {"positive": (10, 0.3, 100, 0.2), "1'": (100, -0.9, 1000, -0.4), "1": (10, -1.7, 500, -1.0),
              "2": (10, -2.3, 500, -1.4), "3": (10, -3.2, 500, -1.4)}       # area, value, area, value
ROOF_ZONES_7 = ("1'", "1", "2", "3")


# Figure 30.3-2A, overhang chart (both surfaces included, note 6), read from the 330 dpi page image: zones 1 and 1'
# -1.7 at 10 ft2, -1.6 at 100, then down to 500; zone 2 -2.3 at 10 through -1.6 at 100 to 500; zone 3 -3.2 at 10
# straight to 500. The chart prints two end values at 500 ft2, -1.1 and -1.0, and the scan does not show which line
# takes which; -1.1 is used for every zone (the larger suction).
OVERHANG_GCP_7 = {"1'": ((10, -1.7), (100, -1.6), (500, -1.1)), "1": ((10, -1.7), (100, -1.6), (500, -1.1)),
                  "2": ((10, -2.3), (100, -1.6), (500, -1.1)), "3": ((10, -3.2), (500, -1.1))}


def _log_points(area, pts):
    if area <= pts[0][0]:
        return pts[0][1]
    for (a1, v1), (a2, v2) in zip(pts[:-1], pts[1:]):
        if area <= a2:
            return _log_line(area, a1, v1, a2, v2)
    return pts[-1][1]


def _log_line(area, a1, v1, a2, v2):
    f = min(1.0, max(0.0, (math.log10(area) - math.log10(a1)) / (math.log10(a2) - math.log10(a1))))
    return v1 + (v2 - v1) * f


ROOF_GCP = {
    "30.3-2A": dict(lo=0, hi=7, zones=("1'", "1", "2", "3"), curves=ROOF_GCP_7),
    "30.3-2B": dict(lo=7, hi=20, zones=("1", "2", "3"), curves={"positive": (10, 0.6, 200, 0.3), "1": (10, -2.0, 300, -0.5),
                                                                "2": (10, -2.7, 200, -1.0), "3": (10, -3.6, 100, -1.8)}),
    "30.3-2C": dict(lo=20, hi=27, zones=("1", "2", "3"), curves={"positive": (10, 0.6, 200, 0.3), "1": (10, -1.5, 200, -0.8),
                                                                 "2": (10, -2.5, 100, -1.2), "3": (10, -3.0, 100, -1.4)}),
    "30.3-2D": dict(lo=27, hi=45, zones=("1", "2", "3"), curves={"positive": (10, 0.9, 200, 0.5), "1": (10, -1.8, 100, -0.8),
                                                                 "2": (10, -2.0, 200, -1.0), "3": (10, -2.5, 200, -1.0)}),
}


ROOF_GCP_MONO = {
    "30.3-5A": dict(lo=3, hi=10, zones=("1", "2", "2'", "3", "3'"),
                    curves={"positive": (10, 0.3, 100, 0.2), "1": (10, -1.1, 100, -1.1), "2": (10, -1.3, 100, -1.2), "2'": (10, -1.6, 100, -1.5),
                            "3": (10, -1.8, 100, -1.2), "3'": (10, -2.6, 100, -1.6)}),
    "30.3-5B": dict(lo=10, hi=30, zones=("1", "2", "3"),
                    curves={"positive": (10, 0.4, 100, 0.3), "1": (10, -1.3, 100, -1.1), "2": (10, -1.6, 100, -1.2), "3": (10, -2.9, 100, -2.0)}),
}
ROOF_GCP_ALL = dict(ROOF_GCP, **ROOF_GCP_MONO)


def cc_roof_figure(theta, roof="gable"):
    """The figure for a gable (or flat) or monoslope roof at theta degrees."""
    if roof == "monoslope":
        if theta is None or theta < 0 or theta > 30:
            raise WindError("wind: roof components and cladding are built for monoslope roofs up to 30 degrees")
        return "30.3-2A" if theta <= 3 else "30.3-5A" if theta <= 10 else "30.3-5B"
    if theta is None or theta < 0 or theta > 45:
        raise WindError("wind: roof components and cladding are built for flat roofs and gable roofs up to 45 degrees")
    for name, f in ROOF_GCP.items():
        if theta <= f["hi"]:
            return name


def cc_roof_gcp(area, zone, theta=0.0, roof="gable"):
    """(GCp) for a flat, gable or monoslope roof, Figures 30.3-2A to 2D, 5A and 5B."""
    if area is None or area <= 0:
        raise WindError("wind: the effective wind area must be positive")
    curves = ROOF_GCP_ALL[cc_roof_figure(theta, roof)]["curves"]
    if zone not in curves:
        raise WindError(f"wind: zone {zone} is not a zone of a {roof} roof at {theta:g} degrees")
    return _log_line(area, *curves[zone])


def cc_roof(V, exposure, h, enclosure, areas, theta=0.0, Kzt=1.0, Ke=1.0, least_dim=None, roof="gable", overhang=False):
    """Roof component and cladding pressures (psf, strength level) for a flat roof or a gable
    roof up to 45 degrees: for each effective wind area, the positive pressure and the
    negative pressure in each zone, with the internal pressure sign that adds, not less than
    16 psf. least_dim (the least horizontal dimension) is needed above 7 degrees, for a."""
    if enclosure not in GCPI or enclosure == "open":
        raise WindError("wind: the enclosure is enclosed, partially enclosed or partially open (open buildings are not covered)")
    if h is None or h <= 0 or h > 60:
        raise WindError("wind: this procedure is for a roof height of 60 ft or less")
    fig = cc_roof_figure(theta, roof)
    zones = ROOF_GCP_ALL[fig]["zones"]
    if fig != "30.3-2A" and (least_dim is None or least_dim <= 0):
        raise WindError("wind: the least horizontal dimension of the building is needed for this roof")
    if not areas:
        raise WindError("wind: list at least one effective wind area")
    gc = GCPI[enclosure]
    qh, kh = velocity_pressure(V, exposure, h, Kzt, Ke)
    rows = []
    for A in sorted(set(areas)):
        g = {z: cc_roof_gcp(A, z, theta, roof) for z in ("positive",) + zones}
        p = {z: qh * KD_CC * (v + gc if z == "positive" else v - gc) for z, v in g.items()}
        d = {z: (max(v, MIN_CC) if z == "positive" else min(v, -MIN_CC)) for z, v in p.items()}
        rows.append(dict(area=A, gcp=g, p=p, design=d))
    if overhang:
        for x in rows:
            if fig == "30.3-2A":
                x["overhang_wall"] = None
                x["overhang_gcp"] = {z: _log_points(x["area"], OVERHANG_GCP_7[z]) for z in zones}
            else:
                w = cc_wall_gcp(x["area"], "positive", theta)
                x["overhang_wall"] = w
                x["overhang_gcp"] = {z: x["gcp"][z] - w for z in zones}
            x["overhang"] = {z: min(qh * KD_CC * (v - gc), -MIN_CC) for z, v in x["overhang_gcp"].items()}
    out = dict(qh=qh, Kh=kh, GCpi=gc, figure=fig, zones=zones, rows=rows, overhang=bool(overhang))
    if fig == "30.3-2A":
        out.update(edge=0.6 * h, corner=0.2 * h)
    else:
        out.update(a=cc_a(least_dim, h, theta))
    return out
