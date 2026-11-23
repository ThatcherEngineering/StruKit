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
