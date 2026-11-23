"""Anchor rod data from AISC Design Guide 1, Base Connection Design for Steel Structures,
3rd Edition (2024).

  GRADES   Table 2-2, Recommended Anchor Rod Materials: tensile strength Fu. The yield
           strength of ASTM F1554 is its grade number (36, 55, 105 ksi; the standard's
           title, cited in the guide's references). Sect. 4.3.2.1: threaded rods
           conforming to ASTM F1554 satisfy the ductile steel element requirements of
           ACI 318.
  THREADS  Table 4-1: threads per inch (UNC) and tensile stress area Ase,N by diameter.
  NUT      Table 4-2: bearing area Abrg of a heavy hex nut by diameter.
"""

SOURCE = "AISC Design Guide 1, 3rd Ed."

# name: (Fu ksi, Fy ksi, ductile per ACI 318, largest diameter in.)
GRADES = {
    "F1554 Gr. 36": (58.0, 36.0, True, 4.0),
    "F1554 Gr. 55": (75.0, 55.0, True, 4.0),
    "F1554 Gr. 105": (125.0, 105.0, True, 3.0),
}

# diameter in.: (threads per inch, Ab in2, Ase,N in2, heavy hex nut Abrg in2)
SIZES = {
    0.625: (11, 0.307, 0.226, 0.671),
    0.75: (10, 0.442, 0.334, 0.911),
    0.875: (9, 0.601, 0.462, 1.19),
    1.0: (8, 0.785, 0.606, 1.50),
    1.125: (7, 0.994, 0.763, 1.85),
    1.25: (7, 1.23, 0.969, 2.24),
    1.5: (6, 1.77, 1.41, 3.12),
    1.75: (5, 2.41, 1.90, 4.14),
    2.0: (4.5, 3.14, 2.50, 5.32),
    2.25: (4.5, 3.98, 3.25, 6.63),
    2.5: (4, 4.91, 4.00, 8.10),
    2.75: (4, 5.94, 4.93, 9.70),
    3.0: (4, 7.07, 5.97, 11.5),
    3.25: (4, 8.30, 7.10, 13.4),
    3.5: (4, 9.62, 8.33, 15.4),
    3.75: (4, 11.0, 9.66, 17.6),
    4.0: (4, 12.6, 11.1, 19.9),
}


def grade(name):
    """(Fu, Fy, ductile, source text) of a listed rod grade, or None."""
    g = GRADES.get(name)
    if not g:
        return None
    return g[0], g[1], g[2], f"ASTM {name}; {SOURCE} Table 2-2"


def size(da):
    """(threads per inch, heavy hex nut Abrg) for a listed diameter, or None."""
    for d, v in SIZES.items():
        if abs(d - da) < 1e-6:
            return v[0], v[3]
    return None
