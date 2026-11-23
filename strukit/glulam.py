"""Structural glued laminated timber beams, 2018 NDS Chapter 5 and Supplement Table 5A.

Read from the standard:
  Table 5A   stress classes, members stressed primarily in bending, 4 or more laminations
             (values typed from the table); 24F-V4 DF/DF from Table 5A Expanded
  Table 5A adjustment factors: CV = (21/L)^(1/x) (12/d)^(1/x) (5.125/b)^(1/x), not more
             than 1.0; x = 20 for Southern Pine, 10 for other species; L = length between
             points of zero moment, ft; wet service factors Fb 0.8, Fv 0.875, Fc_perp 0.53,
             E and Emin 0.833 (moisture content 16 percent or more)
  5.3.6      CV and CL do not apply together; the lesser applies
  5.2.7      Ex for deflection about the x-x axis; Ey min for stability of members
             buckling about the y-y axis (lateral buckling of a beam bent about x-x)
  5.3.10     shear reduction factor Cvr = 0.72 for non-prismatic or notched members,
             members subject to impact or repetitive cyclic loading, and design at
             connections; 1.0 otherwise

Covered: straight prismatic beams, simply supported, bent about the x-x axis with the
tension laminations at the bottom, not notched. Table 5A note 3 (Southern Pine shear
increase) is not taken.
"""


class GlulamError(ValueError):
    pass


SOURCE = "2018 NDS Supplement Table 5A"
# class: Fbx+, Fbx-, Fc_perp x, Fvx, Ex app, Ey min, southern pine only
CLASSES = {
    "16F-1.3E": (1600, 925, 315, 195, 1.3e6, 0.58e6, False),
    "20F-1.5E": (2000, 1100, 425, 195, 1.5e6, 0.63e6, False),
    "24F-1.7E": (2400, 1450, 500, 210, 1.7e6, 0.69e6, False),
    "24F-1.8E": (2400, 1450, 650, 265, 1.8e6, 0.85e6, False),
    "26F-1.9E": (2600, 1950, 650, 265, 1.9e6, 0.85e6, False),
    "28F-2.1E SP": (2800, 2300, 805, 300, 2.1e6, 0.90e6, True),
    "30F-2.1E SP": (3000, 2400, 805, 300, 2.1e6, 0.90e6, True),
    "24F-V4 DF/DF": (2400, 1850, 650, 265, 1.8e6, 0.85e6, False),
}
WET = dict(Fb=0.8, Fv=0.875, Fc_perp=0.53, E=0.833)


def values(cls):
    if cls not in CLASSES:
        raise GlulamError(f"glulam: '{cls}' is not a stress class of 2018 NDS Supplement Table 5A")
    v = CLASSES[cls]
    return dict(Fb=v[0], Fb_neg=v[1], Fc_perp=v[2], Fv=v[3], E=v[4], Ey_min=v[5], sp_only=v[6],
                source=SOURCE + (" Expanded" if "V4" in cls else ""))


def volume_factor(L_ft, d, b, southern_pine):
    if min(L_ft, d, b) <= 0:
        raise GlulamError("glulam: span, depth and width must be positive")
    x = 20.0 if southern_pine else 10.0
    return min(1.0, (21.0 / L_ft) ** (1 / x) * (12.0 / d) ** (1 / x) * (5.125 / min(b, 10.75)) ** (1 / x))


