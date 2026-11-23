"""Layout and load patterns for beams of one or more spans, with or without overhangs.

Statics only (beam.py does the analysis). What is read from a standard:
  ASCE/SEI 7-22 Sect. 4.3.3  partial loading: the full live load on only part of a member
             is to be considered where it gives a more unfavourable effect. For a beam
             with more than one span or with an overhang, every arrangement of the live
             load cases (L and Lr) on whole spans and overhangs is analysed, and each
             check takes the worst arrangement.
  IBC Table 1604.3 note: for a cantilever, the deflection limit is based on twice its
             length.
Partial snow loading (ASCE/SEI 7-22 Sect. 7.5) is not generated.

Units in: ft, plf, lb. Units out: lb, lb-in, in.
"""
from dataclasses import dataclass
from itertools import product

from . import beam as bm

PATTERN_CASES = ("L", "Lr")


@dataclass
class Layout:
    spans: list            # ft
    left: float            # overhang, ft
    right: float

    @property
    def total(self):
        return self.left + sum(self.spans) + self.right

    @property
    def supports(self):
        x, out = self.left, [self.left]
        for s in self.spans:
            x += s
            out.append(x)
        return out

    @property
    def segments(self):
        """(x0, x1, label, deflection length) for each overhang and span, ft."""
        out, x = [], 0.0
        if self.left:
            out.append((0.0, self.left, "left overhang", 2 * self.left)); x = self.left
        for i, s in enumerate(self.spans, 1):
            out.append((x, x + s, f"span {i}" if len(self.spans) > 1 else "span", s)); x += s
        if self.right:
            out.append((x, x + self.right, "right overhang", 2 * self.right))
        return out

    @property
    def simple(self):
        return len(self.spans) == 1 and not self.left and not self.right

    def describe(self):
        t = f"{self.spans[0]:g} ft, simply supported" if len(self.spans) == 1 else \
            "continuous over " + str(len(self.spans) + 1) + " supports, spans " + ", ".join(f"{s:g}" for s in self.spans) + " ft"
        oh = [f"{v:g} ft overhang at the {k}" for k, v in (("left", self.left), ("right", self.right)) if v]
        return t + ("; " + " and ".join(oh) if oh else "")


def layout(span_ft, spans=None, left=0.0, right=0.0):
    sp = [float(s) for s in (spans if spans else [span_ft])]
    if not sp or any(s is None or s <= 0 for s in sp) or (left or 0) < 0 or (right or 0) < 0:
        raise ValueError("beam: every span must be positive and overhangs not negative")
    if len(sp) > 5:
        raise ValueError("beam: at most five spans")
    return Layout(sp, float(left or 0.0), float(right or 0.0))


def _pieces(lay, ld):
    """One load cut at the segment boundaries: list of (segment index, load dict)."""
    out = []
    segs = lay.segments
    if ld["kind"] == "uniform":
        a, b = ld.get("x1_ft", 0.0), ld.get("x2_ft", lay.total)
        for i, (x0, x1, _, _) in enumerate(segs):
            lo, hi = max(a, x0), min(b, x1)
            if hi - lo > 1e-9:
                out.append((i, dict(kind="uniform", w=ld["w"], x1_ft=lo, x2_ft=hi)))
    else:
        for i, (x0, x1, _, _) in enumerate(segs):
            if x0 - 1e-9 <= ld["x_ft"] <= x1 + 1e-9:
                out.append((i, dict(kind="point", P=ld["P"], x_ft=ld["x_ft"])))
                break
    return out


def _solve(lay, EI, items):
    pts, dist = [], []
    for fac, ld in items:
        if ld["kind"] == "uniform":
            w = fac * ld["w"] / 12.0
            dist.append(bm.DistLoad(ld.get("x1_ft", 0.0) * 12, ld.get("x2_ft", lay.total) * 12, w, w))
        else:
            pts.append(bm.PointLoad(ld["x_ft"] * 12, fac * ld["P"]))
    if not pts and not dist:
        return None
    return bm.solve(lay.total * 12.0, [s * 12.0 for s in lay.supports], EI, pts, dist)


def arrangements(lay, by_case, factors):
    """Every load arrangement to analyse for one set of load factors: list of results."""
    fixed, pat = [], {}
    for case, fac in factors.items():
        if not fac:
            continue
        for ld in by_case.get(case, []):
            if case in PATTERN_CASES and not lay.simple:
                for i, piece in _pieces(lay, ld):
                    pat.setdefault(i, []).append((fac, piece))
            else:
                fixed.append((fac, ld))
    keys = sorted(pat)
    return [(on, fixed + [it for k, use in zip(keys, on) if use for it in pat[k]]) for on in product((True, False), repeat=len(keys))]


@dataclass
class Envelope:
    Mpos: float            # largest sagging moment, lb-in
    Mneg: float            # largest hogging moment, lb-in, as a positive number
    V: float
    R_end: float           # largest reaction at an end support (first or last)
    R_int: float           # largest reaction at an interior support
    R_min: float           # smallest reaction at any support (negative = uplift)
    res_pos: object
    res_neg: object
    reactions: dict        # of the arrangement with every span loaded
    n: int


def envelope(lay, EI, by_case, factors):
    sup = [s * 12.0 for s in lay.supports]
    best = None
    for on, items in arrangements(lay, by_case, factors):
        r = _solve(lay, EI, items)
        if r is None:
            continue
        mp, mn, v = max(float(r.M.max()), 0.0), max(-float(r.M.min()), 0.0), float(abs(r.V).max())
        rs = [r.reactions[min(r.reactions, key=lambda k: abs(k - s))] for s in sup]
        ends, ints = (rs[0], rs[-1]), rs[1:-1]
        if best is None:
            best = Envelope(mp, mn, v, max(ends), max(ints) if ints else 0.0, min(rs), r, r, dict(r.reactions), 0)
        else:
            if mp > best.Mpos:
                best.Mpos, best.res_pos = mp, r
            if mn > best.Mneg:
                best.Mneg, best.res_neg = mn, r
            best.V = max(best.V, v); best.R_end = max(best.R_end, *ends)
            best.R_int = max([best.R_int] + ints); best.R_min = min(best.R_min, *rs)
        best.n += 1
    return best


def deflection(lay, EI, by_case, factors, ratio):
    """Worst deflection-to-limit over the overhangs and spans and the live load
    arrangements: (deflection in, limit in, segment label, limit text) or None."""
    worst = None
    for on, items in arrangements(lay, by_case, factors):
        r = _solve(lay, EI, items)
        if r is None:
            continue
        for x0, x1, label, Ld in lay.segments:
            m = (r.x >= x0 * 12 - 1e-6) & (r.x <= x1 * 12 + 1e-6)
            d = float(abs(r.defl[m]).max())
            lim = Ld * 12.0 / ratio
            if worst is None or d / lim > worst[0] / worst[1]:
                txt = f"2 x {Ld / 2:g} ft / {ratio:g}" if "overhang" in label else f"{Ld:g} ft / {ratio:g}"
                worst = (d, lim, label, txt, r)
    return worst
