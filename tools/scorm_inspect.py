#!/usr/bin/env python3
"""scorm_inspect: عرض محتوى حزم SCORM لمنصة نور ومقارنتها بصفحة ألعاب الدرس في q/.

Usage: python3 tools/scorm_inspect.py PATH [PATH ...] [--extract DIR] [--root DIR]

PATH is scorm/<g>/<s>/L##.zip or a folder of them (scorm/<g>/<s>/).
For each package it prints: the manifest title, identifier, SCORM version, mastery score,
the files with their sizes, the lesson the package opens (window.QZ.L[l-1]: title and number
of questions), the SCORM 1.2 calls the page makes (LMSInitialize, cmi.core.*), and whether the
lesson matches lesson N of q/<g>/<s>/index.html. --extract DIR unpacks each package into
DIR/<g>-<s>-L##/ to open index.html in a browser. Standard library only.
"""
import argparse, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

NS = {'cp': 'http://www.imsproject.org/xsd/imscp_rootv1p1p2', 'adlcp': 'http://www.adlnet.org/xsd/adlcp_rootv1p2'}
QZ_RE = re.compile(r'window\.QZ\s*=\s*(\{.*?\})\s*;?\s*</script>', re.S)
ZIP_RE = re.compile(r'scorm/(\d+)/([a-z0-9]+)/L(\d+)\.zip$')


def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return ('%d %s' % (n, u)) if u == 'B' else ('%.1f %s' % (n, u))
        n /= 1024.0


def qz_of(text):
    m = QZ_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


_q_cache = {}


def q_page(root, g, s):
    key = (g, s)
    if key not in _q_cache:
        p = os.path.join(root, 'q', g, s, 'index.html')
        _q_cache[key] = qz_of(open(p, encoding='utf8').read()) if os.path.isfile(p) else None
    return _q_cache[key]


def inspect(path, root, extract):
    print('\n## %s  (%s)' % (path, human(os.path.getsize(path))))
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        print('- خطأ: ليست حزمة zip صالحة (%s)' % e)
        return False
    ok = True
    names = z.namelist()
    if 'imsmanifest.xml' in names:
        man = ET.fromstring(z.read('imsmanifest.xml'))
        print('- العنوان: %s' % (man.findtext('cp:organizations/cp:organization/cp:title', namespaces=NS) or '—'))
        print('- identifier: %s · SCORM %s · درجة الإتقان %s' % (
            man.get('identifier'), man.findtext('cp:metadata/cp:schemaversion', namespaces=NS),
            man.findtext('.//adlcp:masteryscore', namespaces=NS) or '—'))
        for r in man.findall('cp:resources/cp:resource', NS):
            refs = [r.get('href')] + [f.get('href') for f in r.findall('cp:file', NS)]
            missing = [h for h in refs if h and h not in names]
            if missing:
                ok = False
                print('- خطأ: الـ manifest يذكر ملفات غير موجودة: %s' % ', '.join(missing))
    else:
        ok = False
        print('- خطأ: لا يوجد imsmanifest.xml')
    print('- الملفات:')
    for i in z.infolist():
        print('    %-32s %s' % (i.filename, human(i.file_size)))
    if 'index.html' in names:
        html = z.read('index.html').decode('utf8', 'replace')
        calls = sorted(set(re.findall(r'LMS[A-Z][A-Za-z]+|cmi\.[a-z_.]+[a-z]', html)))
        print('- استدعاءات SCORM: %s' % (', '.join(calls) or 'لا شيء (لن تُسجَّل الدرجة في نور)'))
        d = qz_of(html)
        lessons = (d or {}).get('L') or []
        li = int((d or {}).get('l') or 1)  # the package opens lesson l of the subject's lessons
        if 0 < li <= len(lessons):
            l = lessons[li - 1]
            print('- الدرس %d من %d: %s · %d سؤال%s' % (li, len(lessons), l.get('t'), len(l.get('q') or []), (' · ' + l['u']) if l.get('u') else ''))
        m = ZIP_RE.search(path.replace(os.sep, '/'))
        page = q_page(root, m.group(1), m.group(2)) if m else None
        if m and page:
            n = int(m.group(3))
            L = page.get('L') or []
            if n > len(L):
                ok = False
                print('- خطأ: صفحة q/%s/%s فيها %d درسًا فقط ولا يوجد الدرس %d' % (m.group(1), m.group(2), len(L), n))
            elif 0 < li <= len(lessons):
                if li != n:
                    ok = False
                    print('- خطأ: الحزمة L%02d تفتح الدرس %d (QZ.l)' % (n, li))
                same_t = L[n - 1].get('t') == lessons[li - 1].get('t')
                same_q = L[n - 1].get('q') == lessons[li - 1].get('q')
                print('- مقارنة بـ q/%s/%s الدرس %d: العنوان %s، الأسئلة %s' % (
                    m.group(1), m.group(2), n, 'مطابق' if same_t else 'مختلف (%s)' % L[n - 1].get('t'),
                    'مطابقة' if same_q else 'مختلفة (الحزمة قديمة؟ أعد توليدها)'))
    if extract:
        m = ZIP_RE.search(path.replace(os.sep, '/'))
        dest = os.path.join(extract, '%s-%s-L%s' % m.groups() if m else os.path.basename(path)[:-4])
        z.extractall(dest)
        print('- فُكّت في %s' % dest)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--root', default='.', help='repo root (to find q/)')
    ap.add_argument('--extract', metavar='DIR')
    a = ap.parse_args()
    zips = []
    for p in a.paths:
        if os.path.isdir(p):
            zips += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith('.zip'))
        else:
            zips.append(p)
    if not zips:
        sys.exit('لا توجد حزم zip في: %s' % ' '.join(a.paths))
    bad = [z for z in zips if not inspect(z, a.root, a.extract)]
    print('\n%d حزمة، %d فيها خطأ' % (len(zips), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
