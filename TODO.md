# TODO — استيعاب دروس Prime Agent في مشروعنا (graph-based-agent-system)

> كل المهام مبنية على **clone فعلي** لـ `prime-agent` في `/tmp/prime-agent` (v0.7.0، TypeScript/pi‑mono + حزمة Python `prime-agent-runtime`).
> مصنّفة بوضوح: **[✓ كود]** = مؤكد من ملفات prime-agent، **[≈ استنتاج]** = مرجّح، **[مشروعنا]** = يحتاج بناءً في graph-based-agent-system.
> ملاحظة نقدية: مستودع Reference 5 (gemini) وصف prime-agent كـ "Python RL harness" من خياله — هذا **وهمي**؛ prime-agent منتج TypeScript RLM مبني على pi‑mono. أي مهمة هنا لا تفترض خلاف ما في الكود.

## Milestones (نقاط التسليم الكبرى)

- **M1 — فهم (Understanding)**: inventory + study + ADRs جاهزة. ✅ (تم: docs/prime-agent-study.md)
- **M2 — إعادة إنتاج (Replicate)**: نماذج أولية (prototypes) لـ 3 آليات (Harness، JSONL trace، A2A edges) تعمل في مشروعنا.
- **M3 — دمج (Integrate)**: الطبقات تدخل production تحت الـ Constitution الحالي (immutable) دون fork سلطة ثانية.

أولوية عامة: **P0** = أساسي قبل أي دمج · **P1** = قوي · **P2** = توسع · **P3** = تحسين.
حجم التقدير: **S** (<1ي) · **M** (1–3ي) · **L** (3–5ي) · **XL** (>5ي).

## E0 — Recon & Inventory (نصف يوم) ✅ جزئياً

- [x] **E0.1** clone فعلي + API metadata + تحديد اللغة/اللايسنس. **[✓ كود]** → `docs/repository-inventory.md`
- [x] **E0.2** استخراج شجرة الملفات + الحزم (agent/ai/coding-agent/tui/runtime). **[✓ كود]**
- [ ] **E0.3** جدول inventory لكل ملف ≥100 سطر في prime-agent مع وصف مسؤوليته. **[مشروعنا]** (مطلوب: `docs/repository-inventory.md` مكتمل)
  - AC: كل ملف core ظاهر بـ path + LOC + الوظيفة.
- [ ] **E0.4** خريطة الاعتماديات (npm workspaces + pi‑mono + zeromq + ipykernel + photon). **[✓ كود]**
  - AC: رسم Mermaid لـ dependency graph بين الحزم.

## E1 — Architecture Reverse-Engineering (2–3 يوم)

- [ ] **E1.1** مخطط C4 (Context/Container) يعكس الكود فعلياً. **[✓ كود: architecture.md]**
  - AC: المخطط يطابق `docs/architecture.md` flowchart (TUI → supervisor → worker → AgentSession → kernel/providers).
- [ ] **E1.2** sequence diagram لـ rollout واحد (prompt → stream → ipython tool → host_request → observation). **[✓ كود: rlm-runtime.md]**
  - AC: يوضح قنوات ZeroMQ (shell/iopub/control) ولماذا host‑reply على control لا shell.
- [ ] **E1.3** توثيق `agent-loop.ts` نقاط القرار (stop/steer/continue/before‑after‑tool). **[✓ كود: agent-loop.ts:307-461]**
  - AC: جدول بكل hook + متى يُستدعى + القيمة المرجعة.
- [ ] **E1.4** تحديد واجهات (interfaces) فعلية vs coupling. **[✓ كود: types.ts]**
  - AC: قائمة `AgentLoopConfig` hooks كـ "extensibility surface" لمشروعنا.

## E2 — Continual Harness (القرار الأهم) (3 يوم) 🔥 P0

> يقابل دستورنا + `distillation_ledger`/`systems_layer`. (انظر ADR‑0001)

