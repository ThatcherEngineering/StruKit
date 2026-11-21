"""Command line: strukit preflight | run. No window, no prompts (same as HydroKit --quiet)."""
import argparse
import os
import sys

from . import XDATA_APP, __version__
from .dxfin import read_entities
from .outputs import EXIT, FAILED, OK, write_log, write_status
from .preflight import check
from .sidecar import read_sidecar


def _sidecar_for(dxf):
    return os.path.splitext(dxf)[0] + ".csv"


def _load(dxf):
    side = _sidecar_for(dxf)
    for p in (dxf, side):
        if not os.path.isfile(p):
            raise FileNotFoundError(f"file not found: {p}")
    project, _tables = read_sidecar(side)
    return project, read_entities(dxf, XDATA_APP)


class _Lock:
    def __init__(self, folder):
        self.path = os.path.join(folder, "strukit.lock")

    def __enter__(self):
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError("another StruKit run is using this folder (strukit.lock)")
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)

    def __exit__(self, *a):
        if os.path.exists(self.path):
            os.remove(self.path)


def cmd_preflight(a):
    folder = os.path.dirname(os.path.abspath(a.from_dxf))
    name = os.path.basename(a.from_dxf)
    try:
        project, ents = _load(a.from_dxf)
        problems, counts = check(project, ents)
    except (OSError, ValueError) as e:
        problems, counts = [str(e)], {}
    status = FAILED if problems else OK
    msgs = [f"PREFLIGHT: {len(problems)} input problem(s)"] + problems
    write_log(folder, status, name, msgs)
    write_status(folder, status, name, {"preflight_only": True, "problems": len(problems), **counts})
    if not a.quiet:
        print("\n".join([f"{status} {name}"] + msgs))
    return EXIT[status]


def cmd_run(a):
    folder = os.path.dirname(os.path.abspath(a.from_dxf))
    name = os.path.basename(a.from_dxf)
    try:
        with _Lock(folder):
            project, ents = _load(a.from_dxf)
            problems, counts = check(project, ents)
            if not problems:
                problems = [f"StruKit {__version__} has no calculation modules yet: "
                            "preflight only. No results were written."]
    except (OSError, ValueError, RuntimeError) as e:
        problems, counts = [str(e)], {}
    # A failed run never touches the previous results file.
    write_log(folder, FAILED, name, problems)
    write_status(folder, FAILED, name, {"problems": len(problems), **counts})
    if not a.quiet:
        print("\n".join([f"{FAILED} {name}"] + problems))
    return EXIT[FAILED]


def main(argv=None):
    p = argparse.ArgumentParser(prog="strukit")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd, fn in (("preflight", cmd_preflight), ("run", cmd_run)):
        s = sub.add_parser(cmd)
        s.add_argument("--from-dxf", required=True)
        s.add_argument("--results")
        s.add_argument("--quiet", action="store_true")
        s.set_defaults(fn=fn)
    a, _unknown = p.parse_known_args(argv)      # unknown flags are ignored, never fatal
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
