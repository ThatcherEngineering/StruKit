"""Build strukit/data/aisc_shapes_v16_HSS.csv from the AISC Shapes Database v16.0 (SHAPE160.xlsx):
rectangular and square HSS, round HSS and pipe, U.S. customary columns (the first 84 columns).
Run: python tools/parse_hss.py /path/to/SHAPE160.xlsx"""
import csv
import sys

import openpyxl

COLS = [("W", "W"), ("A", "A"), ("Ht", "Ht"), ("B", "B"), ("OD", "OD"), ("ID", "ID"), ("tnom", "tnom"), ("tdes", "tdes"), ("b/tdes", "b_t"), ("h/tdes", "h_t"),
        ("D/t", "D_t"), ("Ix", "Ix"), ("Zx", "Zx"), ("Sx", "Sx"), ("rx", "rx"), ("Iy", "Iy"), ("Zy", "Zy"), ("Sy", "Sy"), ("ry", "ry"), ("J", "J"), ("C", "C")]


def main(src, out):
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True)["Database v16.0"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))[:84]
    ix = {h: hdr.index(h) for h, _ in COLS}
    n = 0
    with open(out, "w", newline="") as f:
        f.write("# Source: AISC Shapes Database v16.0 (SHAPE160.xlsx, August 2023), U.S. customary columns. Rectangular, square and round HSS, and pipe.\n")
        w = csv.writer(f)
        w.writerow(["type", "label"] + [k for _, k in COLS])
        for r in rows:
            if r[0] not in ("HSS", "PIPE"):
                continue
            vals = [r[ix[h]] for h, _ in COLS]
            vals = ["" if v in (None, "–", "-") or isinstance(v, str) else v for v in vals]
            kind = "PIPE" if r[0] == "PIPE" else ("HSS-ROUND" if vals[4] != "" else "HSS-RECT")
            w.writerow([kind, str(r[2]).upper().replace(" ", "")] + vals)
            n += 1
    print(n, "rows")


if __name__ == "__main__":
    main(sys.argv[1], "strukit/data/aisc_shapes_v16_HSS.csv")
