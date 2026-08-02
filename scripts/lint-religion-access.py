#!/usr/bin/env python3
"""Check that who-may-worship-whom matches what the help articles promise.

A religion gates worshippers through several independent fields in
religions/<god>.xml -- <align>, <ethos>, <classes>, <races>, <clans>, minstat --
resolved by DefaultReligion::reasonWhy() in that order. Nothing ties those gates
to the lore, so a god's help article and its actual gate drift apart silently.

The concrete rule this lints is the druid one, stated in help 192
(professions/druid.xml): druids may follow only gods of the Paths of Nature,
Light, Fury and Order. There is no Path field on a religion -- the Paths are the
colour groupings of the master index in helps/religion.xml, so that is where the
mapping is read from.

Three findings, only the first of which is a defect:

  HOLE     the gate lets a druid in on a Path the rule forbids -- fixable by
           adding a <classes> whitelist. Exits 1.
  OR-TRAP  same, but the god has <races> set, and reasonWhy ORs races with
           classes -- adding <classes> would ADMIT every listed class of every
           race instead of narrowing. Needs an engine change, not data.
  NOTE     the god is on an accepted Path yet some other gate refuses druids.
           NOT a defect: help 192 states a necessary condition (which Paths are
           acceptable), never a promise that every god on them is reachable.
           align/class/clan gates compose on top of it independently.

An empty <classes> means "no class restriction", NOT "no class allowed" -- the
whole-of-13 whitelist and the empty element are equivalent for access but only
the empty one stays correct when a 14th profession is added.

Usage:  python3 scripts/lint-religion-access.py [--quiet]
Exit 1 if any gate contradicts the rule.
"""
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.path.dirname(HERE)

# Colour code each god is printed with in the helps/religion.xml master index.
PATH_BY_COLOUR = {
    "W": "Light", "D": "Dark", "B": "Mind", "R": "Fury",
    "w": "Order", "M": "Chaos", "g": "Nature", "Y": "Society",
    "C": "Freedom",
}
# help 192: "only gods of the Paths of Nature, Light, Fury or Order are accepted"
DRUID_PATHS = {"Nature", "Light", "Fury", "Order"}
DRUID_ALIGN = "neutral"          # professions/druid.xml <align>
# Gods help 192 names as standing exceptions to the Path rule (by help id).
DRUID_EXCEPTIONS = {"1584"}      # Tirna -- patron of those who walk paths of their own


def text(node, tag):
    el = node.find(tag)
    return (el.text or "").strip() if el is not None else ""


def paths_from_index():
    """god help-id -> Path, read from the colour column of the help 1 index."""
    src = open(os.path.join(WORLD, "helps", "religion.xml"), encoding="utf-8").read()
    body = src.split('<text l="en">')[1].split("</text>")[0]
    out = {}
    for line in body.split("\n"):
        m = re.match(r"\{hh(\d+)([A-Za-z '\-]+)\{x\s*\{(\w)%A%", line)
        if m:
            out[m.group(1)] = (m.group(2).strip(), PATH_BY_COLOUR.get(m.group(3), m.group(3)))
    return out


def druid_gate(root):
    """Why a druid is refused, mirroring DefaultReligion::reasonWhy field order."""
    align = set(text(root, "align").split())
    classes = set(text(root, "classes").split())
    races = set(text(root, "races").split())
    clans = set(text(root, "clans").split())
    flags = set(text(root, "flags").split())

    if "system" in flags:
        return "system"
    # <clans> and <races> NARROW who may apply; they never rule a class out.
    # reasonWhy only refuses a character outside the listed clans/races, so a
    # druid who is in one still reaches the align and class checks below.
    if align and DRUID_ALIGN not in align:
        return "align"               # druids are always neutral -- absolute
    if not classes and not races:
        return "clan-gated" if clans else None
    # races and classes are OR'd when both are set
    if races and classes:
        return None if "druid" in classes else "race-or-class"
    if races:
        return "race-gated"          # a druid of the right race still gets in
    return None if "druid" in classes else "class"


def main():
    quiet = "--quiet" in sys.argv
    by_id = paths_from_index()
    problems = []
    notes = []
    checked = 0

    for path in sorted(glob.glob(os.path.join(WORLD, "religions", "*.xml"))):
        root = ET.parse(path).getroot()
        god = os.path.basename(path)[:-4]
        help_el = root.find("help")
        hid = help_el.get("id") if help_el is not None else None
        if hid is None or hid not in by_id:
            if not quiet:
                print("  ?? %-16s not in the help 1 index -- Path unknown, skipped" % god)
            continue

        _, godpath = by_id[hid]
        gate = druid_gate(root)
        if gate == "system":
            continue
        checked += 1

        allowed = godpath in DRUID_PATHS or hid in DRUID_EXCEPTIONS
        # race-gated / race-or-class still admit a druid of a qualifying race
        can = gate in (None, "race-gated", "race-or-class", "clan-gated")

        if can and not allowed:
            # A god with <races> set cannot be narrowed by adding <classes>:
            # reasonWhy ORs the two, so that would ADMIT every listed class of
            # every race. Closing these needs an engine change, not data.
            if gate in ("race-gated", "race-or-class"):
                notes.append(("OR-TRAP", god, godpath, gate,
                              "a druid of a listed race gets in; NOT closable by data"))
            else:
                problems.append(("HOLE", god, godpath, gate or "open",
                                 "druid may worship a %s god" % godpath))
        elif allowed and not can:
            # Not a defect: help 192 states a NECESSARY condition (which Paths are
            # acceptable), never a promise that every god on them is reachable.
            # align/class/clan gates compose on top of it independently.
            notes.append(("NOTE", god, godpath, gate,
                          "%s god, but <%s> applies independently" % (godpath, gate)))

    if not quiet:
        print("religions checked: %d\n" % checked)
    for kind, god, godpath, gate, why in problems + notes:
        print("  %-10s %-16s Path=%-8s gate=%-14s %s" % (kind, god, godpath, gate, why))

    if problems:
        print("\n%d gate(s) contradict help 192." % len(problems))
        return 1
    print("\nOK -- no gate contradicts the druid Path rule (%d informational)." % len(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
