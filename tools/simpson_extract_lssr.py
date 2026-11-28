"""Read the Simpson LSSR / LSU slopeable / skewable rafter hanger tables (catalog C-C-2026 p. 178 sloped only, p. 179 skewed or sloped
and skewed) into strukit/data/simpson_ewp_slope.json.

Usage: python tools/simpson_extract_lssr.py <path to C-C-2026.pdf>
The page text (pdftotext -layout) is read line by line. A line with a face and a joist fastener schedule and eight loads is one row; its
model is the model number on the nearest line (each LSSR prints its model on the middle one of its three fastener schedules; each LSU on
its own line). Gauge, H and A are printed once per group of models and are carried from the line that holds them."""
import json, os, re, subprocess, sys

PAGES = {178: "sloped", 179: "skewed"}
FAST = re.compile(r"(\(\d+\) (?:SD ?# ?9|[\d.]+) x \d+(?: \d+/\d+)?)\s+(\(\d+\) (?:SD ?# ?9|[\d.]+) x \d+(?: \d+/\d+)?)\s+([\d,]+(?:\s+[\d,]+){7})(?:\s+[A-Za-z©—].*)?\s*$")
MODEL = re.compile(r"(LSSR[\d.]+(?:-2)?Z|LSU3510-2|LSU\d\.\d\d)")
WIDTH = {"LSSR1.81Z": "1 3/4", "LSSR2.1Z": "2 to 2 1/16", "LSSR2.37Z": "2 5/16", "LSSR2.56Z": "2 1/2", "LSSR210-2Z": "3", "LSSR410Z": "3 1/2",
         "LSU4.12": "Dbl 2", "LSU4.28": "Dbl 2 1/16", "LSU3510-2": "Dbl 2 5/16", "LSU5.12": "Dbl 2 1/2"}


def page_text(pdf, p):
    t = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-"], capture_output=True, text=True).stdout
    return t.replace("⁄", "/").splitlines()


def main(pdf):
    out = []
    for p, table in PAGES.items():
        lines = page_text(pdf, p)
        lines = lines[:next(i for i, l in enumerate(lines) if l.strip().startswith("1. Uplift"))]      # the table, not its notes
        models = [(i, MODEL.search(l).group(1)) for i, l in enumerate(lines) if MODEL.search(l)]
        rows = [(i, FAST.search(l)) for i, l in enumerate(lines) if FAST.search(l)]
        k = 0
        for i_m, mdl in models:                                       # in page order: an LSSR takes the next three schedules, an LSU its own line
            n = 1 if mdl.startswith("LSU") else 3
            grp = rows[k:k + n]
            k += n
            if not (grp[0][0] <= i_m <= grp[-1][0]):
                raise SystemExit(f"p. {p} {mdl}: its model line {i_m} is not within its schedules {[g[0] for g in grp]}")
            for i, m in grp:
                nums = [float(x.replace(",", "")) for x in m.group(3).split()]
                face = re.sub(r"SD ?# ?9", "SD #9", m.group(1))
                jf = re.sub(r"SD ?# ?9", "SD #9", m.group(2))
                out.append(dict(page=p, table=table, model=mdl, joist=WIDTH[mdl], header=face, joist_fast=jf,
                                uplift=nums[0], df_floor=nums[1], df_snow=nums[2], df_roof=nums[3],
                                uplift_spf=nums[4], spf_floor=nums[5], spf_snow=nums[6], spf_roof=nums[7]))
        if k != len(rows):
            raise SystemExit(f"p. {p}: {len(rows) - k} schedules left over")
    # gauge and dimensions: printed once per group (p. 178 and 179 alike)
    dims = {"LSSR1.81Z": ("18", "1 13/16", "8 15/16", "4 1/8"), "LSSR2.1Z": ("18", "2 1/8", "8 15/16", "4 1/8"),
            "LSSR2.37Z": ("18", "2 3/8", "8 15/16", "4 1/8"), "LSSR2.56Z": ("18", "2 9/16", "8 15/16", "4 1/8"),
            "LSSR210-2Z": ("16", "3 1/8", "8 15/16", "5 1/8"), "LSSR410Z": ("16", "3 5/8", "8 15/16", "5 1/8"),
            "LSU4.12": ("14", "4 1/8", "9", "2 1/4"), "LSU4.28": ("14", "4 1/4", "9", "2 3/8"),
            "LSU3510-2": ("14", "4 3/4", "8 7/8", "3 5/8"), "LSU5.12": ("14", "5 1/8", "9", "2 1/4")}
    f = lambda t: sum(float(eval(x)) for x in t.split())
    for r in out:
        ga, W, H, A = dims[r["model"]]
        r.update(ga=ga, W_text=W, W=f(W), H_text=H, H=f(H), A=f(A), B=f(A), nailing="", TF=None, stiff=True,
                 code=("IBC, FL, LA" if r["header"].split(") ")[1] in ("0.148 x 2 1/2", "0.162 x 2 1/2") else "—"))
    for mdl in WIDTH:
        for p in PAGES:
            n = sum(1 for r in out if r["model"] == mdl and r["page"] == p)
            want = 1 if mdl.startswith("LSU") else 3
            if n != want:
                raise SystemExit(f"p. {p} {mdl}: {n} rows, expected {want}")
    dst = os.path.join(os.path.dirname(__file__), "..", "strukit", "data", "simpson_ewp_slope.json")
    with open(dst, "w") as fh:
        json.dump(dict(source="Simpson Strong-Tie Wood Construction Connectors catalog C-C-2026, pp. 178-179 (LSSR / LSU slopeable / skewable rafter hangers)",
                       rows=out), fh, indent=0)
    print(len(out), "rows")
    for r in out:
        print(r["page"], f"{r['joist']:12s} {r['model']:11s} {r['ga']} {r['W_text']:8s} {r['header']:22s} {r['joist_fast']:22s} {r['code']:12s}",
              [r[k] for k in ("uplift", "df_floor", "df_snow", "df_roof", "uplift_spf", "spf_floor", "spf_snow", "spf_roof")])


if __name__ == "__main__":
    main(sys.argv[1])
