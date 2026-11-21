"""The jurisdiction table STRUKIT-JURIS.csv - design criteria as data, not code.

Line 1: STRUKIT-JURIS,1,<version>,<sha256 of the data rows>
Line 2: column names. Then one value per row:
  juris, key, risk_cat, elev_min_ft, elev_max_ft, value, unit, source, source_date, note
Lookup never borrows another agency's number: no row means "no criterion".
"""
import hashlib

REQUIRED = ["juris", "key", "value", "unit", "source", "source_date"]


class JurisError(ValueError):
    pass


def data_hash(lines):
    return hashlib.sha256("\r\n".join(lines).encode("ascii")).hexdigest()


def load(path, verify=True):
    with open(path, "r", encoding="ascii", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f if ln.strip()]
    sig = lines[0].split(",")
    if sig[0] != "STRUKIT-JURIS" or len(sig) < 4:
        raise JurisError(f"{path}: not a STRUKIT-JURIS file")
    if sig[1] != "1":
        raise JurisError(f"{path}: format version {sig[1]} is not known to this build")
    header = [c.strip().lower() for c in lines[1].split(",")]
    for c in REQUIRED:
        if c not in header:
            raise JurisError(f"{path}: column '{c}' is missing")
    body = lines[2:]
    if verify and data_hash(body) != sig[3]:
        raise JurisError(f"{path}: the data rows do not match the file's hash (file was edited)")
    rows = []
    for n, ln in enumerate(body, 3):
        cells = [c.strip() for c in ln.split(",")]
        if len(cells) != len(header):
            raise JurisError(f"{path} line {n}: {len(cells)} fields, header has {len(header)}")
        row = dict(zip(header, cells))
        for c in ("source", "source_date"):
            if not row[c]:
                raise JurisError(f"{path} line {n}: every row needs a {c}")
        rows.append(row)
    return {"version": sig[2], "hash": sig[3], "rows": rows}


def lookup(table, juris, key, risk_cat=None, elev_ft=None):
    """Return the matching row or None. A row with a risk category or an elevation
    range only matches when the job supplies a value inside it."""
    hits = []
    for r in table["rows"]:
        if r["juris"].upper() != juris.upper() or r["key"].lower() != key.lower():
            continue
        rc = r.get("risk_cat", "")
        if rc and (risk_cat is None or str(risk_cat).upper() not in rc.upper().split("/")):
            continue
        lo, hi = r.get("elev_min_ft", ""), r.get("elev_max_ft", "")
        if lo or hi:
            if elev_ft is None:
                continue
            if (lo and elev_ft < float(lo)) or (hi and elev_ft > float(hi)):
                continue
        hits.append(r)
    if len(hits) > 1:
        raise JurisError(f"{juris} {key}: {len(hits)} rows match; the table must not overlap")
    return hits[0] if hits else None
