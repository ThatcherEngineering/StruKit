"""Isolated spread footing under a concentric vertical load.

Source on file: ACI 318-19, Building Code Requirements for Structural Concrete.
Every result line names the section or table it comes from.

Covered: soil bearing pressure (service load, with footing and soil weight), one-way
shear, two-way (punching) shear, flexure, minimum flexural reinforcement, bearing on
the footing under the column or base plate.
Not covered (listed on every result so nothing is implied): eccentric load or moment,
uplift, sliding, overturning, bar development length, bar spacing limits, dowels,
column or pedestal design. Load combinations are supplied by the caller.

Units: lb, inch, psi unless a name says otherwise (dimensions in the argument list are
in feet or inches as named).
"""
import math
from dataclasses import dataclass, field

BAR_DIA = {3: 0.375, 4: 0.500, 5: 0.625, 6: 0.750, 7: 0.875, 8: 1.000}      # in, ASTM A615
BAR_AREA = {3: 0.11, 4: 0.20, 5: 0.31, 6: 0.44, 7: 0.60, 8: 0.79}          # in^2, ASTM A615
NOT_CHECKED = ["eccentric load or moment", "uplift, sliding, overturning",
               "bar development length (ACI 318-19 13.2.8, 25.4)",
               "bar spacing limits (ACI 318-19 8.7.2)", "dowels / force transfer steel (16.3)"]


class FootingInputError(ValueError):
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
    def dc(self):
        return self.demand / self.capacity if self.capacity else float("inf")

    @property
    def ok(self):
        return self.demand <= self.capacity


@dataclass
class FootingResult:
    checks: list
    values: dict
    notes: list = field(default_factory=list)
    not_checked: list = field(default_factory=lambda: list(NOT_CHECKED))

    def get(self, name):
        return next(c for c in self.checks if c.name == name)

    @property
    def ok(self):
        return all(c.ok for c in self.checks)


def _beta1(fc):
    """ACI 318-19 Table 22.2.2.4.3."""
    if fc <= 4000:
        return 0.85
    return max(0.85 - 0.05 * (fc - 4000) / 1000, 0.65)


