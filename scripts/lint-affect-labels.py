#!/usr/bin/env python3
"""
Lint the web-client affect-panel curation.

The panel (plug-ins/web/impl.cpp AffectsWebPromptListener) shows every active affect,
picking its column + short label from the skill profile fields <webColumn>/<webLabel>.
A skill with no <webColumn> still shows -- auto-classified (offensive spell -> mal,
everything else -> enh) and labelled from its own <name>. To keep an internal or
tracking affect out of the panel, say so explicitly: <webColumn>none</webColumn>.

Three checks:
  1. <webColumn> holds a legal value                          (hard error)
  2. no two skills share a (column, label) pair per language  (hard error --
     the panel de-dups on exactly that key, so the second one vanishes)
  3. skills still riding the auto-classify fallback           (advisory)

A skill is panel-relevant if it declares <affect type=...>, or a Fenia script names
it in `af.type = "..."` / `.Affect("...")`, or the engine applies it via
`postaffect_to_char(ch, gsn_x, ...)` / `af.type = gsn_x`. The Fenia and C++ halves
only run when dreamland_fenia / dreamland_fenia_public / dreamland_code sit next to
this repo -- without them the lint under-reports, and says so.

Run from the dreamland_world repo root:  python3 scripts/lint-affect-labels.py
"""
import os, re, sys

DIRS = ["generic-skills", "clan-skills", "other-skills", "race-aptitudes",
        "card-skills", "craft-skills"]
VALID = {"pro", "det", "trv", "enh", "mal", "cln", "none"}
LANGS = ("en", "ru", "ua")

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

col_re = re.compile(r"<webColumn>([^<]*)</webColumn>")
name_re = re.compile(r'<name l="en">([^<]*)</name>')
lab_re = re.compile(r'<webLabel l="([^"]*)">([^<]*)</webLabel>')
fenia_re = re.compile(r'af\.type\s*=\s*"([^"]+)"|\.Affect\(\s*"([^"]+)"')
cpp_re = re.compile(r'postaffect_to_char\s*\(\s*[^,]+,\s*gsn_(\w+)'
                    r'|\.type\s*=\s*gsn_(\w+)')


def _scan(repo, regex, suffixes, convert):
    """Affect names a sibling repo applies. Empty set if that repo isn't checked out."""
    base = os.path.join(os.path.dirname(root), repo)
    if not os.path.isdir(base):
        return set()
    found = set()
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for f in files:
            if suffixes and not f.endswith(suffixes):
                continue
            try:
                txt = open(os.path.join(dirpath, f), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in regex.finditer(txt):
                found.add(convert(m.group(1) or m.group(2)))
    return found


# Fenia names affects by skill name; C++ by gsn_ symbol, where _ stands for a space.
applied = set()
missing_repos = []
for repo, regex, sfx, conv in (
        ("dreamland_fenia", fenia_re, None, lambda s: s),
        ("dreamland_fenia_public", fenia_re, None, lambda s: s),
        ("dreamland_code", cpp_re, (".cpp", ".h"), lambda s: s.replace("_", " ")),
):
    if not os.path.isdir(os.path.join(os.path.dirname(root), repo)):
        missing_repos.append(repo)
        continue
    applied |= _scan(repo, regex, sfx, conv)

uncurated, bad_col, curated = [], [], 0
labels = {}      # (column, lang, lowercased label) -> first skill that claimed it
collisions = []

for d in DIRS:
    dp = os.path.join(root, d)
    if not os.path.isdir(dp):
        continue
    for fn in sorted(os.listdir(dp)):
        if not fn.endswith(".xml"):
            continue
        rel = os.path.join(d, fn)
        txt = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
        names = name_re.findall(txt)
        en = names[-1] if names else "?"
        # Panel-relevant: declares an affect handler, or Fenia applies an affect of this name.
        if "<affect type=" not in txt and en not in applied:
            continue

        m = col_re.search(txt)
        if not m:
            uncurated.append((rel, en))
            continue
        curated += 1
        col = m.group(1).strip()
        if col not in VALID:
            bad_col.append((rel, col))
            continue
        if col == "none":
            continue

        for lang, lab in lab_re.findall(txt):
            if lang not in LANGS or not lab.strip():
                continue
            # Case-sensitive on purpose: mirrors AffectPanelColumns::add exactly,
            # so this never reports a collision the panel does not actually have.
            key = (col, lang, lab.strip())
            if key in labels:
                collisions.append((rel, labels[key], col, lang, lab.strip()))
            else:
                labels[key] = rel

print("Affect-panel curation lint")
print("  curated skills (have <webColumn>): %d" % curated)
print("  uncurated affect skills (auto-classified): %d" % len(uncurated))
if missing_repos:
    print("  NOTE: not checked out next to this repo, so affects applied there are")
    print("        invisible to this lint: %s" % ", ".join(missing_repos))

if bad_col:
    print("\nINVALID <webColumn> values (must be pro/det/trv/enh/mal/cln/none):")
    for rel, col in bad_col:
        print("  %-45s %r" % (rel, col))

if collisions:
    print("\nDUPLICATE (column, label) -- the panel de-dups on this key, so one of the two")
    print("never renders. Give one of them a different <webLabel>:")
    for rel, other, col, lang, lab in collisions:
        print("  %-45s %s/%s %r  collides with %s" % (rel, col, lang, lab, other))

if uncurated:
    print("\nUncurated affect skills -- add <webColumn>+<webLabel> for a proper column/label,")
    print("or <webColumn>none</webColumn> if it should stay out of the panel:")
    for rel, en in uncurated:
        print("  %-45s (%s)" % (rel, en))

# Non-zero exit on hard errors (invalid column, colliding labels); uncurated is advisory.
sys.exit(1 if (bad_col or collisions) else 0)
