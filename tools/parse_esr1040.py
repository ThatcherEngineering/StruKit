"""Build strukit/data/esr1040_table1.csv from the text of ICC-ES ESR-1040 (Versa-Lam LVL),
Table 1. Usage: python tools/parse_esr1040.py ESR-1040.txt"""
import csv, re, sys
rows = []
pat = re.compile(r"^\s*(\d\.\dE \d{4}(?:/\d{4})?)\s+(\d\.\d)\s+(\d\.\dE? \d{4}9?(?:/\d{4})?)\s+(\d\.\d)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")
for ln in open(sys.argv[1], encoding="utf8"):
    m = pat.match(ln)
    if m:
        g = [x.replace(",", "") for x in m.groups()]
        perp_plank = "610" if g[8] == "61010" else g[8]          # "610" with footnote mark 10
        rows.append([g[0], g[1], g[3], g[4], g[5], g[6], g[7], perp_plank, g[9], g[10], g[11]])
assert len(rows) == 38, len(rows)
with open("strukit/data/esr1040_table1.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["grade", "E_true_e6", "E_apparent_e6", "Fb_joist", "Fb_plank", "Ft", "Fc", "Fc_perp_plank", "Fc_perp_joist", "Fv_plank", "Fv_joist"])
    w.writerows(rows)
print(len(rows), rows[0], rows[28])
