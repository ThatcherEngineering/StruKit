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


# ---------------------------------------------------------------- post bases and caps (catalog pp. 73-103)
def _in(s):
    """'5 1/2' -> 5.5; '7' -> 7.0."""
    s = s.strip()
    if " " in s:
        a, b = s.split(" ", 1)
        return float(a) + _in(b)
    if "/" in s:
        n, d = s.split("/")
        return float(n) / float(d)
    return float(s)


# ABA / ABU / ABW adjustable standoff post bases, post installation, DF/SP, catalog p. 77 (copied row by row; the tests find every
# row's loads in order in the page text). Columns: model, nominal post, base ga, strap ga, W, L, H (in.), anchor dia., nails,
# uplift with nails (160), uplift with bolts (160) or None, bolts (qty, dia.) or None, download (100), lb.
POST_BASES = [
    ("ABA24-2Z", "Double 2x4", 16, 16, "3 1/8", "3 3/8", "3 1/8", "1/2", "(6) 0.148 x 2 1/2", 630, None, None, 5925),
    ("ABA44Z", "4x4", 16, 16, "3 9/16", "3 3/8", "3 1/16", "1/2", "(6) 0.148 x 3", 690, None, None, 5925),
    ("ABW44Z", "4x4", 16, 16, "3 9/16", "3 9/16", "2 1/4", "1/2", "(8) 0.148 x 3", 1005, None, None, 7180),
    ("ABU44Z", "4x4", 16, 12, "3 9/16", "3", "5 1/2", "5/8", "(12) 0.162 x 3 1/2", 1900, 2300, (2, "1/2"), 7570),
    ("ABA44RZ", "Rough 4x4", 16, 16, "4 1/16", "3 1/8", "2 13/16", "1/2", "(6) 0.148 x 3", 655, None, None, 7215),
    ("ABW44RZ", "Rough 4x4", 16, 16, "4", "4 1/16", "1 15/16", "1/2", "(8) 0.148 x 3", 835, None, None, 7180),
    ("ABU44RZ", "Rough 4x4", 16, 12, "4 1/16", "3", "5 1/4", "5/8", "(12) 0.162 x 3 1/2", 1900, 2300, (2, "1/2"), 7570),
    ("ABA46Z", "4x6", 14, 14, "3 9/16", "5 3/16", "3 1/8", "5/8", "(8) 0.162 x 3 1/2", 870, None, None, 10500),
    ("ABW46Z", "4x6", 12, 16, "5 9/16", "3 9/16", "3", "1/2", "(10) 0.148 x 3", 845, None, None, 4590),
    ("ABU46Z", "4x6", 12, 12, "3 9/16", "5", "7", "5/8", "(12) 0.162 x 3 1/2", 2405, 2265, (2, "1/2"), 12520),
    ("ABA46RZ", "Rough 4x6", 14, 14, "4 1/16", "5 3/16", "2 7/8", "5/8", "(8) 0.162 x 3 1/2", 870, None, None, 10695),
    ("ABW46RZ", "Rough 4x6", 12, 16, "4", "6", "2 13/16", "1/2", "(10) 0.148 x 3", 780, None, None, 4590),
    ("ABU46RZ", "Rough 4x6", 12, 12, "4 1/16", "5", "6 3/4", "5/8", "(12) 0.162 x 3 1/2", 2405, 2265, (2, "1/2"), 12520),
    ("ABU5-5Z", "5 1/8 x 5 1/8", 12, 10, "5 1/4", "5", "6 1/16", "5/8", "(12) 0.162 x 3 1/2", 2235, 2235, (2, "1/2"), 10570),
    ("ABU5-6Z", "5 1/8 x 6", 12, 10, "6 1/8", "5", "6 1/16", "5/8", "(12) 0.162 x 3 1/2", 2235, 2235, (2, "1/2"), 10570),
    ("ABU65Z", "5 1/2 x 5", 12, 10, "5 1/2", "5", "6 1/16", "5/8", "(12) 0.162 x 3 1/2", 2475, None, None, 10960),
    ("ABA66Z", "6x6", 14, 14, "5 1/2", "5 3/8", "3 1/8", "5/8", "(8) 0.162 x 3 1/2", 920, None, None, 11415),
    ("ABW66Z", "6x6", 12, 14, "5 1/2", "5 9/16", "3", "1/2", "(12) 0.148 x 3", 1190, None, None, 12935),
    ("ABU66Z", "6x6", 12, 10, "5 1/2", "5", "6 1/16", "5/8", "(12) 0.162 x 3 1/2", 2475, 2190, (2, "1/2"), 18205),
    ("ABA66RZ", "Rough 6x6", 14, 14, "6", "5 3/16", "2 7/8", "5/8", "(8) 0.162 x 3 1/2", 920, None, None, 11415),
    ("ABW66RZ", "Rough 6x6", 12, 14, "6", "6", "2 13/16", "1/2", "(12) 0.148 x 3", 1190, None, None, 12935),
    ("ABU66RZ", "Rough 6x6", 12, 10, "6 1/16", "5", "5 13/16", "5/8", "(12) 0.162 x 3 1/2", 2475, 2190, (2, "1/2"), 18205),
    ("ABW7-7Z", "7 1/8 x 7 1/8", 12, 14, "7 5/16", "7 5/16", "3", "1/2", "(12) 0.148 x 3", 840, None, None, 16685),
    ("ABU88Z", "8x8", 14, 12, "7 1/2", "7", "7", "(2) 5/8", "(18) 0.162 x 3 1/2", 4120, None, None, 22405),
    ("ABU88RZ", "Rough 8x8", 14, 12, "8", "7", "6 3/4", "(2) 5/8", "(18) 0.162 x 3 1/2", 4045, None, None, 19870),
    ("ABU1010Z", "10x10", 14, 12, "9 1/2", "9", "7 1/4", "(2) 5/8", "(22) 0.162 x 3 1/2", 2270, None, None, 32020),
    ("ABU1010RZ", "Rough 10x10", 14, 12, "10", "9", "7", "(2) 5/8", "(22) 0.162 x 3 1/2", 1830, None, None, 31650),
    ("ABU1212Z", "12x12", 12, 12, "11 1/2", "11", "7 1/4", "(2) 5/8", "(22) 0.162 x 3 1/2", 3000, None, None, 34745),
    ("ABU1212RZ", "Rough 12x12", 12, 12, "12", "11", "7", "(2) 5/8", "(22) 0.162 x 3 1/2", 3000, None, None, 34745),
]
POST_BASE_PAGE = 77
BASES_NOTES_PAGE = 73


def post_base_posts():
    out = []
    for r in POST_BASES:
        if r[1] not in out:
            out.append(r[1])
    return out


def post_base_models():
    return [r[0] for r in POST_BASES]


def post_base(post, model, download, uplift=0.0, fastening="nails"):
    """Adjustable standoff post base (ABA / ABU / ABW), post installation, DF/SP, catalog p. 77. The download against the table download
    (100; not increased for short-term load, note 2); the uplift against the table uplift (160, wind or earthquake, note 1) with nails,
    or with the through bolts where the table gives them (ABU, note 4: bolts or nails, not both). Download and uplift come from different
    load combinations and are checked separately. model "first that works": the first base for the post in the table order that passes."""
    download, uplift = download or 0.0, uplift or 0.0
    if download < 0 or uplift < 0 or not (download or uplift):
        raise SimpsonError("post base: give the download or the uplift (zero or more, not both zero)")
    bolts = fastening.strip().lower().startswith("bolt")
    cands = [r for r in POST_BASES if r[1] == post]
    if not cands:
        raise SimpsonError(f"post base: no base for a {post} post on catalog p. {POST_BASE_PAGE}")

    def check(r):
        if bolts and r[10] is None:
            return None
        up = r[10] if bolts else r[9]
        rows = []
        if download:
            rows.append(("download", download, r[12]))
        if uplift:
            rows.append(("uplift", uplift, up))
        return rows

    if model.strip().lower() in ("first that works", "lightest that works"):
        for r in cands:
            rows = check(r)
            if rows and all(d <= c + 1e-9 for _, d, c in rows):
                break
        else:
            raise SimpsonError(f"post base: no base for a {post} post on p. {POST_BASE_PAGE} carries these loads"
                               + (" with bolts" if bolts else ""))
        picked = True
    else:
        r = next((x for x in POST_BASES if x[0].lower() == model.strip().lower()), None)
        if r is None:
            raise SimpsonError(f"post base: {model} is not in the table on catalog p. {POST_BASE_PAGE}")
        if r[1] != post:
            raise SimpsonError(f"post base: {r[0]} is for a {r[1]} post (catalog p. {POST_BASE_PAGE}), not {post}")
        rows = check(r)
        if rows is None:
            raise SimpsonError(f"post base: {r[0]} has no bolted values on p. {POST_BASE_PAGE}; fasten it with the nails")
        picked = False
    return dict(base=r, rows=rows, bolts=bolts, picked=picked,
                dims=dict(W=_in(r[4]), L=_in(r[5]), H=_in(r[6])))


