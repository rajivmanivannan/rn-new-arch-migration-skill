"""
Unit tests for generate_pdf.py parsing functions.

Tests cover:
  - _simple_yaml key-value parsing
  - parse_md: PDF_META comment extraction, YAML frontmatter fallback
  - get_section: heading-based section extraction
  - parse_md_table: Markdown table parsing
  - md2rl: Markdown to ReportLab XML conversion
  - parse_dep_groups: dependency audit section structure
  - parse_action_plan: phase and step extraction
  - dep group kind classification
"""
import sys
from pathlib import Path

import pytest

# Add scripts/ to path
SKILL_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import generate_pdf  # noqa: E402


# ── _simple_yaml ──────────────────────────────────────────────────────────────

def test_simple_yaml_basic():
    result = generate_pdf._simple_yaml("key: value\nnum: 42")
    assert result["key"] == "value"
    assert result["num"] == "42"


def test_simple_yaml_quoted_double():
    result = generate_pdf._simple_yaml('name: "MyApp"')
    assert result["name"] == "MyApp"


def test_simple_yaml_quoted_single():
    result = generate_pdf._simple_yaml("rn_version: '0.76.0'")
    assert result["rn_version"] == "0.76.0"


def test_simple_yaml_colon_in_value():
    result = generate_pdf._simple_yaml("audit_date: 2026-03-20")
    assert result["audit_date"] == "2026-03-20"


def test_simple_yaml_empty():
    result = generate_pdf._simple_yaml("")
    assert result == {}


def test_simple_yaml_boolean():
    result = generate_pdf._simple_yaml("new_arch_enabled: false\nrn_eligible: true")
    assert result["new_arch_enabled"] == "false"
    assert result["rn_eligible"] == "true"


# ── parse_md ──────────────────────────────────────────────────────────────────

PDF_META_COMMENT = """\
# Report Title

Some body content here.

<!-- PDF_META
project: TestApp
rn_version: "0.76.0"
tier1_effort: "~3-5 days"
tier1_label: Low
tier2_effort: "~18-30 days"
tier2_label: High
audit_date: "2026-03-20"
new_arch_enabled: false
-->"""


def test_parse_md_extracts_pdf_meta():
    meta, body = generate_pdf.parse_md(PDF_META_COMMENT)
    assert meta.get("project") == "TestApp"
    assert meta.get("tier1_effort") == "~3-5 days"
    assert meta.get("tier1_label") == "Low"
    assert meta.get("tier2_effort") == "~18-30 days"
    assert meta.get("tier2_label") == "High"


def test_parse_md_body_excludes_comment():
    meta, body = generate_pdf.parse_md(PDF_META_COMMENT)
    assert "PDF_META" not in body
    assert "project: TestApp" not in body


def test_parse_md_body_contains_heading():
    meta, body = generate_pdf.parse_md(PDF_META_COMMENT)
    assert "Report Title" in body


def test_parse_md_yaml_frontmatter_fallback():
    md = "---\nproject: OldApp\neffort_label: Low\n---\n# Body content"
    meta, body = generate_pdf.parse_md(md)
    assert meta.get("project") == "OldApp"
    assert "Body content" in body


def test_parse_md_no_meta_returns_empty_dict():
    md = "# Just a heading\n\nSome content."
    meta, body = generate_pdf.parse_md(md)
    assert meta == {}
    assert "Just a heading" in body


# ── get_section ───────────────────────────────────────────────────────────────

def test_get_section_found():
    body = "## Executive Summary\n\nThis is the summary text.\n\n## Next Section\n\nOther content."
    result = generate_pdf.get_section(body, "Executive Summary")
    assert "summary text" in result
    assert "Next Section" not in result


def test_get_section_not_found():
    body = "## Executive Summary\n\nContent."
    result = generate_pdf.get_section(body, "Missing Section")
    assert result == ""


def test_get_section_last_section():
    """Last section has no trailing ##, should still be captured."""
    body = "## First\n\nFirst content.\n\n## Last Section\n\nLast content."
    result = generate_pdf.get_section(body, "Last Section")
    assert "Last content" in result


# ── parse_md_table ────────────────────────────────────────────────────────────

def test_parse_md_table_basic():
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    headers, rows = generate_pdf.parse_md_table(table)
    assert headers == ["A", "B"]
    assert rows == [["1", "2"]]


def test_parse_md_table_multiple_rows():
    table = "| Package | Status |\n|---|---|\n| react-native-foo | ✅ |\n| react-native-bar | ❌ |"
    headers, rows = generate_pdf.parse_md_table(table)
    assert len(rows) == 2
    assert rows[0][0] == "react-native-foo"
    assert rows[1][1] == "❌"


def test_parse_md_table_strips_whitespace():
    table = "|  Package  |  Notes  |\n|---|---|\n|  my-pkg  |  some note  |"
    _, rows = generate_pdf.parse_md_table(table)
    assert rows[0][0] == "my-pkg"
    assert rows[0][1] == "some note"


def test_parse_md_table_insufficient_lines():
    table = "| A | B |"
    headers, rows = generate_pdf.parse_md_table(table)
    assert headers == []
    assert rows == []


