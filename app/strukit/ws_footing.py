"""Footing worksheets: one isolated footing or one continuous footing, inputs to checks.

A thin layer over footing.py (ACI 318-19) that keeps the inputs beside the result so the
calc sheet can print both, and that refuses to run without the source of the allowable
soil bearing pressure.
"""
from dataclasses import dataclass, field

from . import footing
from .ws_steel_beam import Row, WorksheetError


@dataclass
class FootingSheet:
    mark: str
    kind: str                      # "isolated" or "continuous"
    inp: dict
    soil_source: str
    supported: str                 # "wood", "steel" or "concrete": what sits on the footing
    result: object
    rows: list = field(default_factory=list)

    @property
    def ok(self):
        return all(r.status == "OK" for r in self.rows)


def _rows(result):
    return [Row(c.name, c.combo, c.demand, c.capacity, c.unit, c.source, c.note)
            for c in result.checks]


def _need_source(mark, soil_source):
    if not soil_source or not str(soil_source).strip():
        raise WorksheetError(f"{mark}: give the source of the allowable soil bearing pressure "
                             "(soils report name and date, or the code table used)")


def isolated(mark, soil_source, supported, **inp):
    _need_source(mark, soil_source)
    if supported not in ("wood", "steel", "concrete"):
        raise WorksheetError(f"{mark}: supported must be wood, steel or concrete")
    res = footing.check(**inp)
    return FootingSheet(mark, "isolated", inp, soil_source, supported, res, _rows(res))


def continuous(mark, soil_source, **inp):
    _need_source(mark, soil_source)
    res = footing.check_continuous(**inp)
    return FootingSheet(mark, "continuous", inp, soil_source,
                        "concrete", res, _rows(res))
