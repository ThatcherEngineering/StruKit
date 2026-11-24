"""Build strukit/data/aisc_shapes_v16_L.csv from the AISC Shapes Database v16.0 (SHAPE160.xlsx):
single angles, U.S. customary columns (the first 84 columns).
Run: python tools/parse_angles.py /path/to/SHAPE160.xlsx"""
import csv
import sys

import openpyxl

COLS = [("W", "W"), ("A", "A"), ("d", "d"), ("b", "b"), ("t", "t"), ("kdes", "kdes"), ("x", "xbar"), ("y", "ybar"), ("b/t", "b_t"), ("Ix", "Ix"), ("Zx", "Zx"), ("Sx", "Sx"),
        ("rx", "rx"), ("Iy", "Iy"), ("Zy", "Zy"), ("Sy", "Sy"), ("ry", "ry"), ("Iz", "Iz"), ("rz", "rz"), ("Sz", "Sz"), ("J", "J"), ("Cw", "Cw"), ("ro", "ro"), ("H", "H"), ("tan(α)", "tan_alpha")]


def main(src, out):
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True)["Database v16.0"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))[:84]
    ix = {h: hdr.index(h) for h, _ in COLS}
    n = 0
    with open(out, "w", newline="") as f:
        f.write("# Source: AISC Shapes Database v16.0 (SHAPE160.xlsx, August 2023), U.S. customary columns. Single angles; rz is about the minor principal axis.\n")
        w = csv.writer(f)
        w.writerow(["type", "label"] + [k for _, k in COLS])
        for r in rows:
            if r[0] != "L":
                continue
            vals = ["" if r[ix[h]] in (None, "–", "-") or isinstance(r[ix[h]], str) else r[ix[h]] for h, _ in COLS]
            w.writerow([r[0], str(r[2]).upper().replace(" ", "")] + vals)
            n += 1
    print(n, "rows")


if __name__ == "__main__":
    main(sys.argv[1], "strukit/data/aisc_shapes_v16_L.csv")