def test_parse_md_table_only_header_separator():
    table = "| A | B |\n|---|---|"
    headers, rows = generate_pdf.parse_md_table(table)
    assert rows == []


# ── md2rl ─────────────────────────────────────────────────────────────────────

def test_md2rl_bold():
    result = generate_pdf.md2rl("**hello world**")
    assert "<b>hello world</b>" in result


def test_md2rl_inline_code():
    result = generate_pdf.md2rl("`react-native-snap-carousel`")
    assert "react-native-snap-carousel" in result
    assert "Courier" in result


def test_md2rl_escapes_ampersand():
    result = generate_pdf.md2rl("AT&T")
    assert "&amp;" in result
    assert "AT&T" not in result


def test_md2rl_escapes_less_than():
    result = generate_pdf.md2rl("<script>")
    assert "&lt;" in result


def test_md2rl_escapes_greater_than():
    result = generate_pdf.md2rl("x > 0")
    assert "&gt;" in result


def test_md2rl_plain_text_unchanged():
    result = generate_pdf.md2rl("hello world")
    assert result == "hello world"


def test_md2rl_strips_hr():
    result = generate_pdf.md2rl("---")
    assert "---" not in result


# ── parse_dep_groups ──────────────────────────────────────────────────────────

_DEP_AUDIT_BODY = """\
## 1. Dependency Audit

### ❌ Blocking

| Package | Version | Status | Notes |
|---|---|---|---|
| react-native-snap-carousel | ^3.9.1 | ❌ Blocking | Unmaintained |
| react-native-vector-icons | ^9.2.0 | ❌ Blocking | Upgrade to >=10 |

### ✅ Compatible

| Package | Version | Status | Notes |
|---|---|---|---|
| @react-navigation/native | ^6.1.0 | ✅ Compatible | New Arch ready |

## 2. JS/TS Source Findings
"""


def test_parse_dep_groups_count():
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_BODY)
    assert len(groups) == 2


def test_parse_dep_groups_blocking_kind():
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_BODY)
    blocking = next(g for g in groups if "Blocking" in g[0])
    assert blocking[1] == "block"
    assert len(blocking[3]) == 2


def test_parse_dep_groups_compatible_kind():
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_BODY)
    compat = next(g for g in groups if "Compatible" in g[0])
    assert compat[1] == "ok"
    assert len(compat[3]) == 1


def test_parse_dep_groups_row_content():
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_BODY)
    blocking = next(g for g in groups if "Blocking" in g[0])
    pkgs = [row[0] for row in blocking[3]]
    assert "react-native-snap-carousel" in pkgs


# ── parse_action_plan ─────────────────────────────────────────────────────────

_ACTION_PLAN_BODY = """\
## 5. Prioritized Action Plan

### Phase 1 — Replace Blocking Library

1. **Replace react-native-snap-carousel**
   Switch to react-native-reanimated-carousel

2. **Upgrade react-native-vector-icons to v10**
   Run find-replace on import paths after upgrade

### Phase 2 — Rewrite In-house Native Modules

1. **Rewrite InHouseVerify as TurboModule**
   Create a Codegen spec file alongside the native implementation

## 6. Effort Estimate
"""


def test_parse_action_plan_phase_count():
    phases = generate_pdf.parse_action_plan(_ACTION_PLAN_BODY)
    assert len(phases) == 2


def test_parse_action_plan_phase_title():
    phases = generate_pdf.parse_action_plan(_ACTION_PLAN_BODY)
    assert "Phase 1" in phases[0][0]
    assert "Phase 2" in phases[1][0]


def test_parse_action_plan_steps():
    phases = generate_pdf.parse_action_plan(_ACTION_PLAN_BODY)
    phase1_steps = phases[0][1]
    assert len(phase1_steps) == 2
    titles = [s[0] for s in phase1_steps]
    assert "Replace react-native-snap-carousel" in titles


def test_parse_action_plan_step_description():
    phases = generate_pdf.parse_action_plan(_ACTION_PLAN_BODY)
    step = phases[0][1][0]  # Phase 1, Step 1
    assert len(step) == 2   # (title, description)
    assert "reanimated-carousel" in step[1]


# ── dep group kind classification (via parse_dep_groups) ─────────────────────

def test_dep_group_blocking_kind():
    """Blocking heading must produce kind='block'."""
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_BODY)
    blocking = next(g for g in groups if "Blocking" in g[0])
    assert blocking[1] == "block"


def test_dep_group_compatible_kind():
    """Compatible heading must produce kind='ok'."""
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_BODY)
    compat = next(g for g in groups if "Compatible" in g[0])
    assert compat[1] == "ok"


_DEP_AUDIT_WITH_INTEROP = """\
## 1. Dependency Audit

### ⚠️ Interop

| Package | Version | Status | Notes |
|---|---|---|---|
| react-native-modal | ^13.0.0 | ⚠️ Interop | Works under interop layer |

## 2. JS/TS Source Findings
"""


def test_dep_group_interop_kind():
    """Interop heading must produce kind='interop'."""
    groups = generate_pdf.parse_dep_groups(_DEP_AUDIT_WITH_INTEROP)
    interop = next(g for g in groups if "Interop" in g[0])
    assert interop[1] == "interop"
