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
    t = t.replace(",", "").strip()
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


def header_cols(ws, spec):
    ym = min(w["top"] for w in ws if w["text"] == "Model")
    hdr = {}
    load_words = []
    for w in ws:
        if not (ym - 30 < w["top"] < ym + 30):
            continue
        xc = (w["x0"] + w["x1"]) / 2
        t = w["text"]
        if t in ("Ga.",):
            hdr["ga"] = xc
        elif t == "Stiff":
            hdr["stiff"] = xc
        elif t in ("W", "H", "B", "TF"):
            hdr[t] = xc
        elif t == "Min./":
            hdr["minmax"] = xc
        elif t in ("Face", "Header") and abs(w["top"] - max(x["top"] for x in ws if x["text"] in ("W", "H")) ) < 4:
            hdr["face"] = xc
        elif t == "Joist" and w["top"] > ym:
            hdr["joist"] = xc if xc > 200 else hdr.get("joist")
        elif t in ("Uplift", "Floor", "Snow", "Roof", "LVL", "PSL", "LSL", "DF/SP", "SPF/HF", "DF/SCL") and w["top"] > ym:
            load_words.append((xc, t))
        elif t == "Actual":
            hdr["size"] = xc
    load_words.sort()
    for (xc, _), key in zip(load_words, spec["loads"]):
        hdr[key] = xc
    hdr = {k: v for k, v in hdr.items() if v is not None}
    y_head = max(w["bottom"] for w in ws if w["text"] in ("(160)",) and ym - 30 < w["top"] < ym + 40)
    return hdr, y_head


def page_rows(pg, page_no, spec):
    ws = pg.extract_words()
    hdr, y_head = header_cols(ws, spec)
    model_x = min(w["x0"] for w in ws if w["text"] == "Model") - 40
    size_r = model_x
    centers = sorted((x, k) for k, x in hdr.items() if k != "size")
    col = lambda xc: min(centers, key=lambda q: abs(q[0] - xc))[1]
    last_load = spec["loads"][-1]
    body = [w for w in ws if w["top"] > y_head and w["x0"] > size_r and (w["x0"] + w["x1"]) / 2 < hdr[last_load] + 14]
    lines, cur, last_top = {}, None, None
    for w in sorted(body, key=lambda w: w["top"]):
        if cur is None or w["top"] - last_top > 3.0:
            cur = len(lines); lines[cur] = []
        last_top = w["top"]; lines[cur].append(w)
    sx = hdr["size"]
    seps = sorted(set(round(e["top"], 1) for e in pg.edges if e["orientation"] == "h" and e["x1"] <= sx + 25 and e["x0"] < sx - 5
                      and e["x1"] - e["x0"] > 10 and e["top"] > y_head - 2))
    labels = [w for w in ws if sx - 25 < w["x0"] and w["x1"] < sx + 25 and w["top"] > y_head and re.fullmatch(r"[\d/⁄xX]+|to|\(\d\)|DBL|TPL|Double|Triple", w["text"])]
    def group(y):
        lo = max([s_ for s_ in seps if s_ <= y + 1] or [0.0]); hi = min([s_ for s_ in seps if s_ > y + 1] or [9999.0])
        lab = [w for w in labels if lo <= w["top"] < hi]
        if lab:                                           # label lines: words within 6 pt of a line's first word, each line left to right
            out_, rest = [], sorted(lab, key=lambda w: w["top"])
            while rest:
                t0 = rest[0]["top"]
                line = [w for w in rest if w["top"] - t0 < 6]
                rest = [w for w in rest if w["top"] - t0 >= 6]
                out_ += sorted(line, key=lambda w: w["x0"])
            lab = out_
        out = re.sub(r"\s+", " ", " ".join(w["text"] for w in lab).replace("⁄", "/")).strip()
        if not out and labels:                            # a row on a rule line: the group whose label is nearest
            near = min(labels, key=lambda w: abs(w["top"] - y))
            return group(near["top"]) if abs(near["top"] - y) < 40 and abs(near["top"] - y) > 0.5 else out
        return out
    models = []
    for key in sorted(lines):
        ws_ = [w for w in lines[key] if w["x0"] < hdr["ga"] - 12]
        if ws_:
            models.append((min(w["top"] for w in ws_), " ".join(w["text"] for w in sorted(ws_, key=lambda w: w["x0"]))))
    rows, last_model = [], None
    for key in sorted(lines):
        ws_ = sorted(lines[key], key=lambda w: w["x0"])
        cells = {}
        for w in ws_:
            if w["x0"] < hdr["ga"] - 12:
                continue
            c_ = col((w["x0"] + w["x1"]) / 2)
            if "TF" in hdr and c_ == "TF" and w["x0"] > hdr["TF"] + 9:     # fastener text set just right of TF belongs to the header column
                c_ = "face"
            cells.setdefault(c_, []).append(w["text"])
        cells = {k: " ".join(v) for k, v in cells.items()}
        if num(cells.get(spec["loads"][1], "")) is None:
            continue
        top0 = min(w["top"] for w in ws_)
        near = [m for m in models if abs(m[0] - top0) < 9]
        model = min(near, key=lambda m: abs(m[0] - top0))[1] if near else last_model
        if not model or not all(cells.get(k) for k in ("W", "H", "B")):
            continue
        model = re.sub(r"^([\d/⁄]+\s*)+", "", model).strip() or last_model   # a label number set into the model column
        m_ = re.fullmatch(r"(.+?) (\d+)", cells.get("W", ""))
        if m_ and re.match(r"\d+[/⁄]\d+", cells.get("H", "")):     # a whole number of H set close to W ("5 3/8 7 1/2 to 32 1/2")
            cells["W"], cells["H"] = m_[1], m_[2] + " " + cells["H"]
        for k_ in ("W", "H", "B", "TF"):                   # "59/16" printed for 5 9/16 (p. 205, HGLTV6)
            if cells.get(k_):
                cells[k_] = re.sub(r"\b(\d)(\d+/\d+)\b", lambda m: m[1] + " " + m[2] if int(m[2].split("/")[0]) < int(m[2].split("/")[1]) else m[0], cells[k_])
        last_model = model
        r = dict(page=page_no, joist=group(top0), model=model, ga=cells.get("ga", ""), stiff="" in cells.get("stiff", ""),
                 W=frac(cells["W"]), H=frac(cells["H"]), B=frac(cells["B"]), W_text=cells["W"].replace("⁄", "/"), H_text=cells["H"].replace("⁄", "/"),
                 nailing=cells.get("minmax", "").replace("—", "").strip(), TF=frac(cells["TF"]) if cells.get("TF") else None,
                 header=cells.get("face", "").replace("⁄", "/"), joist_fast=cells.get("joist", "").replace("⁄", "/"))
        for k in spec["loads"]:
            r[k] = num(cells.get(k, ""))
        rows.append(r)
    return rows


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
