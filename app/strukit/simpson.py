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

_DATA = {}
SOURCE = "Simpson Strong-Tie catalog C-C-2026"
KINDS = {"face mount": "facemount", "top flange": "topflange"}
PAGES = {"facemount": "pp. 114-123", "topflange": "pp. 142-146"}
DURATIONS = {"floor (100)": "floor", "snow (115)": "snow", "roof (125)": "roof"}


class SimpsonError(ValueError):
    pass


def rows_of(kind="facemount"):
    if kind not in _DATA:
        with open(os.path.join(os.path.dirname(__file__), "data", f"simpson_{kind}.json")) as f:
            _DATA[kind] = json.load(f)["rows"]
    return _DATA[kind]


def facemount_rows():
    return rows_of("facemount")


def joist_sizes():
    order = lambda g: (len(g.split()) > 1, ["", "DBL", "TPL", "QUAD"].index(g.split()[0]) if len(g.split()) > 1 else 0,
                       [int(x) for x in re.findall(r"\d+", g)])
    return sorted({r["joist"] for k in KINDS.values() for r in rows_of(k)}, key=order)


def models():
    out = []
    for k in KINDS.values():
        for r in rows_of(k):
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


def facemount(joist, species, model, download, duration, uplift=0.0, two_by=False, end_grain=False, nailing=None, kind="facemount"):
    """Check (or choose, model = "lightest that works") a face-mount or top-flange hanger. Returns dict(row, allow_down, allow_up, factor,
    notes, rows [(check, demand, capacity)]). Top-flange hangers (catalog pp. 142-146): the carrying member must be solid sawn or SCL wide
    enough for the top flange and its nails; installations on a 2x nailer or welded to steel (p. 136) are not covered, nor end grain;
    a "—" uplift in the table is no uplift capacity; loads may not be increased for load duration (p. 136, note 4: the table's floor,
    snow and roof columns are used as printed)."""
    if kind == "topflange" and (two_by or end_grain):
        raise SimpsonError("joist hanger: top-flange hangers on a 2x nailer or into end grain are not covered (catalog p. 136, nailer table)")
    if species not in ("DF/SP", "SPF/HF"):
        raise SimpsonError("joist hanger: the species group is DF/SP or SPF/HF")
    if duration not in DURATIONS:
        raise SimpsonError("joist hanger: choose the load duration of the download")
    if download is None or download < 0 or (uplift or 0) < 0:
        raise SimpsonError("joist hanger: the download and uplift must be zero or more")
    cands = [r for r in rows_of(kind) if r["joist"] == joist and r["species"] == species]
    what = "face-mount" if kind == "facemount" else "top-flange"
    if not cands:
        raise SimpsonError(f"joist hanger: no {what} hanger for a {joist} joist in the {species} tables")
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
            raise SimpsonError(f"joist hanger: no {species} {what} hanger for a {joist} joist carries {download:,.0f} lb down and {uplift or 0:,.0f} lb up")
        row = ok[0]
    else:
        want = model.strip().upper()
        base = lambda m_: m_.upper().replace("(MAX.)", "").strip()
        mine = [r for r in cands if base(r["model"]) == want or r["model"].upper() == want or want in [x.strip().upper() for x in base(r["model"]).split("/")]]
        if not mine:
            raise SimpsonError(f"joist hanger: {model} is not listed for a {joist} joist in the {species} {what} tables (catalog {PAGES[kind]})")
        if nailing:
            mine = [r for r in mine if r["nailing"].lower().startswith(nailing.lower()[:3])] or mine
        row = mine[-1] if not nailing else mine[0]            # without a choice, the maximum nailing where there are two
    d_, u_, f, e, txt = capacity(row)
    notes = [n for n in (txt, "nailed into the end grain of the carrying member, x 0.67 (catalog p. 110)" if end_grain else "") if n]
    rows = [("download", download, d_), ("uplift", uplift or 0.0, u_)] if uplift else [("download", download, d_)]
    return dict(row=row, allow_down=d_, allow_up=u_, factor=f * e, notes=notes, rows=rows, picked=pick, col=col, kind=kind)


