#!/usr/bin/env python3
"""
LLM Eval runner for the rn-new-arch-migration skill.

For each test case in cases.yaml this script:
  1. Loads the fixture project's files as inline context
  2. Sends user prompt + fixture context to Claude with SKILL.md as system instructions
  3. Runs rule-based checks on the response
  4. Grades the response 0–10 using Claude as an LLM judge
  5. Reports a summary table and exits non-zero if any case fails

Usage:
    python3 eval/llm/run_llm_eval.py [--case CASE_ID] [--model MODEL] [--verbose]

Requirements:
    pip install anthropic pyyaml
    export ANTHROPIC_API_KEY=sk-ant-...
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

EVAL_DIR   = Path(__file__).parent
LLM_DIR    = EVAL_DIR / "llm"
SKILL_ROOT = EVAL_DIR.parent
FIXTURES   = EVAL_DIR / "fixtures"
SKILL_MD   = SKILL_ROOT / "SKILL.md"
CASES_YAML = LLM_DIR / "cases.yaml"

FIXTURE_MAP = {
    "project_blocking": FIXTURES / "project_blocking",
    "project_clean":    FIXTURES / "project_clean",
    "project_interop":  FIXTURES / "project_interop",
    "project_jsonly":   FIXTURES / "project_jsonly",
}

# File extensions to include in fixture context
INCLUDE_EXTENSIONS = {".json", ".ts", ".tsx", ".js", ".jsx", ".m", ".mm", ".swift", ".java", ".kt"}
# Directories to exclude
EXCLUDE_DIRS = {"node_modules", "Pods", "build", "DerivedData", ".rn-arch-cache"}


# ── Fixture context builder ────────────────────────────────────────────────────

def build_fixture_context(fixture_path: Path) -> str:
    """Read all relevant files in the fixture and format as inline context."""
    sections = []
    for file_path in sorted(fixture_path.rglob("*")):
        if not file_path.is_file():
            continue
        # Skip excluded dirs
        if any(excl in file_path.parts for excl in EXCLUDE_DIRS):
            continue
        if file_path.suffix not in INCLUDE_EXTENSIONS:
            continue
        rel = file_path.relative_to(fixture_path)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        sections.append(f"--- FILE: {rel} ---\n{content}")
    return "\n\n".join(sections)


# ── Rule-based checks ─────────────────────────────────────────────────────────

def run_checks(response_text: str, checks: list[dict]) -> list[dict]:
    """Run rule-based checks. Returns list of {check, passed, reason}."""
    results = []
    for check in checks:
        kind = check.get("type")
        desc = check.get("description", "")

        if kind == "contains":
            needle = check["value"]
            text = response_text if not check.get("case_insensitive") else response_text.lower()
            needle_cmp = needle if not check.get("case_insensitive") else needle.lower()
            passed = needle_cmp in text
            results.append({
                "check": desc or f"contains: {needle!r}",
                "passed": passed,
                "reason": f"{'Found' if passed else 'NOT found'}: {needle!r}",
            })

        elif kind == "not_contains":
            needle = check["value"]
            text = response_text if not check.get("case_insensitive") else response_text.lower()
            needle_cmp = needle if not check.get("case_insensitive") else needle.lower()
            found = needle_cmp in text
            passed = not found
            results.append({
                "check": desc or f"not_contains: {needle!r}",
                "passed": passed,
                "reason": f"{'Correctly absent' if passed else 'Unexpectedly found'}: {needle!r}",
            })

        elif kind == "contains_any":
            values = check["values"]
            ci = check.get("case_insensitive", False)
            text = response_text.lower() if ci else response_text
            matched = next((v for v in values if (v.lower() if ci else v) in text), None)
            passed = matched is not None
            results.append({
                "check": desc or f"contains_any: {values}",
                "passed": passed,
                "reason": f"Matched: {matched!r}" if passed else f"None of {values} found",
            })

        elif kind == "contains_pattern":
            pattern = check["pattern"]
            passed = bool(re.search(pattern, response_text))
            results.append({
                "check": desc or f"pattern: {pattern!r}",
                "passed": passed,
                "reason": "Pattern matched" if passed else f"Pattern not found: {pattern!r}",
            })

        else:
            results.append({"check": f"unknown type: {kind}", "passed": False, "reason": "Unknown check type"})

    return results


# ── LLM judge ────────────────────────────────────────────────────────────────

def llm_judge(client: "anthropic.Anthropic", case: dict, response_text: str, model: str) -> dict:
    """Ask Claude to score the response 0–10 against the rubric."""
    judge_prompt = f"""\
You are grading an AI assistant's response to a React Native New Architecture audit task.

**Task given to the assistant:**
{case['prompt']}

**Grading rubric:**
{case['grading_rubric']}

**Assistant's response:**
{response_text[:6000]}{"... [truncated]" if len(response_text) > 6000 else ""}

