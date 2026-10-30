#!/usr/bin/env python3
"""check_site: فحص سريع لمستودع ملفات أفق قبل النشر على GitHub Pages.

Usage: python3 tools/check_site.py [--root DIR] [--limit-gb 1] [--big-mb 10] [--only CHECKS]
                                   [--json] [--strict] [--soft-size]

Checks the files git would publish (tracked + new untracked, minus ignored):
  size      total against the Pages limit (1 GB), files bigger than --big-mb
  links     relative src/href in every .html points to an existing file
  q         q/<g>/<s>/index.html has a valid window.QZ (g/s match the path, lessons have
            a title and questions), every page uses the same engine version (?v=)
  scorm     scorm/<g>/<s>/L##.zip opens, imsmanifest.xml parses (SCORM 1.2, identifier
            afuq-<g>-<s>-L##), every file it names is in the zip, the zips are numbered
            L01..Ln with n = number of lessons in the matching q/ page, and L##
            opens lesson ## with the same questions as the q/ page (not stale)
  names     lower-case ASCII paths without spaces (safe URLs), no empty files,
            duplicate files (same content)
Exit code 1 when there is an error (and with --strict, a warning too). Standard library only.
"""
import argparse, collections, hashlib, io, json, os, re, subprocess, sys, zipfile
import xml.etree.ElementTree as ET

LINK_RE = re.compile(r'''(?:src|href)\s*=\s*["']([^"']+)["']''', re.I)
QZ_RE = re.compile(r'window\.QZ\s*=\s*(\{.*?\})\s*;?\s*</script>', re.S)
VER_RE = re.compile(r'engine\.(?:js|css)\?v=([0-9a-zA-Z]+)')
ZIP_RE = re.compile(r'^scorm/(\d+)/([a-z0-9]+)/L(\d+)\.zip$')
SAFE_RE = re.compile(r'^[A-Za-z0-9._/-]+$')
EXTERNAL = ('http:', 'https:', 'data:', 'mailto:', 'tel:', 'javascript:', 'blob:', '#', '//')
NS = {'cp': 'http://www.imsproject.org/xsd/imscp_rootv1p1p2'}


def publish_files(root):
    try:
        out = subprocess.run(['git', '-C', root, 'ls-files', '-z', '--cached', '--others',
                              '--exclude-standard'], capture_output=True, check=True).stdout
        names = set(n for n in out.decode('utf8').split('\0') if n)
    except Exception:
        names = set()
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if x != '.git']
            names |= {os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/') for f in fs}
    files = {}
    for n in names:
        p = os.path.join(root, n)
        if os.path.isfile(p):
            files[n] = os.path.getsize(p)
    return files


def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return ('%d %s' % (n, u)) if u == 'B' else ('%.*f %s' % (2 if u == 'GB' else 1, n, u))
        n /= 1024.0


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, check, msg, path=''):
        self.items.append({'level': level, 'check': check, 'msg': msg, 'path': path})

    def count(self, level):
        return sum(1 for i in self.items if i['level'] == level)


def check_size(files, rep, limit, big, soft=False):
    total = sum(files.values())
    pct = 100.0 * total / limit if limit else 0
    msg = 'الحجم الكلي %s (%.0f%% من حد %s)' % (human(total), pct, human(limit))
    rep.add('error' if pct > 100 and not soft else 'warn' if pct > 90 else 'info', 'size', msg)
    for n, s in sorted(files.items(), key=lambda x: -x[1]):
        if s < big:
            break
        rep.add('warn', 'size', 'ملف كبير %s' % human(s), n)
    return total


def check_links(root, files, rep):
    dirs = {os.path.dirname(n) for n in files}
    for n in sorted(f for f in files if f.endswith('.html')):
        with open(os.path.join(root, n), encoding='utf8', errors='replace') as fh:
            text = fh.read()
        for url in sorted(set(LINK_RE.findall(text))):
            u = url.strip()
            if not u or u.lower().startswith(EXTERNAL) or '${' in u or '{{' in u or "'+" in u:
                continue
            if u.startswith('/'):
                continue  # root of afuq-edu.github.io (the main site repo), not this one
            u = re.split(r'[?#]', u)[0]
            if not u:
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(n), u)).replace(os.sep, '/')
            if target in files or (target in dirs and target + '/index.html' in files):
                continue
            rep.add('error', 'links', 'رابط مكسور: %s' % url, n)


