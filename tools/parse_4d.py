"""Table 4D (timbers) of the 2018 NDS Supplement -> rows. Groups of grade rows alternate
Beams and Stringers, Posts and Timbers within a species; each group is confirmed by the
classification label printed beside it."""
import re, sys, csv
L = open(sys.argv[1], encoding="utf-8").read().split("\n")
a = next(i for i, l in enumerate(L) if l.startswith("Table 4D          Reference Design Values"))
b = next(i for i, l in enumerate(L) if l.startswith("Table 4E") and i > a)
num = r"[\d,]+"
row = re.compile(rf"^\s*((?:Dense )?(?:Select Structural|No\. ?[123](?: Dense| SR| & Btr)?|Dense No\. ?[12](?: SR)?|Dense Structural \d+|Dense SS)[A-Za-z0-9 .]*?)\s{{2,}}(.*?)({num})\s+({num})\s+({num})\s+({num})\s+({num})\s+({num})\s+({num})(?:\s|$)")
AG = ("NELMA", "NLGA", "NSLB", "SPIB", "WCLIB", "WWPA", "NHLA", "RIS")
species, groups, cur, marks = None, [], None, ""
def close():
    global cur, marks
    if cur:
        groups.append((species, cur, marks))
    cur, marks = None, ""
for l in L[a:b]:
    t = l.strip()
    if re.fullmatch(r"[A-Z][A-Z \-()./]+", t) and len(t) > 3 and t not in AG and not any(k in t for k in ("TABLE", "COUNCIL", "REFERENCE DES", "DESIGN VALUES", "USE WITH", "AMERICAN")):
        close(); species = t; continue
    m = row.match(l)
    if m and species:
        g = re.sub(r"No\.(\d)", r"No. \1", m.group(1).strip())
        v = [int(x.replace(",", "")) for x in m.groups()[2:]]
        if v[5] < 500000:
            continue
        first = g in ("Select Structural", "Dense Select Structural")
        if cur is None or (first and any(x[0] not in ("Dense Select Structural",) for x in cur)):
            close(); cur = []
        cur.append([g] + v)
        marks += " " + m.group(2)
    elif cur is not None:
        marks += " " + t
close()
out, bad = [], []
last = {}
for sp, rows_, mk in groups:
    bs, pt = ("Beams" in mk or "Stringers" in mk), ("Posts" in mk or "Timbers" in mk)
    if bs == pt:
        bad.append((sp, [r[0] for r in rows_], mk[:60])); continue
    cls = "Beams and Stringers" if bs else "Posts and Timbers"
    for r in rows_:
        out.append([sp, cls] + r)
seen, final, conflicts = {}, [], []
for r in out:
    k = tuple(r[:3])
    if k in seen:
        if seen[k] != r[3:]:
            conflicts.append((k, seen[k], r[3:]))
        continue
    seen[k] = r[3:]; final.append(r)
print(len(final), "rows;", len({r[0] for r in final}), "species; unclassified groups:", len(bad), "; conflicts:", len(conflicts))
for x in bad: print("  BAD", x)
for x in conflicts: print("  CONFLICT", x)
sp_ok = {}
for r in final:
    sp_ok.setdefault(r[0], {}).setdefault(r[1], []).append(r[2])
for sp, d in sorted(sp_ok.items()):
    print(f"  {sp}: " + " | ".join(f"{c.split()[0]}: {', '.join(g)}" for c, d2 in [(c, d[c]) for c in sorted(d)] for g in [d2]))
if len(sys.argv) > 2:
    with open(sys.argv[2], "w", newline="") as f:
        w = csv.writer(f); w.writerow(["species", "classification", "grade", "Fb", "Ft", "Fv", "Fc_perp", "Fc", "E", "Emin"]); w.writerows(final)
