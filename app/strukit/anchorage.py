"""Cast-in headed anchor rods in concrete: ACI 318-19 Chapter 17.

Source on file: ACI 318-19 (code pages 233 to 272). Every factor and equation below was
read from that document:
  Table 17.5.3(a), (b), (c)   strength reduction factors
  17.6.1  steel in tension, Eq. 17.6.1.2; Ase,N per R17.6.1.2 (ASME B1.1 formula)
  17.6.2  concrete breakout in tension, Eq. 17.6.2.1a/b, 17.6.2.1.4, 17.6.2.2.1,
          17.6.2.2.3, 17.6.2.4.1, 17.6.2.5.1, and the narrow-member rule 17.6.2.1.2
  17.6.3  pullout, Eq. 17.6.3.1 and 17.6.3.2.2a
  17.6.4  side-face blowout, Eq. 17.6.4.1, 17.6.4.1.1, 17.6.4.2
  17.7.1  steel in shear, Eq. 17.7.1.2b, and 17.7.1.2.1 for grout pads
  17.7.2  concrete breakout in shear, Eq. 17.7.2.1a/b, (c) for shear parallel to an edge,
          17.7.2.1.2, 17.7.2.1.3, 17.7.2.2.1, 17.7.2.4.1, 17.7.2.5.1, 17.7.2.6.1, and the
          load-distribution cases of Fig. R17.7.2.1b
  17.7.3  pryout, Eq. 17.7.3.1b
  17.8    tension and shear interaction, Eq. 17.8.3
  17.9.2  minimum spacing, Table 17.9.2(a)
  Table 17.5.1.3.1            critical spacing for group action
  Table 17.2.4.1              lambda_a = 1.0 lambda for cast-in anchors

Layout covered: two rows of rods, n rods in each row, on a rectangular concrete support
with the pattern centred on it. Moment and shear act across the rows: one row is in
tension, and the shear pushes toward one end of the support.

Not covered: lightweight concrete, hooked (J or L) bolts, post-installed anchors,
anchor reinforcement (17.5.2.1), Seismic Design Category C to F (17.10), shear lugs
(17.11), all rods in tension, and edge cover (17.9.2 refers to 20.5.1.3).

Units: inches, kips, psi for f'c, ksi for steel. Strength design (factored loads) only.
"""
import math
from dataclasses import dataclass, field

from .steel_beam import Line


class AnchorageError(ValueError):
    pass


@dataclass
class Mode:
    key: str
    label: str
    kind: str                    # "tension" or "shear"
    phi: float
    Rn: float                    # nominal strength, kips
    share: float                 # part of the total row tension, or of the base shear, on this check
    source: str
    note: str = ""

    @property
    def design(self):
        return self.phi * self.Rn


@dataclass
class Anchorage:
    modes: list
    lines: list
    notes: list = field(default_factory=list)
    geom: dict = field(default_factory=dict)


def ase(da, nt):
    """Effective area of a threaded rod, ACI 318-19 R17.6.1.2 and R17.7.1.2 (ASME B1.1)."""
    return math.pi / 4 * (da - 0.9743 / nt) ** 2


def hex_bearing_area(F, da):
    """Net bearing area of a hex head or nut: the hexagon (0.866 F^2, geometry) less the
    rod's gross area."""
    return math.sqrt(3) / 2 * F * F - math.pi / 4 * da * da


def _rootfc(fc):
    return math.sqrt(fc)


