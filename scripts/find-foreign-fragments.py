#!/usr/bin/env python3
"""Find translation defects in Cyrillic (RU/UA) text:
  (a) LATIN leaks -- runs of >=3 Latin letters standing as a word inside
      Cyrillic prose (untranslated English/Spanish/German fragments).
  (b) MIXED homoglyphs -- a single Latin letter hiding inside a Cyrillic word
      (breaks KOI-8 render + keyword search): раcу, tёмно, изумрудa.

Strips Dreamland markup before checking so it works on catalog-format data too:
  color codes {x {G {1 {2 ; help anchors {hh<vnum> ; command/help links
  {hc...{x and {hh...{x link BODIES (EN command names there are intentional) ;
  printf specs %s %d %N$C etc. Use --keep-links to also flag link bodies.

Scans JSON (recurses; target keys 'ru'/'ua', or any Cyrillic string not under 'en')
and XML (<... l="ru|ua">text). Usage:
  find-foreign-fragments.py [--keep-links] [path ...]
  default paths: descriptions + config/translations + socials
"""
import sys, os, re, json, glob
import xml.etree.ElementTree as ET

LATIN_WORD = re.compile(r'(?<![A-Za-z])[A-Za-z]{3,}(?![A-Za-z])')
CYR = re.compile(r'[А-Яа-яЁёІіЇїЄєҐґ]')
LAT = re.compile(r'[A-Za-z]')

def strip_markup(t, keep_links):
    if not keep_links:
        # {hcTEXT{x  and  {hh<vnum>TEXT{x  -> drop the link body entirely
        t = re.sub(r'\{hc.*?\{x', ' ', t)
        t = re.sub(r'\{hh\d*.*?\{x', ' ', t)
    t = re.sub(r'\{hh\d+', ' ', t)          # bare anchor prefix
    t = re.sub(r'\{.', ' ', t)              # color / push{1 / pop{2 / {x
    t = re.sub(r'%\d*\$?[-#0-9.]*[A-Za-z]', ' ', t)  # printf incl numbered %N$C
    t = re.sub(r'%[A-Za-z]', ' ', t)
    t = re.sub(r'\$\d*[A-Za-z]\d?', ' ', t)  # Fenia/act codes $g $C1 $o2
    return t

def check(text, where, out, keep_links):
    if not text or not CYR.search(text): return
    t = strip_markup(text, keep_links)
    for m in LATIN_WORD.finditer(t):
        i = m.start()
        out.append((where, 'LATIN', m.group(0), t[max(0,i-20):m.end()+20]))
    for tok in re.findall(r'\S+', t):
        if LAT.search(tok) and CYR.search(tok):
            out.append((where, 'MIXED', tok, tok))

def scan_json(f, out, keep_links):
    try: data = json.load(open(f, encoding='utf-8'))
    except Exception as e: out.append((f,'BADJSON',str(e),'')); return
    def walk(d, path):
        if isinstance(d, dict):
            for k,v in d.items(): walk(v, path+'/'+k)
        elif isinstance(d, list):
            for i,v in enumerate(d): walk(v, f"{path}[{i}]")
        elif isinstance(d, str):
            lang = path.rsplit('/',1)[-1]
            if lang in ('ru','ua') or (lang!='en' and CYR.search(d)):
                check(d, f"{f}:{path}", out, keep_links)
    walk(data,'')

def scan_xml(f, out, keep_links):
    try: root = ET.parse(f).getroot()
    except Exception as e: out.append((f,'BADXML',str(e),'')); return
    for el in root.iter():
        if el.get('l') in ('ru','ua') and el.text:
            check(el.text, f"{f}:<{el.tag} l={el.get('l')}>", out, keep_links)

def main():
    args = sys.argv[1:]
    keep_links = '--keep-links' in args
    args = [a for a in args if a != '--keep-links']
    if not args:
        args = (glob.glob('descriptions/*.json')
                + glob.glob('config/translations/*.json')
                + glob.glob('socials/*.xml'))
    out=[]
    for a in args:
        targets = [a] if os.path.isfile(a) else glob.glob(os.path.join(a,'**','*.*'), recursive=True)
        for f in targets:
            if f.endswith('.json'): scan_json(f, out, keep_links)
            elif f.endswith('.xml'): scan_xml(f, out, keep_links)
    for where,kind,tok,ctx in out[:200]:
        print(f"[{kind:6}] {where}\n         '{tok}'  …{ctx}…")
    n=lambda k:sum(1 for o in out if o[1]==k)
    print(f"\nLATIN leaks: {n('LATIN')} | MIXED homoglyphs: {n('MIXED')} | parse errors: {n('BADJSON')+n('BADXML')}")
    return 1 if out else 0

if __name__=='__main__':
    sys.exit(main())
