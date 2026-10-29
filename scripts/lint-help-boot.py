#!/usr/bin/env python3
"""World-only twin of dreamland_tools help-id-guard.py: the help mistakes that
crash-loop a boot. Keep the two in step.

1. Duplicate help id inside the world: HelpManager::registrate throws.
2. A skill with <spell>/<affect>/<command> but no <help>: DefaultSpell,
   DefaultAffectHandler and DefaultSkillCommand take their id from the skill
   help and throw "... ID not found or zero". Hide a help by level, never
   delete it or move it to another file.

Area helps are not checked here (dreamland_areas is private); the reboot
window runs the full world + areas guard.

usage: lint-help-boot.py [world_dir]   exit 1 on any finding
"""
import os
import re
import sys
from collections import defaultdict

WORLD_ID = re.compile(r'<(?:help|node) id="(\d+)"')
HANDLERS = ('<spell', '<affect', '<command')


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    owners = defaultdict(list)
    nohelp = []
    for dirpath, dirnames, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if rel.split(os.sep)[0] in ('areas.local', 'fenia', '.git'):
            dirnames[:] = []
            continue
        for f in files:
            if not f.endswith('.xml'):
                continue
            path = os.path.join(dirpath, f)
            name = os.path.relpath(path, root)
            with open(path, encoding='utf-8', errors='ignore') as fh:
                text = fh.read()
            for hid in WORLD_ID.findall(text):
                owners[hid].append(name)
            if '<skill' in text[:300] and '<help' not in text and any(h in text for h in HANDLERS):
                nohelp.append(name)

    dups = {k: v for k, v in owners.items() if len(v) > 1}
    for hid in sorted(dups, key=int):
        print('DUP help id %s: %s' % (hid, ', '.join(dups[hid])))
    for name in sorted(nohelp):
        print('NO HELP on a skill with a handler: %s' % name)
    if dups or nohelp:
        return 1
    print('ok: %d help ids, no duplicates, every handler skill has a <help>' % len(owners))
    return 0


if __name__ == '__main__':
    sys.exit(main())
