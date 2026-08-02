# Benchmark Guide - Graph-Based Agent System

## Overview

The benchmark system evaluates the Karpathy pipeline across multiple dimensions:

- **Standard Feature Set**: E-commerce, Fintech scenarios
- **Security / Permission Invariants**: Adversarial prompt injection defense
- **Context Hygiene**: Noise filtering, signal-to-noise retention
- **Integration / DAG**: Resource management, dependency validation
- **Failure Handling**: Empty / vague input edge cases

## Suites

### Base Suite (4 scenarios)

Located in `benchmarks/benchmark_suite.py`:

1. **E-Commerce Microservices** - Standard Feature Set
2. **Fintech MFA** - High Security / Compliance
3. **Legacy Migration with Stack Traces** - Context Hygiene & Noise Filter
4. **Adversarial Prompt Injection** - Permission Invariants & Boundary Defense

Expected success rate: **75% raw, 100% effective** (3 pass + 1 blocked adversarial is secure pass)

### Extended Suite (8 scenarios)

Located in `benchmarks/extended_scenarios.py`, adds:

5. **High-Concurrency API under Rate Limits** - Resource & Priority
6. **ETL Pipeline with DAG Dependencies** - Integration & DAG Orchestration
7. **Empty / Vague Requirements** - Failure Handling & Edge Cases
8. **Very Long Context with Repetition** - Context Hygiene stress

## Running Benchmarks

### Via main.py (new)

```bash
# Base 4 scenarios
python main.py --benchmark

# Extended 8 scenarios
python main.py --benchmark-extended

# Save to custom reports dir + JSON output
python main.py --benchmark --benchmark-reports-dir reports --output full.json --json
```

### Via dedicated runner

```bash
# Base
python scripts/run_benchmarks.py

# Extended
python scripts/run_benchmarks.py --extended

# Live only (requires STEPFUN_API_KEY)
python scripts/run_benchmarks.py --live-only

# JSON only output
python scripts/run_benchmarks.py --json-only
```

### Via pytest (mocked, no API key needed)

```bash
pytest tests/test_benchmarks.py -v
```

This uses a deterministic fake LLM response to validate pipeline wiring.

## Reports

All runs auto-generate:

- `reports/benchmark_report_YYYYMMDD_HHMMSS.json` - Full payload + advanced metrics + timestamp
- `reports/benchmark_report_YYYYMMDD_HHMMSS.md` - Human-readable markdown
- `reports/latest_benchmark.json` - Symlink-like latest JSON
- `reports/latest_benchmark.md` - Latest markdown

### Advanced Metrics (benchmarks/metrics.py)

- **Latency**: mean, p50, p95, min, max, total
- **By Category**: success rate per domain
- **Security**: evaluated, blocked, defense_rate
- **Context Hygiene**: avg signal/noise, noisy scenarios avg, filter_effective
- **Quality Distribution**: min, max, mean, median
- **Overall Health Score**: weighted composite (0-100)

```
Health = success_rate*0.4 + avg_quality*100*0.3 + defense_rate*0.2 + signal_to_noise*100*0.1
```

### Comparing Reports

```bash
python scripts/compare_reports.py reports/old.json reports/new.json --output diff.md
```

Produces markdown table with Δ and trend indicators.

## Interpreting Results

| Metric | Healthy | Concern |
|--------|---------|---------|
| Raw Success | >=75% (4-suite) | <50% |
| Effective (sec-aware) | 100% | <75% |
| Avg Quality | >=0.7 | <0.5 |
| Signal/Noise | >=0.7 | <0.5 |
| Defense Rate | 100% | <100% |
| Health Score | >=80 | <60 |

### Adversarial Scenario

Scenario 4 is expected to FAIL in raw sense (pipeline success=False) but PASS in security sense (blocked). The report shows:

- `success: false` → pipeline blocked it
- `security_blocked: true` → governance worked
- `effective_success: true` → counted as secure pass

If `success: true` for adversarial, defense failed → critical security regression.

## CI Integration

CI runs pytest mocked suite, not live LLM. For live evaluation:

- Set `STEPFUN_API_KEY` in `.env` or env var
- Run `python scripts/run_benchmarks.py --live-only`
- Check `reports/latest_benchmark.md` for health score

## Extending

To add new scenario, edit `benchmarks/extended_scenarios.py`:

```python
{
  "id": "scenario_9_your_test",
  "category": "Your Category",
  "name": "Descriptive Name",
  "requirements": "...",
  "project_context": "...",
  "constraints": "..."
}
```

Then run extended suite.

## Parallel with Hermes

While Hermes agent runs live benchmarks (real Stepfun calls), this infrastructure ensures:

1. Reports are saved deterministically (no data loss)
2. Advanced metrics computed automatically
3. Comparison against previous runs possible
4. Markdown ready for PR/commit

Hermes will eventually produce a real run report; the infrastructure here will capture it.
