"""Read the sidecar CSV written beside the DXF by the ZET drawing tools.

Layout (same shape as HydroKit's sidecars): sections in [brackets].
  [project]   key,value rows
  [anything]  first row = column names, then one row per item
Plain ASCII, commas, no quotes; ';' stands for a comma inside text.
"""


def read_sidecar(path):
    project, tables = {}, {}
    section, header = None, None
    with open(path, "r", encoding="ascii", errors="replace") as f:
        for n, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section, header = line[1:-1].strip().lower(), None
                if section != "project":
                    tables.setdefault(section, [])
                continue
            if section is None:
                raise ValueError(f"{path} line {n}: data before the first [section]")
            cells = [c.strip() for c in line.split(",")]
            if section == "project":
                if len(cells) < 2:
                    raise ValueError(f"{path} line {n}: [project] rows are key,value")
                project[cells[0].upper()] = ",".join(cells[1:]).strip()
            elif header is None:
                header = [c.upper() for c in cells]
            else:
                if len(cells) != len(header):
                    raise ValueError(
                        f"{path} line {n}: [{section}] row has {len(cells)} fields, "
                        f"the header has {len(header)}")
                row = dict(zip(header, cells))
                row["_LINE"] = n
                tables[section].append(row)
    return project, tables
