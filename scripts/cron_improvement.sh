#!/usr/bin/env bash
# Autonomous Systems Layer cycle (in-graph meta-loop, v2+) + opus-5 live review + P7 report.
# Measurement + propose only. Per C1-rev1 the meta-loop DEFAULTS TO DENY: it never edits
# sibling-owned live paths; control proposals are recorded, not applied.
set -u
cd /home/fares/Projects/graph-based-agent-system || exit 1
source .venv/bin/activate
export PYTHONPATH=.

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] systems-layer cycle start (in-graph + opus-5 live)"
python scripts/run_systems_layer.py --opus5

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] P7 pruning report"
python system/self_pruning.py | python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('pruning_candidates=%d external=%d observed_effect=%s' % (
        len(d['pruning_candidates']), len(d['external_declared']), d['controls_with_observed_effect']))
except Exception as e:
    print('pruning report parse error:', e)
"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] cycle done"
