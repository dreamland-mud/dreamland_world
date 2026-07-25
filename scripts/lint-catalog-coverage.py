#!/usr/bin/env python3
"""Verify every localized string in a C++/Fenia source file has an en+ua catalog entry.

The `_("<ru>")` / `l(ch,"<ru>")` wrappers key a MultiMessage by (repo-relative FILE
path, exact RU literal); at display time it resolves per viewer, falling back to RU if
the catalog lacks the phrase. So a wrapped string with no en/ua entry SILENTLY renders
Russian to English/Ukrainian players -- a leak that byte-match/lint-l10n/placeholder
checks do NOT catch (they validate catalog values, not that a source `_()` reached the
catalog at all). This is the source-vs-catalog diff, hand-rolled ~every C++ l10n batch.

For each source file it:
  1. extracts the RU string literals inside `_(...)` and `l(ch|pch, ...)` calls
     (adjacent C++ string-literal concatenation is joined -- the catalog key is the
     joined form), keeping only Cyrillic-bearing literals;
  2. finds the file's catalog section (the section key is the source's repo-relative
     path; matched as a suffix against every shard in config/translations/*.json);
  3. reports each wrapped RU string that has NO catalog key, or a key missing en/ua.

With --unwrapped it ALSO lists raw Cyrillic string literals that are NOT inside a
`_()`/`l()` (potential un-l10n'd leaks like a `buf << "<cyr>"` builder) -- review-only,
since admin/RU-by-policy sites legitimately stay raw.

Usage:
  lint-catalog-coverage.py <src.cpp> [<src2.cpp> ...] [--unwrapped] [--catalog-dir DIR]
Exit 1 if any wrapped string lacks a complete en+ua entry.
"""
import sys, os, re, json, glob

CYR = re.compile(r'[А-Яа-яЁёІіЇїЄєҐґ]')

def read(p):
    return strip_comments(open(p, encoding='utf-8', errors='replace').read())

def strip_comments(src):
    """Blank out // and /* */ comments (respecting string literals) so quoted text in
    comments isn't mistaken for a code literal. Offsets/newlines preserved for line #s."""
    out = []; i = 0; n = len(src)
    while i < n:
        c = src[i]
        if c == '"':                        # string literal -- copy verbatim
            out.append(c); i += 1
            while i < n:
                out.append(src[i])
                if src[i] == '\\' and i+1 < n:
                    out.append(src[i+1]); i += 2; continue
                if src[i] == '"': i += 1; break
                i += 1
            continue
        if c == '/' and i+1 < n and src[i+1] == '/':
            while i < n and src[i] != '\n': out.append(' '); i += 1
            continue
        if c == '/' and i+1 < n and src[i+1] == '*':
            while i < n and not (src[i] == '*' and i+1 < n and src[i+1] == '/'):
                out.append('\n' if src[i] == '\n' else ' '); i += 1
            out.append('  '); i += 2
            continue
        out.append(c); i += 1
    return ''.join(out)

def adjacent_literals(src, pos):
    """From just after a '(' or ',', collect consecutive "..."  literals -> joined str,
    plus the end offset. Returns (text, end) or (None, pos) if no literal there."""
    i = pos; parts = []; last = pos
    while i < len(src):
        while i < len(src) and src[i] in ' \t\r\n': i += 1
        if i < len(src) and src[i] == '"':
            j = i + 1; buf = []
            while j < len(src):
                if src[j] == '\\':
                    buf.append(src[j:j+2]); j += 2; continue
                if src[j] == '"': break
                buf.append(src[j]); j += 1
            parts.append(''.join(buf)); i = j + 1; last = i
        else:
            break
    return (''.join(parts), last) if parts else (None, pos)

def wrapped_keys(src):
    """RU keys inside _(...) and l(ch|pch, ...). Returns set of (raw) literals + list of
    (start,end) spans of every wrapped literal (for --unwrapped exclusion)."""
    keys = set(); spans = []
    for m in re.finditer(r'\b_\(', src):
        s, end = adjacent_literals(src, m.end())
        if s is not None:
            spans.append((m.end(), end))
            if CYR.search(s): keys.add(s)
    for m in re.finditer(r'\bl\(\s*p?ch\s*,', src):
        s, end = adjacent_literals(src, m.end())
        if s is not None:
            spans.append((m.end(), end))
            if CYR.search(s): keys.add(s)
    return keys, spans

def all_cyr_literals(src):
    """Every "..." literal containing Cyrillic, with its start offset (single literal,
    not concat-joined -- enough to flag an unwrapped leak site)."""
    out = []
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', src):
        if CYR.search(m.group(1)):
            out.append((m.start(), m.group(1)))
    return out