def tension_breakout(hef, fc, nx, sx, ny, sy, cx1, cx2, cy1, cy2, psi_c, deep_eq_for_groups=False):
    """Ncbg (lb) of an nx by ny rectangle of rods acting as one group. cx1, cx2, cy1, cy2:
    edge distances from the outer rods. Returns (N, detail dict).
    deep_eq_for_groups: use Eq. 17.6.2.2.3 for a group with 11 to 25 in. embedment. The Code
    words that equation for a single anchor; AISC Design Guide 1 (3rd Ed.) Example 4.7-11
    uses it for a row of two rods. Off by default: Zach ruled 2026-11-23 to use the more
    conservative (lower) value. detail["alt"] carries
    the value the other reading gives."""
    close = [c for c in (cx1, cx2, cy1, cy2) if c < 1.5 * hef]
    h = hef
    if len(close) >= 3:                                   # 17.6.2.1.2
        smax = max(sx if nx > 1 else 0.0, sy if ny > 1 else 0.0)
        h = min(hef, max(max(close) / 1.5, smax / 3))
    n = nx * ny
    A = (min(cx1, 1.5 * h) + (nx - 1) * sx + min(cx2, 1.5 * h)) * (min(cy1, 1.5 * h) + (ny - 1) * sy + min(cy2, 1.5 * h))
    Aco = 9 * h * h                                       # Eq. 17.6.2.1.4
    A = min(A, n * Aco)                                   # 17.6.2.1.1
    cmin = min(cx1, cx2, cy1, cy2)
    psi_ed = 1.0 if cmin >= 1.5 * h else 0.7 + 0.3 * cmin / (1.5 * h)      # Eq. 17.6.2.4.1
    Nb1, Nb3 = 24 * _rootfc(fc) * h ** 1.5, 16 * _rootfc(fc) * h ** (5 / 3)
    deep = 11 <= h <= 25
    if deep and (n == 1 or deep_eq_for_groups):
        Nb, eq = Nb3, "Eq. 17.6.2.2.3"
    else:
        Nb, eq = Nb1, "Eq. 17.6.2.2.1, kc = 24"
    N = A / Aco * psi_ed * psi_c * Nb
    alt = A / Aco * psi_ed * psi_c * Nb3 if (deep and eq.endswith("kc = 24")) else None
    return N, dict(hef=h, ANc=A, ANco=Aco, psi_ed=psi_ed, Nb=Nb, eq=eq, n=n, alt=alt)


def shear_breakout(ca1, n, s, c2a, c2b, ha, da, hef, fc, psi_c, parallel=False):
    """Vcbg (lb) of n rods in a line at ca1 from the edge the shear acts toward (or along,
    when parallel), spacing s along that edge, c2a and c2b from the line's ends to the
    side edges."""
    c1 = ca1
    if max(c2a, c2b) < 1.5 * ca1 and ha < 1.5 * ca1:      # 17.7.2.1.2
        c1 = min(ca1, max(max(c2a, c2b) / 1.5, ha / 1.5, s / 3 if n > 1 else 0.0))
    Aco = 4.5 * c1 * c1                                   # Eq. 17.7.2.1.3
    A = (min(c2a, 1.5 * c1) + (n - 1) * s + min(c2b, 1.5 * c1)) * min(ha, 1.5 * c1)
    A = min(A, n * Aco)                                   # 17.7.2.1.1
    le = min(hef, 8 * da)                                 # 17.7.2.2.1
    Vb = min(7 * (le / da) ** 0.2 * math.sqrt(da) * _rootfc(fc) * c1 ** 1.5, 9 * _rootfc(fc) * c1 ** 1.5)
    cmin = min(c2a, c2b)
    psi_ed = 1.0 if (parallel or cmin >= 1.5 * c1) else 0.7 + 0.3 * cmin / (1.5 * c1)   # Eq. 17.7.2.4.1
    psi_h = math.sqrt(1.5 * c1 / ha) if ha < 1.5 * c1 else 1.0                            # Eq. 17.7.2.6.1
    V = A / Aco * psi_ed * psi_c * psi_h * Vb * (2.0 if parallel else 1.0)                # 17.7.2.1(c)
    return V, dict(ca1=c1, AVc=A, AVco=Aco, psi_ed=psi_ed, psi_h=psi_h, Vb=Vb)