def load_qz(root, files, rep):
    lessons, versions = {}, collections.defaultdict(list)
    for n in sorted(files):
        m = re.match(r'^q/(\d+)/([a-z0-9]+)/index\.html$', n)
        if not m:
            continue
        g, s = m.groups()
        with open(os.path.join(root, n), encoding='utf8', errors='replace') as fh:
            text = fh.read()
        for v in set(VER_RE.findall(text)):
            versions[v].append(n)
        qm = QZ_RE.search(text)
        if not qm:
            rep.add('error', 'q', 'لا يوجد window.QZ', n)
            continue
        try:
            d = json.loads(qm.group(1))
        except ValueError as e:
            rep.add('error', 'q', 'window.QZ ليس JSON صالحًا: %s' % e, n)
            continue
        if str(d.get('g')) != g or d.get('s') != s:
            rep.add('error', 'q', 'g/s في QZ (%s/%s) لا يطابقان المسار' % (d.get('g'), d.get('s')), n)
        L = d.get('L') or []
        if not L:
            rep.add('error', 'q', 'لا توجد دروس في QZ.L', n)
        for i, l in enumerate(L, 1):
            if not l.get('t'):
                rep.add('error', 'q', 'الدرس %d بلا عنوان' % i, n)
            if not l.get('q'):
                rep.add('warn', 'q', 'الدرس %d بلا أسئلة' % i, n)
        lessons[(g, s)] = L
    if len(versions) > 1:
        top = max(versions, key=lambda v: len(versions[v]))
        for v, pages in versions.items():
            if v != top:
                for p in pages:
                    rep.add('warn', 'q', 'نسخة المحرك ?v=%s تختلف عن أغلب الصفحات (%s)' % (v, top), p)
    for f in ('q/engine.js', 'q/engine.css'):
        if lessons and f not in files:
            rep.add('error', 'q', '%s غير موجود وصفحات الألعاب تعتمد عليه' % f)
    return lessons


def check_scorm(root, files, rep, lessons):
    packs = collections.defaultdict(list)
    for n in sorted(files):
        if not n.startswith('scorm/'):
            continue
        m = ZIP_RE.match(n)
        if not m:
            rep.add('warn', 'scorm', 'اسم غير متوقع في scorm/ (المتوقع scorm/<صف>/<مادة>/L01.zip)', n)
            continue
        g, s, num = m.groups()
        packs[(g, s)].append(int(num))
        ident = 'afuq-%s-%s-L%s' % (g, s, num)
        try:
            z = zipfile.ZipFile(os.path.join(root, n))
            names = set(z.namelist())
            bad = z.testzip()
            if bad:
                rep.add('error', 'scorm', 'ملف تالف داخل الحزمة: %s' % bad, n)
            if 'imsmanifest.xml' not in names:
                rep.add('error', 'scorm', 'لا يوجد imsmanifest.xml في جذر الحزمة', n)
                continue
            man = ET.fromstring(z.read('imsmanifest.xml'))
        except (zipfile.BadZipFile, ET.ParseError, OSError) as e:
            rep.add('error', 'scorm', 'الحزمة لا تُقرأ: %s' % e, n)
            continue
        if man.get('identifier') != ident:
            rep.add('warn', 'scorm', 'identifier هو %s والمتوقع %s' % (man.get('identifier'), ident), n)
        ver = man.findtext('cp:metadata/cp:schemaversion', namespaces=NS)
        if ver != '1.2':
            rep.add('warn', 'scorm', 'schemaversion هو %s والمتوقع 1.2' % ver, n)
        res = man.findall('cp:resources/cp:resource', NS)
        if not res:
            rep.add('error', 'scorm', 'لا توجد resource في imsmanifest.xml', n)
        for r in res:
            refs = [r.get('href')] + [f.get('href') for f in r.findall('cp:file', NS)]
            for h in refs:
                if h and h not in names:
                    rep.add('error', 'scorm', 'imsmanifest.xml يذكر %s وهو غير موجود في الحزمة' % h, n)
        L = lessons.get((g, s))
        if L and 'index.html' in names and int(num) <= len(L):
            qm = QZ_RE.search(z.read('index.html').decode('utf8', 'replace'))
            try:
                d = json.loads(qm.group(1)) if qm else {}
            except ValueError:
                d = {}
            li, PL = int(d.get('l') or 0), d.get('L') or []
            if li != int(num) or li > len(PL):
                rep.add('error', 'scorm', 'الحزمة تفتح الدرس %s بدل %d (QZ.l)' % (d.get('l'), int(num)), n)
            elif PL[li - 1].get('q') != L[li - 1].get('q') or PL[li - 1].get('t') != L[li - 1].get('t'):
                rep.add('warn', 'scorm', 'أسئلة الحزمة تختلف عن q/%s/%s الدرس %d (أعد توليد الحزمة)' % (g, s, li), n)
    for (g, s), nums in sorted(packs.items()):
        nums.sort()
        where = 'scorm/%s/%s/' % (g, s)
        if nums != list(range(1, len(nums) + 1)):
            missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
            rep.add('error', 'scorm', 'ترقيم الحزم غير متصل، الناقص: %s' % ', '.join('L%02d' % i for i in missing), where)
        if (g, s) in lessons and len(lessons[(g, s)]) != len(nums):
            rep.add('warn', 'scorm', 'عدد الحزم %d وعدد دروس q/%s/%s هو %d' % (len(nums), g, s, len(lessons[(g, s)])), where)
        if (g, s) not in lessons:
            rep.add('warn', 'scorm', 'حزم SCORM بلا صفحة ألعاب q/%s/%s/' % (g, s), where)
    for (g, s) in sorted(lessons):
        if (g, s) not in packs:
            rep.add('warn', 'scorm', 'صفحة ألعاب بلا حزم SCORM في scorm/%s/%s/' % (g, s), 'q/%s/%s/' % (g, s))


