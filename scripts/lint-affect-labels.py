#!/usr/bin/env python3
"""
Lint the web-client affect-panel curation.

The panel (plug-ins/web/impl.cpp AffectsWebPromptListener) shows every active affect,
picking its column + short label from the skill profile fields <webColumn>/<webLabel>.
A skill that applies a lasting affect but has no <webColumn> still shows -- auto-classified
(offensive -> mal, else -> enh) and labelled from its own <name> -- so nothing is silently
missing, but it lands in a guessed column with an un-abbreviated label.

This script lists those skills so the gap is a visible TODO, not a silent omission.
Run from the dreamland_world repo root:  python3 scripts/lint-affect-labels.py
"""
import os, re, sys

DIRS = ["generic-skills", "clan-skills", "other-skills", "race-aptitudes", "card-skills"]
VALID = {"pro", "det", "trv", "enh", "mal", "cln", "none"}

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

col_re = re.compile(r"<webColumn>([^<]*)</webColumn>")
name_re = re.compile(r'<name l="en">([^<]*)</name>')

uncurated, bad_col, curated = [], [], 0

for d in DIRS:
    dp = os.path.join(root, d)
    if not os.path.isdir(dp):
        continue
    for fn in sorted(os.listdir(dp)):
        if not fn.endswith(".xml"):
            continue
        p = os.path.join(dp, fn)
        txt = open(p, encoding="utf-8", errors="replace").read()
        # Only skills that apply a lasting affect are panel-relevant.
        if "<affect type=" not in txt:
            continue
        rel = os.path.join(d, fn)
        m = col_re.search(txt)
        if not m:
            names = name_re.findall(txt)
            uncurated.append((rel, names[-1] if names else "?"))
            continue
        curated += 1
        col = m.group(1).strip()
        if col not in VALID:
            bad_col.append((rel, col))

print("Affect-panel curation lint")
print("  curated skills (have <webColumn>): %d" % curated)
print("  uncurated affect skills (auto-classified): %d" % len(uncurated))

if bad_col:
    print("\nINVALID <webColumn> values (must be pro/det/trv/enh/mal/cln/none):")
    for rel, col in bad_col:
        print("  %-45s %r" % (rel, col))

if uncurated:
    print("\nUncurated affect skills -- add <webColumn>+<webLabel> for a proper column/label:")
    for rel, en in uncurated:
        print("  %-45s (%s)" % (rel, en))

# Non-zero exit only on hard errors (invalid column); uncurated is advisory.
sys.exit(1 if bad_col else 0)
