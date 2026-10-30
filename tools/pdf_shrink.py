#!/usr/bin/env python3
"""pdf_shrink: تصغير ملفات PDF الكبيرة (السبورات والملخصات المصوّرة) بـ Ghostscript دون تغيير عدد الصفحات.

Usage: python3 tools/pdf_shrink.py [PATH ...] [--top N] [--min-mb 2] [--dpi 150]
                                   [--min-saving 15] [--jobs N] [--preview DIR] [--apply]

PATH is a .pdf or a folder (default: the whole repo). The PDFs here are page images
(JPEG ~200 ppi), so the gain comes from re-encoding the images at --dpi (150 keeps the
board text sharp on a screen). Each file is written to a temp file first and kept only if:
the page count is unchanged (checked with qpdf, or Ghostscript) and it is at least
--min-saving % smaller. Without --apply nothing is replaced: it only reports the saving.
--preview DIR writes page 1 before/after as PNG to compare by eye.
Needs Ghostscript (gs); qpdf is optional. Python standard library only.
"""
import argparse, concurrent.futures, os, shutil, subprocess, sys, tempfile


def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024 or u == 'GB':
            return ('%d %s' % (n, u)) if u == 'B' else ('%.*f %s' % (2 if u == 'GB' else 1, n, u))
        n /= 1024.0


def find_pdfs(paths):
    out = []
    for p in paths:
        if os.path.isfile(p) and p.lower().endswith('.pdf'):
            out.append(p)
        elif os.path.isdir(p):
            for d, dirs, fs in os.walk(p):
                dirs[:] = [x for x in dirs if not x.startswith('.')]
                out += [os.path.join(d, f) for f in fs if f.lower().endswith('.pdf')]
    return sorted(set(os.path.normpath(p) for p in out))


def pages(path):
    if shutil.which('qpdf'):
        r = subprocess.run(['qpdf', '--show-npages', path], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip())
    ps = '(%s) (r) file runpdfbegin pdfpagecount = quit' % path.replace('\\', '/').replace('(', '\\(').replace(')', '\\)')
    r = subprocess.run(['gs', '-q', '-dNODISPLAY', '-dNOSAFER', '-c', ps], capture_output=True, text=True)
    try:
        return int(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def gs_shrink(src, dst, dpi):
    cmd = ['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite',
           '-dCompatibilityLevel=1.5', '-dPDFSETTINGS=/ebook', '-dDetectDuplicateImages=true',
           '-dPassThroughJPEGImages=false', '-dAutoRotatePages=/None']
    for kind in ('Color', 'Gray'):
        cmd += ['-dDownsample%sImages=true' % kind, '-d%sImageDownsampleType=/Bicubic' % kind,
                '-d%sImageResolution=%d' % (kind, dpi), '-d%sImageDownsampleThreshold=1.0' % kind]
    cmd += ['-dMonoImageResolution=%d' % (dpi * 2), '-sOutputFile=' + dst, src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0, r.stderr.strip()[-300:]


def preview(src, out_png):
    subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=png16m', '-r80',
                    '-dFirstPage=1', '-dLastPage=1', '-sOutputFile=' + out_png, src], capture_output=True)


def work(path, a, tmpdir):
    before = os.path.getsize(path)
    tmp = os.path.join(tmpdir, '%d-%s' % (abs(hash(path)), os.path.basename(path)))
    ok, err = gs_shrink(path, tmp, a.dpi)
    if not ok:
        return path, before, before, 'فشل Ghostscript: ' + err
    after = os.path.getsize(tmp)
    saving = 100.0 * (before - after) / before
    n0, n1 = pages(path), pages(tmp)
    if n0 is None or n0 != n1:
        os.remove(tmp)
        return path, before, before, 'تُرك: عدد الصفحات %s ← %s' % (n0, n1)
    if saving < a.min_saving:
        os.remove(tmp)
        return path, before, before, 'تُرك: التوفير %.0f%% فقط' % saving
    if a.preview:
        stem = os.path.join(a.preview, path.replace(os.sep, '_')[:-4])
        preview(path, stem + '.before.png')
        preview(tmp, stem + '.after.png')
    if a.apply:
        shutil.move(tmp, path)
        return path, before, after, 'استُبدل (−%.0f%%، %d صفحة)' % (saving, n0)
    os.remove(tmp)
    return path, before, after, 'سيُوفّر %.0f%% (%d صفحة)' % (saving, n0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='*', default=['.'])
    ap.add_argument('--top', type=int, help='only the N largest PDFs')
    ap.add_argument('--min-mb', type=float, default=2.0, help='skip PDFs smaller than this')
    ap.add_argument('--dpi', type=int, default=150)
    ap.add_argument('--min-saving', type=float, default=15.0, help='keep the result only if it saves at least this %%')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--preview', metavar='DIR', help='write page-1 before/after PNGs here')
    ap.add_argument('--apply', action='store_true', help='replace the files in place')
    a = ap.parse_args()
    if not shutil.which('gs'):
        sys.exit('Ghostscript (gs) غير مثبّت: apt-get install ghostscript أو brew install ghostscript')
    pdfs = [p for p in find_pdfs(a.paths) if os.path.getsize(p) >= a.min_mb * 1024 ** 2]
    pdfs.sort(key=lambda p: -os.path.getsize(p))
    if a.top:
        pdfs = pdfs[:a.top]
    if not pdfs:
        print('لا توجد ملفات PDF أكبر من %.1f MB' % a.min_mb)
        return
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
    print('%s %d ملف PDF (%s) بدقة %d dpi…' % ('تصغير' if a.apply else 'تجربة تصغير', len(pdfs),
                                           human(sum(os.path.getsize(p) for p in pdfs)), a.dpi))
    tot0 = tot1 = 0
    with tempfile.TemporaryDirectory() as tmpdir, concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for path, b, af, note in ex.map(lambda p: work(p, a, tmpdir), pdfs):
            tot0 += b
            tot1 += af
            print('- %s  %s ← %s  %s' % (path, human(b), human(af), note))
    print('\nالمجموع: %s ← %s (توفير %s)' % (human(tot0), human(tot1), human(tot0 - tot1)))
    if not a.apply and tot1 < tot0:
        print('لم يُستبدل شيء. أعد الأمر مع --apply للتطبيق.')


if __name__ == '__main__':
    main()
