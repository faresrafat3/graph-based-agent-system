# خطة: توحيد المنهجيات + بناء الـ Systems Layer داخل الـ graph

> **للمستخدم:** دي خطة معمارية (architecture reconciliation) مش بس كود. الهدف: نجمع كل
> المنهجيات الشغّالة (Karpathy + opus-5 P1-P7 + Cynefin + reflexive loops + thrashing +
> verification + distributed governance)، نطلّع التضارب والمغالطات بينهم، ونحوّلهم
> **Systems Layer حقيقية جوه الـ LangGraph** (مش scripts بره) — بالاتحاد مع الـ 27 agent.
>
> السياق: كل اللي اتعمل لحد دلوقتي (الـ 27 agent + الـ loop + الـ governance + META-SYSTEM
> script) هو **إثبات مفهوم** على `step-3.7-flash` الضعيف. النظام "الحقيقي" اللي بيوفّق
> وبيقرر = (hy3 في دوره) + (opus-5 في دوره كـ pressure-advisor مقطّر). إحنا (أنا+opus-5)
> أقوى من الـ flash، فبنستخدم المنهج ده خارجياً لمراجعة وتوحيد، ونحط النتيجة جوه العظمه.

---

## 0. التحليل: التضارب والمغالطات (ناتج "النظام" hy3 + opus-5)

### تضارب (Contradictions)
- **C1** — "لا حاكم أعلى" (GOVERNANCE-SYSTEM) ⚡ META-SYSTEM بيقرر يحط/يشيل controls أوتوماتيك.
  الحل: الـ meta-loop يقترح (propose) بس، التطبيق (apply) لازم يكون عنده **human/checkpoint**
  أو يكون reversible-by-flag فقط (ده بيحافظ على "لا حاكم أعلى").
- **C2** — Law 7 (Simplicity/small core) ⚡ ULTIMATE-GRAPH-PLAN (22 agent).
  الحل: نضيف **معيار توفيق** صريح: نكبر agent بس لو P1 (Requisite Variety) محقق + P7 بيأكد
  إنه بيcatch failure؛ نصغّر لو P7 بيقول silent.
- **C3** — Law 11 (لا LLM في evaluate) ⚡ Reflexion/Debugger بيولّدوا LLM reflections.
  الحل: نحدد الحدود صراحة — الـ *verdict* (نعم/لا) zero-LLM دايماً؛ الـ *reflection* (تغذية
  الـ propose) مسموح LLM بس **مُوسَم كـ input مش كـ evaluation**. نوثّقها في CONSTITUTION.
- **C4** — P3 (Cynefin domain-gated) ⚡ `detect_task_type` بالكلمات المفتاحية.
  الحل: نستبدل الـ keyword router بـ **Cynefin classifier** حقيقي (domain + reversibility)
  — ده الـ node اللي هيحقق P3 فعلياً جوه الـ graph.
- **C5** — ادعاء "distillation من opus-5" من غير channel مُوثَّق.
  الحل: نعمل **distillation ledger** (ملف) بيسجّل كل مبدأ + مصدره من opus-5 + تاريخه +
  إن كان فعلاً مقطّر مش مجرد نص — عشان P1-P7 يكونوا auditable.

### مغالطات (Fallacies)
- **F1** — "27 agent = تغطية شاملة". الحقيقة: 9 مش reachable (vanity metric). القوة =
  reachable+observed-effect مش العدد.
- **F2** — "الـ loop/reflexion بيحسّن النتائج". على flash: مقريبش الـ resolve rate (1/8=1/8).
  الـ systems دي بتحسّن **الموثوقية/الحوكمة** مش الـ resolve — لازم نفصل الاتنين في القياس.
- **F3** — "الـ script = النظام بيتحسّن بنفسه". script بره = observer. عشان حقيقي لازم
  **nodes جوه الـ StateGraph** (زي ما المستخدم طلب: "جوه العظمه").

---

## 1. Goals (الأهداف الكبيرة)

- **G1 — Reconcile:** توحيد المنهجيات الخمسة في وثيقة واحدة (CONSTITUTION موسّع) من غير تضارب.
- **G2 — Embed:** تحويل الـ META-SYSTEM (measure/compare/propose/distill/gate) لـ **nodes حقيقية**
  جوه الـ LangGraph StateGraph (Systems Layer) — مش script.
