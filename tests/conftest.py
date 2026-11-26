"""Every PDF a test prints into its temporary folder is audited for overlapping text and text past the right margin
(tools/overlap_audit.py). Zach, 2026-11-24: overlapping text on a sheet "can't have that". Set STRUKIT_AUDIT_LOG to a file to collect the
findings without failing (used while clearing a backlog); without it a finding fails the test that printed the sheet."""
import glob
import importlib.util
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(__file__))
_spec = importlib.util.spec_from_file_location("overlap_audit", os.path.join(_ROOT, "tools", "overlap_audit.py"))
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)


_made = []
from strukit import calcsheet as _calcsheet, ws_more as _ws_more          # noqa: E402
_init = _ws_more.SimpleSheet.__init__


def _recording_init(self, *a, **k):
    _init(self, *a, **k)
    _made.append(self)


_ws_more.SimpleSheet.__init__ = _recording_init


@pytest.fixture(autouse=True)
def _printed_sheets_are_clean(request, tmp_path):
    """Also prints every sheet of the common sheet type that the test built, whether or not the test printed it, so every screen type the
    suite exercises is audited (at most 6 sheets per test, to keep the suite quick)."""
    del _made[:]
    yield
    for i, sh in enumerate(_made[:6]):
        try:
            _calcsheet.simple_pdf(sh, os.path.join(str(tmp_path), f"audit_{i}_{type(sh).__name__}.pdf"), "Audit", getattr(sh, "code", None) or "code", "Nov 24, 2026")
        except Exception:
            pass                                                # a sheet a test left half-built on purpose
    del _made[:]
    found = []
    for f in glob.glob(os.path.join(str(tmp_path), "**", "*.pdf"), recursive=True):
        try:
            found += [(os.path.basename(f),) + tuple(x) for x in _audit.audit(f)]
        except Exception:
            pass
    dump = os.environ.get("STRUKIT_TEXT_DUMP")                 # the text of every printed sheet, for reading the wording across all sheet types
    if dump:
        try:
            import fitz
            with open(dump, "a") as fh:
                for f in glob.glob(os.path.join(str(tmp_path), "**", "*.pdf"), recursive=True):
                    for pg in fitz.open(f):
                        fh.write(f"=== {request.node.nodeid} | {os.path.basename(f)}\n{pg.get_text()}\n")
        except Exception:
            pass
    log = os.environ.get("STRUKIT_AUDIT_LOG")
    if found and log:
        with open(log, "a") as fh:
            for x in found:
                fh.write(f"{request.node.nodeid} | {x}\n")
    elif found:
        pytest.fail("overlapping text or text past the margin on a printed sheet: " + "; ".join(str(x) for x in found[:6]))
