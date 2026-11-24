"""Simpson Strong-Tie hold-downs: allowable tension loads typed from the Wood Construction
Connectors catalog C-C-2026 (pp. 59, 61, 63 and 67). Loads are allowable (160), lb, already
increased for wind or earthquake. Each entry: allowable for Douglas Fir-Larch / Southern
Pine posts and for Spruce-Pine-Fir / Hem-Fir posts, the minimum post, the fasteners, the
anchor diameter and the deflection at the allowable load.

Screw and nail hold-downs (catalog p. 59, 61, 63): LRFD = 1.4 x allowable (p. 61 note 2).
Embedded strap ties LSTHD / STHD (p. 67): one table for wind and Seismic Design Category A
and B, one for C to F; by stem wall width, cracked or uncracked concrete and position
(midwall, corner, end wall); LRFD = 1.67 x wind, 1.43 x seismic (p. 67 note 6); concrete
2,500 psi minimum (note 2)."""

SOURCE = "Simpson Strong-Tie catalog C-C-2026"

# model: (DF/SP, SPF/HF, minimum post (in.), fasteners, anchor dia. (in.), deflection (in.), page)
BOLTED = {
    "DTT1Z": (910, 640, "1-1/2 x 3-1/2", "(6) 0.148 x 1-1/2 nails", "3/8", 0.167, 61),
    "DTT2Z": (1825, 1800, "1-1/2 x 3-1/2", "(8) 1/4 x 1-1/2 SDS screws", "1/2", 0.105, 61),
    "DTT2Z-SDS2.5": (2145, 2105, "3 x 3-1/2", "(8) 1/4 x 2-1/2 SDS screws", "1/2", 0.128, 61),
    "HDUE3-SDS3": (3790, 3340, "3 x 3-1/2", "(7) 1/4 x 3 SDS screws", "5/8", 0.127, 61),
    "HDUE5-SDS3": (5375, 4700, "3 x 3-1/2", "(10) 1/4 x 3 SDS screws", "5/8", 0.146, 61),
    "HDUE7-SDS3": (7015, 6030, "3 x 3-1/2", "(13) 1/4 x 3 SDS screws", "5/8", 0.154, 61),
    "HDUE9-SDS3.5": (8425, 7305, "3-1/2 x 3-1/2", "(16) 1/4 x 3-1/2 SDS screws", "7/8", 0.159, 61),
    "HDUE13-SDS3.5": (11900, 10215, "5-1/2 x 3-1/2", "(23) 1/4 x 3-1/2 SDS screws", "1", 0.164, 61),
    "HDUE17-SDS4.5": (16040, 13545, "5-1/2 x 3-1/2", "(28) 1/4 x 4-1/2 SDS screws", "1", 0.094, 61),
    "HTT4": (3610, 3105, "3 x 3-1/2", "(18) 0.148 x 1-1/2 nails", "5/8", 0.086, 63),
    "HTT5": (4350, 3740, "3 x 3-1/2", "(26) 0.148 x 1-1/2 nails", "5/8", 0.120, 63),
    "HDQ8-SDS3": (5715, 4915, "3 x 3-1/2", "(20) 1/4 x 3 SDS screws", "7/8", 0.073, 59),
    "HHDQ11-SDS2.5": (11810, 8425, "3-1/2 x 5-1/2", "(24) 1/4 x 2-1/2 SDS screws", "1", 0.131, 59),
    "HHDQ14-SDS2.5": (13015, 10530, "3-1/2 x 7-1/4", "(30) 1/4 x 2-1/2 SDS screws", "1", 0.107, 59),
}
PICK_ORDER = ["DTT2Z", "DTT2Z-SDS2.5", "HDUE3-SDS3", "HDUE5-SDS3", "HDUE7-SDS3", "HDUE9-SDS3.5", "HDUE13-SDS3.5", "HDUE17-SDS4.5"]

