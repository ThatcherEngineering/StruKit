"""Read the drawing export: R12 DXF entities with handles and KEY=value xdata.

Dependency-free reader for the DXF the ZET LISP writes (HYDROKIT-RUN-SPEC round 2):
ENTITIES only, real handles on group 5, xdata as 1001 app + 1000 strings.
StruKit only reads. It never writes a drawing.
"""
from dataclasses import dataclass, field


@dataclass
class Entity:
    kind: str
    handle: str = ""
    layer: str = ""
    points: list = field(default_factory=list)      # (x, y, z) in drawing order
    keys: dict = field(default_factory=dict)        # KEY -> value, from our xdata app

    @property
    def name(self):
        """How messages name this object: mark (if any) plus handle."""
        mark = self.keys.get("MARK") or self.keys.get("FTG") or self.keys.get("CONN") \
            or self.keys.get("WALL") or self.keys.get("DIAPH") or ""
        return f"{mark} (handle {self.handle})" if mark else f"{self.kind} (handle {self.handle})"


def _pairs(path):
    with open(path, "r", encoding="ascii", errors="replace") as f:
        lines = f.read().splitlines()
    if len(lines) % 2:
        lines = lines[:-1]
    for i in range(0, len(lines), 2):
        try:
            yield int(lines[i].strip()), lines[i + 1].strip()
        except ValueError:
            raise ValueError(f"{path}: line {i + 1} is not a DXF group code: {lines[i]!r}")


def read_entities(path, app):
    """Return every entity in the ENTITIES section. Keys come only from xdata app `app`."""
    ents, cur, in_entities, section_next = [], None, False, False
    in_app = False
    poly = None                      # open POLYLINE collecting VERTEX points
    x = y = None
    for code, val in _pairs(path):
        if code == 0:
            if cur is not None:
                if cur.kind == "VERTEX" and poly is not None:
                    poly.points.extend(cur.points)
                elif cur.kind == "SEQEND":
                    poly = None
                else:
                    ents.append(cur)
                    poly = cur if cur.kind == "POLYLINE" else None
            cur, in_app = None, False
            if val == "SECTION":
                section_next = True
            elif val == "ENDSEC":
                in_entities = False
            elif val == "EOF":
                break
            elif in_entities:
                cur = Entity(kind=val)
            continue
        if section_next and code == 2:
            in_entities, section_next = (val == "ENTITIES"), False
            continue
        if cur is None:
            continue
        if code == 5:
            cur.handle = val
        elif code == 8:
            cur.layer = val
        elif code in (10, 11):
            x = float(val)
        elif code in (20, 21):
            y = float(val)
            cur.points.append((x, y, 0.0))
        elif code in (30, 31) and cur.points:
            px, py, _ = cur.points[-1]
            cur.points[-1] = (px, py, float(val))
        elif code == 1001:
            in_app = (val.upper() == app.upper())
        elif code == 1000 and in_app and "=" in val:
            k, v = val.split("=", 1)
            cur.keys[k.strip().upper()] = v.strip()
    return ents
