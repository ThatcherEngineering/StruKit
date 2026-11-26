"""Open a project in the StruKit window in a headless browser, recalculate every member, and report each member's result and any page error.
The check every new or changed screen gets before a release (CLAUDE.md).

usage:  python tools/browser_check.py project.strukit [--port 8899] [--select MARK]
needs:  playwright (pip install playwright) and a Chrome or Chromium; set STRUKIT_CHROME to its path if it is not /usr/bin/google-chrome.
For a button on a screen, add steps after the load in the same pattern, for example
    pg.locator("button", has_text="Run the 3D frame free to sway").evaluate("e => e.click()")
"""
import argparse
import json
import os
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--select", default="")
    ap.add_argument("--click", action="append", default=[], help="press a button on the Project page with this text first (repeatable)")
    a = ap.parse_args()
    d = json.load(open(a.project))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONPATH=root)
    srv = subprocess.Popen([sys.executable, "-m", "strukit.gui", "--port", str(a.port), "--no-browser"], env=env)
    time.sleep(5)
    bad = 0
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=os.environ.get("STRUKIT_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox", "--no-proxy-server"])
            pg = b.new_page(viewport=dict(width=1300, height=2400))
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(f"http://127.0.0.1:{a.port}/")
            pg.wait_for_timeout(1000)
            pg.evaluate("async (d) => { load(d, null); await recalcAll(); select('project'); }", d)
            pg.wait_for_timeout(2000)
            for t in a.click:
                pg.evaluate("() => select('project')")
                pg.wait_for_timeout(500)
                pg.locator("button", has_text=t).first.evaluate("e => e.click()")
                pg.wait_for_timeout(6000)
                print(f"pressed '{t}': {len(pg.evaluate('() => S.members'))} members")
            rows = pg.evaluate("() => S.members.map(m => { const r = R.get(m); return [m.values.mark || '', m.kind, "
                               "r ? (r.state !== 'done' ? (r.state || 'no result') : ((r.rows || []).some(x => x.status === 'FLAG') ? 'FLAG' : 'OK')) : 'no result', "
                               "r && r.state !== 'done' ? String(r.message || r.missing || '').slice(0, 120) : '']; })")
            for mark, kind, status, err in rows:
                print(f"{mark:<10} {kind:<26} {status:<10} {err}")
                bad += status not in ("OK", "FLAG")
            if a.select:
                i = [r[0] for r in rows].index(a.select)
                pg.evaluate(f"() => select({i})")
                pg.wait_for_timeout(2000)
                print(pg.locator("#res").inner_text()[:1500])
            print("page errors:", errs or "none")
            bad += len(errs)
            b.close()
    finally:
        srv.terminate()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
