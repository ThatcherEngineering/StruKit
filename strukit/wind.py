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
enclosed and partially open rigid buildings with a gable, hip, monoslope or flat roof
(hip roofs: see mwfrs_hip; Zach's ruling of 2026-11-23 14:03):
  Eq. 27.3-1     p = q Kd G Cp - qi Kd (GCpi); q = qz on the windward wall, qh on the leeward
                 wall, side walls and roof; qi = qh (permitted in all cases: qh is not less
                 than qz at an opening).
  Table 26.6-1   Kd = 0.85, buildings, main wind force resisting system.
  Sect. 26.11.1  G = 0.85 for a rigid building.
  Table 26.13-1  GCpi; both signs are considered.
  Figure 27.3-1  Cp for walls and roofs; interpolation between values of the same sign, with
                 0.0 taken where the figure gives no value of that sign (notes 2 and 3). The
                 area reduction of the -1.3 value (note b) is not taken.
  Sect. 27.3.4   parapets (pdf p. 347, page image): pp = qp Kd (GCpn), Eq. 27.3-3, qp at the top
                 of the parapet, (GCpn) = +1.5 for the windward parapet and -1.0 for the
                 leeward parapet (net on both faces; both push downwind).
  Sect. 27.3.5, Figure 27.3-8 (pdf pp. 352-353, page image): Case 1 full pressure along each
                 axis separately; Case 2 0.75 of the wall pressures along one axis with a
                 torsional moment 0.75 (pW + pL) B e, e = 0.15 B, B normal to the wind; Case 3
                 0.75 of the wall pressures along both axes together; Case 4 0.563 along both
                 with the torsional moments of both, 0.563 (pW + pL) B e each. Roof pressures:
                 Case 2, 75 percent of Case 1; Cases 3 and 4, the larger of the Case 1 and
                 Case 2 roof pressures on each roof area (note 2). Function load_cases.
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
  Sect. 30.6     parapets (pdf pp. 394-396, Figure 30.6-1 on p. 400): p = qp Kd [(GCp) - (GCpi)],
                 Eq. 30.6-1, qp at the top of the parapet. Load Case A, windward parapet: the
                 positive wall value on the outside face and the negative roof edge or corner
                 value (zone 2 or 3) on the roof side face. Load Case B, leeward parapet: the
                 positive wall value on the roof side face and the negative wall value (zone 4
                 or 5) on the outside face. Built for roofs in the range of Figure 30.3-2A, as
                 the net pressure on the two faces together.
  Figure 30.3-2A note 5: with a parapet 3 ft or higher around the perimeter of a roof at 7
                 degrees or less, the negative zone 3 values equal those of zone 2, and the
                 positive values in zones 2 and 3 equal those of wall zones 4 and 5.
Not covered: roof components and cladding on other roof shapes, on gable and hip roofs over 45
degrees and monoslope roofs over 30 degrees, the parapet provision of Figure 30.3-2A note 5, roof overhangs
(Sect. 30.7); Parts 2 to 5 of Chapter 30;
hip, mansard and arched roofs; open buildings; flexible buildings;
the horizontal force on roof overhangs; the torsional cases of Figure 27.3-8; Chapters 28 and 30.
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


GCPN_WINDWARD, GCPN_LEEWARD = 1.5, -1.0                 # Sect. 27.3.4
CP_OVERHANG_BOTTOM = 0.8                                # Sect. 27.3.3 (pdf p. 347): bottom surface of a windward roof overhang


def mwfrs_overhang(r, width):
    """Windward roof overhang, Sect. 27.3.3: positive pressure on the bottom surface with Cp = 0.8,
    combined with the top surface pressure of Figure 27.3-1 at the windward edge. r: a result of
    mwfrs(); width: horizontal projection of the overhang, ft. Returns the bottom pressure (psf,
    acting upward), and for each top surface value (Cp, top pressure, net pressure positive
    downward, net load per foot of eave on the horizontal projection). No internal pressure acts."""
    if width is None or width <= 0:
        raise WindError("wind: the roof overhang width must be positive")
    roof = r["roof"]
    if r["sloped"]:
        tops = [x for x in roof if x.name == "windward roof"] or [x for x in roof if x.name == "roof"]
    else:
        zoned = [x for x in roof if x.zone]
        tops = zoned[:1] + [x for x in roof if not x.zone][-1:]
    bottom = r["qh"] * KD_MWFRS * G_RIGID * CP_OVERHANG_BOTTOM
    vals = [dict(Cp=x.Cp, top=x.external, net=x.external - bottom, w=(x.external - bottom) * width) for x in tops]
    return dict(width=width, bottom=bottom, values=vals, net=min(v["net"] for v in vals), w=min(v["w"] for v in vals))



def mwfrs_hip(V, exposure, h, eave, B, L, enclosure, direction, theta, theta_hip, Kzt=1.0, Ke=1.0, parapet=0.0):
    """Hip roof. theta: slope of the main roof planes (eave parallel to the ridge); theta_hip:
    slope of the hip end planes. For each wind direction the plane facing the wind takes the
    windward roof coefficients of Figure 27.3-1 at its own slope, the opposite plane the
    leeward coefficients, and the planes at the sides the coefficients by distance from the
    windward edge. direction "normal" (to the ridge) or "parallel". Walls run to the eave."""
    if direction not in ("normal", "parallel"):
        raise WindError("wind: the wind direction is normal or parallel to the ridge")
    for nm, v in (("the roof angle", theta), ("the hip end roof angle", theta_hip)):
        if v is None or v <= 0 or v >= 90:
            raise WindError(f"wind: {nm} of a hip roof is over 0 and under 90 degrees")
    r = mwfrs(V, exposure, h, eave, B, L, enclosure, "normal", 0.0, Kzt, Ke, parapet=parapet)      # walls to the eave; roof by zones
    normal = direction == "normal"
    across, along = (L, B) if normal else (B, L)
    rise = math.tan(math.radians(theta)) * across / 2.0
    run_hip = rise / math.tan(math.radians(theta_hip))
    ridge = along - 2.0 * run_hip
    if ridge < -1e-6:
        raise WindError("wind: the hip ends meet before the ridge forms (the hip end slope is too flat for this plan)")
    ridge = max(ridge, 0.0)
    facing = theta if normal else theta_hip
    A_proj = (B + ridge) / 2.0 * rise if normal else B * rise / 2.0
    gc, qh, hl = r["GCpi"], r["qh"], r["h_over_L"]
    zones = r["roof"]
    roof_h, sloped = [0.0], facing >= 10
    if sloped:
        for z in zones:
            z.name = "side slopes" if z.zone else "sides, all zones"
        a, b = roof_cp_windward(facing, hl)
        lee = Surface("leeward roof", qh, "qh", roof_cp_leeward(facing, hl), qh, gc)
        ww = [Surface("windward roof", qh, "qh", v, qh, gc) for v in (a, b) if v is not None]
        roof_h = [(x.external - lee.external) * A_proj for x in ww]
        r["roof"] = ww + [lee] + zones
    walls = r["F_walls"]
    total = max([walls] + [walls + x for x in roof_h])
    F_min = MIN_WALL * r["A_wall"] + MIN_ROOF * A_proj
    r.update(direction=direction, theta=facing, rise=rise, ridge=ridge, run_hip=run_hip, sloped=sloped, F_roof=roof_h, F_total=total,
             A_roof=A_proj, F_min=F_min, F_design=max(total, F_min), hip=True)
    return r


def mwfrs(V, exposure, h, eave, B, L, enclosure, direction, theta=0.0, Kzt=1.0, Ke=1.0, roof="gable", parapet=0.0, theta_hip=None):
    if roof == "hip":
        return mwfrs_hip(V, exposure, h, eave, B, L, enclosure, direction, theta, theta_hip, Kzt, Ke, parapet)
    return _mwfrs(V, exposure, h, eave, B, L, enclosure, direction, theta, Kzt, Ke, roof, parapet)


def _mwfrs(V, exposure, h, eave, B, L, enclosure, direction, theta=0.0, Kzt=1.0, Ke=1.0, roof="gable", parapet=0.0):
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
    par = None
    if parapet:
        if parapet < 0:
            raise WindError("wind: the parapet height must be positive")
        qw, _ = velocity_pressure(V, exposure, top_w + parapet, Kzt, Ke)
        ql, _ = velocity_pressure(V, exposure, top_l + parapet, Kzt, Ke)
        par = dict(height=parapet, q_windward=qw, q_leeward=ql, p_windward=qw * KD_MWFRS * GCPN_WINDWARD, p_leeward=ql * KD_MWFRS * GCPN_LEEWARD)
        par["F"] = (par["p_windward"] - par["p_leeward"]) * B * parapet
    walls = F_w + F_l + (par["F"] if par else 0.0)
    total = max([walls] + [walls + r for r in roof_h])
    A_wall = area(0.0, top_w) + (B * parapet if par else 0.0)
    A_roof = B * rise if normal and direction != "normal_high" else 0.0    # behind the high wall of a monoslope roof: none
    F_min = MIN_WALL * A_wall + MIN_ROOF * A_roof
    return dict(qh=qh, Kh=kh, h_over_L=hl, L_over_B=lb, GCpi=gc, windward=windward, leeward=leeward, side=side, roof=surfaces,
                walls_together=walls_together, direction=direction, theta=theta, rise=rise, top_w=top_w, top_l=top_l, sloped=sloped,
                F_windward=F_w, F_leeward=F_l, F_walls=walls, F_roof=roof_h, F_total=total, A_wall=A_wall, A_roof=A_roof,
                F_min=F_min, F_design=max(total, F_min), parapet=par, B=B, eave=eave, taper=taper)


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
# Hip roofs, Figures 30.3-2E (over 7 to 20 degrees), 2F (over 20 to 27) and 2G (45 degrees), pdf pp. 384-386, read from
# 330 dpi page images, break points measured on the log scale. Figure 30.3-2G note 6: between 27 and 45 degrees
# (GCp) = [GCp(2G) - GCp(2F)] (theta - 27) / (45 - 27) + GCp(2F), zone by zone. Zones: 3 within a of the eaves; 2 within a
# of the ridge and of each hip, on each side; 1 the rest. At 7 degrees or less Figure 30.3-2A is used.
ROOF_GCP_HIP = {
    "30.3-2E": dict(lo=7, hi=20, zones=("1", "2", "3"), curves={"positive": (10, 0.7, 100, 0.3), "1": (10, -1.8, 200, -0.8), "2": (10, -2.4, 200, -1.3), "3": (10, -2.6, 200, -1.4)}),
    "30.3-2F": dict(lo=20, hi=27, zones=("1", "2", "3"), curves={"positive": (10, 0.7, 100, 0.3), "1": (10, -1.4, 100, -0.8), "2": (10, -2.0, 100, -1.0), "3": (10, -2.0, 100, -1.0)}),
    "30.3-2G": dict(lo=45, hi=45, zones=("1", "2", "3"), curves={"positive": (10, 0.7, 100, 0.3), "1": (10, -1.5, 100, -0.7), "2": (10, -1.8, 100, -0.8), "3": (10, -2.4, 100, -1.0)}),
    "30.3-2F and 30.3-2G": dict(lo=27, hi=45, zones=("1", "2", "3"), curves=None),
}
ROOF_GCP_ALL = dict(ROOF_GCP, **ROOF_GCP_MONO, **ROOF_GCP_HIP)


def cc_roof_figure(theta, roof="gable"):
    """The figure for a gable (or flat) or monoslope roof at theta degrees."""
    if roof == "monoslope":
        if theta is None or theta < 0 or theta > 30:
            raise WindError("wind: roof components and cladding are built for monoslope roofs up to 30 degrees")
        return "30.3-2A" if theta <= 3 else "30.3-5A" if theta <= 10 else "30.3-5B"
    if theta is None or theta < 0 or theta > 45:
        raise WindError("wind: roof components and cladding are built for flat roofs and gable and hip roofs up to 45 degrees")
    if roof == "hip":
        return "30.3-2A" if theta <= 7 else "30.3-2E" if theta <= 20 else "30.3-2F" if theta <= 27 else "30.3-2G" if theta >= 45 else "30.3-2F and 30.3-2G"
    for name, f in ROOF_GCP.items():
        if theta <= f["hi"]:
            return name


def cc_roof_gcp(area, zone, theta=0.0, roof="gable"):
    """(GCp) for a flat, gable or monoslope roof, Figures 30.3-2A to 2D, 5A and 5B."""
    if area is None or area <= 0:
        raise WindError("wind: the effective wind area must be positive")
    fig = cc_roof_figure(theta, roof)
    if fig == "30.3-2F and 30.3-2G":
        f_, g_ = ROOF_GCP_HIP["30.3-2F"]["curves"], ROOF_GCP_HIP["30.3-2G"]["curves"]
        if zone not in f_:
            raise WindError(f"wind: zone {zone} is not a zone of a hip roof at {theta:g} degrees")
        vf, vg = _log_line(area, *f_[zone]), _log_line(area, *g_[zone])
        return (vg - vf) * (theta - 27.0) / 18.0 + vf
    curves = ROOF_GCP_ALL[fig]["curves"]
    if zone not in curves:
        raise WindError(f"wind: zone {zone} is not a zone of a {roof} roof at {theta:g} degrees")
    return _log_line(area, *curves[zone])


def cc_roof(V, exposure, h, enclosure, areas, theta=0.0, Kzt=1.0, Ke=1.0, least_dim=None, roof="gable", overhang=False, parapet=False):
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
    if parapet and (fig != "30.3-2A" or theta > 7):
        raise WindError("wind: the parapet provision applies to roofs at 7 degrees or less (Figure 30.3-2A, note 5)")
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
        row = dict(area=A, gcp=g, p=p, design=d)
        if parapet:                          # Figure 30.3-2A note 5
            g["3"] = g["2"]
            p["3"], d["3"] = p["2"], d["2"]
            row["edge_positive_gcp"] = cc_wall_gcp(A, "positive", theta)
            row["edge_positive"] = max(qh * KD_CC * (row["edge_positive_gcp"] + gc), MIN_CC)
        rows.append(row)
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
    out = dict(qh=qh, Kh=kh, GCpi=gc, figure=fig, zones=zones, rows=rows, overhang=bool(overhang), parapet=bool(parapet))
    if fig == "30.3-2A":
        out.update(edge=0.6 * h, corner=0.2 * h)
    else:
        out.update(a=cc_a(least_dim, h, theta))
    return out


def cc_parapet(V, exposure, hp_top, h, least_dim, areas, theta=0.0, Kzt=1.0, Ke=1.0):
    """Net component and cladding pressure (psf, strength level) on a parapet of a roof in the
    range of Figure 30.3-2A, Sect. 30.6, the two faces together: Load Case A (windward
    parapet, pressure toward the roof) beside roof zone 2 and beside roof zone 3; Load Case B
    (leeward parapet, pressure away from the roof) in wall zone 4 and in wall zone 5.
    hp_top: height of the top of the parapet above ground; h: the eave height."""
    for nm, v in (("the height of the top of the parapet", hp_top), ("the eave height", h), ("the least horizontal dimension", least_dim)):
        if v is None or v <= 0:
            raise WindError(f"wind: {nm} must be positive")
    if hp_top <= h:
        raise WindError("wind: the top of the parapet is above the eave")
    if h > 60:
        raise WindError("wind: this procedure is for a roof height of 60 ft or less")
    if theta is None or theta < 0 or theta > 7:
        raise WindError("wind: parapets are built for roofs at 7 degrees or less (Figure 30.3-2A)")
    if not areas:
        raise WindError("wind: list at least one effective wind area")
    qp, kp = velocity_pressure(V, exposure, hp_top, Kzt, Ke)
    rows = []
    for A in sorted(set(areas)):
        g = dict(wall_pos=cc_wall_gcp(A, "positive", theta), roof2=cc_roof_gcp(A, "2", theta), roof3=cc_roof_gcp(A, "3", theta),
                 wall4=cc_wall_gcp(A, 4, theta), wall5=cc_wall_gcp(A, 5, theta))
        net = dict(A_edge=g["wall_pos"] - g["roof2"], A_corner=g["wall_pos"] - g["roof3"],
                   B_edge=g["wall_pos"] - g["wall4"], B_corner=g["wall_pos"] - g["wall5"])
        rows.append(dict(area=A, gcp=g, net=net, p={k: max(qp * KD_CC * v, MIN_CC) for k, v in net.items()}))
    return dict(qp=qp, Kp=kp, a=cc_a(least_dim, h, theta), edge=0.6 * h, rows=rows)


def load_cases(Fx, Bx, Fy, By):
    """Figure 27.3-8 for a rigid building, from the wall forces: Fx along the x axis on walls
    of width Bx normal to it, Fy and By likewise. Returns [(case, force along x, force along
    y, torsional moment)]; the moment acts either way."""
    ex, ey = 0.15 * Bx, 0.15 * By
    return [("Case 1, x", Fx, 0.0, 0.0), ("Case 1, y", 0.0, Fy, 0.0),
            ("Case 2, x", 0.75 * Fx, 0.0, 0.75 * Fx * ex), ("Case 2, y", 0.0, 0.75 * Fy, 0.75 * Fy * ey),
            ("Case 3", 0.75 * Fx, 0.75 * Fy, 0.0),
            ("Case 4", 0.563 * Fx, 0.563 * Fy, 0.563 * Fx * ex + 0.563 * Fy * ey)]


def line_load(r, z1, z2):
    """Wind load per foot of building width (plf, strength level) delivered to a diaphragm by
    the walls between heights z1 and z2 above ground, from a mwfrs() result r: windward plus
    leeward wall pressure over the tributary height (windward pressure at the top of each
    height band), the horizontal roof force and the parapets where z2 reaches the top of the
    walls, and the Sect. 27.1.5 minimum on the same areas. Walls under a roof slope (wind
    parallel to the ridge) are averaged over the building width."""
    B, eave, taper = r["B"], r["eave"], r["taper"]
    if z1 is None or z2 is None or z1 < 0 or z2 <= z1:
        raise WindError("wind: the tributary wall heights run from a lower height to a higher one")
    top = max(r["top_w"], r["top_l"])
    if z2 > top + 1e-6:
        raise WindError(f"wind: the tributary height goes above the top of the walls ({top:g} ft)")

    def width(z):
        return B if z <= eave or not taper else B * max(0.0, 1.0 - (z - eave) / taper)

    def area(a, b):
        if b <= a:
            return 0.0
        cuts = sorted({a, b} | ({eave} if a < eave < b else set()))
        return sum((width(p) + width(q)) / 2 * (q - p) for p, q in zip(cuts[:-1], cuts[1:]))

    ww, z0 = 0.0, 0.0
    for s in r["windward"]:
        ww += s.external * area(max(z0, z1), min(s.z, z2))
        z0 = s.z
    A_w = area(z1, min(z2, r["top_w"]))
    A_l = area(z1, min(z2, r["top_l"]))
    lw = -r["leeward"].external * A_l
    at_top = z2 >= top - 1e-6
    roof = max([0.0] + list(r["F_roof"])) if at_top else 0.0
    par = r["parapet"]["F"] if (at_top and r["parapet"]) else 0.0
    A_min = A_w + (B * r["parapet"]["height"] if (at_top and r["parapet"]) else 0.0)
    w_min = (MIN_WALL * A_min + (MIN_ROOF * r["A_roof"] if at_top else 0.0)) / B
    w = (ww + lw + roof + par) / B
    return dict(w=max(w, w_min), w_pressures=w, w_min=w_min, windward=ww / B, leeward=lw / B, roof=roof / B, parapet=par / B,
                governs="the minimum of Sect. 27.1.5" if w_min > w else "the wall and roof pressures", at_top=at_top)


# ---- Topographic factor, Sect. 26.8 and Figure 26.8-1 (pdf p. 336, 337) --------------------------
# shape -> (K1/(H/Lh) by exposure, gamma, mu upwind of crest, mu downwind of crest)
TOPO = {"2D ridge": ({"B": 1.30, "C": 1.45, "D": 1.55}, 3.0, 1.5, 1.5),
        "2D escarpment": ({"B": 0.75, "C": 0.85, "D": 0.95}, 2.5, 1.5, 4.0),
        "3D axisymmetrical hill": ({"B": 0.95, "C": 1.05, "D": 1.15}, 4.0, 1.5, 1.5)}
TOPO_MIN_H = {"B": 60.0, "C": 15.0, "D": 15.0}          # Sect. 26.8.1 condition 3
TOPO_MIN_SLOPE = 0.2                                     # Sect. 26.8.1 condition 2


def kzt(shape, exposure, H, Lh, x, z, downwind, located=True):
    """Topographic factor Kzt = (1 + K1 K2 K3)^2, Eq. 26.8-1, by the equations of Figure 26.8-1.
    H: height of the feature; Lh: distance upwind of the crest to half the height; x: distance
    from the crest to the site (positive), downwind True or False; z: height above the ground
    at the site; located: the site is in the upper half of the hill or ridge or near the crest
    of the escarpment. K1/(H/Lh) is the larger of the value for the exposure and the Exposure C
    value the figure's table of multipliers is built on (its note d: used for any exposure).
    Returns a dict; applies False with Kzt 1.0 and the reason where Sect. 26.8.1 is not met."""
    if shape not in TOPO:
        raise WindError("wind: the topographic feature is one of: " + "; ".join(TOPO))
    if exposure not in TOPO_MIN_H:
        raise WindError("wind: the exposure category is B, C or D")
    for nm, v in (("the height of the feature, H", H), ("the distance Lh", Lh)):
        if v is None or v <= 0:
            raise WindError(f"wind: {nm} must be positive")
    if x is None or x < 0 or z is None or z < 0:
        raise WindError("wind: the distance from the crest and the height above ground are zero or more")
    slope = H / Lh
    why = None
    if not located:
        why = "the site is not in the upper half of the hill or ridge or near the crest of the escarpment (Sect. 26.8.1, condition 1)"
    elif slope < TOPO_MIN_SLOPE:
        why = f"H/Lh = {slope:.2f}, less than 0.2 (Sect. 26.8.1, condition 2)"
    elif H < TOPO_MIN_H[exposure]:
        why = f"H = {H:g} ft, less than {TOPO_MIN_H[exposure]:g} ft for Exposure {exposure} (Sect. 26.8.1, condition 3)"
    k1s, gamma, mu_up, mu_down = TOPO[shape]
    k1_ratio = max(k1s[exposure], k1s["C"])
    steep = slope > 0.5
    slope_used = 0.5 if steep else slope
    L_used = 2.0 * H if steep else Lh                     # Figure 26.8-1 note b
    mu = mu_down if downwind else mu_up
    K1 = k1_ratio * slope_used
    K2 = max(0.0, 1.0 - x / (mu * L_used))
    K3 = math.exp(-gamma * z / L_used)
    val = (1.0 + K1 * K2 * K3) ** 2
    return dict(applies=why is None, why=why, slope=slope, slope_used=slope_used, steep=steep, L_used=L_used, k1_ratio=k1_ratio, gamma=gamma, mu=mu,
                K1=K1, K2=K2, K3=K3, Kzt=val if why is None else 1.0, Kzt_feature=val)


# ---- Open buildings with monoslope free roofs, Sect. 27.3.2 (pdf p. 347), Figures 27.3-4 and 27.3-7 (pdf pp. 348, 351) -------
# Figure 27.3-4, read from the page image: angle -> case -> (CNW, CNL) for [0 clear, 0 obstructed, 180 clear, 180 obstructed].
# gamma = 0: wind against the high edge; gamma = 180: wind against the low edge. First row: roof angles under 7.5 degrees.
FREE_MONO = {
    0.0: {"A": ((1.2, 0.3), (-0.5, -1.2), (1.2, 0.3), (-0.5, -1.2)), "B": ((-1.1, -0.1), (-1.1, -0.6), (-1.1, -0.1), (-1.1, -0.6))},
    7.5: {"A": ((-0.6, -1.0), (-1.0, -1.5), (0.9, 1.5), (-0.2, -1.2)), "B": ((-1.4, 0.0), (-1.7, -0.8), (1.6, 0.3), (0.8, -0.3))},
    15.0: {"A": ((-0.9, -1.3), (-1.1, -1.5), (1.3, 1.6), (0.4, -1.1)), "B": ((-1.9, 0.0), (-2.1, -0.6), (1.8, 0.6), (1.2, -0.3))},
    22.5: {"A": ((-1.5, -1.6), (-1.5, -1.7), (1.7, 1.8), (0.5, -1.0)), "B": ((-2.4, -0.3), (-2.3, -0.9), (2.2, 0.7), (1.3, 0.0))},
    30.0: {"A": ((-1.8, -1.8), (-1.5, -1.8), (2.1, 2.1), (0.6, -1.0)), "B": ((-2.5, -0.5), (-2.3, -1.1), (2.6, 1.0), (1.6, 0.1))},
    37.5: {"A": ((-1.8, -1.8), (-1.5, -1.8), (2.1, 2.2), (0.7, -0.9)), "B": ((-2.4, -0.6), (-2.2, -1.1), (2.7, 1.1), (1.9, 0.3))},
    45.0: {"A": ((-1.6, -1.8), (-1.3, -1.8), (2.2, 2.5), (0.8, -0.9)), "B": ((-2.3, -0.7), (-1.9, -1.2), (2.6, 1.4), (2.1, 0.4))}}
# Figure 27.3-7 (gamma = 90, 270; all free roof shapes to 45 degrees): zone by horizontal distance from the windward edge -> case -> (clear, obstructed)
FREE_PARALLEL = (("0 to h", {"A": (-0.8, -1.2), "B": (0.8, 0.5)}), ("h to 2h", {"A": (-0.6, -0.9), "B": (0.5, 0.5)}), ("over 2h", {"A": (-0.3, -0.6), "B": (0.3, 0.3)}))


def free_mono_cn(theta, obstructed=False):
    """(CNW, CNL) for gamma = 0 and gamma = 180, Cases A and B, Figure 27.3-4, with straight-line
    interpolation between 7.5 and 45 degrees (note 3); under 7.5 degrees the first row."""
    if theta is None or theta < 0 or theta > 45:
        raise WindError("wind: a monoslope free roof is between 0 and 45 degrees (Figure 27.3-4)")
    k = 1 if obstructed else 0
    if theta < 7.5:
        row = lambda case, col: FREE_MONO[0.0][case][col]
    else:
        angs = sorted(a for a in FREE_MONO if a >= 7.5)
        lo = max(a for a in angs if a <= theta)
        hi = min(a for a in angs if a >= theta)
        f = 0.0 if hi == lo else (theta - lo) / (hi - lo)
        row = lambda case, col: tuple(x + (y - x) * f for x, y in zip(FREE_MONO[lo][case][col], FREE_MONO[hi][case][col]))
    return {g: {case: row(case, col) for case in ("A", "B")} for g, col in ((0, k), (180, 2 + k))}


def free_roof_monoslope(V, exposure, h, theta, L, obstructed=False, Kzt=1.0, Ke=1.0):
    """Net design pressures (psf, strength level) on a monoslope free roof of an open building,
    p = qh Kd G CN (Eq. 27.3-2): the windward and leeward halves for wind across the slope
    (Figure 27.3-4, 0.25 <= h/L <= 1.0) and the zones of Figure 27.3-7 for wind along it.
    L: horizontal dimension of the roof in the direction of the slope."""
    for nm, v in (("the mean roof height", h), ("the roof dimension L", L)):
        if v is None or v <= 0:
            raise WindError(f"wind: {nm} must be positive")
    hl = h / L
    low = 0.05 <= hl < 0.25 and theta is not None and theta < 5.0          # Figure 27.3-4 note 4
    if not (0.25 <= hl <= 1.0) and not low:
        raise WindError(f"wind: h/L = {hl:.2f} is outside Figure 27.3-4 (0.25 to 1.0; 0.05 to 0.25 only under 5 degrees, by Figure 27.3-7)")
    qh, kh = velocity_pressure(V, exposure, h, Kzt, Ke)
    k = qh * KD_MWFRS * G_RIGID
    col = 1 if obstructed else 0
    par = [dict(zone=z, x0=i * h, x1=(i + 1) * h if i < 2 else None, A=cn["A"][col], B=cn["B"][col], pA=k * cn["A"][col], pB=k * cn["B"][col])
           for i, (z, cn) in enumerate(FREE_PARALLEL)]
    across = None
    if not low:
        cn = free_mono_cn(theta, obstructed)
        across = [dict(gamma=g, case=c, CNW=cn[g][c][0], CNL=cn[g][c][1], pW=k * cn[g][c][0], pL=k * cn[g][c][1]) for g in (0, 180) for c in ("A", "B")]
    return dict(qh=qh, Kh=kh, h_over_L=hl, factor=k, across=across, parallel=par, low=low)


# Figure 27.3-5 (pdf p. 349), pitched free roofs, gamma = 0 and 180 (the same by symmetry): angle -> case -> (CNW, CNL) for [clear, obstructed].
# Under 7.5 degrees the figure sends the reader to Figure 27.3-4 (its note 3).
FREE_PITCHED = {
    7.5: {"A": ((1.1, -0.3), (-1.6, -1.0)), "B": ((0.2, -1.2), (-0.9, -1.7))},
    15.0: {"A": ((1.1, -0.4), (-1.2, -1.0)), "B": ((0.1, -1.1), (-0.6, -1.6))},
    22.5: {"A": ((1.1, 0.1), (-1.2, -1.2)), "B": ((-0.1, -0.8), (-0.8, -1.7))},
    30.0: {"A": ((1.3, 0.3), (-0.7, -0.7)), "B": ((-0.1, -0.9), (-0.2, -1.1))},
    37.5: {"A": ((1.3, 0.6), (-0.6, -0.6)), "B": ((-0.2, -0.6), (-0.3, -0.9))},
    45.0: {"A": ((1.1, 0.9), (-0.5, -0.5)), "B": ((-0.3, -0.5), (-0.3, -0.7))}}


# Figure 27.3-6 (pdf p. 350), troughed free roofs, same layout as FREE_PITCHED.
FREE_TROUGHED = {
    7.5: {"A": ((-1.1, 0.3), (-1.6, -0.5)), "B": ((-0.2, 1.2), (-0.9, -0.8))},
    15.0: {"A": ((-1.1, 0.4), (-1.2, -0.5)), "B": ((0.1, 1.1), (-0.6, -0.8))},
    22.5: {"A": ((-1.1, -0.1), (-1.2, -0.6)), "B": ((-0.1, 0.8), (-0.8, -0.8))},
    30.0: {"A": ((-1.3, -0.3), (-1.4, -0.4)), "B": ((0.1, 0.9), (-0.2, -0.5))},
    37.5: {"A": ((-1.3, -0.6), (-1.4, -0.3)), "B": ((0.2, 0.6), (-0.3, -0.4))},
    45.0: {"A": ((-1.1, -0.9), (-1.2, -0.3)), "B": ((0.3, 0.5), (-0.3, -0.4))}}


def free_pitched_cn(theta, obstructed=False, table=None):
    """(CNW, CNL) for Cases A and B, Figure 27.3-5 (or 27.3-6 with table=FREE_TROUGHED); under
    7.5 degrees the Figure 27.3-4 values (note 3 of both figures)."""
    table = table or FREE_PITCHED
    if theta is None or theta < 0 or theta > 45:
        raise WindError("wind: a pitched or troughed free roof is between 0 and 45 degrees (Figures 27.3-5, 27.3-6)")
    k = 1 if obstructed else 0
    if theta < 7.5:
        return {c: FREE_MONO[0.0][c][k] for c in ("A", "B")}
    angs = sorted(table)
    lo, hi = max(a for a in angs if a <= theta), min(a for a in angs if a >= theta)
    f = 0.0 if hi == lo else (theta - lo) / (hi - lo)
    return {c: tuple(x + (y - x) * f for x, y in zip(table[lo][c][k], table[hi][c][k])) for c in ("A", "B")}


def free_roof(V, exposure, h, theta, L, roof="monoslope", obstructed=False, Kzt=1.0, Ke=1.0):
    """free_roof_monoslope, or the same for a pitched (gable) free roof: L is then the whole
    horizontal width, eave to eave, and the windward and leeward halves are the two slopes."""
    if roof == "monoslope":
        return free_roof_monoslope(V, exposure, h, theta, L, obstructed, Kzt, Ke)
    if roof not in ("pitched", "troughed"):
        raise WindError("wind: the free roof is monoslope, pitched or troughed")
    r = free_roof_monoslope(V, exposure, h, min(theta, 45.0) if theta is not None else theta, L, obstructed, Kzt, Ke)      # range checks, qh and Figure 27.3-7
    if r["across"] is not None:
        cn = free_pitched_cn(theta, obstructed, FREE_TROUGHED if roof == "troughed" else None)
        r["across"] = [dict(gamma=0, case=c, CNW=cn[c][0], CNL=cn[c][1], pW=r["factor"] * cn[c][0], pL=r["factor"] * cn[c][1]) for c in ("A", "B")]
    return r


MIN_OPEN = 16.0                                          # psf on the area Af, Sect. 27.1.5 (pdf p. 342), open buildings


def free_roof_totals(r, theta, L, B, roof="monoslope"):
    """Total force on the roof for each case of wind across the slope or ridge: H along the
    wind direction (plus = with the wind) and V vertical (plus = downward), lb, from the net
    pressures on the two halves (each 0.5 L by B in plan; pressures normal to the surface),
    and the Sect. 27.1.5 minimum 16 psf x Af with Af the roof projected on a vertical plane
    normal to the wind. B: roof dimension perpendicular to L."""
    if B is None or B <= 0:
        raise WindError("wind: the roof width must be positive")
    if not r.get("across"):
        return None
    t = math.tan(math.radians(theta))
    half = 0.5 * L * B                                    # plan area of one half
    out = []
    for x in r["across"]:
        V = (x["pW"] + x["pL"]) * half
        if roof == "pitched":
            H = (x["pW"] - x["pL"]) * half * t
        elif roof == "troughed":                          # the windward half faces downwind, the leeward half upwind
            H = (x["pL"] - x["pW"]) * half * t
        else:                                             # the top surface faces the low edge: downwind for gamma = 0, upwind for gamma = 180
            H = (-1.0 if x["gamma"] == 0 else 1.0) * (x["pW"] + x["pL"]) * half * t
        out.append(dict(gamma=x["gamma"], case=x["case"], H=H, V=V))
    Af = B * (L * t if roof == "monoslope" else 0.5 * L * t)
    return dict(rows=out, Af=Af, F_min=MIN_OPEN * Af)


def free_roof_hip(V, exposure, h, theta, theta_hip, L, length, obstructed=False, Kzt=1.0, Ke=1.0):
    """Open building with a hip roof. ASCE/SEI 7-22 has no free-roof figure for hip roofs; by the
    Thatcher Engineering standard of 2026-11-23 the roof is taken as a pitched free roof in each
    direction: wind across the long side with the main slope theta and L (eave to eave), wind on
    the hip end with the hip-end slope theta_hip and the building length. Where h over that
    direction's dimension is outside Figure 27.3-5 (0.25 to 1.0) the zones of Figure 27.3-7 are
    given for that direction instead. Returns dict(qh, Kh, factor, dirs=[...])."""
    for nm, v in (("the mean roof height", h), ("the roof dimension L", L), ("the building length", length)):
        if v is None or v <= 0:
            raise WindError(f"wind: {nm} must be positive")
    qh, kh = velocity_pressure(V, exposure, h, Kzt, Ke)
    k = qh * KD_MWFRS * G_RIGID
    col = 1 if obstructed else 0
    dirs = []
    for name, th, dim, other in (("across the long side", theta, L, length), ("on the hip end", theta_hip, length, L)):
        hl = h / dim
        d = dict(name=name, theta=th, L=dim, B=other, h_over_L=hl, across=None, parallel=None)
        if 0.25 <= hl <= 1.0:
            cn = free_pitched_cn(th, obstructed)
            d["across"] = [dict(gamma=0, case=c, CNW=cn[c][0], CNL=cn[c][1], pW=k * cn[c][0], pL=k * cn[c][1]) for c in ("A", "B")]
        else:
            if th is None or th < 0 or th > 45:
                raise WindError("wind: a free roof is between 0 and 45 degrees")
            d["parallel"] = [dict(zone=z, x0=i * h, x1=(i + 1) * h if i < 2 else None, A=c_["A"][col], B=c_["B"][col], pA=k * c_["A"][col], pB=k * c_["B"][col])
                             for i, (z, c_) in enumerate(FREE_PARALLEL)]
        dirs.append(d)
    return dict(qh=qh, Kh=kh, factor=k, dirs=dirs)


# Components and cladding of free roofs, net pressure coefficients CN, ASCE/SEI 7-22 Figures 30.5-1 (monoslope), 30.5-2 (pitched) and
# 30.5-3 (troughed), pdf pp. 397-399, read from the page images.  Per angle: zone 3, zone 2, zone 1, each (plus, minus), for an effective
# wind area of a^2 or less.  Over a^2 up to 4 a^2 zone 3 takes the zone 2 values; over 4 a^2 every zone takes the zone 1 values.
FREE_CC = {
    "monoslope": {False: {0: ((2.4, -3.3), (1.8, -1.7), (1.2, -1.1)), 7.5: ((3.2, -4.2), (2.4, -2.1), (1.6, -1.4)), 15: ((3.6, -3.8), (2.7, -2.9), (1.8, -1.9)),
                          30: ((5.2, -5.0), (3.9, -3.8), (2.6, -2.5)), 45: ((5.2, -4.6), (3.9, -3.5), (2.6, -2.3))},
                  True: {0: ((1.0, -3.6), (0.8, -1.8), (0.5, -1.2)), 7.5: ((1.6, -5.1), (1.2, -2.6), (0.8, -1.7)), 15: ((2.4, -4.2), (1.8, -3.2), (1.2, -2.1)),
                         30: ((3.2, -4.6), (2.4, -3.5), (1.6, -2.3)), 45: ((4.2, -3.8), (3.2, -2.9), (2.1, -1.9))}},
    "pitched": {False: {0: ((2.4, -3.3), (1.8, -1.7), (1.2, -1.1)), 7.5: ((2.2, -3.6), (1.7, -1.8), (1.1, -1.2)), 15: ((2.2, -2.2), (1.7, -1.7), (1.1, -1.1)),
                        30: ((2.6, -1.8), (2.0, -1.4), (1.3, -0.9)), 45: ((2.2, -1.6), (1.7, -1.2), (1.1, -0.8))},
                True: {0: ((1.0, -3.6), (0.8, -1.8), (0.5, -1.2)), 7.5: ((1.0, -5.1), (0.8, -2.6), (0.5, -1.7)), 15: ((1.0, -3.2), (0.8, -2.4), (0.5, -1.6)),
                       30: ((1.0, -2.4), (0.8, -1.8), (0.5, -1.2)), 45: ((1.0, -2.4), (0.8, -1.8), (0.5, -1.2))}},
    "troughed": {False: {0: ((2.4, -3.3), (1.8, -1.7), (1.2, -1.1)), 7.5: ((2.4, -3.3), (1.8, -1.7), (1.2, -1.1)), 15: ((2.2, -2.2), (1.7, -1.7), (1.1, -1.1)),
                         30: ((1.8, -2.6), (1.4, -2.0), (0.9, -1.3)), 45: ((1.6, -2.2), (1.2, -1.7), (0.8, -1.1))},
                 True: {0: ((1.0, -3.6), (0.8, -1.8), (0.5, -1.2)), 7.5: ((1.0, -4.8), (0.8, -2.4), (0.5, -1.6)), 15: ((1.0, -2.4), (0.8, -1.8), (0.5, -1.2)),
                        30: ((1.0, -2.8), (0.8, -2.1), (0.5, -1.4)), 45: ((1.0, -2.4), (0.8, -1.8), (0.5, -1.2))}},
}
FREE_CC_FIGURE = {"monoslope": "Figure 30.5-1", "pitched": "Figure 30.5-2", "troughed": "Figure 30.5-3"}


def free_cc_cn(theta, roof="monoslope", obstructed=False):
    """CN for an effective wind area of a^2 or less: ((z3+, z3-), (z2+, z2-), (z1+, z1-)), interpolated on the roof angle (note 3)."""
    if roof not in FREE_CC:
        raise WindError("wind: free roof cladding is for monoslope, pitched and troughed roofs (Figures 30.5-1 to 30.5-3)")
    if theta is None or theta < 0 or theta > 45:
        raise WindError("wind: a free roof is between 0 and 45 degrees")
    t = FREE_CC[roof][bool(obstructed)]
    ks = sorted(t)
    for lo, hi in zip(ks, ks[1:]):
        if lo <= theta <= hi:
            f = (theta - lo) / (hi - lo)
            return tuple(tuple(a + f * (b - a) for a, b in zip(za, zb)) for za, zb in zip(t[lo], t[hi]))
    raise WindError("wind: a free roof is between 0 and 45 degrees")


def free_cc(V, exposure, h, theta, least_dim, roof="monoslope", obstructed=False, Kzt=1.0, Ke=1.0):
    """Components and cladding of a free roof, p = qh Kd G CN (Eq. 30.5-1), not less than 16 psf either way (Sect. 30.2.2).
    Returns dict(qh, a, factor, figure, rows=[dict(band, lo, hi, zones={3: (CN+, CN-, p+, p-), 2: ..., 1: ...})])."""
    if least_dim is None or least_dim <= 0:
        raise WindError("wind: the least horizontal dimension of the roof must be positive")
    qh, kh = velocity_pressure(V, exposure, h, Kzt, Ke)
    k = qh * KD_CC * G_RIGID
    a = max(min(0.10 * least_dim, 0.4 * h), 0.04 * least_dim, 3.0)
    z3, z2, z1 = free_cc_cn(theta, roof, obstructed)
    rows = []
    for band, lo, hi, zs in (("a^2 or less", 0.0, a * a, (z3, z2, z1)), ("over a^2 to 4 a^2", a * a, 4 * a * a, (z2, z2, z1)), ("over 4 a^2", 4 * a * a, None, (z1, z1, z1))):
        rows.append(dict(band=band, lo=lo, hi=hi, zones={n: (c[0], c[1], max(k * c[0], MIN_CC), min(k * c[1], -MIN_CC)) for n, c in zip((3, 2, 1), zs)}))
    return dict(qh=qh, Kh=kh, a=a, factor=k, figure=FREE_CC_FIGURE[roof], rows=rows)


def enclosure(walls, roof_gross, roof_open=0.0):
    """Enclosure classification, ASCE/SEI 7-22 Sect. 26.2 definitions (pdf pp. 322-323) and Sect. 26.12.  walls: list of dict(name, gross, open), ft2,
    each wall taken in turn as the wall that receives positive external pressure; roof_gross, roof_open: ft2.
    Open: every wall Ao >= 0.8 Ag.  Enclosed: every wall Ao <= the smaller of 0.01 Ag and 4 ft2.  Partially enclosed: for some wall Ao > 1.10 Aoi,
    Ao > the smaller of 4 ft2 and 0.01 Ag, and Aoi / Agi <= 0.20.  Partially open: none of these.
    Returns dict(classification, GCpi, walls=[per-wall values], governing wall)."""
    if not walls:
        raise WindError("wind: enter the walls of the building")
    if roof_gross is None or roof_gross <= 0 or roof_open < 0 or roof_open > roof_gross:
        raise WindError("wind: the roof needs a gross area, and openings between zero and that area")
    for w in walls:
        if w["gross"] <= 0 or w["open"] < 0 or w["open"] > w["gross"]:
            raise WindError(f"wind: wall '{w['name']}' needs a gross area, and openings between zero and that area")
    tot_o, tot_g = sum(w["open"] for w in walls) + roof_open, sum(w["gross"] for w in walls) + roof_gross
    out = []
    for w in walls:
        Ao, Ag = w["open"], w["gross"]
        Aoi, Agi = tot_o - Ao, tot_g - Ag
        lim = min(0.01 * Ag, 4.0)
        out.append(dict(name=w["name"], Ao=Ao, Ag=Ag, Aoi=Aoi, Agi=Agi, ratio=Ao / Ag, limit=lim, open80=Ao >= 0.8 * Ag, small=Ao <= lim,
                        c1=Ao > 1.10 * Aoi, c2=Ao > lim, c3=Aoi / Agi <= 0.20, balance=Aoi / Agi))
    gov = None
    if all(x["open80"] for x in out):
        cls = "open"
    elif all(x["small"] for x in out):
        cls = "enclosed"
    else:
        pe = [x for x in out if x["c1"] and x["c2"] and x["c3"]]
        cls = "partially enclosed" if pe else "partially open"
        gov = pe[0]["name"] if pe else None
    return dict(classification=cls, GCpi=GCPI[cls], walls=out, governing=gov)