# CC / ECC / ECCU column caps, DF/SP, catalog p. 101 (row by row; tests find each row's five loads in order in the page text).
# Columns: model, beam width(s) (in.), W1, W2, L (CC, ECC, ECCU), H1, bolt size, beam bolts (CC, ECC, ECCU), post bolts,
# CC uplift (160), CC down (100), ECC down (100), ECCU uplift (160), ECCU down (100), lb.
COLUMN_CAPS = [
    ("CC3 1/4-4", "3 1/8", "3 1/4", "3 5/8", ("11", "7 1/2", "9 1/2"), "6 11/16", "5/8", (4, 2, 4), 2, 3150, 16980, 6835, 3150, 6835),
    ("CC3 1/4-6", "3 1/8", "3 1/4", "5 1/2", ("11", "7 1/2", "9 1/2"), "6 11/16", "5/8", (4, 2, 4), 2, 3150, 21485, 10740, 3150, 10740),
    ("CC44", "3 1/2", "3 5/8", "3 5/8", ("7", "5 1/2", "6 1/2"), "4", "5/8", (2, 1, 2), 2, 1850, 15315, 7655, 1850, 7655),
    ("CC46", "3 1/2", "3 5/8", "5 1/2", ("11", "8 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 3530, 24065, 12030, 3530, 12030),
    ("CC48", "3 1/2", "3 5/8", "7 1/2", ("11", "8 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 3530, 24065, 16405, 3530, 16405),
    ("CC4.62-3.62", "4 1/2", "4 5/8", "3 5/8", ("11", "8 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 4535, 23390, 9845, 4535, 9845),
    ("CC4.62-4.62", "4 1/2", "4 5/8", "4 5/8", ("11", "8 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 4535, 30070, 12655, 4535, 12655),
    ("CC4.62-5.50", "4 1/2", "4 5/8", "5 1/2", ("11", "8 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 4535, 30940, 15470, 4535, 15470),
    ("CC5 1/4-4", "5 1/8", "5 1/4", "3 5/8", ("13", "10 1/2", "10 1/2"), "8 1/8", "3/4", (4, 2, 4), 2, 6300, 26635, 11210, 6300, 11210),
    ("CC5 1/4-6", "5 1/8", "5 1/4", "5 1/2", ("13", "10 1/2", "10 1/2"), "8 1/8", "3/4", (4, 2, 4), 2, 6500, 28190, 17615, 6500, 17615),
    ("CC5 1/4-8", "5 1/8", "5 1/4", "7 1/2", ("13", "10 1/2", "10 1/2"), "8 1/8", "3/4", (4, 2, 4), 2, 6645, 35235, 24025, 6645, 24025),
    ("CC64", "5 1/4, 5 1/2", "5 1/2", "3 5/8", ("11", "7 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 5545, 28585, 12030, 5545, 12030),
    ("CC66", "5 1/4, 5 1/2", "5 1/2", "5 1/2", ("11", "7 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 5545, 30250, 18905, 5545, 18905),
    ("CC68", "5 1/4, 5 1/2", "5 1/2", "7 1/2", ("11", "9 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 5545, 37815, 25780, 5545, 25780),
    ("CC6-7 1/8", "5 1/4, 5 1/2", "5 1/2", "7 1/8", ("11", "9 1/2", "9 1/2"), "6 1/2", "5/8", (4, 2, 4), 2, 5545, 37815, 24490, 5545, 24490),
    ("CC74", "6 3/4", "6 7/8", "3 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 6330, 33490, 15355, 6330, 15355),
    ("CC76", "6 3/4", "6 7/8", "5 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 6790, 37125, 24130, 6790, 24130),
    ("CC77", "6 3/4", "6 7/8", "6 7/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 7020, 48265, 29615, 7020, 29615),
    ("CC78", "6 3/4", "6 7/8", "7 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 7145, 48265, 32090, 7145, 32905),
    ("CC7 1/8-4", "7", "7 1/8", "3 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 6360, 34730, 18375, 6360, 18375),
    ("CC7 1/8-6", "7", "7 1/8", "5 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 6825, 38500, 28875, 6825, 28875),
    ("CC7 1/8-7 1/8", "7", "7 1/8", "7 1/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 7105, 57750, 36750, 7105, 36750),
    ("CC7 1/8-8", "7", "7 1/8", "7 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 7190, 52500, 39375, 7190, 39375),
    ("CC84", "7 1/2", "7 1/2", "3 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 6410, 37210, 16405, 6410, 16405),
    ("CC86", "7 1/2", "7 1/2", "5 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 6885, 41250, 25780, 6885, 25780),
    ("CC88", "7 1/2", "7 1/2", "7 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 2, 4), 2, 7250, 51565, 35155, 7250, 35155),
    ("CC94", "8 3/4", "8 7/8", "3 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 6580, 47545, 19905, 6580, 19905),
    ("CC96", "8 3/4", "8 7/8", "5 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 7080, 48125, 31280, 7080, 31280),
    ("CC98", "8 3/4", "8 7/8", "7 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 7455, 62565, 42655, 7455, 42655),
    ("CC106", "9 1/4", "9 1/2", "5 1/2", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 7160, 52250, 32655, 7160, 32655),
    ("CC126", "11 1/2", "11 5/8", "5 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 7410, 63250, 39530, 7410, 39530),
    ("CC128", "11 1/2", "11 5/8", "7 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 7790, 86250, 53905, 7790, 53905),
    ("CC1210", "11 1/2", "11 5/8", "9 5/8", ("13", "10 1/2", "10 1/2"), "8", "3/4", (4, 4, 4), 2, 8080, 93440, 68280, 8080, 68280),
]
COLUMN_CAP_PAGE = 101
# CCQ / ECCQ column caps with 1/4 x 2-1/2 in. SDS screws, DF/SP, catalog p. 99, row by row in the COLUMN_CAPS layout: model, beam width,
# W1, W2, L (CCQ, ECCQ, ECCQ), H, fastener size (None: SDS screws), beam screws (CCQ, ECCQ, ECCQ), post screws, CCQ uplift (160),
# CCQ down (100), (no ECC slot), ECCQ uplift (160), ECCQ down (100). The ECCQ is the end cap and takes the ECCU slot.
CCQ_CAPS = [
    ("CCQ3-4SDS2.5", "3 1/8", "3 1/4", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 16980, None, 3465, 6125),
    ("CCQ3-6SDS2.5", "3 1/8", "3 1/4", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 21485, None, 3465, 10740),
    ("CCQ44SDS2.5", "3 1/2", "3 5/8", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 19020, None, 3785, 7655),
    ("CCQ46SDS2.5", "3 1/2", "3 5/8", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 24065, None, 3785, 12030),
    ("CCQ48SDS2.5", "3 1/2", "3 5/8", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 24065, None, 3785, 16405),
    ("CCQ4.62-3.62SDS", "4 1/2", "4 5/8", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 23390, None, 3785, 9845),
    ("CCQ4.62-4.62SDS", "4 1/2", "4 5/8", "4 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 30070, None, 3785, 12655),
    ("CCQ4.62-5.50SDS", "4 1/2", "4 5/8", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 30940, None, 3785, 15470),
    ("CCQ5-4SDS2.5", "5 1/8", "5 1/4", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 26635, None, 3785, 11210),
    ("CCQ5-6SDS2.5", "5 1/8", "5 1/4", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 28190, None, 5355, 17615),
    ("CCQ5-8SDS2.5", "5 1/8", "5 1/4", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 35235, None, 5355, 24025),
    ("CCQ64SDS2.5", "5 1/4, 5 1/2", "5 1/2", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 28585, None, 3785, 12030),
    ("CCQ66SDS2.5", "5 1/4, 5 1/2", "5 1/2", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 30250, None, 3785, 18905),
    ("CCQ68SDS2.5", "5 1/4, 5 1/2", "5 1/2", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 37815, None, 3785, 25780),
    ("CCQ6-7.13SDS2.5", "5 1/4, 5 1/2", "5 1/2", "7 1/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 37815, None, 3785, 24490),
    ("CCQ74SDS2.5", "6 3/4", "6 7/8", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 33490, None, 3785, 15355),
    ("CCQ76SDS2.5", "6 3/4", "6 7/8", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 37125, None, 5355, 24130),
    ("CCQ77SDS2.5", "6 3/4", "6 7/8", "6 7/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 48265, None, 5355, 29615),
    ("CCQ78SDS2.5", "6 3/4", "6 7/8", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 48265, None, 5355, 32905),
    ("CCQ7.1-4SDS2.5", "7", "7 1/8", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 5370, 34730, None, 3785, 18375),
    ("CCQ7.1-6SDS2.5", "7", "7 1/8", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 38500, None, 5355, 28875),
    ("CCQ7.1-7.1SDS2.5", "7", "7 1/8", "7 1/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 57750, None, 5355, 36750),
    ("CCQ7.1-8SDS2.5", "7", "7 1/8", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 52500, None, 5355, 39375),
    ("CCQ84SDS2.5", "7 1/2", "7 1/2", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 37210, None, 5355, 16405),
    ("CCQ86SDS2.5", "7 1/2", "7 1/2", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 41250, None, 5355, 25780),
    ("CCQ88SDS2.5", "7 1/2", "7 1/2", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 51565, None, 5355, 35155),
    ("CCQ94SDS2.5", "8 3/4", "8 7/8", "3 5/8", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 47545, None, 5355, 19905),
    ("CCQ96SDS2.5", "8 3/4", "8 7/8", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 48125, None, 5355, 31280),
    ("CCQ98SDS2.5", "8 3/4", "8 7/8", "7 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 62565, None, 5355, 42655),
    ("CCQ106SDS2.5", "9 1/4", "9 1/2", "5 1/2", ("11", "8 1/2", "8 1/2"), "7", None, (16, 14, 14), 14, 6785, 52250, None, 5355, 32655),
]
CCQ_PAGE = 99

# BC post caps, DF/SP, catalog p. 93: model, W1, W2, L1, L2, H1, H2 (in.), beam flange nails, post flange nails, uplift (160),
# lateral (160), lb. No download in the table: the beam bears on the post.
BC_CAPS = [
    ("BC4", "3 9/16", "3 9/16", "2 7/8", "2 7/8", "3", "3", "(6) 0.162 x 3 1/2", "(6) 0.162 x 3 1/2", 605, 1000),
    ("BC46", "3 9/16", "5 1/2", "4 7/8", "2 7/8", "3 1/2", "2 1/2", "(12) 0.162 x 3 1/2", "(6) 0.162 x 3 1/2", 945, 1000),
    ("BC4R", "4", "4", "4", "4", "3", "3", "(12) 0.162 x 3 1/2", "(12) 0.162 x 3 1/2", 605, 1000),
    ("BC6", "5 1/2", "5 1/2", "4 3/8", "4 3/8", "3 3/8", "3 3/8", "(12) 0.162 x 3 1/2", "(12) 0.162 x 3 1/2", 1185, 1825),
    ("BC6R", "6", "6", "6", "6", "3", "3", "(12) 0.162 x 3 1/2", "(12) 0.162 x 3 1/2", 1185, 1825),
    ("BC8", "7 1/2", "7 1/2", "7 1/2", "7 1/2", "4", "4", "(12) 0.162 x 3 1/2", "(12) 0.162 x 3 1/2", 1660, 1825),
    ("BCS2-2/4", "3 1/8", "3 9/16", "2 7/8", "2 7/8", "2 15/16", "2 15/16", "(8) 0.148 x 3", "(6) 0.148 x 3", 895, 890),
    ("BCS2-3/6", "4 5/8", "5 9/16", "4 3/8", "2 7/8", "3 5/16", "2 15/16", "(12) 0.162 x 3 1/2", "(6) 0.162 x 3 1/2", 895, 1330),
]
BC_PAGE = 93
# AC / ACHZ / LPCZ / LCE post caps, DF/SP, catalog p. 95 (heights and gauges p. 94), in the BC_CAPS layout: model (with the fastening
# option), W, W, L, L, H on the beam, H on the post (in.), beam fasteners, post fasteners (total, for the pair), uplift (160), lateral
# (160, parallel to the beam, note 3), lb; then the gauge. Installed in pairs; one side only x 0.4 (note 2).
AC_CAPS = [
    ("AC4 (min. nailing)", "3 9/16", "3 9/16", "6 1/2", "6 1/2", "3", "2 1/2", "(8) 0.162 x 3 1/2", "(8) 0.162 x 3 1/2", 1745, 1610, 18),
    ("AC4 (max. nailing)", "3 9/16", "3 9/16", "6 1/2", "6 1/2", "3", "2 1/2", "(14) 0.162 x 3 1/2", "(14) 0.162 x 3 1/2", 2490, 1610, 18),
    ("AC4RZ (min. nailing)", "4", "4", "7", "7", "3", "2 1/2", "(8) 0.162 x 3 1/2", "(8) 0.162 x 3 1/2", 1745, 1610, 18),
    ("AC4RZ (max. nailing)", "4", "4", "7", "7", "3", "2 1/2", "(14) 0.162 x 3 1/2", "(14) 0.162 x 3 1/2", 2490, 2075, 18),
    ("ACH4Z (nails)", "3 9/16", "3 9/16", "6 1/2", "6 1/2", "4 3/4", "4 3/4", "(20) 0.162 x 2 1/2", "(20) 0.162 x 2 1/2", 4045, 1765, 16),
    ("ACH4Z (SD screws)", "3 9/16", "3 9/16", "6 1/2", "6 1/2", "4 3/4", "4 3/4", "(20) SD10212", "(20) SD10212", 5895, 2595, 16),
    ("ACH4Z end (nails)", "3 9/16", "3 9/16", "6 1/2", "6 1/2", "4 3/4", "4 3/4", "(20) 0.162 x 2 1/2", "(20) 0.162 x 2 1/2", 2580, 1360, 16),
    ("ACH4Z end (SD screws)", "3 9/16", "3 9/16", "6 1/2", "6 1/2", "4 3/4", "4 3/4", "(20) SD10212", "(20) SD10212", 2680, 1815, 16),
    ("LCE4", "3 1/2", "3 1/2", "5 3/8", "5 3/8", "5 3/8", "5 3/8", "(14) 0.162 x 3 1/2", "(10) 0.162 x 3 1/2", 1950, 1350, 20),
    ("AC6 (min. nailing)", "5 1/2", "5 1/2", "8 1/2", "8 1/2", "3", "2 1/2", "(8) 0.162 x 3 1/2", "(8) 0.162 x 3 1/2", 1665, 1565, 18),
    ("AC6 (max. nailing)", "5 1/2", "5 1/2", "8 1/2", "8 1/2", "3", "2 1/2", "(14) 0.162 x 3 1/2", "(14) 0.162 x 3 1/2", 2815, 2075, 18),
    ("AC6RZ (min. nailing)", "6", "6", "9", "9", "3", "2 1/2", "(8) 0.162 x 3 1/2", "(8) 0.162 x 3 1/2", 1665, 1565, 18),
    ("AC6RZ (max. nailing)", "6", "6", "9", "9", "3", "2 1/2", "(14) 0.162 x 3 1/2", "(14) 0.162 x 3 1/2", 3055, 2450, 18),
    ("ACH6Z (nails)", "5 1/2", "5 1/2", "8 1/2", "8 1/2", "4 3/4", "4 3/4", "(20) 0.162 x 2 1/2", "(20) 0.162 x 2 1/2", 4045, 2640, 16),
    ("ACH6Z (SD screws)", "5 1/2", "5 1/2", "8 1/2", "8 1/2", "4 3/4", "4 3/4", "(20) SD10212", "(20) SD10212", 5895, 4130, 16),
    ("ACH6Z end (nails)", "5 1/2", "5 1/2", "8 1/2", "8 1/2", "4 3/4", "4 3/4", "(20) 0.162 x 2 1/2", "(20) 0.162 x 2 1/2", 2580, 1965, 16),
    ("ACH6Z end (SD screws)", "5 1/2", "5 1/2", "8 1/2", "8 1/2", "4 3/4", "4 3/4", "(20) SD10212", "(20) SD10212", 2680, 2200, 16),
    ("LPC4Z", "3 9/16", "3 9/16", "3 1/2", "3 1/2", "2 1/2", "2 1/4", "(8) 0.148 x 3", "(8) 0.148 x 3", 755, 760, 18),
    ("LPC6Z", "5 9/16", "5 9/16", "5 1/2", "5 1/2", "2 1/2", "2 1/4", "(8) 0.148 x 3", "(8) 0.148 x 3", 920, 885, 16),
]
AC_PAGE = 95
# RTC44 and LCE4 corner post caps, catalog p. 95 (lower table): model, W, L (in.), beam nails, post nails, DF/SP uplift side beam, main
# beam, post; SPF/HF the same three (160), lb. The beams' combined uplift not over the post value (note 3); LCE4 in pairs (note 4).
RTC_CAPS = [
    ("RTC44 (mitered corner)", "3 9/16", "4 3/4", "(19) 0.162 x 3 1/2", "(10) 0.162 x 3 1/2", (900, 900, 1800), (775, 775, 1550)),
    ("RTC44 (square cut)", "3 9/16", "4 3/4", "(19) 0.162 x 3 1/2", "(10) 0.162 x 3 1/2", (925, 1230, 1760), (795, 1060, 1515)),
    ("LCE4 (mitered corner)", "5 3/8", "5 3/8", "(14) 0.162 x 3 1/2", "(10) 0.162 x 3 1/2", (445, 445, 885), (380, 380, 760)),
]


def corner_cap(model, species, uplift_main, uplift_side):
    """Corner post cap RTC44 / LCE4 (catalog p. 95 lower table), uplift (160) on each beam, and their sum against the post value (note 3)."""
    r = next((x for x in RTC_CAPS if x[0].lower() == model.strip().lower()), None)
    if r is None:
        raise SimpsonError("corner cap: " + ", ".join(x[0] for x in RTC_CAPS) + f" (catalog p. {AC_PAGE})")
    if species not in ("DF/SP", "SPF/HF"):
        raise SimpsonError("corner cap: the species group is DF/SP or SPF/HF")
    if not (uplift_main or uplift_side) or min(uplift_main or 0, uplift_side or 0) < 0:
        raise SimpsonError("corner cap: give the uplift of the main or side beam")
    al = r[5] if species == "DF/SP" else r[6]
    rows = []
    if uplift_side:
        rows.append(("uplift, side beam", uplift_side, al[0]))
    if uplift_main:
        rows.append(("uplift, main beam", uplift_main, al[1]))
    rows.append(("uplift, both beams, at the post (note 3)", (uplift_main or 0) + (uplift_side or 0), al[2]))
    return dict(row=r, rows=rows, allow=al)
CAP_SERIES = ["CC", "ECC", "ECCU", "BC", "CCQ", "ECCQ", "AC"]
_SLOT = {"CC": 0, "ECC": 1, "ECCU": 2, "CCQ": 0, "ECCQ": 2}


def _cap_table(series):
    return CCQ_CAPS if series in ("CCQ", "ECCQ") else COLUMN_CAPS


def cap_models(series):
    if series == "BC":
        return [r[0] for r in BC_CAPS]
    if series == "AC":
        return [r[0] for r in AC_CAPS]
    if series in ("CCQ", "ECCQ"):
        return [("E" if series == "ECCQ" else "") + r[0] for r in CCQ_CAPS]
    pre = {"CC": "", "ECC": "E", "ECCU": "E"}[series]
    suf = "U" if series == "ECCU" else ""
    out = []
    for r in COLUMN_CAPS:                                    # ECC / ECCU models carry the CC size: ECC44, ECCU44 (p. 100)
        size = r[0][2:]
        out.append((pre + "CC" + (("U" + size) if suf else size)) if series != "CC" else r[0])
    return out


def _cap_row(series, model):
    if series in ("BC", "AC"):
        return next((r for r in (BC_CAPS if series == "BC" else AC_CAPS) if r[0].lower() == model.strip().lower()), None)
    for r, m in zip(_cap_table(series), cap_models(series)):
        if m.lower().replace(" ", "") == model.strip().lower().replace(" ", ""):
            return r
    return None


def column_cap(series, model, download=0.0, uplift=0.0, lateral=0.0, beam_width=None, post_width=None, beam_depth=None,
               spliced=False, download2=0.0, one_side=False):
    """Column or post cap, DF/SP. CC / ECC / ECCU (catalog p. 101): download (100) and uplift (160) from the table; ECC has no uplift
    value (p. 101: ECCU is the end cap rated for uplift); the beam at least as deep as H1 (note 7). A CC at a beam splice over the post
    (p. 73 note l): each spliced beam not over half the table download and not over 2 x the other beam's download; uplift and lateral
    values do not apply. BC (p. 93): uplift and lateral (both 160); no download value (the beam bears on the post); spliced beams not
    permitted (note 4); uplift with lateral by the unity equation (p. 23 note e, p. 289 Option 1). model "first that works": the first
    cap in the table order whose beam and post widths match the typed widths and that passes."""
    download, uplift, lateral, download2 = download or 0.0, uplift or 0.0, lateral or 0.0, download2 or 0.0
    if series not in CAP_SERIES:
        raise SimpsonError("column cap: the series is CC, ECC, ECCU, CCQ, ECCQ, BC or AC")
    if min(download, uplift, lateral, download2) < 0:
        raise SimpsonError("column cap: loads are zero or more")
    if not (download or uplift or lateral or download2):
        raise SimpsonError("column cap: give a load")
    bc = series in ("BC", "AC")
    if series == "BC" and spliced:
        raise SimpsonError(f"column cap: spliced beams on a BC post cap are not permitted (catalog p. {BC_PAGE} note 4)")
    if series == "AC" and spliced and (uplift or lateral):
        raise SimpsonError(f"column cap: uplift loads do not apply to spliced conditions (catalog p. {AC_PAGE} note 5)")
    if one_side and series != "AC":
        raise SimpsonError("column cap: the one-side factor (x 0.4) is for the AC, ACHZ, LCE post caps (p. 95 note 2)")
    if one_side and model.upper().startswith("LPC"):
        raise SimpsonError("column cap: the LPCZ is not tabulated for one side")
    if spliced and series not in ("CC", "CCQ"):
        raise SimpsonError("column cap: a beam splice over the post is for a CC cap (an end cap carries one beam end)")
    if spliced and (uplift or lateral) and not bc:
        raise SimpsonError(f"column cap: table uplift and lateral loads do not apply to spliced beams (catalog p. {BASES_NOTES_PAGE} note l)")
    if lateral and not bc:
        raise SimpsonError(f"column cap: the {series} table gives no lateral load (catalog p. {page_of(series)})")
    page = page_of(series)
    if bc and (download or download2):
        raise SimpsonError(f"column cap: the {series} table gives no download (catalog p. {page}); the beam bears on the post, checked on its own sheet")
    f_side = 0.4 if one_side else 1.0

    def fits(r):
        if beam_width is None or post_width is None:
            return False
        if bc:
            return _in(r[1]) - 0.13 <= beam_width <= _in(r[1]) + 0.01 and _in(r[2]) - 0.13 <= post_width <= _in(r[2]) + 0.01 and \
                not (series == "AC" and r[0].startswith("LCE"))
        bws = [_in(x) for x in r[1].split(",")]
        return any(abs(beam_width - b) <= 0.07 for b in bws) and _in(r[3]) - 0.26 <= post_width <= _in(r[3]) + 0.01

    def check(r):
        rows = []
        if bc:
            ua, la = r[9] * f_side, r[10] * f_side
            if uplift:
                rows.append(("uplift", uplift, ua))
            if lateral:
                rows.append(("lateral", lateral, la))
            if uplift and lateral:
                rows.append(("loads together, U/Ua + L/La", uplift / ua + lateral / la, 1.0))
            return rows
        down_a, up_a = {0: (r[10], r[9]), 1: (r[11], None), 2: (r[13], r[12])}[_SLOT[series]]
        if uplift and up_a is None:
            return None
        if spliced:
            for nm, d_, o_ in (("download, beam 1 at the splice", download, download2), ("download, beam 2 at the splice", download2, download)):
                rows.append((nm + " (half the table value)", d_, down_a / 2.0))
                if o_:
                    rows.append((nm + " (not over 2 x the other beam)", d_, 2.0 * o_))
        elif download:
            rows.append(("download", download, down_a))
        if uplift:
            rows.append(("uplift", uplift, up_a))
        if beam_depth is not None:
            rows.append(("beam depth at least H1 (note 7)", _in(r[5]), beam_depth))
        return rows

    if model.strip().lower() in ("first that works", "lightest that works"):
        if beam_width is None or post_width is None:
            raise SimpsonError("column cap: give the beam and post widths to choose a cap")
        if not bc and beam_depth is None:
            raise SimpsonError(f"column cap: give the beam depth (the beam must be at least as deep as H1, p. {page} note 7)")
        tab = (BC_CAPS if series == "BC" else AC_CAPS) if bc else _cap_table(series)
        fit = [r for r in tab if fits(r) and " end" not in r[0]]            # the end-of-beam options only when named
        if not fit:
            raise SimpsonError(f"column cap: no {series} cap on p. {page} fits a {beam_width:g} in. beam on a {post_width:g} in. post")
        for r in fit:
            rows = check(r)
            if rows and all(d <= c + 1e-9 for _, d, c in rows):
                break
        else:
            raise SimpsonError(f"column cap: no {series} cap on p. {page} for these widths carries these loads")
        picked = True
    else:
        r = _cap_row(series, model)
        if r is None:
            raise SimpsonError(f"column cap: {model} is not a {series} cap in the table on catalog p. {page}")
        rows = check(r)
        if rows is None:
            raise SimpsonError(f"column cap: the ECC table gives no uplift (catalog p. {COLUMN_CAP_PAGE}); use an ECCU or ECCQ end cap")
        picked = False
    mdl = r[0].split(" (")[0].replace(" end", "") if bc else cap_models(series)[_cap_table(series).index(r)]
    if bc:
        dims = dict(W1=_in(r[1]), W2=_in(r[2]), L=_in(r[3]), H1=_in(r[5]), H2=_in(r[6]))
    else:
        dims = dict(W1=_in(r[2]), W2=_in(r[3]), L=_in(r[4][_SLOT[series]]), H1=_in(r[5]), bolt=_in(r[6]) if r[6] else None,
                    beam_bolts=r[7][_SLOT[series]], post_bolts=r[8])
    return dict(row=r, model=mdl, series=series, rows=rows, picked=picked, dims=dims, page=page, one_side=one_side, label=r[0])


# ---------------------------------------------------------------- straps (catalog pp. 288-297)
# Straight strap ties, catalog p. 291 (HRS, HTP, LSTA, LSTI, MSTA, MSTC, MSTI, ST), copied row by row; the tests find every row in the
# page text. Columns: model, gauge, W, L (in.), fasteners (total, half in each member, p. 288 note d), DF/SP and SPF/HF allowable
# tension (160), lb.
STRAPS = [
    ('ST2115', 20, '3/4', '16 5/16', '(10) 0.162 x 2 1/2', 660, 660),
    ('LSTA9', 20, '1 1/4', '9', '(8) 0.148 x 2 1/2', 740, 635),
    ('LSTA12', 20, '1 1/4', '12', '(10) 0.148 x 2 1/2', 925, 795),
    ('LSTA15', 20, '1 1/4', '15', '(12) 0.148 x 2 1/2', 1110, 955),
    ('LSTA18', 20, '1 1/4', '18', '(14) 0.148 x 2 1/2', 1235, 1115),
    ('LSTA21', 20, '1 1/4', '21', '(16) 0.148 x 2 1/2', 1235, 1235),
    ('LSTA24', 20, '1 1/4', '24', '(18) 0.148 x 2 1/2', 1235, 1235),
    ('LSTA30', 18, '1 1/4', '30', '(22) 0.148 x 2 1/2', 1640, 1640),
    ('LSTA36', 18, '1 1/4', '36', '(24) 0.148 x 2 1/2', 1640, 1640),
    ('MSTA9', 18, '1 1/4', '9', '(8) 0.148 x 2 1/2', 750, 650),
    ('MSTA12', 18, '1 1/4', '12', '(10) 0.148 x 2 1/2', 940, 810),
    ('MSTA15', 18, '1 1/4', '15', '(12) 0.148 x 2 1/2', 1130, 970),
    ('MSTA18', 18, '1 1/4', '18', '(14) 0.148 x 2 1/2', 1315, 1135),
    ('MSTA21', 18, '1 1/4', '21', '(16) 0.148 x 2 1/2', 1505, 1295),
    ('MSTA24', 18, '1 1/4', '24', '(18) 0.148 x 2 1/2', 1640, 1460),
    ('MSTA30', 18, '1 1/4', '30', '(22) 0.148 x 2 1/2', 2050, 1825),
    ('MSTA36', 18, '1 1/4', '36', '(26) 0.148 x 2 1/2', 2050, 2050),
    ('MSTA49', 18, '1 1/4', '49', '(26) 0.148 x 2 1/2', 2020, 2020),
    ('ST9', 16, '1 1/4', '9', '(8) 0.162 x 2 1/2', 885, 765),
    ('ST12', 16, '1 1/4', '11 5/8', '(10) 0.162 x 2 1/2', 1105, 955),
    ('ST18', 16, '1 1/4', '17 3/4', '(14) 0.162 x 2 1/2', 1420, 1335),
    ('ST22', 16, '1 1/4', '21 5/8', '(18) 0.162 x 2 1/2', 1420, 1420),
    ('HRS6', 12, '1 3/8', '6', '(6) 0.148 x 2 1/2', 605, 530),
    ('HRS8', 12, '1 3/8', '8', '(10) 0.148 x 2 1/2', 1010, 880),
    ('HRS12', 12, '1 3/8', '12', '(14) 0.148 x 2 1/2', 1415, 1230),
    ('ST292', 20, '2 1/16', '9 5/16', '(12) 0.162 x 2 1/2', 1260, 1120),
    ('ST2122', 20, '2 1/16', '12 13/16', '(16) 0.162 x 2 1/2', 1530, 1510),
    ('ST2215', 20, '2 1/16', '16 5/16', '(20) 0.162 x 2 1/2', 1875, 1875),
    ('ST6215', 16, '2 1/16', '16 5/16', '(20) 0.162 x 2 1/2', 2090, 1910),
    ('ST6224', 16, '2 1/16', '23 5/16', '(28) 0.162 x 2 1/2', 2535, 2535),
    ('ST6236', 14, '2 1/16', '33 13/16', '(40) 0.162 x 2 1/2', 3845, 3845),
    ('MSTI26', 12, '2 1/16', '26', '(26) 0.148 x 1 1/2', 2745, 2380),
    ('MSTI36', 12, '2 1/16', '36', '(36) 0.148 x 1 1/2', 3800, 3295),
    ('MSTI48', 12, '2 1/16', '48', '(48) 0.148 x 1 1/2', 5070, 4390),
    ('MSTI60', 12, '2 1/16', '60', '(60) 0.148 x 1 1/2', 5070, 5070),
    ('MSTI72', 12, '2 1/16', '72', '(72) 0.148 x 1 1/2', 5070, 5070),
    ('HTP37Z', 16, '3', '7', '(20) 0.148 x 1 1/2', 900, 690),
    ('MSTC28', 16, '3', '28 1/4', '(36) 0.148 x 3 1/4', 3460, 2990),
    ('MSTC40', 16, '3', '40 1/4', '(52) 0.148 x 3 1/4', 4735, 4315),
    ('MSTC52', 16, '3', '52 1/4', '(62) 0.148 x 3 1/4', 4735, 4735),
    ('MSTC66', 14, '3', '65 3/4', '(68) 0.148 x 3 1/4', 5850, 5850),
    ('MSTC78', 14, '3', '77 3/4', '(76) 0.148 x 3 1/4', 5850, 5850),
    ('HRS416Z', 12, '3 1/4', '16', '(16) 1/4 x 1 1/2 SDS', 2835, 2305),
    ('LSTI49', 18, '3 3/4', '49', '(32) 0.148 x 1 1/2', 2970, 2560),
    ('LSTI73', 18, '3 3/4', '73', '(48) 0.148 x 1 1/2', 4205, 3840),
]
STRAP_PAGE = 291
# MST strap ties, catalog p. 292 (lower table): model, gauge, W, L, nails (total), bolts (qty, dia.), DF/SP nails, DF/SP bolts,
# SPF/HF nails, SPF/HF bolts (160), lb. Bolts or nails, not both (note 2); parallel-to-grain loading, members at least 2-1/2 in. (note 3).
MST = [
    ("MST27", 12, "2 1/16", "27", "(30) 0.162 x 2 1/2", (4, "1/2"), 3700, 2165, 3210, 2000),
    ("MST37", 12, "2 1/16", "37 1/2", "(42) 0.162 x 2 1/2", (6, "1/2"), 5070, 3030, 4495, 2800),
    ("MST48", 12, "2 1/16", "48", "(50) 0.162 x 2 1/2", (8, "1/2"), 5310, 3675, 5190, 3395),
    ("MST60", 10, "2 1/16", "60", "(68) 0.162 x 2 1/2", (10, "1/2"), 6730, 4490, 6475, 4150),
    ("MST72", 10, "2 1/16", "72", "(68) 0.162 x 2 1/2", (10, "1/2"), 6730, 4490, 6475, 4150),
]
MST_PAGE = 292
# Coiled straps CMST / CMSTC / CS, catalog p. 296: model, coil length (ft), gauge, then nail options: (DF/SP nails total, DF/SP end
# length in., SPF/HF nails total, SPF/HF end length in.), allowable tension (160), lb (the same for both species groups).
COILS = [
    ("CMST12", "40", 12, [("(74) 0.162 x 2 1/2", 33, "(84) 0.162 x 2 1/2", 38), ("(86) 0.148 x 2 1/2", 39, "(98) 0.148 x 2 1/2", 44)], 9215),
    ("CMST14", "52 1/2", 14, [("(56) 0.162 x 2 1/2", 26, "(66) 0.162 x 2 1/2", 30), ("(66) 0.148 x 2 1/2", 30, "(76) 0.148 x 2 1/2", 34)], 6475),
    ("CMSTC16", "54", 16, [("(50) 0.148 x 3 1/4", 20, "(50) 0.148 x 3 1/4", 25)], 4690),
    ("CS14", "100", 14, [("(26) 0.148 x 2 1/2", 15, "(30) 0.148 x 2 1/2", 16), ("(30) 0.131 x 2 1/2", 16, "(36) 0.131 x 2 1/2", 19)], 2490),
    ("CS16", "150", 16, [("(20) 0.148 x 2 1/2", 11, "(22) 0.148 x 2 1/2", 13), ("(22) 0.131 x 2 1/2", 13, "(26) 0.131 x 2 1/2", 15)], 1705),
    ("CS18", "200", 18, [("(16) 0.148 x 2 1/2", 9, "(18) 0.148 x 2 1/2", 11), ("(18) 0.131 x 2 1/2", 11, "(22) 0.131 x 2 1/2", 12)], 1370),
    ("CS20", "250", 20, [("(12) 0.148 x 2 1/2", 7, "(14) 0.148 x 2 1/2", 9), ("(14) 0.131 x 2 1/2", 9, "(16) 0.131 x 2 1/2", 9)], 1030),
    ("CS22", "300", 22, [("(10) 0.148 x 2 1/2", 6, "(12) 0.148 x 2 1/2", 7), ("(12) 0.131 x 2 1/2", 7, "(14) 0.131 x 2 1/2", 8)], 845),
]
COIL_PAGE = 296
STRAP_NOTES_PAGE = 288
STRAP_KINDS = ["strap tie", "MST", "coiled strap", "floor-to-floor", "heavy strap"]
# Heavy straps, catalog pp. 293-294: model, family, gauge, W, L (in.), fasteners, (qty, dia.) of bolts or None, tension DF/SP, SPF/HF (160),
# lateral F1 DF/SP, SPF/HF or None, page. HL / HT (p. 293): installed in pairs, bolts in double shear, members 3-1/2 in. or more (note 1); the
# table names no species group, so its values are used for DF/SP only; 1616HTQ per part (note 2). PS / PSQ (p. 294): per part, members
# 3-1/2 in. or more (notes 3, 4). HST (p. 294): parallel to grain, members 3-1/2 in. (HST2, HST5) or 4-1/2 in. (HST3, HST6) (note 2).
HEAVY_STRAPS = [
    ("1212HL", "HL", 7, "2 1/2", "12", '(5) 5/8" bolts', (5, "5/8"), (1535, None), (565, None), 293),
    ("1616HL", "HL", 7, "2 1/2", "16", '(5) 5/8" bolts', (5, "5/8"), (1535, None), (565, None), 293),
    ("1212HT", "HT", 7, "2 1/2", "12", '(6) 5/8" bolts', (6, "5/8"), (2585, None), (815, None), 293),
    ("1616HT", "HT", 7, "2 1/2", "16", '(6) 5/8" bolts', (6, "5/8"), (2585, None), (815, None), 293),
    ("1616HTQ", "HTQ", 7, "2 1/2", "16", "(10) SDWH27400G", None, (2670, None), (870, None), 293),
    ("PS218", "PS", 7, "2", "18", '(4) 3/4" bolts', (4, "3/4"), (1740, 1385), None, 294),
    ("PS418", "PS", 7, "4", "18", '(4) 3/4" bolts', (4, "3/4"), (1740, 1385), None, 294),
    ("PS720", "PS", 7, "6 3/4", "20", '(8) 1/2" bolts', (8, "1/2"), (3075, 2645), None, 294),
    ("PSQ218", "PSQ", 7, "2", "18", "(8) SDWH27400G", None, (2815, 2420), (750, 645), 294),
    ("PSQ418", "PSQ", 7, "4", "18", "(8) SDWH27400G", None, (3045, 2620), (780, 670), 294),
    ("HST2", "HST", 7, "2 1/2", "21 1/4", '(6) 5/8" bolts', (6, "5/8"), (5220, 4835), None, 294),
    ("HST5", "HST", 7, "5", "21 1/4", '(12) 5/8" bolts', (12, "5/8"), (10650, 9870), None, 294),
    ("HST3", "HST", 3, "3", "25 1/2", '(6) 3/4" bolts', (6, "3/4"), (7650, 6580), None, 294),
    ("HST6", "HST", 3, "6", "25 1/2", '(12) 3/4" bolts', (12, "3/4"), (15425, 13265), None, 294),
]
NOT_RATED_STRAPS = ("55L", "66L", "88L", "1212L", "66T", "128T", "1212T")          # p. 293 note 1: not load rated
# Floor-to-floor straps across a clear span (rim and floor framing between), catalog p. 292 upper table: model, clear span (in.), nails
# (total, half above and half below the clear span), DF/SP, SPF/HF allowable tension (160), lb.
FLOOR_TO_FLOOR = [
    ("MSTA49", 18, "(26) 0.148 x 2 1/2", 2020, 2020), ("MSTA49", 16, "(26) 0.148 x 2 1/2", 2020, 2020),
    ("MSTC28", 18, "(12) 0.148 x 3 1/4", 1150, 995), ("MSTC28", 16, "(16) 0.148 x 3 1/4", 1535, 1330),
    ("MSTC40", 24, "(20) 0.148 x 3 1/4", 1920, 1660), ("MSTC40", 18, "(28) 0.148 x 3 1/4", 2690, 2325), ("MSTC40", 16, "(32) 0.148 x 3 1/4", 3070, 2655),
    ("MSTC52", 24, "(36) 0.148 x 3 1/4", 3455, 2990), ("MSTC52", 18, "(44) 0.148 x 3 1/4", 4225, 3650), ("MSTC52", 16, "(48) 0.148 x 3 1/4", 4610, 3985),
    ("MSTC66", 30, "(48) 0.148 x 3 1/4", 4775, 4130), ("MSTC66", 24, "(54) 0.148 x 3 1/4", 5375, 4645), ("MSTC66", 18, "(64) 0.148 x 3 1/4", 5850, 5505),
    ("MSTC66", 16, "(68) 0.148 x 3 1/4", 5850, 5850),
    ("MSTC78", 30, "(64) 0.148 x 3 1/4", 5850, 5505), ("MSTC78", 24, "(72) 0.148 x 3 1/4", 5850, 5850), ("MSTC78", 18, "(76) 0.148 x 3 1/4", 5850, 5850),
    ("MST37", 24, "(14) 0.162 x 2 1/2", 1720, 1500), ("MST37", 18, "(20) 0.162 x 2 1/2", 2460, 2140), ("MST37", 16, "(22) 0.162 x 2 1/2", 2705, 2355),
    ("MST48", 24, "(26) 0.162 x 2 1/2", 3210, 2780), ("MST48", 18, "(32) 0.162 x 2 1/2", 3950, 3425), ("MST48", 16, "(34) 0.162 x 2 1/2", 4200, 3640),
    ("MST60", 30, "(34) 0.162 x 2 1/2", 4605, 3995), ("MST60", 24, "(40) 0.162 x 2 1/2", 5240, 4700), ("MST60", 18, "(46) 0.162 x 2 1/2", 6235, 5405),
    ("MST72", 30, "(48) 0.162 x 2 1/2", 6505, 5640), ("MST72", 24, "(54) 0.162 x 2 1/2", 6730, 6345), ("MST72", 18, "(62) 0.162 x 2 1/2", 6730, 6475),
]
_STRAP_LEN = {"MSTA49": "49", "MSTC28": "28 1/4", "MSTC40": "40 1/4", "MSTC52": "52 1/4", "MSTC66": "65 3/4", "MSTC78": "77 3/4",
              "MST37": "37 1/2", "MST48": "48", "MST60": "60", "MST72": "72"}
_STRAP_W = {"MSTA49": "1 1/4", "MST37": "2 1/16", "MST48": "2 1/16", "MST60": "2 1/16", "MST72": "2 1/16"}
_STRAP_GA = {"MSTA49": 18, "MSTC28": 16, "MSTC40": 16, "MSTC52": 16, "MSTC66": 14, "MSTC78": 14, "MST37": 12, "MST48": 12, "MST60": 10, "MST72": 10}


def _count(fast):
    return int(fast.split(")")[0].strip("("))


def strap_models(kind):
    return [r[0] for r in {"strap tie": STRAPS, "MST": MST, "coiled strap": COILS}[kind]]


def heavy_strap(model, species, tension, F1=0.0):
    """HL / HT / HTQ (p. 293), PS / PSQ (p. 294), HST (p. 294), ASD (160). Tension (uplift for HT / HL) and lateral F1 where tabulated, the two
    together by the unity equation (p. 23 note e, p. 289)."""
    if model.strip().upper() in NOT_RATED_STRAPS:
        raise SimpsonError(f"strap: {model} is not load rated (catalog p. 293 note 1)")
    sp = 0 if species == "DF/SP" else 1
    if model.strip().lower() in ("first that works", "lightest that works"):
        cands = HEAVY_STRAPS
    else:
        cands = [r for r in HEAVY_STRAPS if r[0].lower() == model.strip().lower()]
        if not cands:
            raise SimpsonError(f"strap: {model} is not on catalog pp. 293-294")
    for r in cands:
        Ta = r[7][sp]
        if Ta is None:
            if len(cands) == 1:
                raise SimpsonError(f"strap: the {r[0]} table (catalog p. {r[9]}) names no species group; StruKit uses it for DF/SP only")
            continue
        Fa = r[8][sp] if (r[8] and F1) else None
        if F1 and Fa is None:
            if len(cands) == 1:
                raise SimpsonError(f"strap: {r[0]} has no lateral F1 value for {species} (catalog p. {r[9]})")
            continue
        rows = [("tension", tension, Ta)] + ([("lateral F1", F1, Fa)] if F1 else [])
        if F1:
            rows.append(("loads together, sum of load / allowable", tension / Ta + F1 / Fa, 1.0))
        if len(cands) == 1 or all(d <= c + 1e-9 for _, d, c in rows):
            break
    else:
        raise SimpsonError(f"strap: no heavy strap on catalog pp. 293-294 carries these loads ({species})")
    bolts = r[6]
    return dict(model=r[0], family=r[1], ga=r[2], W=r[3], L=r[4], fast=r[5], allow=r[7][sp], page=r[9], n=(bolts[0] if bolts else int(r[5].split(")")[0][1:])),
                kind="heavy strap", species=species, tension=tension, bolts=bool(bolts), bolt=bolts, picked=len(cands) > 1, rows=rows, F1=F1)


def strap(kind, model, species, tension, fastening="nails", nail="0.148", nails_per_end=None, clear_span=None, F1=0.0):
    """Strap in tension, ASD (160, wind or earthquake; reduce where other loads govern, p. 288 note a), half the fasteners in each member
    (note d). kind "strap tie": p. 291; "MST": p. 292, nails or bolts (note 2); "coiled strap": p. 296, nail option by diameter
    (0.162 / 0.148 / 0.131), allowable x nails used / nails in the table for fewer nails (note 2), cut length = 2 x end length + clear
    span (p. 288 note h). model "first that works": the first strap in the table order that passes."""
    if species not in ("DF/SP", "SPF/HF"):
        raise SimpsonError("strap: the species group is DF/SP or SPF/HF")
    if not tension or tension <= 0:
        raise SimpsonError("strap: give the tension")
    sp = 0 if species == "DF/SP" else 1
    bolts = fastening.strip().lower().startswith("bolt")
    if kind not in STRAP_KINDS:
        raise SimpsonError("strap: the kind is strap tie, MST or coiled strap")
    if kind == "heavy strap":
        return heavy_strap(model, species, tension, F1)
    if F1:
        raise SimpsonError("strap: a lateral F1 value is tabulated only for the heavy straps (HL, HT, HTQ, PSQ)")
    if kind == "floor-to-floor":
        if clear_span is None or clear_span <= 0:
            raise SimpsonError("strap: give the clear span between the nailed ends (floor-to-floor table, catalog p. 292)")
        def ff(m):
            rows_ = [r for r in FLOOR_TO_FLOOR if r[0] == m and r[1] >= clear_span - 1e-9]
            return min(rows_, key=lambda r: r[1]) if rows_ else None
        models_ = []
        for r in FLOOR_TO_FLOOR:
            if r[0] not in models_:
                models_.append(r[0])
        if model.strip().lower() in ("first that works", "lightest that works"):
            r = next((ff(m) for m in models_ if ff(m) and tension <= ff(m)[3 + sp] + 1e-9), None)
            if r is None:
                raise SimpsonError(f"strap: no floor-to-floor strap on catalog p. {MST_PAGE} carries {tension:,.0f} lb over a {clear_span:g} in. clear span")
            picked = True
        else:
            m = model.strip().upper()
            if m not in models_:
                raise SimpsonError(f"strap: {model} is not in the floor-to-floor table (catalog p. {MST_PAGE})")
            r = ff(m)
            if r is None:
                raise SimpsonError(f"strap: {m} is tabulated for clear spans up to {max(x[1] for x in FLOOR_TO_FLOOR if x[0] == m)} in. (catalog p. {MST_PAGE})")
            picked = False
        return dict(model=r[0], ga=_STRAP_GA[r[0]], W=_STRAP_W.get(r[0], "3"), L=_STRAP_LEN[r[0]], fast=r[2], allow=r[3 + sp], page=MST_PAGE,
                    n=_count(r[2]), kind=kind, species=species, tension=tension, bolts=False, picked=picked, table_span=r[1], clear=clear_span,
                    rows=[("tension", tension, r[3 + sp])])
    if bolts and kind != "MST":
        raise SimpsonError(f"strap: only the MST straps have bolted values (catalog p. {MST_PAGE})")

    def one(r):
        if kind == "strap tie":
            return dict(model=r[0], ga=r[1], W=r[2], L=r[3], fast=r[4], allow=r[5 + sp], page=STRAP_PAGE, n=_count(r[4]))
        if kind == "MST":
            al = (r[7] if bolts else r[6]) if sp == 0 else (r[9] if bolts else r[8])
            fast = f"({r[5][0]}) {r[5][1]} in. bolts" if bolts else r[4]
            return dict(model=r[0], ga=r[1], W=r[2], L=r[3], fast=fast, allow=al, page=MST_PAGE, n=r[5][0] if bolts else _count(r[4]))
        opt = next((o for o in r[3] if f" {nail} x" in o[2 * sp]), None)
        if opt is None:
            return None
        n_tab = _count(opt[2 * sp])
        n_used = n_tab if not nails_per_end else 2 * int(nails_per_end)
        if n_used > n_tab:
            n_used = n_tab                                    # more nails than the table: no increase (note 2 is a reduction)
        al = r[4] * n_used / n_tab
        end = opt[2 * sp + 1]
        return dict(model=r[0], ga=r[2], W="1 1/4" if r[0].startswith("CS") else "3", L=None,                                     # p. 295 hole patterns
                    fast=opt[2 * sp], allow=al, table_allow=r[4], n=n_used, n_tab=n_tab, end=end, page=COIL_PAGE,
                    cut=(2 * end + clear_span) if clear_span is not None else None)

    tab = {"strap tie": STRAPS, "MST": MST, "coiled strap": COILS}[kind]
    if model.strip().lower() in ("first that works", "lightest that works"):
        for r in tab:
            s_ = one(r)
            if s_ and tension <= s_["allow"] + 1e-9:
                break
        else:
            pg = {"strap tie": STRAP_PAGE, "MST": MST_PAGE, "coiled strap": COIL_PAGE}[kind]
            raise SimpsonError(f"strap: no {kind} on catalog p. {pg} carries {tension:,.0f} lb ({species}" + (", bolted)" if bolts else ")"))
        picked = True
    else:
        r = next((x for x in tab if x[0].lower() == model.strip().lower()), None)
        if r is None:
            raise SimpsonError(f"strap: {model} is not in the {kind} table")
        s_ = one(r)
        if s_ is None:
            raise SimpsonError(f"strap: {r[0]} has no {nail} in. nail option on catalog p. {COIL_PAGE}")
        picked = False
    s_.update(kind=kind, species=species, tension=tension, bolts=bolts, picked=picked,
              rows=[("tension", tension, s_["allow"])])
    return s_


# ---------------------------------------------------------------- framing angles and plates (catalog pp. 309-310)
# A34, A35, LTP4, LTP5, catalog p. 310, row by row (tests find each row in the page text). Columns: model, configuration (the type of
# connection numbered on p. 309), fasteners, direction of load, DF/SP floor (100), roof (125), (160); SPF/HF floor, roof, (160), lb.
ANGLES = [
    ("A34", 1, "(8) 0.131 x 1 1/2", "F1", (395, 480, 545), (340, 415, 480)),
    ("A34", 1, "(8) 0.131 x 1 1/2", "F2", (395, 430, 430), (340, 370, 370)),
    ("A34", 1, '(8) #9 x 1 1/2" SD', "F1", (640, 640, 640), (550, 550, 550)),
    ("A34", 1, '(8) #9 x 1 1/2" SD', "F2", (495, 495, 495), (425, 425, 425)),
    ("A34", 1, '(8) #9 x 1 1/2" SD', "Uplift", (240, 240, 240), (170, 170, 170)),
    ("A35", 2, "(9) 0.131 x 1 1/2", "A1", (295, 350, 350), (255, 300, 300)),
    ("A35", 2, "(9) 0.131 x 1 1/2", "E", (295, 360, 385), (255, 310, 330)),
    ("A35", 2, "(9) 0.131 x 1 1/2", "C1", (185, 185, 185), (160, 160, 160)),
    ("A35", 3, "(12) 0.131 x 1 1/2", "A2", (295, 325, 325), (255, 280, 280)),
    ("A35", 3, "(12) 0.131 x 1 1/2", "C2", (295, 330, 330), (255, 285, 285)),
    ("A35", 3, "(12) 0.131 x 1 1/2", "D", (225, 225, 225), (195, 195, 195)),
    ("A35", 4, "(12) 0.131 x 1 1/2", "F1", (590, 650, 650), (510, 560, 560)),
    ("A35", 4, "(12) 0.131 x 1 1/2", "F2", (590, 670, 670), (510, 575, 575)),
    ("A35", 5, "(12) 0.131 x 1 1/2", "F1", (555, 555, 555), (475, 475, 475)),
    ("A35", 6, "(12) PH612I", "F1", (420, 420, 420), (360, 360, 360)),
    ("LTP4", 7, "(12) 0.131 x 1 1/2", "G", (580, 715, 715), (500, 615, 615)),
    ("LTP4", 7, "(12) 0.131 x 1 1/2", "H", (525, 525, 525), (450, 450, 450)),
    ("LTP4", 7, '(12) #9 x 1 1/2" SD', "G", (910, 910, 910), (670, 780, 780)),
    ("LTP4", 7, '(12) #9 x 1 1/2" SD', "H", (800, 800, 800), (670, 690, 690)),
    ("LTP5", 8, "(12) 0.131 x 1 1/2", "G", (565, 565, 565), (485, 485, 485)),
    ("LTP5", 8, "(12) 0.131 x 1 1/2", "H", (465, 465, 465), (400, 400, 400)),
    ("LTP5", 8, '(12) #9 x 1 1/2" SD', "G", (800, 800, 800), (670, 685, 685)),
    ("LTP5", 8, '(12) #9 x 1 1/2" SD', "H", (730, 730, 730), (625, 625, 625)),
]
ANGLE_PAGE, ANGLE_FIG_PAGE = 310, 309
# L / LS / GA reinforcing and skewable angles, catalog p. 313, row by row: model, fasteners, L (in.), direction ("F1/F2": the value is for
# either), DF/SP floor (100), snow (115), roof (125), wind or seismic (160); SPF/HF the same four, lb.
ANGLES_L = [
    ("GA1", "(4) 0.148 x 1 1/2", "2 3/4", "F1/F2", (235, 270, 290, 350), (200, 230, 250, 300)),
    ("GA1", '(4) #9 x 1 1/2" SD', "2 3/4", "F1", (340, 375, 375, 375), (225, 260, 280, 325)),
    ("GA1", '(4) #9 x 1 1/2" SD', "2 3/4", "F2", (340, 395, 430, 435), (225, 260, 280, 360)),
    ("GA2", "(6) 0.148 x 1 1/2", "3 1/4", "F1/F2", (355, 405, 435, 550), (305, 350, 375, 475)),
    ("GA2", '(6) #9 x 1 1/2" SD', "3 1/4", "F1", (515, 590, 640, 695), (335, 385, 420, 540)),
    ("GA2", '(6) #9 x 1 1/2" SD', "3 1/4", "F2", (515, 590, 640, 820), (335, 385, 420, 540)),
    ("L30", "(4) 0.148 x 1 1/2", "3", "F1", (245, 250, 250, 250), (210, 215, 215, 215)),
    ("L30", "(4) 0.148 x 1 1/2", "3", "F2", (245, 275, 295, 370), (210, 235, 255, 320)),
    ("L50", "(6) 0.148 x 1 1/2", "5", "F1", (365, 415, 445, 525), (315, 355, 385, 450)),
    ("L50", "(6) 0.148 x 1 1/2", "5", "F2", (365, 415, 445, 555), (315, 355, 385, 475)),
    ("L70", "(8) 0.148 x 1 1/2", "7", "F1/F2", (485, 550, 595, 740), (415, 475, 510, 635)),
    ("L90", "(10) 0.148 x 1 1/2", "9", "F1/F2", (610, 690, 740, 925), (525, 595, 635, 795)),
    ("LS30", "(6) 0.148 x 1 1/2", "3 3/8", "F1", (320, 320, 320, 320), (275, 275, 275, 275)),
    ("LS30", "(6) 0.148 x 3", "3 3/8", "F1", (355, 395, 395, 395), (305, 340, 340, 340)),
    ("LS50", "(8) 0.148 x 1 1/2", "4 7/8", "F1", (475, 540, 560, 560), (410, 465, 480, 480)),
    ("LS50", "(8) 0.148 x 3", "4 7/8", "F1", (475, 540, 580, 730), (410, 465, 500, 630)),
    ("LS70", "(10) 0.148 x 1 1/2", "6 3/8", "F1", (590, 645, 645, 645), (510, 555, 555, 555)),
    ("LS70", "(10) 0.148 x 3", "6 3/8", "F1", (590, 675, 725, 915), (510, 580, 625, 785)),
    ("LS90", "(12) 0.148 x 1 1/2", "7 7/8", "F1", (710, 805, 870, 890), (610, 690, 750, 765)),
    ("LS90", "(12) 0.148 x 3", "7 7/8", "F1", (710, 805, 870, 1040), (610, 690, 750, 895)),
]
ANGLE_L_PAGE = 313
ANGLE_CONFIGS = {1: "A34, joists to plate or beam (fig. 1)", 2: "A35, joist to plate, A leg (fig. 2)", 3: "A35, stud to plate, B leg (fig. 3)",
                 4: "A35, joist to beam or plate, flat (fig. 4)", 5: "A35, blocking to plate (fig. 5)", 6: "A35, to subfloor over sheathing (fig. 6)",
                 7: "LTP4, top plates to rim or blocking (fig. 7)", 8: "LTP5, over the subfloor to rim or blocking (fig. 8)",
                 9: "L, LS or GA angle, as the typical installations (p. 313)"}
ANGLE_DURATIONS = {"floor (100)": 0, "snow (115)": 0, "roof (125)": 1, "wind or earthquake (160)": 2}


def angle_models():
    out = []
    for r in ANGLES + ANGLES_L + ANGLES_A + ANGLES_HL:
        if r[0] not in out:
            out.append(r[0])
    return out


# A angles, catalog p. 314 (the rated ones; A66, A88, A24, A311 have no table loads): model, W1, W2, L (in.), fasteners base, post, DF/SP F1,
# F2 (160), lb. SPF/HF x 0.86 (note 2); F1 both ways needs connectors on both sides (note 3).
ANGLES_A = [
    ("A21", "2", "1 1/2", "1 3/8", "(2) 0.148 x 1 1/2", "(2) 0.148 x 1 1/2", 330, 150),
    ("A23", "2", "1 1/2", "2 3/4", "(4) 0.148 x 1 1/2", "(4) 0.148 x 1 1/2", 680, 535),
    ("A33", "3", "3", "1 1/2", "(4) 0.148 x 3", "(4) 0.148 x 3", 765, 340),
    ("A44", "4 9/16", "4 3/8", "1 1/2", "(4) 0.148 x 3", "(4) 0.148 x 3", 775, 290),
]
ANGLE_A_PAGE = 314
# HL heavy angles, catalog p. 315: model, gauge, W1 = W2, L, bolts (qty, dia.), DF/SP uplift, F1 (160), lb; rows "double" for the HL5x / HL7x.
# SPF/HF x 0.85 (note 2); members at least 3-1/2 in. (HL3x, HL5x) or 5-1/8 in. (HL4x, HL7x) thick (notes 4, 5); one connector (note 6).
ANGLES_HL = [
    ("HL33", 7, "3 1/4", "2 1/2", (2, "1/2"), 740, 1040), ("HL35", 7, "3 1/4", "5", (4, "1/2"), 740, 1310),
    ("HL37", 7, "3 1/4", "7 1/2", (6, "1/2"), 740, 1310), ("HL43", 3, "4 1/4", "3", (2, "3/4"), 1275, 1445),
    ("HL46", 3, "4 1/4", "6", (4, "3/4"), 1275, 1680), ("HL49", 3, "4 1/4", "9", (6, "3/4"), 1275, 1680),
    ("HL53", 7, "5 3/4", "2 1/2", (4, "1/2"), 740, 1310), ("HL55", 7, "5 3/4", "5", (8, "1/2"), 740, 1310),
    ("HL57", 7, "5 3/4", "7 1/2", (12, "1/2"), 740, 1310), ("HL73", 3, "7 1/4", "3", (4, "3/4"), 2445, 2885),
    ("HL76", 3, "7 1/4", "6", (8, "3/4"), 2445, 4310), ("HL79", 3, "7 1/4", "9", (12, "3/4"), 2445, 4310),
]
ANGLE_HL_PAGE = 315
ANGLE_CONFIGS.update({10: "A angle, as the installations shown (p. 314)", 11: "HL heavy angle, as the installation shown (p. 315)"})


def _angle_a_hl(model, config, species, duration, loads):
    a = next((r for r in ANGLES_A if r[0] == model), None)
    hl = next((r for r in ANGLES_HL if r[0] == model), None)
    want = 10 if a else 11
    pg = ANGLE_A_PAGE if a else ANGLE_HL_PAGE
    if config != want:
        raise SimpsonError(f"framing angle: {model} is {'an A' if a else 'an HL'} angle (catalog p. {pg}); use type {want}")
    if duration != "wind or earthquake (160)":
        raise SimpsonError(f"framing angle: the {model} table (catalog p. {pg}) gives (160) loads only, for wind or earthquake")
    f = 1.0 if species == "DF/SP" else (0.86 if a else 0.85)
    al = {"F1": a[6], "F2": a[7]} if a else {"Uplift": hl[5], "F1": hl[6]}
    rows, unity = [], 0.0
    for dname, dem in loads.items():
        key = next((k for k in al if k.lower() == dname.lower()), None)
        if key is None:
            raise SimpsonError(f"framing angle: {model} has no {dname} value (directions: {', '.join(al)})")
        cap = al[key] * f
        rows.append((key, dem, cap)); unity += dem / cap
    if len(rows) > 1:
        rows.append(("loads together, sum of load / allowable", unity, 1.0))
    fast = (f"base {a[4]}; post {a[5]}" if a else f'({hl[4][0]}) {hl[4][1]}" dia. bolts')
    return dict(model=model, config=config, fast=fast, species=species, duration=duration, factor=f, rows=rows, directions=list(al), page=pg,
                L=_in(a[3]) if a else _in(hl[3]), leg=_in(a[1]) if a else _in(hl[2]), bolts=hl[4] if hl else None,
                ga=(18 if model in ("A21", "A23") else 12) if a else hl[1])


def framing_angle(model, config, fasteners, species, duration, loads, sheathing=None):
    """Framing angle or plate (A34, A35, LTP4, LTP5), catalog p. 310, one connector (note 1). loads: {direction: lb}, ASD. Each load
    against the table value for its direction, fasteners, species and load duration; with more than one direction loaded, the unity
    equation (p. 23 note e, p. 289 Option 1). Snow (115) takes the floor (100) value (no snow column in the table). LTP4 / LTP5 over
    wood structural panel sheathing with the tabulated fasteners: 3/8 in. x 0.72, 1/2 in. x 0.64 (note 3)."""
    if species not in ("DF/SP", "SPF/HF"):
        raise SimpsonError("framing angle: the species group is DF/SP or SPF/HF")
    if duration not in ANGLE_DURATIONS:
        raise SimpsonError("framing angle: the load duration is floor (100), snow (115), roof (125) or wind or earthquake (160)")
    loads = {k: v for k, v in loads.items() if v}
    if not loads or min(loads.values()) < 0:
        raise SimpsonError("framing angle: give at least one load (zero or more)")
    if any(r[0] == model for r in ANGLES_A + ANGLES_HL):
        if sheathing:
            raise SimpsonError("framing angle: the over-sheathing factors of note 3 are for LTP4 and LTP5")
        return _angle_a_hl(model, config, species, duration, loads)
    lang = any(r[0] == model for r in ANGLES_L)
    if lang:                                                # p. 313: rows as (model, 9, fasteners, direction, DF/SP, SPF/HF)
        if config != 9:
            raise SimpsonError(f"framing angle: {model} is an L, LS or GA angle (catalog p. {ANGLE_L_PAGE}); use type 9")
        rows_m = [(r[0], 9, r[1], r[3], r[4], r[5]) for r in ANGLES_L if r[0] == model]
    else:
        rows_m = [r for r in ANGLES if r[0] == model and r[1] == config]
    if not rows_m:
        raise SimpsonError(f"framing angle: configuration {config} is not tabulated for {model} on catalog p. {ANGLE_PAGE}")
    fopts = []
    for r in rows_m:
        if r[2] not in fopts:
            fopts.append(r[2])
    keys = {"nails": ("0.131 x 1 1/2", "0.148 x 1 1/2"), "3 in. nails": ("0.148 x 3",), "sd": ("sd",), "ph612i": ("ph612i",)}.get(
        (fasteners or "nails").strip().lower(), ((fasteners or "").strip().lower(),))
    fast = next((f for f in fopts if any(k.lower() in f.lower() for k in keys)), None)
    if fast is None:
        raise SimpsonError(f"framing angle: {model} in configuration {config} is tabulated with {' or '.join(fopts)}")
    col = ANGLE_DURATIONS[duration] if not lang else {"floor (100)": 0, "snow (115)": 1, "roof (125)": 2,
                                                       "wind or earthquake (160)": 3}[duration]
    factor = 1.0
    if sheathing:
        if model not in ("LTP4", "LTP5"):
            raise SimpsonError("framing angle: the over-sheathing factors of note 3 are for LTP4 and LTP5")
        factor = {"3/8": 0.72, "1/2": 0.64}[sheathing]
    rows, unity = [], 0.0
    for dname, dem in loads.items():
        r = next((x for x in rows_m if x[2] == fast and dname.lower() in x[3].lower().split("/")), None)
        if r is None:
            dirs = sorted({x[3] for x in rows_m if x[2] == fast})
            raise SimpsonError(f"framing angle: {model} in configuration {config} with {fast} has no {dname} value (directions: {', '.join(dirs)})")
        cap = (r[4] if species == "DF/SP" else r[5])[col] * factor
        rows.append((dname if "/" in r[3] else r[3], dem, cap)); unity += dem / cap
    if len(rows) > 1:
        rows.append(("loads together, sum of load / allowable", unity, 1.0))
    return dict(model=model, config=config, fast=fast, species=species, duration=duration, factor=factor, rows=rows,
                directions=sorted({d_ for x in rows_m if x[2] == fast for d_ in x[3].split("/")}),
                page=ANGLE_L_PAGE if lang else ANGLE_PAGE, L=next((x[2] for x in ANGLES_L if x[0] == model), None) if lang else None)


# ---------------------------------------------------------------- MPBZ moment post base (catalog pp. 88-89)
# Catalog p. 89, row by row (tests find each row in the page text). Key: (concrete "nonreinforced" / "reinforced", "A&B" / "C-F").
# Row: model, post, W1/W2, D, H (in.), SDS screws, concrete uplift (uncracked, cracked), lateral F1 (uncracked, cracked), moment M
# (uncracked, cracked) (lb, ft-lb); wood assembly DF/SP download (100), download (160), moment (160); rotational stiffness (in.-lb/rad).
_MPB_WOOD = {"MPB44Z": (6240, 6410, 1520, 1245000), "MPB66Z": (9360, 10855, 3730, 2405000), "MPB88Z": (15120, 17690, 4560, 5515000)}
_MPB_GEO = {"MPB44Z": ("4x4", "3 9/16", "7 1/4", "7 1/4", '(16) 1/4" x 2 1/2"'), "MPB66Z": ("6x6", "5 9/16", "7 1/4", "7 1/4", '(24) 1/4" x 2 1/2"'),
            "MPB88Z": ("8x8", "7 9/16", "7 1/4", "7 1/4", '(36) 1/4" x 3"')}
MPBZ = {
    ("nonreinforced", "A&B"): {"MPB44Z": (4900, 3820, 1750, 1225, 1350, 945), "MPB66Z": (5815, 5815, 3435, 2405, 2680, 1875),
                               "MPB88Z": (11860, 9315, 7200, 5560, 4160, 2910)},
    ("nonreinforced", "C-F"): {"MPB44Z": (4785, 3350, 1535, 1075, 1180, 830), "MPB66Z": (5815, 5815, 3015, 2110, 2055, 1645),
                               "MPB88Z": (10155, 8165, 6965, 4875, 3470, 2550)},
    ("reinforced", "A&B"): {"MPB44Z": (4900, 3820, 1750, 1225, 1520, 1520), "MPB66Z": (5815, 5815, 3435, 2405, 3730, 3190),
                            "MPB88Z": (11860, 9315, 7200, 5560, 4560, 4560)},
    ("reinforced", "C-F"): {"MPB44Z": (4785, 3350, 1535, 1075, 1520, 1520), "MPB66Z": (5815, 5815, 3015, 2110, 3350, 2795),
                            "MPB88Z": (10155, 8165, 6965, 4875, 4560, 4560)},
}
MPBZ_PAGE = 89
# Minimum side cover (in.) and the reinforced footing details, catalog p. 88: MPB44Z 4 in., 12 in. square, (4) #4 vertical at 8 in. out to
# out; MPB66Z 5 in., 16 in. square, (4) #4 at 12 in.; MPB88Z (p. 89) 6 in., 20 in. square, (4) #5 at 16 in.; #4 ties at 3 in., square and diamond.
MPBZ_COVER = {"MPB44Z": (4, 12, "(4) #4", 8), "MPB66Z": (5, 16, "(4) #4", 12), "MPB88Z": (6, 20, "(4) #5", 16)}


def mpbz(model, post, concrete, cracked, sdc, download=0.0, uplift=0.0, lateral=0.0, moment=0.0, down_short=False):
    """MPBZ moment post base, catalog p. 89 (ASD; loads not increased for duration, note 1; f'c 2,500 psi or more, note 3). Each
    allowable is the lesser of the wood assembly and the concrete (note 8): download from the wood assembly ((100), or (160) for a wind or
    seismic download), uplift and lateral from the concrete, moment the lesser of both. Loads together by note 9: (uplift / allowable
    uplift, or download / allowable download) + moment / allowable moment + lateral / allowable lateral <= 1.0. model "first that works":
    the base for the post size (one per size)."""
    download, uplift, lateral, moment = (abs(x or 0.0) for x in (download, uplift, lateral, moment))
    if download and uplift:
        raise SimpsonError("MPBZ: download and uplift are separate load combinations; check them on separate sheets")
    if not (download or uplift or lateral or moment):
        raise SimpsonError("MPBZ: give a load")
    key = (concrete, sdc)
    if key not in MPBZ:
        raise SimpsonError("MPBZ: concrete is nonreinforced or reinforced; seismic design category A&B (and wind) or C-F")
    if model.strip().lower() in ("first that works", "lightest that works"):
        model = next((m for m, g in _MPB_GEO.items() if g[0] == post), None)
        if model is None:
            raise SimpsonError(f"MPBZ: made for 4x4, 6x6 and 8x8 posts (catalog p. {MPBZ_PAGE})")
        picked = True
    else:
        model = model.strip().upper()
        if model not in _MPB_GEO:
            raise SimpsonError(f"MPBZ: {model} is not on catalog p. {MPBZ_PAGE}")
        if post and _MPB_GEO[model][0] != post:
            raise SimpsonError(f"MPBZ: {model} is for a {_MPB_GEO[model][0]} post")
        picked = False
    c_ = MPBZ[key][model]
    k = 1 if cracked else 0
    w = _MPB_WOOD[model]
    al = dict(uplift=c_[0 + k], lateral=c_[2 + k], moment=min(c_[4 + k], w[2]), download=w[1] if down_short else w[0])
    rows, unity = [], 0.0
    for nm, dem in (("download", download), ("uplift", uplift), ("moment", moment), ("lateral F1", lateral)):
        if dem:
            cap = al[nm.split()[0]]
            rows.append((nm, dem, cap)); unity += dem / cap
    if len(rows) > 1:
        rows.append(("loads together (note 9)", unity, 1.0))
    return dict(model=model, post=_MPB_GEO[model][0], geo=_MPB_GEO[model], conc=c_, wood=w, allow=al, rows=rows, picked=picked,
                concrete=concrete, cracked=cracked, sdc=sdc, cover=MPBZ_COVER[model], moment_gov="wood" if w[2] <= c_[4 + k] else "concrete")


def page_of(series):
    return {"BC": BC_PAGE, "AC": AC_PAGE, "CCQ": CCQ_PAGE, "ECCQ": CCQ_PAGE}.get(series, COLUMN_CAP_PAGE)


# ---------------------------------------------------------------- CBSTQ / CBSQ cast-in column bases (catalog pp. 84-85)
# Catalog p. 85: model, post, base ga, strap, W1, W2, D, H (in.), SDS screws, uplift (uncracked, cracked) for wind and SDC A&B, the same for
# SDC C-F, download (100), lb. (The p. 85 A&B block prints the 6x6 model as "CBSQT66Z-SDS2"; the C-F block "CBSTQ66Z-SDS2".)
COLUMN_BASES = [
    ("CBSTQ44Z-SDS2", "4x4", 12, '10 ga. x 2 1/4"', "3 9/16", "3 1/2", "7 1/8", "8 3/8", "(14) 1/4 x 2 SDS", (5390, 4650), (5390, 4070), 12840),
    ("CBSTQ46Z-SDS2", "4x6", 12, '10 ga. x 3"', "3 9/16", "5 5/16", "7 13/16", "8 11/16", "(14) 1/4 x 2 SDS", (5390, 4650), (5390, 4070), 16850),
    ("CBSTQ66Z-SDS2", "6x6", 12, '10 ga. x 3"', "5 1/2", "5 1/2", "6 7/8", "8 3/4", "(14) 1/4 x 2 SDS", (4375, 3060), (3830, 2680), 19335),
    ("CBSQ86-SDS2", "6x8", 12, '7 ga. x 3"', "7 1/2", "5 3/8", "6 1/8", "8 11/16", "(12) 1/4 x 2 SDS", (3815, 2670), (3340, 2335), 20915),
    ("CBSQ88-SDS2", "8x8", 12, '7 ga. x 3"', "7 1/2", "7 3/8", "6 1/8", "8 11/16", "(12) 1/4 x 2 SDS", (3815, 2670), (3340, 2335), 22225),
]
COLUMN_BASE_PAGE = 85
CBSTQ_LATERAL = (485, 1270)              # p. 85 note 5: F1, F2 for all CBSTQ models, 3 in. minimum side cover


def column_base(post, model, cracked, sdc, download=0.0, uplift=0.0, F1=0.0, F2=0.0):
    """Cast-in column base CBSTQ / CBSQ, DF/SP, catalog p. 85 (ASD; no duration increase, note 1; f'c 2,500 psi or more, note 3). Uplift by
    concrete cracked or uncracked and SDC; download (100); lateral F1 and F2 for the CBSTQ models only (note 5). More than one direction
    loaded: the unity equation (p. 23 note e, p. 289 Option 1). model "first that works": the base for the post size."""
    download, uplift, F1, F2 = (abs(x or 0.0) for x in (download, uplift, F1, F2))
    if download and uplift:
        raise SimpsonError("column base: download and uplift are separate load combinations; check them on separate sheets")
    if not (download or uplift or F1 or F2):
        raise SimpsonError("column base: give a load")
    if sdc not in ("A&B", "C-F"):
        raise SimpsonError("column base: seismic design category A&B (and wind) or C-F")
    if model.strip().lower() in ("first that works", "lightest that works"):
        r = next((x for x in COLUMN_BASES if x[1] == post), None)
        if r is None:
            raise SimpsonError(f"column base: made for 4x4, 4x6, 6x6, 6x8 and 8x8 posts (catalog p. {COLUMN_BASE_PAGE})")
        picked = True
    else:
        r = next((x for x in COLUMN_BASES if x[0].lower() == model.strip().lower()), None)
        if r is None:
            raise SimpsonError(f"column base: {model} is not on catalog p. {COLUMN_BASE_PAGE}")
        if post and r[1] != post:
            raise SimpsonError(f"column base: {r[0]} is for a {r[1]} post")
        picked = False
    cbstq = r[0].startswith("CBSTQ")
    if (F1 or F2) and not cbstq:
        raise SimpsonError(f"column base: lateral values are given for the CBSTQ models only (catalog p. {COLUMN_BASE_PAGE} note 5)")
    up_a = (r[9] if sdc == "A&B" else r[10])[1 if cracked else 0]
    rows = []
    for nm, dem, cap in (("download", download, r[11]), ("uplift", uplift, up_a), ("lateral F1", F1, CBSTQ_LATERAL[0]),
                         ("lateral F2", F2, CBSTQ_LATERAL[1])):
        if dem:
            rows.append((nm, dem, cap))
    if len(rows) > 1:
        rows.append(("loads together, sum of load / allowable", sum(d / c for _, d, c in rows), 1.0))
    return dict(row=r, rows=rows, picked=picked, cracked=cracked, sdc=sdc, cbstq=cbstq, uplift_allow=up_a)


# ---------------------------------------------------------------- cast-in post and column bases: CB, PB, PBST, EPB (catalog pp. 80-87)
# One row per model in a common form: model, nominal post, series, page, W1, W2, embedment D and height H drawn (in.), standoff (in.),
# fasteners, uplift wind and SDC A&B (uncracked, cracked), uplift SDC C-F (uncracked, cracked), download (100), lateral {fastening: (F1, F2)}
# or None, minimum side cover (in.), gauge text, bolts available. Loads, lb. D and H of CB, PB and EPB are the figures' dimensions (pp. 80, 82,
# 86), drawn only.
def _cb(model, post, w1, w2, bolt, ab_u, ab_c, cf_u, cf_c, down):
    strap = 7 if model[2] in "456" else 3
    base = 3 if model.startswith("CB1") and len(model) > 4 and model[2:4] in ("10", "12") else 7
    return dict(model=model, post=post, series="CB", page=87, W1=w1, W2=w2, D="8", H="6" if bolt == "5/8" else "7 1/2", standoff=0,
                fast=f'(2) {bolt}" dia. bolts', AB=(ab_u, ab_c), CF=(cf_u, cf_c), down=down, lat=None, cover=3,
                ga=f"strap {strap} ga, base {base} ga", bolts=True, nails=False, kind="strap")


CAST_BASES = [
    _cb("CB44", "4x4", "3 9/16", "3 9/16", "5/8", 6110, 4510, 5640, 3945, 19020),
    _cb("CB46", "4x6", "3 9/16", "5 1/2", "5/8", 6110, 4510, 5640, 3945, 28585),
    _cb("CB48", "4x8", "3 9/16", "7 1/2", "5/8", 6110, 4510, 5640, 3945, 35970),
    _cb("CB5-4.5", "Glulam", "4 1/2", "5 1/8", "5/8", 6110, 4510, 5640, 3945, 38055),
    _cb("CB5-6", "Glulam", "6", "5 1/8", "5/8", 6110, 4510, 5640, 3945, 50740),
    _cb("CB64", "6x4", "5 1/2", "3 9/16", "5/8", 6110, 4510, 5640, 3945, 28585),
    _cb("CB66", "6x6", "5 1/2", "5 1/2", "5/8", 6110, 4510, 5640, 3945, 30250),
    _cb("CB6-7", "6x", "5 1/2", "7", "5/8", 6110, 4510, 5640, 3945, 38500),
    _cb("CB68", "6x8", "5 1/2", "7 1/2", "5/8", 6110, 4510, 5640, 3945, 41250),
    _cb("CB610", "6x10", "5 1/2", "9 1/2", "5/8", 6445, 4510, 5640, 3945, 52250),
    _cb("CB612", "6x12", "5 1/2", "11 1/2", "5/8", 6445, 4510, 5640, 3945, 63250),
    _cb("CB7 1/8-4", "PSL", "7 1/8", "3 1/2", "3/4", 6445, 4510, 5640, 3945, 41145),
    _cb("CB7 1/8-6", "PSL", "7 1/8", "5 1/2", "3/4", 6445, 4510, 5640, 3945, 64660),
    _cb("CB7 1/8-7", "PSL", "7 1/8", "7", "3/4", 6445, 4510, 5640, 3945, 78410),
    _cb("CB7-6", "Glulam", "6", "6 3/4", "3/4", 6445, 4510, 5640, 3945, 66825),
    _cb("CB7-7.5", "Glulam", "7 1/2", "6 3/4", "3/4", 6445, 4510, 5640, 3945, 79345),
    _cb("CB7-9", "Glulam", "9", "6 3/4", "3/4", 6445, 4510, 5640, 3945, 91620),
    _cb("CB7-10.5", "Glulam", "10 1/2", "6 3/4", "3/4", 6445, 4510, 5640, 3945, 103790),
    _cb("CB86", "8x6", "7 1/2", "5 1/2", "3/4", 6110, 4510, 5640, 3945, 41250),
    _cb("CB88", "8x8", "7 1/2", "7 1/2", "3/4", 6445, 4510, 5640, 3945, 56250),
    _cb("CB810", "8x10", "7 1/2", "9 1/2", "3/4", 6445, 4510, 5640, 3945, 71250),
    _cb("CB812", "8x12", "7 1/2", "11 1/2", "3/4", 6445, 4510, 5640, 3945, 86250),
    _cb("CB9-6", "Glulam", "6", "8 3/4", "3/4", 6445, 4510, 5640, 3945, 81940),
    _cb("CB9-7.5", "Glulam", "7 1/2", "8 3/4", "3/4", 6445, 4510, 5640, 3945, 97165),
    _cb("CB9-9", "Glulam", "9", "8 3/4", "3/4", 6445, 4510, 5640, 3945, 112200),
    _cb("CB9-10.5", "Glulam", "10 1/2", "8 3/4", "3/4", 6445, 4510, 5640, 3945, 127105),
    _cb("CB1010", "10x10", "9 1/2", "9 1/2", "3/4", 6445, 4510, 5640, 3945, 90250),
    _cb("CB1012", "10x12", "9 1/2", "11 1/2", "3/4", 6445, 4510, 5640, 3945, 109250),
    _cb("CB1212", "12x12", "11 1/2", "11 1/2", "3/4", 6445, 4510, 5640, 3945, 132250),
]
for _m, _p, _w, _l, _b, _d in (("PB44", "4x4", "3 9/16", "3 1/4", False, 12685), ("PB44R", "Rough 4x4", "4", "3 1/4", False, 12685),
                               ("PB46", "4x6", "5 1/2", "3 1/4", False, 22445), ("PB66", "6x6", "5 1/2", "5 1/4", True, 25270),
                               ("PB66R", "Rough 6x6", "6", "5 1/4", True, 25270)):
    CAST_BASES.append(dict(model=_m, post=_p, series="PB", page=82, W1=_w, W2=_l, D="3 1/4", H="5", standoff=0,
                           fast="(12) 0.162 x 3 1/2 nails" + ('; or (2) 1/2" dia. bolts' if _b else ""), AB=(850, 850), CF=(850, 850), down=_d,
                           lat={"nails": (765, 1325), "bolts": (765, 1325)}, cover=2, ga="12 ga", bolts=_b, nails=True, kind="strap"))
for _m, _p, _s, _w, _l, _h, ab, cf, _d in (("PBST44Z", "4x4", 14, "3 9/16", "3 1/2", "6 1/4", (1235, 865), (1080, 755), 9570),
                                           ("PBST46Z", "4x6", 14, "3 9/16", "5 7/16", "6 9/16", (1235, 865), (1080, 755), 10170),
                                           ("PBST66Z", "6x6", 12, "5 1/2", "5 3/8", "6 1/2", (2165, 2165), (2165, 2165), 11815)):
    CAST_BASES.append(dict(model=_m, post=_p, series="PBST", page=83, W1=_w, W2=_l, D="5" if "66" in _m else "3 1/2", H=_h, standoff=1,
                           fast='(14) 0.162 x 3 1/2 nails; or (2) 1/2" dia. bolts', AB=ab, CF=cf, down=_d,
                           lat={"nails": (1165, 835), "bolts": (230, 835)}, cover=2, ga=f"base 12 ga, strap {_s} ga", bolts=True, nails=True,
                           kind="strap"))
for _m, _p, _w, _l, _h, _n, ab, cf, _d, lat in (("EPB44A", "4x4", "3 9/16", "3", "2 3/8", 8, (1075, 755), (940, 660), 2670, (695, 795)),
                                                ("EPB44", "4x4", "3 9/16", "3 1/4", "2 5/16", 8, (995, 695), (870, 605), 5165, (850, 965)),
                                                ("EPB46", "4x6", "5 1/2", "3 5/16", "3", 12, (995, 695), (870, 605), 5165, (850, 965)),
                                                ("EPB66", "6x6", "5 1/2", "5 1/2", "3", 12, (995, 695), (870, 605), 5165, (850, 965))):
    CAST_BASES.append(dict(model=_m, post=_p, series="EPB", page=80, W1=_w, W2=_l, D="6", H=_h, standoff=2,
                           fast=f"({_n}) 0.162 x 3 1/2 nails", AB=ab, CF=cf, down=_d, lat={"nails": lat}, cover=4,
                           ga="14 ga" if _m == "EPB44A" else "12 ga base, 1-5/16 in. OD pipe", bolts=False, nails=True, kind="pipe"))
for _r in COLUMN_BASES:
    CAST_BASES.append(dict(model=_r[0], post=_r[1], series="CBSTQ / CBSQ", page=85, W1=_r[4], W2=_r[5], D=_r[6], H=_r[7], standoff=1,
                           fast=_r[8] + " screws", AB=_r[9], CF=_r[10], down=_r[11],
                           lat={"nails": CBSTQ_LATERAL} if _r[0].startswith("CBSTQ") else None, cover=3 if _r[0].startswith("CBSTQ") else 2,
                           ga=f"base {_r[2]} ga, strap {_r[3]}", bolts=False, nails=True, kind="strap"))
CAST_SERIES = ["CBSTQ / CBSQ", "CB", "PB", "PBST", "EPB"]


def cast_base(series, post, model, cracked, sdc, download=0.0, uplift=0.0, F1=0.0, F2=0.0, fastening="nails"):
    """Cast-in post or column base (CBSTQ / CBSQ p. 85, CB p. 87, PB p. 82, PBST p. 83, EPB p. 80), ASD, no duration increase. Uplift by
    concrete cracked or uncracked and the seismic design category; download (100); lateral F1, F2 where the catalog gives them (CBSTQ note 5,
    PB note 6, PBST note 9 by nails or bolts, EPB table); more than one direction by the unity equation (p. 23 note e, p. 289 Option 1).
    "first that works": the first base of the series for the post that passes."""
    download, uplift, F1, F2 = (abs(x or 0.0) for x in (download, uplift, F1, F2))
    if download and uplift:
        raise SimpsonError("post base: download and uplift are separate load combinations; check them on separate sheets")
    if not (download or uplift or F1 or F2):
        raise SimpsonError("post base: give a load")
    if sdc not in ("A&B", "C-F"):
        raise SimpsonError("post base: seismic design category A&B (and wind) or C-F")
    if series not in CAST_SERIES:
        raise SimpsonError("post base: the series is " + ", ".join(CAST_SERIES))
    bolts = str(fastening or "").lower().startswith("bolt")
    cands = [r for r in CAST_BASES if r["series"] == series]

    def check(r):
        if bolts and not r["bolts"]:
            return None
        if not bolts and not r["nails"]:
            return None                                       # CB: bolts only
        if (F1 or F2) and not r["lat"]:
            return None
        rows = []
        up_a = (r["AB"] if sdc == "A&B" else r["CF"])[1 if cracked else 0]
        lat = r["lat"][("bolts" if bolts else "nails") if r["lat"] and len(r["lat"]) > 1 else "nails"] if r["lat"] else (None, None)
        for nm, dem, cap in (("download", download, r["down"]), ("uplift", uplift, up_a), ("lateral F1", F1, lat[0]), ("lateral F2", F2, lat[1])):
            if dem:
                rows.append((nm, dem, cap))
        if len(rows) > 1:
            rows.append(("loads together, sum of load / allowable", sum(d / c for _, d, c in rows), 1.0))
        return rows, up_a, lat

    if model.strip().lower() in ("first that works", "lightest that works"):
        if post in ("Glulam", "PSL", "6x"):
            raise SimpsonError(f"post base: name the {series} model for a {post} column (its width and depth set the base)")
        fit = [r for r in cands if r["post"] == post]
        if not fit:
            raise SimpsonError(f"post base: no {series} base for a {post} post (catalog p. {cands[0]['page']})")
        for r in fit:
            c_ = check(r)
            if c_ and all(d <= c + 1e-9 for _, d, c in c_[0]):
                break
        else:
            raise SimpsonError(f"post base: no {series} base for a {post} post carries these loads" + (" with bolts" if bolts else ""))
        picked = True
    else:
        r = next((x for x in cands if x["model"].lower() == model.strip().lower()), None)
        if r is None:
            raise SimpsonError(f"post base: {model} is not a {series} base")
        if post and r["post"] not in (post, "Glulam", "PSL", "6x") and r["post"] != post:
            raise SimpsonError(f"post base: {r['model']} is for a {r['post']} post")
        c_ = check(r)
        if c_ is None:
            why = ("it is not tabulated with bolts" if bolts and not r["bolts"] else "it is fastened with bolts" if not r["nails"] and not bolts
                   else "the catalog gives it no lateral value")
            raise SimpsonError(f"post base: {r['model']}: {why} (catalog p. {r['page']})")
        picked = False
    rows, up_a, lat = c_
    return dict(base=r, rows=rows, picked=picked, cracked=cracked, sdc=sdc, uplift_allow=up_a, lat=lat, bolts=bolts)
