"""Build strukit/data/ijoists.csv from the text of ICC-ES ESR-1336 (Boise BCI joists,
Tables 2 and 3) and ESR-1153 (Weyerhaeuser TJI joists, Table 3).
Usage: python tools/parse_ijoists.py ESR-1336.txt ESR-1153.txt

BCI: only the series in Boise's West Specifier Guide MTP-W7000 are kept (5000-1.7,
6000-1.8, 6500-1.8, 60-2.0, 90-2.0); joist weights are from that guide. "" = not permitted
without web stiffeners."""
import csv, re, sys

DEP = {"9 1/2": 9.5, "11 7/8": 11.875}
KEEP = {"5000-1.7": "5000", "6000-1.8": "6000", "6500-1.8": "6500", "60-2.0": "60", "90-2.0": "90"}
WEIGHT = {("5000-1.7", 9.5): 2.0, ("5000-1.7", 11.875): 2.3, ("5000-1.7", 14): 2.5,
          ("6000-1.8", 9.5): 2.2, ("6000-1.8", 11.875): 2.5, ("6000-1.8", 14): 2.7, ("6000-1.8", 16): 2.9,
          ("6500-1.8", 9.5): 2.3, ("6500-1.8", 11.875): 2.6, ("6500-1.8", 14): 3.0, ("6500-1.8", 16): 3.2,
          ("60-2.0", 11.875): 2.9, ("60-2.0", 14): 3.1, ("60-2.0", 16): 3.3,
          ("90-2.0", 11.875): 3.9, ("90-2.0", 14): 4.1, ("90-2.0", 16): 4.4, ("90-2.0", 18): 4.6, ("90-2.0", 20): 4.8}


def groups(lines, n_min):
    out, cur, labs = [], [], []
    for ln in lines:
        m = re.match(r"^\s*(?:[\dSE, ]*?\s{2,})?(9 1/2|11 7/8|14|16|18|20|22|24)\s{3,}(.*)$", ln)
        found = re.findall(r"\b(\d{2,4}S?-\d\.\d)\b", ln)
        toks = None
        if m:
            rest = re.sub(r"\b\d{2,4}S?-\d\.\d\b", " ", m.group(2))
            toks = [t for t in rest.split() if re.fullmatch(r"[\d.]+|N/A", t)]
            if len(toks) < n_min:
                toks = None
        if toks:
            d = DEP.get(m.group(1)) or float(m.group(1))
            if cur and d <= cur[-1][0]:
                out.append((labs, cur)); cur, labs = [], []
            cur.append((d, toks))
        labs += found
    out.append((labs, cur))
    return out


L = open(sys.argv[1], encoding="utf8").read().split("\n")
t2 = next(i for i, x in enumerate(L) if "TABLE 2—REFERENCE DESIGN VALUES FOR BCI" in x)
t3 = next(i for i, x in enumerate(L) if "TABLE 3—REFERENCE DESIGN REACTION VALUES" in x)
t4 = next(i for i, x in enumerate(L) if "TABLE 4—BLOCKING PANELS" in x)
prop = {}
for labs, rows in groups(L[t2:t3], 12):
    assert len(labs) == 3, labs
    for k, lab in enumerate(labs):
        for d, t in rows:
            prop[(lab, d)] = [float(x) for x in t[4 * k:4 * k + 4]]           # moment, EI, K, shear
fam_order = ["40", "45", "50", "60", "65", "90", "4000", "4500", "5000", "6000", "6500", "9000", "90E"]
rg = groups(L[t3:t4], 4)
assert len(rg) == len(fam_order), len(rg)
react = {}
for fam, (_, rows) in zip(fam_order, rg):
    for d, t in rows:
        react[(fam, d)] = ["" if x == "N/A" else x for x in t[:4]]              # 1.5 in no/yes, 3.5 in no/yes
rows = []
for ser, fam in KEEP.items():
    for (lab, d), (M, EI, K, V) in sorted(prop.items(), key=lambda kv: kv[0][1]):
        if lab == ser and (ser, d) in WEIGHT:
            r = react[(fam, d)]
            rows.append(["BCI", ser, d, WEIGHT[(ser, d)], M, V, EI, K * 1e6, 1.5] + r + ["ICC-ES ESR-1336 Tables 2 and 3"])

T = open(sys.argv[2], encoding="utf8").read().split("\n")
a = next(i for i, x in enumerate(T) if "TABLE 3—REFERENCE DESIGN VALUES FOR TJI" in x)
ser = None
pending = None
for ln in T[a:a + 70]:
    m = re.match(r"^\s*TJI (\d+D?)\s*$", ln)
    if m:
        ser = m.group(1); continue
    ln2 = ln.replace("91/2", "9.5").replace("117/8", "11.875")
    t = ln2.split()
    if ser and len(t) == 15 and re.fullmatch(r"[\d.]+", t[0]) and float(t[0]) < 8:   # the row whose depth printed on its own lines
        t = ["11.875"] + t
    if ser and len(t) == 16 and re.fullmatch(r"[\d.]+", t[0]):
        d, w, M, V, EI, K = (float(x) for x in t[:6])
        na = lambda x: "" if x == "NA" else x
        rows.append(["TJI", ser, d, w, M, V, EI, K * d * 1e5, 1.75, na(t[6]), na(t[7]), na(t[8]), na(t[9]), "ICC-ES ESR-1153 Table 3"])
with open("strukit/data/ijoists.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product", "series", "depth", "weight_plf", "M", "V", "EI_e6", "K_shear_lb", "short_bearing_in", "Re_short", "Re_short_ws",
                "Re_35", "Re_35_ws", "source"])
    w.writerows(rows)
print(len(rows), sum(r[0] == "BCI" for r in rows), sum(r[0] == "TJI" for r in rows))
