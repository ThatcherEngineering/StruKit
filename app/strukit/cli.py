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


# ---------------------------------------------------------------- StruKit project files
KIND_OF = {"steel_beam": "MEMBER", "steel_column": "MEMBER", "frame": "MEMBER", "footing_iso": "FTG",
           "footing_cont": "FTG", "footing_moment": "FTG", "weld": "CONN", "bolts": "CONN", "single_plate": "CONN", "end_plate": "CONN", "cap_plate": "CONN", "through_plate": "CONN", "cutout_plate": "CONN", "wt_flange": "CONN", "beam_hss_moment": "CONN", "stiffened_seat": "CONN", "flush_end_plate": "CONN", "base_plate_biaxial": "CONN", "seat": "CONN", "base_plate": "CONN", "base_plate_moment": "CONN", "base_plate_uplift": "CONN", "snow": "LOAD", "wood_beam": "MEMBER", "decking": "MEMBER", "wood_post": "MEMBER", "shear_wall": "MEMBER", "lvl_beam": "MEMBER", "lvl_post": "MEMBER", "glulam_beam": "MEMBER", "wey_beam": "MEMBER", "ijoist": "MEMBER", "wey_post": "MEMBER", "builtup_post": "MEMBER", "perforated_wall": "MEMBER", "ftao_wall": "MEMBER", "snow_drift": "LOAD", "snow_corner": "LOAD", "rain_load": "LOAD", "guard": "MEMBER", "hss_column": "MEMBER", "stair_stringer": "MEMBER", "tension_member": "MEMBER", "angle_strut": "MEMBER", "angle_beam": "MEMBER", "crane_runway": "MEMBER", "shear_lug": "CONN", "stair_tread": "MEMBER", "glulam_post": "MEMBER", "wind_pressure": "LOAD", "wind_free_roof": "LOAD", "wind_kzt": "LOAD", "wind_enclosure": "LOAD", "wind_mwfrs": "LOAD", "wind_cc_walls": "LOAD", "wind_cc_roof": "LOAD", "wind_cc_parapet": "LOAD", "seismic_elf": "LOAD", "live_load": "LOAD", "diaphragm": "MEMBER", "collector": "MEMBER", "nailed_connection": "CONN", "nail_withdrawal": "CONN", "lag_connection": "CONN", "lag_withdrawal": "CONN", "screw_connection": "CONN", "screw_withdrawal": "CONN", "bolted_connection": "CONN"}