# Seismic and hurricane ties, wood to wood (H/TSP), catalog C-C-2026 p. 300, copied row by row from the table (tests check every row's
# loads against the page). Columns: model, gauge, nails to rafter / truss, to plates, to studs; DF/SP uplift, F1, F2; SPF/HF uplift,
# F1, F2. Allowable loads (lb) for wind or earthquake (160), no further increase (p. 274 note 1; general notes pp. 288-289).
# None = no value in the table (that direction is not rated). The column "uplift with 0.131 x 1-1/2 in. nails" is not used.
TIES = [
    ("H1A", 18, "(4) 0.131 x 1 1/2", "(4) 0.131 x 1 1/2", None, (545, 420, 265), (470, 360, 205)),
    ("H1.81Z", 18, "(6) 0.131 x 1 1/2", "(4) 0.131 x 2 1/2", None, (540, 440, 170), (465, 380, 130)),
    ("H2A", 18, "(5) 0.131 x 1 1/2", "(2) 0.131 x 1 1/2", "(5) 0.131 x 1 1/2", (525, 130, 55), (495, 130, 55)),
    ("H2ASS", 18, "(5) 0.131 x 1 1/2", "(2) 0.131 x 1 1/2", "(5) 0.131 x 1 1/2", (400, 130, 55), (345, 130, 55)),
    ("H2.5A", 18, "(5) 0.131 x 2 1/2", "(5) 0.131 x 2 1/2", None, (700, 110, 110), (615, 110, 110)),
    ("H2.5ASS", 18, "(5) 0.131 x 2 1/2", "(5) 0.131 x 2 1/2", None, (440, 75, 70), (380, 75, 70)),
    ("H2.5T", 18, "(5) 0.131 x 2 1/2", "(5) 0.131 x 2 1/2", None, (590, 135, 145), (565, 135, 145)),
    ("H3", 18, "(4) 0.131 x 2 1/2", "(4) 0.131 x 2 1/2", None, (400, 210, 170), (365, 180, 145)),
    ("H3SS", 18, "(4) 0.131 x 2 1/2", "(4) 0.131 x 2 1/2", None, (280, 145, 120), (225, 100, 85)),
    ("H6 (to plates)", 16, None, "(8) 0.131 x 2 1/2", "(8) 0.131 x 2 1/2", (930, None, None), (800, None, None)),
    ("H6 (to rim)", 16, "(8) 0.131 x 2 1/2", None, "(8) 0.131 x 2 1/2", (1230, None, None), (1065, None, None)),
    ("H7Z", 16, "(4) 0.131 x 2 1/2", "(2) 0.131 x 1 1/2", "(8) 0.131 x 2 1/2", (830, 410, None), (715, 355, None)),
    ("H8", 18, "(5) 0.148 x 1 1/2", "(5) 0.148 x 1 1/2", None, (780, 95, 90), (710, 95, 90)),
    ("H8SS", 18, "(5) 0.148 x 1 1/2", "(5) 0.148 x 1 1/2", None, (610, 90, 120), (370, 90, 55)),
    ("H10A (field bent)", 18, "(9) 0.148 x 1 1/2", "(9) 0.148 x 1 1/2", None, (780, 565, 285), (760, 485, 285)),
    ("H10A", 18, "(9) 0.148 x 1 1/2", "(9) 0.148 x 1 1/2", None, (1040, 565, 285), (1015, 485, 285)),
    ("H10ASS", 18, "(9) 0.148 x 1 1/2", "(9) 0.148 x 1 1/2", None, (970, 565, 170), (835, 485, 170)),
    ("H10AR", 18, "(9) 0.148 x 1 1/2", "(9) 0.148 x 1 1/2", None, (1050, 490, 285), (905, 420, 285)),
    ("H10S", 18, "(8) 0.131 x 1 1/2", "(8) 0.131 x 1 1/2", "(8) 0.131 x 2 1/2", (910, 660, 215), (785, 570, 185)),
    ("H10A-2", 18, "(9) 0.148 x 1 1/2", "(9) 0.148 x 1 1/2", None, (1080, 680, 260), (930, 585, 225)),
    ("H11Z", 18, "(6) 0.162 x 2 1/2", "(6) 0.162 x 2 1/2", None, (830, 525, 760), (715, 450, 655)),
    ("H14 (13 nails to plates)", 18, "(12) 0.131 x 1 1/2", "(13) 0.131 x 2 1/2", None, (1275, 725, 285), (1050, 480, 245)),
    ("H14 (15 nails to plates)", 18, "(12) 0.131 x 1 1/2", "(15) 0.131 x 2 1/2", None, (1340, 670, 230), (1050, 480, 245)),
    ("TSP (0.148 x 1-1/2 to plates)", 16, "(9) 0.148 x 1 1/2", "(6) 0.148 x 1 1/2", None, (755, 310, 190), (650, 265, 160)),
    ("TSP (0.148 x 3 to plates)", 16, "(9) 0.148 x 1 1/2", "(6) 0.148 x 3", None, (1015, 310, 190), (875, 265, 160)),
]
TIE_PAGE = 300


def tie_models():
    return [t[0] for t in TIES]


def hurricane_tie(model, species, uplift, F1=0.0, F2=0.0):
    """Seismic or hurricane tie (wood to wood), catalog p. 300. Each load against its allowable, and with loads in more than one
    direction the unity equation of the catalog's general notes (p. 289, Option 1): U/Ua + F1/F1a + F2/F2a <= 1.0. A direction with
    no table value cannot take load. model "first that works": the first tie in the catalog table order that passes. Returns dict."""
    if species not in ("DF/SP", "SPF/HF"):
        raise SimpsonError("hurricane tie: the species group is DF/SP or SPF/HF")
    loads = (uplift or 0.0, F1 or 0.0, F2 or 0.0)
    if min(loads) < 0 or max(loads) <= 0:
        raise SimpsonError("hurricane tie: give the uplift and lateral loads (zero or more, not all zero)")

    def check(t):
        al = t[5] if species == "DF/SP" else t[6]
        rows, unity = [], 0.0
        for nm, dem, cap in zip(("uplift", "lateral F1 (parallel to the plate)", "lateral F2 (perpendicular to the plate)"), loads, al):
            if dem > 0:
                if cap is None:
                    return None
                rows.append((nm, dem, cap)); unity += dem / cap
        if len(rows) > 1:
            rows.append(("loads together, U/Ua + F1/F1a + F2/F2a", unity, 1.0))
        return rows, al

    if model.strip().lower() in ("first that works", "lightest that works"):
        for t in TIES:
            c_ = check(t)
            if c_ and all(d <= c + 1e-9 for _, d, c in c_[0]):
                break
        else:
            raise SimpsonError(f"hurricane tie: no tie on p. {TIE_PAGE} carries these loads; consider two ties or another connector")
        picked = True
    else:
        t = next((x for x in TIES if x[0].lower() == model.strip().lower()), None)
        if t is None:
            raise SimpsonError(f"hurricane tie: {model} is not in the table on catalog p. {TIE_PAGE}")
        c_ = check(t)
        if c_ is None:
            raise SimpsonError(f"hurricane tie: {t[0]} has no rated value in a direction that is loaded")
        picked = False
    rows, al = c_
    return dict(tie=t, rows=rows, allow=al, picked=picked)
