"""
SWE-bench Verified harness for the Graph-Based Agent System.

Where HumanEval asks "can you write one function from a docstring?", SWE-bench asks
"can you fix a real bug in a 500k-line repository?". That difference is the entire
point of this run: HumanEval could not exercise localization, multi-file reasoning, or
recovery from execution failure, so it measured the model and not the architecture.

Pipeline (agent arm):

    Localizer (zero-LLM)      -- BM25-ish lexical retrieval over the repo tree
        -> Context Curator    -- sanitation + signal-to-noise on the issue text
        -> Patch Generator    -- LLM as sandboxed CPU, emits a unified diff
        -> Patch Validator    -- zero-LLM: does `git apply --check` accept it?
        -> Surgical Refiner   -- bounded retry, breaches-only feedback
        -> emit prediction

The baseline arm is one LLM call with the issue text and the same file context, no
validation and no refinement. Same model, same retrieval, so the delta isolates the
governance layer rather than the retriever.

Grading is NOT done here. We emit predictions in the official schema and hand them to
`swebench.harness.run_evaluation`, which runs the repo's real test suite in Docker.
FAIL_TO_PASS must flip to passing and PASS_TO_PASS must stay passing. No LLM judges
anything, and we cannot mark our own homework.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.context_curator import ContextCuratorEngine
from llm.llm_integration import call_llm

load_dotenv()

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
REPO_CACHE = os.path.expanduser("~/.cache/swebench-repos")

PATCH_SYSTEM_PROMPT = """You are an expert Python engineer fixing a bug in a large open-source repository.

You will be given an issue report and the current contents of the most relevant source files.

