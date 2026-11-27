"""Simpson Strong-Tie connectors from the Wood Construction Connectors catalog C-C-2026 (on file in Zach's reference folder).

Face-mount joist hangers for solid sawn lumber: the tables on catalog pp. 114 to 118 (DF/SP) and 119 to 123 (SPF/HF), read into
data/simpson_facemount.json by tools/simpson_extract.py and checked row by row against the page text. Allowable loads are ASD, in lb,
for uplift (160, wind or earthquake, no further increase, footnote 1 p. 118), floor (100), snow (115) and roof (125) load duration.
Adjustments applied:
  * carrying member of 2x lumber: the header nails are shortened to 0.148 x 1-1/2 in. (catalog p. 112 for LUS/HUS: 0.64 of the table
    load where 0.162 in. nails are specified, 0.77 where 0.148 x 3 in. nails are; p. 26, Load Adjustment Factors for Optional
    Fasteners, the same factors for the other face-mount hangers);
  * nailing into the end grain of a solid sawn carrying member: 0.67 (p. 110).
Hangers fastened with SDS screws are not used on a 2x carrying member (no factor is given).
"""
import json
import os
import re

_DATA = None
SOURCE = "Simpson Strong-Tie catalog C-C-2026"
DURATIONS = {"floor (100)": "floor", "snow (115)": "snow", "roof (125)": "roof"}


class SimpsonError(ValueError):
    pass


def facemount_rows():
    global _DATA
    if _DATA is None:
        with open(os.path.join(os.path.dirname(__file__), "data", "simpson_facemount.json")) as f:
            _DATA = json.load(f)["rows"]
    return _DATA


def joist_sizes():
    order = lambda g: (len(g.split()) > 1, ["", "DBL", "TPL", "QUAD"].index(g.split()[0]) if len(g.split()) > 1 else 0,
                       [int(x) for x in re.findall(r"\d+", g)])
    return sorted({r["joist"] for r in facemount_rows()}, key=order)


def models():
    out = []
    for r in facemount_rows():
        if r["model"] not in out:
            out.append(r["model"])
    return out


def header_factor(row, two_by):
    """Allowable load factor for the carrying member: 1.0, or for a 2x carrying member with the header nails shortened to
    0.148 x 1-1/2 in.: 0.64 (0.162 in. nails in the table) or 0.77 (0.148 x 2-1/2, 3 or 3-1/4 in.); p. 112 and p. 26."""
    if not two_by:
        return 1.0, ""
    h = row["header"]
    if "SDS" in h:
        raise SimpsonError(f"{row['model']}: hangers fastened with SDS screws are not covered on a 2x carrying member")
    if "0.162" in h:
        return 0.64, "2x carrying member: header nails 0.148 x 1-1/2 in. for the 0.162 in. nails, x 0.64 (catalog pp. 26, 112)"
    if "0.148" in h and not h.rstrip().endswith("1 1/2"):
        return 0.77, "2x carrying member: header nails 0.148 x 1-1/2 in. for the 0.148 in. nails, x 0.77 (catalog pp. 26, 112)"
    return 1.0, "2x carrying member: the table header nails fit"


def facemount(joist, species, model, download, duration, uplift=0.0, two_by=False, end_grain=False, nailing=None):
    """Check (or choose, model = "lightest that works") a face-mount hanger. Returns dict(row, allow_down, allow_up, factor, notes,
    rows [(check, demand, capacity)])."""
    if species not in ("DF/SP", "SPF/HF"):
        raise SimpsonError("joist hanger: the species group is DF/SP or SPF/HF")
    if duration not in DURATIONS:
        raise SimpsonError("joist hanger: choose the load duration of the download")
    if download is None or download < 0 or (uplift or 0) < 0:
        raise SimpsonError("joist hanger: the download and uplift must be zero or more")
    cands = [r for r in facemount_rows() if r["joist"] == joist and r["species"] == species]
    if not cands:
        raise SimpsonError(f"joist hanger: no face-mount hanger for a {joist} joist in the {species} tables")
    col = DURATIONS[duration]

    def capacity(r):
        f, txt = header_factor(r, two_by)
        e = 0.67 if end_grain else 1.0
        return r[col] * f * e, (r["uplift"] or 0.0) * f * e, f, e, txt

    pick = model.strip().upper() == "LIGHTEST THAT WORKS"
    if pick:
        ok = []
        for r in cands:
            try:
                d_, u_, *_ = capacity(r)
            except SimpsonError:
                continue
            if d_ >= download - 1e-9 and u_ >= (uplift or 0.0) - 1e-9:
                ok.append(r)
        if not ok:
            raise SimpsonError(f"joist hanger: no {species} face-mount hanger for a {joist} joist carries {download:,.0f} lb down and {uplift or 0:,.0f} lb up")
        row = ok[0]
    else:
        want = model.strip().upper()
        mine = [r for r in cands if r["model"].upper() == want or want in [x.strip().upper() for x in r["model"].split("/")]]
        if not mine:
            raise SimpsonError(f"joist hanger: {model} is not listed for a {joist} joist in the {species} tables (catalog pp. 114-123)")
        if nailing:
            mine = [r for r in mine if r["nailing"].lower().startswith(nailing.lower()[:3])] or mine
        row = mine[-1] if not nailing else mine[0]            # without a choice, the maximum nailing where there are two
    d_, u_, f, e, txt = capacity(row)
    notes = [n for n in (txt, "nailed into the end grain of the carrying member, x 0.67 (catalog p. 110)" if end_grain else "") if n]
    rows = [("download", download, d_), ("uplift", uplift or 0.0, u_)] if uplift else [("download", download, d_)]
    return dict(row=row, allow_down=d_, allow_up=u_, factor=f * e, notes=notes, rows=rows, picked=pick, col=col)
