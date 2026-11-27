"""Read the face-mount joist hanger tables of the Simpson Strong-Tie Wood Construction Connectors catalog C-C-2026 into a data file.

    python tools/simpson_extract.py <path to C-C-2026.pdf> [facemount | topflange] [out.json]

Pages read (catalog page numbers): 114 to 118, Face-Mount Hangers - Solid Sawn Lumber (DF/SP); 119 to 123, the same for SPF/HF.
Each table row: joist size group, model, gauge, W, H, B, min./max. nailing, header and joist fasteners, allowable loads (lb) for
uplift (160), floor (100), snow (115) and roof (125) load duration. The joist size groups are read from the rule lines drawn in the
size column. The catalog is not copied into the repository; only the numbers of these rows are written, with their page.
"""
import json
import re
import sys

TABLES = {
    "facemount": ("Face-Mount Hangers - Solid Sawn Lumber, pp. 114-123", [(p, "DF/SP") for p in range(114, 119)] + [(p, "SPF/HF") for p in range(119, 124)]),
    "topflange": ("Top-Flange Hangers - Solid Sawn Lumber, pp. 142-146", [(p, "DF/SP") for p in range(142, 145)] + [(p, "SPF/HF") for p in range(145, 147)]),
}
COLS = ["size", "model", "ga", "W", "H", "B", "minmax", "header", "joist", "uplift", "floor", "snow", "roof", "ici"]
HEAD = {"Size": "size", "Model": "model", "Ga.": "ga", "W": "W", "H": "H", "B": "B", "TF": "TF", "Min./": "minmax", "Header": "header",
        "Uplift": "uplift", "Floor": "floor", "Snow": "snow", "Roof": "roof", "Installed": "ici"}


def frac(t):
    """'1 9/16' or '1 9⁄16' or '7' to a float."""
    t = t.replace("⁄", "/").strip()
    if " to " in t:                                       # a range (adjustable width): the smaller value
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
    t = t.replace(",", "").strip()
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


def page_rows(pg, species, page_no):
    words = pg.extract_words(keep_blank_chars=False)
    hdr = {}
    joist_x = []
    y_head = 0.0
    ym = min(w["top"] for w in words if w["text"] == "Model")
    for w in words:
        if abs(w["top"] - ym) > 25:                       # the table header only (not the Hanger Selector badge)
            continue
        if w["text"] in ("Uplift", "Floor", "Snow", "Roof", "(160)", "(100)", "(115)", "(125)"):
            y_head = max(y_head, w["bottom"])
        if w["text"] in HEAD and HEAD[w["text"]] not in hdr:
            hdr[HEAD[w["text"]]] = (w["x0"] + w["x1"]) / 2
        if w["text"] == "Joist":
            joist_x.append((w["x0"] + w["x1"]) / 2)
    joist_x.sort()
    hdr["size"] = joist_x[0]
    hdr["joist"] = joist_x[-1]
    if "ici" not in hdr:
        hdr["ici"] = hdr["roof"] + 30
    centers = sorted((x, k) for k, x in hdr.items())
    def col(xc, x0=None):
        if x0 is not None and size_r - 8 < x0 < hdr["ga"] - 12:   # model names are set flush left in their column
            return "model"
        return min(centers, key=lambda q: abs(q[0] - xc))[1]
    # size groups: rule lines across the size column
    size_r = min(w["x0"] for w in words if w["top"] > y_head and re.fullmatch(r"[A-Z]+\d.*", w["text"]) and w["x0"] > hdr["size"]) - 2
    seps = sorted(set(round(l["top"], 1) for l in pg.lines if abs(l["top"] - l["bottom"]) < 0.6 and l["x0"] < size_r and l["x1"] < size_r + 8
                      and l["x1"] - l["x0"] > 10))
    labels = [w for w in words if (w["x0"] + w["x1"]) / 2 < size_r and w["top"] > y_head and re.fullmatch(r"(DBL|TPL|QUAD|\d+[xX]\d+)", w["text"])]
    def group(y):
        lo = max([s for s in seps if s <= y] or [0.0]); hi = min([s for s in seps if s > y] or [9999.0])
        lab = sorted([w for w in labels if lo <= w["top"] < hi], key=lambda w: w["top"])
        return " ".join(w["text"] for w in lab).upper().replace("X", "x"), (lo, hi)
    lines, cur, last_top = {}, None, None                 # rows: words whose tops lie within 3.5 pt of the row's first word
    for w in sorted([w for w in words if w["top"] > y_head and size_r - 8 < w["x0"] and (w["x0"] + w["x1"]) / 2 < hdr["roof"] + 18],
                    key=lambda w: w["top"]):
        if cur is None or w["top"] - last_top > 3.0:
            cur = len(lines)
            lines[cur] = []
        last_top = w["top"]
        lines[cur].append(w)
    mcol = [w for w in words if w["top"] > y_head and col((w["x0"] + w["x1"]) / 2, w["x0"]) == "model"]
    mlines, cur_ = [], None                                # model names: one line each (a two-row model sits between its rows)
    for w in sorted(mcol, key=lambda w: (round(w["top"]), w["x0"])):
        if cur_ is not None and abs(w["top"] - cur_["top"]) < 3.5:
            cur_["text"] += " " + w["text"]
        else:
            cur_ = dict(top=w["top"], text=w["text"]); mlines.append(cur_)
    rows, last_model = [], None
    for key in sorted(lines):
        ws = sorted(lines[key], key=lambda w: w["x0"])
        cells = {}
        for w in ws:
            c = col((w["x0"] + w["x1"]) / 2, w["x0"])
            cells.setdefault(c, []).append(w["text"])
        cells = {k: " ".join(v) for k, v in cells.items()}
        if num(cells.get("floor", "")) is None or (num(cells.get("uplift", "")) is None and cells.get("uplift", "").strip() != "—"):
            continue
        top0 = min(w["top"] for w in ws)
        near = [m for m in mlines if abs(m["top"] - top0) < 10.5]
        if not all(cells.get(k_) for k_ in ("W", "H", "B")):
            print("skipped (no dimensions):", page_no, " | ".join(f"{k}={v}" for k, v in cells.items()), file=sys.stderr)
            continue
        model = (min(near, key=lambda m: abs(m["top"] - top0))["text"] if near else "") or last_model
        if not model:
            continue
        last_model = model
        top = min(w["top"] for w in ws)
        g, _ = group(top)
        rows.append(dict(species=species, page=page_no, joist=g, model=model, ga=int(num(cells.get("ga", "0")) or 0),
                         W=frac(cells["W"]), H=frac(cells["H"]), B=frac(cells["B"]), W_text=cells["W"].replace("⁄", "/"), nailing=cells.get("minmax", "—").replace("—", "").strip(),
                         TF=frac(cells["TF"]) if cells.get("TF") else None,
                         header=cells.get("header", ""), joist_fast=cells.get("joist", ""), uplift=num(cells["uplift"]) or 0.0, floor=num(cells["floor"]),
                         snow=num(cells["snow"]), roof=num(cells["roof"])))
    return rows


def main(path, which="facemount", out=None):
    import pdfplumber
    pdf = pdfplumber.open(path)
    title, pages = TABLES[which]
    rows = []
    for page_no, species in pages:
        rows += page_rows(pdf.pages[page_no - 1], species, page_no)
    with open(out or f"strukit/data/simpson_{which}.json", "w") as f:
        json.dump(dict(source="Simpson Strong-Tie catalog C-C-2026, " + title, rows=rows), f, indent=0)
    print(len(rows), "rows")


if __name__ == "__main__":
    main(*sys.argv[1:])
