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
CAP_SERIES = ["CC", "ECC", "ECCU", "BC"]


def cap_models(series):
    if series == "BC":
        return [r[0] for r in BC_CAPS]
    pre = {"CC": "", "ECC": "E", "ECCU": "E"}[series]
    suf = "U" if series == "ECCU" else ""
    out = []
    for r in COLUMN_CAPS:                                    # ECC / ECCU models carry the CC size: ECC44, ECCU44 (p. 100)
        size = r[0][2:]
        out.append((pre + "CC" + (("U" + size) if suf else size)) if series != "CC" else r[0])
    return out


def _cap_row(series, model):
    if series == "BC":
        return next((r for r in BC_CAPS if r[0].lower() == model.strip().lower()), None)
    for r, m in zip(COLUMN_CAPS, cap_models(series)):
        if m.lower().replace(" ", "") == model.strip().lower().replace(" ", ""):
            return r
    return None


def column_cap(series, model, download=0.0, uplift=0.0, lateral=0.0, beam_width=None, post_width=None, beam_depth=None,
               spliced=False, download2=0.0):
    """Column or post cap, DF/SP. CC / ECC / ECCU (catalog p. 101): download (100) and uplift (160) from the table; ECC has no uplift
    value (p. 101: ECCU is the end cap rated for uplift); the beam at least as deep as H1 (note 7). A CC at a beam splice over the post
    (p. 73 note l): each spliced beam not over half the table download and not over 2 x the other beam's download; uplift and lateral
    values do not apply. BC (p. 93): uplift and lateral (both 160); no download value (the beam bears on the post); spliced beams not
    permitted (note 4); uplift with lateral by the unity equation (p. 23 note e, p. 289 Option 1). model "first that works": the first
    cap in the table order whose beam and post widths match the typed widths and that passes."""
    download, uplift, lateral, download2 = download or 0.0, uplift or 0.0, lateral or 0.0, download2 or 0.0
    if series not in CAP_SERIES:
        raise SimpsonError("column cap: the series is CC, ECC, ECCU or BC")
    if min(download, uplift, lateral, download2) < 0:
        raise SimpsonError("column cap: loads are zero or more")
    if not (download or uplift or lateral or download2):
        raise SimpsonError("column cap: give a load")
    bc = series == "BC"
    if bc and spliced:
        raise SimpsonError(f"column cap: spliced beams on a BC post cap are not permitted (catalog p. {BC_PAGE} note 4)")
    if spliced and series != "CC":
        raise SimpsonError("column cap: a beam splice over the post is for a CC cap (an end cap carries one beam end)")
    if spliced and (uplift or lateral):
        raise SimpsonError(f"column cap: table uplift and lateral loads do not apply to spliced beams (catalog p. {BASES_NOTES_PAGE} note l)")
    if lateral and not bc:
        raise SimpsonError(f"column cap: the {series} table gives no lateral load (catalog p. {COLUMN_CAP_PAGE})")
    if bc and (download or download2):
        raise SimpsonError(f"column cap: the BC table gives no download (catalog p. {BC_PAGE}); the beam bears on the post, checked on its own sheet")
    page = BC_PAGE if bc else COLUMN_CAP_PAGE

    def fits(r):
        if beam_width is None or post_width is None:
            return False
        if bc:
            return _in(r[1]) - 0.13 <= beam_width <= _in(r[1]) + 0.01 and _in(r[2]) - 0.13 <= post_width <= _in(r[2]) + 0.01
        bws = [_in(x) for x in r[1].split(",")]
        return any(abs(beam_width - b) <= 0.07 for b in bws) and _in(r[3]) - 0.26 <= post_width <= _in(r[3]) + 0.01

    def check(r):
        rows = []
        if bc:
            if uplift:
                rows.append(("uplift", uplift, r[9]))
            if lateral:
                rows.append(("lateral", lateral, r[10]))
            if uplift and lateral:
                rows.append(("loads together, U/Ua + L/La", uplift / r[9] + lateral / r[10], 1.0))
            return rows
        down_a, up_a = {"CC": (r[10], r[9]), "ECC": (r[11], None), "ECCU": (r[13], r[12])}[series]
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
            raise SimpsonError("column cap: give the beam depth (the beam must be at least as deep as H1, p. 101 note 7)")
        tab = BC_CAPS if bc else COLUMN_CAPS
        fit = [r for r in tab if fits(r)]
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
            raise SimpsonError(f"column cap: the ECC table gives no uplift (catalog p. {COLUMN_CAP_PAGE}); use an ECCU end cap")
        picked = False
    mdl = r[0] if bc else cap_models(series)[COLUMN_CAPS.index(r)]
    if bc:
        dims = dict(W1=_in(r[1]), W2=_in(r[2]), L=_in(r[3]), H1=_in(r[5]), H2=_in(r[6]))
    else:
        dims = dict(W1=_in(r[2]), W2=_in(r[3]), L=_in(r[4][CAP_SERIES.index(series)]), H1=_in(r[5]), bolt=_in(r[6]),
                    beam_bolts=r[7][CAP_SERIES.index(series)], post_bolts=r[8])
    return dict(row=r, model=mdl, series=series, rows=rows, picked=picked, dims=dims, page=page)


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
STRAP_KINDS = ["strap tie", "MST", "coiled strap"]


