"""
Integration tests — run check_libs.py against fixture projects and assert JSON output.

Override and PURE_JS lookups require no network (resolved in-process).
Tests marked CI_NO_NETWORK are skipped when network is unavailable since
they rely on live reactnative.directory lookups.

Set CI_NO_NETWORK=1 to skip network-dependent tests.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SKILL_ROOT  = Path(__file__).parent.parent.parent
EVAL_ROOT   = SKILL_ROOT / "eval"
FIXTURES    = EVAL_ROOT / "fixtures"
SCRIPT      = SKILL_ROOT / "scripts" / "check_libs.py"

CI_NO_NETWORK = os.environ.get("CI_NO_NETWORK", "").lower() in ("1", "true", "yes")


def run_check_libs(fixture_name: str, tmp_path: Path) -> dict:
    out_file = tmp_path / "lib_report.json"
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--project-root", str(FIXTURES / fixture_name),
            "--output", str(out_file),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"check_libs.py exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert out_file.exists(), "lib_report.json was not written"
    return json.loads(out_file.read_text())


# ── Report schema ──────────────────────────────────────────────────────────────

def test_report_json_schema(tmp_path):
    data = run_check_libs("project_blocking", tmp_path)
    required_keys = {
        "summary", "libraries", "pure_js_skipped",
        "total_deps", "native_checked", "generated_at",
    }
    assert required_keys.issubset(data.keys())


def test_summary_has_correct_counters(tmp_path):
    data = run_check_libs("project_blocking", tmp_path)
    summary = data["summary"]
    assert set(summary.keys()) >= {"compatible", "interop", "unknown"}
    for val in summary.values():
        assert isinstance(val, int)


# ── project_blocking ──────────────────────────────────────────────────────────

@pytest.mark.skipif(CI_NO_NETWORK, reason="requires live reactnative.directory")
def test_blocking_app_has_non_compatible_entries(tmp_path):
    """Blocking project should have at least some interop or unknown entries (live lookup)."""
    data = run_check_libs("project_blocking", tmp_path)
    non_compatible = data["summary"]["interop"] + data["summary"]["unknown"]
    assert non_compatible >= 1


@pytest.mark.skipif(CI_NO_NETWORK, reason="requires live reactnative.directory")
def test_blocking_app_snap_carousel_detected(tmp_path):
    """snap-carousel should appear in results (interop or unknown via live lookup — unmaintained is not blocking)."""
    data = run_check_libs("project_blocking", tmp_path)
    pkgs = {lib["package"]: lib for lib in data["libraries"]}
    assert "react-native-snap-carousel" in pkgs
    assert pkgs["react-native-snap-carousel"]["status"] in ("interop", "unknown")


@pytest.mark.skipif(CI_NO_NETWORK, reason="requires live reactnative.directory")
def test_blocking_app_vector_icons_detected(tmp_path):
    """vector-icons should appear in results (status depends on live lookup)."""
    data = run_check_libs("project_blocking", tmp_path)
    pkgs = {lib["package"]: lib for lib in data["libraries"]}
    assert "react-native-vector-icons" in pkgs


def test_blocking_app_pure_js_skipped(tmp_path):
    data = run_check_libs("project_blocking", tmp_path)
    # lodash and axios are in PURE_JS
    assert data["pure_js_skipped"] >= 2


def test_blocking_app_react_native_not_in_libraries(tmp_path):
    """react-native core is in PURE_JS — must not appear in output."""
    data = run_check_libs("project_blocking", tmp_path)
    pkgs = [lib["package"] for lib in data["libraries"]]
    assert "react-native" not in pkgs


# ── project_clean ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(CI_NO_NETWORK, reason="requires live reactnative.directory")
def test_clean_app_zero_unknown(tmp_path):
    """Clean project should have no unknown entries — all resolved as compatible or interop."""
    data = run_check_libs("project_clean", tmp_path)
    assert data["summary"]["unknown"] == 0


@pytest.mark.skipif(CI_NO_NETWORK, reason="requires live reactnative.directory")
def test_clean_app_has_compatible_entries(tmp_path):
    data = run_check_libs("project_clean", tmp_path)
    assert data["summary"]["compatible"] >= 3


@pytest.mark.skipif(CI_NO_NETWORK, reason="requires live reactnative.directory")
def test_clean_app_reanimated_compatible(tmp_path):
    data = run_check_libs("project_clean", tmp_path)
    pkgs = {lib["package"]: lib for lib in data["libraries"]}
    if "react-native-reanimated" in pkgs:
        assert pkgs["react-native-reanimated"]["status"] == "compatible"


def test_clean_app_pure_js_skipped(tmp_path):
    data = run_check_libs("project_clean", tmp_path)
    # lodash, axios, zustand are all PURE_JS
    assert data["pure_js_skipped"] >= 3


# ── project_jsonly ────────────────────────────────────────────────────────────

def test_jsonly_app_all_packages_skipped(tmp_path):
    """All 5 packages are pure JS — native_checked must be 0."""
    data = run_check_libs("project_jsonly", tmp_path)
    assert data["native_checked"] == 0


def test_jsonly_app_libraries_empty(tmp_path):
    data = run_check_libs("project_jsonly", tmp_path)
    assert data["libraries"] == []


def test_jsonly_app_no_unknown(tmp_path):
    """JS-only project should have no unknown entries — everything is pure JS."""
    data = run_check_libs("project_jsonly", tmp_path)
    assert data["summary"]["unknown"] == 0


# ── Error cases ───────────────────────────────────────────────────────────────

def test_malformed_package_json_exits_nonzero(tmp_path):
    bad_dir = tmp_path / "bad_project"
    bad_dir.mkdir()
    (bad_dir / "package.json").write_text("{ this is not valid JSON }")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(bad_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Cannot parse" in result.stderr or "Cannot parse" in result.stdout


def test_missing_package_json_exits_nonzero(tmp_path):
    empty_dir = tmp_path / "empty_project"
    empty_dir.mkdir()

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(empty_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    error_output = result.stderr + result.stdout
    assert "package.json" in error_output


def test_empty_dependencies_exits_nonzero(tmp_path):
    proj_dir = tmp_path / "empty_deps"
    proj_dir.mkdir()
    (proj_dir / "package.json").write_text(json.dumps({"name": "test", "version": "1.0.0"}))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(proj_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


# ── Output file location ──────────────────────────────────────────────────────

def test_output_written_to_custom_path(tmp_path):
    custom_out = tmp_path / "custom_report.json"
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--project-root", str(FIXTURES / "project_jsonly"),
            "--output", str(custom_out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert custom_out.exists()
    data = json.loads(custom_out.read_text())
    assert "libraries" in data
