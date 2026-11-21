"""Steel column worksheet: one column under axial load, from loads to the check.

Ties together the Shapes Database (shapes.py) and the AISC 360-22 Chapter E strength
check (steel_column.py). Axial compression only: a column with moment, or with load
applied off its centre, is outside this worksheet and the sheet says so.

Nothing is defaulted: the effective length factors and where they come from, the
unbraced length about each axis, the load combinations, and whether self-weight is
included are all inputs, and each is printed.

Units: feet, kips, ksi.
"""
from dataclasses import dataclass, field

from . import shapes, steel_column
from .ws_steel_beam import Row, WorksheetError

NOT_CHECKED = ["bending or eccentric load (AISC 360-22 Ch. H)", "base plate and anchor rods",
               "connections at the top and bottom", "tension or uplift"]


@dataclass
class SteelColumnSheet:
    mark: str
    shape: str
    Fy: float
    height_ft: float
    method: str
    props: dict
    loads: list                    # dicts: case, P (kips), label
    Lx_ft: float
    Ly_ft: float
    Kx: float
    Ky: float
    k_source: str
    totals: dict = field(default_factory=dict)         # combo name -> axial load, kips
    rows: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    governing: str = ""
    assumptions: list = field(default_factory=list)
    not_checked: list = field(default_factory=lambda: list(NOT_CHECKED))

    @property
    def ok(self):
        return all(r.status == "OK" for r in self.rows)


def run(mark, shape, Fy, height_ft, loads, combos, Kx, Ky, k_source, method,
        include_self_weight, Lx_ft=None, Ly_ft=None, self_weight_case="D"):
    """Lx_ft and Ly_ft are the unbraced lengths for buckling about the x (strong) and
    y (weak) axes; left as None they are the full height. k_source says where Kx and Ky
    come from (for example "pinned top and bottom, braced frame")."""
    if method not in ("ASD", "LRFD"):
        raise WorksheetError("method must be ASD or LRFD")
    if not combos:
        raise WorksheetError(f"{mark}: no load combinations given")
    if include_self_weight not in (True, False):
        raise WorksheetError(f"{mark}: say whether self-weight is included (True or False)")
    if not k_source:
        raise WorksheetError(f"{mark}: say where the effective length factors come from")
    if Kx is None or Ky is None or Kx <= 0 or Ky <= 0:
        raise WorksheetError(f"{mark}: Kx and Ky must be given")
    for ld in loads:
        for k in ("case", "P"):
            if k not in ld:
                raise WorksheetError(f"{mark}: a load is missing '{k}'")
    if not loads:
        raise WorksheetError(f"{mark}: no loads given")
    props = shapes.get(shape)
    Lx = height_ft if Lx_ft is None else Lx_ft
    Ly = height_ft if Ly_ft is None else Ly_ft
    all_loads = list(loads)
    assumptions = ["Load is applied along the centre of the column; no bending is considered."]
    if include_self_weight:
        sw = props["W"] * height_ft / 1000.0
        all_loads.append(dict(case=self_weight_case, P=sw,
                              label=f"self-weight {props['W']:.0f} lb/ft x {height_ft:g} ft"))
        assumptions.append(f"Column self-weight ({props['W']:.0f} lb/ft, {shapes.SOURCE}) added "
                           f"to load case {self_weight_case}.")
    else:
        assumptions.append("Column self-weight is NOT added separately; it is taken as "
                           "included in the loads entered.")
    chk = steel_column.check(props, Fy, Kx * Lx * 12, Ky * Ly * 12, method=method)
    sheet = SteelColumnSheet(mark, shapes.normalize(shape), Fy, height_ft, method, props,
                             all_loads, Lx, Ly, Kx, Ky, k_source, assumptions=assumptions)
    for cb in combos:
        sheet.totals[cb.name] = sum(cb.factors.get(ld["case"], 0.0) * ld["P"] for ld in all_loads)
    worst = max(sheet.totals, key=lambda k: sheet.totals[k])
    if sheet.totals[worst] <= 0:
        raise WorksheetError(f"{mark}: no combination puts the column in compression; "
                             "tension is not covered by this worksheet")
    sheet.governing = worst
    sheet.rows.append(Row("axial compression", worst, sheet.totals[worst], chk.P_avail, "kip",
                          "AISC 360-22 Ch. E: " + chk.governs,
                          f"Lcx = {Kx:g} x {Lx:g} ft, Lcy = {Ky:g} x {Ly:g} ft"))
    sheet.rows.append(Row("slenderness", "-", chk.slenderness, 200.0, "",
                          "AISC 360-22 Sect. E2 User Note (recommended limit, not a requirement)",
                          "governing Lc / r"))
    sheet.steps = chk.lines
    return sheet
