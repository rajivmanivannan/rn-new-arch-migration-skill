#!/usr/bin/env bash
# Run all three eval tiers and print a combined summary.
# Usage: ./eval/run_all.sh [--no-llm] [--verbose]
#
# Tier 1: Unit tests       (pytest eval/unit/)
# Tier 2: Integration tests (pytest eval/integration/)
# Tier 3: LLM eval         (python3 eval/llm/run_llm_eval.py)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NO_LLM=false
VERBOSE=""
for arg in "$@"; do
  case "$arg" in
    --no-llm)  NO_LLM=true ;;
    --verbose) VERBOSE="--verbose" ;;
  esac
done

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "${GREEN}✅  $*${NC}"; }
fail() { echo -e "${RED}❌  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️   $*${NC}"; }

UNIT_PASS=false
INTEG_PASS=false
LLM_PASS=false
LLM_SKIPPED=false

echo "=================================================="
echo " React Native New Arch Migration Skill — Eval Suite"
echo "=================================================="
echo

# ── Tier 1: Unit tests ────────────────────────────────────────────────────────
echo "── Tier 1: Unit tests ──────────────────────────────"
if python3 -m pytest "$SCRIPT_DIR/unit/" -v --tb=short 2>&1; then
  pass "Unit tests passed"
  UNIT_PASS=true
else
  fail "Unit tests failed"
fi
echo

# ── Tier 2: Integration tests ─────────────────────────────────────────────────
echo "── Tier 2: Integration tests ───────────────────────"
if python3 -m pytest "$SCRIPT_DIR/integration/" -v --tb=short 2>&1; then
  pass "Integration tests passed"
  INTEG_PASS=true
else
  fail "Integration tests failed"
fi
echo

# ── Tier 3: LLM eval ─────────────────────────────────────────────────────────
echo "── Tier 3: LLM eval ────────────────────────────────"
if $NO_LLM; then
  warn "LLM eval skipped (--no-llm)"
  LLM_SKIPPED=true
elif [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  warn "LLM eval skipped — ANTHROPIC_API_KEY not set"
  warn "  Set it and re-run, or use --no-llm to suppress this warning"
  LLM_SKIPPED=true
else
  if python3 "$SCRIPT_DIR/llm/run_llm_eval.py" $VERBOSE 2>&1; then
    pass "LLM eval passed"
    LLM_PASS=true
  else
    fail "LLM eval failed"
  fi
fi
echo

# ── Summary ───────────────────────────────────────────────────────────────────
echo "=================================================="
echo " SUMMARY"
echo "=================================================="

$UNIT_PASS  && pass "Tier 1 Unit tests" || fail "Tier 1 Unit tests"
$INTEG_PASS && pass "Tier 2 Integration tests" || fail "Tier 2 Integration tests"

if $LLM_SKIPPED; then
  warn "Tier 3 LLM eval — skipped"
elif $LLM_PASS; then
  pass "Tier 3 LLM eval"
else
  fail "Tier 3 LLM eval"
fi

echo

if $UNIT_PASS && $INTEG_PASS && ($LLM_PASS || $LLM_SKIPPED); then
  pass "All active eval tiers passed"
  exit 0
else
  fail "One or more eval tiers failed"
  exit 1
fi
