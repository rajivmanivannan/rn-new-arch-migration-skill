A Claude Code skill that audits your bare React Native project for New Architecture readiness and generates a structured, prioritized migration plan — as both a Markdown report and a styled PDF.

---

## What it does

Drop this skill into your Claude Code setup, point it at a bare React Native project, and ask Claude to run a New Architecture audit. It scans your entire codebase — dependencies, JS/TS source, iOS native files, and Android native files — then writes a date-stamped `MIGRATION_AUDIT_YYYYMMDD.md` to your project root. A styled PDF is generated on request after the Markdown report is delivered.

The report tells you:

- Which npm packages will block New Arch and what to replace them with
- Every Bridge-era pattern in your JS/TS source, with file and line number
- Every `RCTBridgeModule`, `RCT_EXPORT_METHOD`, `ViewManager`, and related pattern in your iOS code
- Every `@ReactMethod`, `ReactContextBaseJavaModule`, and related pattern in your Android code
- Which findings must be rewritten before enabling New Arch vs. which can run under the interop layer
- An **Effort Estimate** — a plain time range and tier (Low / Moderate / High / Very High) that any developer or stakeholder can immediately understand
- A **Progress delta** when re-run on a project with a previous audit (resolved vs. remaining vs. new)

---

## What's included

```
rn-new-arch-migration/
├── SKILL.md                        ← Claude Code skill instructions
├── scripts/
│   ├── check_libs.py               ← Parallel library compatibility checker (live lookup)
│   └── generate_pdf.py             ← Styled PDF generator (reportlab)
└── references/
    └── library-compat.md           ← Human-readable compat reference (documentation only)
```

---

## How library checking works

Library classification uses a fast, token-efficient pipeline — Claude never wastes reasoning tokens on HTTP responses:

```bash
python3 scripts/check_libs.py --project-root .
```

**Resolution order per package:**

| Step | Source | Speed |
|------|--------|-------|
| 1 | `PURE_JS` set (lodash, axios, zustand, RN core, tooling…) | Instant — skipped silently |
| 2 | reactnative.directory search API — live, per-package | Network — always fresh |
| 3 | npm registry | Network — pure-JS heuristic fallback |

All packages are checked **in parallel** (10 workers). A project with 80 deps typically completes in 5–15 seconds.

There are no manual overrides — every native library is looked up live so results always reflect the current state of reactnative.directory.

### What gets auto-detected

- **Pure JS** — packages with no native code are silently skipped (no table row, no tokens wasted)
- **Unmaintained** — packages marked unmaintained on reactnative.directory are flagged ❌
- **Unknown** — packages not found in the directory or npm are marked ❓ for manual verification

---

## Output files

Output files use a date suffix so every audit run is preserved and delta mode can compare them:

```
MIGRATION_AUDIT_20260320.md    ← Always generated — full report, readable in any Markdown viewer
MIGRATION_AUDIT_20260320.pdf   ← Generated on request — styled PDF for sharing with stakeholders
```

The PDF includes: cover page with meta chips, table of contents, executive summary with metric cards, dependency audit tables, JS/TS and native findings, phased action plan, and Effort Estimate with rationale.

> **Audit Metadata** (model, token estimates, scan stats) is appended to the Markdown only — intentionally omitted from the PDF.

---

## Delta / progress mode

When re-running the audit on a project with a previous `MIGRATION_AUDIT_*.md`, the skill automatically diffs findings and prepends a Progress Summary:

```
Previous audit: MIGRATION_AUDIT_20260301.md  (Effort: High)
Current  audit: MIGRATION_AUDIT_20260320.md  (Effort: Moderate)

Resolved (8):   ✅ react-native-snap-carousel removed
                ✅ IOS_BRIDGE_MODULE ios/OldModule.m — fixed
New (2):        🆕 NativeModules.NewFeature in src/feature.ts:42
Remaining (14): ⏳ IOS_BRIDGE_MODULE ios/AcmePayModule.m

Progress: Effort level improved from High → Moderate
```

---

## Monorepo support

The skill detects `workspaces` in `package.json` or `packages/` / `apps/` directories and scans each sub-package independently. The combined report has a workspace summary table followed by per-package audit sections.

