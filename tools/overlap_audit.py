"""Text overlap audit of printed sheets: every pair of text runs whose boxes overlap, and every text run that passes the right margin.
Usage: python tools/overlap_audit.py file.pdf [file.pdf ...]   (exit code 1 when anything is found)"""
import sys
import pymupdf


def audit(path, right_margin=43.2):
    found = []
    doc = pymupdf.open(path)
    for pn, page in enumerate(doc, 1):
        spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln["spans"]:
                    t = sp["text"].strip()
                    if not t:
                        continue
                    x0, y0, x1, y1 = sp["bbox"]
                    h = y1 - y0
                    lead = len(sp["text"]) - len(sp["text"].lstrip())
                    cw = (x1 - x0) / max(len(sp["text"]), 1)
                    spans.append((x0 + lead * cw, y0 + 0.28 * h, x0 + (lead + len(sp["text"].strip())) * cw, y1 - 0.28 * h, t))
        W = page.rect.width
        for s in spans:
            if s[2] > W - right_margin + 1.5:
                found.append((pn, "past the right margin", s[4][:70], ""))
        for i, a in enumerate(spans):
            for b in spans[i + 1:]:
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox > 1.0 and oy > 0.8:
                    found.append((pn, "text on text", a[4][:50], b[4][:50]))
    return found


if __name__ == "__main__":
    bad = 0
    for f in sys.argv[1:]:
        for pn, what, a, b in audit(f):
            bad += 1
            print(f"{f} sheet {pn}: {what}: {a!r} {b!r}")
    print(f"{bad} found")
    sys.exit(1 if bad else 0)
