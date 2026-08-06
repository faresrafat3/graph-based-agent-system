# ADR-0003: أوضاع تواصل الوكلاء (A2A edges) — auto / steer / follow_up

- **الحالة**: مقترح (Proposed) — Epic E3
- **التاريخ**: 2026-08-06

## السياق (Context)

مشروعنا إطار graph: `topology_assembler` يبني حواف بين وكلاء bespoke. نحتاج دلالات توصيل على الحواف تتجاوز "fire‑and‑forget".

prime-agent يطبّق 3 أوضاع تسليم لـ `agent_message.send(...)`: [✓ code: long-running-agents.md:104‑110]
- `auto`: توجيه عمل نشط أو تسليم فوري لهدف idle.
- `steer`: حقن مقصود في عمل نشط.
- `follow_up`: انتظار انتهاء عمل الهدف الحالي.

ويحتفظ بسجل أبوي للـ subagents يبقى عبر compaction/restart/restore. [✓ code: rlm.md:88‑104]

## القرار (Decision)

1. كل حافة graph في مشروعنا تحمل `delivery_mode ∈ {auto, steer, follow_up}`.
2. `steer` يُحقن في العمل النشط للوكيل الهدف (لا ينتظر نهاية turn).
3. `follow_up` يُوضع في queue ويُسلّم بعد انتهاء turn الحالي.
4. سجل subagents أبوي (مسارات session + status) يبقى عبر compaction/restart.
5. scheduled prompts: due‑tick يُطالَب قبل التسليم (لا إعادة تشغيل عند crash)؛ miss → coalesce. [✓ code: long-running-agents.md:170]

## العواقب (Consequences)

- **إيجابي**: حواف graph ذات دلالات صريحة؛ تحسّن حلقات التغذية الراجعة (feedback edges) التي يفضّلها Fares.
- **سلبي**: تعقيد في جدولة الحواف.
- **مخاطر**: رسالة `steer` تقطع عملاً — يُحل بحدود صلاحيات صريحة لكل حافة.

## المراجع

- [✓ code] `packages/coding-agent/docs/long-running-agents.md:71‑110`
- [✓ code] `packages/coding-agent/docs/rlm.md:78‑104`
- مشروعنا: `agents/topology_assembler.py`, `agents/agent_forge.py`