---

## What gets scanned

| Layer | What's checked |
|-------|----------------|
| `package.json` | All native dependencies via `check_libs.py` — parallel, live lookup |
| `src/`, `app/`, `screens/`, `components/` | `NativeModules`, `requireNativeComponent`, `NativeEventEmitter`, `DeviceEventEmitter` |
| `ios/` (`.m`, `.mm`, `.swift`) | `RCTBridgeModule`, `RCT_EXPORT_MODULE`, `RCT_EXPORT_METHOD`, `RCTViewManager`, `.bridge` access |
| `android/` (`.java`, `.kt`) | `ReactContextBaseJavaModule`, `@ReactMethod`, `@ReactProp`, `ViewGroupManager`, `ReactPackage` |

Excludes: `node_modules/`, `Pods/`, `build/`, `DerivedData/`, `__tests__/`, `coverage/`

---

## Effort Estimate

The audit classifies migration effort into a plain label and time range that any engineer or stakeholder can interpret immediately:

| Label | Time range | When assigned |
|-------|-----------|---------------|
| Low | < 10 days | No blocking libs, no in-house native modules, minor bridge patterns |
| Moderate | 10–20 days | 0–1 blocking libs, 1 native module rewrite, several interop dependencies |
| High | 20–40 days | 1–2 blocking libs or 2 native module rewrites or many bridge patterns |
| Very High | 40+ days | 3+ blocking libs or 3+ in-house native module rewrites |

> **Note:** Effort covers in-house work only. Vendor native modules (payment gateways, analytics SDKs, etc.) are reported separately — the team cannot rewrite those.

Re-run the audit after each sprint to reassess — effort label should drop as blockers are resolved.

---

## Interop vs. rewrite

- **`[BLOCKING]`** — must be resolved before setting `newArchEnabled=true`. Includes in-house `RCTBridgeModule` implementations, `ViewManager` subclasses, and libraries with no New Arch support.
- **`[INTEROP-OK]`** — can temporarily run under React Native's interop layer (RN 0.73+). The interop layer may be removed in a future RN version — these are deferred, not resolved.

---

## Installation

### Option A — Manual install (personal)

```bash
git clone https://github.com/rajivmanivannan/rn-new-arch-migration-skill.git

# Personal Claude skills directory
cp -r rn-new-arch-migration-skill ~/.claude/skills/
```

### Option B — Project-level install

```bash
# Inside your RN project root
mkdir -p .claude/skills
cp -r path/to/rn-new-arch-migration-skill .claude/skills/
```

### First-run setup

**Install PDF dependency** (only needed if you want PDF output):

```bash
pip install reportlab
```

> The library checker fetches live data from reactnative.directory on every run — no setup needed, always accurate.

---

## Usage

Open Claude Code inside your React Native project and use any of these prompts:

```
Audit this project for New Architecture readiness
```
```
Check if my native modules are compatible with New Arch
```
```
Generate a React Native migration plan for this repo
```
```
Is this RN app ready to enable newArchEnabled?
```
```
Scan my iOS and Android native code for TurboModule migration issues
```

Claude will detect the skill, run `check_libs.py` to classify all dependencies efficiently, scan the source and native layers, and write both output files.

---

## Prerequisites

- **React Native 0.73+** — the skill flags an upgrade requirement if you're below this
- **Bare React Native** — Expo managed workflow has a separate migration path not covered here
- **Claude Code** with file system access to the project root
- **Python 3.8+** — required for `check_libs.py` and `generate_pdf.py`
- **reportlab** — required for PDF generation (`pip install reportlab`)

---

## Scope and limitations

- **Audit only** — the skill reads and reports. It does not modify your code.
- **Pattern-based scanning** — static pattern matching, not full AST analysis. Complex dynamic `NativeModules` patterns (e.g. computed module names) may not be caught.
- **No Expo managed workflow** — Expo has a separate New Arch migration path not covered here.
- **Network required** — the library checker fetches live data from reactnative.directory on every run. Air-gapped environments cannot use the dependency audit step.

---

## License

MIT — see [LICENSE](./LICENSE)

---

✦ Co-crafted with AI · [@rajivmanivannan](https://rajivmanivannan.dev)
