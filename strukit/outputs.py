"""Write the run outputs: results CSV, log, status JSON. Same contract as HydroKit.

- results: line 1 signature, line 2 column names, CRLF, ASCII, no quotes, ';' for commas,
  blank = no value. Written to a temp name then renamed; a .done marker follows.
- log: first line is OK / SOLVED WITH FLAGS / FAILED.
- a failed run never touches the previous results file.
"""
import json
import os
from datetime import datetime

from . import __version__

SIGNATURE = "STRUKIT-RESULTS"
FORMAT = "1"
COLUMNS = ["KIND", "ID", "HANDLE", "CHECK", "COMBO", "DEMAND", "CAPACITY", "UNIT",
           "DC", "STATUS", "SOURCE", "NOTE"]
OK, FLAGS, FAILED = "OK", "SOLVED WITH FLAGS", "FAILED"
EXIT = {OK: 0, FLAGS: 1, FAILED: 2}


def _clean(v):
    if v is None:
        return ""
    s = v if isinstance(v, str) else (f"{v:.4g}" if isinstance(v, float) else str(v))
    s = s.replace(",", ";").replace("\r", " ").replace("\n", " ")
    return s.encode("ascii", "replace").decode("ascii")


def _atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def write_results(path, project, rows):
    cols = list(COLUMNS)
    for r in rows:                       # extra columns are appended, never reordered
        for k in r:
            if k not in cols:
                cols.append(k)
    lines = [f"{SIGNATURE},{FORMAT},{_clean(project)}", ",".join(cols)]
    lines += [",".join(_clean(r.get(c)) for c in cols) for r in rows]
    done = path + ".done"
    if os.path.exists(done):
        os.remove(done)
    _atomic(path, "\r\n".join(lines) + "\r\n")
    _atomic(done, datetime.now().isoformat(timespec="seconds") + "\r\n")


def write_log(folder, status, name, messages):
    text = "\r\n".join([f"{status} {name}", f"StruKit {__version__}", ""] + list(messages)) + "\r\n"
    _atomic(os.path.join(folder, "strukit.log"), text.encode("ascii", "replace").decode("ascii"))


def write_status(folder, status, name, counts, results_path=None):
    data = {"status": status, "exit": EXIT[status], "name": name, "version": __version__,
            "time": datetime.now().isoformat(timespec="seconds"),
            "results": results_path, **counts}
    _atomic(os.path.join(folder, "strukit-status.json"), json.dumps(data, indent=1) + "\n")
