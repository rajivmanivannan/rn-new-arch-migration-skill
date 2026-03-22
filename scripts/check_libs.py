#!/usr/bin/env python3
"""
check_libs.py — React Native New Architecture library compatibility checker

Resolution order for each package:
  1. PURE_JS set   → skip entirely (return None) — pure JS / RN core / tooling
  2. reactnative.directory search API → live, per-package, always fresh
  3. npm registry  → pure-JS heuristic fallback for anything not in directory

Always fetches live from reactnative.directory — no overrides, no stale data.

Usage:
    python3 check_libs.py --project-root /path/to/rn-project
    python3 check_libs.py --project-root . --output report.json
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── Pure-JS / RN core / tooling — skip silently, zero network calls ───────────
# Only add packages that are guaranteed to have NO native code.
# Everything else is looked up live on reactnative.directory for accuracy.
PURE_JS = {
    # State management / data fetching
    "lodash", "axios", "date-fns", "moment", "immer", "zustand", "jotai",
    "recoil", "redux", "@reduxjs/toolkit", "react-query", "swr",
    "redux-saga", "redux-thunk", "redux-observable", "redux-persist",
    # Forms / validation
    "formik", "react-hook-form", "yup", "zod",
    # i18n
    "i18next", "react-i18next", "i18n-js",
    # Utilities — pure JS, no native code
    "uuid", "nanoid", "clsx", "classnames", "ramda",
    "currency.js", "libphonenumber-js",
    "react-native-global-props", "deprecated-react-native-prop-types",
    # Tanstack
    "@tanstack/react-query", "@tanstack/react-table", "@tanstack/react-virtual",
    # Core React
    "react", "react-native-web",
    # React Native core — skip (not a third-party native library)
    "react-native",
    # Build / bundler tooling
    "typescript", "prettier", "eslint", "@babel/core", "@babel/runtime",
    "metro", "metro-config", "metro-resolver",
    "hermes-profile-transformer", "jetifier", "ts-migrate",
    "eslint-config-airbnb", "eslint-config-react-native",
    # RN community CLI tools — build-time only, no native runtime
    "@react-native-community/cli",
    "@react-native-community/cli-platform-android",
    "@react-native-community/cli-platform-ios",
    "@react-native-community/cli-tools",
    # RNX kit — dependency alignment tooling only
    "@rnx-kit/align-deps", "@rnx-kit/dep-check",
    # Test utilities
    "jest", "@testing-library/react-native", "@testing-library/jest-native",
    "babel-jest", "ts-jest", "react-test-renderer",
    "husky", "mockdate", "fishery",
    # Sentry JS-only core (no native code — @sentry/react-native has native)
    "@sentry/core", "@sentry/browser", "@sentry/hub", "@sentry/tracing",
}

# Package name prefixes that are always pure JS / tooling — skip silently.
PURE_JS_PREFIXES = (
    "@types/",      # TypeScript type definitions — zero runtime code
    "@tsconfig/",   # Shared tsconfig presets — dev-time only
    "@react-native/",  # RN framework internals (babel-preset, metro-config, etc.)
)

NATIVE_KEYWORDS = {
    "react-native", "native", "android", "ios", "jsi", "turbomodule",
    "fabric", "nativemodule", "objc", "kotlin", "java", "swift", "c++"
}


# ── Network helpers ────────────────────────────────────────────────────────────

def fetch_json(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rn-arch-checker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def search_directory(pkg_name):
    """
    Search reactnative.directory for a specific package.
    Returns (new_arch: bool, unmaintained: bool) or None if not found / network error.

    The API has two locations for newArchitecture:
      - lib["newArchitecture"]          — top-level, manually curated
      - lib["github"]["newArchitecture"] — auto-detected from the repo
    We treat either as true.
    """
    encoded = urllib.parse.quote(pkg_name, safe="")
    data = fetch_json(
        f"https://reactnative.directory/api/libraries?search={encoded}",
        timeout=10,
    )
    if not data:
        return None
    for lib in data.get("libraries", []):
        npm_pkg = lib.get("npmPkg") or lib.get("npmPackageName", "")
        if npm_pkg == pkg_name:
            new_arch = (
                lib.get("newArchitecture")
                or (lib.get("github") or {}).get("newArchitecture")
                or False
            )
            unmaintained = lib.get("unmaintained") or False
            return bool(new_arch), bool(unmaintained)
    return None



def is_likely_pure_js(pkg_name, npm_meta):
    if npm_meta is None:
        return False
    latest_ver  = npm_meta.get("dist-tags", {}).get("latest", "")
    latest_meta = npm_meta.get("versions", {}).get(latest_ver, {})
    peers       = set((latest_meta.get("peerDependencies") or {}).keys())
    if "react-native" in peers:
        return False
    keywords = [k.lower() for k in (latest_meta.get("keywords") or [])]
    desc     = (npm_meta.get("description") or "").lower()
    if any(kw in " ".join(keywords) + " " + desc for kw in NATIVE_KEYWORDS):
        return False
    files = [f.lower() for f in (latest_meta.get("files") or [])]
    if any(d in files for d in ["android", "ios", "native"]):
        return False
    return True


# ── Per-package lookup ─────────────────────────────────────────────────────────

def lookup_package(pkg_name, pkg_version):
    # 1. Pure JS / RN core / tooling — skip silently
    if pkg_name in PURE_JS:
        return None
    if any(pkg_name.startswith(prefix) for prefix in PURE_JS_PREFIXES):
        return None

    # 2. Live search on reactnative.directory — always fresh, always accurate
    dir_result = search_directory(pkg_name)
    if dir_result is not None:
        new_arch, unmaintained = dir_result
        if new_arch:
            # Confirmed New Arch support — compatible regardless of maintenance status
            status = "compatible"
            notes  = "New Arch confirmed via reactnative.directory."
        elif unmaintained:
            # Unmaintained + no New Arch flag — still works under interop layer,
            # but will never get a proper TurboModule/Fabric rewrite.
            # This is a maintenance risk, not a technical blocker.
            status = "interop"
            notes  = "Unmaintained — no New Arch support and unlikely to receive updates. Works under interop layer (RN 0.73+) but consider replacing with an actively maintained alternative."
        else:
            # Maintained but not yet flagged as New Arch ready — works under interop layer
            status = "interop"
            notes  = "Not yet New Arch compatible per reactnative.directory — works under interop layer (RN 0.73+). Monitor for updates."
        return {"package": pkg_name, "version": pkg_version,
                "status": status, "notes": notes,
                "source": "directory", "replacement": ""}

    # 3. npm registry — pure-JS heuristic only, never marks blocking
    npm = fetch_json(
        f"https://registry.npmjs.org/{urllib.parse.quote(pkg_name, safe='')}"
    )
    if npm:
        if is_likely_pure_js(pkg_name, npm):
            return None
        latest_ver = npm.get("dist-tags", {}).get("latest", "")
        repo_url   = (npm.get("versions", {}).get(latest_ver, {})
                      .get("repository", {}).get("url", ""))
        return {"package": pkg_name, "version": pkg_version,
                "status": "unknown",
                "notes": f"Not in reactnative.directory — verify manually. Repo: {repo_url}",
                "source": "npm_fallback", "replacement": ""}

    # 4. Nothing worked
    return {"package": pkg_name, "version": pkg_version,
            "status": "unknown",
            "notes": "Could not fetch package data — verify manually",
            "source": "none", "replacement": ""}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--output",       default=None)
    ap.add_argument("--workers",      type=int, default=10)
    args = ap.parse_args()

    project_root  = Path(args.project_root).resolve()
    pkg_json_path = project_root / "package.json"
    if not pkg_json_path.exists():
        print(f"ERROR: package.json not found at {pkg_json_path}", file=sys.stderr)
        sys.exit(1)

    try:
        pkg_json = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print("ERROR: Cannot parse package.json — fix JSON syntax errors before running the audit.", file=sys.stderr)
        print(f"  Detail: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not read package.json: {e}", file=sys.stderr)
        sys.exit(1)

    project_name = pkg_json.get("name", project_root.name)

    all_deps = {}
    all_deps.update(pkg_json.get("dependencies", {}))
    all_deps.update(pkg_json.get("devDependencies", {}))
    if not all_deps:
        print("ERROR: No dependencies found in package.json", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else project_root / "lib_report.json"

    print(f"\n🔍  Scanning {len(all_deps)} packages in {project_name}...")
    print(f"    Source  : reactnative.directory (live)")
    print(f"    Workers : {args.workers}")
    print()

    start   = time.time()
    results = []
    skipped = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(lookup_package, name, ver): name
            for name, ver in all_deps.items()
        }
        for future in as_completed(futures):
            pkg_name = futures[future]
            try:
                result = future.result()
                if result is None:
                    skipped += 1
                else:
                    results.append(result)
                    sym = {"compatible": "✅", "interop": "⚠️ ", "unknown": "❓"}.get(result["status"], "·")
                    src = f"[{result['source']}]" if result["source"] != "directory" else ""
                    print(f"  {sym}  {pkg_name:<52} {result['status']:<12} {src}")
            except Exception as e:
                print(f"  💥  {pkg_name:<52} ERROR: {e}")

    elapsed = time.time() - start

    order = {"unknown": 0, "interop": 1, "compatible": 2}
    results.sort(key=lambda r: (order.get(r["status"], 9), r["package"]))

    counts = {"compatible": 0, "interop": 0, "unknown": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    report = {
        "generated_at":    datetime.now().isoformat(),
        "project":         project_name,
        "total_deps":      len(all_deps),
        "native_checked":  len(results),
        "pure_js_skipped": skipped,
        "elapsed_seconds": round(elapsed, 1),
        "summary":         counts,
        "libraries":       results,
    }
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print()
    print(f"{'─'*60}")
    print(f"  ✅  Compatible  : {counts['compatible']}")
    print(f"  ⚠️   Interop-OK  : {counts['interop']}")
    print(f"  ❓  Unknown     : {counts['unknown']}")
    print(f"  ⏭️   Skipped     : {skipped}  (pure JS / RN core / tooling)")
    print(f"{'─'*60}")
    print(f"  ⏱️   Completed in {elapsed:.1f}s")
    print(f"  📄  Report      : {output_path}")
    print()
    print(f"REPORT_PATH={output_path}")


if __name__ == "__main__":
    main()
