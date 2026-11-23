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

  NDS 3.6, 3.7             columns; column stability factor CP (Eq. 3.7-1, c = 0.8 for sawn
                           lumber, FcE = 0.822 Emin' / (le/d)^2, le/d not over 50)
  Supplement Table 4D      timbers 5 x 5 and larger, and its wet service factors. 29 species
                           are in StruKit's file: those whose Beams and Stringers and Posts
                           and Timbers rows both read cleanly from the table text, each
                           group confirmed by its printed classification label. Left out:
                           Alaska Cedar, Baldcypress, Hem-Fir (North), Mixed Oak, Redwood,
                           Sitka Spruce, Spruce-Pine-Fir (South), Western Juniper, and
                           Southern Pine.

Covered: visually graded dimension lumber 2 to 4 in. thick (Table 4A) as beams and posts,
and timbers (Table 4D) as posts, allowable stress design. Not covered: Southern Pine
(Table 4B), glued laminated timber, LRFD, flat use, notches, built-up columns (NDS 15.3),
temperatures above 100 F.

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


def _load_timbers():
    vals, secs = {}, {}
    with open(os.path.join(_DATA, "nds2018_table4d.csv"), newline="") as f:
        for r in csv.DictReader(f):
            vals[(r["species"], r["classification"], r["grade"])] = {k: float(r[k]) for k in ("Fb", "Ft", "Fv", "Fc_perp", "Fc", "E", "Emin")}
    with open(os.path.join(_DATA, "nds2018_table1b.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["group"] == "post and timber":
                secs[r["nominal"]] = (float(r["b"]), float(r["d"]))
    return vals, secs


TIMBER_VALUES, TIMBER_SIZES = _load_timbers()
TIMBER_SPECIES = sorted({k[0] for k in TIMBER_VALUES})
# Table 4A size factors for Fc: nominal width -> factor (Select Structural to No. 3)
_CF_C_MAIN = {2: 1.15, 3: 1.15, 4: 1.15, 5: 1.1, 6: 1.1, 8: 1.05, 10: 1.0, 12: 1.0, 14: 0.9, 16: 0.9}
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


def timber_class(b, d):
    """NDS 4.1.3: Beams and Stringers are 5 in. or more thick with the width more than 2 in.
    greater than the thickness; Posts and Timbers are 5 x 5 and larger with the width not
    more than 2 in. greater than the thickness (nominal dimensions)."""
    return "Beams and Stringers" if abs(d - b) > 2 else "Posts and Timbers"


def post_values(species, grade, size):
    """Reference design values, the Fc size factor, and the table used, for a solid post:
    dimension lumber (Table 4A) or a timber (Table 4D)."""
    if size in SIZES:
        ref, _, note = values(species, grade, size)
        t, w = nominal(size)
        g = "No. 3" if (grade == "Stud" and w >= 8) else grade
        if g in _MAIN:
            CF = _CF_C_MAIN[w]
        elif g == "Stud":
            CF = 1.05 if w <= 4 else 1.0
        elif g in ("Construction", "Standard"):
            CF = 1.0
        else:                                              # Utility
            CF = 1.0 if w == 4 else 0.6
        return ref, CF, SIZES[size], "Table 4A", note
    if size in TIMBER_SIZES:
        t, w = nominal(size)
        cls = timber_class(t, w)
        if (species, cls, grade) not in TIMBER_VALUES:
            raise WoodError(f"wood: {species} {grade} {cls} is not in StruKit's {SUPP} Table 4D file")
        return dict(TIMBER_VALUES[(species, cls, grade)]), 1.0, TIMBER_SIZES[size], "Table 4D, " + cls, ""
    raise WoodError(f"wood: {size} is not a size in {SUPP} Table 1B")


def column_stability(Fc_star, Emin_adj, le1, d1, le2, d2):
    """CP by NDS Eq. 3.7-1 for a solid rectangular sawn lumber column (c = 0.8). le1/d1 and
    le2/d2 are the two slenderness ratios; the larger governs (3.7.1.3)."""
    r = max(le1 / d1, le2 / d2)
    if r > 50:
        raise WoodError(f"wood: slenderness ratio le/d = {r:.1f} exceeds 50 (NDS 3.7.1.4)")
    if r <= 0:
        return 1.0, dict(ratio=0.0, FcE=float("inf"))
    FcE = 0.822 * Emin_adj / r ** 2
    a, c = FcE / Fc_star, 0.8
    CP = (1 + a) / (2 * c) - math.sqrt(((1 + a) / (2 * c)) ** 2 - a / c)
    return CP, dict(ratio=r, FcE=FcE)
