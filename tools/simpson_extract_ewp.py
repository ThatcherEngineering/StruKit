"""Read the I-joist, glulam and SCL hanger tables of the Simpson Strong-Tie catalog C-C-2026 into data files.

    python tools/simpson_extract_ewp.py <path to C-C-2026.pdf>

Face-Mount Hangers - I-Joists, Glulam and SCL, catalog pp. 158-164 -> strukit/data/simpson_ewp_facemount.json: actual joist size, model,
gauge, I-joist compatible, web stiffener required, W, H, B, min./max. nailing, face and joist fasteners, uplift (160, DF/SP), downloads floor
(100), snow (115), roof (125) for a DF/SP and an SPF/HF species header.
Top-Flange Hangers - I-Joists, Glulam and SCL, catalog pp. 198-206 -> strukit/data/simpson_ewp_topflange.json: the same through TF, header
and joist fasteners, uplift (160), and the download by header type: LVL, PSL, LSL, DF/SP, SPF/HF, DF/SCL I-joist.
Columns are found from the table header words; joist size groups from the rule lines in the size column. Only the numbers are written.
"""
import json
import re
import sys

FACE = dict(name="ewp_facemount", pages=range(158, 165), title="Face-Mount Hangers - I-Joists, Glulam and SCL, pp. 158-164",
            loads=["uplift", "df_floor", "df_snow", "df_roof", "spf_floor", "spf_snow", "spf_roof"])
TOP = dict(name="ewp_topflange", pages=range(198, 207), title="Top-Flange Hangers - I-Joists, Glulam and SCL, pp. 198-206",
           loads=["uplift", "LVL", "PSL", "LSL", "DF/SP", "SPF/HF", "DF/SCL I-joist"])


def frac(t):
    t = t.replace("⁄", "/").strip()
    if " to " in t:                                       # a range (adjustable): the smaller value
        t = t.split(" to ")[0]
    v = 0.0
    for part in t.split():
        if "/" in part:
            a, b = part.split("/")
            v += float(a) / float(b)
        else:
            v += float(part)
    return v


def num(t):
    t = t.strip()
    if re.fullmatch(r"\d\.\d{3}", t):                      # a period printed for the thousands comma (p. 198, "2.985")
        t = t.replace(".", "")
    t = t.replace(",", "")
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


FACE["cols"] = ["size", "model", "ga", "ijc", "stiff", "W", "H", "B", "minmax", "face", "joist"] + FACE["loads"]
TOP["cols"] = ["size", "model", "ga", "ijc", "stiff", "W", "H", "B", "TF", "face", "joist"] + TOP["loads"]


