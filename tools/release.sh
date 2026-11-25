#!/bin/sh
# Release one build: run every test, and only if all pass commit, push main, and rebuild the release branch.
# usage (from anywhere):  sh tools/release.sh "commit subject" ["commit trailer lines"]
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH="$(pwd)"
python3 -m pytest -q -x > /tmp/strukit-release-tests.txt 2>&1 || { echo "TESTS FAILED - not released"; tail -5 /tmp/strukit-release-tests.txt; exit 1; }
tail -1 /tmp/strukit-release-tests.txt
git add -A
if [ -n "$2" ]; then git commit -q -m "$1" -m "$2"; else git commit -q -m "$1"; fi
git push -q origin main || { echo "PUSH FAILED"; exit 1; }
sh tools_make_release.sh 2>&1 | tail -1
git status --short | wc -l