- [ ] **E2.1** نمذجة `HarnessState` (prompt|memory|skill|subagent × local|global) كـ schema في مشروعنا. **[✓ كود: harness.py:18-122]**
  - AC: dataclass/pydantic يطابق `HarnessEntry` + `RefinementEvent`.
- [ ] **E2.2** تنفيذ CRUD + `save()`/`load()` مع **mtime sync من القرص** (لا تطميس كتابات متوازية). **[✓ كود: harness.py:186-196]**
  - AC: اختبار: عمليتان تكتبان نفس الملف لا تفقدان تعديلات بعض.
- [ ] **E2.3** واجهة `/refine` مبنية على أدلة (evidence) + snapshots للـ rollback. **[✓ كود: rlm-runtime.md:213]**
  - AC: `refine.run(instructions)` ينشئ `RefinementEvent` بـ `evidence`؛ `refine.rollback(id)` يرجع الحالة.
- [ ] **E2.4** حماية الحقول (None = احتفظ، قيمة صريحة = طغى). **[✓ كود: harness.py:366-398]**
  - AC: اختبار تحديث title فقط لا يمس reference/arguments.
- [ ] **E2.5** دمج harness كبطبقة **تكميلية** فوق `CONSTITUTION.md` (immutable)، لا بديل. **[مشروعنا]**
  - AC: تغيير في harness لا يعدّل CONSTITUTION.md؛ rollback مسجّل.

## E3 — Agent-to-Agent Communication (2 يوم) 🔥 P1

> يقابل `topology_assembler` / حواف الـ graph عندنا. (ADR‑0003)

- [ ] **E3.1** أنماط تسليم الرسائل: `auto | steer | follow_up`. **[✓ كود: long-running-agents.md:104-110]**
  - AC: enum + سلوك لكل وضع (steer = حقن في عمل نشط، follow_up = بعد انتهاء turn).
- [ ] **E3.2** سجل أبوي للـ subagents يبقى عبر compaction/restart. **[✓ كود: rlm.md:88-104]**
  - AC: schema `SubagentRegistry` بمسارات session + status.
- [ ] **E3.3** تطبيق أوضاع التسليم على حواف `topology_assembler` في مشروعنا. **[مشروعنا]**
  - AC: agent A يرسل لـ B بوضع `steer` ويُحقن في عمل B النشط.
- [ ] **E3.4** due‑tick claim قبل التسليم (لا إعادة تشغيل prompt عند crash). **[✓ كود: long-running-agents.md:170]**
  - AC: scheduled prompt يُطالَب قبل الإرسال؛ miss → coalesce.

## E4 — Session/Trace Tree Schema (2 يوم) 🔥 P1

> يقابل `distillation_ledger.jsonl` عندنا. (ADR‑0004)

- [ ] **E4.1** اعتماد JSONL tree (v3) بـ `id`/`parentId` + entries (compaction/branch_summary/label). **[✓ كود: session-format.md:1-40,327-353]**
  - AC: parser يبني الشجرة ويتجاهل bookkeeping entries عند بناء context.
- [ ] **E4.2** `buildSessionContext()` walk من leaf لـ root + إسقاط compaction. **[✓ كود: session-format.md:341-353]**
  - AC: اختبار يسترجع الـ messages الصحيحة عبر branch.
- [ ] **E4.3** تطبيق schema على `system/distillation_ledger.jsonl` (append‑only + replay). **[مشروعنا]**
  - AC: replay لـ session يُعيد نفس الـ context.
- [ ] **E4.4** Custom entries (لا تدخل context) vs CustomMessage (تدخل). **[✓ كود: session-format.md:257-288]**
  - AC: توثيق أي بيانات sage_council تبقى خارج context.

## E5 — Host-Request Bridge (2 يوم) 🔥 P1

> يفصل سطح تحكم النموذج عن الحالة الموثوقة (متوافق مع صلاحياتنا المعمارية).

- [ ] **E5.1** نمط `rlm.host_request(type, payload)` → host يصادق ويملك انتقال الحالة. **[✓ كود: rlm.md:135-139, rlm-runtime.md:32]**
  - AC: مهارة Python لا تعدّل state مباشرة؛ ترسل host_request فقط.
