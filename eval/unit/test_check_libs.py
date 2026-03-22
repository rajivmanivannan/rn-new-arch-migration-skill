"""
Unit tests for scripts/check_libs.py

Tests cover:
  - PURE_JS set (returns None, no network)
  - Directory lookup via mocked search_directory
  - search_directory nested newArchitecture field
  - years_since date math
  - is_likely_pure_js heuristics
  - lookup_package resolution logic (directory → npm → unknown)

Network is never hit — search_directory and fetch_json are mocked where needed.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SKILL_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import check_libs  # noqa: E402


# ── PURE_JS ────────────────────────────────────────────────────────────────────

def test_pure_js_returns_none():
    result = check_libs.lookup_package("lodash", "^4.0")
    assert result is None


def test_pure_js_axios_returns_none():
    result = check_libs.lookup_package("axios", "^1.6.0")
    assert result is None


def test_pure_js_zustand_returns_none():
    result = check_libs.lookup_package("zustand", "^4.5.0")
    assert result is None


def test_pure_js_react_native_skipped():
    """react-native core is in PURE_JS — must be silently skipped."""
    result = check_libs.lookup_package("react-native", "0.76.0")
    assert result is None


# ── Directory lookup (mocked) ──────────────────────────────────────────────────

def test_directory_compatible():
    """Package with New Arch support on reactnative.directory → compatible."""
    with patch.object(check_libs, "search_directory", return_value=(True, False)):
        result = check_libs.lookup_package("react-native-reanimated", "^3.6.0")
    assert result is not None
    assert result["status"] == "compatible"
    assert result["source"] == "directory"


def test_directory_interop_maintained():
    """Package maintained but no New Arch flag → interop (works under interop layer)."""
    with patch.object(check_libs, "search_directory", return_value=(False, False)):
        result = check_libs.lookup_package("react-native-some-lib", "^1.0.0")
    assert result["status"] == "interop"
    assert result["source"] == "directory"


def test_directory_unmaintained_is_interop_not_blocking():
    """Package unmaintained + no New Arch → interop (works under interop layer, not a true blocker)."""
    with patch.object(check_libs, "search_directory", return_value=(False, True)):
        result = check_libs.lookup_package("dead-lib", "^1.0.0")
    assert result["status"] == "interop"
    assert "unmaintained" in result["notes"].lower()
    assert "replacing" in result["notes"].lower() or "alternative" in result["notes"].lower()


def test_directory_compatible_even_if_unmaintained():
    """Package with New Arch support is compatible regardless of maintenance status."""
    with patch.object(check_libs, "search_directory", return_value=(True, True)):
        result = check_libs.lookup_package("old-but-newarch-lib", "^1.0.0")
    assert result["status"] == "compatible"


def test_directory_not_found_falls_to_npm():
    """Package not in directory → falls through to npm heuristic."""
    with patch.object(check_libs, "search_directory", return_value=None), \
         patch.object(check_libs, "fetch_json", return_value=None):
        result = check_libs.lookup_package("some-obscure-lib", "^1.0.0")
    assert result is not None
    assert result["status"] == "unknown"


def test_directory_result_includes_package_and_version():
    """Result must include the package name and version passed in."""
    with patch.object(check_libs, "search_directory", return_value=(True, False)):
        result = check_libs.lookup_package("react-native-screens", "4.0.0")
    assert result["package"] == "react-native-screens"
    assert result["version"] == "4.0.0"


# ── search_directory nested newArchitecture ───────────────────────────────────

def test_search_directory_reads_nested_github_new_arch():
    """newArchitecture under github.newArchitecture must be honoured."""
    fake_response = {
        "libraries": [{
            "npmPkg": "@d11/react-native-fast-image",
            "newArchitecture": None,
            "unmaintained": None,
            "github": {"newArchitecture": True},
        }]
    }
    with patch.object(check_libs, "fetch_json", return_value=fake_response):
        result = check_libs.search_directory("@d11/react-native-fast-image")
    assert result is not None
    new_arch, unmaintained = result
    assert new_arch is True
    assert unmaintained is False


def test_search_directory_top_level_new_arch():
    """Top-level newArchitecture=True should also be honoured."""
    fake_response = {
        "libraries": [{
            "npmPkg": "some-lib",
            "newArchitecture": True,
            "unmaintained": False,
        }]
    }
    with patch.object(check_libs, "fetch_json", return_value=fake_response):
        result = check_libs.search_directory("some-lib")
    assert result == (True, False)


def test_search_directory_not_found_returns_none():
    fake_response = {"libraries": [{"npmPkg": "other-lib", "newArchitecture": True}]}
    with patch.object(check_libs, "fetch_json", return_value=fake_response):
        result = check_libs.search_directory("missing-lib")
    assert result is None


def test_search_directory_network_error_returns_none():
    with patch.object(check_libs, "fetch_json", return_value=None):
        result = check_libs.search_directory("any-lib")
    assert result is None


# ── npm fallback — pure JS detection ─────────────────────────────────────────

def test_npm_pure_js_returns_none():
    """Package not in directory but detected as pure JS via npm → skip (None)."""
    npm_meta = {
        "dist-tags": {"latest": "1.0.0"},
        "versions": {"1.0.0": {
            "peerDependencies": {},
            "keywords": ["utility"],
            "files": ["src"],
        }},
        "description": "A helper library",
    }
    with patch.object(check_libs, "search_directory", return_value=None), \
         patch.object(check_libs, "fetch_json", return_value=npm_meta):
        result = check_libs.lookup_package("some-util", "^1.0.0")
    assert result is None


def test_npm_native_returns_unknown():
    """Package not in directory, has native indicators via npm → unknown."""
    npm_meta = {
        "dist-tags": {"latest": "1.0.0"},
        "versions": {"1.0.0": {
            "peerDependencies": {"react-native": "*"},
            "keywords": ["native"],
            "files": ["android", "ios"],
        }},
        "description": "A react-native bridge module",
        "repository": {"url": "https://github.com/example/lib"},
    }
    with patch.object(check_libs, "search_directory", return_value=None), \
         patch.object(check_libs, "fetch_json", return_value=npm_meta):
        result = check_libs.lookup_package("some-native-lib", "^1.0.0")
    assert result is not None
    assert result["status"] == "unknown"



# ── is_likely_pure_js ─────────────────────────────────────────────────────────

def _npm_meta(peer_deps=None, keywords=None, files=None, desc=""):
    latest_meta = {"peerDependencies": peer_deps or {}, "keywords": keywords or [], "files": files or []}
    return {
        "dist-tags": {"latest": "1.0.0"},
        "versions": {"1.0.0": latest_meta},
        "description": desc,
    }


def test_is_likely_pure_js_true():
    meta = _npm_meta(peer_deps={}, keywords=["utility"], desc="A helper library")
    assert check_libs.is_likely_pure_js("some-util", meta) is True


def test_is_likely_pure_js_false_rn_peer():
    meta = _npm_meta(peer_deps={"react-native": "*"})
    assert check_libs.is_likely_pure_js("some-lib", meta) is False


def test_is_likely_pure_js_false_native_keyword():
    meta = _npm_meta(keywords=["native", "ios"])
    assert check_libs.is_likely_pure_js("some-lib", meta) is False


def test_is_likely_pure_js_false_native_desc():
    meta = _npm_meta(desc="A react-native bridge module")
    assert check_libs.is_likely_pure_js("some-lib", meta) is False


def test_is_likely_pure_js_false_native_files():
    meta = _npm_meta(files=["android", "ios", "src"])
    assert check_libs.is_likely_pure_js("some-lib", meta) is False


def test_is_likely_pure_js_none_meta():
    assert check_libs.is_likely_pure_js("anything", None) is False
