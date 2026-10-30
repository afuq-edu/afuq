# afuq · ملفات منصة أفق

مستودع ملفات ثابتة تُنشر على GitHub Pages في `https://afuq-edu.github.io/afuq/` (نفس نطاق الموقع الرئيسي `afuq-edu.github.io`). لا يوجد بناء ولا Jekyll (`.nojekyll`): كل ملف متتبَّع في git يُنشر كما هو.

- المالك: عيسى (`afuq-edu`). اكتب له بالعربية وباختصار.
- الملفات هنا **ناتجة** عن سكربتات المستودع الرئيسي `afuq-edu/afuq-edu.github.io` (مجلد `tools/`: `build_quiz.py`، `build_scorm.py`، `add_summaries.py`…). إصلاح محتوى درس أو لعبة مكانه هناك ثم يُعاد توليد الملف هنا، لا التعديل اليدوي على ملف مولَّد.
- الروابط التي تبدأ بـ `/` (مثل `/assets/lessonidx.js`) تشير إلى المستودع الرئيسي، لا إلى هذا المستودع.

## البنية

```
<صف 1..12>/<مادة>/
  board/       lesson-boards.pdf, classroom-board-questions.pdf (+ how-my-board.pdf, board-layouts.pdf)
  recap/       lesson-summaries.pdf            ملخصات بالصور
  summaries/   <وحدة>-<درس>-m.pdf (خريطة ذهنية) و -s.pdf (ملخص)، all.pdf
  view/        slides/ | interactive/ | lessons/  index.html  العرض التفاعلي
  games/       index.html
q/engine.js, q/engine.css                     محرك ألعاب الدروس (مشترك)
q/<صف>/<مادة>/index.html                      بيانات الدروس في window.QZ = {g, gn, s, sn, L:[{t, u, q, o}]}
scorm/<صف>/<مادة>/L01.zip …                   حزمة SCORM 1.2 لكل درس (لمنصة نور): imsmanifest.xml + index.html + fonts/
```

أسماء المواد: math, science, arabic, english, islamic, social, it, arts, pe, physics, chemistry, biology, envsci, advmath, basicmath.

## القيود المهمة

- **حد GitHub Pages هو 1 GB للموقع المنشور.** المستودع كان 1.14 GB في 2026-10-30، و75% منه ملفات PDF في `board/` و`recap/`. أي إضافة يجب أن تُفحص بالحجم أولًا.
- الملف الواحد يجب أن يبقى أقل من 100 MB (حد GitHub)، ويُفضّل أقل من 10 MB.
- الأسماء بحروف إنجليزية وأرقام و `-` فقط، بلا مسافات ولا حروف عربية (روابط آمنة).
- لا تدفع مباشرة إلى `main`: افتح فرعًا وطلب دمج، والمالك يدمج بنفسه.

## الأدوات (Python بلا مكتبات خارجية)

| الأمر | ماذا يفعل |
|---|---|
| `python3 tools/check_site.py` | فحص كامل: الحجم مقابل 1 GB، الملفات الكبيرة، الروابط النسبية المكسورة، صحة `window.QZ`، حزم SCORM (manifest، الملفات، الترقيم، مطابقتها لعدد الدروس)، الأسماء، التكرار. يخرج بـ 1 عند وجود خطأ. `--only scorm,q` لفحص جزء، `--json` للآلة. |
| `python3 tools/pdf_shrink.py [مسار] --top 20` | تجربة تصغير أكبر ملفات PDF بـ Ghostscript (150 dpi) وعرض التوفير. `--apply` يستبدل الملفات، `--preview DIR` يحفظ صورة الصفحة الأولى قبل/بعد. يتحقق من بقاء عدد الصفحات. |
| `python3 tools/graphify.py OUT.html` | خريطة مرئية للمستودع (إن كانت موجودة في الفرع، انظر المهارة `/graphify`). |

## المهارات في `.claude/skills/`

- `/check-site`: افحص الموقع ولخّص النتائج.
- `/shrink-pdfs`: أنزل حجم الموقع تحت حد 1 GB بتصغير ملفات PDF مع مراجعة الجودة بالعين.
- `/add-files`: أضف ملفات صف أو مادة أو دروس جديدة في أماكنها الصحيحة وافحصها وافتح طلب دمج.
- `/scorm-inspect`: افتح حزمة SCORM واشرح محتواها أو مشكلتها.

## نصائح للسرعة

- المستودع كبير (≈1.2 GB). للنسخ استعمل `git clone --depth 1` بمهلة طويلة (5–10 دقائق)، ولا تشغّل نسختين معًا.
- للقراءة دون نسخ كل شيء: `git clone --depth 1 --filter=blob:none --sparse` ثم `git sparse-checkout set q scorm/1/math` مثلًا. انتبه أن `git ls-tree -l` يجلب كل الملفات الناقصة ليعرف أحجامها.
- لعدّ الأحجام بسرعة دون قراءة الملفات: `git ls-files -z | xargs -0 du -cb | tail -1`.
- قبل دفع فرع من نسخة سطحية: `git fetch origin main` حتى لا يُرفع المستودع كاملًا من جديد.
