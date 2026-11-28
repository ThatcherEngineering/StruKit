"""Read the Simpson SUR/SUL/HSUR/HSUL skewed 45-degree hanger table (catalog C-C-2026 p. 175) into strukit/data/simpson_ewp_skew.json.

Usage: python tools/simpson_extract_skew.py <path to C-C-2026.pdf>
Words are read with pdfplumber; each line holding a model number is one row. The web-stiffener column prints a Wingdings check mark
(required) or a dash (not required). The joist size is the text left of the model column on the row's line or, for sizes printed over
two lines or centred on a pair of models, the nearest size text above and below within the row's band."""
import json, os, re, sys
import pdfplumber

PAGE = 175
MODEL = re.compile(r"^H?SUR/L[\d./-]+$")


def mixed(tokens, i):
    """A dimension starting at tokens[i]: '9', '1 5/8' or '5/16'. Returns (value, text, next i)."""
    t = tokens[i]
    if "/" in t:
        a, b = t.split("/")
        return int(a) / int(b), t, i + 1
    v = int(t)
    if i + 1 < len(tokens) and "/" in tokens[i + 1] and not tokens[i + 1].startswith("("):
        a, b = tokens[i + 1].split("/")
        return v + int(a) / int(b), t + " " + tokens[i + 1], i + 2
    return float(v), t, i + 1


def main(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    p = pdf.pages[PAGE - 1]
    chars = p.chars
    words = p.extract_words(keep_blank_chars=False, use_text_flow=False, extra_attrs=["fontname"])
    for w in words:
        w["text"] = w["text"].replace("\u2044", "/")                  # fraction slash
    words = [w for w in words if 60 < w["x0"] < 570]                 # not the vertical side tabs and copyright text
    lines, cur = {}, None                                            # lines: words whose tops are within 2.5 pt (fractions sit a little high)
    for w in sorted(words, key=lambda w: w["top"]):
        if cur is None or w["top"] - cur > 2.5:
            cur = w["top"]
        lines.setdefault(cur, []).append(w)
    keys = sorted(lines)
    model_x = None
    rows = []
    left = []                                                       # (top, text) of the size column
    for k in keys:
        ws = sorted(lines[k], key=lambda w: w["x0"])
        m = next((w for w in ws if MODEL.match(w["text"])), None)
        if m is not None:
            model_x = m["x0"]
    for k in keys:
        ws = sorted(lines[k], key=lambda w: w["x0"])
        lt = " ".join(w["text"] for w in ws if w["x1"] < model_x - 2)
        if lt and 100 < k < 760:
            left.append((k, lt))
    for k in keys:
        ws = sorted(lines[k], key=lambda w: w["x0"])
        m = next((w for w in ws if MODEL.match(w["text"])), None)
        if m is None:
            continue
        after = [w for w in ws if w["x0"] > m["x1"]]
        stiff_chars = [c for c in chars if abs(c["top"] - m["top"]) < 3 and m["x1"] < c["x0"] < m["x1"] + 40]
        stiff = any("Wingdings" in c["fontname"] for c in stiff_chars)
        toks = [w["text"] for w in after if "Wingdings" not in w["fontname"] and w["text"] != "—"]
        ga = toks[0]
        i = 1
        dims = []
        while len(dims) < 5:
            v, t, i = mixed(toks, i)
            dims.append((v, t))
        rest = " ".join(toks[i:])
        fm = re.match(r"(\(\d+\) [\d.]+ x [\d /]+?) (\(\d+\) [\d.]+ x \d+(?: \d+/\d+)?) (.*)$", rest)
        if fm is None:
            print("FAIL", m["text"], m["top"], toks); continue
        face, joist_f, loads = fm.group(1), fm.group(2), fm.group(3)
        nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\d|\d", loads)]
        if len(nums) != 8:
            raise SystemExit(f"p. {PAGE} {m['text']}: {len(nums)} loads: {loads}")
        rows.append(dict(top=m["top"], model=m["text"], ga=ga, stiff=stiff, dims=dims, face=face, joist_fast=joist_f, nums=nums))
    # sizes: the size text on the row's line, else the size text nearest the row (above or below) within half a row pitch on each side
    out = []
    for r in rows:
        near = sorted((k, t) for (k, t) in left if abs(k - r["top"]) <= 8)       # a size over one or two lines, or centred on a pair of rows
        if near:
            size = " ".join(t for k, t in near)
        else:
            cand = sorted(((abs(k - r["top"]), k, t) for (k, t) in left if abs(k - r["top"]) <= 12))
            if not cand:
                raise SystemExit(f"p. {PAGE} {r['model']}: no size")
            size = cand[0][2]
        (W, Wt), (H, Ht), (B, Bt), (A1, _), (A2, _) = r["dims"]
        n = r["nums"]
        out.append(dict(page=PAGE, joist=re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", size)).strip(), model=r["model"], ga=r["ga"], stiff=r["stiff"], W=W, H=H, B=B,
                        W_text=Wt, H_text=Ht, A1=A1, A2=A2, nailing="", TF=None, header=r["face"], joist_fast=r["joist_fast"],
                        uplift=n[0], df_floor=n[1], df_snow=n[2], df_roof=n[3], uplift_spf=n[4], spf_floor=n[5], spf_snow=n[6], spf_roof=n[7]))
    dst = os.path.join(os.path.dirname(__file__), "..", "strukit", "data", "simpson_ewp_skew.json")
    with open(dst, "w") as f:
        json.dump(dict(source="Simpson Strong-Tie Wood Construction Connectors catalog C-C-2026, p. 175 (SUR/SUL/HSUR/HSUL skewed 45-degree hangers)",
                       rows=out), f, indent=0)
    print(len(out), "rows")
    for r in out:
        print(f"{r['joist']:30s} {r['model']:15s} {r['ga']:3s} {'stiff' if r['stiff'] else '-':5s} W {r['W_text']:7s} H {r['H_text']:8s} B {r['B']:g} "
              f"{r['header']:20s} {r['joist_fast']:20s} {r['uplift']:g} {r['df_floor']:g} {r['df_snow']:g} {r['df_roof']:g} | {r['uplift_spf']:g} {r['spf_floor']:g} {r['spf_snow']:g} {r['spf_roof']:g}")


if __name__ == "__main__":
    main(sys.argv[1])
