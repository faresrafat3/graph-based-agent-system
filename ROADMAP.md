# ROADMAP — من فهم Prime Agent إلى دمج في مشروعنا

> مراحل M1→M3 مبنية على الاستيعاب الفعلي (clone في `/tmp/prime-agent`). كل مرحلة لها خرج قابل للتحقق.

## M1 — فهم (Understanding) ✅ منجز أساساً

**الهدف**: خريطة حقيقية لـ prime-agent + قرارات استيعاب.
- [x] clone + inventory (docs/repository-inventory.md)
- [x] دراسة معمارية (docs/prime-agent-study.md)
- [x] ADRs (docs/adr/0001‑0004)
- [x] TODO Epics (TODO.md)
- [ ] **متبقي**: E0.3 (inventory كامل بكل ملف ≥100 سطر) + E0.4 (dependency graph)
- **خرج**: المستندات أعلاه + قرار "استلهام انتقائي" (DECISIONS.md)

## M2 — إعادة إنتاج (Replicate) — نماذج أولية

**الهدف**: 3 آليات تعمل في مشروعنا كـ prototypes مستقلة.

| Proto | Epic | المخرج | تحقق |
|---|---|---|---|
| Harness محلي | E2 | `system/harness_state.json` + `refine` CLI | اختبار mtime sync + rollback |
| Trace schema | E4 | محوّل `distillation_ledger.jsonl` → JSONL tree v3 | اختبار replay/branch |
| A2A edges | E3 | أوضاع `auto/steer/follow_up` على `topology_assembler` | اختبار حقن `steer` |

- **الأولوية**: P0 (E2 + E11 security + E12) أولاً، ثم P1.
- **لا يبدأ نسخ كود** قبل E11 (security review) + E12.3 (attribution).

## M3 — دمج (Integrate) — إنتاج تحت الدستور

**الهدف**: الطبقات تدخل التشغيل تحت `CONSTITUTION.md` (immutable) دون fork سلطة ثانية.

- [ ] Harness كبطبقة تكميلية مفعّلة في `main.py` pipeline.
- [ ] Trace schema هو المسجّل الرسمي (يحل محل أي صيغة عشوائية).
- [ ] Host‑request bridge لـ `sage_council` / `systems_layer`.
- [ ] Typed tools + MCP registry مع metadata صريحة + before/after hooks.
- [ ] Unified ModelProvider + faux provider في pytest.
- [ ] Security gate: عزل حقيقي للكود غير الموثوق + فحص صلاحيات معمارية.

## جدول زمني تقريبي (بافتراضات معلنة)

| المرحلة | المدة | التبعية |
|---|---|---|
| M1 (متبقي) | 0.5 يوم | — |
| M2 Prototypes | 1.5–2 أسبوع | E0, E1 |
| M3 Integration | 2–3 أسبوع | M2 + E11 + E12 |

## مؤشرات النجاح (Success Metrics)

- هل الطبقة الجديدة **لا تعدّل** `CONSTITUTION.md`؟ (حوكمة)
- هل `refine` ينتج `evidence` إلزامي + rollback مسجّل؟ (قابلية تطوير بالأدلة)
- هل replay لـ session يعيد نفس الـ context؟ (تتبع)
- هل أداة خارج صلاحياتها تُرفض قبل التنفيذ؟ (أمان)
- هل pytest يمرّ بلا مفاتيح/تكلفة حقيقية؟ (faux provider)

## مخاطر الطريق (Road Risks)

- **Paradigm mismatch**: prime-agent = وكيل REPL؛ نحن graph. → لا تنسخ شكل المنتج.
- **API churn**: v0.7.0. → أخذ أفكار لا كود.
- **Security**: kernel ليس sandbox. → عزل حقيقي قبل أي تنفيذ كود.
- **Lock‑in**: pi‑mono. → اقتباس مفاهيمي (نحن Python).