def check(B_ft, L_ft, h_in, fc, fy, col_x_in, col_y_in, bar, n_x, n_y, cover_in,
          P_service, service_combo, Pu, strength_combo, q_allow_psf, conc_pcf,
          plate_x_in=None, plate_y_in=None, bottom_layer="x",
          soil_depth_ft=0.0, soil_pcf=0.0, lam=1.0):
    """B is the plan dimension along x, L along y. n_x bars run in the x direction
    (they resist bending of the x cantilevers), n_y in the y direction. bottom_layer
    names the bar direction placed lowest. P_service and Pu are the column loads (lb)
    for the governing service and factored combinations named by the caller."""
    if bar not in BAR_DIA:
        raise FootingInputError(f"footing: bar size #{bar} is not in the bar table (#3 to #8)")
    if bottom_layer not in ("x", "y"):
        raise FootingInputError("footing: bottom_layer must be 'x' or 'y'")
    for nm, v in (("B_ft", B_ft), ("L_ft", L_ft), ("h_in", h_in), ("fc", fc), ("fy", fy),
                  ("col_x_in", col_x_in), ("col_y_in", col_y_in), ("q_allow_psf", q_allow_psf),
                  ("conc_pcf", conc_pcf), ("n_x", n_x), ("n_y", n_y)):
        if v is None or v <= 0:
            raise FootingInputError(f"footing: {nm} must be a positive number")
    if (plate_x_in is None) != (plate_y_in is None):
        raise FootingInputError("footing: give both base plate dimensions or neither")

    B, L = B_ft * 12, L_ft * 12
    db, Ab = BAR_DIA[bar], BAR_AREA[bar]
    d_low = h_in - cover_in - db / 2
    d_up = h_in - cover_in - db - db / 2
    d = {"x": d_low if bottom_layer == "x" else d_up,
         "y": d_low if bottom_layer == "y" else d_up}
    d_avg = (d_low + d_up) / 2                                   # 22.6.2.1
    if d_up <= 0:
        raise FootingInputError("footing: thickness is too small for the cover and two bar layers")
    As = {"x": n_x * Ab, "y": n_y * Ab}
    width = {"x": L, "y": B}             # width of the section that x bars / y bars cross
    span = {"x": B, "y": L}
    # critical-section half dimension of the supported member, Table 13.2.7.1
    if plate_x_in:
        half = {"x": (col_x_in + plate_x_in) / 4, "y": (col_y_in + plate_y_in) / 4}
        crit_src = "Table 13.2.7.1: halfway between column face and plate edge"
        A1 = plate_x_in * plate_y_in
        load_x, load_y = plate_x_in, plate_y_in
    else:
        half = {"x": col_x_in / 2, "y": col_y_in / 2}
        crit_src = "Table 13.2.7.1: face of column"
        A1 = col_x_in * col_y_in
        load_x, load_y = col_x_in, col_y_in
    if 2 * half["x"] >= B or 2 * half["y"] >= L:
        raise FootingInputError("footing: the column is as large as the footing")

    area_sf = B_ft * L_ft
    checks, notes, val = [], [], {}
    sq = math.sqrt(fc)

    # --- soil bearing, service loads (13.2.6.1, 13.3.1.1) ---
    W_ftg = area_sf * h_in / 12 * conc_pcf
    W_soil = (area_sf - A1 / 144) * soil_depth_ft * soil_pcf
    q = (P_service + W_ftg + W_soil) / area_sf
    val.update(W_ftg=W_ftg, W_soil=W_soil)
    checks.append(Check("soil bearing pressure", q, q_allow_psf, "psf", service_combo,
                        "ACI 318-19 13.3.1.1; allowable from the soils source",
                        f"column {P_service:.0f} + footing {W_ftg:.0f} + soil {W_soil:.0f} lb "
                        f"over {area_sf:.2f} sf"))

    # --- factored net pressure (13.2.6.3) ---
    qu = Pu / (B * L)                                            # psi
    val.update(qu_psf=qu * 144, d_x=d["x"], d_y=d["y"], d_avg=d_avg, As_x=As["x"], As_y=As["y"])

    for ax in ("x", "y"):
        b, dd, a_s = width[ax], d[ax], As[ax]
        cant = span[ax] / 2 - half[ax]                           # cantilever from the Mu section
        # one-way shear at d from the critical section (13.2.7.2, 7.4.3.2)
        reach = cant - dd
        Vu = qu * b * max(reach, 0.0)
        rho = a_s / (b * dd)
        Vc = min(8 * lam * rho ** (1 / 3) * sq * b * dd, 5 * lam * sq * b * dd)
        checks.append(Check(f"one-way shear, {ax} direction", Vu, 0.75 * Vc, "lb", strength_combo,
                            "ACI 318-19 Table 22.5.5.1(c), 22.5.5.1.1; phi = 0.75 (Table 21.2.1)",
                            f"section at d = {dd:.2f} in from the critical section ({crit_src}); "
                            f"rho_w = {rho:.5f}; size effect neglected per 13.2.6.2"))
        # flexure at the critical section (13.2.7.1)
        Mu = qu * b * cant ** 2 / 2                              # lb-in
        a = a_s * fy / (0.85 * fc * b)                           # 22.2.2.4.1
        c = a / _beta1(fc)
        eps_t = 0.003 * (dd - c) / c                             # 22.2.2.1
        eps_ty = fy / 29.0e6
        if eps_t < eps_ty + 0.003:
            raise FootingInputError(
                f"footing: the {ax}-direction section is not tension controlled "
                f"(eps_t = {eps_t:.4f}); Table 21.2.2 transition is not built yet")
        Mn = a_s * fy * (dd - a / 2)
        checks.append(Check(f"flexure, {ax} direction", Mu / 12, 0.90 * Mn / 12, "lb-ft",
                            strength_combo,
                            "ACI 318-19 13.2.7.1, 22.2.2.4.1; phi = 0.90 (Table 21.2.2)",
                            f"cantilever {cant:.2f} in; a = {a:.3f} in; d = {dd:.2f} in; "
                            f"eps_t = {eps_t:.4f}"))
        As_min = 0.0018 * b * h_in
        checks.append(Check(f"minimum reinforcement, {ax} direction", As_min, a_s, "in^2", "-",
                            "ACI 318-19 8.6.1.1: As,min = 0.0018 Ag",
                            "demand is the required area, capacity is the area provided"))

    # --- two-way shear at d/2 from the critical section (22.6.4.1) ---
    b1, b2 = 2 * half["x"] + d_avg, 2 * half["y"] + d_avg
    if b1 >= B or b2 >= L:
        notes.append("two-way shear: the critical perimeter falls outside the footing, so "
                     "punching does not apply")
    else:
        bo = 2 * (b1 + b2)
        beta = max(load_x, load_y) / min(load_x, load_y)
        vc = min(4, 2 + 4 / beta, 2 + 40 * d_avg / bo) * lam * sq
        Vu2 = Pu - qu * b1 * b2
        checks.append(Check("two-way shear", Vu2, 0.75 * vc * bo * d_avg, "lb", strength_combo,
                            "ACI 318-19 Table 22.6.5.2, 22.6.4.1, 22.6.2.1; phi = 0.75",
                            f"bo = {bo:.2f} in; d = {d_avg:.3f} in (average of both layers); "
                            f"vc = {vc:.1f} psi; alpha_s = 40; size effect neglected per 13.2.6.2"))

    # --- bearing on the footing (22.8.3.2) ---
    e = min(2 * h_in, (B - load_x) / 2, (L - load_y) / 2)       # 1 vertical : 2 horizontal
    A2 = (load_x + 2 * e) * (load_y + 2 * e)
    Bn = min(math.sqrt(A2 / A1), 2.0) * 0.85 * fc * A1
    checks.append(Check("bearing on footing", Pu, 0.65 * Bn, "lb", strength_combo,
                        "ACI 318-19 Table 22.8.3.2(a),(b); phi = 0.65 (Table 21.2.1)",
                        f"A1 = {A1:.0f} in^2; A2 = {A2:.0f} in^2"))
    return FootingResult(checks, val, notes)


