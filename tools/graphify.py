#!/usr/bin/env python3
"""graphify: خريطة مرئية لمستودع ملفات أفق في صفحة HTML واحدة مستقلة (RTL، فاتح/داكن، هاتف).

Usage: python3 tools/graphify.py OUT.html [--root DIR] [--limit-gb 1]

Reads the files tracked by git (what GitHub Pages publishes; falls back to a plain walk),
takes grade and subject names from the lesson-games pages (q/<g>/<s>/index.html, window.QZ)
and builds: key numbers, folder sizes against the Pages limit (1 GB), the coverage of each
grade/subject by section, the project tree (<details>), scripts, file types and notes.
Standard library only.
"""
import argparse, collections, hashlib, html, json, os, re, subprocess, sys, time

# What each folder name means in this repo (sections of a subject, and the top-level parts).
SECTIONS = collections.OrderedDict([
    ('board', 'السبورات'),
    ('recap', 'ملخصات بالصور'),
    ('summaries', 'ملخصات وخرائط ذهنية'),
    ('view', 'العرض التفاعلي'),
    ('games', 'الألعاب'),
])
SUBSECTIONS = {'interactive': 'تفاعلي', 'slides': 'شرائح', 'lessons': 'دروس'}
TOP = {'q': 'ألعاب ونشاط الدرس', 'scorm': 'حزم SCORM لنور'}
GRADE_FALLBACK = ['', 'الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع',
                  'الثامن', 'التاسع', 'العاشر', 'الحادي عشر', 'الثاني عشر']
SUBJECT_FALLBACK = {'math': 'الرياضيات', 'science': 'العلوم', 'arabic': 'اللغة العربية',
                    'english': 'اللغة الإنجليزية', 'islamic': 'التربية الإسلامية',
                    'social': 'الدراسات الاجتماعية', 'it': 'تقنية المعلومات', 'pe': 'الرياضة',
                    'arts': 'الفنون', 'sport': 'الرياضة', 'physics': 'الفيزياء',
                    'chemistry': 'الكيمياء', 'biology': 'الأحياء', 'envsci': 'العلوم البيئية',
                    'homeland': 'الوطنية', 'advmath': 'الرياضيات المتقدمة',
                    'basicmath': 'الرياضيات الأساسية'}
SCRIPT_EXT = {'.py', '.js', '.mjs', '.sh', '.ps1', '.rb'}
BIG_FILE = 10 * 1024 * 1024
TREE_FILES = 25  # files listed per folder before "و N أخرى"


