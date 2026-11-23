"""Build StruKit's wood data files from the text of the 2018 NDS Supplement."""
import csv, re, sys
src, out = sys.argv[1], sys.argv[2]
L = open(src, encoding="utf-8").read().split("\n")
# ---- Table 4A: lines between its first data page and the Table 4B adjustment factors
a = next(i for i, l in enumerate(L) if l.startswith("Table 4A        Reference Design Values"))
b = next(i for i, l in enumerate(L) if l.startswith("Table 4B Adjustment Factors"))
num = r"[\d,]+"
row = re.compile(rf"^\s*([A-Z][A-Za-z0-9 .&/\-]*?)\s{{2,}}(?:\S.*?\s{{2,}})?({num})\s+({num})\s+({num})\s+({num})\s+({num})\s+({num})\s+({num})(?:\s|$)")
species, rows = None, []
for l in L[a:b]:
    t = l.strip()
    if re.fullmatch(r"[A-Z][A-Z \-()./]+(\d)?", t) and "TABLE" not in t and "COUNCIL" not in t and "REFERENCE DES" not in t \
            and "DESIGN VALUES" not in t and "USE WITH" not in t and len(t) > 3 and not t.startswith("AMERICAN") \
            and t not in ("NELMA", "NLGA", "NSLB", "SPIB", "WCLIB", "WWPA", "NHLA", "RIS"):
        species = re.sub(r"\d$", "", t).strip()
        continue
    m = row.match(l)
    if m and species:
        g = m.group(1).strip()
        v = [int(x.replace(",", "")) for x in m.groups()[1:]]
        if v[5] >= 500000:                                   # E column is always large
            rows.append([species, g] + v)
with open(out + "/nds2018_table4a.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["species", "grade", "Fb", "Ft", "Fv", "Fc_perp", "Fc", "E", "Emin"]); w.writerows(rows)
print(len(rows), "rows;", len({r[0] for r in rows}), "species")
for sp in sorted({r[0] for r in rows}):
    print("  ", sp, [r[1] for r in rows if r[0] == sp])
# ---- Table 1B: nominal and dressed sizes
a = next(i for i, l in enumerate(L) if l.startswith("Table 1B       Section Properties of Standard Dressed"))
b = next(i for i, l in enumerate(L) if l.startswith("Table 1C") and i > a + 50)
def frac(s):
    s = s.strip()
    if "-" in s:
        w, f = s.split("-"); n, d = f.split("/"); return int(w) + int(n) / int(d)
    if "/" in s:
        n, d = s.split("/"); return int(n) / int(d)
    return float(s)
sec, group = [], None
pat = re.compile(r"^\s*(\d+)\s*x\s*(\d+)\s+([\d\-/]+)\s*x\s*([\d\-/]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")
for l in L[a:b]:
    t = l.strip()
    for key, name in (("Boards", "board"), ("Dimension Lumber", "dimension"), ("Post and Timber", "post and timber"), ("Beams and Stringers", "beam and stringer")):
        if t.startswith(key):
            group = name
    m = pat.match(l)
    if m and group:
        sec.append([group, f"{m.group(1)}x{m.group(2)}", frac(m.group(3)), frac(m.group(4)), float(m.group(5)), float(m.group(6)), float(m.group(7))])
with open(out + "/nds2018_table1b.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["group", "nominal", "b", "d", "A", "Sxx", "Ixx"]); w.writerows(sec)
print(len(sec), "sections", {g: sum(1 for s in sec if s[0] == g) for g in {s[0] for s in sec}})
