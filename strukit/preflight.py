"""Preflight: list every input problem at once, each naming its drawing object.

Nothing is assumed silently. A missing key is a problem, never a default.
"""
JOB_KEYS = ["JURIS", "ADDRESS", "ELEV_FT", "RISK_CAT", "ENCLOSURE", "EXPOSURE",
            "SOIL_SOURCE", "DATUM_EL", "METHOD"]

MEMBER_TYPES = {"POST", "RAFTER", "PURLIN", "GIRT", "JOIST", "BEAM", "HEADER",
                "LEDGER", "CARRIER", "TRUSS"}
MEMBER_KEYS = ["MARK", "TYPE", "SIZE", "SPECIES", "GRADE"]
REPETITIVE = {"RAFTER", "PURLIN", "GIRT", "JOIST"}
FTG_KINDS = {"EMBEDDED": ["DIA_IN", "EMBED_FT", "CONSTRAINED", "BACKFILL"],
             "PIER": ["DIA_IN", "EMBED_FT"],
             "SPREAD": ["W_FT", "L_FT", "THICK_IN"],
             "CONT": ["W_FT", "THICK_IN"]}
NUMERIC = {"ELEV_FT", "DATUM_EL", "SPACING_IN", "SPAN_FT", "TRIB_FT", "BRACE_FT",
           "DIA_IN", "EMBED_FT", "W_FT", "L_FT", "THICK_IN"}


def _num_problems(name, keys):
    out = []
    for k in NUMERIC & set(keys):
        try:
            float(keys[k])
        except ValueError:
            out.append(f"{name}: {k}={keys[k]!r} is not a number")
    return out


def check(project, entities):
    """Return (problems, counts). An empty problem list means the run may proceed."""
    problems = []
    for k in JOB_KEYS:
        if not project.get(k):
            problems.append(f"job record: missing key {k}")
    problems += _num_problems("job record", project)

    members = [e for e in entities if "TYPE" in e.keys or "MARK" in e.keys]
    footings = [e for e in entities if "FTG" in e.keys]
    marks = {}
    for e in members:
        for k in MEMBER_KEYS:
            if not e.keys.get(k):
                problems.append(f"{e.name}: missing key {k}")
        t = e.keys.get("TYPE", "").upper()
        if t and t not in MEMBER_TYPES:
            problems.append(f"{e.name}: TYPE={t} is not a known member type")
        if t in REPETITIVE and not e.keys.get("SPACING_IN"):
            problems.append(f"{e.name}: missing key SPACING_IN (required for {t})")
        if len(e.points) < 2 and not e.keys.get("SPAN_FT"):
            problems.append(f"{e.name}: no drawn length and no SPAN_FT")
        problems += _num_problems(e.name, e.keys)
        m = e.keys.get("MARK")
        if m:
            marks.setdefault(m, []).append(e)
    for e in members:                                   # supports must exist
        s = e.keys.get("SUPPORT")
        for ref in (s.split(";") if s else []):
            if ref.strip() and ref.strip() not in marks:
                problems.append(f"{e.name}: SUPPORT={ref.strip()} is not a mark in the drawing")
    for e in footings:
        kind = e.keys.get("KIND", "").upper()
        if not kind:
            problems.append(f"{e.name}: missing key KIND")
        elif kind not in FTG_KINDS:
            problems.append(f"{e.name}: KIND={kind} is not a known footing kind")
        else:
            for k in FTG_KINDS[kind]:
                if not e.keys.get(k):
                    problems.append(f"{e.name}: missing key {k} (required for {kind})")
        post = e.keys.get("POST")
        if post and post not in marks:
            problems.append(f"{e.name}: POST={post} is not a mark in the drawing")
        problems += _num_problems(e.name, e.keys)
    if not members and not footings:
        problems.append("drawing: no structural objects found (no member or footing keys)")
    return problems, {"members": len(members), "footings": len(footings)}
