#!/bin/sh
# Builds the ready-to-run Windows folder and commits it to the "release" branch, which is
# what Install-StruKit.bat and StruKit-Get-Latest.bat download. Run from the repo root on
# main, after the tests pass and main is committed:   sh tools_make_release.sh
set -e
python -m pytest -q
SHA=$(git rev-parse HEAD)
VER=$(python -c "import strukit; print(strukit.__version__)")
OUT=$(mktemp -d)
cp -r windows/. "$OUT"/
mkdir -p "$OUT/app"
cp -r strukit "$OUT/app/strukit"
find "$OUT" -name __pycache__ -type d -prune -exec rm -rf {} +
printf 'StruKit build %s\r\ncommit %s\r\n' "$VER" "$SHA" > "$OUT/app/VERSION.txt"
WT=$(mktemp -d)
if git show-ref --verify --quiet refs/remotes/origin/release; then
  git worktree add -q -B release "$WT" origin/release
else
  git worktree add -q --detach "$WT"
  (cd "$WT" && git checkout -q --orphan release && git rm -rfq . )
fi
(cd "$WT" && find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + && cp -r "$OUT"/. . \
  && printf '* -text\n' > .gitattributes && git add -A \
  && git commit -qm "StruKit build $VER (from main $SHA)" && git push -q origin release)
git worktree remove --force "$WT"
echo "release branch now at build $VER"