def check_continuous(W_ft, h_in, fc, fy, wall_in, bar_t, spacing_t_in, bar_l, n_l, cover_in,
                     P_service_plf, service_combo, Pu_plf, strength_combo, dead_factor,
                     q_allow_psf, conc_pcf, wall_kind="concrete", stem_h_in=0.0,
                     stem_pcf=None, soil_depth_ft=0.0, soil_pcf=0.0, lam=1.0):
    """Continuous (strip) footing under a concentric wall, per foot of length.

    Transverse bars (bar_t at spacing_t_in) are the bottom layer and resist bending of
    the projections. n_l longitudinal bars of size bar_l run along the footing.
    P_service_plf and Pu_plf are the wall loads at the top of the stem wall (lb/ft) for
    the combinations the caller names. The stem wall's own weight is added here: at
    full weight for soil bearing, and times dead_factor (the dead-load factor of the
    governing strength combination, e.g. 1.2) for strength. Footing weight and the soil
    over the projections count toward soil bearing only (ACI 318-19 13.2.6.3: strength
    uses the pressure caused by the factored loads).
    """
    for b in (bar_t, bar_l):
        if b not in BAR_DIA:
            raise FootingInputError(f"footing: bar size #{b} is not in the bar table (#3 to #8)")
    if wall_kind not in ("concrete", "masonry"):
        raise FootingInputError("footing: wall_kind must be 'concrete' or 'masonry'")
    if stem_h_in and stem_pcf is None:
        raise FootingInputError("footing: a stem wall height needs stem_pcf (its unit weight)")
    for nm, v in (("W_ft", W_ft), ("h_in", h_in), ("fc", fc), ("fy", fy), ("wall_in", wall_in),
                  ("spacing_t_in", spacing_t_in), ("n_l", n_l), ("q_allow_psf", q_allow_psf),
                  ("conc_pcf", conc_pcf)):
        if v is None or v <= 0:
            raise FootingInputError(f"footing: {nm} must be a positive number")
    if dead_factor is None or dead_factor < 0:
        raise FootingInputError("footing: dead_factor must be given (0 leaves the stem wall out)")
    W = W_ft * 12
    if wall_in >= W:
        raise FootingInputError("footing: the wall is as wide as the footing")

    d = h_in - cover_in - BAR_DIA[bar_t] / 2
    As = BAR_AREA[bar_t] * 12 / spacing_t_in                     # in^2 per ft
    b = 12.0
    sq = math.sqrt(fc)
    if wall_kind == "concrete":
        half, crit_src = wall_in / 2, "Table 13.2.7.1: face of wall"
    else:
        half, crit_src = wall_in / 4, "Table 13.2.7.1: halfway between center and face of masonry wall"

    W_ftg = W_ft * h_in / 12 * conc_pcf
    W_stem = wall_in / 12 * stem_h_in / 12 * (stem_pcf or 0.0)
    W_soil = (W_ft - wall_in / 12) * soil_depth_ft * soil_pcf
    checks, notes = [], []
    q = (P_service_plf + W_ftg + W_stem + W_soil) / W_ft
    checks.append(Check("soil bearing pressure", q, q_allow_psf, "psf", service_combo,
                        "ACI 318-19 13.3.1.1; allowable from the soils source",
                        f"wall {P_service_plf:.0f} + footing {W_ftg:.1f} + stem {W_stem:.1f} + "
                        f"soil {W_soil:.1f} lb/ft over {W_ft:.2f} ft"))

    Pu = Pu_plf + dead_factor * W_stem
    qu = Pu / W / 12                                             # psi
    cant = W / 2 - half
    reach = cant - d
    Vu = qu * b * max(reach, 0.0)
    rho = As / (b * d)
    Vc = min(8 * lam * rho ** (1 / 3) * sq * b * d, 5 * lam * sq * b * d)
    checks.append(Check("one-way shear", Vu, 0.75 * Vc, "lb/ft", strength_combo,
                        "ACI 318-19 Table 22.5.5.1(c), 22.5.5.1.1; phi = 0.75 (Table 21.2.1)",
                        f"section at d = {d:.2f} in from the critical section ({crit_src}); "
                        f"rho_w = {rho:.5f}; size effect neglected per 13.2.6.2"))
    Mu = qu * b * cant ** 2 / 2
    a = As * fy / (0.85 * fc * b)
    c = a / _beta1(fc)
    eps_t = 0.003 * (d - c) / c
    if eps_t < fy / 29.0e6 + 0.003:
        raise FootingInputError("footing: the section is not tension controlled; "
                                "Table 21.2.2 transition is not built yet")
    Mn = As * fy * (d - a / 2)
    checks.append(Check("flexure", Mu / 12, 0.90 * Mn / 12, "lb-ft/ft", strength_combo,
                        "ACI 318-19 13.2.7.1, 22.2.2.4.1; phi = 0.90 (Table 21.2.2)",
                        f"projection {cant:.2f} in; a = {a:.3f} in; d = {d:.2f} in; "
                        f"eps_t = {eps_t:.4f}"))
    checks.append(Check("minimum reinforcement, transverse", 0.0018 * b * h_in, As, "in^2/ft", "-",
                        "ACI 318-19 7.6.1.1: As,min = 0.0018 Ag",
                        "demand is the required area, capacity is the area provided"))
    checks.append(Check("minimum reinforcement, longitudinal", 0.0018 * W * h_in,
                        n_l * BAR_AREA[bar_l], "in^2", "-",
                        "ACI 318-19 24.4.3.2 (shrinkage and temperature): 0.0018 Ag",
                        "demand is the required area, capacity is the area provided"))
    val = dict(W_ftg=W_ftg, W_stem=W_stem, W_soil=W_soil, qu_psf=qu * 144, d=d, As=As, Pu_plf=Pu)
    return FootingResult(checks, val, notes)
