"""Add the T dimension (clear distance between the web fillets, detailing value) of the AISC Shapes Database v16.0
to strukit/data/aisc_shapes_v16_I.csv as a last column "T".  Run: python tools/add_T.py /path/to/SHAPE160.xlsx"""
import csv
import sys

import openpyxl


def main(src, path):
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True)["Database v16.0"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))[:84]
    iT = hdr.index("T")
    T = {str(r[2]).upper().replace(" ", ""): r[iT] for r in rows if r[0] in ("W", "M", "S", "HP") and isinstance(r[iT], (int, float))}
    lines = open(path, newline="").read().splitlines()
    head, body = lines[0], list(csv.reader(lines[1:]))
    if "T" in body[0]:
        print("already has T"); return
    out = [body[0] + ["T"]] + [r + [T.get(r[1], "")] for r in body[1:]]
    with open(path, "w", newline="") as f:
        f.write(head + "\n")
        csv.writer(f).writerows(out)
    print(sum(1 for r in out[1:] if r[-1] != ""), "of", len(out) - 1, "rows have T")


if __name__ == "__main__":
    main(sys.argv[1], "strukit/data/aisc_shapes_v16_I.csv")