def check(da, nt, futa, fya, ductile, hef, Abrg, fc, ha, n, s_row, s_rows, c_end, c_side,
          cracked, supplementary, edge_reinf, grout, rows_in_shear):
    """Design strengths of the rod pattern.

    da: rod diameter; nt: threads per inch; futa, fya: rod tensile and yield strength (ksi);
    ductile: the rod is a ductile steel element (ACI 318-19 Chapter 2); hef: embedment to
    the bearing face of the head; Abrg: net bearing area of the head (in2); fc: psi;
    ha: concrete thickness; n: rods in each row; s_row: spacing of the rods within a row;
    s_rows: distance between the two rows; c_end: from a row to the nearer end of the
    concrete (the edge the moment and shear act toward); c_side: from the outer rods to the
    sides of the concrete; cracked: cracking at service load at the rods; supplementary:
    supplementary reinforcement present (Table 17.5.3(b)); edge_reinf: 0 none or smaller
    than No. 4, 1 a No. 4 bar or larger between the rods and the edge, 2 the same enclosed
    in stirrups at 4 in. or less (Table 17.7.2.5.1); grout: built-up grout pad under the
    plate; rows_in_shear: 0, 1 or 2 rows of rods counted on for shear."""
    for nm, v in (("rod diameter", da), ("threads per inch", nt), ("rod Fu", futa), ("rod Fy", fya),
                  ("embedment hef", hef), ("head bearing area", Abrg), ("f'c", fc), ("concrete thickness", ha),
                  ("row spacing", s_rows), ("end distance", c_end), ("side distance", c_side)):
        if v is None or v <= 0:
            raise AnchorageError(f"anchorage: {nm} must be a positive number")
    if n < 1 or (n > 1 and s_row <= 0):
        raise AnchorageError("anchorage: the rods in a row need a spacing")
    if rows_in_shear not in (0, 1, 2):
        raise AnchorageError("anchorage: the rods counted on for shear must be none, one row, or both rows")
    if edge_reinf not in (0, 1, 2):
        raise AnchorageError("anchorage: edge reinforcement must be 0, 1 or 2")
    if da > 4:
        raise AnchorageError("anchorage: rods larger than 4 in. are outside ACI 318-19 17.3.2")
    if fc > 10000:
        raise AnchorageError("anchorage: f'c above 10,000 psi is outside ACI 318-19 17.3.1")
    if hef >= ha:
        raise AnchorageError("anchorage: the embedment is not less than the concrete thickness")
    fu = min(futa, 1.9 * fya, 125.0)                      # 17.6.1.2
    A_se = ase(da, nt)
    if A_se <= 0:
        raise AnchorageError("anchorage: threads per inch gives no rod area")
    phi_ts, phi_vs = (0.75, 0.65) if ductile else (0.65, 0.60)          # Table 17.5.3(a)
    phi_c = 0.75 if supplementary else 0.70                              # Table 17.5.3(b), cast-in
    phi_p = 0.70                                                         # Table 17.5.3(c), cast-in
    psi_cN = 1.0 if cracked else 1.25                                    # 17.6.2.5.1
    psi_cP = 1.0 if cracked else 1.4                                     # 17.6.3.3.1
    psi_cV = (1.0, 1.2, 1.4)[edge_reinf] if cracked else 1.4             # 17.7.2.5.1
    c_far = c_end + s_rows                                # the far row to the same end
    L = [Line("Ase = pi/4 (da - 0.9743/nt)^2", A_se, "in2", "ACI 318-19 R17.6.1.2"),
         Line("futa used", fu, "ksi", "17.6.1.2", "not more than 1.9 fya or 125 ksi"),
         Line("Abrg", Abrg, "in2", "head bearing area"),
         Line("row to the end of the concrete, c_end", c_end, "in", "geometry"),
         Line("outer rods to the sides, c_side", c_side, "in", "geometry")]
    notes = []
    M = []
    # ---------------------------------------------------------------- tension
    M.append(Mode("Nsa", "rod steel, tension", "tension", phi_ts, A_se * fu, 1.0 / n,
                  "ACI 318-19 Eq. 17.6.1.2; Table 17.5.3(a)", "per rod"))
    L.append(Line("Nsa = Ase futa", A_se * fu, "kip", "Eq. 17.6.1.2", f"phi = {phi_ts:g} ({'ductile' if ductile else 'brittle'} steel)"))
    if n > 1 and s_row >= 3 * hef:                         # Table 17.5.1.3.1: no group action
        N, d = tension_breakout(hef, fc, 1, 0, 1, 0, c_end, c_far, c_side, c_side + (n - 1) * s_row, psi_cN)
        share, who = 1.0 / n, "outer rod alone (rods are 3 hef or more apart)"
    else:
        N, d = tension_breakout(hef, fc, 1, 0, n, s_row, c_end, c_far, c_side, c_side, psi_cN)
        share, who = 1.0, "the row in tension as a group" if n > 1 else "single rod"
    if d["hef"] < hef:
        L.append(Line("hef used for breakout", d["hef"], "in", "17.6.2.1.2", "three or more edges closer than 1.5 hef"))
    L += [Line("ANc", d["ANc"], "in2", "17.6.2.1.1", who), Line("ANco = 9 hef^2", d["ANco"], "in2", "Eq. 17.6.2.1.4"),
          Line("psi_ed,N", d["psi_ed"], "", "Eq. 17.6.2.4.1"), Line("psi_c,N", psi_cN, "", "17.6.2.5.1"),
          Line("Nb", d["Nb"] / 1000, "kip", d["eq"]),
          Line("Ncbg" if d["n"] > 1 else "Ncb", N / 1000, "kip", "Eq. 17.6.2.1b" if d["n"] > 1 else "Eq. 17.6.2.1a",
               f"phi = {phi_c:g}")]
    M.append(Mode("Ncb", "breakout, tension", "tension", phi_c, N / 1000, share,
                  "ACI 318-19 17.6.2; Table 17.5.3(b)", who))
    Np = psi_cP * 8 * Abrg * fc / 1000                    # Eq. 17.6.3.1, 17.6.3.2.2a
    L.append(Line("Npn = psi_c,P 8 Abrg f'c", Np, "kip", "Eq. 17.6.3.1, 17.6.3.2.2a", f"psi_c,P = {psi_cP:g}; phi = {phi_p:g}"))
    M.append(Mode("Npn", "pullout", "tension", phi_p, Np, 1.0 / n,
                  "ACI 318-19 17.6.3; Table 17.5.3(c)", "per rod"))
    # side-face blowout: the end of the concrete (the row lies along it) and the sides
    if hef > 2.5 * c_end:
        Nsb = 160 * c_end * math.sqrt(Abrg) * _rootfc(fc) / 1000          # Eq. 17.6.4.1
        if n > 1 and s_row < 6 * c_end:
            Nsbg = (1 + (n - 1) * s_row / (6 * c_end)) * Nsb              # Eq. 17.6.4.2
            L.append(Line("Nsbg, end of the concrete", Nsbg, "kip", "Eq. 17.6.4.1, 17.6.4.2", f"phi = {phi_c:g}"))
            M.append(Mode("Nsb_end", "side blowout, end", "tension", phi_c, Nsbg, 1.0,
                          "ACI 318-19 17.6.4.2; Table 17.5.3(b)", "the row in tension"))
        else:
            r = min(max(c_side / c_end, 1.0), 3.0)
            f = (1 + r) / 4 if c_side < 3 * c_end else 1.0                # 17.6.4.1.1
            L.append(Line("Nsb, end of the concrete", Nsb * f, "kip", "Eq. 17.6.4.1, 17.6.4.1.1", f"phi = {phi_c:g}"))
            M.append(Mode("Nsb_end", "side blowout, end", "tension", phi_c, Nsb * f, 1.0 / n,
                          "ACI 318-19 17.6.4.1; Table 17.5.3(b)", "per rod"))
    if hef > 2.5 * c_side:
        Nsb = 160 * c_side * math.sqrt(Abrg) * _rootfc(fc) / 1000
        r = min(max(c_end / c_side, 1.0), 3.0)
        f = (1 + r) / 4 if c_end < 3 * c_side else 1.0
        L.append(Line("Nsb, side of the concrete", Nsb * f, "kip", "Eq. 17.6.4.1, 17.6.4.1.1", f"phi = {phi_c:g}"))
        M.append(Mode("Nsb_side", "side blowout, side", "tension", phi_c, Nsb * f, 1.0 / n,
                      "ACI 318-19 17.6.4.1; Table 17.5.3(b)", "outer rod"))
    if hef <= 2.5 * min(c_end, c_side):
        L.append(Line("2.5 x least edge distance", 2.5 * min(c_end, c_side), "in", "17.6.4.1",
                      "not less than hef: side-face blowout does not apply"))
    # ---------------------------------------------------------------- shear
    if rows_in_shear:
        Vsa = 0.6 * A_se * fu * (0.8 if grout else 1.0)                   # Eq. 17.7.1.2b, 17.7.1.2.1
        two = rows_in_shear == 2
        case2 = two and s_rows >= c_end                    # Fig. R17.7.2.1b
        steel_rods = n if (case2 or not two) else 2 * n
        L.append(Line("Vsa = 0.6 Ase futa" + (" x 0.8" if grout else ""), Vsa, "kip",
                      "Eq. 17.7.1.2b" + (", 17.7.1.2.1 (grout pad)" if grout else ""), f"phi = {phi_vs:g}"))
        M.append(Mode("Vsa", "rod steel, shear", "shear", phi_vs, Vsa, 1.0 / steel_rods,
                      "ACI 318-19 Eq. 17.7.1.2b; Table 17.5.3(a)",
                      f"per rod, {steel_rods} rod(s)" + ("; the row farther from the edge alone, to match breakout Case 2 "
                                                         "(17.7.1.1, R17.7.2.1)" if case2 else "")))

        def line_toward(ca1, label, share, case):
            if n > 1 and s_row >= 3 * ca1:                 # Table 17.5.1.3.1: rods act singly
                V, d = shear_breakout(ca1, 1, 0, c_side, c_side + (n - 1) * s_row, ha, da, hef, fc, psi_cV)
                sh, who = share / n, "outer rod alone"
            else:
                V, d = shear_breakout(ca1, n, s_row, c_side, c_side, ha, da, hef, fc, psi_cV)
                sh, who = share, "the row as a group" if n > 1 else "single rod"
            L.extend([Line(f"ca1, {label}", d["ca1"], "in", "17.7.2.1.1" + (", 17.7.2.1.2" if d["ca1"] < ca1 else "")),
                      Line("AVc", d["AVc"], "in2", "17.7.2.1.1", who), Line("AVco = 4.5 ca1^2", d["AVco"], "in2", "Eq. 17.7.2.1.3"),
                      Line("psi_ed,V", d["psi_ed"], "", "Eq. 17.7.2.4.1"), Line("psi_h,V", d["psi_h"], "", "Eq. 17.7.2.6.1"),
                      Line("Vb", d["Vb"] / 1000, "kip", "Eq. 17.7.2.2.1a, b (lesser)"),
                      Line(f"Vcbg, {label}" if n > 1 else f"Vcb, {label}", V / 1000, "kip", "Eq. 17.7.2.1b" if n > 1 else "Eq. 17.7.2.1a",
                           f"psi_c,V = {psi_cV:g}; phi = {phi_c:g}")])
            M.append(Mode("Vcb_" + case, f"shear breakout, {short[case]}", "shear", phi_c, V / 1000, sh,
                          "ACI 318-19 17.7.2; Fig. R17.7.2.1b; Table 17.5.3(b)", who + "; " + case_note[case]))

        short = {"case1": "near row", "case2": "far row", "case3": "near row", "one": "near row"}
        case_note = {"case1": "Case 1: half the shear on the row nearer the edge",
                     "case2": "Case 2: all the shear on the row farther from the edge",
                     "case3": "Case 3: rows closer together than the edge distance, all the shear on the row nearer the edge",
                     "one": "one row counted on; taken as the row nearer the edge"}
        if not two:
            line_toward(c_end, "row nearer the edge", 1.0, "one")
        elif case2:
            line_toward(c_end, "row nearer the edge", 0.5, "case1")
            line_toward(c_far, "row farther from the edge", 1.0, "case2")
        else:
            line_toward(c_end, "row nearer the edge", 1.0, "case3")
        # shear parallel to the sides: the outer rod of each row in shear
        if two and s_rows < 3 * c_side:
            V, d = shear_breakout(c_side, 2, s_rows, c_end, c_end, ha, da, hef, fc, psi_cV, parallel=True)
            sh, who = 1.0 / n, "outer rod of each row, as a group"
        else:
            V, d = shear_breakout(c_side, 1, 0, c_end, c_far, ha, da, hef, fc, psi_cV, parallel=True)
            sh, who = 1.0 / (rows_in_shear * n), "outer rod alone"
        L.append(Line("Vcb, parallel to the side", V / 1000, "kip", "17.7.2.1(c)",
                      f"twice the value for shear toward that edge with psi_ed,V = 1; ca1 = {d['ca1']:.2f} in; {who}"))
        M.append(Mode("Vcb_par", "shear breakout, along side", "shear", phi_c, V / 1000, sh,
                      "ACI 318-19 17.7.2.1(c); Table 17.5.3(b)", who + "; shear parallel to the side edge"))
        # pryout: the rods in shear as a tension-breakout group
        nx = rows_in_shear
        if nx == 2 and s_rows >= 3 * hef:
            nx, share_x, cx2 = 1, 0.5, c_far
        else:
            share_x, cx2 = 1.0, c_end if nx == 2 else c_far
        if n > 1 and s_row >= 3 * hef:
            N, d = tension_breakout(hef, fc, nx, s_rows, 1, 0, c_end, cx2, c_side, c_side + (n - 1) * s_row, psi_cN)
            share = share_x / n
        else:
            N, d = tension_breakout(hef, fc, nx, s_rows, n, s_row, c_end, cx2, c_side, c_side, psi_cN)
            share = share_x
        kcp = 1.0 if hef < 2.5 else 2.0                    # 17.7.3.1
        L.append(Line("Vcpg = kcp Ncbg", kcp * N / 1000, "kip", "Eq. 17.7.3.1b, 17.7.3.1.2",
                      f"kcp = {kcp:g}; Ncbg of the rods in shear = {N / 1000:.2f} kip; phi = {phi_p:g}"))
        M.append(Mode("Vcp", "pryout", "shear", phi_p, kcp * N / 1000, share,
                      "ACI 318-19 17.7.3; Table 17.5.3(c)", "the rods counted on for shear"))
    return Anchorage(M, L, notes, dict(c_end=c_end, c_side=c_side, c_far=c_far, min_spacing=4 * da))


