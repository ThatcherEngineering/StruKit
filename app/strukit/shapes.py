"""Steel section properties from the AISC Shapes Database v16.0.

Source on file: SHAPE160.xlsx (AISC, August 2023), U.S. customary columns.
Loaded here: W, M, S and HP shapes (data/aisc_shapes_v16_I.csv); rectangular, square and round
HSS and pipe (data/aisc_shapes_v16_HSS.csv, built by tools/parse_hss.py); C and MC channels
(data/aisc_shapes_v16_C.csv, built by tools/parse_channels.py).
"""
import csv
import os

SOURCE = "AISC Shapes Database v16.0"
_PATH = os.path.join(os.path.dirname(__file__), "data", "aisc_shapes_v16_I.csv")
_cache = None


class ShapeError(ValueError):
    pass


def _load():
    global _cache
    if _cache is None:
        with open(_PATH, newline="") as f:
            rows = csv.DictReader(line for line in f if not line.startswith("#"))
            _cache = {}
            for r in rows:
                props = {}
                for k, v in r.items():
                    if k in ("type", "label"):
                        props[k] = v
                    elif v != "":
                        props[k] = float(v)
                _cache[r["label"]] = props
    return _cache


def normalize(name):
    return name.upper().replace(" ", "").replace("×", "X")


def get(name):
    """Properties of a shape by its Manual label, e.g. 'W18x50', or of a built-up three-plate I ("BU 14x2 / 62x1/2 / 14x2", see builtup).
    Unknown names are refused."""
    from . import builtup
    if builtup.is_builtup(name):
        try:
            return builtup.props(name)
        except builtup.BuiltUpError as e:
            raise ShapeError(str(e))
    table = _load()
    key = normalize(name)
    if key not in table:
        raise ShapeError(f"shape '{name}' is not in the {SOURCE} I-shape table")
    return dict(table[key])


def labels(kind=None):
    return [k for k, v in _load().items() if kind is None or v["type"] == kind]


_HSS_PATH = os.path.join(os.path.dirname(__file__), "data", "aisc_shapes_v16_HSS.csv")
_hss_cache = None
HSS_KINDS = ("HSS-RECT", "HSS-ROUND", "PIPE")


def _load_hss():
    global _hss_cache
    if _hss_cache is None:
        with open(_HSS_PATH, newline="") as f:
            _hss_cache = {}
            for r in csv.DictReader(line for line in f if not line.startswith("#")):
                _hss_cache[r["label"]] = {k: (v if k in ("type", "label") else float(v)) for k, v in r.items() if v != ""}
    return _hss_cache


def hss(name):
    """Properties of an HSS or pipe by its Manual label, e.g. 'HSS6x4x1/4', 'HSS1.900x0.145',
    'Pipe 3 STD'. type is HSS-RECT, HSS-ROUND or PIPE; tdes is the design wall thickness."""
    table = _load_hss()
    key = normalize(name)
    if key not in table:
        raise ShapeError(f"shape '{name}' is not in the {SOURCE} HSS and pipe table")
    return dict(table[key])


def hss_labels(kind=None):
    return [k for k, v in _load_hss().items() if kind is None or v["type"] == kind]


_C_PATH = os.path.join(os.path.dirname(__file__), "data", "aisc_shapes_v16_C.csv")
_c_cache = None


def _load_c():
    global _c_cache
    if _c_cache is None:
        with open(_C_PATH, newline="") as f:
            _c_cache = {}
            for r in csv.DictReader(line for line in f if not line.startswith("#")):
                _c_cache[r["label"]] = {k: (v if k in ("type", "label") else float(v)) for k, v in r.items() if v != ""}
    return _c_cache


def channel(name):
    """Properties of a C or MC channel by its Manual label, e.g. 'C15x33.9', 'MC12x10.6'.
    bf_2tf holds the flange width-to-thickness ratio b/t (full flange width over thickness)."""
    table = _load_c()
    key = normalize(name)
    if key not in table:
        raise ShapeError(f"shape '{name}' is not in the {SOURCE} channel table")
    return dict(table[key])


def channel_labels():
    return list(_load_c())


_L_PATH = os.path.join(os.path.dirname(__file__), "data", "aisc_shapes_v16_L.csv")
_l_cache = None


def _load_l():
    global _l_cache
    if _l_cache is None:
        with open(_L_PATH, newline="") as f:
            _l_cache = {}
            for r in csv.DictReader(line for line in f if not line.startswith("#")):
                _l_cache[r["label"]] = {k: (v if k in ("type", "label") else float(v)) for k, v in r.items() if v != ""}
    return _l_cache


def angle(name):
    """Properties of a single angle by its Manual label, e.g. 'L3x3x3/16', 'L6x4x1/2'. rz is the radius of gyration about the minor principal axis."""
    table = _load_l()
    key = normalize(name)
    if key not in table:
        raise ShapeError(f"shape '{name}' is not in the {SOURCE} single angle table")
    return dict(table[key])


def angle_labels():
    return list(_load_l())
