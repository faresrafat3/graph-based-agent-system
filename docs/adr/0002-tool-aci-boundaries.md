# ADR-0002: حدود الأدوات (Tool/ACI) — typed tools + MCP، لا IPython‑كأداة‑شاملة

- **الحالة**: مقبول (Accepted) — Epic E6
- **التاريخ**: 2026-08-06

## السياق (Context)

prime-agent يعتمد فلسفة "كل شيء برمجي": IPython الثابت هو الأداة المدمجة الوحيدة؛ القراءة/التعديل/الشل/الأدوات/subagents كلها عبر كود Python في الـ kernel. [✓ code: README.md:38, rlm.md:31‑51]

مشروعنا يفضّل **typed tools + MCP** لأسباب حوكمية: الصلاحيات (READ/WRITE/NEVER/HUMAN_CHECKPOINT) عندنا هي **طبقة معمارية لا prompt‑jailbox**. [✓ code مشروعنا: CONSTITUTION.md:41‑64]

أداة IPython‑الشاملة أضعف في فرض الصلاحيات لأن النموذج يكتب كوداً تعسفياً ينفّذ بصلاحيات OS. [✓ code: rlm-runtime.md:251]

## القرار (Decision)

1. **لا نتبنى** نمط RLM/REPL (IPython‑كأداة‑شاملة).
2. **نحتفظ** بأدوات مكتوبة (typed)، كل أداة تحمل metadata صريحة:
   `name, description, input_schema, permissions, risk_level, timeout, network_access, filesystem_access, requires_confirmation`. [≈ استنتاج من E6.2]
3. **نعتمد MCP** كطبقة أدوات معيارية (لا lock‑in بمزود). [✓ code: packages/ai/src/mcp/]
4. **before/after tool hooks**: `beforeToolCall` يستطيع `block:true`؛ `afterToolCall` يتجاوز `isError`/`terminate`. [✓ code: types.ts:257‑277]
5. **صلاحيات معمارية**: أداة خارج نطاقها تُرفض في runtime قبل التنفيذ (لا تنتظر النموذج).

## العواقب (Consequences)

- **إيجابي**: توافق مع فلسفة الحوكمة عندنا؛ فرض صلاحيات قابل للاختبار؛ عزل أوضح.
- **سلبي**: فقدان مرونة "اكتب أي كود" — مقبول لأننا graph/DAG مُحكم لا REPL.
- **مخاطر**: أداة جديدة بلا metadata → تُرفض عند التحميل (fail loudly).

## المراجع

- [✓ code] `packages/coding-agent/docs/rlm.md:31‑51`
- [✓ code] `packages/agent/src/types.ts:257‑277`
- [✓ code] `packages/ai/src/mcp/index.ts`
- [✓ code] `packages/coding-agent/docs/rlm-runtime.md:249‑252`
