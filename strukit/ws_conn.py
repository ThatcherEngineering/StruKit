"""Connection worksheets: a fillet weld group and a line of bolts, from loads to checks.

Thin layers over welds.py (AISC 360-22 J2) and bolts.py (J3) that carry the load
combinations, find the governing one and keep the inputs beside the result for the calc
sheet. The force is taken as acting through the centre of the weld group or along the
line of bolts; a connection with eccentricity is outside these worksheets and the sheet
says so.

Units: inches, kips, ksi.
"""
from dataclasses import dataclass, field

from . import bolts, welds
from .ws_steel_beam import Row, WorksheetError

WELD_NOT_CHECKED = ["eccentric load on the weld group (instantaneous centre / elastic method)",
                    "strength of the connected parts other than shear rupture at the weld (J4)",
                    "fatigue (Appendix 3)", "weld access, returns and termination details (J2.2b)"]
BOLT_NOT_CHECKED = ["eccentric load on the bolt group", "block shear and net-section rupture of the "
                    "connected parts (J4)", "slip-critical connections (J3.9)",
                    "minimum spacing and edge distance (J3.3 to J3.5)",
                    "prying action", "pattern length over 38 in (Table J3.2 footnote)"]


@dataclass
class ConnSheet:
    mark: str
    kind: str                    # "weld" or "bolts"
    method: str
    inp: dict
    loads: list                  # dicts: case, P (kips), label
    totals: dict = field(default_factory=dict)
    governing: str = ""
    rows: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    not_checked: list = field(default_factory=list)

    @property
    def ok(self):
        return all(r.status == "OK" for r in self.rows)


def _demand(mark, loads, combos):
    if not combos:
        raise WorksheetError(f"{mark}: no load combinations given")
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    for ld in loads:
        if "case" not in ld or "P" not in ld:
            raise WorksheetError(f"{mark}: a load needs 'case' and 'P'")
    totals = {cb.name: abs(sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in loads)) for cb in combos}
    worst = max(totals, key=lambda k: totals[k])
    return totals, worst


def fillet_weld(mark, loads, combos, method, size, length, n_lines, FEXX, theta_deg, directional,
                end_loaded, t_thinner=None, t_edge=None, base_t=None, base_Fu=None):
    """n_lines equal fillet welds of leg `size` and `length` each, loaded through the
    centre of the group at theta_deg to the weld axis. directional and end_loaded must be
    given (True / False); see welds.fillet. The optional thicknesses turn on the size
    limits and the base-metal check."""
    for nm, v in (("directional", directional), ("end_loaded", end_loaded)):
        if v not in (True, False):
            raise WorksheetError(f"{mark}: say yes or no for '{nm}'")
    totals, worst = _demand(mark, loads, combos)
    res = welds.fillet(size, length, n_lines, FEXX, theta_deg, directional, end_loaded,
                       t_thinner, t_edge, base_t, base_Fu, method)
    inp = dict(size=size, length=length, n_lines=n_lines, FEXX=FEXX, theta_deg=theta_deg,
               directional=directional, end_loaded=end_loaded, t_thinner=t_thinner, t_edge=t_edge,
               base_t=base_t, base_Fu=base_Fu)
    s = ConnSheet(mark, "weld", method, inp, list(loads), totals, worst, steps=list(res.lines),
                  not_checked=list(WELD_NOT_CHECKED))
    s.rows.append(Row("weld strength", worst, totals[worst], res.R_avail, "kip",
                      "AISC 360-22 Sect. J2.4: " + res.governs,
                      f"({n_lines:g}) {size:g} in fillet welds, {length:g} in each"))
    if t_thinner is not None:
        s.rows.append(Row("minimum weld size", "-", welds.min_fillet_size(t_thinner), size, "in",
                          "AISC 360-22 Table J2.4", f"thinner part joined {t_thinner:g} in; demand is the "
                          "minimum size, capacity is the size provided"))
    else:
        s.not_checked.append("minimum weld size, Table J2.4 (thinner part thickness not entered)")
    if t_edge is not None:
        s.rows.append(Row("maximum weld size at an edge", "-", size, welds.max_fillet_size(t_edge), "in",
                          "AISC 360-22 Sect. J2.2b(b)", f"edge thickness {t_edge:g} in"))
    else:
        s.not_checked.append("maximum weld size along an edge, J2.2b(b) (edge thickness not entered)")
    if base_t is None:
        s.not_checked.append("base metal shear rupture at the weld, Eq. J2-2 (base metal not entered)")
    s.assumptions = ["The force acts through the centre of the weld group; all welds are the same size.",
                     ("Directional strength increase of Eq. J2-5 is used." if directional else
                      "No directional strength increase is taken (Eq. J2-4 only).")]
    s.assumptions += [f for f in res.flags if "minimum" not in f and "maximum" not in f and "exceeds" not in f]
    return s


def bolt_line(mark, loads, combos, method, d, group, n, spacing, edge, plies, threads, planes,
              deformation):
    """A line of n bolts loaded along the line toward the edge. plies as in bolts.bolt_line.
    threads "N" (in the shear plane) or "X"; deformation True when deformation at the bolt
    hole at service load is a design consideration (J3.11a)."""
    if deformation not in (True, False):
        raise WorksheetError(f"{mark}: say yes or no for whether hole deformation is a design consideration")
    if threads not in ("N", "X"):
        raise WorksheetError(f"{mark}: threads must be N (in the shear plane) or X (excluded)")
    if not plies:
        raise WorksheetError(f"{mark}: no connected parts (plies) given")
    totals, worst = _demand(mark, loads, combos)
    res = bolts.bolt_line(d, group, int(n), spacing, edge, plies, threads, int(planes), deformation, method)
    one = bolts.shear(d, group, threads, int(planes), method)
    inp = dict(d=d, group=group, n=int(n), spacing=spacing, edge=edge, plies=list(plies), threads=threads,
               planes=int(planes), deformation=deformation)
    s = ConnSheet(mark, "bolts", method, inp, list(loads), totals, worst,
                  steps=list(one.lines) + list(res.lines), not_checked=list(BOLT_NOT_CHECKED))
    s.rows.append(Row("bolt line strength", worst, totals[worst], res.R_avail, "kip",
                      "AISC 360-22 Sect. J3.7, J3.11a: " + res.governs,
                      f"({int(n)}) {d:g} in {group} bolts; each bolt takes the least of its shear, bearing "
                      "and tearout strength (J3.7 User Note)"))
    s.assumptions = ["The force acts along the line of bolts, toward the edge, with no eccentricity.",
                     "Standard holes (Table J3.3). Bolts are snug-tight or pretensioned bearing-type.",
                     ("Deformation at the bolt hole at service load is a design consideration "
                      "(Eq. J3-6a, J3-6c)." if deformation else
                      "Deformation at the bolt hole is not a design consideration (Eq. J3-6b, J3-6d).")]
    return s
