# Prime Agent — دراسة هندسية (Facts‑First) لمشروعنا

> الوثيقة مبنية على **clone فعلي** للمستودع في `/tmp/prime-agent` (فرع `main`، آخر push 2026‑08‑06، إصدار `0.7.0`)،
> ومصنّفة بوضوح بين: **[✓ كود]** = مؤكد من الملفات، **[≈ استنتاج]** = مرجّح من السياق، **[؟]** = يحتاج تحققاً إضافياً.
> مهم: مستودع Prime Intellect `prime-agent` **ليس** Python RL harness — هو **منتج TypeScript RLM agent** مبني على `pi-mono`. أي تحليل يصفه كـ Python/RL‑training harness هو وهمي ولا يمت للكود بصلة.

---

## 0. خلاصة الحالة (حالة الجلب)

- الرابط الأصلي `@url:...prime-agent.git` فشل في الاستخراج 5 مرات؛ تم التعافي بـ `git clone` فعلي.
- اللغة: **TypeScript** (monorepo، `npm workspaces`) + حزمة Python صغيرة `prime-agent-runtime` (فقط طبقة `rlm` shim + harness state).
- الترخيص: **MIT** (Copyright Mario Zechner 2025 + Prime Intellect 2026) — يسمح بالاقتباس/التعديل مع إبقاء الإشعار. [✓ code: LICENSE]
- النجوم: ~2539. مبني على `pi` (pi‑mono) لـ Mario Zechner (badlogic) — مؤلف libGDX. [✓ code: README.md:104, package.json]

---

## 1. الهوية والغرض (ما المشكلة اللي بيحلها)

Prime Agent = **وكيل ترميز وبحث ذاتي التحسين** للأعمال الطويلة والمستقلة. [✓ code: README.md:31, package.json description]

التجريدان الأساسيان (من README):
1. **RLM — Recursive Language Model**: "السياق متغيرات (prompt‑as‑a‑variable)، والأدوات كـ recursive subagents تُستدعى كـ function calls داخل REPL IPython ثابت". [✓ code: README.md:33]
2. **Continual Harness**: يخزّن prompts إضافية وmemories ووصف skills وspecs لـ subagents كحالة دائمة، ويحسّنها عبر تحديثات صغيرة مبنية على أدلة (evidence‑backed) محلية للجلسة افتراضياً. [✓ code: README.md:34]

> الفرق الفلسفي الجوهري عن مشروعنا: prime‑agent منتج **وكيل واحد** (جذر + أبناء متكررون)؛ مشروعنا إطار **حوكمة/تنسيق graph/DAG** لوكلاء bespoke مُحكمين. نقترض *آليات*، لا *شكل المنتج*.

---

## 2. المعمارية (مخطط المكوّنات — من الكود)

الحزم (npm workspaces) [✓ code: root package.json, find packages/]:

| الحزمة | المسؤولية | ملفات جوهرية |
|---|---|---|
| `packages/agent` | نواة حلقة الوكيل + transport abstraction + state | `src/agent-loop.ts` (986 سطر)، `src/agent.ts` (613)، `src/types.ts` |
| `packages/ai` | تجريد مزوّدات النموذج + streaming + MCP | `src/stream.ts`, `src/providers/*` (anthropic, openai-*, google, bedrock, mistral…), `src/mcp/` |
| `packages/coding-agent` | CLI + TUI + أدوات IPython + session manager + daemon | `src/core/`, `src/cli/`, `src/modes/`, `docs/` |
| `packages/tui` | واجهة المستخدم الطرفية | `src/` |
| `prime-agent-runtime` | طبقة Python: `rlm` shim + harness state + Python skills | `src/rlm/harness.py`, `skill.py`, `mcp_base.py` |

تدفق التنفيذ (من `docs/architecture.md` — مخطط Mermaid مؤكد) [✓ code: packages/coding-agent/docs/architecture.md]:

```
Interactive TUI / Headless clients (Print·JSON·RPC)
        │ local daemon protocol
        ▼
Daemon supervisor  (routing · attachments · recovery · cross-agent messages)
        ▼
Session worker (يOwn جذر واحد: AgentSessionRuntime + Scheduler + Kernel + Children)
        ▼
Root AgentSession → IPython kernel (model-facing control env) + RLM child runtimes
        │
        ▼
Model providers  (streaming)   +   Session JSONL + artifacts (persistence)
```