def check_names(root, files, rep):
    for n in sorted(files):
        if n.startswith('.') or n.startswith(('tools/', '.claude/', '.github/')) or n in ('README.md', 'CLAUDE.md'):
            continue
        if not SAFE_RE.match(n):
            rep.add('warn', 'names', 'اسم غير آمن للروابط (استعمل حروفًا إنجليزية وأرقامًا و - فقط، بلا مسافات)', n)
        if files[n] == 0:
            rep.add('warn', 'names', 'ملف فارغ', n)
    by_size = collections.defaultdict(list)
    for n, s in files.items():
        if s > 0:
            by_size[s].append(n)
    for s, group in by_size.items():
        if len(group) < 2:
            continue
        by_hash = collections.defaultdict(list)
        for n in group:
            h = hashlib.sha1()
            with open(os.path.join(root, n), 'rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b''):
                    h.update(chunk)
            by_hash[h.hexdigest()].append(n)
        for same in by_hash.values():
            if len(same) > 1:
                same.sort()
                rep.add('info', 'names', 'ملفات متطابقة (%s لكل نسخة): %s' % (human(s), ', '.join(same[1:])), same[0])


LABEL = {'error': 'خطأ', 'warn': 'تنبيه', 'info': 'معلومة'}
TITLE = {'size': 'الحجم', 'links': 'الروابط', 'q': 'صفحات الألعاب q/', 'scorm': 'حزم SCORM', 'names': 'الأسماء والتكرار'}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default='.')
    ap.add_argument('--limit-gb', type=float, default=1.0)
    ap.add_argument('--big-mb', type=float, default=10.0)
    ap.add_argument('--only', help='comma list of checks: size,links,q,scorm,names')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    ap.add_argument('--strict', action='store_true', help='fail on warnings too')
    ap.add_argument('--soft-size', action='store_true', help='going over the size limit is a warning, not an error')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    only = set(a.only.split(',')) if a.only else set(TITLE)
    files = publish_files(root)
    rep = Report()
    if 'size' in only:
        check_size(files, rep, int(a.limit_gb * 1024 ** 3), int(a.big_mb * 1024 ** 2), a.soft_size)
    if 'links' in only:
        check_links(root, files, rep)
    lessons = load_qz(root, files, rep) if only & {'q', 'scorm'} else {}
    if 'scorm' in only:
        check_scorm(root, files, rep, lessons)
    if 'names' in only:
        check_names(root, files, rep)
    rep.items = [i for i in rep.items if i['check'] in only]
    errors, warns = rep.count('error'), rep.count('warn')
    if a.json:
        json.dump({'files': len(files), 'errors': errors, 'warnings': warns, 'items': rep.items},
                  sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print('فحص %d ملفًا: %d خطأ، %d تنبيه' % (len(files), errors, warns))
        for check in TITLE:
            items = [i for i in rep.items if i['check'] == check]
            if check not in only:
                continue
            print('\n## %s%s' % (TITLE[check], '' if items else ': سليم'))
            shown = collections.Counter()
            for i in sorted(items, key=lambda i: ('error', 'warn', 'info').index(i['level'])):
                shown[i['level']] += 1
                if shown[i['level']] > 30:
                    continue
                print('- [%s] %s%s' % (LABEL[i['level']], i['msg'], ('  ← ' + i['path']) if i['path'] else ''))
            for lvl, c in shown.items():
                if c > 30:
                    print('- … و %d %s أخرى (استعمل --json للقائمة كاملة)' % (c - 30, LABEL[lvl]))
    sys.exit(1 if errors or (a.strict and warns) else 0)


if __name__ == '__main__':
    main()
