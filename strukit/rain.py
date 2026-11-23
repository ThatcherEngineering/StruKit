"""Rain loads, ASCE/SEI 7-22 Chapter 8, with the hydraulic head of a channel scupper and the
ponding head by amplified first-order analysis from AISC Design Guide 40 (Rain Loads and
Ponding).

    R = 5.2 (ds + dh + dp)                      ASCE/SEI 7-22 Eq. 8.2-1, psf with heads in inches
    Q = 0.0104 A i                              ASCE/SEI 7-22 Eq. C8.2-1 (Design Guide 40 Eq. 1-6), gal/min
    dh = [3.85 Q / ((2/3) cd Ws sqrt(2 g))]^(2/3)     Design Guide 40 Eq. 1-7, channel scupper, cd = 0.6
    Bp = 1 / (1 - 1.15 Cp - Cs)                 Design Guide 40 Eq. 3-1
    Cp = 32 Ls Lp^4 / (10^7 Ip), Cs = 32 S Ls^4 / (10^7 Is)        Eq. 3-4, 3-5 (steel)
    Cp = gamma Ls Lp^4 / (pi^4 E Ip), Cs = gamma S Ls^4 / (pi^4 E Is)   Eq. 3-2, 3-3 (any E)
"""
import math

GAMMA = 5.2                      # psf per inch of water, Eq. 8.2-1
GAMMA_PCF = 62.4
RETURN_PERIOD = {"I": 100, "II": 100, "III": 200, "IV": 500}      # Table 8.2-1, years; 15 minute duration
CD_SCUPPER = 0.6
G_IN = 386.0                     # in./s2, as Design Guide 40 Example 2
# stiffness used in the ponding analysis, Design Guide 40 Sect. 2 (pdf p. 21): name -> (factor on I, note)
STIFFNESS = {"structural steel member": (0.8, "0.8 I, Design Guide 40 Ch. 2"),
             "open web steel joist or joist girder": (1 / 1.15, "I / 1.15, Design Guide 40 Ch. 2"),
             "effective moment of inertia entered": (1.0, "as entered")}


class RainError(ValueError):
    pass


def flow(A, i):
    if A is None or A <= 0 or i is None or i <= 0:
        raise RainError("rain: the tributary area and the rainfall intensity must be positive")
    return 0.0104 * A * i


def scupper_head(Q, Ws):
    """Hydraulic head (in.) at a channel scupper Ws inches wide passing Q gal/min."""
    if Ws is None or Ws <= 0:
        raise RainError("rain: the scupper width must be positive")
    return (3.85 * Q / ((2.0 / 3.0) * CD_SCUPPER * Ws * math.sqrt(2 * G_IN))) ** (2.0 / 3.0)


def flexibility(Lp, Ls, S, Ip, Is, Ep=None, Es=None):
    """Flexibility coefficients of a rectangular bay: Lp, Ls, S in ft; Ip, Is in in4 (the
    values used in the analysis); Ep, Es in psi, None = steel by Eq. 3-4 and 3-5."""
    for nm, v in (("the primary member span", Lp), ("the secondary member span", Ls), ("the secondary member spacing", S),
                  ("the primary member moment of inertia", Ip), ("the secondary member moment of inertia", Is)):
        if v is None or v <= 0:
            raise RainError(f"rain: {nm} must be positive")
    kp = 32e-7 if Ep is None else GAMMA_PCF * 144.0 / (math.pi ** 4 * Ep)
    ks = 32e-7 if Es is None else GAMMA_PCF * 144.0 / (math.pi ** 4 * Es)
    return kp * Ls * Lp ** 4 / Ip, ks * S * Ls ** 4 / Is


def amplification(Cp, Cs):
    den = 1.0 - 1.15 * Cp - Cs
    if den <= 0:
        raise RainError(f"rain: the bay is not stiff enough to avoid ponding instability (1.15 Cp + Cs = {1.15 * Cp + Cs:.2f}, 1.0 or more)")
    return 1.0 / den


def rain_load(ds, dh, dp=0.0):
    for nm, v in (("the static head", ds), ("the hydraulic head", dh), ("the ponding head", dp)):
        if v is None or v < 0:
            raise RainError(f"rain: {nm} is zero or more")
    return GAMMA * (ds + dh + dp)


def ponded(D, ds, dh, Cp, Cs):
    """Rain load with the ponding head by amplified first-order analysis: the uniform load
    without ponding, D + 5.2 (ds + dh), is multiplied by Bp; the dead load is then taken out."""
    if D is None or D < 0:
        raise RainError("rain: the dead load is zero or more")
    Bp = amplification(Cp, Cs)
    w0 = D + rain_load(ds, dh)
    R = Bp * w0 - D
    return dict(Bp=Bp, w0=w0, total=Bp * w0, R=R, dp=R / GAMMA - ds - dh)


LOW_SLOPE = 0.25                 # in. per ft, Sect. 8.3 condition 1


def low_slope(slope, Ls=None, S=None, parallel_edge=False):
    """ASCE/SEI 7-22 Sect. 8.3 screening of a free-draining bay or an internal bay without
    accumulated rain: slope in in. per ft; parallel_edge: the bay is beside a free-draining edge
    with its secondary members parallel to that edge, then beta = (Ls/S + pi)/20 in. per ft
    (Ls, S in the same units). Returns dict(beta, cond1, cond2, investigate)."""
    if slope is None or slope < 0:
        raise RainError("rain: the roof slope is zero or more")
    beta = None
    if parallel_edge:
        if Ls is None or S is None or Ls <= 0 or S <= 0:
            raise RainError("rain: the span and spacing of the secondary members are needed for the Sect. 8.3 slope limit")
        beta = (Ls / S + math.pi) / 20.0
    c1 = slope < LOW_SLOPE
    c2 = beta is not None and slope < beta
    return dict(beta=beta, cond1=c1, cond2=c2, investigate=c1 or c2)