قاعدة صريحة من الكود: **Workers و Kernels عمليات منفصلة لـ lifecycle/failure containment، مش sandbox أمني**. [✓ code: README.md:66, architecture.md:49, rlm-runtime.md:251]

### 2.1 حلقة الوكيل الفعلية (`agent-loop.ts`)

الحلقة الحقيقية (مقروءة سطراً بسطر) [✓ code: packages/agent/src/agent-loop.ts:307‑461]:
- **حلقة خارجية** (`while true`) تعالج follow‑up و continuation messages.
- **حلقة داخلية** تعالج tool calls + steering messages.
- نقاط قرار قابلة للحقن عبر `AgentLoopConfig` [✓ code: packages/agent/src/types.ts:119‑278]:
  - `convertToLlm` (AgentMessage[] → Message[]) عند حدود استدعاء LLM.
  - `transformContext` (قبل التحويل — pruning/حقن).
  - `shouldStopAfterTurn` / `shouldStopBeforeTurn` (توقف متدرج).
  - `getSteeringMessages` (حقن توجيه أثناء العمل).
  - `getFollowUpMessages` / `getContinuationMessages` (استمرار مضيف).
  - `beforeToolCall` (يستطيع `block:true`) / `afterToolCall` (يتجاوز المحتوى/isError/terminate).
  - `toolExecution: "sequential" | "parallel"`.
- معالجة إجهاض كاملة عبر `AbortSignal` (raceWithAbort) [✓ code: agent-loop.ts:42‑104].
- الحدث (EventStream) يبث `agent_start/turn_start/message_*/tool_execution_*/agent_end` [✓ code: types.ts:406‑421].

> درس لمشروعنا: فصل "نقاط القرار" (stop/steer/continue/before‑after‑tool) في config واحد = قابلية تكوين عالية دون لمس الحلقة. نمط نرشّحه لطبقة الـ orchestration عندنا.

---

## 3. طبقة الأدوات وواجهة ACI (Agent–Computer Interface)

الفلسفة: **"كل شيء برمجي"** — IPython الثابت هو الأداة المدمجة الوحيدة؛ القراءة/التعديل/الشل/الأدوات/subagents كلها عبر كود Python. [✓ code: README.md:38, rlm.md:31‑51]

- `ipython` tool = نواة IPython ثابتة؛ متغيرات/imports/دوال/حالة تبقى عبر الـ turns والـ compaction. [✓ code: rlm.md:35]
- `rlm(...)` قابل للاستدعاء مسبق التحميل في الـ kernel: يولّد child session مستقلة ويرجع handle فور القبول (لا ينتظر النتيجة). [✓ code: rlm.md:53‑71, rlm-runtime.md:23‑30]
- أدوات النظام: `%%bash` cells، ملفات، أوامر المشروع — كلها من الـ kernel.
- **MCP مدعوم** كطبقة أدوات معيارية (`packages/ai/src/mcp/`) [✓ code: packages/ai/src/mcp/index.ts].

> contrast مع مشروعنا: نحن نفضّل **typed tools + MCP** لأسباب حوكمية (حدود صلاحيات READ/WRITE/NEVER/HUMAN_CHECKPOINT معمارية، لا prompt). الـ IPython‑كأداة‑شاملة أضعف في فرض الصلاحيات؛ لكن "context‑as‑variables" فكرة نقترضها لطبقة الذاكرة العاملة.

---

## 4. إدارة السياق والذاكرة (Context Engineering)

- **Compaction تلقائي**: يلخّص الرسائل القديمة ويبقي الحديثة + حالة kernel؛ ليس إشارة إنهاء (لا يوقف goals/autonomous/heartbeats/children). [✓ code: long-running-agents.md:228‑239, session-format.md:233‑239]
- **Harness state** (انظر §5) = الذاكرة الدائمة القابلة للتطوير.
- **Subagent registry** أبوي يبقى عبر compaction/restart/restore. [✓ code: rlm.md:88‑104]
- صيغة الجلسة: **JSONL tree** (v3) بـ `id`/`parentId`، تفرّع موضعي (in‑place branching)، compaction/branch_summary entries. [✓ code: session-format.md:1‑40, 327‑353]

> نقترض صيغة الـ JSONL tree + entries (compaction/branch/label) كـ schema لتسجيلنا (distillation_ledger / traces) بدل إعادة اختراعها.

---

## 5. Continual Harness — أهم مكوّن للاقتباس لمشروعنا

`rlm/harness.py` = متجر CRUD لحالة harness مُراجَعة‑بلا‑reset. [✓ code: prime-agent-runtime/src/rlm/harness.py]

