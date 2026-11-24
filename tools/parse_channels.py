"""Build strukit/data/aisc_shapes_v16_C.csv from the AISC Shapes Database v16.0 (SHAPE160.xlsx):
C and MC channels, U.S. customary columns (the first 84 columns). The flange width-to-thickness
ratio b/t of the database is written under bf_2tf, the name the beam check reads.
Run: python tools/parse_channels.py /path/to/SHAPE160.xlsx"""
import csv
import sys

import openpyxl

COLS = [("W", "W"), ("A", "A"), ("d", "d"), ("bf", "bf"), ("tw", "tw"), ("tf", "tf"), ("kdes", "kdes"), ("b/t", "bf_2tf"), ("h/tw", "h_tw"), ("Ix", "Ix"), ("Zx", "Zx"),
        ("Sx", "Sx"), ("rx", "rx"), ("Iy", "Iy"), ("Zy", "Zy"), ("Sy", "Sy"), ("ry", "ry"), ("J", "J"), ("Cw", "Cw"), ("rts", "rts"), ("ho", "ho"), ("x", "xbar"), ("eo", "eo")]


def main(src, out):
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True)["Database v16.0"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))[:84]
    ix = {h: hdr.index(h) for h, _ in COLS}
    n = 0
    with open(out, "w", newline="") as f:
        f.write("# Source: AISC Shapes Database v16.0 (SHAPE160.xlsx, August 2023), U.S. customary columns. C and MC channels; bf_2tf holds the database b/t.\n")
        w = csv.writer(f)
        w.writerow(["type", "label"] + [k for _, k in COLS])
        for r in rows:
            if r[0] not in ("C", "MC"):
                continue
            vals = ["" if r[ix[h]] in (None, "–", "-") or isinstance(r[ix[h]], str) else r[ix[h]] for h, _ in COLS]
            w.writerow([r[0], str(r[2]).upper().replace(" ", "")] + vals)
            n += 1
    print(n, "rows")


if __name__ == "__main__":
    main(sys.argv[1], "strukit/data/aisc_shapes_v16_C.csv")
