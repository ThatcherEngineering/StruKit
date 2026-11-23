"""Sawn dimension lumber in bending: 2018 NDS (ANSI/AWC NDS-2018) and its Supplement.

Read from the documents:
  NDS Table 2.3.2          load duration factor CD
  NDS 3.3.2, 3.3.3         bending; beam stability factor CL (Table 3.3.3 note 1 for the
                           effective length; Eq. 3.3-5, 3.3-6; FbE = 1.20 Emin' / RB^2)
  NDS 3.4.2                shear parallel to grain, fv = 3V / (2bd)
  NDS 3.10.2, 3.10.4       bearing perpendicular to grain
  NDS Table 4.3.1          which adjustment factors apply to sawn lumber
  NDS 4.3.8, Table 4.3.8   incising factor Ci
  NDS 4.3.9                repetitive member factor Cr
  Supplement Table 1B      dressed (S4S) sizes; A, S, I are computed from them
  Supplement Table 4A      reference design values, and its adjustment factors
                           (size factor CF, wet service factor CM)

Covered: visually graded dimension lumber 2 to 4 in. thick (Table 4A), loaded on its
narrow face, allowable stress design. Not covered: Southern Pine (Table 4B), timbers
(Table 4D), glued laminated timber, LRFD, flat use, notches, temperatures above 100 F.

Units: lb, in, psi.
"""
import csv
import math
import os
from dataclasses import dataclass

_DATA = os.path.join(os.path.dirname(__file__), "data")
SUPP = "2018 NDS Supplement"


class WoodError(ValueError):
    pass


def _load():
    vals, secs = {}, {}
    with open(os.path.join(_DATA, "nds2018_table4a.csv"), newline="") as f:
        for r in csv.DictReader(f):
            vals[(r["species"], r["grade"])] = {k: float(r[k]) for k in ("Fb", "Ft", "Fv", "Fc_perp", "Fc", "E", "Emin")}
    with open(os.path.join(_DATA, "nds2018_table1b.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["group"] == "dimension":
                secs[r["nominal"]] = (float(r["b"]), float(r["d"]))
    return vals, secs


VALUES, SIZES = _load()
SPECIES = sorted({k[0] for k in VALUES})

# NDS Table 2.3.2: load case -> (CD, duration)
CD = {"D": (0.9, "permanent"), "L": (1.0, "ten years"), "S": (1.15, "two months"), "Lr": (1.25, "seven days"),
      "W": (1.6, "ten minutes"), "E": (1.6, "ten minutes")}

_MAIN = ("Select Structural", "No. 1 & Btr", "No. 1", "No. 2", "No. 3", "No. 1/ No. 2")
# Table 4A size factors for Fb: nominal width -> (2 and 3 in. thick, 4 in. thick)
_CF_MAIN = {2: (1.5, 1.5), 3: (1.5, 1.5), 4: (1.5, 1.5), 5: (1.4, 1.4), 6: (1.3, 1.3), 8: (1.2, 1.3), 10: (1.1, 1.2),
            12: (1.0, 1.1), 14: (0.9, 1.0), 16: (0.9, 1.0)}


def grades(species):
    return [g for (s, g) in VALUES if s == species]


def nominal(size):
    t, w = size.lower().replace(" ", "").split("x")
    return int(t), int(w)


def values(species, grade, size):
    """Reference design values and the Fb size factor for a species, grade and nominal size.
    A Stud 8 in. and wider takes the No. 3 values and factors (Table 4A adjustment factors)."""
    if (species, grade) not in VALUES:
        raise WoodError(f"wood: {species} {grade} is not in {SUPP} Table 4A")
    if size not in SIZES:
        raise WoodError(f"wood: {size} is not a dimension lumber size in {SUPP} Table 1B")
    t, w = nominal(size)
    col = 1 if t == 4 else 0
    note = ""
    if grade == "Stud" and w >= 8:
        if (species, "No. 3") not in VALUES:
            raise WoodError(f"wood: a Stud {w} in. wide uses No. 3 values, which {species} does not list")
        grade, note = "No. 3", "Stud 8 in. and wider: No. 3 values and size factors"
    if grade in _MAIN:
        CF = _CF_MAIN[w][col]
    elif grade == "Stud":
        CF = 1.1 if w <= 4 else 1.0
    elif grade in ("Construction", "Standard"):
        if w > 4:
            raise WoodError(f"wood: {grade} grade is for members 2 to 4 in. wide")
        CF = 1.0
    elif grade == "Utility":
        if w == 4:
            CF = 1.0
        elif w in (2, 3) and t in (2, 3):
            CF = 0.4
        else:
            raise WoodError("wood: Utility grade size is outside the Table 4A size factors")
    else:
        raise WoodError(f"wood: no size factor rule for grade {grade}")
    return dict(VALUES[(species, grade)]), CF, note


def load_duration(cases):
    """CD for a combination: the factor of its shortest-duration load (NDS 2.3.2, Table 2.3.2)."""
    unknown = sorted(c for c in cases if c not in CD)
    if unknown:
        raise WoodError("wood: no load duration factor in NDS Table 2.3.2 for load case " + ", ".join(unknown))
    c = max(cases, key=lambda k: CD[k][0])
    return CD[c][0], c, CD[c][1]


def effective_length(lu, d):
    """NDS Table 3.3.3, note 1 (loading conditions not listed in the table)."""
    r = lu / d
    if r < 7:
        return 2.06 * lu
    if r <= 14.3:
        return 1.63 * lu + 3 * d
    return 1.84 * lu


def beam_stability(Fb_star, Emin_adj, lu, b, d):
    """CL by NDS Eq. 3.3-6. Returns (CL, detail). lu = 0 means the compression edge is
    supported throughout (3.3.3.3)."""
    if d <= b or lu <= 0:
        return 1.0, dict(why="depth does not exceed breadth (3.3.3.1)" if d <= b else
                         "compression edge supported throughout its length (3.3.3.3)")
    le = effective_length(lu, d)
    RB = math.sqrt(le * d / b ** 2)
    if RB > 50:
        raise WoodError(f"wood: slenderness ratio RB = {RB:.1f} exceeds 50 (NDS 3.3.3.7)")
    FbE = 1.20 * Emin_adj / RB ** 2
    a = FbE / Fb_star
    CL = (1 + a) / 1.9 - math.sqrt(((1 + a) / 1.9) ** 2 - a / 0.95)
    return CL, dict(le=le, RB=RB, FbE=FbE)


@dataclass
class Factors:
    CM_b: float
    CM_v: float
    CM_perp: float
    CM_E: float
    Ci_b: float
    Ci_E: float
    Cr: float


def factors(Fb, CF, wet, incised, repetitive):
    """Wet service (Table 4A adjustment factors), incising (NDS Table 4.3.8) and repetitive
    member (NDS 4.3.9) factors. Temperature factor Ct = 1.0 (NDS 2.3.3, to 100 F)."""
    CM_b = (1.0 if Fb * CF <= 1150 else 0.85) if wet else 1.0
    return Factors(CM_b, 0.97 if wet else 1.0, 0.67 if wet else 1.0, 0.9 if wet else 1.0,
                   0.80 if incised else 1.0, 0.95 if incised else 1.0, 1.15 if repetitive else 1.0)