أنواع الإدخالات (`HarnessKind`): `prompt | memory | skill | subagent`. مع نطاق `local | global`. [✓ code: harness.py:18‑19]

`HarnessEntry` (dataclass) يحوي: id, kind, title, content, path, scope, reference, arguments, metadata, source, created_at, updated_at, version. [✓ code: harness.py:93‑109]

`RefinementEvent`: id, trigger, changes[], evidence, outcome. [✓ code: harness.py:112‑122]

سلوك هندسي دقيق يستحق النقل:
- **مزامنة mtime من القرص** (`_sync_from_disk`) لئلا يطمس كتابة `/refine` من الـ host كتابة kernel العالقة. [✓ code: harness.py:186‑196]
- **in_memory fallback** عند فشل حل المسار (لا يرمي ثانية). [✓ code: harness.py:152‑155]
- **تسامح مع ملف فاسد**: `load()` يلتقط OSError/ValueError ويعامله فارغاً. [✓ code: harness.py:203‑214]
- **حماية الحقول**: التحديث يحفظ path/reference/arguments عند حذفها (None)؛ قيمة صريحة (حتى `{}`) تطغى. [✓ code: harness.py:366‑398]
- النظام الأساسي **immutable**؛ الـ `/refine` يطبّق تحديثات تكميلية صغيرة فقط مع snapshots للـ rollback. [✓ code: rlm-runtime.md:213]

> **هذا هو المحور الحقيقي للاستفادة**: مشروعنا عنده `CONSTITUTION.md` (immutable base) + `systems_layer`/`sage_council` + `distillation_ledger`. نمط Continual Harness = بالضبط الآلية اللي نحتاجها لإضافة "طبقة تكميلية قابلة للمراجعة والتطوير بالأدلة" فوق الدستور، مع rollback. (يتوافق مع توجيه Fares: "EXTEND existing governance، لا fork سلطة ثانية".)

---

## 6. Skills (قابلة للتنفيذ)

- ينفّذ معيار **Agent Skills** + امتداد **Python‑backed skills** (حزمة Python تُثبّت في kernel venv). [✓ code: skills.md:7, 141‑170]
- مدمجة: `prime-intellect`, `skill-creator`, `websearch`. [✓ code: skills.md:49‑53]
- اكتشاف تدريجي (progressive disclosure): الأوصاف فقط في الـ context، الـ SKILL.md الكامل يُحمّل عند الحاجة. [✓ code: skills.md:130‑139]
- `SKILL.md` بـ frontmatter (name/description/license/allowed-tools…). [✓ code: skills.md:297‑318]

> يقابلها عندنا: وكلاءنا bespoke = "skills قابلة للتنفيذ" بصلاحيات معماريّة. نمط `skill-creator` (يولّد مهارة من تكرار) يكافئ فكرة `distillation_ledger` عندنا.

---

## 7. العزل والأمان (Trust Boundary)

- **تحذير صريح ومتكرر**: IPython ينفّذ Python المولّد من النموذج بصلاحيات OS الخاصة بـ worker — **ليس sandbox أمني**. استخدم sandbox خارجي للكود غير الموثوق. [✓ code: README.md:65‑66, rlm.md:141‑143, rlm-runtime.md:249‑252]
- بيانات الاعتماد يحلّها TypeScript host؛ كتالوج النموذج يعبر لـ Python كـ metadata فقط. [✓ code: rlm-runtime.md:253]
- **نمط host‑request bridge**: مهارات Python تطلب عبر `rlm.host_request(...)`؛ الـ host يصادق ويملك انتقال الحالة (goal/agent_message/rlm_heartbeat). [✓ code: rlm.md:135‑139, rlm-runtime.md:32]

> **توافق عميق مع مشروعنا**: حدود الصلاحيات عندنا (READ/WRITE/NEVER/HUMAN_CHECKPOINT) هي *طبقة معمارية* لا prompt‑jailbox — نفس روح "الـ host يملك الحالة والسياسات، والنموذج يطلب عبر واجهة مكتوبة". نحافظ عليها ونوسّعها، لا نستعير نواة IPython.

---

## 8. طبقة النموذج (Model Layer)