Score the response 0–10 where 10 is perfect according to the rubric.
Respond ONLY with valid JSON in this exact format: {{"score": <int 0-10>, "reason": "<one sentence>"}}"""

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        raw = msg.content[0].text.strip()
        # Extract JSON even if the model wraps it in markdown
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return {"score": int(data.get("score", 0)), "reason": str(data.get("reason", ""))}
    except Exception as e:
        return {"score": -1, "reason": f"Judge error: {e}"}
    return {"score": -1, "reason": "Could not parse judge response"}


# ── Main eval runner ──────────────────────────────────────────────────────────

def run_case(client: "anthropic.Anthropic", case: dict, skill_md: str, model: str, verbose: bool) -> dict:
    fixture_name = case["fixture"]
    fixture_path = FIXTURE_MAP.get(fixture_name)
    if fixture_path is None or not fixture_path.exists():
        return {
            "id": case["id"], "name": case["name"],
            "rule_passed": 0, "rule_total": len(case.get("checks", [])),
            "llm_score": -1, "llm_reason": f"Fixture not found: {fixture_name}",
            "elapsed": 0, "status": "ERROR",
        }

    fixture_context = build_fixture_context(fixture_path)
    user_message = (
        f"Here is the React Native project to audit:\n\n{fixture_context}\n\n"
        f"---\n\n{case['prompt']}"
    )

    system_prompt = (
        "You are Claude Code running the React Native New Architecture Migration skill. "
        "The following are your skill instructions — follow them precisely.\n\n"
        f"{skill_md}"
    )

    t0 = time.time()
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        response_text = msg.content[0].text
    except Exception as e:
        return {
            "id": case["id"], "name": case["name"],
            "rule_passed": 0, "rule_total": len(case.get("checks", [])),
            "llm_score": -1, "llm_reason": f"API error: {e}",
            "elapsed": round(time.time() - t0, 1), "status": "ERROR",
        }

    elapsed = round(time.time() - t0, 1)

    if verbose:
        print(f"\n{'='*60}")
        print(f"CASE: {case['id']}")
        print(f"{'='*60}")
        print(response_text[:2000])
        if len(response_text) > 2000:
            print(f"... [{len(response_text) - 2000} chars truncated]")

    # Rule-based checks
    check_results = run_checks(response_text, case.get("checks", []))
    rule_passed = sum(1 for c in check_results if c["passed"])
    rule_total  = len(check_results)

    if verbose:
        print(f"\nRule checks: {rule_passed}/{rule_total}")
        for cr in check_results:
            sym = "✅" if cr["passed"] else "❌"
            print(f"  {sym}  {cr['check']} — {cr['reason']}")

    # LLM judge
    judge = llm_judge(client, case, response_text, model)

    if verbose:
        print(f"\nLLM score: {judge['score']}/10 — {judge['reason']}")

    status = "PASS" if (rule_passed == rule_total and judge["score"] >= 6) else "FAIL"

    return {
        "id":           case["id"],
        "name":         case["name"],
        "rule_passed":  rule_passed,
        "rule_total":   rule_total,
        "rule_details": check_results,
        "llm_score":    judge["score"],
        "llm_reason":   judge["reason"],
        "elapsed":      elapsed,
        "status":       status,
    }


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("EVAL SUMMARY")
    print("=" * 70)

    col_id    = max(len(r["id"]) for r in results) + 2
    header    = f"{'Case ID':<{col_id}}  {'Rules':>6}  {'LLM':>4}  {'Time':>6}  Status"
    print(header)
    print("-" * len(header))

    for r in results:
        rules = f"{r['rule_passed']}/{r['rule_total']}"
        llm   = str(r["llm_score"]) if r["llm_score"] >= 0 else "ERR"
        sym   = "✅" if r["status"] == "PASS" else ("⚠️ " if r["status"] == "ERROR" else "❌")
        print(f"{r['id']:<{col_id}}  {rules:>6}  {llm:>4}  {r['elapsed']:>5.1f}s  {sym}  {r['status']}")

    total   = len(results)
    passed  = sum(1 for r in results if r["status"] == "PASS")
    avg_llm = sum(r["llm_score"] for r in results if r["llm_score"] >= 0)
    n_llm   = sum(1 for r in results if r["llm_score"] >= 0)

    print("-" * len(header))
    print(f"Result: {passed}/{total} cases passed")
    if n_llm:
        print(f"Average LLM score: {avg_llm / n_llm:.1f}/10")


def main():
    parser = argparse.ArgumentParser(description="LLM Eval runner for rn-new-arch-migration skill")
    parser.add_argument("--case",    help="Run only this case ID")
    parser.add_argument("--model",   default="claude-sonnet-4-6", help="Claude model to use")
    parser.add_argument("--verbose", action="store_true", help="Print full responses and check details")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("  Set it with: export ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Load skill instructions
    if not SKILL_MD.exists():
        print(f"ERROR: SKILL.md not found at {SKILL_MD}", file=sys.stderr)
        sys.exit(1)
    skill_md = SKILL_MD.read_text(encoding="utf-8")

    # Load test cases
    if not CASES_YAML.exists():
        print(f"ERROR: cases.yaml not found at {CASES_YAML}", file=sys.stderr)
        sys.exit(1)
    with open(CASES_YAML) as f:
        raw = yaml.safe_load(f)
    cases = raw.get("cases", [])

    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"ERROR: no case with id={args.case!r}", file=sys.stderr)
            sys.exit(1)

    print(f"Running {len(cases)} eval case(s) with model={args.model}")
    print()

    results = []
    for case in cases:
        print(f"  ▶  {case['id']} — {case['name']}")
        result = run_case(client, case, skill_md, args.model, args.verbose)
        results.append(result)
        sym = "✅" if result["status"] == "PASS" else ("⚠️ " if result["status"] == "ERROR" else "❌")
        print(f"     {sym} rules {result['rule_passed']}/{result['rule_total']}  "
              f"llm {result['llm_score']}/10  {result['elapsed']}s")

    print_summary(results)

    failed = [r for r in results if r["status"] != "PASS"]
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