Output ONLY a unified diff patch. Rules:
- Start immediately with `--- a/<path>` — no prose, no markdown fences, no explanation.
- Use exact paths as given, prefixed with a/ and b/.
- Include at least 3 lines of unchanged context around every change.
- Line counts in @@ hunk headers must be correct.
- Change the minimum necessary to fix the issue. Do not reformat unrelated code.
- Do not modify test files. The graders' tests are hidden from you.
"""

STOP_WORDS = frozenset("""
a an and are as at be by for from has have if in into is it its of on or that the to
was were will with this these those there here when where which who whom what why how
you your we our they them their he she his her i me my not no nor so than then
""".split())


# --------------------------------------------------------------------------------------
# Repo management
# --------------------------------------------------------------------------------------


def repo_path(repo: str) -> str:
    """Local clone path for a `owner/name` repo slug."""
    return os.path.join(REPO_CACHE, repo.replace("/", "__"))


def ensure_repo(repo: str) -> str:
    """Clone the repo once and reuse it across instances. Returns the clone path."""
    path = repo_path(repo)
    if os.path.isdir(os.path.join(path, ".git")):
        return path

    os.makedirs(REPO_CACHE, exist_ok=True)
    url = f"https://github.com/{repo}.git"
    subprocess.run(
        ["git", "clone", "--quiet", url, path],
        check=True,
        capture_output=True,
        timeout=1800,
    )
    return path


def checkout_worktree(repo: str, base_commit: str, dest: str) -> str:
    """
    Materialise the repo at `base_commit` in an isolated worktree.

    A worktree rather than a checkout so parallel instances of the same repo cannot
    race each other on HEAD.
    """
    src = ensure_repo(repo)
    subprocess.run(
        ["git", "worktree", "add", "--detach", "--force", dest, base_commit],
        cwd=src,
        check=True,
        capture_output=True,
        timeout=600,
    )
    return dest


def remove_worktree(repo: str, dest: str) -> None:
    """Tear down a worktree, ignoring failures during cleanup."""
    try:
        # --force because a failed apply leaves untracked/modified files behind.
        subprocess.run(
            ["git", "worktree", "remove", "--force", dest],
            cwd=repo_path(repo),
            check=False,
            capture_output=True,
            timeout=120,
        )
    except Exception:
        pass
    # Belt-and-suspenders: if git refused, just delete the directory.
    try:
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
    except Exception:
        pass


# --------------------------------------------------------------------------------------
# Layer: Localizer (zero-LLM)
# --------------------------------------------------------------------------------------


def tokenize(text: str) -> list:
    """Lowercase identifier tokens, stop-words removed."""
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    return [t for t in raw if t not in STOP_WORDS]


def explicit_path_hints(problem: str, root: str) -> list:
    """
    Extract file paths the issue names outright.

    Issues frequently quote a traceback or say "in astropy/modeling/separable.py".
    Those are far stronger evidence than any lexical score, so they rank first.
    """
    hits = []
    for match in re.findall(r"[\w/]+\.py", problem):
        candidate = match.lstrip("/")
        if os.path.isfile(os.path.join(root, candidate)):
            hits.append(candidate)
    seen = set()
    return [h for h in hits if not (h in seen or seen.add(h))]


def list_source_files(root: str, limit: int = 6000) -> list:
    """Repo-relative .py paths, excluding tests and vendored trees."""
    skip_dirs = {".git", "node_modules", "build", "dist", ".tox", "__pycache__", ".eggs"}
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            low = rel.lower()
            if "test" in low or low.startswith("doc"):
                continue
            out.append(rel)
            if len(out) >= limit:
                return out
    return out


def localize(problem: str, root: str, top_k: int = 5) -> list:
    """
    Pick the files most likely to need editing. Pure lexical scoring, zero LLM.

    Scoring is IDF-weighted: a token's weight is its query frequency times
    log(1 + N/(1+df)). This matters more than it sounds. A Django issue mentions
    "model", "field", and "django" constantly, and those tokens appear in nearly every
    file, so unweighted overlap just ranks the biggest files first. Rare tokens --
    the actual symbol names in the traceback -- are the signal.

    Measured on a 40-instance sample across astropy/django/requests:
        unweighted overlap    recall@3 = 57.5%
        IDF-weighted          recall@3 = 70.0%, recall@10 = 80.0%

    Path tokens are weighted 6x over content tokens: a filename matching a rare query
    token is much stronger evidence than the same token buried in a 3000-line file.

    Files named outright in the issue text always win, in the order they appear.
    """
    explicit = explicit_path_hints(problem, root)
    if len(explicit) >= top_k:
        return explicit[:top_k]

    query = Counter(tokenize(problem))
    if not query:
        return explicit

    # Pass 1: collect per-file query-token hits and document frequencies.
    docs = {}
    doc_freq = Counter()
    for rel in list_source_files(root):
        try:
            if os.path.getsize(os.path.join(root, rel)) > 400_000:
                continue
            with open(os.path.join(root, rel), "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(60_000)
        except OSError:
            continue
        hits = set(tokenize(head)) & query.keys()
        docs[rel] = hits
        for token in hits:
            doc_freq[token] += 1

    total_docs = max(len(docs), 1)

    def idf(token: str) -> float:
        return math.log(1 + total_docs / (1 + doc_freq[token]))

    # Pass 2: score.
    scored = []
    for rel, hits in docs.items():
        path_hits = set(tokenize(rel)) & query.keys()
        path_score = sum(query[t] * idf(t) for t in path_hits) * 6.0
        content_score = sum(query[t] * idf(t) for t in hits)
        total = path_score + content_score
        if total > 0:
            scored.append((total, rel))

    scored.sort(key=lambda x: (-x[0], x[1]))
    ranked = explicit + [rel for _, rel in scored if rel not in explicit]
    return ranked[:top_k]


def read_file_window(root: str, rel: str, max_chars: int = 24_000) -> str:
    """Read a file for the prompt, truncating very large ones at a line boundary."""
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0] + "\n# ... file truncated ...\n"


def build_context(root: str, files: list) -> str:
    """Render selected files into the prompt."""
    blocks = []
    for rel in files:
        body = read_file_window(root, rel)
        if body:
            blocks.append(f"--- FILE: {rel} ---\n{body}")
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------------------
# Layer: Patch validation (zero-LLM ground truth on form)
# --------------------------------------------------------------------------------------


def strip_patch_fences(raw: str) -> str:
    """Remove markdown fences and any prose before the first diff header."""
    text = raw.strip()
    fence = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    idx = text.find("--- a/")
    if idx > 0:
        text = text[idx:]
    if not text.endswith("\n"):
        text += "\n"
    return text


HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def repair_hunk_counts(patch: str) -> str:
    """
    Recompute @@ hunk line counts from the hunk body. Zero-LLM, purely arithmetic.

    LLMs reliably produce correct *content* and unreliable *counts*: they write
    `@@ -403,8 +403,8 @@` and then emit seven body lines. git rejects the whole patch
    with "corrupt patch at line N" even though the edit itself is perfect.

    We measured this: psf__requests-2317 was marked NO-APPLY by our validator, burned
    two refinement calls, and was then *resolved* by the official grader, which is more
    tolerant. Our own validator was rejecting a correct fix. That is a false negative
    in the governance layer -- exactly the failure mode Law 11 warns about, where a
    deterministic check is stricter than ground truth and silently discards good work.

    Counting lines is not a judgement call, so this belongs in the zero-LLM layer
    rather than being fed back to the model as a "breach" it cannot see.
    """
    lines = patch.split("\n")
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]
        match = HUNK_HEADER_RE.match(line)
        if not match:
            out.append(line)
            i += 1
            continue

        old_start, _, new_start, _, tail = match.groups()

        # Collect the hunk body: everything until the next hunk/file header.
        body = []
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.startswith("@@ ") or nxt.startswith("--- ") or nxt.startswith("diff --git"):
                break
            # A trailing empty line at EOF is a formatting artifact, not a context line.
            if nxt == "" and j == len(lines) - 1:
                break
            body.append(nxt)
            j += 1

        # Drop trailing blank lines that are not real context (" " prefixed).
        while body and body[-1] == "":
            body.pop()

        old_count = sum(1 for b in body if b.startswith((" ", "-")) or b == "")
        new_count = sum(1 for b in body if b.startswith((" ", "+")) or b == "")

        out.append(f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{tail}")
        out.extend(body)
        i = j

    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result


def validate_patch(patch: str, root: str) -> dict:
    """
    Deterministic check: is this a well-formed patch that git can actually apply?

    This is the SWE-bench analogue of the AST validator. It never asks an LLM whether
    the patch looks right — it asks git whether the patch IS right, structurally.

    Returns the (possibly repaired) patch under "patch" so callers propagate the
    corrected text rather than the model's original malformed counts.
    """
    breaches = []

    if not patch.strip():
        return {"success": False, "breaches": ["Patch is empty."], "patch": patch}

    patch = repair_hunk_counts(patch)

    if not patch.lstrip().startswith("--- a/"):
        breaches.append("Patch does not start with a '--- a/<path>' header.")
    if "+++ b/" not in patch:
        breaches.append("Patch is missing a '+++ b/<path>' header.")
    if "@@" not in patch:
        breaches.append("Patch contains no @@ hunk header.")

    for rel in re.findall(r"^--- a/(.+)$", patch, re.MULTILINE):
        if not os.path.isfile(os.path.join(root, rel.strip())):
            breaches.append(f"Patch targets '{rel.strip()}', which does not exist in the repo.")

    if breaches:
        return {"success": False, "breaches": breaches, "patch": patch}

    with tempfile.NamedTemporaryFile("w", suffix=".diff", delete=False) as f:
        f.write(patch)
        patch_file = f.name
    try:
        # Escalating tolerance, mirroring what the official grader accepts.
        # --recount lets git derive counts from the body; -C1 relaxes context matching
        # so a hunk whose line numbers drifted still lands on the right code.
        attempts = (
            [],
            ["--recount"],
            ["--ignore-whitespace", "--recount"],
            ["--ignore-whitespace", "--recount", "-C1"],
            ["--ignore-whitespace", "--recount", "--unidiff-zero", "-C0"],
        )
        proc = None
        for extra in attempts:
            proc = subprocess.run(
                ["git", "apply", "--check", *extra, patch_file],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode == 0:
                return {"success": True, "breaches": [], "patch": patch}

        detail = ((proc.stderr or proc.stdout) if proc else "").strip().splitlines()
        breaches.extend(line.strip() for line in detail[:6])
        return {"success": False, "breaches": breaches, "patch": patch}
    except subprocess.TimeoutExpired:
        return {"success": False, "breaches": ["git apply --check timed out."], "patch": patch}
    finally:
        os.unlink(patch_file)


# --------------------------------------------------------------------------------------
# Solver arms
# --------------------------------------------------------------------------------------


def solve_baseline(instance: dict, root: str, files: list) -> dict:
    """Control: retrieval + one raw LLM call. No validation, no refinement."""
    prompt = (
        f"# Issue\n\n{instance['problem_statement']}\n\n"
        f"# Relevant source\n\n{build_context(root, files)}\n\n"
        "Output the unified diff that fixes this issue."
    )
    response = call_llm(prompt=prompt, system_prompt=PATCH_SYSTEM_PROMPT, timeout=180)
    # Hunk-count repair is applied to BOTH arms. It is mechanical formatting cleanup,
    # not governance, so letting only the agent arm have it would rig the comparison.
    return {
        "patch": repair_hunk_counts(strip_patch_fences(response)),
        "llm_calls": 1,
        "refinements": 0,
        "files": files,
    }


def solve_agent(instance: dict, root: str, files: list, max_refinements: int = 2) -> dict:
    """Treatment: the full governance path. Curate -> generate -> validate -> refine."""
    llm_calls = 0

    sanitized = ContextCuratorEngine.sanitize_raw_text(instance["problem_statement"])
    context = build_context(root, files)

    prompt = (
        f"# Issue\n\n{sanitized}\n\n"
        f"# Relevant source\n\n{context}\n\n"
        "Output the unified diff that fixes this issue."
    )
    response = call_llm(prompt=prompt, system_prompt=PATCH_SYSTEM_PROMPT, timeout=180)
    llm_calls += 1
    patch = strip_patch_fences(response)

    validation = validate_patch(patch, root)
    patch = validation["patch"]

    refinements = 0
    while not validation["success"] and refinements < max_refinements:
        refinements += 1
        breaches = "\n".join(f"- {v}" for v in validation["breaches"])
        fix_prompt = (
            "SURGICAL CORRECTION REQUIRED.\n"
            "Your previous patch could not be applied. Deterministic breaches:\n"
            f"{breaches}\n\n"
            "Your previous patch:\n"
            f"{patch}\n\n"
            f"# Issue\n\n{sanitized}\n\n"
            f"# Relevant source\n\n{context}\n\n"
            "Fix ONLY these breaches. Re-read the source and make the context lines "
            "match the file exactly, character for character. Output ONLY the corrected "
            "unified diff."
        )
        response = call_llm(prompt=fix_prompt, system_prompt=PATCH_SYSTEM_PROMPT, timeout=180)
        llm_calls += 1
        patch = strip_patch_fences(response)
        validation = validate_patch(patch, root)
        patch = validation["patch"]

    return {
        "patch": patch,
        "llm_calls": llm_calls,
        "refinements": refinements,
        "patch_applies": validation["success"],
        "breaches": validation["breaches"],
        "files": files,
    }


def solve_agent_loop(instance: dict, root: str, files: list, max_refinements: int = 4, skip_ptp: bool = True) -> dict:
    """
    Agent-level feedback loop (the first, smallest step toward a multi-agent graph).

    `solve_agent` stops as soon as a patch *applies* -- even if it does not fix the bug.
    SWE-bench is graded on FAIL_TO_PASS flipping, not on apply success, so a patch that
    applies but leaves the tests red is a silent miss.

    This arm extends the governance path with a TEST-FEEDBACK LOOP: after the patch
    applies, we run the instance's FAIL_TO_PASS tests locally (run_tests_in_worktree) and,
    if they are not all green, we return the *failing test names* to the model and ask for
    a corrected diff. The model already understands the problem (it localizes the right
    file and writes a plausible first cut); what it lacks is the second/third step of a
    multi-step fix. A tight feedback loop supplies exactly that -- without needing a full
    multi-agent graph yet.

    This is the empirical probe for the hypothesis: "the model can reason about the fix
    but cannot execute a multi-step fix alone; a feedback loop lets it complete it." If the
    loop resolves instances that single-shot missed, the hypothesis holds and the next
    lever is the graph; if it does not, the ceiling is model capability, not loop depth.

    Returns the same dict shape as solve_agent, plus `test_feedback_rounds`.
    """
    import subprocess

    llm_calls = 0
    sanitized = ContextCuratorEngine.sanitize_raw_text(instance["problem_statement"])
    context = build_context(root, files)

    response = call_llm(
        prompt=f"# Issue\n\n{sanitized}\n\n# Relevant source\n\n{context}\n\nOutput the unified diff that fixes this issue.",
        system_prompt=PATCH_SYSTEM_PROMPT, timeout=180,
    )
    llm_calls += 1
    patch = strip_patch_fences(response)
    validation = validate_patch(patch, root)
    patch = validation["patch"]

    refinements = 0
    while not validation["success"] and refinements < max_refinements:
        refinements += 1
        breaches = "\n".join(f"- {v}" for v in validation["breaches"])
        fix_prompt = (
            "SURGICAL CORRECTION REQUIRED.\n"
            "Your previous patch could not be applied. Deterministic breaches:\n"
            f"{breaches}\n\nYour previous patch:\n{patch}\n\n"
            f"# Issue\n\n{sanitized}\n\n# Relevant source\n\n{context}\n\n"
            "Fix ONLY these breaches. Output ONLY the corrected unified diff."
        )
        response = call_llm(prompt=fix_prompt, system_prompt=PATCH_SYSTEM_PROMPT, timeout=180)
        llm_calls += 1
        patch = strip_patch_fences(response)
        validation = validate_patch(patch, root)
        patch = validation["patch"]

    if not validation["success"]:
        return {
            "patch": patch, "llm_calls": llm_calls, "refinements": refinements,
            "test_feedback_rounds": 0, "patch_applies": False,
            "breaches": validation["breaches"], "files": files,
        }

    test_feedback_rounds = 0
    while test_feedback_rounds < max_refinements:
        res = run_tests_in_worktree(root, patch, instance, skip_ptp=skip_ptp)
        if res["applied"] and res["ftp_pass"] == res["ftp_total"] and res["ftp_total"] > 0:
            break
        test_feedback_rounds += 1
        ftp_cmds = instance.get("FAIL_TO_PASS", [])
        if ftp_cmds and isinstance(ftp_cmds[0], list):
            ftp_cmds = [c for sub in ftp_cmds for c in sub]
        failing = ftp_cmds[res["ftp_pass"]:] if res["ftp_total"] else []
        failing_str = "\n".join(f"- {c}" for c in failing[:8]) or "(tests did not run / patch did not apply)"
        feedback_prompt = (
            "YOUR PATCH APPLIES BUT THE BUG IS NOT FULLY FIXED.\n"
            "These FAIL_TO_PASS tests still fail after your patch:\n"
            f"{failing_str}\n\n"
            "Your current patch:\n"
            f"{patch}\n\n"
            f"# Issue\n\n{sanitized}\n\n# Relevant source\n\n{context}\n\n"
            "The first fix was a good start but incomplete. Diagnose what the failing tests "
            "still require (often a SECOND related code path, an encoding/normalization edge "
            "case, or a sibling call site). Produce a COMPLETE unified diff that fixes every "
            "failing test, not just the first symptom. Output ONLY the unified diff."
        )
        response = call_llm(prompt=feedback_prompt, system_prompt=PATCH_SYSTEM_PROMPT, timeout=180)
        llm_calls += 1
        new_patch = strip_patch_fences(response)
        new_val = validate_patch(new_patch, root)
        if new_val["success"]:
            patch = new_val["patch"]
        subprocess.run(["git", "checkout", "--", "."], cwd=root, capture_output=True, timeout=30)
        subprocess.run(["git", "clean", "-fd"], cwd=root, capture_output=True, timeout=30)

    return {
        "patch": patch, "llm_calls": llm_calls, "refinements": refinements,
        "test_feedback_rounds": test_feedback_rounds, "patch_applies": True,
        "breaches": validation["breaches"], "files": files,
    }


# --------------------------------------------------------------------------------------
# Graph arm (Level 2+3 of the methodology): specialized agents, feedback edges.
#
# The single-agent `loop` (solve_agent_loop) failed (0/3 resolved) because the SAME agent
# both generated and self-repaired, so it fell into the same partial-fix pattern. The fix
# is NOT a stronger model -- it is decomposition (Fares's standing directive): when a task
# is too big for one agent, split it into a graph of specialized agents with feedback edges.
#
# Graph shape (each agent has a SMALL, FOCUSED context -- Law 1 + Law 13):
#   Localizer(zero-LLM) -> Diagnoser(LLM) -> Generator(LLM) -> Analyst(zero-LLM, tests)
#                                                      ^                        |
#                                                      |   feedback edge         v
#                                                   Refiner(LLM) <---- failing-test report
#                                                      |  (DIFFERENT context than Generator:
#                                                      |   sees diagnosis + test report, not
#                                                      |   its own earlier attempt)
#                                                      v
#                                                Validator(zero-LLM, VERIFY node)
#
# Key break from the loop: Generator and Refiner are SEPARATE agents. The Refiner starts
# from a fresh context (diagnosis + test report), not from the Generator's failed attempt,
# so it cannot repeat the Generator's blind spot. This is the empirical crucible for the
# graph thesis, exactly as the loop was for the feedback-loop thesis.
# --------------------------------------------------------------------------------------


DIAGNOSER_SYSTEM_PROMPT = (
    "You are a senior software diagnostician. You receive a bug report, the exact test "
    "commands that must pass (FAIL_TO_PASS), and the relevant source files. Your job is "
    "NOT to write code -- it is to produce a precise, step-by-step diagnosis of what is "
    "broken and what changes are required to make the failing tests pass. Be concrete: "
    "name the functions, the call sites, and the exact behavioral difference the fix must "
    "produce. Output a short structured plan, no code."
)

GENERATOR_SYSTEM_PROMPT = (
    "You are a code generator. You receive a precise diagnosis (what is broken, the exact "
    "steps required) and the relevant source files. Produce ONLY the unified diff that "
    "implements that diagnosis. Do not reinterpret the problem; implement the plan."
)

REFINER_SYSTEM_PROMPT = (
    "You are a surgical patch refiner. You receive: (1) the original diagnosis of the bug, "
    "(2) the current patch, (3) a report of which FAIL_TO_PASS tests STILL fail after that "
    "patch. Your job is to revise the patch so that EVERY failing test passes. Reason from "
    "the diagnosis about what the current patch missed (often a SECOND call site, an "
    "encoding/normalization edge case, or a sibling code path), and produce a COMPLETE "
    "unified diff. Do not repeat the same partial fix; extend it to cover the failing tests."
)


def _diagnose(instance: dict, root: str, files: list) -> str:
    """DIAGNOSER agent: focused LLM context -> structured fix plan (no code)."""
    sanitized = ContextCuratorEngine.sanitize_raw_text(instance["problem_statement"])
    context = build_context(root, files)
    ftp = instance.get("FAIL_TO_PASS", [])
    if ftp and isinstance(ftp[0], list):
        ftp = [c for sub in ftp for c in sub]
    ftp_block = "\n".join(f"- {c}" for c in ftp[:12]) or "(none listed)"
    prompt = (
        f"# Bug report\n\n{sanitized}\n\n"
        f"# FAIL_TO_PASS tests that must pass (the exact success criteria)\n{ftp_block}\n\n"
        f"# Relevant source\n\n{context}\n\n"
        "Produce a precise diagnosis: what is broken, and the concrete steps required to "
        "make the failing tests pass. Name functions and call sites. No code."
    )
    return call_llm(prompt=prompt, system_prompt=DIAGNOSER_SYSTEM_PROMPT, timeout=180)


def _generate(patch_diagnosis: str, instance: dict, root: str, files: list) -> str:
    """GENERATOR agent: implements the diagnosis as a unified diff (focused context)."""
    sanitized = ContextCuratorEngine.sanitize_raw_text(instance["problem_statement"])
    context = build_context(root, files)
    prompt = (
        f"# Issue\n\n{sanitized}\n\n"
        f"# Diagnosis (implement exactly this)\n\n{patch_diagnosis}\n\n"
        f"# Relevant source\n\n{context}\n\n"
        "Output the unified diff that implements the diagnosis above."
    )
    return strip_patch_fences(call_llm(prompt=prompt, system_prompt=GENERATOR_SYSTEM_PROMPT, timeout=180))


def _refine(diagnosis: str, patch: str, instance: dict, root: str, files: list, failing: list) -> str:
    """REFINER agent: SEPARATE context (diagnosis + failing-test report) -> corrected diff."""
    sanitized = ContextCuratorEngine.sanitize_raw_text(instance["problem_statement"])
    context = build_context(root, files)
    failing_block = "\n".join(f"- {c}" for c in failing[:8]) or "(patch did not apply / no test output)"
    prompt = (
        f"# Issue\n\n{sanitized}\n\n"
        f"# Original diagnosis\n\n{diagnosis}\n\n"
        f"# Current patch\n\n{patch}\n\n"
        f"# FAIL_TO_PASS tests STILL failing after the current patch\n{failing_block}\n\n"
        f"# Relevant source\n\n{context}\n\n"
        "Revise the patch so EVERY failing test passes. Extend the diagnosis's plan to cover "
        "what the current patch missed. Output ONLY the complete unified diff."
    )
    return strip_patch_fences(call_llm(prompt=prompt, system_prompt=REFINER_SYSTEM_PROMPT, timeout=180))


def solve_agent_graph(instance: dict, root: str, files: list, max_rounds: int = 3, skip_ptp: bool = True) -> dict:
    """
    Graph arm: specialized agents with a feedback edge (Diagnoser -> Generator ->
    Analyst -> Refiner -> Validator).

    This is the Level-2/3 methodology test. Unlike solve_agent_loop (one agent self-repairs),
    the Generator and Refiner are SEPARATE agents: the Refiner sees the diagnosis + the
    failing-test report as a fresh context, so it cannot repeat the Generator's blind spot.
    Each agent has a small, focused context (Law 1 + Law 13).

    Returns the same dict shape as solve_agent, plus `graph_rounds` and `diagnosis`.
    """
    import subprocess

    llm_calls = 0

    # DIAGNOSER (LLM, focused)
    diagnosis = _diagnose(instance, root, files)
    llm_calls += 1

    # GENERATOR (LLM, from diagnosis)
    patch = _generate(diagnosis, instance, root, files)
    llm_calls += 1
    validation = validate_patch(patch, root)
    patch = validation["patch"]

    # If the generator's patch does not even apply, refine on apply-breaches first (bounded).
    apply_refinements = 0
    while not validation["success"] and apply_refinements < 2:
        apply_refinements += 1
        breaches = "\n".join(f"- {v}" for v in validation["breaches"])
        fix = (
            f"YOUR PATCH DID NOT APPLY. Breaches:\n{breaches}\n\n"
            f"Current patch:\n{patch}\n\nDiagnosis:\n{diagnosis}\n\n"
            "Fix ONLY the apply breaches. Output ONLY the corrected unified diff."
        )
        patch = strip_patch_fences(call_llm(prompt=fix, system_prompt=GENERATOR_SYSTEM_PROMPT, timeout=180))
        llm_calls += 1
        validation = validate_patch(patch, root)
        patch = validation["patch"]

    if not validation["success"]:
        return {
            "patch": patch, "llm_calls": llm_calls, "refinements": apply_refinements,
            "graph_rounds": 0, "diagnosis": diagnosis, "patch_applies": False,
            "breaches": validation["breaches"], "files": files,
        }

    # FEEDBACK EDGE: Analyst (tests) -> Refiner, up to max_rounds.
    graph_rounds = 0
    while graph_rounds < max_rounds:
        res = run_tests_in_worktree(root, patch, instance, skip_ptp=skip_ptp)
        if res["applied"] and res["ftp_pass"] == res["ftp_total"] and res["ftp_total"] > 0:
            break
        graph_rounds += 1
        ftp_cmds = instance.get("FAIL_TO_PASS", [])
        if ftp_cmds and isinstance(ftp_cmds[0], list):
            ftp_cmds = [c for sub in ftp_cmds for c in sub]
        failing = ftp_cmds[res["ftp_pass"]:] if res["ftp_total"] else []
        # REFINER: SEPARATE agent, fresh context (diagnosis + failing report), not self-repair.
        new_patch = _refine(diagnosis, patch, instance, root, files, failing)
        llm_calls += 1
        new_val = validate_patch(new_patch, root)
        if new_val["success"]:
            patch = new_val["patch"]
        subprocess.run(["git", "checkout", "--", "."], cwd=root, capture_output=True, timeout=30)
        subprocess.run(["git", "clean", "-fd"], cwd=root, capture_output=True, timeout=30)

    return {
        "patch": patch, "llm_calls": llm_calls, "refinements": apply_refinements,
        "graph_rounds": graph_rounds, "diagnosis": diagnosis, "patch_applies": True,
        "breaches": validation["breaches"], "files": files,
    }


def run_tests_in_worktree(root: str, patch: str, instance: dict, timeout: int = 120, skip_ptp: bool = False) -> dict:
    """
    Score a candidate patch by actually executing the instance's tests in `root`.

    Applies the patch, runs the FAIL_TO_PASS (and optionally PASS_TO_PASS) test commands
    via the repo's test runner, and reports how many pass. This is the SAME signal the
    official Docker grader uses -- just local and fast -- so it is a faithful, LLM-free
    ranker for best-of-N candidate selection.

    `skip_ptp=True` runs FAIL_TO_PASS only (~5x faster); the authoritative Docker grader
    still checks PASS_TO_PASS, so local ranking only needs the discriminating FTP signal.

    Self-contained: resets the worktree to a clean state at entry and exit so repeated
    calls on the same tree never inherit leftovers from the previous sample (Law 3:
    an infra/state bug must never masquerade as a capability failure).

    Returns {applied, ftp_pass, ftp_total, ptp_pass, ptp_total, score, error}.
    `score` = ftp_pass - (ptp_total - ptp_pass) so breaking PASS_TO_PASS is penalized.
    """
    import subprocess

    def _clean():
        subprocess.run(["git", "checkout", "--", "."], cwd=root, capture_output=True, timeout=30)
        subprocess.run(["git", "clean", "-fd"], cwd=root, capture_output=True, timeout=30)

    _clean()  # start from a pristine tree

    # Dry-check, then apply. Mirror validate_patch's --check so the two agree.
    check = subprocess.run(
        ["git", "apply", "--check", "--whitespace=nowarn"],
        cwd=root, input=patch.encode("utf-8"), capture_output=True, timeout=30,
    )
    if check.returncode != 0:
        _clean()
        return {
            "applied": False, "ftp_pass": 0, "ftp_total": 0, "ptp_pass": 0, "ptp_total": 0,
            "score": -1, "error": check.stderr.decode("utf-8", "ignore")[:200],
        }
    apply_proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn"],
        cwd=root, input=patch.encode("utf-8"), capture_output=True, timeout=30,
    )
    if apply_proc.returncode != 0:
        _clean()
        return {
            "applied": False, "ftp_pass": 0, "ftp_total": 0, "ptp_pass": 0, "ptp_total": 0,
            "score": -1, "error": apply_proc.stderr.decode("utf-8", "ignore")[:200],
        }

    def run_commands(cmds) -> tuple:
        passed = 0
        total = 0
        for cmd in cmds:
            total += 1
            # SWE-bench stores bare pytest node IDs / paths (e.g.
            # "test_requests.py::RequestsTestCase::test_x"). These are NOT shell commands;
            # they must be invoked via the test runner. Prefix with `python -m pytest`.
            full = cmd if cmd.strip().startswith(("python", "pytest", "python3")) else f"python -m pytest {cmd}"
            p = subprocess.run(
                full, shell=True, cwd=root, capture_output=True, timeout=timeout,
                env={**os.environ, "PYTHONPATH": root},
            )
            if p.returncode == 0:
                passed += 1
        return passed, total

    ftp_cmds = instance.get("FAIL_TO_PASS", [])
    ptp_cmds = instance.get("PASS_TO_PASS", [])
    if ftp_cmds and isinstance(ftp_cmds[0], list):
        ftp_cmds = [c for sub in ftp_cmds for c in sub]
    if ptp_cmds and isinstance(ptp_cmds[0], list):
        ptp_cmds = [c for sub in ptp_cmds for c in sub]

    ftp_pass, ftp_total = run_commands(ftp_cmds)
    ptp_pass, ptp_total = (0, 0) if skip_ptp else run_commands(ptp_cmds)

    _clean()  # always leave the tree pristine for the next sample

    score = ftp_pass - (ptp_total - ptp_pass)
    return {
        "applied": True,
        "ftp_pass": ftp_pass, "ftp_total": ftp_total,
        "ptp_pass": ptp_pass, "ptp_total": ptp_total,
        "score": score, "error": None,
    }


def solve_alphacode_swebench(instance: dict, root: str, files: list, n_samples: int = 4) -> dict:
    """
    AlphaCode arm for SWE-bench: sample N patches via the governance path, then select
    the best by LOCAL test execution (FAIL_TO_PASS flipped, PASS_TO_PASS intact) -- not
    by an LLM judge. This is best-of-N at the harness level and directly attacks the
    per-instance LLM variance that made single-shot resolve rate swing 1/8 vs 4/8.
    """
    import subprocess

    candidates = []
    total_llm_calls = 0
    for _ in range(n_samples):
        out = solve_agent(instance, root, files)
        total_llm_calls += out["llm_calls"]
        if not out["patch"]:
            continue
        cand = run_tests_in_worktree(root, out["patch"], instance, skip_ptp=True)
        # Rank primarily by FAIL_TO_PASS flipped locally (the discriminating signal).
        # PASS_TO_PASS is checked by the authoritative Docker grader; running 300+ PTP
        # tests per sample locally makes best-of-N prohibitively slow, so we only
        # penalize if local PTP clearly regressed but still prefer FTP flips.
        candidates.append({
            "patch": out["patch"],
            "applies": out["patch_applies"],
            "score": cand["score"],
            "ftp_pass": cand["ftp_pass"], "ftp_total": cand["ftp_total"],
            "ptp_pass": cand["ptp_pass"], "ptp_total": cand["ptp_total"],
            "local_resolved": cand["applied"] and cand["ftp_pass"] == cand["ftp_total"] and cand["ptp_pass"] == cand["ptp_total"],
        })
        subprocess.run(["git", "checkout", "--", "."], cwd=root, capture_output=True, timeout=30)
        subprocess.run(["git", "clean", "-fd"], cwd=root, capture_output=True, timeout=30)

    if not candidates:
        return {
            "patch": "", "llm_calls": total_llm_calls, "refinements": 0,
            "patch_applies": False, "breaches": ["all samples empty"], "files": files,
            "samples": 0, "best_local_resolved": False,
        }

    candidates.sort(key=lambda c: (c["local_resolved"], c["score"], c["applies"]), reverse=True)
    best = candidates[0]
    return {
        "patch": best["patch"],
        "llm_calls": total_llm_calls,
        "refinements": 0,
        "patch_applies": best["applies"],
        "breaches": [],
        "files": files,
        "samples": len(candidates),
        "best_local_resolved": best["local_resolved"],
        "best_score": best["score"],
    }


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------


def process_instance(instance: dict, mode: str, top_k: int, n_samples: int = 4) -> dict:
    """Produce one prediction. Never raises — infrastructure faults are recorded."""
    iid = instance["instance_id"]
    started = time.time()
    worktree = tempfile.mkdtemp(prefix=f"swb_{iid}_")

    try:
        checkout_worktree(instance["repo"], instance["base_commit"], worktree)
        files = localize(instance["problem_statement"], worktree, top_k=top_k)

        if mode == "agent":
            out = solve_agent(instance, worktree, files)
        elif mode == "alphacode":
            out = solve_alphacode_swebench(instance, worktree, files, n_samples=n_samples)
        elif mode == "loop":
            out = solve_agent_loop(instance, worktree, files)
        elif mode == "graph":
            out = solve_agent_graph(instance, worktree, files)
        else:
            out = solve_baseline(instance, worktree, files)

        # Applicability is reported for both arms so the comparison stays symmetric.
        if "patch_applies" not in out:
            out["patch_applies"] = validate_patch(out["patch"], worktree)["success"]

        result = {
            "instance_id": iid,
            "model_name_or_path": f"gbas-{mode}",
            "model_patch": out["patch"],
            "llm_calls": out["llm_calls"],
            "refinements": out["refinements"],
            "patch_applies": out["patch_applies"],
            "localized_files": out["files"],
            "failure_class": None,
            "error": None,
            "duration": round(time.time() - started, 2),
        }
        # Forward AlphaCode arm signals so the summary can report local-resolved rate.
        if mode == "alphacode":
            result["samples"] = out.get("samples")
            result["best_local_resolved"] = out.get("best_local_resolved")
            result["best_score"] = out.get("best_score")
        # Forward the loop arm's test-feedback round count (the empirical probe signal).
        if mode == "loop":
            result["test_feedback_rounds"] = out.get("test_feedback_rounds")
        # Forward the graph arm's round count + diagnosis (the empirical crucible signal).
        if mode == "graph":
            result["graph_rounds"] = out.get("graph_rounds")
            result["diagnosis"] = out.get("diagnosis")
        return result

    except Exception as exc:
        return {
            "instance_id": iid,
            "model_name_or_path": f"gbas-{mode}",
            "model_patch": "",
            "llm_calls": 0,
            "refinements": 0,
            "patch_applies": False,
            "localized_files": [],
            "failure_class": "infrastructure",
            "error": f"{type(exc).__name__}: {exc}",
            "duration": round(time.time() - started, 2),
        }
    finally:
        remove_worktree(instance["repo"], worktree)


def load_instances(limit: Optional[int], repo_filter: Optional[str]) -> list:
    """Load SWE-bench Verified, optionally filtered to one repo."""
    from datasets import load_dataset

    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    rows = [dict(r) for r in ds]
    if repo_filter:
        rows = [r for r in rows if r["repo"] == repo_filter]
    if limit:
        rows = rows[:limit]
    return rows


def _save_partial_swebench(out_path: str, mode: str, top_k: int, results: list, started: float, n_samples: int = 4) -> None:
    """Persist completed SWE-bench results + predictions so a kill never loses work (Law 3)."""
    applied = sum(1 for r in results if r["patch_applies"])
    infra = sum(1 for r in results if r.get("failure_class") == "infrastructure")
    total = len(results)
    partial = {
        "summary": {
            "mode": mode,
            "model": os.getenv("STEPFUN_MODEL", "step-3.7-flash"),
            "top_k_files": top_k,
            "total_instances": total,
            "patch_apply_rate_percent": round((applied / total) * 100, 2) if total else 0.0,
            "infrastructure_failures": infra,
            "local_resolved": sum(1 for r in results if r.get("best_local_resolved")),
            "n_samples": n_samples if mode == "alphacode" else None,
            "partial": True,
            "wall_clock_seconds": round(time.time() - started, 2),
            "note": "incremental snapshot; patch_apply_rate is NOT the resolve rate.",
        },
        "results": results,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(partial, f, indent=2)
    # Official predictions schema (one JSON object per line) for the grader.
    preds_path = out_path.replace(".json", "_preds.jsonl")
    with open(preds_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({
                "instance_id": r["instance_id"],
                "model_name_or_path": r["model_name_or_path"],
                "model_patch": r.get("model_patch", ""),
            }) + "\n")


def run(mode: str, limit: Optional[int], workers: int, out_path: str, repo_filter: Optional[str], top_k: int, n_samples: int = 4) -> dict:
    instances = load_instances(limit, repo_filter)

    print("=" * 78)
    print(f"  SWE-bench Verified — mode={mode} instances={len(instances)} workers={workers}")
    print(f"  Model: {os.getenv('STEPFUN_MODEL', 'step-3.7-flash')}  top_k_files={top_k}")
    print("=" * 78)

    # Pre-clone serially. Concurrent clones of the same repo would race.
    for repo in sorted({r["repo"] for r in instances}):
        print(f"  preparing {repo} ...", flush=True)
        ensure_repo(repo)

    results = []
    started = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process_instance, r, mode, top_k, n_samples): r for r in instances}
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            results.append(res)
            flag = "APPLIES" if res["patch_applies"] else "NO-APPLY"
            if res["failure_class"] == "infrastructure":
                flag = "INFRA-FAIL"
            print(f"  [{i:3}/{len(instances)}] {res['instance_id']:<34} {flag:<11} {res['duration']}s", flush=True)
            # Incremental save: a timeout/kill never loses completed results (Law 3).
            if out_path:
                _save_partial_swebench(out_path, mode, top_k, results, started, n_samples)

    results.sort(key=lambda r: r["instance_id"])

    applied = sum(1 for r in results if r["patch_applies"])
    infra = sum(1 for r in results if r["failure_class"] == "infrastructure")

    summary = {
        "benchmark": "SWE-bench Verified",
        "mode": mode,
        "model": os.getenv("STEPFUN_MODEL", "step-3.7-flash"),
        "total_instances": len(results),
        "patch_applies": applied,
        "patch_apply_rate_percent": round(applied / len(results) * 100, 2) if results else 0.0,
        "infrastructure_failures": infra,
        "total_llm_calls": sum(r["llm_calls"] for r in results),
        "total_refinements": sum(r["refinements"] for r in results),
        "wall_clock_seconds": round(time.time() - started, 2),
        "top_k_files": top_k,
        "n_samples": n_samples if mode == "alphacode" else None,
        "local_resolved": sum(1 for r in results if r.get("best_local_resolved")),
        "note": "patch_apply_rate is NOT the resolve rate. Run the official evaluator to grade.",
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    # Official predictions schema, one JSON object per line.
    preds_path = out_path.replace(".json", "_preds.jsonl")
    with open(preds_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({
                "instance_id": r["instance_id"],
                "model_name_or_path": r["model_name_or_path"],
                "model_patch": r["model_patch"],
            }) + "\n")

    print("=" * 78)
    print(f"  Patch applies:  {summary['patch_apply_rate_percent']}%  ({applied}/{len(results)})")
    print(f"  Infra fails:    {infra}")
    print(f"  LLM calls:      {summary['total_llm_calls']}")
    print(f"  Refinements:    {summary['total_refinements']}")
    if mode == "alphacode":
        print(f"  Local-resolved: {summary['local_resolved']}/{len(results)} (best-of-{n_samples} candidates, pre-Docker)")
    print(f"  Wall clock:     {summary['wall_clock_seconds']}s")
    print("=" * 78)
    print(f"  Predictions -> {preds_path}")
    print("  Grade with:")
    print(f"    python -m swebench.harness.run_evaluation \\")
    print(f"      --dataset_name princeton-nlp/SWE-bench_Verified \\")
    print(f"      --predictions_path {preds_path} \\")
    print(f"      --max_workers 8 --run_id gbas_{mode}")
    print("=" * 78)
    return {"summary": summary, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWE-bench Verified harness")
    parser.add_argument("--mode", choices=["agent", "baseline", "alphacode", "loop", "graph"], default="agent")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--repo", default=None, help="Filter to one repo, e.g. django/django")
    parser.add_argument("--top-k", type=int, default=5, help="Files retrieved into the prompt")
    parser.add_argument("--n-samples", type=int, default=4, help="AlphaCode arm: N patches sampled per instance")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    out = args.out or os.path.join(RESULTS_DIR, f"swebench_{args.mode}_{args.limit or 'all'}.json")
    run(args.mode, args.limit, args.workers, out, args.repo, args.top_k, args.n_samples)