# (model, stem wall in.): nails, then {"low": wind and SDC A-B, "high": SDC C-F}: (uncracked midwall, corner, end wall, cracked midwall, corner, end wall)
STRAP = {
    ("LSTHD8", 6): ("(20) 0.148 x 3-1/4 nails", "(16) 0.148 x 3-1/4 nails", (2985, 2590, 1620, 2565, 2225, 1395), (2270, 2090, 1220, 2250, 1950, 1220)),
    ("STHD10", 6): ("(24) 0.148 x 3-1/4 nails", "(18) 0.148 x 3-1/4 nails", (3535, 3535, 1960, 2910, 2910, 1635), (2750, 2750, 1615, 2550, 2550, 1435)),
    ("STHD14", 6): ("(30) 0.148 x 3-1/4 nails", "(22) 0.148 x 3-1/4 nails", (4935, 4935, 3065, 4935, 4935, 3065), (3695, 3695, 2685, 3695, 3695, 2685)),
    ("LSTHD8", 8): ("(20) 0.148 x 3-1/4 nails", "(16) 0.148 x 3-1/4 nails", (2985, 2590, 2135, 2565, 2225, 1835), (2615, 2125, 1635, 2250, 1950, 1610)),
    ("STHD10", 8): ("(28) 0.148 x 3-1/4 nails", "(20) 0.148 x 3-1/4 nails", (4755, 4075, 3015, 4020, 3350, 2480), (3400, 2940, 2295, 3400, 2940, 2175)),
    ("STHD14", 8): ("(30) 0.148 x 3-1/4 nails", "(24) 0.148 x 3-1/4 nails", (5285, 5285, 4410, 5285, 5285, 4410), (3815, 3815, 3500, 3815, 3815, 3500)),
}
STRAP_DEFL = {"LSTHD8": 0.114, "STHD10": 0.146, "STHD14": 0.164}       # over 1/2 in. sheathing, p. 67 note 5 (the larger values)
STRAP_PICK = ["LSTHD8", "STHD10", "STHD14"]
POSITIONS = ["midwall", "corner", "end wall"]
MODELS = ["smallest HDUE or DTT that works", "smallest LSTHD or STHD that works"] + list(BOLTED) + STRAP_PICK


class HoldDownError(ValueError):
    pass


def _species(G):
    """DF/SP column for specific gravity 0.49 and over, else SPF/HF (catalog species groups)."""
    return 0 if G >= 0.49 else 1


def _one(model, G, load, method, stem=None, position=None, cracked=None, sdc_high=None):
    if model in BOLTED:
        b = BOLTED[model]
        col = _species(G)
        allow = b[col]
        f = 1.4 if method == "LRFD" else 1.0
        return dict(model=model, capacity=allow * f, allowable=allow, factor=f, post=b[2], fasteners=b[3], anchor=b[4], deflection=b[5], page=b[6],
                    text=f"{model}: {allow:,} lb allowable, {'DF/SP' if col == 0 else 'SPF/HF'} post {b[2]} in. minimum, {b[3]}, {b[4]} in. anchor"
                         + (" x 1.4 for LRFD" if f != 1 else ""), source=f"{SOURCE}, p. {b[6]}")
    if model in STRAP_PICK:
        miss = [n for n, v in (("stem wall width", stem), ("position on the wall", position), ("cracked or uncracked concrete", cracked)) if v in (None, "")]
        if load == "seismic" and sdc_high is None:
            miss.append("Seismic Design Category A-B or C-F")
        if miss:
            raise HoldDownError("hold-down: an embedded strap tie needs " + ", ".join(miss))
        if (model, int(stem)) not in STRAP:
            raise HoldDownError("hold-down: strap tie loads are tabulated for 6 in. and 8 in. stem walls")
        if position not in POSITIONS:
            raise HoldDownError("hold-down: position is midwall, corner or end wall")
        n_low, n_high, low, high = STRAP[(model, int(stem))]
        hi = bool(load == "seismic" and sdc_high)
        allow = (high if hi else low)[POSITIONS.index(position) + (3 if cracked else 0)]
        f = (1.43 if load == "seismic" else 1.67) if method == "LRFD" else 1.0
        return dict(model=model, capacity=allow * f, allowable=allow, factor=f, post="double studs", fasteners=n_high if hi else n_low, anchor="",
                    deflection=STRAP_DEFL[model], page=67,
                    text=f"{model}: {allow:,} lb allowable, {int(stem)} in. stem wall, {position}, {'cracked' if cracked else 'uncracked'} concrete, "
                         f"{'Seismic Design Category C to F' if hi else 'wind and Seismic Design Category A and B'}, {n_high if hi else n_low}"
                         + (f" x {f:g} for LRFD" if f != 1 else ""), source=f"{SOURCE}, p. 67")
    raise HoldDownError(f"hold-down: '{model}' is not in the table")


def check(model, T, G, load, method, **kw):
    """The hold-down for tension T (lb, at the level of `method`). model: an entry of MODELS;
    the two "smallest ... that works" entries pick the first of their family whose capacity
    is not less than T (the largest of the family if none is)."""
    if model.startswith("smallest"):
        fam = STRAP_PICK if "STHD" in model else PICK_ORDER
        got = None
        for m in fam:
            got = _one(m, G, load, method, **kw)
            if got["capacity"] >= T:
                break
        got["picked"] = True
        return got
    got = _one(model, G, load, method, **kw)
    got["picked"] = False
    return got
