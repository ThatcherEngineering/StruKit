"""Reduction of uniform live loads, ASCE/SEI 7-22 Sect. 4.7 and 4.8.

Read from the standard (pdf pp. 78-79; equations and Table 4.7-1 confirmed against the page images):
  Sect. 4.7.2    members with KLL AT of 400 ft2 or more: L = Lo (0.25 + 15 / sqrt(KLL AT)),
                 Eq. 4.7-1; not less than 0.50 Lo for members supporting one floor and
                 0.40 Lo for members supporting two or more floors.
  Table 4.7-1    KLL: interior columns 4; exterior columns without cantilever slabs 4; edge
                 columns with cantilever slabs 3; corner columns with cantilever slabs 2;
                 edge beams without cantilever slabs 2; interior beams 2; all other members 1.
  Sect. 4.7.3    live loads over 100 psf are not reduced; exception: members supporting two
                 or more floors, by at most 20 percent, and not below L of Sect. 4.7.2.
  Sect. 4.7.4    passenger vehicle garages: not reduced; the same exception.
  Sect. 4.7.5    assembly areas: not reduced.
  Sect. 4.8.2    ordinary roofs: Lr = Lo R1 R2, 12 <= Lr <= 20 psf, Eq. 4.8-1. R1 = 1 for AT
                 of 200 ft2 or less, 1.2 - 0.001 AT between, 0.6 for 600 ft2 or more. R2 = 1
                 for F of 4 or less, 1.2 - 0.05 F between, 0.6 for F of 12 or more; F = the
                 rise in inches per foot.
Not covered: one-way slab area limit (4.7.6), a calculated KLL, arches and domes, occupiable
roofs (4.8.3), the greenhouse provision of 4.8.2.
"""
import math

KLL = {"interior column": 4, "exterior column without cantilever slabs": 4, "edge column with cantilever slabs": 3,
       "corner column with cantilever slabs": 2, "edge beam without cantilever slabs": 2, "interior beam": 2, "all other members": 1}
OCCUPANCY = ("ordinary", "passenger vehicle garage", "assembly area")


class LiveLoadError(ValueError):
    pass


def floor(Lo, element, AT, floors, occupancy="ordinary"):
    """Reduced floor live load: dict(L, factor, KLL, KLL_AT, eq (Eq. 4.7-1 value or None), by)."""
    if element not in KLL:
        raise LiveLoadError("live load: the element is one of: " + "; ".join(KLL))
    if occupancy not in OCCUPANCY:
        raise LiveLoadError("live load: the occupancy is one of: " + "; ".join(OCCUPANCY))
    if Lo is None or Lo <= 0 or AT is None or AT <= 0 or floors is None or floors < 1:
        raise LiveLoadError("live load: the load, the tributary area and the number of floors must be positive")
    k = KLL[element]
    ka = k * AT
    out = dict(KLL=k, KLL_AT=ka, eq=None)
    if occupancy == "assembly area":
        return dict(out, L=Lo, factor=1.0, by="Sect. 4.7.5: not reduced")
    if ka < 400:
        return dict(out, L=Lo, factor=1.0, by="Sect. 4.7.2: KLL AT under 400 ft2, not reduced")
    f = 0.25 + 15.0 / math.sqrt(ka)
    low = 0.5 if floors < 2 else 0.4
    f472 = min(1.0, max(f, low))
    out["eq"] = f
    heavy = Lo > 100
    if heavy or occupancy == "passenger vehicle garage":
        sect = "Sect. 4.7.3" if heavy else "Sect. 4.7.4"
        if floors < 2:
            return dict(out, L=Lo, factor=1.0, by=f"{sect}: not reduced")
        f2 = max(0.8, f472)
        return dict(out, L=Lo * f2, factor=f2, by=f"{sect}, exception: at most 20 percent")
    by = "Eq. 4.7-1" if f472 == f else (f"Sect. 4.7.2: minimum {low:.2f} Lo" if f < low else "Eq. 4.7-1")
    return dict(out, L=Lo * f472, factor=f472, by=by)


def roof(Lo, AT, F):
    """Reduced roof live load, ordinary roofs: dict(Lr, R1, R2, by)."""
    if Lo is None or Lo <= 0 or AT is None or AT <= 0 or F is None or F < 0:
        raise LiveLoadError("live load: the roof load, the tributary area and the rise must be entered")
    R1 = 1.0 if AT <= 200 else 0.6 if AT >= 600 else 1.2 - 0.001 * AT
    R2 = 1.0 if F <= 4 else 0.6 if F >= 12 else 1.2 - 0.05 * F
    raw = Lo * R1 * R2
    Lr = min(max(raw, 12.0), 20.0)
    return dict(Lr=Lr, R1=R1, R2=R2, raw=raw, by="Eq. 4.8-1" if Lr == raw else ("minimum 12 psf" if raw < 12 else "maximum 20 psf"))
