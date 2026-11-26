"""Every AISC Manual citation names its edition, and the 16th Ed. numbers are the ones confirmed in AISC Design Examples v16.0 and Design
Guide 24 (2nd Ed.): tmin 3.09 D / Fu is Eq. 9-6, 6.19 D / Fu is Eq. 9-7 (9-2 and 9-3 in the 15th Ed.); no-prying thickness is Eq. 9-34."""
import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[1] / "strukit"


def test_manual_citations_name_an_edition():
    bad = []
    for f in SRC.rglob("*.py"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            for m in re.finditer(r"AISC Manual (?!\(1[456]th Ed\.\)|1[456]th Ed\.)", line):
                bad.append(f"{f.name}:{i}")
    assert not bad, bad


def test_renumbered_equations():
    text = "\n".join(f.read_text() for f in SRC.rglob("*.py"))
    assert "(16th Ed.) Eq. 9-74" not in text and '(16th Ed.) Eq. 9-2"' not in text and '(16th Ed.) Eq. 9-3"' not in text
    assert "(16th Ed.) Eq. 9-34" in text and "(16th Ed.) Eq. 9-6" in text and "(16th Ed.) Eq. 9-7" in text
