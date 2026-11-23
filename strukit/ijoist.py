"""Prefabricated wood I-joists: Boise Cascade BCI (ICC-ES ESR-1336) and Weyerhaeuser TJI
(ICC-ES ESR-1153), designed by the 2018 NDS Chapter 7, ASD.

Data: data/ijoists.csv, built by tools/parse_ijoists.py from the text of the two reports.
BCI is limited to the series in Boise's West Specifier Guide MTP-W7000 (5000-1.7, 6000-1.8,
6500-1.8, 60-2.0, 90-2.0); joist weights for BCI are from that guide, for TJI from
ESR-1153 Table 3.

Read from the reports and the NDS:
  NDS Table 7.3.1   Mr' = Mr CD ..., Vr' = Vr CD, Rr' = Rr CD (dry use, CM = 1.0)
  NDS 7.3.5         the compression flange is to be supported throughout its length
  ESR-1336 Table 2 note 3, ESR-1153 Table 3 note 9: no repetitive member increase
  ESR-1336 Sect. 4.11   shear deflection = 8 M / K  (M in lb-in, K in lb)
  ESR-1153 Table 3 note 2   deflection = 22.5 W L^4 / EI + 12 W L^2 / (K d x 10^5), which
                    is the same shear term 8 M / (K d x 10^5) with M in lb-in
  ESR-1153 Table 3 note 4   interpolation between bearing lengths is permitted (TJI).
                    ESR-1336 Table 3 gives minimum bearing lengths; for BCI the value of
                    the longest tabulated bearing not longer than the one provided is used.
End reactions only (simple spans).
"""
import csv
from pathlib import Path


class IJoistError(ValueError):
    pass


JOISTS = {}
with open(Path(__file__).parent / "data" / "ijoists.csv", newline="") as _f:
    for _r in csv.DictReader(_f):
        num = lambda k: float(_r[k]) if _r[k] != "" else None
        JOISTS[(_r["product"], _r["series"], float(_r["depth"]))] = dict(
            weight=float(_r["weight_plf"]), M=float(_r["M"]), V=float(_r["V"]), EI=float(_r["EI_e6"]) * 1e6, K=float(_r["K_shear_lb"]),
            short=float(_r["short_bearing_in"]), Re_short=num("Re_short"), Re_short_ws=num("Re_short_ws"), Re_35=num("Re_35"),
            Re_35_ws=num("Re_35_ws"), source=_r["source"])
NAMES = sorted({f"{p} {s}" for p, s, _ in JOISTS}, key=lambda x: (x.split()[0], x))
DEPTHS = sorted({d for _, _, d in JOISTS})


def joist(name, depth):
    p, _, s = name.partition(" ")
    j = JOISTS.get((p, s, float(depth)))
    if j is None:
        have = sorted(d for (pp, ss, d) in JOISTS if (pp, ss) == (p, s))
        if not have:
            raise IJoistError(f"I-joist: '{name}' is not on file")
        raise IJoistError(f"I-joist: {name} is not made {depth:g} in. deep (depths on file: " + ", ".join(f"{d:g}" for d in have) + ")")
    return dict(j, product=p, series=s, depth=float(depth))


def end_reaction(j, bearing_in, stiffeners):
    """Reference end reaction for the bearing length, and how it was found."""
    lo = j["Re_short_ws"] if stiffeners else j["Re_short"]
    hi = j["Re_35_ws"] if stiffeners else j["Re_35"]
    if lo is None or hi is None:
        raise IJoistError(f"I-joist: {j['product']} {j['series']} {j['depth']:g} in. " +
                          ("has no tabulated end reaction with web stiffeners" if stiffeners else "requires web stiffeners at the end bearing"))
    if bearing_in < j["short"]:
        raise IJoistError(f"I-joist: the end bearing must be at least {j['short']:g} in.")
    if bearing_in >= 3.5:
        return hi, "3.5 in. bearing"
    if j["product"] == "TJI":
        return lo + (hi - lo) * (bearing_in - j["short"]) / (3.5 - j["short"]), f"interpolated between {j['short']:g} and 3.5 in. bearing"
    return lo, f"{j['short']:g} in. bearing"
