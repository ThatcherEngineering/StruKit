"""Steel section properties from the AISC Shapes Database v16.0.

Source on file: SHAPE160.xlsx (AISC, August 2023), U.S. customary columns.
Loaded here: W, M, S and HP shapes (data/aisc_shapes_v16_I.csv).
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
    """Properties of a shape by its Manual label, e.g. 'W18x50'. Unknown names are refused."""
    table = _load()
    key = normalize(name)
    if key not in table:
        raise ShapeError(f"shape '{name}' is not in the {SOURCE} I-shape table")
    return dict(table[key])


def labels(kind=None):
    return [k for k, v in _load().items() if kind is None or v["type"] == kind]
