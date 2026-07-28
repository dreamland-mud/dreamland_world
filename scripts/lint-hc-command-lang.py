#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint-hc-command-lang.py -- flag {hc<command> ...{x} clickable links whose command
word is not a command of the language the string is written in.

A {hc} link is sent to the server verbatim when the player clicks it. The interpreter
resolves command names in the PLAYER'S language only, so an EN catalog value carrying
{hcсказать да{x} gives an English player a link that does nothing. The same trap in
reverse produces mixed strings like {hcсказать так{x} (RU verb, UA argument).

Reports, per language, every {hc} link whose first token does not resolve to a
registered command / social / alias of that language.

Command vocabulary is read from:
    commands/**/*.xml   <name l=..> and <aliases l=..>
    socials/*.xml                       <rusName>, <uaName>, EN = file stem
    prio/commands_*.json

Abbreviations resolve by prefix (as the interpreter does), so "к" is accepted for
"колдовать" and the report names what it resolves to.

Usage:
    dreamland_world/scripts/lint-hc-command-lang.py                    # lint the whole catalog
    dreamland_world/scripts/lint-hc-command-lang.py areas4.json ...    # only these shards
    dreamland_world/scripts/lint-hc-command-lang.py --vocab            # dump the resolved vocabulary
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

WORLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CATALOG = os.path.join(WORLD, 'config', 'translations')

HC = re.compile(r'\{hc(.*?)\{x')
# {lE<english>{lR<russian>{lU<ukrainian> -- per-viewer-language literal switch
LANGSEG = re.compile(r'\{l([eruERU])')
LANGS = ('en', 'ru', 'ua')
LANG_MARKER = {'en': 'e', 'ru': 'r', 'ua': 'u'}


def load_vocab():
    """({lang: {name: source}}, {source: langs-that-name-it}) for every command word."""
    vocab = {l: {} for l in LANGS}
    cmd_langs = {}

    for path in glob.glob(os.path.join(WORLD, 'commands', '**', '*.xml'), recursive=True):
        txt = open(path, encoding='utf-8', errors='replace').read()
        base = os.path.basename(path)
        for tag in ('name', 'aliases', 'alias'):
            for lang, val in re.findall(rf'<{tag}\s+l="(en|ru|ua)">([^<]*)</{tag}>', txt):
                if tag == 'name' and val.split():
                    cmd_langs.setdefault(base, set()).add(lang)
                for word in val.split():
                    vocab[lang].setdefault(word.lower(), base)

    # note channels (qnote, note, ...) live outside commands/
    for path in glob.glob(os.path.join(WORLD, 'notes', '*.xml')):
        txt = open(path, encoding='utf-8', errors='replace').read()
        base = os.path.basename(path)
        for tag in ('name', 'aliases'):
            for lang, val in re.findall(rf'<{tag}\s+l="(en|ru|ua)">([^<]*)</{tag}>', txt):
                if tag == 'name' and val.split():
                    cmd_langs.setdefault(base, set()).add(lang)
                for word in val.split():
                    vocab[lang].setdefault(word.lower(), base)

    for path in glob.glob(os.path.join(WORLD, 'socials', '*.xml')):
        txt = open(path, encoding='utf-8', errors='replace').read()
        base = os.path.basename(path)
        vocab['en'].setdefault(base[:-4].lower(), base)
        cmd_langs.setdefault(base, set()).update(LANGS)
        for tag, lang in (('rusName', 'ru'), ('uaName', 'ua')):
            m = re.search(rf'<{tag}>([^<]*)</{tag}>', txt)
            if m and m.group(1).strip():
                vocab[lang].setdefault(m.group(1).strip().lower(), base)

    for lang in LANGS:
        p = os.path.join(WORLD, 'prio', f'commands_{lang}.json')
        if not os.path.exists(p):
            continue
        for word in re.findall(r'"([^"]+)"', open(p, encoding='utf-8').read()):
            vocab[lang].setdefault(word.lower(), f'prio/commands_{lang}.json')

    return vocab, cmd_langs


def resolve(token, lang, vocab):
    """Return (ok, what_it_resolves_to). Exact hit first, then prefix, as the parser does."""
    t = token.lower()
    if t in vocab[lang]:
        return True, t
    hits = [w for w in vocab[lang] if w.startswith(t)]
    if hits:
        return True, min(hits, key=len)
    return False, None


def pick_lang(link, lang):
    """Collapse a {lE..{lR..{lU..} switch down to the segment this language sees."""
    parts = LANGSEG.split(link)
    if len(parts) == 1:
        return link
    want = LANG_MARKER[lang]
    out = parts[0]
    for i in range(1, len(parts) - 1, 2):
        if parts[i].lower() == want:
            out += parts[i + 1]
    return out


def first_token(link, lang):
    """First word of a {hc} link body, after language switches and colour codes."""
    body = pick_lang(link, lang).strip()
    while len(body) > 1 and body[0] == '{':
        body = body[2:].strip()
    return body.split()[0] if body.split() else ''


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    vocab, cmd_langs = load_vocab()

    if '--vocab' in sys.argv:
        for lang in LANGS:
            print(f'{lang}: {len(vocab[lang])} words')
        return 0

    shards = args or sorted(os.listdir(CATALOG))
    findings = []
    for fn in shards:
        if not fn.endswith('.json'):
            continue
        data = json.load(open(os.path.join(CATALOG, fn), encoding='utf-8'))
        for key, entries in data.items():
            for ru, v in entries.items():
                if not isinstance(v, dict):
                    continue
                for lang in LANGS:
                    val = ru if lang == 'ru' else (v.get(lang) or '')
                    if not val:
                        continue
                    for link in HC.findall(val):
                        tok = first_token(link, lang)
                        if tok.startswith('%'):
                            continue
                        if not tok:
                            findings.append(('NO-FORM', fn, key, lang, tok, link.strip()))
                            continue
                        if resolve(tok, lang, vocab)[0]:
                            continue
                        other = [l for l in LANGS if l != lang and resolve(tok, l, vocab)[0]]
                        if not other:
                            findings.append(('NOT-A-COMMAND', fn, key, lang, tok, link.strip()))
                            continue
                        # A command registered in one language only (most immortal
                        # commands) is typed the same way whatever the player speaks.
                        src = vocab[other[0]].get(resolve(tok, other[0], vocab)[1])
                        if src and lang not in cmd_langs.get(src, set()):
                            continue
                        findings.append((f'WRONG-LANG(is {"/".join(other)})',
                                         fn, key, lang, tok, link.strip()))

    counts = defaultdict(int)
    for f in findings:
        counts[f[0].split('(')[0]] += 1
    print(f'{len(findings)} bad {{hc}} links  ' +
          '  '.join(f'{k}={v}' for k, v in sorted(counts.items())))
    print('  WRONG-LANG   = command word belongs to another language; swap it')
    print('  NOT-A-COMMAND= link body is bare prose; needs a speech verb in front')
    print('  NO-FORM      = {lE/{lR/{lU switch has no segment for this language')
    print()
    for cls, fn, key, lang, tok, link in sorted(findings):
        print(f'[{lang}] {cls}  {fn} :: {key}')
        print(f'      {{hc{link}{{x   -- first token {tok!r}')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