- `packages/ai` يجرّد المزوّدات: Anthropic, OpenAI (completions + responses), Google (gemini + vertex), Azure, Bedrock, Mistral, Cloudflare, GitHub Copilot, Codex، و faux (للاختبار). [✓ code: packages/ai/src/providers/, AGENTS.md:135‑186]
- streaming موحّد، تطبيع الأحداث (`text|tool_call|thinking|usage|stop`)، tokens/cost accounting، cache pricing. [✓ code: packages/ai/src/stream.ts, cache-pricing.ts]
- **توليد النماذج من script** (`generate-models.ts`) لا تعديل يدوي للملف المولّد. [✓ code: AGENTS.md:21, 163‑173]

> نحتاج interface موحّد مشابه (`ModelProvider`) عبر `llm/` عندنا، بعيداً عن ربط مزوّد واحد.

---

## 9. التشغيل الطويل والمستقل (Long‑Running)

- **Daemon‑backed sessions**: العامل يملك الـ queue/schedules/kernel/descendants بعد انفصال الـ client. [✓ code: long-running-agents.md:45‑67]
- **Agent‑to‑agent**: `agent_message.send(...)` بأوضاع `auto | steer | follow_up`؛ `rlm.list_subagents()`. [✓ code: long-running-agents.md:71‑110, rlm.md:78‑86]
- **Heartbeats**: `/heartbeat` (مستخدم) + `rlm_heartbeat` (وكيل، متعدد). [✓ code: long-running-agents.md:112‑157]
- **Schedules**: one‑time + cron، persisted per session، due‑ticks تُطالَب قبل التسليم (لا إعادة تشغيل). [✓ code: long-running-agents.md:159‑170]
- **Goals**: هدف دائم يستمر عبر الـ turns حتى `complete()`. [✓ code: long-running-agents.md:172‑197]
- **Autonomous mode**: bounded بحدود (turns/tokens/wall‑clock) + quality gates اختيارية. [✓ code: long-running-agents.md:199‑227]

> يقابلها عندنا: `agents/` mode + persistent goals + `sage_council`. نقترض أوضاع التسليم `auto/steer/follow_up` ونمط "due‑tick claim" لتجنّب تكرار الـ prompts.

---

## 10. التقييم والجودة الهندسية

- CI + build‑binaries workflows. [✓ code: README.md:22‑27]
- قواعد تطوير صارمة (AGENTS.md): `npm run check` (biome + tsgo) قبل الـ commit، لا `npm run dev/build/test` عشوائي، اختبار عبر `faux` provider بلا مفاتيح حقيقية، regressions تحت `test/suite/regressions/`. [✓ code: AGENTS.md:23‑33]
- **تزامن إصدارات lockstep** (كل الحزم بنفس الرقم). [✓ code: AGENTS.md:188‑207]
- قواعد git for parallel agents (لا `git add -A`، لا `reset --hard`). [✓ code: AGENTS.md:209‑259]

> انضباط هندسي مرجعي. نحن نملك Makefile + pytest؛ نقترض "faux provider" pattern و regression‑first testing.

---

## 11. الأدبيات والفلسفة (مرتبطة بالكود فعلاً)

| المكوّن | المرجع الفكري (مؤكد من الكود) | الصلة |
|---|---|---|
| RLM (context‑as‑variables + subagents كـ function calls) | مدونة RLM الخاصة بهم [✓ code: README.md:33 → primeintellect.ai/blog/rlm] | "السياق متغيرات" = قلب فلسفة CodeAct |
| Continual Harness | ورقة Continual Harness [✓ code: README.md:34 → arxiv 2605.09998] | تحسين مبني على أدلة + rollback |
| Agent Skills | معيار Agent Skills [✓ code: skills.md:7 → agentskills.io] | progressive disclosure |
| MCP | Model Context Protocol [✓ code: packages/ai/src/mcp/] | أدوات معيارية بلا lock‑in |
| `pi` / pi‑mono | Mario Zechner (badlogic) [✓ code: README.md:104] | أساس الـ TUI/agent |
| IPython‑as‑tool | CodeAct (Yang et al. 2023) [≈ استنتاج] | الكود كواجهة فعل لا JSON |
| Subagent recursion | OpenAI Swarm / parallel tool calls [≈ استنتاج] | تفويض كـ function call |
| Skill evolution | Voyager (Minecraft skill library) [≈ استنتاج] | مهارة تتولّد من تكرار |
| Refinement | Reflexion [≈ استنتاج] | مراجعة trajectory + تحديث |

