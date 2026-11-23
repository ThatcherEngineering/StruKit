"""Build strukit/data/glm5000_columns.csv from the text of Boise Cascade's Glulam Specifier
Guide GLM-5000 (pdftotext -layout), "BOISE GLULAM Column Tables", Combination 3 Column Grade.
Each number is assigned to the nearest 100% / 115% / 125% heading by its position on the
line, so blank cells stay blank. Usage: python tools/parse_glm5000.py GLM-5000.txt"""
import csv, re, sys

FR = {"⅛": 0.125, "½": 0.5, "¾": 0.75}


def inches(t):
    m = re.match(r"(\d+)([⅛½¾]?)", t)
    return int(m.group(1)) + FR.get(m.group(2), 0.0)


L = open(sys.argv[1], encoding="utf8").read().split("\n")
out = {}
i = 0
while i < len(L):
    if L[i].count("100%") >= 1 and "115%" in L[i] and "Length" not in L[i]:
        heads = [(m.start() + 2, m.group(0)) for m in re.finditer(r"1(?:00|15|25)%", L[i])]
        sizes = re.findall(r"(\d+[⅛½¾]?)\"\s*x\s*(\d+[⅛½¾]?)\"", L[i - 1])
        assert len(heads) == 3 * len(sizes), (i, heads, sizes)
        j = i + 1
        while j < len(L):
            m = re.match(r"^\s*(\d{1,2})(\s|$)", L[j])
            if not m:
                if L[j].strip() == "":
                    j += 1
                    if j < len(L) and not re.match(r"^\s*\d{1,2}(\s|$)", L[j]):
                        break
                    continue
                break
            length = int(m.group(1))
            for t in re.finditer(r"[\d,]{4,}", L[j][m.end():]):
                val = int(t.group(0).replace(",", ""))
                centre = m.end() + (t.start() + t.end()) / 2
                k = min(range(len(heads)), key=lambda q: abs(heads[q][0] - centre))
                b, d = sizes[k // 3]
                out[(inches(b), inches(d), length, heads[k][1])] = val
            j += 1
        i = j
    else:
        i += 1
rows = sorted(out.items())
with open("strukit/data/glm5000_columns.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["b_in", "d_in", "length_ft", "duration", "P_lb"])
    for (b, d, ln, dur), v in rows:
        w.writerow([b, d, ln, dur, v])
print(len(rows), sorted({(b, d) for (b, d, _, _) in out}))