- **G3 — Cynefin-route:** استبدال الـ keyword router بـ Cynefin classifier حقيقي (يحقق P3).
- **G4 — Distillation ledger:** ملف بيسجّل كل مبدأ + مصدره من opus-5 + إن كان مقطّر صح.
- **G5 — Observe-then-act:** الـ Systems Layer يقترح بس، والتطبيق reversible/checkpointed (يحل C1).
- **G6 — Honest metrics:** فصل "governance improvement" عن "resolve-rate improvement" في القياس (يحل F2).

---

## 2. Tasks (بالترتيب، مع TDD)

### Task A — Reconciliation doc (G1, C1-C5, F1-F3)
- اكتب `docs/METHODOLOGY-RECONCILIATION.md`: جدول المنهجيات + التضارب + القرار لكل تضارب.
- تحدّث CONSTITUTION Article VI عشان تحل C1/C2/C3 صراحة (تضيف "meta-loop proposes, human/flag applies").
- **Test:** `test_reconciliation_doc.py` — يتأكد إن كل تضارب له قرار موثّق.

### Task B — Systems Layer nodes داخل الـ graph (G2, F3)
- اكتب `agents/systems_layer.py`: StateGraph فيه nodes: `measure`, `compare`, `propose`,
  `distill`, `gate`, `record`. يقرأ state من الـ domain layer (breaches/success/thrash)،
  يكتب `control_proposals` في state.
- يربط بـ `agent_registry.py` (يبقى agent من الدرجة الأولى).
- **Test:** `test_systems_layer.py` — يعمل cycle كامل في-memory، يتأكد إن nodes بتتصل
  وبتكتب proposals من غير ما تعدّل live agents.

### Task C — Cynefin classifier node (G3, C4)
- اكتب `agents/cynefin_classifier.py`: بياخد requirements + reversibility → {Clear,
  Complicated, Complex, Chaotic} → control intensity.
- يستبدل `detect_task_type` في الـ routing (يحترم P3).
- **Test:** `test_cynefin_classifier.py` — يتأكد إن input معيّن بيرجّع domain صح.

### Task D — Distillation ledger (G4, C5)
- اكتب `system/distillation_ledger.py` + `docs/DISTILLATION-LEDGER.md`: بيسجّل كل مبدأ
  (P1-P7 + أي إضافة) + مصدره من opus-5 + تاريخ + حالة (proposed/distilled/enforced).
- يربط بـ `distill_opus5` في self_improvement.
- **Test:** `test_distillation_ledger.py` — يتأكد إن مبدأ من غير مصدر مرفوض.

### Task E — Apply-with-checkpoint (G5, C1)
- في `systems_layer`, الـ `gate` node بيطلّع `accepted` بس التطبيق لازم يكون:
  (أ) reversible flag، أو (ب) human checkpoint. نضيف `apply_or_escalate` node.
- **Test:** `test_apply_checkpoint.py` — يتأكد إن control مش-reversible بيتصعّد لـ human مش يتطبق.

### Task F — Honest metric split (G6, F2)
- في `self_improvement.Measurement` نضيف `governance_score` منفصل عن `success_rate`.
- الـ benchmark suite يطلع الاتنين.
- **Test:** `test_metric_split.py` — يتأكد إن governance_score و success_rate مستقلين.

---

## 3. Notes
- كل ده بيتبني **بالتدريج**، على flash كـ إثبات، والمراجعة بتتم **أنا+opus-5 بالنظام**.
- السيشن التانية لسه ممكن تلمس debugger/reflexion — بنبني nodes جديدة (systems_layer،
  cynefin_classifier) من غير ما نلمس ملفاتهم.
- الـ cron (gbas-improvement-cycle) يفضل شغال ويقيس؛ لما الـ Systems Layer يخلص هنربطه بيها.

---

## 4. التنفيذ (يتم تعبئته أثناء العمل)
- [ ] Task A: Reconciliation doc + CONSTITUTION update
- [ ] Task B: systems_layer.py nodes inside graph
- [ ] Task C: cynefin_classifier.py
- [ ] Task D: distillation_ledger.py
- [ ] Task E: apply_or_escalate node
- [ ] Task F: metric split
