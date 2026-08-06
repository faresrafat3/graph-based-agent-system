# DECISIONS — استيعاب دروس Prime Agent لمشروعنا

> التوصية النهائية مبنية على clone فعلي لـ `prime-agent` (v0.7.0، TypeScript/pi‑mono) في `/tmp/prime-agent`.
> مرجع النفي: Reference 5 (gemini) وصف الريبو كـ "Python RL harness + Docker + MCTS + Vector DB" من خياله — **هذا وهمي**، لا يطابق الكود.

## القرار الرئيسي

**استلهام انتقائي (Selective Adoption) — لا تبنٍّ كامل، لا رفض.**
نأخذ **الآليات** (المعمارية القابلة للنقل) ونترك **شكل المنتج** (REPL agent).

## ما نتبنّاه (Adopt)

1. **Continual Harness** كطبقة حوكمة تكميلية فوق `CONSTITUTION.md` (immutable) مع rollback بالأدلة.
   - لماذا: يخدم توجيه Fares "EXTEND existing governance، لا fork سلطة ثانية"؛ يقابل `distillation_ledger`/`systems_layer`.
   - مصدر: [✓ code] `prime-agent-runtime/src/rlm/harness.py`, `docs/rlm-runtime.md:207‑213`
2. **Host‑request bridge** (Python↔runtime يملك الحالة؛ النموذج يطلب عبر واجهة مكتوبة).
   - لماذا: يطابق صلاحياتنا المعمارية (READ/WRITE/NEVER/HUMAN_CHECKPOINT لا prompt‑jailbox).
   - مصدر: [✓ code] `docs/rlm.md:135‑139`, `docs/rlm-runtime.md:32`
3. **JSONL tree trace schema** (id/parentId + entries) لمسجّلنا.
   - مصدر: [✓ code] `docs/session-format.md`
4. **أوضاع A2A** (`auto | steer | follow_up`) + due‑tick claim لحواف الـ graph.
   - مصدر: [✓ code] `docs/long-running-agents.md:104‑170`
5. **Unified ModelProvider interface** + faux provider للاختبار.
   - مصدر: [✓ code] `packages/ai/src/providers/`, AGENTS.md:150‑154

## ما نستلهمه جزئياً (Adapt)

- **Tool/ACI**: نحتفظ بـ typed tools + MCP (لا IPython‑كأداة‑شاملة — أضعف في فرض الصلاحيات). [✓ code] `docs/rlm.md:31‑51`
- **Compaction/context budgeting**: السياسة فقط؛ تتصل بطبقة الذاكرة العاملة عندنا. [✓ code] `docs/long-running-agents.md:228‑239`
- **Skill progressive disclosure**: للـ `skill-creator` يقابل استخراج الأنماط في `distillation_ledger`. [✓ code] `docs/skills.md`

## ما نتجنّبه (Reject)

- **RLM / REPL paradigm** (IPython‑كأداة‑شاملة): مختلف عن graph/DAG التنسيقي عندنا. [✓ code] `README.md:31`
- **افتراض أن kernel = sandbox**: ليس sandbox أمني؛ عزل حقيقي للكود غير الموثوق. [✓ code] `docs/rlm-runtime.md:251`
- **lock‑in على pi‑mono**: نحن Python؛ الاقتباس مفاهيمي لا كودي. [✓ code] `README.md:104`

## معايير القرار (Decision Criteria)

| معيار | وزن | تعليق |
|---|---|---|
| توافق مع الدستور/الحوكمة | عالي | الأولوية القصوى (Fares) |
| قابلية النقل لمعماريتنا (graph) | عالي | رفض RLM/REPL |
| النضج/استقرار الواجهة | متوسط | v0.7.0 — أفكار أأمن من كود |
| الترخيص (MIT) | عالي | يسمح بالاقتباس مع attribution |
| الأمان | حرج | لا تنازل عن صلاحيات معمارية |

## ما لم نقرره بعد (Open)

- هل نتبنى `prime-agent` كـ **تطبيق واجهة** (TUI plugin في Hermes) أم فقط **مفاهيم**؟ → يحتاج قرار من Fares (المفضّل عنده: native Hermes surfaces لا HTML مخصص).
- حدود العزل الحقيقي (gVisor/Firecracker/E2B) عند تنفيذ كود غير موثوق في `tools/`.

## Attribution

أي كود منقول من `prime-agent` يحتفظ بإشعار MIT (Copyright Mario Zechner 2025 + Prime Intellect 2026). [✓ code] `LICENSE`