def page_rows(pg, page_no, spec):
    """Columns from the table's vertical rule lines (each drawn the full height of the table); rows from the words' tops; joist size
    groups from the horizontal rules in the size column."""
    import collections
    ws = pg.extract_words()
    cnt = collections.Counter(round(e["x0"]) for e in pg.edges if e["orientation"] == "v" and e["top"] > 60 and 40 < e["x0"] < 600)
    top_n = max(cnt.values())
    xs = sorted(x for x, n in cnt.items() if n >= 0.45 * top_n)
    bounds = []
    for x in xs:
        if not bounds or x - bounds[-1] > 3:
            bounds.append(x)
    cols = spec["cols"]
    if len(bounds) < len(cols) + 1:
        raise ValueError(f"p. {page_no}: {len(bounds)} column rules for {len(cols)} columns")
    bounds = bounds[:len(cols) + 1]
    def col(xc):
        for k, (a, b) in enumerate(zip(bounds, bounds[1:])):
            if a <= xc < b:
                return cols[k]
        return None
    y_head = max(w["bottom"] for w in ws if w["text"] == "(160)")
    body = [w for w in ws if w["top"] > y_head and bounds[1] - 2 < w["x0"] and w["x1"] < bounds[-1] + 2]
    lines, cur, last_top = {}, None, None
    for w in sorted(body, key=lambda w: w["top"]):
        if cur is None or w["top"] - last_top > 3.0:
            cur = len(lines); lines[cur] = []
        last_top = w["top"]; lines[cur].append(w)
    sx0, sx1 = bounds[0], bounds[1]
    seps = sorted(set(round(e["top"], 1) for e in pg.edges if e["orientation"] == "h" and e["x0"] < sx0 + 5 and e["x1"] <= sx1 + 2
                      and e["x1"] - e["x0"] > 10 and e["top"] > y_head - 2))
    labels = [w for w in ws if sx0 - 2 < w["x0"] and w["x1"] < sx1 + 2 and w["top"] > y_head
              and re.fullmatch(r"[\d/⁄xX]+|to|Double|Triple|LAM", w["text"])]
    def group(y, depth=0):
        lo = max([s_ for s_ in seps if s_ <= y + 1] or [0.0]); hi = min([s_ for s_ in seps if s_ > y + 1] or [9999.0])
        lab = [w for w in labels if lo <= w["top"] < hi]
        out_, rest = [], sorted(lab, key=lambda w: w["top"])
        while rest:
            t0 = rest[0]["top"]
            line = [w for w in rest if w["top"] - t0 < 6]
            rest = [w for w in rest if w["top"] - t0 >= 6]
            out_ += sorted(line, key=lambda w: w["x0"])
        out = re.sub(r"\s+", " ", " ".join(w["text"] for w in out_).replace("⁄", "/")).strip()
        if not out and labels and depth == 0:
            near = min(labels, key=lambda w: abs(w["top"] - y))
            return group(near["top"], 1) if abs(near["top"] - y) < 40 else out
        return out
    models = []
    for key in sorted(lines):
        mw = [w for w in lines[key] if col((w["x0"] + w["x1"]) / 2) == "model"]
        if mw:
            models.append((min(w["top"] for w in mw), " ".join(w["text"] for w in sorted(mw, key=lambda w: w["x0"]))))
    rows, last_model = [], None
    allcells = []
    for key in sorted(lines):
        cells = {}
        for w in sorted(lines[key], key=lambda w: w["x0"]):
            c_ = col((w["x0"] + w["x1"]) / 2)
            if c_ and c_ != "model":
                cells.setdefault(c_, []).append(w["text"])
        allcells.append((min(w["top"] for w in lines[key]), {k: " ".join(v) for k, v in cells.items()}))
    spans = [(t, c_) for t, c_ in allcells if num(c_.get(spec["loads"][1], "")) is None]   # cells set once between a min. and a max. row
    for top0, cells in allcells:
        if num(cells.get(spec["loads"][1], "")) is None:
            continue
        near_s = [c_ for t, c_ in spans if abs(t - top0) < 9]
        for c_ in near_s:
            for k_, v_ in c_.items():
                cells.setdefault(k_, v_)
        near = [m for m in models if abs(m[0] - top0) < 9]
        model = min(near, key=lambda m: abs(m[0] - top0))[1] if near else last_model
        if not model or not all(cells.get(k) for k in ("W", "H", "B")):
            continue
        for k_ in ("W", "H", "B", "TF"):                   # "59/16" printed for 5 9/16 (p. 205, HGLTV6)
            if cells.get(k_):
                cells[k_] = re.sub(r"\b(\d)(\d+)/(\d+)\b", lambda m: f"{m[1]} {m[2]}/{m[3]}" if int(m[1] + m[2]) > int(m[3]) else m[0],
                                   cells[k_].replace("⁄", "/"))
        last_model = model
        ga_ = cells.get("ga", "").replace("•", "").strip() or ("14" if model.startswith("HU") else "")   # U 16 ga, HU / HUC 14 ga (p. 156)
        r = dict(page=page_no, joist=group(top0 + 3), model=model, ga=ga_, stiff="\uf0fc" in cells.get("stiff", ""),
                 W=frac(cells["W"]), H=frac(cells["H"]), B=frac(cells["B"]), W_text=cells["W"], H_text=cells["H"],
                 nailing=cells.get("minmax", "").replace("—", "").strip(), TF=frac(cells["TF"]) if cells.get("TF") else None,
                 header=cells.get("face", "").replace("⁄", "/"), joist_fast=cells.get("joist", "").replace("⁄", "/"))
        for k in spec["loads"]:
            r[k] = num(cells.get(k, ""))
        rows.append(r)
    for k, r in enumerate(rows):                          # a row set on its group's rule line: take the neighbour's group when the widths fit
        if not _fits(r) and k + 1 < len(rows) and _fits(dict(r, joist=rows[k + 1]["joist"])):
            r["joist"] = rows[k + 1]["joist"]
    return rows


def _fits(r):
    lab = r["joist"].replace(" LAM", "")
    m = re.match(r"(Double|Triple) (.*)", lab)
    k = 1
    if m:
        k, lab = (2 if m[1] == "Double" else 3), m[2]
    try:
        jw = frac(lab.split(" x ")[0].replace("x", "")) * k
    except ValueError:
        return True
    return -0.01 <= r["W"] - jw <= 0.4


def main(path):
    import pdfplumber
    pdf = pdfplumber.open(path)
    for spec in (FACE, TOP):
        rows = []
        for p in spec["pages"]:
            rows += page_rows(pdf.pages[p - 1], p, spec)
        with open(f"strukit/data/simpson_{spec['name']}.json", "w") as f:
            json.dump(dict(source="Simpson Strong-Tie catalog C-C-2026, " + spec["title"], rows=rows), f, indent=0)
        print(spec["name"], len(rows), "rows")


if __name__ == "__main__":
    main(*sys.argv[1:])
