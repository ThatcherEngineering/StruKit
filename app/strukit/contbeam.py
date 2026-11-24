"""Layout and load patterns for beams of one or more spans, with or without overhangs.

Statics only (beam.py does the analysis). What is read from a standard:
  ASCE/SEI 7-22 Sect. 4.3.3  partial loading: the full live load on only part of a member
             is to be considered where it gives a more unfavourable effect. For a beam
             with more than one span or with an overhang, every arrangement of the live
             load cases (L and Lr) on whole spans and overhangs is analysed, and each
             check takes the worst arrangement.
  IBC Table 1604.3 note: for a cantilever, the deflection limit is based on twice its
             length.
  ASCE/SEI 7-22 Sect. 7.5.1  partial snow loading of continuous beams (a cantilever
             counts as a span): besides the balanced load on every span, Case 1: full
             balanced load on either exterior span and half on the others; Case 2: half
             on either exterior span and full on the others; Case 3: full on any two
             adjacent spans and half on the others. Not required for members spanning
             perpendicular to the ridge of a gable roof sloped 1/2 on 12 to 7 on 12; the
             caller says whether it applies.

A uniform load may carry "w2": it then varies in a straight line from w at its start to
w2 at its end (a snow drift on a joist or rafter).

Units in: ft, plf, lb. Units out: lb, lb-in, in.
"""
from dataclasses import dataclass
from itertools import product

from . import beam as bm

PATTERN_CASES = ("L", "Lr")
SNOW_CASE = "S"


def snow_weights(n, partial=True):
    """Arrangements of the snow load over n spans: a list of per-span multipliers."""
    out = [[1.0] * n]
    if partial and n >= 2:
        for e in (0, n - 1):
            w = [0.5] * n; w[e] = 1.0; out.append(w)
            w = [1.0] * n; w[e] = 0.5; out.append(w)
        for i in range(n - 1):
            w = [0.5] * n; w[i] = w[i + 1] = 1.0; out.append(w)
    uniq = []
    for w in out:
        if w not in uniq:
            uniq.append(w)
    return uniq


@dataclass
class Layout:
    spans: list            # ft
    left: float            # overhang, ft
    right: float
    fixed: bool = False    # one support, fixed against rotation (a beam cantilevering each side of a column); spans is then empty

    def bm_supports(self):
        """(supports, fixed) for beam.solve, inches."""
        return ([], [self.left * 12.0]) if self.fixed else ([s * 12.0 for s in self.supports], [])

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
            out.append((0.0, self.left, "left cantilever" if self.fixed else "left overhang", 2 * self.left)); x = self.left
        for i, s in enumerate(self.spans, 1):
            out.append((x, x + s, f"span {i}" if len(self.spans) > 1 else "span", s)); x += s
        if self.right:
            out.append((x, x + self.right, "right cantilever" if self.fixed else "right overhang", 2 * self.right))
        return out

    @property
    def simple(self):
        return len(self.spans) == 1 and not self.left and not self.right

    def describe(self):
        if self.fixed:
            arms = [f"{v:g} ft to the {k}" for k, v in (("left", self.left), ("right", self.right)) if v]
            return "fixed at one support, cantilevering " + " and ".join(arms)
        t = f"{self.spans[0]:g} ft, simply supported" if len(self.spans) == 1 else \
            "continuous over " + str(len(self.spans) + 1) + " supports, spans " + ", ".join(f"{s:g}" for s in self.spans) + " ft"
        oh = [f"{v:g} ft overhang at the {k}" for k, v in (("left", self.left), ("right", self.right)) if v]
        return t + ("; " + " and ".join(oh) if oh else "")


def layout(span_ft, spans=None, left=0.0, right=0.0, fixed=False):
    if fixed:
        if (left or 0) < 0 or (right or 0) < 0 or not ((left or 0) + (right or 0) > 0):
            raise ValueError("beam: a beam fixed at one support needs a cantilever length on at least one side")
        return Layout([], float(left or 0.0), float(right or 0.0), True)
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
                w1, w2 = ld["w"], ld.get("w2", ld["w"])
                at = lambda x: w1 + (w2 - w1) * (x - a) / (b - a)
                out.append((i, dict(kind="uniform", w=at(lo), w2=at(hi), x1_ft=lo, x2_ft=hi)))
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
            dist.append(bm.DistLoad(ld.get("x1_ft", 0.0) * 12, ld.get("x2_ft", lay.total) * 12, fac * ld["w"] / 12.0,
                                    fac * ld.get("w2", ld["w"]) / 12.0))
        else:
            pts.append(bm.PointLoad(ld["x_ft"] * 12, fac * ld["P"]))
    if not pts and not dist:
        return None
    sup, fx = lay.bm_supports()
    return bm.solve(lay.total * 12.0, sup, EI, pts, dist, fixed=fx)


