# ADR-0004: مخطط التتبع (Trace Schema) — JSONL tree مستوحى من session-format

- **الحالة**: مقترح (Proposed) — Epic E4
- **التاريخ**: 2026-08-06

## السياق (Context)

مشروعنا يسجّل في `system/distillation_ledger.jsonl` لكن بصيغة غير موحّدة. نحتاج schema قابل لـ replay وإعادة بناء context.

prime-agent يخزّن الجلسات كـ **JSONL tree (v3)** بـ `id`/`parentId`، وentries متخصصة: `compaction`, `branch_summary`, `label`, `child_usage_attributed`, `custom` (لا تدخل context), `custom_message` (تدخل context). [✓ code: session-format.md:1‑40, 233‑353]

`buildSessionContext()` يمشي من leaf لـ root، يطبّق compaction، ويتجاهل bookkeeping entries. [✓ code: session-format.md:341‑353]

## القرار (Decision)

1. نعتمد JSONL tree بـ `id`/`parentId` + header (`version`, `cwd`, `parentSession?`).
2. أنواع entries: `message`, `compaction`, `branch_summary`, `label`, `custom` (خارج context), `custom_message` (داخل context), `refinement` (من ADR‑0001).
3. `buildContext()` walk leaf→root + إسقاط compaction + تجاهل bookkeeping.
4. التفريع موضعي (in‑place branching) عبر `parentId` — لا ملفات جديدة.
5. **مسجّلنا** (`distillation_ledger.jsonl`) يستخدم نفس schema؛ sage_council entries = `custom` (خارج context).

## العواقب (Consequences)

- **إيجابي**: replay قابل للتكرار؛ توافق مع أدوات تحليل خارجية؛ تقسيم واضح context/non‑context.
- **سلبي**: هجرة السجل الحالي (إن وُجد) إلى v3.
- **مخاطر**: ملف ضخم → تقسيم حسب session‑id (مثل prime-agent: `~/.prime/agent/sessions/<id>.jsonl`).

## المراجع

- [✓ code] `packages/coding-agent/docs/session-format.md` (كامل)
- [✓ code] `packages/coding-agent/src/core/session-manager.ts` (2324 LOC)
- مشروعنا: `system/distillation_ledger.jsonl`