def _project(path):
    import json
    if not os.path.isfile(path):
        raise FileNotFoundError(f"file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("format") != "strukit-project":
        raise ValueError(f"{os.path.basename(path)} is not a StruKit project file")
    return data


def _solve_project(data):
    """Every member of a project file through the same calculations as the StruKit window.
    Returns (problems, results rows, counts, members that calculated)."""
    from .gui import calc
    proj, members = data.get("project") or {}, data.get("members") or []
    problems, rows, good = [], [], []
    counts = {"members": len(members), "ok": 0, "flagged": 0}
    if not members:
        problems.append("the project has no members")
    seen = set()
    for n, m in enumerate(members, 1):
        mark = (m.get("values") or {}).get("mark") or f"(member {n}, no mark)"
        if mark in seen:
            problems.append(f"{mark}: two members have this mark")
        seen.add(mark)
        if m.get("kind") not in calc.FORMS:
            problems.append(f"{mark}: unknown member type '{m.get('kind')}'")
            continue
        r = calc.results(m["kind"], m.get("values") or {}, proj, members)
        if r["state"] != "done":
            problems += [f"{mark}: {t}" for t in r["messages"]]
            continue
        good.append(m)
        counts["ok" if r["status"] == "OK" else "flagged"] += 1
        kind = KIND_OF[m["kind"]]
        for x in r["rows"]:
            rows.append(dict(KIND=kind, ID=mark, HANDLE="", CHECK=x["check"], COMBO=x["combo"], DEMAND=x["demand"],
                             CAPACITY=x["capacity"], UNIT=x["unit"], DC=x["dc"], STATUS=x["status"],
                             SOURCE=x["source"], NOTE=x["note"], MARK=mark))
        for x in r["members"]:                              # the members of a frame
            rows.append(dict(KIND="MEMBER", ID=f"{mark}/{x['member']}", HANDLE="", CHECK="axial, bending and shear",
                             COMBO=x["combo"], DEMAND=x["ratio"], CAPACITY=1.0, UNIT="", DC=x["ratio"],
                             STATUS=x["status"], SOURCE="AISC 360-22 H1.1, G2.1",
                             NOTE=f"{x['shape']}; axial {x['axial']:.1f} kip {x['sense']}; moment {x['moment']:.1f} kip-ft; "
                                  f"shear {x['shear']:.1f} kip", MARK=mark))
    return problems, rows, counts, good


def _project_cmd(a, solve):
    from .outputs import FLAGS, write_results
    src = os.path.abspath(a.src)
    folder, name = os.path.dirname(src), os.path.basename(src)
    stem = os.path.splitext(src)[0]
    results = os.path.abspath(a.results) if a.results else stem + "-stresults.csv"
    counts, pdf = {}, None
    try:
        with _Lock(folder):
            data = _project(src)
            problems, rows, counts, good = _solve_project(data)
            if solve and not problems:
                from .gui import calc
                pdf = stem + "-calcs.pdf"
                tmp = pdf + ".tmp"
                sheets, _ = calc.package_pdf(data.get("project") or {}, good, tmp)
                os.replace(tmp, pdf)
                write_results(results, (data.get("project") or {}).get("number") or name, rows)
                counts["sheets"] = sheets
    except (OSError, ValueError, RuntimeError) as e:
        problems = [str(e)]
    if problems:                                           # a failed run never touches the previous results
        status = FAILED
        msgs = [f"{'PREFLIGHT' if not solve else 'RUN'}: {len(problems)} input problem(s)"] + problems
        write_status(folder, status, name, {"preflight_only": not solve, "problems": len(problems), **counts})
    elif not solve:
        status = OK
        msgs = [f"PREFLIGHT: no input problems; {counts['members']} member(s)"]
        write_status(folder, status, name, {"preflight_only": True, "problems": 0, **counts})
    else:
        status = FLAGS if counts["flagged"] else OK
        msgs = [f"{counts['members']} member(s): {counts['ok']} pass, {counts['flagged']} with flags",
                f"results: {results}", f"calc package: {pdf} ({counts['sheets']} sheets)"]
        msgs += [f"FLAG {r['ID']}: {r['CHECK']} D/C {r['DC']:.2f} ({r['COMBO']})" for r in rows if r["STATUS"] == "FLAG"]
        write_status(folder, status, name, {**counts, "calc_package": pdf}, results)
    write_log(folder, status, name, msgs)
    if not a.quiet:
        print("\n".join([f"{status} {name}"] + msgs))
    return EXIT[status]


def _dispatch(a, dxf_fn, solve):
    if a.src and a.src.lower().endswith(".strukit"):
        return _project_cmd(a, solve)
    if a.src and not a.from_dxf:
        folder = os.path.dirname(os.path.abspath(a.src))
        msg = [f"StruKit {__version__} reads StruKit project files (.strukit) with --from. The drawing "
               "export format (<name>-struct.csv) is not read yet. No results were written."]
        write_log(folder, FAILED, os.path.basename(a.src), msg)
        write_status(folder, FAILED, os.path.basename(a.src), {"problems": 1})
        if not a.quiet:
            print("\n".join([f"{FAILED} {os.path.basename(a.src)}"] + msg))
        return EXIT[FAILED]
    if not a.from_dxf:
        print("FAILED give --from <project.strukit> (or --from-dxf <file>)")
        return EXIT[FAILED]
    return dxf_fn(a)


def main(argv=None):
    p = argparse.ArgumentParser(prog="strukit")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd, fn, solve in (("preflight", cmd_preflight, False), ("run", cmd_run, True)):
        s = sub.add_parser(cmd)
        s.add_argument("--from", dest="src")
        s.add_argument("--from-dxf")
        s.add_argument("--results")
        s.add_argument("--quiet", action="store_true")
        s.set_defaults(fn=lambda a, fn=fn, solve=solve: _dispatch(a, fn, solve))
    a, _unknown = p.parse_known_args(argv)      # unknown flags are ignored, never fatal
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
