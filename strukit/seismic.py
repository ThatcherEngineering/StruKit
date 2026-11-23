"""Seismic base shear and its vertical distribution, ASCE/SEI 7-22 Sect. 12.8, the
equivalent lateral force procedure.

Read from the standard (pdf pp. 185-186; equations and tables confirmed against the page images):
  Eq. 12.8-1     V = Cs W
  Sect. 12.8.1.1, Method 2:
    Eq. 12.8-3   Cs = SDS / (R/Ie)
    Eq. 12.8-4   need not exceed SD1 / [T (R/Ie)] for T <= TL
    Eq. 12.8-5   need not exceed SD1 TL / [T^2 (R/Ie)] for T > TL
    Eq. 12.8-6   not less than 0.044 SDS Ie, and not less than 0.01
    Eq. 12.8-7   where S1 is 0.6 or more, not less than 0.5 S1 / (R/Ie)
  Sect. 12.8.2   T may be taken as Ta; a period from analysis is limited to Cu Ta.
  Table 12.8-1   Cu: SD1 0.4 and over 1.4; 0.3 1.4; 0.2 1.5; 0.15 1.6; 0.1 and under 1.7.
                 For an SD1 between rows the value of the row with the higher SD1 is used
                 (the smaller Cu, which gives the shorter period).
  Eq. 12.8-8     Ta = Ct hn^x, Table 12.8-2: steel moment-resisting frames 0.028, 0.8;
                 concrete moment-resisting frames 0.016, 0.9; steel eccentrically braced
                 frames and steel buckling-restrained braced frames 0.03, 0.75; all other
                 structural systems 0.02, 0.75 (hn in ft).
  Eq. 12.8-12, 12.8-13   Fx = Cvx V, Cvx = wx hx^k / sum(wi hi^k); k = 1 for T of 0.5 s or
                 less, 2 for 2.5 s or more, linear between.
  Eq. 12.8-14    story shear Vx = the sum of the forces at and above the level.
R, Ie, SDS, SD1, S1 and TL are entered with their sources. Not covered: Method 1 (the
multi-period spectrum), the SDS limit of Sect. 12.8.1.3, the Seismic Design Category, the
redundancy factor, vertical seismic load, torsion, drift, P-delta, structural irregularities
and whether this procedure is permitted (Table 12.6-1).
"""

PERIOD = {"steel moment-resisting frame": (0.028, 0.8), "concrete moment-resisting frame": (0.016, 0.9),
          "steel eccentrically braced frame": (0.03, 0.75), "steel buckling-restrained braced frame": (0.03, 0.75),
          "all other structural systems": (0.02, 0.75)}
CU = ((0.4, 1.4), (0.3, 1.4), (0.2, 1.5), (0.15, 1.6), (0.1, 1.7))


class SeismicError(ValueError):
    pass


def cu(SD1):
    for s, c in reversed(CU):              # the first row at or above SD1, from the low end
        if SD1 <= s:
            return c
    return CU[0][1]


def ta(structure, hn):
    if structure not in PERIOD:
        raise SeismicError("seismic: the structure type for the period is one of: " + "; ".join(PERIOD))
    if hn is None or hn <= 0:
        raise SeismicError("seismic: the structural height must be positive")
    Ct, x = PERIOD[structure]
    return Ct * hn ** x, Ct, x


def k_exponent(T):
    return 1.0 if T <= 0.5 else 2.0 if T >= 2.5 else 1.0 + (T - 0.5) / 2.0


def elf(SDS, SD1, S1, TL, R, Ie, structure, hn, levels, T_analysis=None):
    """levels: [(name, weight, height above the base ft)], any order; weight in kips (any
    one unit; forces come out in the same unit). Returns a dict of every step."""
    for nm, v in (("SDS", SDS), ("SD1", SD1), ("S1", S1), ("TL", TL), ("R", R), ("Ie", Ie)):
        if v is None or v < 0 or (v == 0 and nm in ("TL", "R", "Ie")):
            raise SeismicError(f"seismic: {nm} must be positive")
    if not levels:
        raise SeismicError("seismic: enter at least one level with its weight and height")
    for nm, w, h in levels:
        if w is None or w <= 0 or h is None or h <= 0:
            raise SeismicError(f"seismic: level {nm}: the weight and the height must be positive")
        if h > hn + 1e-9:
            raise SeismicError(f"seismic: level {nm} is above the structural height")
    Ta, Ct, x = ta(structure, hn)
    Cu = cu(SD1)
    if T_analysis is None:
        T, T_note = Ta, "T = Ta"
    elif T_analysis > Cu * Ta:
        T, T_note = Cu * Ta, "T from analysis is over Cu Ta; Cu Ta is used"
    else:
        T, T_note = T_analysis, "T from analysis"
    RI = R / Ie
    c3 = SDS / RI
    cap = SD1 / (T * RI) if T <= TL else SD1 * TL / (T * T * RI)
    cap_eq = "Eq. 12.8-4" if T <= TL else "Eq. 12.8-5"
    c6 = max(0.044 * SDS * Ie, 0.01)
    c7 = 0.5 * S1 / RI if S1 >= 0.6 else None
    Cs, governs = c3, "Eq. 12.8-3"
    if cap < Cs:
        Cs, governs = cap, cap_eq
    if c6 > Cs:
        Cs, governs = c6, "Eq. 12.8-6"
    if c7 is not None and c7 > Cs:
        Cs, governs = c7, "Eq. 12.8-7"
    W = sum(w for _, w, _ in levels)
    V = Cs * W
    k = k_exponent(T)
    lv = sorted(levels, key=lambda r: -r[2])
    den = sum(w * h ** k for _, w, h in lv)
    rows, shear = [], 0.0
    for nm, w, h in lv:
        cvx = w * h ** k / den
        F = cvx * V
        shear += F
        rows.append(dict(name=nm, w=w, h=h, whk=w * h ** k, Cvx=cvx, F=F, V=shear))
    for i, r in enumerate(rows):               # overturning moment at each level: forces above times their height over it
        r["M"] = sum(q["F"] * (q["h"] - r["h"]) for q in rows[:i + 1])
    M_base = sum(r["F"] * r["h"] for r in rows)
    return dict(Ta=Ta, Ct=Ct, x=x, Cu=Cu, T=T, T_note=T_note, R_over_Ie=RI, Cs_123=c3, Cs_cap=cap, cap_eq=cap_eq, Cs_min=c6, Cs_s1=c7,
                Cs=Cs, governs=governs, W=W, V=V, k=k, rows=rows, M_base=M_base)