def _count(fast):
    return int(fast.split(")")[0].strip("("))


def strap_models(kind):
    return [r[0] for r in {"strap tie": STRAPS, "MST": MST, "coiled strap": COILS}[kind]]


def strap(kind, model, species, tension, fastening="nails", nail="0.148", nails_per_end=None, clear_span=None):
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
ANGLE_CONFIGS = {1: "A34, joists to plate or beam (fig. 1)", 2: "A35, joist to plate, A leg (fig. 2)", 3: "A35, stud to plate, B leg (fig. 3)",
                 4: "A35, joist to beam or plate, flat (fig. 4)", 5: "A35, blocking to plate (fig. 5)", 6: "A35, to subfloor over sheathing (fig. 6)",
                 7: "LTP4, top plates to rim or blocking (fig. 7)", 8: "LTP5, over the subfloor to rim or blocking (fig. 8)"}
ANGLE_DURATIONS = {"floor (100)": 0, "snow (115), floor value": 0, "roof (125)": 1, "wind or earthquake (160)": 2}


def angle_models():
    out = []
    for r in ANGLES:
        if r[0] not in out:
            out.append(r[0])
    return out


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
    rows_m = [r for r in ANGLES if r[0] == model and r[1] == config]
    if not rows_m:
        raise SimpsonError(f"framing angle: configuration {config} is not tabulated for {model} on catalog p. {ANGLE_PAGE}")
    fopts = []
    for r in rows_m:
        if r[2] not in fopts:
            fopts.append(r[2])
    fast = next((f for f in fopts if fasteners.strip().lower() in f.lower()), None) if fasteners else fopts[0]
    if fast is None:
        raise SimpsonError(f"framing angle: {model} in configuration {config} is tabulated with {' or '.join(fopts)}")
    col = ANGLE_DURATIONS[duration]
    factor = 1.0
    if sheathing:
        if model not in ("LTP4", "LTP5"):
            raise SimpsonError("framing angle: the over-sheathing factors of note 3 are for LTP4 and LTP5")
        factor = {"3/8": 0.72, "1/2": 0.64}[sheathing]
    rows, unity = [], 0.0
    for dname, dem in loads.items():
        r = next((x for x in rows_m if x[2] == fast and x[3].lower() == dname.lower()), None)
        if r is None:
            dirs = sorted({x[3] for x in rows_m if x[2] == fast})
            raise SimpsonError(f"framing angle: {model} in configuration {config} with {fast} has no {dname} value (directions: {', '.join(dirs)})")
        cap = (r[4] if species == "DF/SP" else r[5])[col] * factor
        rows.append((r[3], dem, cap)); unity += dem / cap
    if len(rows) > 1:
        rows.append(("loads together, sum of load / allowable", unity, 1.0))
    return dict(model=model, config=config, fast=fast, species=species, duration=duration, factor=factor, rows=rows,
                directions=sorted({x[3] for x in rows_m if x[2] == fast}))