class Basis:
    """Solves each load once at unit factor on one common mesh (every support, end and load
    boundary is a node) and builds the result of any arrangement by superposition. The
    analysis is linear, so this equals solving the arrangement directly."""

    def __init__(self, lay, EI, by_case):
        self.lay, self.EI, self.cache = lay, EI, {}
        br = set()
        for lst in by_case.values():
            for ld in lst:
                for _, pc in _pieces(lay, ld):
                    br.update((pc["x1_ft"], pc["x2_ft"]) if pc["kind"] == "uniform" else (pc["x_ft"],))
                if ld["kind"] == "uniform":
                    br.update((ld.get("x1_ft", 0.0), ld.get("x2_ft", lay.total)))
        if lay.fixed:                                         # the moment jumps at a fixed support: a node just each side of it
            br.update((lay.left - 1e-4, lay.left + 1e-4))
        self.nodes = [bm.PointLoad(x * 12.0, 0.0) for x in sorted(br) if 0.0 <= x <= lay.total]

    def _unit(self, ld):
        key = (ld["kind"], ld.get("w"), ld.get("w2", ld.get("w")), ld.get("x1_ft", 0.0), ld.get("x2_ft", self.lay.total)) if ld["kind"] == "uniform" \
            else (ld["kind"], ld["P"], ld["x_ft"])
        if key not in self.cache:
            lay = self.lay
            if ld["kind"] == "uniform":
                r = bm.solve(lay.total * 12.0, lay.bm_supports()[0], self.EI, list(self.nodes),
                             [bm.DistLoad(key[3] * 12, key[4] * 12, key[1] / 12.0, key[2] / 12.0)], fixed=lay.bm_supports()[1])
            else:
                r = bm.solve(lay.total * 12.0, lay.bm_supports()[0], self.EI, list(self.nodes) + [bm.PointLoad(ld["x_ft"] * 12, ld["P"])], fixed=lay.bm_supports()[1])
            self.cache[key] = r
        return self.cache[key]

    def solve(self, items):
        out = None
        for fac, ld in items:
            if not fac:
                continue
            u = self._unit(ld)
            if out is None:
                out = bm.BeamResult(u.x, fac * u.V, fac * u.M, fac * u.defl, {k: fac * v for k, v in u.reactions.items()}, {k: fac * v for k, v in u.fixed_moments.items()})
            else:
                out.V = out.V + fac * u.V; out.M = out.M + fac * u.M; out.defl = out.defl + fac * u.defl
                for k, v in u.reactions.items():
                    out.reactions[k] += fac * v
                for k, v in u.fixed_moments.items():
                    out.fixed_moments[k] = out.fixed_moments.get(k, 0.0) + fac * v
        return out


_RECENT = {}


def basis_for(lay, EI, by_case):
    """The Basis for this beam and these loads, kept between calls (one member is analysed
    for many load combinations and deflection checks in a row)."""
    key = (tuple(lay.spans), lay.left, lay.right, EI,
           tuple(sorted((c, tuple(sorted((k, v) for k, v in ld.items() if isinstance(v, (int, float, str)))))
                        for c, lst in by_case.items() for ld in lst)))
    if key not in _RECENT:
        if len(_RECENT) >= 6:
            _RECENT.pop(next(iter(_RECENT)))
        _RECENT[key] = Basis(lay, EI, by_case)
    return _RECENT[key]


def arrangements(lay, by_case, factors, snow_partial=True):
    """Every load arrangement to analyse for one set of load factors: list of
    (description, [(factor, load)])."""
    fixed, pat, snow = [], {}, {}
    for case, fac in factors.items():
        if not fac:
            continue
        for ld in by_case.get(case, []):
            if case in PATTERN_CASES and not lay.simple:
                for i, piece in _pieces(lay, ld):
                    pat.setdefault(i, []).append((fac, piece))
            elif case == SNOW_CASE and not lay.simple and snow_partial:
                for i, piece in _pieces(lay, ld):
                    snow.setdefault(i, []).append((fac, piece))
            else:
                fixed.append((fac, ld))
    keys = sorted(pat)
    sw = snow_weights(len(lay.segments), True) if snow else [None]
    out = []
    for on in product((True, False), repeat=len(keys)):
        live = [it for k, use in zip(keys, on) if use for it in pat[k]]
        for w in sw:
            sn = [(fac * w[i], piece) for i, lst in snow.items() for fac, piece in lst] if w else []
            out.append(((on, w), fixed + live + sn))
    return out


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


def envelope(lay, EI, by_case, factors, snow_partial=True, basis=None):
    sup = [s * 12.0 for s in lay.supports]
    best = None
    basis = basis or basis_for(lay, EI, by_case)
    for on, items in arrangements(lay, by_case, factors, snow_partial):
        r = basis.solve(items)
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


def deflection(lay, EI, by_case, factors, ratio, snow_partial=True, basis=None):
    """Worst deflection-to-limit over the overhangs and spans and the live load
    arrangements: (deflection in, limit in, segment label, limit text) or None."""
    worst = None
    basis = basis or basis_for(lay, EI, by_case)
    for on, items in arrangements(lay, by_case, factors, snow_partial):
        r = basis.solve(items)
        if r is None:
            continue
        for x0, x1, label, Ld in lay.segments:
            m = (r.x >= x0 * 12 - 1e-6) & (r.x <= x1 * 12 + 1e-6)
            d = float(abs(r.defl[m]).max())
            lim = Ld * 12.0 / ratio
            if worst is None or d / lim > worst[0] / worst[1]:
                txt = f"2 x {Ld / 2:g} ft / {ratio:g}" if ("overhang" in label or "cantilever" in label) else f"{Ld:g} ft / {ratio:g}"
                worst = (d, lim, label, txt, r)
    return worst
