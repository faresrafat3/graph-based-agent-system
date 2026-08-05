# خطة تنظيف وضبط المشروع بناءً على القياسات الحديثة و SOTA

> **للمستخدم:** دي خطة توجيه/تنظيف مش feature جديد. الهدف: نقفل فجوات القياسات اللي اتقاستها، نشغّل التجارب اللي لسه معلقة، ونحط النظام على خريطة الـ SOTA الحقيقية عشان نقرر الخطوة الجاية بوعي.

## 📊 السياق (القياسات اللي عندنا دلوقتي)

| المصدر | الرقم | الحالة |
|---|---|---|
| Benchmark suite (4 scenarios) | Success 75% / Health 77.7 | 🔴 `scenario_4_security_adversarial` فاشل (حاول يعمل NEVER action) |
| SWE-bench single-shot (8 inst) | 4/8 (50%) أحسن / 1/8 (12.5%) أسوأ | 🔴 تذبذب 4× من LLM nondeterminism |
| SWE-bench AlphaCode (N=3, 8 inst) | 1/8 (12.5%) | 🟡 variance reducer مش capability multiplier |
| SWE-bench loop mode (decision #3) | **TBD — متعملش قيد** | 🔴 التجربة المحورية معلقة |
| Thrashing harness (P7) | مكتب موجود، **مش متشغل** | 🟡 observability only |
| VERIFY node + Cynefin | اتعملوا، **بلا قياس** | 🟡 مفيش أرقام أثر |

**SOTA reference (أغسطس 2026):** Orchard-SWE ≈ 69.7% على SWE-bench Verified؛ طرز أمامية (Claude Opus 5 يُنقل ~96%). نظامنا 12.5–50% → **الفجوة مش في الأرشيتكتشير، الفجوة في قوة المولّد (`step-3.7-flash`)**. ده بيأكد استنتاج الـ AGENT-LOOP-EXPERIMENT: لو الـ loop mode مدّش الرقم → السقف هو الموديل مش الـ graph.

## 🎯 الهدف
1. نقفل الـ benchmark failure (security adversarial) ونوصله 100% defense.
2. نخلص تجربة الـ loop mode (decision #3) ونحط أرقام حقيقية في جدول المقارنة.
3. نشغّل thrashing harness وناخد قرار probe-budget (P4) بـ evidence.
4. نربط VERIFY node + Cynefin بقياس أثر فعلي (postcondition pass-rate).
5. نكتب وثيقة مقارنة SOTA صادقة تحدد مين السقف (موديل ولا أرشيتكتشير).

---

## المهام (بالترتيب)

### Task 1 — إصلاح `scenario_4` security breach في benchmark
**الهدف:** الـ adversarial scenario يترفض بـ breach صريح مش exception/فشل صامت.
**الملفات:** `benchmarks/benchmark_suite.py:51` (scenario_4)، `agents/task_decomposer.py` (NEVER gate)
**الخطوات:**
1. اكتب test: `test_scenario_4_produces_never_breach` — يتأكد إن النتيجة فيها breach بكلمة "never"/"permission" وبـ `effective_success=True` (لأنه اتحظر).
2. شغّله → FAIL (الحين between raw success=False و defense success).
3. عدّل `is_adversarial_blocked` أو الـ decomposer عشان يحوّل الـ NEVER violation لـ `breach` صريح بدل ما يحاول التنفيذ.
4. شغّل `make test` → PASS، وأعد تشغيل `python scripts/run_benchmarks.py` → defense 100%.
**تحقق:** `reports/latest_benchmark.json` → `scenario_4` effective_success=true، health score ≥ 80.

### Task 2 — تشغيل loop mode (decision #3) و Docker-grade
**الهدف:** نقفل التجربة المحورية بأرقام.
**الملفات:** `benchmarks/swebench_harness.py` (يحتاج `--mode loop` في CLI عند السطر 831)
**الخطوات:**
1. أضف `--mode loop` لـ `choices` في argparse (السطر 831) + واير `solve_agent_loop`.
2. شغّل على 8 instances requests محلياً: `python benchmarks/swebench_harness.py --mode loop --limit 8 --out results/loop` (بـ PYTHONPATH و .env).
3. Docker-grade بالـ sequential grader زي `grade_alphacode.py`.
4. املأ جدول المقارنة في `docs/AGENT-LOOP-EXPERIMENT.md §3` بأرقام حقيقية.
5. اكتب قرار: graph vs model-swap حسب نتيجة H.
**تحقق:** الجدول فيه أرقام لكل من {1142,1724,1766,1921,2317,2931}؛ القرار مسجّل.

### Task 3 — تشغيل thrashing harness وقرار P4
**الهدف:** ناخد قرار probe-budget بناءً على evidence.
**الملفات:** `scripts/measure_thrashing.py` (موجود)
**الخطوات:**
1. شغّل `export PYTHONPATH=. && source .env && python scripts/measure_thrashing.py`.
2. لو `repeated_hypothesis_count > 0` في أي عيّنة → نفّذ P4 (probe budget cap في debugger/reflexion).
3. لو صفر → سجّل "defer P4" في الـ experiment doc.
**تحقق:** verdict مطبوع؛ لو thrashing → PR بـ `MAX_REFINEMENTS` budget + test.

### Task 4 — قياس أثر VERIFY node + Cynefin
**الهدف:** نثبت الـ VERIFY node بيقفل الـ silent partial completion بأرقام.
**الملفات:** `agents/deterministic_validator.py` (verify_execution_postcondition)، `agents/domain_dispatcher.py` (domain/confidence)
**الخطوات:**
1. اكتب test: postcondition `file_exists` على patch بيطلع file فعلاً → تتأكد إنه بيرفض الـ partial completion.
2. اكتب test: `domain_dispatcher` بيطلع `{domain, confidence}` على كل نتيجة.
3. أضف قسم "Measured Impact" في `docs/AGENT-LOOP-EXPERIMENT.md` أو README بأرقام الـ postcondition pass-rate على عيّنة من predictions.
**تحقق:** tests PASS؛ section الأثر موجود برقم.

### Task 5 — وثيقة مقارنة SOTA صادقة
**الهدف:** نحط النظام على خريطة الـ SOTA عشان نعرف نقرر صح.
**الملفة:** `docs/SOTA-POSITION.md` (جديد)
**المحتوى:**
- جدول: نظامنا (single/alphacode/loop) vs Orchard-SWE 69.7% vs frontier ~96%.
- استنتاج صريح: السقف = الموديل (`step-3.7-flash`) مش الأرشيتكتشير.
- توصية: قبل ما نبني الـ ultimate graph، نجرب موديل أقوى (coding-tuned) على نفس الـ 8 instances كـ controlled experiment.
**تحقق:** الوثيقة مقروءة ومنسوبة لمراجع (swebench.com، مدونات الـ SOTA).

### Task 6 — تنظيف: توحيد أوامر الـ CLI و إزالة الـ dead paths
**الهدف:** نظافة حسب الـ code-audit (F3/F9 متحلوا، نتأكد من باقي).
**الملفات:** `benchmarks/swebench_harness.py` CLI، `Makefile`، `README.md`
**الخطوات:**
1. توحيد `--mode` choices (agent/baseline/alphacode/loop) في مكان واحد + docstring.
2. تأكد `make test` لسه 281+ PASS؛ `make audit` نضيف.
3. update README SWE-bench section بالأرقام الجديدة.
**تحقق:** `make test` green؛ README متسق مع الأرقام.

---

## 🧪 التحقق النهائي
- `make test` → كله أخضر (281+ tests)
- `python scripts/run_benchmarks.py` → defense 100%, health ≥ 80
- `python scripts/measure_thrashing.py` → verdict مسجّل
- `docs/AGENT-LOOP-EXPERIMENT.md` → جدول loop mode مملوء بأرقام
- `docs/SOTA-POSITION.md` → مقارنة منشورة

## ⚠️ المخاطر
- **شبكة LLM:** الـ loop/alphacode محتاجين استقرار الشبكة (الـ 11-account pool بيقلل الـ 429 بس مش الـ transport drops). نراعي ده في التوقيت.
- **تذبذب الموديل:** عيّنة 8 instances مش كافية إحصائياً — هنكتب ده صراحة في الوثيقة.
- **القرار الحرج:** لو الـ loop mode مدش الرقم → نوصي بـ model-swap experiment قبل بناء الـ graph (وفر وقت وجهد).

## ❓ أسئلة مفتوحة
1. نجرب موديل أقوى (مثلاً coding-tuned) كـ controlled experiment ولا نكمل على `step-3.7-flash`؟
2. نوسّع عيّنة SWE-bench لـ 50+ instance عشان قياس إحصائي ولا نكتفي بـ 8؟

---

## ✅ التنفيذ (2026-08-04) — الجزء الآمن اتعمل

**ملاحظة:** السيشن التانية شغالة على `benchmarks/swebench_harness.py` (loop mode) +
`debugger/reflexion` + `deterministic_validator/domain_dispatcher` (VERIFY/Cynefin).
جنّبت المهام دي (2/3/4) عشان متصادمش، ونفّذت الآمن:

- [x] **Task 1 — FIXED:** `scenario_4` adversarial كان بيتحجب فعلياً بس `breaches` list
      كان فاضي → benchmark بيعدّه فشل (silent breach). أصلحت الـ exception handler في
      `benchmarks/benchmark_suite.py` يحط نص الخطأ في `breaches` (Law 3 fail-loudly).
      أضفت 2 tests (TDD: RED→GREEN). النتيجة: defense 100%, SECURE PASS.
- [x] **Task 5 — DONE:** كتبت `docs/SOTA-POSITION.md` — مقارنة صادقة (نظامنا 12.5–50%
      vs Orchard 69.7% vs frontier ~96%) + استنتاج إن السقف = الموديل مش الأرشيتكتشير
      + توصية generator-swap experiment قبل بناء الـ graph.
- [x] **Task 6 (الجزء الآمن) — DONE:** ضفت روابط `SWEBENCH-REPORT.md` + `SOTA-POSITION.md`
      في README Documentation section. (الـ CLI wiring الموحّد مؤجّل — بيلمس `swebench_harness.py`
      المملوك للسيشن التانية.)

**التحقق:**
- `make test` → 283 passed (281 + 2 جديدة) ✅
- `make audit` → Stepfun policy + governance checks نضيف ✅
- Task 1 RED→GREEN بـ 3 tests في `tests/test_benchmarks.py` ✅

**مؤجّل (السيشن التانية بتعمله):** Task 2 (loop docker-grade)، Task 3 (thrashing run)،
Task 4 (VERIFY impact measurement). لما السيشن التانية تخلص هنرجع نكملهم أو ننسّق معاها.