def demands(a, T_row, V):
    """Demand over design strength for every mode. T_row: factored tension in the whole
    tension row; V: factored base shear. Returns (list of (mode, demand, ratio),
    interaction sum or None, governing tension ratio, governing shear ratio). Interaction per 17.8: neglected when either governing
    ratio is 0.2 or less, otherwise Nua/phiNn + Vua/phiVn <= 1.2 (reported over 1.2)."""
    out = []
    rt = rv = 0.0
    for m in a.modes:
        dem = (T_row if m.kind == "tension" else abs(V)) * m.share
        ratio = dem / m.design
        out.append((m, dem, ratio))
        if m.kind == "tension":
            rt = max(rt, ratio)
        else:
            rv = max(rv, ratio)
    inter = (rt + rv) if (rt > 0.2 and rv > 0.2) else None
    return out, inter, rt, rv


def tension_grid(da, nt, futa, fya, ductile, hef, Abrg, fc, ha, nx, sx, ny, sy, cx1, cx2, cy1, cy2, cracked, supplementary, runs,
                 deep_eq_for_groups=False):
    """Rods of an nx by ny grid all able to take tension (a base plate in uplift, or the rods of a plate under biaxial moment), ACI 318-19
    17.6, by load case. Spacing sx along x (nx rods), sy along y; cx1 / cx2: from the rods at x = 0 / x = (nx - 1) sx to the concrete edges,
    cy1 / cy2 likewise. runs: [(name, {(i, j): tension kips of the rod at column i, row j})] at factored (LRFD) loads.
    For each run: rod steel and pullout for the most loaded rod; concrete breakout for the rods in tension as a group (the smallest
    rectangle of the grid holding them; eccentricity of their resultant from its centre by Eq. 17.6.2.3.1 about each axis, the product of the
    two, 17.6.2.3.2); side-face blowout of each edge closer than hef / 2.5, for the rods along it (Eq. 17.6.4.1, 17.6.4.1.1, 17.6.4.2).
    Returns dict(rows=[(check, run, demand, design, source, note)], lines=[Line], phi=dict)."""
    for nm, v in (("rod diameter", da), ("threads per inch", nt), ("rod Fu", futa), ("rod Fy", fya), ("embedment hef", hef),
                  ("head bearing area", Abrg), ("f'c", fc), ("concrete thickness", ha)):
        if v is None or v <= 0:
            raise AnchorageError(f"anchorage: {nm} must be a positive number")
    if hef >= ha:
        raise AnchorageError("anchorage: the embedment is not less than the concrete thickness")
    if da > 4 or fc > 10000:
        raise AnchorageError("anchorage: outside ACI 318-19 17.3.1 / 17.3.2 (rod over 4 in. or f'c over 10,000 psi)")
    fu = min(futa, 1.9 * fya, 125.0)
    A_se = ase(da, nt)
    phi_ts = 0.75 if ductile else 0.65
    phi_c = 0.75 if supplementary else 0.70
    phi_p = 0.70
    psi_cN = 1.0 if cracked else 1.25
    psi_cP = 1.0 if cracked else 1.4
    Nsa = A_se * fu
    Npn = psi_cP * 8 * Abrg * fc / 1000.0
    L = [Line("Ase = pi/4 (da - 0.9743/nt)^2", A_se, "in2", "ACI 318-19 R17.6.1.2"),
         Line("Nsa = Ase futa", Nsa, "kip", "Eq. 17.6.1.2", f"futa = {fu:g} ksi (not over 1.9 fya or 125 ksi); phi = {phi_ts:g}"),
         Line("Npn = psi_c,P 8 Abrg f'c", Npn, "kip", "Eq. 17.6.3.1, 17.6.3.2.2a", f"psi_c,P = {psi_cP:g}; phi = {phi_p:g}")]
    best = {}

    def keep(key, check, run, dem, des, src, note):
        if dem <= 0:
            return
        if key not in best or dem / des > best[key][2] / best[key][3]:
            best[key] = (check, run, dem, des, src, note)

    edges = [("x", 0, cx1, cy1, cy2), ("x", nx - 1, cx2, cy1, cy2), ("y", 0, cy1, cx1, cx2), ("y", ny - 1, cy2, cx1, cx2)]
    shown = set()
    for name, T in runs:
        ten = {k: t for k, t in T.items() if t > 1e-9}
        if not ten:
            continue
        tmax = max(ten.values())
        keep("Nsa", "rod steel, tension", name, tmax, phi_ts * Nsa, "ACI 318-19 Eq. 17.6.1.2; Table 17.5.3(a)", "most loaded rod")
        keep("Npn", "pullout", name, tmax, phi_p * Npn, "ACI 318-19 17.6.3; Table 17.5.3(c)", "most loaded rod")
        i0, i1 = min(i for i, _ in ten), max(i for i, _ in ten)
        j0, j1 = min(j for _, j in ten), max(j for _, j in ten)
        Ttot = sum(ten.values())
        xc, yc = (i0 + i1) / 2 * sx, (j0 + j1) / 2 * sy
        ex = abs(sum(t * i * sx for (i, j), t in ten.items()) / Ttot - xc)
        ey = abs(sum(t * j * sy for (i, j), t in ten.items()) / Ttot - yc)
        N, d = tension_breakout(hef, fc, i1 - i0 + 1, sx, j1 - j0 + 1, sy, cx1 + i0 * sx, cx2 + (nx - 1 - i1) * sx,
                                cy1 + j0 * sy, cy2 + (ny - 1 - j1) * sy, psi_cN, deep_eq_for_groups)
        h_ = d["hef"]
        psi_ec = 1.0 / (1 + ex / (1.5 * h_)) * 1.0 / (1 + ey / (1.5 * h_))
        Ncbg = N * psi_ec / 1000.0
        who = f"{len(ten)} rod{'s' if len(ten) > 1 else ''} in tension as a group"
        keep("Ncb", "breakout, tension", name, Ttot, phi_c * Ncbg, "ACI 318-19 17.6.2; Table 17.5.3(b)",
             f"{who}; ANc {d['ANc']:.0f} in2, ANco {d['ANco']:.0f} in2, psi_ec,N {psi_ec:.3f}, psi_ed,N {d['psi_ed']:.3f}, psi_c,N {psi_cN:g}, Nb {d['Nb'] / 1000:.1f} kip ({d['eq']})")
        if ("Ncb", i0, i1, j0, j1) not in shown:
            shown.add(("Ncb", i0, i1, j0, j1))
            L.append(Line(f"Ncbg, {who}", N / 1000.0, "kip", "Eq. 17.6.2.1b, 17.6.2.2.1",
                          f"ANc = {d['ANc']:.0f} in2; ANco = 9 hef^2 = {d['ANco']:.0f} in2; psi_ed,N = {d['psi_ed']:.3f}; psi_c,N = {psi_cN:g}; before psi_ec,N"))
        for ax, idx, c1, c2a, c2b in edges:
            if hef <= 2.5 * c1:
                continue
            along = [k for k in ten if (k[0] if ax == "x" else k[1]) == idx]
            if not along:
                continue
            n_al = (ny if ax == "x" else nx)
            s_al = sy if ax == "x" else sx
            Nsb = 160 * c1 * math.sqrt(Abrg) * _rootfc(fc) / 1000.0
            c2 = min(c2a, c2b)
            f_ = (1 + min(max(c2 / c1, 1.0), 3.0)) / 4 if c2 < 3 * c1 else 1.0
            if n_al > 1 and s_al < 6 * c1:
                Nsbg = (1 + (n_al - 1) * s_al / (6 * c1)) * Nsb
                keep(f"Nsb{ax}{idx}", f"side blowout, edge {c1:g} in. away", name, sum(ten[k] for k in along), phi_c * Nsbg,
                     "ACI 318-19 Eq. 17.6.4.1, 17.6.4.2; Table 17.5.3(b)", f"the {n_al} rods along that edge as a group")
            else:
                keep(f"Nsb{ax}{idx}", f"side blowout, edge {c1:g} in. away", name, max(ten[k] for k in along), phi_c * Nsb * f_,
                     "ACI 318-19 Eq. 17.6.4.1, 17.6.4.1.1; Table 17.5.3(b)", "the rod nearest that edge")
    if min(cx1, cx2, cy1, cy2) * 2.5 >= hef:
        L.append(Line("2.5 x least edge distance", 2.5 * min(cx1, cx2, cy1, cy2), "in", "17.6.4.1", "not less than hef: side-face blowout does not apply"))
    order = ["Nsa", "Ncb", "Npn"] + sorted(k for k in best if k.startswith("Nsb"))
    return dict(rows=[best[k] for k in order if k in best], lines=L, phi=dict(steel=phi_ts, concrete=phi_c, pullout=phi_p))