**الفلسفة الحاكمة المستخلصة من الكود** [✓ code: README.md:31‑44]:
- الذكاء = برنامج يعيش في بيئة تحكم ثابتة (IPython)، لا مجرد نص.
- السياق والأنماط القابلة لإعادة الاستخدام **تبقى بعد نافذة الشات** (durable state).
- الحوكمة = تحديثات تكميلية صغيرة مبنية على أدلة فوق base immutable، مع rollback — لا إعادة كتابة الـ system prompt.

**البُعد النقدي (Bitter Lesson vs السقالات)**: هل سقالاتهم (RLM/Harness) استثمار طويل الأمد أم عرضة للإهمال عند تغيّر النماذج؟ مشروعنا يتبنى نهج Fares: "ارفض model‑swap لسقف القدرة — فكّك إلى graph وكلاء متخصصين بـ feedback edges". نرى Continual Harness كـ *طبقة حوكمة* لا كـ prompt‑engineering، فتبقى قيمتها عبر أجيال النماذج.

---

## 12. مصفوفة "ناخد / نستلهم / نتجنب" (لمشروعنا)

| المكوّن | الحكم | السبب | الإجراء |
|---|---|---|---|
| Continual Harness (harness_state.json + /refine) | **نستلهم + نتبنّى** | يقابل الدستور+distillation_ledger عندنا بدقة | أنشئ `system/harness_state.json` + واجهة refine مبنية على أدلة (Epic 2) |
| Agent‑to‑agent (auto/steer/follow_up) | **نستلهم** | يحسّن حواف الـ graph عندنا | أضف أوضاع تسليم لحواف `topology_assembler` (Epic 3) |
| Session JSONL tree (id/parentId + entries) | **نستلهم** | schema جاهز لتسجيلنا | طبّق لنقاط `distillation_ledger` (Epic 4) |
| Host‑request bridge (Python↔TS owns state) | **نستلهم** | يفصل سطح تحكم النموذج عن الحالة الموثوقة | طبّق لنمط `sage_council`/systems_layer (Epic 5) |
| RLM / REPL execution | ندرس، **لا ننسخ** | مختلف عن paradigm الـ graph/DAG عندنا | ابقَ typed tools + MCP (Epic 6) |
| IPython‑كأداة‑شاملة | **نتجنب** | أضعف في فرض الصلاحيات المعمارية | نحافظ على READ/WRITE/NEVER كطبقة معمارية |
| Kernel‑as‑sandbox assumption | **نتجنب** (تحذيرهم) | ليس sandbox؛ نحتاج عزل حقيقي للكود غير الموثوق | sandbox خارجي عند تنفيذ كود في `tools/` |
| Unified ModelProvider interface | **نستلهم** | فك الارتباط بمزوّد | وسّع `llm/` (Epic 7) |
| Faux provider + regression tests | **نستلهم** | اختبار بلا مفاتيح/تكلفة | أضف لمشروعنا (Epic 8) |

---

## 13. مخاطر التبنّي

- **Paradigm mismatch**: prime‑agent = وكيل واحد REPL؛ مشروعنا = graph مُحكم. لا تنسخ شكل المنتج. [✓ code: README.md:31]
- **النضج/API churn**: إصدار `0.7.0`، واجهات قد تتغير؛ أخذ أفكار أأمن من أخذ كود. [✓ code: package.json]
- **Lock‑in على pi‑mono**: الـ TUI/agent مبني على `pi`؛ لو اقتبسنا كود TS نرتبط به. (نحن Python — الاقتباس مفاهيمي فقط.) [✓ code: README.md:104]
- **أمان**: kernel ليس sandbox؛ أي تنفيذ كود غير موثوق عندنا يجب في عزل حقيقي. [✓ code: rlm-runtime.md:251]

---

## 14. القرار النهائي (Recommendation)

**استلهام انتقائي (selective adoption)، لا تبنٍّ كامل ولا رفض.**
القيمة الأعلى لمشروعنا مركّزة في 3 آليات قابلة للنقل لمعماريتنا (Python/LangGraph + حوكمة):
1. **Continual Harness** كطبقة حوكمة تكميلية فوق الدستور (مع rollback) — يخدم توجيه "EXTEND existing governance".
2. **Host‑request bridge + typed edges** لأوثق تواصل الوكلاء (sage_council / graph edges).
3. **Session/trace tree schema** لمسجّلنا (distillation_ledger) بصيغة قابلة لإعادة التشغيل.

نبتعد عن: RLM/REPL paradigm، IPython‑كأداة‑شاملة، وافتراض أن kernel = sandbox.

> التفصيل التنفيذي في `TODO.md` (Epics E0–E12) و`docs/adr/` (ADR‑0001..0004).