def unescape(s):
    """Decode C/C++ string escapes, incl. octal \\ooo and hex \\xHH -- combat damage
    frames embed \\5 / \\6 (byte 0x05/0x06, the verb-splice points) which the catalog
    stores as the raw byte, so the key won't match unless we decode them here."""
    out = []; i = 0; n = len(s)
    simple = {'n': '\n', 'r': '\r', 't': '\t', '"': '"', "'": "'", '\\': '\\', '0': '\0'}
    while i < n:
        c = s[i]
        if c != '\\' or i+1 >= n:
            out.append(c); i += 1; continue
        nxt = s[i+1]
        if nxt in '01234567':                    # octal \o, \oo, \ooo
            j = i+1; digs = ''
            while j < n and len(digs) < 3 and s[j] in '01234567':
                digs += s[j]; j += 1
            out.append(chr(int(digs, 8))); i = j
        elif nxt == 'x':                          # hex \xHH
            j = i+2; digs = ''
            while j < n and len(digs) < 2 and s[j] in '0123456789abcdefABCDEF':
                digs += s[j]; j += 1
            out.append(chr(int(digs, 16)) if digs else 'x'); i = j
        elif nxt in simple:
            out.append(simple[nxt]); i += 2
        else:
            out.append(nxt); i += 2
    return ''.join(out)

def load_catalog(catalog_dir):
    """Merge every shard into {section_key: {ru: entry}}."""
    sections = {}
    for f in sorted(glob.glob(os.path.join(catalog_dir, '*.json'))):
        try: data = json.load(open(f, encoding='utf-8'))
        except Exception as e:
            print(f"  ! bad catalog shard {f}: {e}", file=sys.stderr); continue
        for sec, entries in data.items():
            if isinstance(entries, dict):
                sections.setdefault(sec, {}).update(entries)
    return sections

def section_for(path, sections):
    """The catalog section whose key is the source's repo-relative path -- matched as a
    trailing path suffix so absolute or repo-relative inputs both resolve."""
    norm = path.replace('\\', '/')
    best = None
    for key in sections:
        if norm == key or norm.endswith('/' + key):
            if best is None or len(key) > len(best):
                best = key
    return best

def find_catalog_dir(explicit):
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(os.getcwd(), 'dreamland_world/config/translations'),
                 os.path.join(here, '..', 'config', 'translations'),
                 os.path.join(os.getcwd(), 'config/translations')):
        if os.path.isdir(cand):
            return cand
    return None

def ok(entry, lang):
    return isinstance(entry, dict) and bool((entry.get(lang) or '').strip())

def main():
    args = sys.argv[1:]
    show_unwrapped = '--unwrapped' in args
    args = [a for a in args if a != '--unwrapped']
    catalog_dir = None
    if '--catalog-dir' in args:
        i = args.index('--catalog-dir'); catalog_dir = args[i+1]; del args[i:i+2]
    files = args
    if not files:
        print(__doc__); return 2
    catalog_dir = find_catalog_dir(catalog_dir)
    if not catalog_dir:
        print("! could not locate config/translations (pass --catalog-dir)", file=sys.stderr)
        return 2
    sections = load_catalog(catalog_dir)

    total_missing = 0
    for path in files:
        src = read(path)
        sec_key = section_for(path, sections)
        sec = sections.get(sec_key, {})
        keys, spans = wrapped_keys(src)
        missing = []
        for s in sorted(keys):
            entry = sec.get(unescape(s)) or sec.get(s)
            if entry is None:
                missing.append(('NO-KEY', s))
            elif not (ok(entry, 'en') and ok(entry, 'ua')):
                missing.append((f"en={ok(entry,'en')} ua={ok(entry,'ua')}", s))
        tag = f"[section '{sec_key}']" if sec_key else "[NO catalog section matched]"
        print(f"{path} {tag}: {len(keys)} wrapped RU strings, {len(missing)} missing/incomplete")
        for why, s in missing:
            print(f"    {why}: {s[:80]!r}")
        total_missing += len(missing)

        if show_unwrapped:
            wrapped_starts = {}  # offset just after '(' -> covers literal
            # a literal is 'wrapped' if its start lies within a recorded span
            leaks = []
            for start, lit in all_cyr_literals(src):
                inside = any(a <= start < b for a, b in spans)
                if not inside:
                    line = src.count('\n', 0, start) + 1
                    leaks.append((line, lit))
            if leaks:
                print(f"    --unwrapped: {len(leaks)} raw Cyrillic literal(s) not in _()/l() (review):")
                for line, lit in leaks[:60]:
                    print(f"      {path}:{line}: {lit[:70]!r}")

    print(f"\nTOTAL missing/incomplete catalog entries: {total_missing}")
    return 1 if total_missing else 0

if __name__ == '__main__':
    sys.exit(main())