# ---- Glulam columns: 2018 NDS Supplement Table 5B, NDS 3.7, 15.4 ---------------------------
# Table 5B (members stressed primarily in axial tension or compression), visually graded
# western species, values typed from the table:
#   combination: species, grade, Eaxial min, Fc (4 or more laminations), Fc (2 or 3),
#                Fby (4 or more, 3, 2 laminations), Fbx (2 laminations to 15 in. deep)
# NDS 3.7.1.5: c = 0.9 for glued laminated timber. Table 5B note 4: Fbx as tabulated applies
# to members up to 15 in. deep (deeper members are not covered here).
# Bending from an eccentric load: about the x-x axis (the depth is the stack of
# laminations) Fbx x CV; about the y-y axis (the depth is the lamination width) Fby with no
# flat use increase.
#
# Zach's ruling 2026-11-23 11:57: for Combination 3 columns of a size and length in Boise
# Cascade's column tables (Boise Glulam Specifier Guide GLM-5000, "BOISE GLULAM Column
# Tables", Combination 3 Column Grade; data/glm5000_columns.csv by tools/parse_glm5000.py),
# the axial load is also limited to the table value. The table is written to the 2024 NDS
# with Ke = 1.0, the column braced at its ends only, and an eccentricity of 0.167 times the
# column dimension; it lists 100, 115 and 125 percent load durations. Used here: the longer
# effective length rounded up to a whole foot (the shortest listed length where the column
# is shorter than the table starts); CD 0.9 -> 0.9 x the 100 percent value; CD 1.6 -> the
# 125 percent value.
COLUMNS = {
    "1 (DF L3)": dict(Emin=0.79e6, Fc4=1550, Fc23=1250, Fby=(1450, 1250, 1000), Fbx=1250),
    "2 (DF L2)": dict(Emin=0.85e6, Fc4=1950, Fc23=1600, Fby=(1800, 1600, 1300), Fbx=1700),
    "3 (DF L2D)": dict(Emin=1.00e6, Fc4=2300, Fc23=1900, Fby=(2100, 1850, 1550), Fbx=2000),
    "5 (DF L1)": dict(Emin=1.06e6, Fc4=2400, Fc23=2100, Fby=(2400, 2100, 1800), Fbx=2200),
    "14 (HF L3)": dict(Emin=0.69e6, Fc4=1100, Fc23=1050, Fby=(1200, 1050, 850), Fbx=1100),
    "15 (HF L2)": dict(Emin=0.74e6, Fc4=1350, Fc23=1350, Fby=(1500, 1350, 1100), Fbx=1450),
    "16 (HF L1)": dict(Emin=0.85e6, Fc4=1500, Fc23=1500, Fby=(1750, 1550, 1300), Fbx=1600),
    "17 (HF L1D)": dict(Emin=0.90e6, Fc4=1750, Fc23=1750, Fby=(2000, 1850, 1550), Fbx=1900),
}
SOURCE_5B = "2018 NDS Supplement Table 5B"
BOISE_TABLE = "Boise Glulam Specifier Guide GLM-5000, Column Tables, Combination 3"
_BOISE = {}


def _boise():
    if not _BOISE:
        import csv
        from pathlib import Path
        with open(Path(__file__).parent / "data" / "glm5000_columns.csv", newline="") as f:
            for r in csv.DictReader(f):
                _BOISE[(float(r["b_in"]), float(r["d_in"]), int(r["length_ft"]), r["duration"])] = float(r["P_lb"])
    return _BOISE


def column_values(combination, laminations):
    if combination not in COLUMNS:
        raise GlulamError(f"glulam: combination '{combination}' is not in StruKit's Table 5B file")
    if laminations is None or laminations < 2:
        raise GlulamError("glulam: a glued laminated column has two or more laminations")
    v = COLUMNS[combination]
    return dict(Emin=v["Emin"], Fc=v["Fc4"] if laminations >= 4 else v["Fc23"],
                Fby=v["Fby"][0] if laminations >= 4 else (v["Fby"][1] if laminations == 3 else v["Fby"][2]), Fbx=v["Fbx"])


def boise_column_load(combination, b, d, le_ft, CD):
    """Table value for the column, or None where the table does not list it:
    (allowable load lb, length used ft, duration heading, multiplier)."""
    if not combination.startswith("3 "):
        return None
    T = _boise()
    key = None
    for bb, dd in ((b, d), (d, b)):
        if any(abs(k[0] - bb) < 0.01 and abs(k[1] - dd) < 0.01 for k in T):
            key = (bb, dd)
    if key is None:
        return None
    lens = sorted({k[2] for k in T if abs(k[0] - key[0]) < 0.01 and abs(k[1] - key[1]) < 0.01})
    import math
    L = max(int(math.ceil(le_ft - 1e-9)), lens[0])
    if L > lens[-1]:
        return None
    head, mult = ("100%", 0.9) if CD < 1.0 else (("100%", 1.0) if CD < 1.15 else (("115%", 1.0) if CD < 1.25 else ("125%", 1.0)))
    k = next(k for k in T if abs(k[0] - key[0]) < 0.01 and abs(k[1] - key[1]) < 0.01 and k[2] == L and k[3] == head)
    return T[k] * mult, L, head, mult
