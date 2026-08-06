# ADR-0001: اعتماد نمط Continual Harness كطبقة حوكمة تكميلية

- **الحالة**: مقترح (Proposed) — جاهز للتنفيذ في Epic E2
- **التاريخ**: 2026-08-06

## السياق (Context)

مشروعنا يحكمه `CONSTITUTION.md` (immutable base) + `LAWS.md` + `sage_council` + `systems_layer` + `cynefin`. توجيه Fares الصريح: **"EXTEND existing governance، لا fork سلطة ثانية"**.

prime-agent ينفّذ النمط ذاته في الكود: "النظام الأساسي immutable؛ الـ `/refine` يطبّق تحديثات تكميلية صغيرة مبنية على أدلة (evidence‑backed) فوق الـ base، مع snapshots للـ rollback". [✓ code: rlm-runtime.md:213, README.md:40]

نحتاج آلية لإضافة "طبقة تكميلية قابلة للمراجعة والتطوير بالأدلة" فوق الدستور دون لمسه — بالضبط ما يفعله `HarnessState`. [✓ code: prime-agent-runtime/src/rlm/harness.py]

## القرار (Decision)

نتبنّى نمط Continual Harness كطبقة حوكمة تكميلية في مشروعنا:

1. **Schema**: `HarnessEntry{kind: prompt|memory|skill|subagent, scope: local|global, ...}` + `RefinementEvent{trigger, changes[], evidence, outcome}`. [✓ code: harness.py:18‑122]
2. **التخزين**: `system/harness_state.json` (json، v1 schema) محلي للجلسة + نطاق global اختياري.
3. **Refinement**: واجهة `refine.run(instructions)` تنشئ `RefinementEvent` بـ `evidence` إلزامي؛ `refine.rollback(id)` يرجع الحالة من snapshot.
4. **حماية الحقول**: تحديث بـ `None` يحتفظ بالحقول؛ قيمة صريحة (حتى `{}`) تطغى. [✓ code: harness.py:366‑398]
5. **مزامنة**: `load()` يعيد القراءة إن تغير mtime على القرص (لا تطميس كتابات متوازية). [✓ code: harness.py:186‑196]
6. **الدستور يبقى immutable**: harness لا يعدّل `CONSTITUTION.md`؛ rollback مسجّل في `distillation_ledger`.

## العواقب (Consequences)

- **إيجابي**: يحقق توجيه "EXTEND"؛ يضيف قابلية تطوير بالأدلة دون سلطة ثانية؛ يقلل تكلفة تعديل الدستور.
- **سلبي**: طبقة حالة إضافية يجب اختبارها (mtime sync، rollback).
- **مخاطر**: تصادم بين harness global ومحتوى الدستور — يُحل بالأسبقية الصريحة (الدستور > harness).

## المراجع

- [✓ code] `prime-agent-runtime/src/rlm/harness.py` (CRUD + RefinementEvent)
- [✓ code] `packages/coding-agent/docs/rlm-runtime.md:207‑213`
- [✓ code] `packages/coding-agent/skills/refine/SKILL.md`
- مشروعنا: `CONSTITUTION.md`, `system/distillation_ledger.jsonl`
