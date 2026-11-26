"""Build strukit/data/aisc_shapes_v16_T.csv from the AISC Shapes Database v16.0 (SHAPE160.xlsx):
WT, MT and ST tees, U.S. customary columns (the first 84 columns); k1 converted from its printed fraction.
Run: python tools/parse_tees.py /path/to/SHAPE160.xlsx"""
import csv
import sys

import openpyxl
from fractions import Fraction


def _num(v):
    """A database value; k1 is printed as a fraction (for example 7/8 or 1-1/8)."""
    if v is None or v in ("–", "-"):
        return ""
    if isinstance(v, str):
        t = v.strip()
        try:
            if "-" in t:
                a, b = t.split("-", 1)
                return float(a) + float(Fraction(b))
            return float(Fraction(t))
        except (ValueError, ZeroDivisionError):
            return ""
    return v

COLS = [("W", "W"), ("A", "A"), ("d", "d"), ("bf", "bf"), ("tw", "tw"), ("tf", "tf"), ("kdes", "kdes"), ("bf/2tf", "bf_2tf"), ("D/t", "d_tw"), ("k1", "k1"), ("y", "ybar"), ("Ix", "Ix"), ("Zx", "Zx"),
        ("Sx", "Sx"), ("rx", "rx"), ("Iy", "Iy"), ("Zy", "Zy"), ("Sy", "Sy"), ("ry", "ry"), ("J", "J"), ("Cw", "Cw"), ("ro", "ro")]


def main(src, out):
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True)["Database v16.0"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))[:84]
    ix = {h: hdr.index(h) for h, _ in COLS}
    n = 0
    with open(out, "w", newline="") as f:
        f.write("# Source: AISC Shapes Database v16.0 (SHAPE160.xlsx, August 2023), U.S. customary columns. WT, MT and ST tees.\n")
        w = csv.writer(f)
        w.writerow(["type", "label"] + [k for _, k in COLS])
        for r in rows:
            if r[0] not in ("WT", "MT", "ST"):
                continue
            vals = [_num(r[ix[h]]) for h, _ in COLS]
            w.writerow([r[0], str(r[2]).upper().replace(" ", "")] + vals)
            n += 1
    print(n, "rows")


if __name__ == "__main__":
    main(sys.argv[1], "strukit/data/aisc_shapes_v16_T.csv")
