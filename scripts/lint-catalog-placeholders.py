#!/usr/bin/env python3
"""Catch EN/UA catalog values whose placeholders read a different arg type than the RU key.

The formatter (dreamland_code plug-ins/output/msgformatter.cpp) takes the arg type from
the conversion letter. A translation that swaps one (%G -> %g) or drops one so that
sequential args shift (%1$G...%d -> ...%d) feeds a character into argInt(). In Fenia
that throws "Invalid cast: expected 'number' got 'OBJECT'" and kills the whole call (a
quest that never starts). In C++ varargs it reads garbage memory.
check-translation-batch.py compares code multisets and misses that positional drift.

Parser mirrors msgformatter's state machine: positional vs sequential args,
#/-/width/limit/^/_, the case digit after C/O/P/T/p/N/K, |-separated form runs, and
invalid conversions. Old act() $-codes are mapped per act.cpp. Positional args follow
Fenia's RegFormatter (shiftArg sets the cursor); C++ VarArgFormatter keeps the max,
which differs only for a sequential conversion after a backward positional (none today).

Reports:
  TYPE-MISMATCH  the translation reads an arg as NOUN/INT/STR where RU reads another type
  ARG-NOT-IN-RU  the translation reads an arg RU never touches
  INVALID-CONV   '%' followed by a letter the formatter does not know (Cyrillic look-alikes),
                 in the RU key too

Usage: lint-catalog-placeholders.py [shard.json ...]   (default: every shard)
Exit 1 on any finding.
"""
import glob, json, os, re, sys

CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'translations')

# (section, RU key) -> reason. One string each, never a whole section.
ALLOW = {
    ('plug-ins/comm/configs.cpp', '\nИспользуй команду {hc{yрежим %s %s{x для изменения.'):
        'caller passes 6 args, RU reads 1-2, EN 3-4, UA 5-6 by design',
    ('plug-ins/services/shop/oldshop.cpp', 'Я дал%2$Gо||а бы тебе %3s за %4$O4, но у меня нет денег.'):
        'tell_fmt prepends %2$^C1, so the sequential %3s reads arg 3',
}

ACT = {
    'C': '%3$C', 'G': '%3$G', 'O': '%3$O',
    'E': '%3$P1', 'S': '%3$P2', 'M': '%3$P3', 'X': '%3$P4', 'Y': '%3$P5', 'Z': '%3$P6', 'U': '%3$P7',
    'c': '%1$C', 'g': '%1$G', 'o': '%2$O',
    'e': '%1$P1', 's': '%1$P2', 'm': '%1$P3', 'x': '%1$P4', 'y': '%1$P5', 'z': '%1$P6', 'u': '%1$P7',
    'T': '%3$s', 'N': '%3$N', 'd': '%3$S', 't': '%2$s', 'n': '%2$N', 'w': '%2$w', 'W': '%3$w',
}

CLS = {}
for c in 'diluf': CLS[c] = 'INT'
for c in 'pIg': CLS[c] = 'INT'
for c in 'sSN': CLS[c] = 'STR'
for c in 'COPTGn': CLS[c] = 'NOUN'
CLS['w'] = 'LANGTEXT'
CLS['c'] = 'CHAR'
CLS['K'] = 'SKILL'


def parse(fmt):
    """List of (argIndex, convChar); invalid conversions come back as 'INVALID:<ch>'."""
    uses = []
    f = fmt + '\0'
    state, argcnt, cur, num, i = 0, 0, None, 0, 0
    while i < len(f):
        ch = f[i]
        if state == 0:
            if ch == '%':
                num, state = 0, 1
            elif ch == '\0':
                break
            i += 1
            continue
        if state == 1:
            if ch == '%':
                state = 0
                i += 1
                continue
            state = 2
        if state == 2:
            if ch.isdigit():
                num = num * 10 + int(ch)
                i += 1
                continue
            if ch == '$':
                cur = argcnt = num
                num, state = 0, 3
                i += 1
                continue
            argcnt += 1
            cur, state = argcnt, 3
        if state == 3:
            if ch in '#-':
                i += 1
                continue
            state = 4
        if state == 4:
            if ch.isdigit():
                i += 1
                continue
            state = 5
        if state == 5:
            if ch.isdigit() or ch == '.':
                i += 1
                continue
            state = 55
        if state == 55:
            if ch in '^_':
                i += 1
                continue
            state = 6
        if state == 6:
            if ch in 'dilufsSwc':
                uses.append((cur, ch))
                state = 0
                i += 1
                continue
            if ch in 'CPTOKNp':
                uses.append((cur, ch))
                state = 7
                i += 1
                continue
            if ch in 'GIgn':
                uses.append((cur, ch))
                state = 8
                i += 1
                continue
            uses.append((cur, 'INVALID:' + ch))
            state = 0
            continue
        if state == 7:
            state = 0
            i += 1
            continue
        if state in (8, 9, 10, 11):
            if ch == '|' and state < 11:
                state += 1
                i += 1
                continue
            if ch in "|\0 -?!,.:{()":
                state = 0
                continue
            i += 1
            continue
    return uses


def act_codes(fmt):
    return ''.join(ACT.get(m.group(1), '') + '1 ' for m in re.finditer(r'(?<![0-9])\$(.)', fmt))


def classes(fmt):
    types, invalid = {}, []
    pairs = parse(fmt) + [(('act', a), c) for a, c in parse(act_codes(fmt))]
    for a, c in pairs:
        if c.startswith('INVALID'):
            invalid.append((a, c))
        else:
            types.setdefault(a, set()).add((CLS[c], c))
    return types, invalid


def lint(path):
    found = 0
    shard = os.path.basename(path)
    data = json.load(open(path, encoding='utf-8'))
    for sec, entries in data.items():
        if not isinstance(entries, dict):
            continue
        for ru, tr in entries.items():
            if not isinstance(tr, dict) or (sec, ru) in ALLOW:
                continue
            rtypes, rinvalid = classes(ru)
            for a, c in rinvalid:
                print(f"{shard}: {sec} [ru] INVALID-CONV arg{a} %{c[8:]!r}\n    ru: {ru}")
                found += 1
            rcls = {a: {t for t, _ in v} for a, v in rtypes.items()}
            for lang in ('en', 'ua'):
                t = tr.get(lang)
                if not isinstance(t, str) or not t:
                    continue
                ttypes, tinvalid = classes(t)
                for a, v in ttypes.items():
                    tc = {x for x, _ in v}
                    convs = ''.join(sorted(c for _, c in v))
                    if a not in rcls:
                        print(f"{shard}: {sec} [{lang}] ARG-NOT-IN-RU arg{a} %{convs}\n    ru: {ru}\n    {lang}: {t}")
                        found += 1
                    elif tc - rcls[a]:
                        rconvs = ''.join(sorted(c for _, c in rtypes[a]))
                        print(f"{shard}: {sec} [{lang}] TYPE-MISMATCH arg{a} ru=%{rconvs} {lang}=%{convs}\n    ru: {ru}\n    {lang}: {t}")
                        found += 1
                for a, c in tinvalid:
                    print(f"{shard}: {sec} [{lang}] INVALID-CONV arg{a} %{c[8:]!r}\n    {lang}: {t}")
                    found += 1
    return found


def main():
    args = sys.argv[1:]
    if args:
        paths = [a if os.path.exists(a) else os.path.join(CATALOG, a) for a in args]
    else:
        paths = sorted(glob.glob(os.path.join(CATALOG, '*.json')))
    found = sum(lint(p) for p in paths)
    if found:
        print(f"--- {found} placeholder finding(s)")
    sys.exit(1 if found else 0)


main()