- [ ] **E5.2** تطبيق لنمط `sage_council` / `systems_layer` عندنا. **[مشروعنا]**
  - AC: council يستقبل طلبات عبر واجهة مكتوبة؛ القرار موثّق؛ لا تعديل دستور من النموذج.
- [ ] **E5.3** تحديد الـ "trusted surface" (مهارات = كود موثوق؛ تنفيذ كود غير موثوق = sandbox خارجي). **[✓ كود: rlm.md:141-143]**
  - AC: تحذير أمني في docs + فحص `tools/` قبل تنفيذ كود.

## E6 — Tool / ACI Strategy (3 يوم) ⚠️ P1 (لا ننسخ RLM)

- [ ] **E6.1** تحليل فلسفة "IPython‑كأداة‑شاملة" + نقطة ضعفها في فرض الصلاحيات. **[✓ كود: rlm.md:31-51]**
  - AC: وثيقة تقرر: نحتفظ بـ typed tools + MCP، لا نتبنى REPL.
- [ ] **E6.2** توصيف كل أداة بميتاداتا (name/description/schema/permissions/risk/timeout/network/fs). **[مشروعنا]** (انظر ADR‑0002)
  - AC: كل أداة في `tools/` تحمل metadata صريحة.
- [ ] **E6.3** MCP كطبقة أدوات معيارية (لا lock‑in بمزود). **[✓ كود: packages/ai/src/mcp/]**
  - AC: `tools/mcp_tools.py` يدعم server خارجي واحد على الأقل.
- [ ] **E6.4** before/after tool hooks (block/terminate/override) كـ extensibility. **[✓ كود: types.ts:257-277]**
  - AC: hook `beforeToolCall` يستطيع `block:true` للأدوات خارج الصلاحيات.

## E7 — Unified Model Provider (2 يوم) P1

- [ ] **E7.1** interface موحّد `ModelProvider` (generate(messages, tools, config) → response). **[مشروعنا]** (مستوحى من `packages/ai/src/stream.ts`)
  - AC: stub + تنفيذان (Stepfun الحالي + faux للاختبار).
- [ ] **E7.2** streaming موحّد + تطبيع الأحداث (text|tool_call|thinking|usage|stop). **[✓ كود: AGENTS.md:150-154]**
  - AC: كل المزوّدات تُصدر نفس شكل الحدث.
- [ ] **E7.3** token/cost accounting + cache pricing. **[✓ كود: packages/ai/src/cache-pricing.ts]**
  - AC: تقرير تكلفة لكل run.
- [ ] **E7.4** faux provider للاختبار بلا مفاتيح/تكلفة. **[✓ كود: AGENTS.md:32, packages/ai/src/providers/faux.ts]**
  - AC: suite اختبار كامل بلا مفاتيح حقيقية.

## E8 — Long-Running & Autonomous (2 يوم) P2

- [ ] **E8.1** goals دائمة (مكتملة فقط بـ `complete()`). **[✓ كود: long-running-agents.md:172-197]**
  - AC: goal يبقى عبر turns + token budget.
- [ ] **E8.2** autonomous mode محدود بـ (turns/tokens/wall‑clock) + quality gates. **[✓ كود: long-running-agents.md:199-227]**
  - AC: gate يفشل → يعود للوكيل بـ output محدود.