def tracked_files(root):
    try:
        out = subprocess.run(['git', '-C', root, 'ls-files', '-z'], capture_output=True, check=True).stdout
        names = [n for n in out.decode('utf8').split('\0') if n]
    except Exception:
        names = []
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if x != '.git']
            names += [os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/') for f in fs]
    files = []
    for n in sorted(names):
        p = os.path.join(root, n)
        if os.path.isfile(p):
            files.append((n, os.path.getsize(p)))
    return files


def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return ('%d %s' % (n, u)) if u == 'B' else ('%.*f %s' % (2 if u == 'GB' else 1, n, u))
        n /= 1024.0


def hs(n):
    return '<span class="sz" dir="ltr">%s</span>' % human(n)


def ar(n):
    return str(n).replace(',', '٬').translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def num(n):
    return ar('{:,}'.format(n))


def ext_of(name):
    b = name.rsplit('/', 1)[-1]
    return b.rsplit('.', 1)[-1].lower() if '.' in b.strip('.') else '(بلا امتداد)'


def read_names(root, files):
    """Grade and subject names, and lessons per grade/subject, from q/<g>/<s>/index.html."""
    grades, subjects, lessons = {}, {}, {}
    for n, _ in files:
        m = re.match(r'q/(\d+)/([^/]+)/index\.html$', n)
        if not m:
            continue
        try:
            t = open(os.path.join(root, n), encoding='utf8').read()
            d, _ = json.JSONDecoder().raw_decode(t, t.index('window.QZ=') + 10)
        except Exception:
            continue
        grades[m.group(1)] = d.get('gn') or grades.get(m.group(1))
        subjects[(m.group(1), m.group(2))] = d.get('sn')
        lessons[(m.group(1), m.group(2))] = len(d.get('L') or [])
    return grades, subjects, lessons


def first_doc_line(path):
    try:
        t = open(path, encoding='utf8', errors='replace').read(4000)
    except Exception:
        return ''
    t = re.sub(r'^#!.*\n', '', t)
    m = (re.match(r'\s*(?:[rRuU]?("""|\'\'\'))\s*(.*?)\s*(?:\1|\n)', t, re.S)
         or re.match(r'\s*/\*+\s*(.*?)\s*(?:\*/|\n)', t, re.S)
         or re.match(r'\s*(?://|#)\s*(.*)', t))
    return (m.group(m.lastindex) if m else '').strip()


class Node:
    def __init__(self, name):
        self.name, self.kids, self.files, self.size, self.count = name, {}, [], 0, 0


def build_tree(files):
    root = Node('')
    for n, s in files:
        parts = n.split('/')
        node = root
        node.size += s; node.count += 1
        for p in parts[:-1]:
            node = node.kids.setdefault(p, Node(p))
            node.size += s; node.count += 1
        node.files.append((parts[-1], s))
    return root


def folder_count(node):
    return len(node.kids) + sum(folder_count(k) for k in node.kids.values())


def grade_key(x):
    return (0, int(x)) if x.isdigit() else (1, x)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out')
    ap.add_argument('--root', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--limit-gb', type=float, default=1.0, help='GitHub Pages limit (0 = none)')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    limit = int(a.limit_gb * 1024 ** 3)

    files = tracked_files(root)
    total = sum(s for _, s in files)
    tree = build_tree(files)
    gnames, snames, lessons = read_names(root, files)
    gname = lambda g: gnames.get(g) or (GRADE_FALLBACK[int(g)] if g.isdigit() and int(g) < len(GRADE_FALLBACK) else g)
    sname = lambda s, g=None: snames.get((g, s)) or SUBJECT_FALLBACK.get(s) or s
    grades = sorted([k for k in tree.kids if k.isdigit()], key=int)

    # ---- coverage: grade -> subject -> {section: (files, size)}
    cov = collections.defaultdict(lambda: collections.defaultdict(dict))
    cols = list(SECTIONS) + ['q', 'scorm']
    for g in grades:
        for s, sn in tree.kids[g].kids.items():
            for sec, node in sn.kids.items():
                cov[g][s][sec] = (node.count, node.size)
    for top in ('q', 'scorm'):
        for g, gn in tree.kids.get(top, Node('')).kids.items():
            for s, sn in gn.kids.items():
                cov[g][s][top] = (sn.count, sn.size)
    for g in cov:
        for s in cov[g]:
            for sec in cov[g][s]:
                if sec not in cols:
                    cols.append(sec)

    # ---- key numbers
    cnt = collections.Counter()
    for n, _ in files:
        p = n.split('/')
        if p[0].isdigit() and len(p) >= 4:
            sec = p[2]
            if sec == 'summaries' and n.endswith('-s.pdf'):
                cnt['summaries'] += 1
            elif sec in ('view', 'games') and p[-1] == 'index.html':
                cnt[sec] += 1
            elif sec in ('board', 'recap') and n.endswith('.pdf'):
                cnt[sec] += 1
        elif p[0] == 'scorm' and n.endswith('.zip'):
            cnt['scorm'] += 1
        elif p[0] == 'q' and p[-1] == 'index.html':
            cnt['q'] += 1
    pairs = {(g, s) for g in cov for s in cov[g]}
    cards = [
        ('الملفات', num(len(files)), ''),
        ('المجلدات', num(folder_count(tree)), ''),
        ('الحجم الكلي', hs(total), ('%s من حد %s' % (ar('%d٪' % round(100.0 * total / limit)), hs(limit))) if limit else ''),
        ('الصفوف', num(len(grades)), ''),
        ('مواد الصفوف', num(len(pairs)), 'صف × مادة'),
        ('دروس الألعاب', num(sum(lessons.values())), 'من صفحات q/'),
        ('ملفات السبورات', num(cnt['board']), 'PDF'),
        ('ملخصات بالصور', num(cnt['recap']), 'PDF'),
        ('ملخصات دروس', num(cnt['summaries']), 'ملخص + خريطة ذهنية'),
        ('عروض تفاعلية', num(cnt['view']), 'صفحة'),
        ('صفحات ألعاب', num(cnt['games'] + cnt['q']), '%s في المواد + %s في q/' % (num(cnt['games']), num(cnt['q']))),
        ('حزم SCORM', num(cnt['scorm']), 'ZIP'),
    ]

    # ---- notes
    notes = []
    if limit:
        pct = 100.0 * total / limit
        if pct >= 90:
            notes.append(('bad', 'الحجم الكلي %s أي %s من حد GitHub Pages (%s)%s.' % (
                hs(total), ar('%d٪' % round(pct)), hs(limit),
                '، تجاوز الحد بـ %s' % hs(total - limit) if total > limit else '')))
        elif pct >= 70:
            notes.append(('warn', 'الحجم الكلي %s من الحد.' % ar('%d٪' % round(pct))))
    big = sorted([(s, n) for n, s in files if s >= BIG_FILE], reverse=True)
    if big:
        notes.append(('warn', 'ملفات أكبر من %s: %s' % (hs(BIG_FILE), '، '.join(
            '<span dir="ltr">%s</span> (%s)' % (html.escape(n), hs(s)) for s, n in big))))
    bysize = collections.defaultdict(list)
    for n, s in files:
        if s > 0:
            bysize[s].append(n)
    dups, waste = [], 0
    for s, ns in bysize.items():
        if len(ns) < 2:
            continue
        byhash = collections.defaultdict(list)
        for n in ns:
            h = hashlib.sha1()
            with open(os.path.join(root, n), 'rb') as f:
                for b in iter(lambda: f.read(1 << 20), b''):
                    h.update(b)
            byhash[h.hexdigest()].append(n)
        for g in byhash.values():
            if len(g) > 1:
                dups.append((s, g)); waste += s * (len(g) - 1)
    if dups:
        dups.sort(reverse=True)
        notes.append(('warn', '%s مجموعة ملفات مكررة بالمحتوى (هدر %s). أكبرها: %s' % (
            num(len(dups)), hs(waste), '؛ '.join(
                '<span dir="ltr">%s</span>' % html.escape(' = '.join(g)) for s, g in dups[:5]))))
    # sections a subject lacks while most subjects of its grade have them, and q/scorm mismatches;
    # one line per (gap, subject) listing the grades
    gaps = collections.OrderedDict()
    for g in grades:
        subs = [s for s in cov[g] if s in tree.kids[g].kids]
        for sec in SECTIONS:
            have = [s for s in subs if sec in cov[g][s]]
            for s in subs:
                if sec not in cov[g][s] and len(have) > len(subs) / 2:
                    gaps.setdefault(('«%s» ناقص' % SECTIONS[sec], s), []).append(g)
    for g in sorted(cov, key=grade_key):
        for s in cov[g]:
            if 'q' in cov[g][s] and 'scorm' not in cov[g][s]:
                gaps.setdefault(('ألعاب q/ بلا حزمة SCORM', s), []).append(g)
            if 'scorm' in cov[g][s] and 'q' not in cov[g][s]:
                gaps.setdefault(('حزمة SCORM بلا ألعاب q/', s), []).append(g)
            L, z = lessons.get((g, s)), cov[g][s].get('scorm', (0, 0))[0]
            if L and z and L != z:
                notes.append(('info', 'الصف %s، %s: %s درسًا في q/ و%s حزمة SCORM.' % (gname(g), sname(s, g), num(L), num(z))))
    for (what, s), gs in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
        notes.append(('info', '%s في %s: %s %s.' % (what, sname(s, gs[0]), 'الصف' if len(gs) == 1 else 'الصفوف',
                                                   '، '.join(ar(g) for g in gs))))
    odd = [n for n, _ in files if re.search(r'[A-Z\s]', n.rsplit('/', 1)[-1]) and n not in ('README.md',)
           and not re.match(r'scorm/.+/L\d+\.zip$', n)]
    if odd:
        notes.append(('info', 'أسماء فيها مسافات أو أحرف كبيرة: %s' % '، '.join(
            '<span dir="ltr">%s</span>' % html.escape(n) for n in odd[:15])))
    loose = [n for n, _ in files if n.split('/')[0].isdigit() and n.count('/') < 3]
    if loose:
        notes.append(('info', 'ملفات خارج أقسام المواد: %s' % '، '.join(
            '<span dir="ltr">%s</span>' % html.escape(n) for n in loose[:15])))
    empty = [n for n, s in files if s == 0 and not n.endswith('.nojekyll')]
    if empty:
        notes.append(('info', 'ملفات فارغة: %s' % '، '.join('<span dir="ltr">%s</span>' % html.escape(n) for n in empty[:15])))
    if not notes:
        notes.append(('ok', 'لا ملاحظات.'))

    # ---- HTML pieces
    e = html.escape
    lvl = lambda p: 'bad' if p > 90 else 'warn' if p >= 70 else 'ok'

    def bar(size, base):
        p = 100.0 * size / base if base else 0
        return '<div class="bar"><i class="%s" style="width:%.2f%%"></i></div><b class="pct %s">%s</b>' % (
            lvl(p), min(p, 100), lvl(p), ar('%.1f٪' % p))

    base = limit or total
    folders = sorted(tree.kids.values(), key=lambda k: -k.size)
    def flabel(k):
        if k.name.isdigit(): return 'الصف %s' % gname(k.name)
        return TOP.get(k.name, '')
    rows_folders = ''.join(
        '<div class="frow"><div class="fname"><span dir="ltr" class="path">%s/</span> <small>%s</small></div>'
        '<div class="fbar">%s</div><div class="fsize">%s<small> · %s ملف</small></div></div>' % (
            e(k.name), e(flabel(k)), bar(k.size, base), hs(k.size), num(k.count)) for k in folders)
    loose_root = [(n, s) for n, s in tree.files]

    def label(path, name):
        p = path.split('/')
        if len(p) == 1:
            return flabel(Node(name)) if (name.isdigit() or name in TOP) else ''
        if p[0].isdigit():
            if len(p) == 2: return sname(name, p[0])
            if len(p) == 3: return SECTIONS.get(name, '')
            if len(p) == 4: return SUBSECTIONS.get(name, '')
        if p[0] in TOP:
            if len(p) == 2: return 'الصف ' + gname(name)
            if len(p) == 3:
                L = lessons.get((p[1], name))
                return sname(name, p[1]) + (' · %s درسًا' % num(L) if L else '')
        return ''

    def tree_html(node, path, depth):
        out = []
        key = (lambda k: grade_key(k.name)) if depth == 0 or (depth == 1 and path.split('/')[0] in TOP) else (lambda k: k.name)
        for k in sorted(node.kids.values(), key=key):
            p = (path + '/' if path else '') + k.name
            lb = label(p, k.name)
            out.append('<details%s><summary><span dir="ltr" class="path">%s/</span>%s'
                       '<span class="meta">%s عنصر · %s</span></summary><div class="kids">%s</div></details>' % (
                           '', e(k.name), (' <span class="lb">%s</span>' % e(lb)) if lb else '',
                           num(k.count), hs(k.size), tree_html(k, p, depth + 1)))
        fs = sorted(node.files)
        if fs:
            shown = fs[:TREE_FILES]
            out.append('<ul class="files">%s%s</ul>' % (''.join(
                '<li><span dir="ltr" class="path">%s</span><span class="meta">%s</span></li>' % (e(n), hs(s)) for n, s in shown),
                ('<li class="more">و%s ملفات أخرى</li>' % num(len(fs) - len(shown))) if len(fs) > len(shown) else ''))
        return ''.join(out)

    # coverage table
    head = ''.join('<th>%s</th>' % e(SECTIONS.get(c) or TOP.get(c) or c) for c in cols)
    body = []
    for g in sorted(cov, key=grade_key):
        body.append('<tr class="grp"><th colspan="%d">الصف %s <span dir="ltr">(%s)</span></th></tr>' % (len(cols) + 1, e(gname(g)), e(g)))
        for s in sorted(cov[g], key=lambda s: sname(s, g)):
            cells = ''.join(('<td class="y" title="%s ملف · %s">%s</td>' % (num(v[0]), human(v[1]), num(v[0])))
                            if (v := cov[g][s].get(c)) else '<td class="n">—</td>' for c in cols)
            body.append('<tr><th>%s <small dir="ltr">%s</small></th>%s</tr>' % (e(sname(s, g)), e(s), cells))
    cov_html = '<div class="scroll"><table class="cov"><thead><tr><th>المادة</th>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, ''.join(body))

    scripts = [(n, s, first_doc_line(os.path.join(root, n))) for n, s in files if os.path.splitext(n)[1].lower() in SCRIPT_EXT]
    scripts_html = ''.join('<tr><td dir="ltr" class="path">%s</td><td>%s</td><td dir="auto">%s</td></tr>' % (
        e(n), hs(s), e(d) or '<span class="muted">بلا شرح</span>') for n, s, d in scripts) or '<tr><td colspan="3">لا سكربتات.</td></tr>'

    types = collections.defaultdict(lambda: [0, 0])
    for n, s in files:
        t = types[ext_of(n)]; t[0] += 1; t[1] += s
    types_html = ''.join('<tr><td dir="ltr">.%s</td><td>%s</td><td>%s</td><td class="tb">%s</td></tr>' % (
        e(x) if not x.startswith('(') else '', num(c), hs(s), bar(s, total).replace('class="ok', 'class="n').replace('class="warn', 'class="n').replace('class="bad', 'class="n').replace('class="pct ok', 'class="pct n').replace('class="pct warn', 'class="pct n').replace('class="pct bad', 'class="pct n')) for x, (c, s) in
        sorted(types.items(), key=lambda kv: -kv[1][1])).replace('<td dir="ltr">.</td>', '<td>بلا امتداد</td>')

    notes_html = ''.join('<li class="%s">%s</li>' % (k, t) for k, t in notes)
    cards_html = ''.join('<div class="card"><div class="k">%s</div><div class="v">%s</div><div class="s">%s</div></div>' % (
        e(k), v, s) for k, v, s in cards)
    try:
        commit = subprocess.run(['git', '-C', root, 'log', '-1', '--format=%h · %ci'], capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ''
    repo = os.path.basename(root.rstrip('/'))
    total_bar = bar(total, limit) if limit else ''

    page = TEMPLATE.format(
        repo=e(repo), commit=e(commit), now=time.strftime('%Y-%m-%d %H:%M'), cards=cards_html,
        total_bar=total_bar, total=hs(total), limit=hs(limit) if limit else '—',
        folders=rows_folders + ''.join('<div class="frow"><div class="fname"><span dir="ltr" class="path">%s</span></div><div class="fbar">%s</div><div class="fsize">%s</div></div>' % (
            e(n), bar(s, base), hs(s)) for n, s in loose_root),
        coverage=cov_html, tree=tree_html(tree, '', 0), scripts=scripts_html, types=types_html, notes=notes_html,
        basis='حد GitHub Pages (%s)' % hs(limit) if limit else 'الحجم الكلي')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf8') as f:
        f.write(page)
    print('%s: %s files, %s, %d notes' % (a.out, len(files), human(total), len(notes)))


TEMPLATE = '''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>خريطة المشروع · {repo}</title>
<style>
:root{{--bg:#f5f7f8;--card:#fff;--ink:#1d2a31;--mute:#5f7380;--line:#dfe7eb;--accent:#1f7a7a;
--ok:#2e9e5b;--warn:#e08a1e;--bad:#d6453d;--okb:#e5f5eb;--warnb:#fdf1e1;--badb:#fbe7e5;--info:#2f6fb3;--infob:#e8f0fa;--track:#e9eef1}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#11181c;--card:#1a2328;--ink:#e3eaee;--mute:#93a6b1;--line:#2b383f;
--accent:#4fc1b5;--okb:#173326;--warnb:#3a2a12;--badb:#3d1c1a;--infob:#172a40;--track:#26323a}}}}
:root[data-theme=dark]{{--bg:#11181c;--card:#1a2328;--ink:#e3eaee;--mute:#93a6b1;--line:#2b383f;
--accent:#4fc1b5;--okb:#173326;--warnb:#3a2a12;--badb:#3d1c1a;--infob:#172a40;--track:#26323a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Segoe UI",Tahoma,"Noto Naskh Arabic","Noto Sans Arabic",system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:16px}}
header{{display:flex;gap:12px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}}
h1{{margin:0;font-size:1.5rem}} h2{{font-size:1.15rem;margin:28px 0 10px}}
.sub{{color:var(--mute);font-size:.85rem}}
button#t{{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:6px 12px;font:inherit;cursor:pointer}}
.path{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88em;unicode-bidi:isolate}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px}}
.card .k{{color:var(--mute);font-size:.85rem}} .card .v{{font-size:1.5rem;font-weight:700;color:var(--accent)}} .card .s{{color:var(--mute);font-size:.78rem;min-height:1em}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}}
.bar{{height:10px;background:var(--track);border-radius:99px;overflow:hidden;flex:1}}
.bar i{{display:block;height:100%;border-radius:99px;margin-inline-start:0}}
.bar i.ok{{background:var(--ok)}} .bar i.n{{background:var(--accent)}} .sz{{white-space:nowrap;unicode-bidi:isolate}} .bar i.warn{{background:var(--warn)}} .bar i.bad{{background:var(--bad)}}
.pct{{font-size:.8rem;min-width:52px;text-align:left}} .pct.bad{{color:var(--bad)}} .pct.warn{{color:var(--warn)}} .pct.ok{{color:var(--ok)}} .pct.n{{color:var(--mute)}}
.total{{display:flex;align-items:center;gap:10px;margin-bottom:8px}} .total .bar{{height:16px}}
.frow{{display:grid;grid-template-columns:minmax(150px,1.2fr) 2fr auto;gap:10px;align-items:center;padding:7px 0;border-top:1px solid var(--line)}}
.frow:first-child{{border-top:0}}
.fbar{{display:flex;align-items:center;gap:8px}} .fsize{{white-space:nowrap;font-variant-numeric:tabular-nums}}
small{{color:var(--mute)}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;background:var(--card)}}
th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}}
thead th{{position:sticky;top:0;background:var(--card);font-size:.85rem;color:var(--mute)}}
table.cov td{{text-align:center;font-variant-numeric:tabular-nums}} table.cov td.y{{background:var(--okb)}} table.cov td.n{{color:var(--bad);background:var(--badb)}}
table.cov th{{white-space:nowrap}} tr.grp th{{background:var(--infob);font-weight:700}}
td.tb{{min-width:140px}} td.tb .bar{{display:inline-block;width:calc(100% - 60px);vertical-align:middle}}
details{{margin:2px 0}} summary{{cursor:pointer;padding:4px 6px;border-radius:8px;display:flex;flex-wrap:wrap;gap:6px;align-items:baseline}}
summary:hover{{background:var(--track)}}
.lb{{color:var(--accent)}} .meta{{color:var(--mute);font-size:.8rem;margin-inline-start:auto}}
.kids{{border-inline-start:2px solid var(--line);margin-inline-start:12px;padding-inline-start:8px}}
ul.files{{list-style:none;margin:2px 0;padding:0}} ul.files li{{display:flex;gap:8px;padding:1px 6px;font-size:.9rem}} li.more{{color:var(--mute)}}
.tools{{display:flex;gap:8px;margin-bottom:8px}} .tools button{{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:8px;padding:3px 10px;font:inherit;font-size:.85rem;cursor:pointer}}
ul.notes{{list-style:none;padding:0;margin:0}} ul.notes li{{padding:8px 12px;border-radius:10px;margin:6px 0;border-inline-start:4px solid}}
li.bad{{background:var(--badb);border-color:var(--bad)}} li.warn{{background:var(--warnb);border-color:var(--warn)}}
li.info{{background:var(--infob);border-color:var(--info)}} li.ok{{background:var(--okb);border-color:var(--ok)}}
.muted{{color:var(--mute)}}
@media (max-width:640px){{main{{padding:12px}} h1{{font-size:1.25rem}}
.frow{{grid-template-columns:1fr auto;}} .fbar{{grid-column:1/-1;grid-row:2}}
.card .v{{font-size:1.25rem}} th,td{{padding:5px 6px;font-size:.88rem}}}}
</style></head><body><main>
<header><div><h1>خريطة المشروع <span dir="ltr" class="path">{repo}</span></h1>
<div class="sub">آخر إيداع: <span dir="ltr">{commit}</span> · أُنشئت: <span dir="ltr">{now}</span></div></div>
<button id="t" type="button" aria-label="تبديل الوضع">◐ الوضع</button></header>

<section class="cards">{cards}</section>

<h2>ملاحظات</h2><ul class="notes">{notes}</ul>

<h2>المساحة</h2>
<div class="panel"><div class="total"><b>الكل {total}</b>{total_bar}<small>الحد {limit}</small></div>
<div class="sub">النسبة لكل مجلد من {basis}. أخضر تحت ٧٠٪، برتقالي حتى ٩٠٪، أحمر فوقه.</div>
{folders}</div>

<h2>تغطية المواد</h2>
<div class="sub">عدد الملفات في كل قسم لكل مادة من كل صف (— يعني لا يوجد).</div>
<div class="panel">{coverage}</div>

<h2>شجرة المشروع</h2>
<div class="panel"><div class="tools"><button type="button" data-a="1">فتح الكل</button><button type="button" data-a="0">إغلاق الكل</button></div>{tree}</div>

<h2>السكربتات والأدوات</h2>
<div class="panel scroll"><table><thead><tr><th>الملف</th><th>الحجم</th><th>الشرح</th></tr></thead><tbody>{scripts}</tbody></table></div>

<h2>أنواع الملفات</h2>
<div class="panel scroll"><table><thead><tr><th>النوع</th><th>العدد</th><th>الحجم</th><th>من الكل</th></tr></thead><tbody>{types}</tbody></table></div>
</main>
<script>
(function(){{var r=document.documentElement,k='graphify-theme';
try{{var s=localStorage.getItem(k);if(s)r.dataset.theme=s;}}catch(e){{}}
document.getElementById('t').onclick=function(){{var d=r.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
r.dataset.theme=d==='dark'?'light':'dark';try{{localStorage.setItem(k,r.dataset.theme);}}catch(e){{}}}};
document.querySelectorAll('.tools button').forEach(function(b){{b.onclick=function(){{var o=b.dataset.a==='1';
document.querySelectorAll('details').forEach(function(d){{d.open=o;}});}};}});}})();
</script></body></html>
'''

if __name__ == '__main__':
    main()