- [ ] **E8.3** heartbeats (user `/heartbeat` + agent `rlm_heartbeat`). **[✓ كود: long-running-agents.md:112-157**
  - AC: heartbeat واحد للمستخدم + multiple للوكيل.
- [ ] **E8.4** جدولة one‑time + cron مع persisted per session. **[✓ كود: long-running-agents.md:159-170**
  - AC: cron يعيش بعد انفصال الـ client.

## E9 — Context Engineering / Compaction (2 يوم) P1

- [ ] **E9.1** سياسة compaction تلقائي (يلخّص القديم، يبقي الحديث + حالة kernel). **[✓ كود: long-running-agents.md:228-239]**
  - AC: تراجع في استخدام الـ tokens مع بقاء المتغيرات الحديثة.
- [ ] **E9.2** `transformContext` hook للـ pruning/حقن قبل LLM. **[✓ كود: types.ts:150-170]**
  - AC: يتصل بطبقة الذاكرة العاملة عندنا.
- [ ] **E9.3** context budgeting + إنذار قرب الحد. **[مشروعنا]**
  - AC: قياس تكلفة الـ compaction بالتوكنات.

## E10 — Skill System (2 يوم) P2

- [ ] **E10.1** معيار Agent Skills + Python‑backed skills. **[✓ كود: skills.md:141-170]**
  - AC: مهارة markdown + حزمة Python تُثبّت في venv.
- [ ] **E10.2** progressive disclosure (وصف فقط في context، SKILL.md عند الحاجة). **[✓ كود: skills.md:130-139]**
  - AC: تقليل استهلاك context للوكلاء.
- [ ] **E10.3** `skill-creator` يقابل `distillation_ledger` (مهارة تولد من تكرار). **[✓ كود: skills.md:201-227]**
  - AC: عند تكرار نمط → اقتراح مهارة/entry.

## E11 — Security & Trust Boundary (2 يوم) 🔥 P0

- [ ] **E11.1** توثيق صريح: kernel **ليس sandbox**؛ عزل حقيقي للكود غير الموثوق. **[✓ كود: README.md:66, rlm-runtime.md:251]**
  - AC: تحذير في README + فحص قبل أي تنفيذ كود في `tools/`.
- [ ] **E11.2** صلاحيات READ/WRITE/NEVER/HUMAN_CHECKPOINT كطبقة **معمارية** (لا prompt‑jailbox). **[مشروعنا: CONSTITUTION.md:41-64]**
  - AC: أداة خارج صلاحياتها تُرفض في runtime قبل التنفيذ.
- [ ] **E11.3** منع prompt injection عبر UI (skill كود موثوق، لا نص عشوائي). **[✓ كود: skills.md:25, rlm.md:141-143]**
  - AC: فحص skills قبل التحميل.
- [ ] **E11.4** أسرار لا تُخزّن في state/traces. **[مشروعنا]**
  - AC: redaction قبل الكتابة في distillation_ledger.

## E12 — Roadmap & Decision Memo (1 يوم) P0

- [ ] **E12.1** كتابة `DECISIONS.md` بالتوصية النهائية (استلهام انتقائي). **[مشروعنا]**
  - AC: قرار موثّق بمبررات + رفض RLM/REPL.
- [ ] **E12.2** ROADMAP مرحلي M1→M3. **[مشروعنا]**
- [ ] **E12.3** صيانة attribution/license (MIT) عند أي اقتباس كود. **[✓ كود: LICENSE]**
  - AC: إشعار MIT محفوظ في أي ملف منقول.

## مصفوفة الأولوية السريعة

| Epic | الأولوية | الحجم | القرار |
|---|---|---|---|
| E2 Continual Harness | P0 | M | **نتبنّى** (يخدم الدستور) |
| E11 Security | P0 | M | **نتبنّى** (صلاحيات معمارية) |
| E12 Decision Memo | P0 | S | **نتبنّى** |
| E3 A2A edges | P1 | M | **نستلهم** |
| E4 Trace schema | P1 | M | **نستلهم** |
| E5 Host bridge | P1 | M | **نستلهم** |
| E6 Tool/ACI | P1 | L | **جزئي** (typed+MCP فقط) |
| E7 Model Provider | P1 | M | **نستلهم** |
| E9 Compaction | P1 | M | **نستلهم** |
| E1 Arch recon | — | L | **تم جزئياً** |
| E8 Long-running | P2 | M | **نستلهم لاحقاً** |
| E10 Skills | P2 | M | **نستلهم لاحقاً** |
| E0 Inventory | — | S | **تم جزئياً** |

> لا تبدأ نسخ أي كود من prime-agent قبل E12.3 (attribution) و E11 (security review).
