---
name: workflow
description: 3-Phase (Planner -> Generator -> Evaluator) workflow with selectable single-agent or multi-agent persona mode. Use for development tasks (feature work, bug fixes, maintenance) AND non-development tasks (planning data processing, document generation, analysis) that benefit from structured planning, implementation, and review.
---

# Agent Harness Workflow — Thin Orchestrator (v2)

You are a **state-machine orchestrator**. Your role is:
1. Manage phase transitions via `state.json`
2. Dispatch sub-agents with minimal context
3. Parse 1-line return values
4. Present gates to the user

**You do NOT**: read intermediate artifacts (proposals, critiques, plans, reviews), accumulate sub-agent output in context, or make quality judgments about code. Sub-agents handle all domain work; you handle transitions.

## Sub-agent Return Value Rules

When a sub-agent returns:
1. Read only the **first line** (up to first newline) for state decisions
2. Extract keywords: `"FAIL"`, `"PASS"`, `"generated"`, `"changed"`, `"written"`
3. Use the first line as the progress message shown to the user
4. **Ignore all remaining text** — do not analyze, reference, or include it in subsequent prompts

**1-line return parse failure**: If the return value does not match the expected format (`<keyword> — <summary>`), treat as `confidence: Unknown` and print `[harness] ⚠ 1-line return parse failed — fallback: confidence Unknown`. For Auto-fix Proposer specifically, the expected fallback format is: `auto_fix_patch written — confidence: Unknown — <reason>`.

## Version & Compatibility

This is **state.json v2** (version `"2.0"`). When loading an existing state.json:
- If `version` field is missing → treat as **v1**. Run v1 logic (see below).
- If `version` is `"2.0"` → run v2 logic defined in this file.
- **Do NOT migrate v1 sessions to v2.** v1 sessions continue with v1 behavior.

### v1 Logic Summary (for sessions without version field)

v1 uses a simpler flow without the thin orchestrator pattern:
- Phases: `plan_ready → gen_ready → verify_ready → verifying → verify_done → eval_ready → completed`
- The orchestrator directly accumulates sub-agent results (no 1-line return constraint)
- No `run_style` — always auto mode
- No Layer 2 structural verification — Evaluator runs Layer 3 only
- Verify step may be absent (pre-v7.1 sessions without `verify` field → skip verify entirely)
- Resume v1 session by jumping to the v1 phase's corresponding step in the original flow

### v1 → v2 Phase Mapping (for reference only)

| v1 phase | v2 equivalent | Notes |
|----------|---------------|-------|
| `plan_ready` | `plan_ready` | same |
| `gen_ready` | `generate_ready` | renamed |
| `eval_ready` | `evaluate_ready` | renamed |
| `completed` | `completed` | same |
| `verify_ready` | `verify_ready` | v7.1, kept |
| `verifying` | `verifying` | v7.1, kept |
| `verify_done` | `verify_done` | v7.1, kept |

## Zero-Setup Environment Detection

At startup, detect whether the current directory is inside a git repository:
```
git rev-parse --is-inside-work-tree 2>/dev/null
```
- If succeeds → `has_git = true`
- If fails → `has_git = false`

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json.

**All user-facing communication** in `user_lang`: progress updates, questions, confirmations, errors, spec sections, QA narrative, commit messages (if has_git).

**Stays in English:** template instructions, state.json field names, file names, git branch names.

**Re-detection:** On every user message, check if language changed. If so, update `user_lang`.

## Standard Status Format

Read `.harness/state.json` and print (in `user_lang`):
```
[harness]
  Task   : <task>
  Mode   : <single | standard | multi>
  Model  : <model_config preset name>
  Style  : <auto | phase | step>
  Phase  : <phase label>
  Round  : <round> / <max_rounds>
  Branch : <branch>          ← omit if has_git == false
  Scope  : <scope>
```

Phase labels:
- `plan_ready` → "Plan — ready"
- `planning` → "Plan — in progress"
- `plan_done` → "Plan — complete"
- `generate_ready` → "Generate — ready"
- `generating` → "Generate — in progress"
- `generate_done` → "Generate — complete"
- `verify_ready` → "Verify — ready"
- `verifying` → "Verify — running checks"
- `verify_done` → "Verify — complete"
- `evaluate_ready` → "Evaluate — ready"
- `evaluating` → "Evaluate — in progress"
- `evaluate_done` → "Evaluate — complete"
- `completed` → "Completed"

## Session Recovery

Before starting a new task, check if `.harness/state.json` exists:

1. Read state.json. Check `skill` field (if present):
   - If `skill` field exists and is NOT `"workflow"` → warn user (in detected language): "A `/{skill}` skill session is active in this directory." Ask via AskUserQuestion: header "Session Conflict", question "A `/{skill}` session exists. Delete it and start /workflow?", options: "Delete and start" / "Delete .harness/ and proceed with /workflow", "Cancel" / "Keep existing session and halt". If "Cancel" → halt. If "Delete and start" → delete `.harness/`, proceed to Step 1.
   - If `skill` field is `"workflow"` or missing → continue below.

2. Check `version` field:
   - **Missing** → v1 session. Print status with `[harness] Previous session detected (v1).`, then run v1 recovery logic (pre-v8 behavior). Do NOT apply v2 state machine.
   - **`"2.0"`** → v2 session. Continue below.

3. Print status in standard format, prefixed with `[harness] Previous session detected.`
4. Restore `model_config` from state.json. Apply to all subsequent sub-agent launches.
5. Restore `conventions` from state.json. If value starts with `"file:"`, verify the referenced file exists. If file missing, set `conventions → null` (will trigger Step 1.5 on resume).
6. If `has_git` is not in state.json, re-detect and store.
7. Ask the user via AskUserQuestion (in `user_lang`):
   - header: "Session"
   - question: "[harness] Previous session detected. [standard status]. Resume, restart, or stop?"
   - options:
     - "Resume" / "Continue from {phase}"
     - "Restart" / "Delete .harness/ and start fresh"
     - "Stop" / "Delete .harness/ and halt"

   Actions:
   - **Resume**: Before jumping to any step, run Safety Guard re-validation:
     - Read `docs_path` directly from state.json. **Do NOT recompute from `cli_flags.output_dir`** — `cli_flags` is for audit/record only.
     - Run `validate_path(docs_path, kind=output_dir)`: slug validation + relative path + reserved name check.
     - If validation fails: print `[harness] ⚠ Recovered docs_path failed validation: <path>` and treat as Restart.

     Then jump to the state matching `phase`:
     - `plan_ready` → Step 1.5 (Convention Scan) if `conventions` is `null` (not yet executed), else Step 2 (Plan). Note: `"skipped"` means user already decided — go to Step 2. If `conventions` starts with `"file:"` but the file does not exist, treat as `null` and re-run Step 1.5.
     - `planning` / `plan_done` → Step 3 (Gate) if spec.md exists, else Step 2
     - `generate_ready` → Step 4 (Generate)
     - `generating` / `generate_done` → Step 5 (Verify)
     - `verify_ready` / `verifying` → Step 5 (Verify), reset retries to 0
     - `verify_done`:
       - if `state.autofix == null` → Step 5 (Verify), reset `layer1_retries` to 0 (existing behavior)
       - if `autofix.applied == "proposed"` → Step 5 "2nd HARD-GATE" direct re-entry (I3; do NOT reset retries)
       - if `autofix.applied == "applied"` → Step 5 re-verify from Layer 1 (retries from state.json, no reset)
       - if `autofix.applied` is `"stopped"` or `"rejected"` → Step 5 "1st HARD-GATE" (Auto-fix HIDE per I2; `layer1_retries` unchanged — I4 clamp applies to "stopped")
     - `evaluate_ready` → Step 6 (Evaluate)
     - `evaluating` / `evaluate_done` → Step 7 (Verdict)
     - `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` and proceed to Step 1
   - **Stop**: Delete `.harness/` and halt

If `.harness/state.json` does not exist, proceed to Step 1.

## run_style (Execution Mode)

Three execution styles control how phases progress:

| Style | Behavior | Session end points |
|-------|----------|-------------------|
| `auto` | Automatic progression, user gates at plan_done and evaluate_done(FAIL) only | `completed` |
| `phase` | Stop at each `*_done` state, resume in next session | `plan_done`, `generate_done`, `verify_done`, `evaluate_done` |
| `step` | Execute only the specified step, then stop | Immediately after step |

### CLI Parsing

```
/workflow "task description"              → auto (default)
/workflow plan "task description"         → phase mode, plan step
/workflow generate                        → phase mode, generate step
/workflow verify                          → step mode, verify only
/workflow evaluate                        → step mode, evaluate only
/workflow --mode single "task"            → auto + single mode
/workflow --model-config balanced "task"  → auto + balanced preset
```

When state.json exists and `/workflow` is called with no arguments:
→ Read phase, suggest next step: e.g. "Plan complete. Run generate?"

### Step Mode Prerequisites

| Step | Required files | Required phase (minimum) | Missing action |
|------|---------------|-------------------------|----------------|
| `/workflow plan` | (none) | (new session OK) | Normal start |
| `/workflow generate` | spec.md | after `plan_done` | Error: "Run plan first" |
| `/workflow verify` | changes.md | after `generate_done` | Error: "Run generate first" |
| `/workflow evaluate` | spec.md + changes.md + verify_report.md | after `verify_done` | Error: "Run verify first" |

---

## State Machine

### State Transition Diagram

```
plan_ready → planning → plan_done → [User Gate] → generate_ready
  → generating → generate_done → verify_ready → verifying → verify_done
  → evaluate_ready → evaluating → evaluate_done → [Verdict Gate]
  → completed

Retry loops:
  verify_done(FAIL) + retries<3 → generating → generate_done → verifying → ...
  evaluate_done(FAIL) + user Fix → generating → generate_done → verifying → ...
```

### Transition Rules

- `*_ready` → `*ing`: sub-agent dispatch (immediate)
- `*ing` → `*_done`: sub-agent completion
- `*_done` → next `*_ready`: auto mode = automatic / phase mode = next session
- Phase mode can end session at: `plan_done`, `generate_done`, `verify_done`, `evaluate_done`

### Auto-fix State Transition Table

| `autofix.applied` | Meaning |
|---|---|
| `null` (idle) | Auto-fix not yet attempted |
| `"proposed"` | Proposer dispatched, awaiting 2nd HARD-GATE |
| `"applied"` | Patch applied, re-verification in progress |
| `"rejected"` | User rejected proposal |
| `"stopped"` | Patch applied but re-verification failed |

**Transitions:**

| From | Event | To |
|---|---|---|
| `null` (idle) | 1st HARD-GATE "Auto-fix" selected | `proposed` |
| `proposed` | User "Apply patch" (2nd HARD-GATE) | `applied` |
| `proposed` | User "Reject" (2nd HARD-GATE) | `rejected` |
| `applied` | Re-verify PASS | (cleared — continues to Step 6) |
| `applied` | Re-verify FAIL | `stopped` |

**Invariants (I1–I4):**

- **I1**: `verify.autofix_attempted == true ⟺ autofix != null ∧ autofix.applied ≠ "proposed"`
- **I2**: 1st HARD-GATE Auto-fix option is visible only when `verify.autofix_attempted == false AND state.autofix == null`
- **I3**: On session resume, if `autofix.applied == "proposed"` → re-enter 2nd HARD-GATE directly (skip 1st GATE)
- **I4**: `autofix.applied == "stopped"` ⟹ `layer1_retries = min(layer1_retries, 3)` (clamp — no further increment)

---

## Workflow Steps

### Step 1: Setup

1. **Detect user language** from task description. Store as `user_lang`.
2. **Parse CLI arguments**:
   - Bare task → `run_style: "auto"`
   - `plan|generate` prefix → `run_style: "phase"` (multi-step progression)
   - `verify|evaluate` prefix → `run_style: "step"` (single step only)
   - `--mode single|standard|multi` → set mode
   - `--model-config <preset>` → set model config
   - `--lint-cmd <cmd>` → override lint_cmd
   - `--type-check-cmd <cmd>` → override type_check_cmd
   - `--verifier-model <haiku|sonnet|opus>` → override verifier model (default: haiku). **Validation**: if value is not one of `haiku`, `sonnet`, `opus` → halt with error: "Invalid --verifier-model value. Allowed: haiku, sonnet, opus."
   - `--output-dir <path>` → override output base directory (default: `docs/harness`). **Validation** — apply `validate_path(path, kind=output_dir)` (see §Architecture Principles §Path Validator):
     - **Step 0** (before normalization): Empty string → halt with error: "output-dir cannot be empty."
     - **Step 1** Normalize: `\` → `/` (always, OS-independent). UNC pattern (`\\server\…` or `//server/…`) → halt with error: "UNC paths are not allowed."
     - **Step 2** Absolute path: matches `^/` or `^[A-Za-z]:/` → halt with error: "output-dir must be a relative path."
     - **Step 3** Segment `..`: `path.split("/")` — if any segment `== ".."` → halt with error: "output-dir must not contain '..'." (segment-exact check, not substring)
     - **Step 4** Reserved first segment: `path.split("/")[0]` ∈ `{memory, spec, planner, generator, evaluator, verify, harness, .harness, docs}` → halt with error: "output-dir value starts with a reserved directory name." (first segment only — trailing slash stripped first; full-path comparison is NOT performed)
     - If valid: normalize with trailing slash stripped, store in `cli_flags.output_dir`.
3. **Slugify the task:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.
4. **Auto-detect project language and commands.** Scan the working directory:

   | File | Language | Test Command | Build Command |
   |------|----------|-------------|---------------|
   | `build.gradle(.kts)` | java | `./gradlew test` | `./gradlew build` |
   | `pom.xml` | java | `mvn test` | `mvn compile` |
   | `pyproject.toml` / `setup.py` | python | `pytest` | (none) |
   | `package.json` | typescript | `npm test` | `npm run build` |
   | `*.csproj` | csharp | `dotnet test` | `dotnet build` |
   | `go.mod` | go | `go test ./...` | `go build ./...` |
   | `Cargo.toml` | rust | `cargo test` | `cargo build` |

   If none match, set language to "unknown", test/build commands to null.

5. **Auto-detect lint command** (skip if `--lint-cmd` provided). Check in order, stop at first match:

   | # | Detection | Condition | lint_cmd |
   |---|-----------|-----------|----------|
   | 1 | Read `package.json` | `scripts.lint` key exists | `npm run lint` |
   | 2 | Glob | `.eslintrc*` / `eslint.config.*` exists | `npx eslint .` |
   | 3 | Read `pyproject.toml` | `[tool.ruff]` section exists | `ruff check .` |
   | 4 | Glob+Read | `.pylintrc` exists OR `pyproject.toml` has `[tool.pylint]` | `pylint {scope}` |
   | 5 | Glob | `.golangci.yml` / `.golangci.yaml` exists | `golangci-lint run` |
   | 6 | Glob | `Cargo.toml` exists | `cargo clippy` |

   If none match → `null` (SKIPPED during verify).

6. **Auto-detect type-check command** (skip if `--type-check-cmd` provided). Check in order, stop at first match:

   | # | Detection | Condition | type_check_cmd |
   |---|-----------|-----------|----------------|
   | 1 | Glob | `tsconfig.json` exists | `npx tsc --noEmit` |
   | 2 | Glob+Read | `mypy.ini` exists OR `pyproject.toml` has `[tool.mypy]` | `mypy .` |
   | 3 | Glob+Read | `pyrightconfig.json` exists OR `pyproject.toml` has `[tool.pyright]` | `pyright` |
   | 4-6 | — | `*.csproj` / `go.mod` / `Cargo.toml` | null (build includes type-check) |

   If none match → `null` (SKIPPED during verify).

7. **Determine `docs_path`:**
   ```
   output_base = cli_flags.output_dir ?? "docs/harness"
   docs_path = output_base + "/" + <slug> + "/"
   ```
   **Create directories:** `.harness/`, `.harness/planner/`, `.harness/generator/`, `{docs_path}`

   **Immediately after docs_path is determined**, write partial state.json (crash recovery checkpoint):
   ```json
   { "version": "2.0", "task": "<task>", "cli_flags": {...}, "user_lang": "<lang>",
     "has_git": <bool>, "created_at": "<ISO8601>", "docs_path": "<docs_path>", "slug": "<slug>" }
   ```
   Remaining fields (mode, model_config, etc.) are `null` until Step 1.11 final write.

8. **Create git branch (if has_git):** `git checkout -b harness/<slug>`. Skip if `has_git == false`.
9. **Mode selection:** If `--mode` provided, use it. Otherwise, ask via AskUserQuestion (in `user_lang`):
   - header: "Mode"
   - question: "Select workflow mode:"
   - options:
     - "standard (Recommended)" / "2 specialists analyze + synthesize. ~1.5x tokens. Balanced depth"
     - "single" / "1 agent. Fast, token-saving. Best for simple tasks"
     - "multi" / "3 specialists + cross-critique. ~2-2.5x tokens. Deepest analysis"

10. **Model configuration:** If `--model-config` provided, use it. Otherwise, ask via AskUserQuestion (in `user_lang`):
    - header: "Model"
    - question: "Select model configuration for sub-agents:"
    - options:
      - "default" / "Inherit parent model, no changes"
      - "all-opus" / "All sub-agents use Opus (highest quality)"
      - "balanced (Recommended)" / "Sonnet executor + Opus advisor/evaluator (cost-efficient)"
      - "economy" / "Haiku executor + Sonnet advisor/evaluator (max savings)"

    If "Other": parse `executor:<model>,advisor:<model>,evaluator:<model>`. Validate — only `opus`, `sonnet`, `haiku`. Max 3 retries, then default to `balanced`. Fill missing roles from `balanced` defaults.

    Store as `model_config`: `{ "preset": "<name>", "executor": "<model|null>", "advisor": "<model|null>", "evaluator": "<model|null>", "verifier": "<resolved-verifier>" }`.
    For `default` preset: `{ "preset": "default", "verifier": "<resolved-verifier>" }`.

10.5. **Verifier model determination:** `model_config.verifier = cli_flags.verifier_model ?? "haiku"` (CLI flag takes priority; preset default is always `haiku`). Store resolved value in `model_config.verifier`.

    **Backward compat (Session Recovery):** When resuming a v2.0 session that lacks `cli_flags`, `verify.autofix_attempted`, `autofix`, or `docs_path`, resolve missing fields to defaults in memory without writing back to state.json:
    - `cli_flags` → `{ "verifier_model": null, "output_dir": null }`
    - `model_config.verifier` (missing) → `"haiku"`
    - `verify.autofix_attempted` (missing) → `false`
    - `autofix` (missing) → `null`
    - `docs_path` (missing) → `"docs/harness/<slug>/"` (reconstruct from `task` slug)
    This ensures `state.get(field, default)` pattern — KeyError-free resume for all pre-v8.1 sessions.

    **docs_path usage rule**: Always read `docs_path` directly from state.json. Do NOT recompute from `cli_flags.output_dir`. `cli_flags` is for audit/record purposes only. Safety Guard in Session Recovery also uses `docs_path` directly (not recomputed).

11. **Write `.harness/state.json`:**

```json
{
  "version": "2.0",
  "task": "<task>",
  "mode": "single|standard|multi",
  "run_style": "auto|phase|step",
  "model_config": {
    "preset": "<name>",
    "executor": "<model|null>",
    "advisor": "<model|null>",
    "evaluator": "<model|null>",
    "verifier": "<haiku|sonnet|opus>"
  },
  "cli_flags": {
    "verifier_model": null,
    "output_dir": null
  },
  "user_lang": "<lang>",
  "has_git": true,
  "repo_name": "<name>",
  "repo_path": "<path>",
  "phase": "plan_ready",
  "round": 1,
  "max_rounds": 3,
  "max_files": 20,
  "scope": "<scope or (no limit)>",
  "branch": "harness/<slug>",
  "lang": "<detected>",
  "build_cmd": "<cmd or null>",
  "test_cmd": "<cmd or null>",
  "lint_cmd": "<cmd or null>",
  "type_check_cmd": "<cmd or null>",
  "verify": {
    "layer1_result": null,
    "layer1_retries": 0,
    "layer2_result": null,
    "layer2_retries": 0,
    "todo_blocking": false,
    "autofix_attempted": false
  },
  "autofix": null,
  "docs_path": "<output_base>/<slug>/",
  "conventions": null,
  "created_at": "<ISO8601>",
  "updated_at": "<ISO8601>"
}
```

> `cli_flags.verifier_model` and `cli_flags.output_dir` are `null` by default (no CLI override).
> `verify.autofix_attempted` starts `false` each new session (session-wide once-only limit — not reset on round increment).
> `autofix` starts `null`; transitions to `{ "last_patch_path": "...", "applied": "proposed"|"applied"|"rejected"|"stopped", "triggered_at": "<ISO8601>" }` during H2 flow.

12. **Print setup summary** (in `user_lang`):
```
[harness] Task started!
  Directory : <path>
  Branch    : harness/<slug>     ← omit if has_git == false
  Mode      : <single | standard | multi>
  Model     : <preset>
  Verifier  : <model_config.verifier>    ← always shown
  Style     : <auto | phase | step>
  Language  : <lang>
  Test      : <test_cmd or "none">
  Build     : <build_cmd or "none">
  Lint      : <lint_cmd or "none">
  TypeCheck : <type_check_cmd or "none">
  Scope     : <scope>
  Output    : <docs_path>
```

If `model_config.verifier` is `sonnet` or `opus`, also print:
```
  ⚠ Verifier set to <model> — high cost for mechanical verification. haiku is usually sufficient.
```

13. **Proceed to Step 1.5** (Convention Scan). If `run_style == "step"` and the CLI step is not `plan`, check prerequisites and jump to the requested step after Step 1.5 completes.

---

### Step 1.5: Convention Scan

*This step runs after Setup and before Plan, in all modes.*

**Persisted Spec Artifacts Check (NEW in 8.4):**

Before running CLAUDE.md richness check, look for `{docs_path}conventions.md` (persisted by /spec Phase 3 in slug-matched directory):

- File exists → copy content to `.harness/conventions.md`, set `state.conventions → "file:.harness/conventions.md"`, skip the rich/sparse/missing trichotomy entirely. Proceed to Step 2 (Plan).
- File does NOT exist → proceed with the existing CLAUDE.md richness flow below.

**Resume idempotency:** if `state.conventions == "file:.harness/conventions.md"` but `.harness/conventions.md` is missing (e.g., `.harness/` was deleted), the persisted check re-copies from `{docs_path}conventions.md` if still present. **If both `.harness/conventions.md` AND `{docs_path}conventions.md` are missing**, reset `state.conventions = null` and fall through to the existing CLAUDE.md richness flow (treat as fresh execution — no convention context available).

**CLAUDE.md Richness Check:**

1. Check if `CLAUDE.md` exists in the repository root.
2. If it exists, count lines: `wc -l CLAUDE.md` (or read and count).
3. **Richness determination:**
   - Exists AND ≥ 50 lines → **rich** → skip scan, read CLAUDE.md content as conventions.
   - Exists AND < 50 lines → **sparse** → proceed to scan Q&A.
   - Does not exist → **missing** → proceed to scan Q&A.

**`conventions` field contract:** Always stores one of three values:
- `null` → Step 1.5 not yet executed (initial state)
- `"skipped"` → user explicitly chose to skip convention scan
- `"file:<path>"` → conventions available at the given path (e.g., `"file:.harness/conventions.md"`)

**Conventions injection rule (used by Step 2):** When `conventions` starts with `"file:"`, read the file at the path after the prefix. If the file does not exist, treat as `null` and re-run Step 1.5. When `conventions` is `null` or `"skipped"`, pass `{conventions}` as empty string.

---

**If rich (CLAUDE.md ≥ 50 lines):**

1. Copy CLAUDE.md content to `.harness/conventions.md` (so all convention sources use the same path pattern).
2. Store `conventions → "file:.harness/conventions.md"` in state.json.
3. Print: `  [harness] Conventions: CLAUDE.md detected (rich). Copied to .harness/conventions.md`
Proceed to Step 2 (Plan).

**If sparse or missing:**

Ask via AskUserQuestion (in `user_lang`):
- header: "Convention Scan"
- question: "No rich CLAUDE.md found. Scan codebase to auto-detect project conventions (DB, API, file structure, test patterns)? This helps the Planner align with existing patterns."
- options:
  - "Scan" / "Run convention scanner sub-agent (~1 token overhead)"
  - "Skip" / "Proceed without convention data"

**If "Skip":** Set `conventions → "skipped"` in state.json. Print: `  [harness] Conventions: skipped.` Proceed to Step 2.

**If "Scan":**

1. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/planner/convention_scanner.md`
2. Fill variables: `{repo_path}`, `{lang}`, `{scope}`, `{output_path}` = `.harness/conventions.md`.
3. **Dispatch 1 sub-agent** (convention scanner). Model: if preset ≠ "default", use `model_config.advisor` (or haiku for economy).
4. Parse return — first line should contain `"conventions written"`.
5. Verify `.harness/conventions.md` exists.
   - **If file does NOT exist** (sub-agent reported success but file missing): warn user (in `user_lang`): "Convention scan completed but output file not found." Ask via AskUserQuestion: header "Convention Scan Failed", question "Output file missing. Retry or skip?", options: "Retry" / "Re-run scanner", "Skip" / "Proceed without conventions". If "Retry" → re-dispatch sub-agent (max 2 retries). If "Skip" → set `conventions → "skipped"`. Do NOT store a `"file:"` reference to a non-existent file.
6. Store `conventions → "file:.harness/conventions.md"` in state.json.
7. Print: `  [harness] Conventions: scanned and saved to .harness/conventions.md`

Update state.json: `updated_at → now`.
Proceed to Step 2 (Plan).

---

### Step 2: Plan Phase

Update state.json: `phase → "plan_ready"`, `updated_at → now`.

Print: `[harness] Phase: Plan`

**Discovery Notes Injection (NEW in 8.4) — applies to all planner dispatches in single/standard/multi mode:**

Before any planner sub-agent dispatch, prepare:
- `qa_discovery_notes` = read content of `{docs_path}qa_notes.md` if exists, else empty string `""`.
- `critic_findings` = read content of `{docs_path}critic_findings.md` if exists, else empty string `""`.

When dispatching ANY planner template (`architect.md`, `senior_developer.md`, `qa_specialist.md`, `planner_single.md`), pass `{qa_discovery_notes}` and `{critic_findings}` as keyword variables (always — even when empty, to avoid `str.format()` KeyError on the new placeholders).

Backward compat: pre-8.4 sessions where these files do not exist receive empty strings — templates render the `## Discovery Notes from Spec Phase` section with empty sub-bodies, which is harmless.

#### Step 2 — single mode

1. Update phase → `"planning"`.
2. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/planner/planner_single.md`
3. **Dispatch 1 sub-agent** with prompt built from template variables: `{task_description}`, `{repo_path}`, `{lang}`, `{scope}`, `{user_lang}`, `{qa_discovery_notes}`, `{critic_findings}`, `{spec_path}` = `{docs_path}spec.md`.
   - **Conventions injection:** If `conventions` in state.json starts with `"file:"`, extract the path after the prefix, read the file content, and pass as `{conventions}`. If `conventions` is `null`, `"skipped"`, or the referenced file does not exist, pass `{conventions}` as empty string.
   - Model: if preset ≠ "default", use `model_config.advisor`.
4. Parse return → extract first line. Print: `  ✓ {first line}`
5. Verify `spec.md` exists.
6. Update phase → `"plan_done"`, `updated_at → now`.

#### Step 2 — standard mode

##### 2a: Independent Proposals (Parallel)

1. Update phase → `"planning"`.
2. Read templates: `architect.md`, `senior_developer.md`
3. **Dispatch 2 sub-agents in parallel.** Each gets: `{task_description}`, `{repo_path}`, `{lang}`, `{scope}`, `{user_lang}`, `{qa_discovery_notes}`, `{critic_findings}`, `{output_path}` = `.harness/planner/proposal_<persona>.md`.
   - **Conventions injection:** If `conventions` starts with `"file:"`, read the file and pass as `{conventions}`. If `null`, `"skipped"`, or file missing, pass empty string.
   - Model: if preset ≠ "default", use `model_config.advisor`.
4. Parse returns. Print: `  ✓ 2 proposals generated`
5. Verify both proposal files exist.

##### 2b: Synthesis

1. Read template: `synthesis_standard.md`
2. **Dispatch 1 sub-agent** with: `{task_description}`, `{user_lang}`, `{all_proposals}` (read both proposals, concatenate with author labels), `{spec_path}`.
   - Model: if preset ≠ "default", use `model_config.advisor`.
3. Parse return. Print: `  ✓ {first line}`
4. Verify `spec.md` exists.
5. Update phase → `"plan_done"`, `updated_at → now`.

#### Step 2 — multi mode

##### 2a: Independent Proposals (Parallel)

1. Update phase → `"planning"`.
2. Read templates: `architect.md`, `senior_developer.md`, `qa_specialist.md`
3. **Dispatch 3 sub-agents in parallel.** Each gets template vars + `{qa_discovery_notes}` + `{critic_findings}` + `{output_path}` = `.harness/planner/proposal_<persona>.md`.
   - **Conventions injection:** If `conventions` starts with `"file:"`, read the file and pass as `{conventions}`. If `null`, `"skipped"`, or file missing, pass empty string.
   - Model: if preset ≠ "default", use `model_config.advisor`.
4. Parse returns. Print: `  ✓ 3 proposals generated`
5. Verify all 3 proposal files exist.

##### 2b: Cross-Critique (Parallel)

1. Read template: `cross_critique.md`
2. Read all 3 proposals.
3. For each persona, prepare critique prompt with the OTHER two proposals.
4. **Dispatch 3 sub-agents in parallel.** Each writes to `.harness/planner/critique_<persona>.md`.
   - Model: if preset ≠ "default", use `model_config.advisor`.
5. Parse returns. Print: `  ✓ 3 cross-critiques completed`
6. Verify all 3 critique files exist.

##### 2c: Synthesis

1. Read template: `synthesis.md`
2. Read all 6 files (3 proposals + 3 critiques).
3. **Dispatch 1 sub-agent** with: `{task_description}`, `{user_lang}`, `{all_proposals}`, `{all_critiques}`, `{spec_path}`.
   - Model: if preset ≠ "default", use `model_config.advisor`.
4. Parse return. Print: `  ✓ {first line}`
5. Verify `spec.md` exists.
6. Update phase → `"plan_done"`, `updated_at → now`.

#### After Plan Phase

Print: `[harness] Plan complete.`

**If `run_style == "phase"` or (`run_style == "step"` and requested step was `plan`):** Print spec.md path, inform user session can end. Halt.

**If `run_style == "auto"`:** Continue to Step 3 (Gate).

---

### Step 3: HARD GATE — Spec Confirmation

<HARD-GATE>
Read and show spec.md to the user. Ask via AskUserQuestion (in `user_lang`):
- header: "Spec"
- question: "Review the spec above. Implementation consumes significant tokens. Confirm to proceed."
- options:
  - "Proceed" / "Start implementation as specified"
  - "Modify" / "Edit the spec, then re-confirm"
  - "Stop" / "Halt the workflow"

If "Modify": update spec.md and re-present.
If "Stop": halt.
Only "Proceed" advances.
</HARD-GATE>

Update state.json: `phase → "generate_ready"`, `updated_at → now`.

---

### Step 4: Generate Phase

Print: `[harness] Phase: Generate`

Print: `  Dispatching generator sub-agent...`

#### Step 4 — single mode

1. Update phase → `"generating"`, `updated_at → now`.
2. Read template: `generator_single.md`
3. Prepare prompt: `{spec_content}` from spec.md, `{qa_feedback}` from qa_report.md if round > 1 else "(First round)", `{round_num}`, `{scope}`, `{max_files}`, `{user_lang}`, `{changes_path}` = `{docs_path}changes.md`.
   - **If retry** (from verify/evaluate failure): add `{verify_failure}` = 1-line FAIL summary, `{verify_report_path}` = `{docs_path}verify_report.md`.
   - Model: if preset ≠ "default", use `model_config.executor`.
4. **Dispatch 1 sub-agent.**
5. Parse return. Print: `  ✓ {first line}`
6. Verify `changes.md` exists.
7. Update phase → `"generate_done"`, `updated_at → now`.

#### Step 4 — standard mode

##### 4a: Implementation Plan

1. Update phase → `"generating"`, `updated_at → now`.
2. Read template: `lead_developer.md`
3. **Dispatch 1 sub-agent** (Lead Developer): `{spec_content}`, `{qa_feedback}`, `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}`, `{output_path}` = `.harness/generator/plan.md`.
   - Model: if preset ≠ "default", use `model_config.executor`.
4. Parse return. Print: `  ✓ Plan: {first line}`
5. Verify `.harness/generator/plan.md` exists.

##### 4b: Combined Advisory Review

1. Read template: `combined_advisor.md`
2. Read `.harness/generator/plan.md`.
3. **Dispatch 1 sub-agent** (Combined Advisor): `{spec_content}`, `{plan_content}`, `{repo_path}`, `{lang}`, `{test_cmd}`, `{user_lang}`, `{output_path}` = `.harness/generator/review_combined.md`.
   - Model: if preset ≠ "default", use `model_config.advisor`.
4. Parse return. Print: `  ✓ Review: {first line}`
5. Verify `.harness/generator/review_combined.md` exists.

##### 4c: Implementation

1. Read template: `implementation_standard.md`
2. Read plan + review from `.harness/generator/`.
3. Prepare prompt: `{spec_content}`, `{plan_content}`, `{advisor_review}`, `{qa_feedback}`, `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}`, `{round_num}`, `{changes_path}` = `{docs_path}changes.md`.
   - **If retry**: add `{verify_failure}`, `{verify_report_path}` = `{docs_path}verify_report.md`.
   - Model: if preset ≠ "default", use `model_config.executor`.
4. **Dispatch 1 sub-agent.**
5. Parse return. Print: `  ✓ Code: {first line}`
6. Verify `{docs_path}changes.md` exists.
7. Update phase → `"generate_done"`, `updated_at → now`.

#### Step 4 — multi mode

##### 4a: Implementation Plan

Same as standard 4a.

##### 4b: Advisory Review (Parallel)

1. Read templates: `code_quality_advisor.md`, `test_stability_advisor.md`
2. Read `.harness/generator/plan.md`.
3. **Dispatch 2 sub-agents in parallel.** Each writes to `.harness/generator/review_<advisor>.md`.
   - Model: if preset ≠ "default", use `model_config.advisor`.
4. Parse returns. Print: `  ✓ Reviews: 2 advisors completed`
5. Verify both review files exist.

##### 4c: Implementation

1. Read template: `implementation.md`
2. Read plan + both reviews from `.harness/generator/`.
3. Prepare prompt: `{spec_content}`, `{plan_content}`, `{code_quality_review}`, `{test_stability_review}`, `{qa_feedback}`, `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}`, `{round_num}`, `{changes_path}` = `{docs_path}changes.md`.
   - **If retry**: add `{verify_failure}`, `{verify_report_path}` = `{docs_path}verify_report.md`.
   - Model: if preset ≠ "default", use `model_config.executor`.
4. **Dispatch 1 sub-agent.**
5. Parse return. Print: `  ✓ Code: {first line}`
6. Verify `{docs_path}changes.md` exists.
7. Update phase → `"generate_done"`, `updated_at → now`.

#### After Generate Phase

Print: `[harness] Generate complete.`

**If `run_style == "phase"` or (`run_style == "step"` and requested step was `generate`):** Inform user, halt.

**If `run_style == "auto"`:** Continue to Step 5 (Verify).

---

### Step 5: Verify Phase (Layer 1 — Mechanical)

**First entry only** (from generate_done, not from retry loop): Update state.json: `phase → "verify_ready"`, `verify.layer1_result → null`, `verify.layer1_retries → 0`, `updated_at → now`.

**Retry re-entry** (from Generator retry): Update state.json: `phase → "verify_ready"`, `verify.layer1_result → null`, `updated_at → now`. Do NOT reset `layer1_retries` — it was already incremented at retry dispatch.

Print: `[harness] Phase: Verify (Layer 1 — Mechanical)`

1. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/verify/verify_layer1.md`
2. Prepare prompt with:
   - `{build_cmd}`: from state.json (or `"SKIP"` if null)
   - `{test_cmd}`: from state.json (or `"SKIP"` if null)
   - `{lint_cmd}`: from state.json (or `"SKIP"` if null)
   - `{type_check_cmd}`: from state.json (or `"SKIP"` if null)
   - `{changes_md_path}`: `{docs_path}changes.md`
   - `{verify_report_path}`: `{docs_path}verify_report.md`
   - `{todo_blocking}`: from state.json `verify.todo_blocking`
3. Update phase → `"verifying"`, `updated_at → now`.
4. **Dispatch Verify sub-agent** with `model: model_config.verifier` (default: haiku; override via --verifier-model).
5. Parse return — first line:
   - Contains `"PASS"` → `verify.layer1_result → "PASS"`
   - Contains `"FAIL"` → `verify.layer1_result → "FAIL"`
6. Update phase → `"verify_done"`, `updated_at → now`.

#### If PASS:

Print:
```
[harness] Verify (Layer 1) complete.
  Result : PASS
  {first line from sub-agent}
```
Continue to Step 6.

#### If FAIL and retries < 3:

Increment `verify.layer1_retries` in state.json.
Print:
```
[harness] Verify (Layer 1) FAIL — retrying Generator (attempt {layer1_retries}/3)
  {first line error summary}
```

**Generator retry** — regardless of mode, launch **one implementation sub-agent only** (no re-plan, no re-review):
- `single` → `generator_single.md`
- `standard` → `implementation_standard.md` (with existing plan.md + review_combined.md)
- `multi` → `implementation.md` (with existing plan.md + reviews)

Add to prompt:
- `{verify_failure}` = the 1-line FAIL summary
- `{verify_report_path}` = `{docs_path}verify_report.md`
- Model: if preset ≠ "default", use `model_config.executor`.

Update phase → `"generating"`, `updated_at → now` (skip `generate_ready` — retry is automatic, no user gate).
After retry sub-agent completes: phase → `"generate_done"`, `updated_at → now`, then loop back to Step 5 (re-run verify).

#### If FAIL and retries >= 3:

Print:
```
[harness] Verify (Layer 1) FAIL — max retries reached (3/3)
  Latest error: {first line error summary}
  See: {docs_path}verify_report.md
```

<HARD-GATE>
Ask via AskUserQuestion (in `user_lang`):
- header: "Verify"
- question: "Mechanical verification failed after 3 attempts. [error summary]"
- options:
  - "Auto-fix proposal" / "Let AI (Opus) analyze the failure and propose a minimal diff (1 attempt only)" ← **HIDE this option if `verify.autofix_attempted == true OR state.autofix != null`** (see §State Machine — I2)
  - "Continue to Evaluator" / "Skip remaining verify issues, proceed to QA"
  - "Stop" / "Halt for manual intervention. Review verify_report.md"
</HARD-GATE>

If "Continue": proceed to Step 6.
If "Stop": halt (keep phase as `verify_done`).

**If "Auto-fix proposal":**

> `verify.autofix_attempted` is set to `true` only after the 2nd HARD-GATE decision (Apply/Reject/Stop), NOT at Proposer dispatch. This ensures session interruption between dispatch and the 2nd gate does not consume the once-only right (I1).
> **On session resume with `autofix.applied == "proposed"`**: re-enter 2nd HARD-GATE directly using saved `autofix.last_patch_path` — skip 1st GATE (I3).

1. Update state.json: `autofix → { "last_patch_path": ".harness/generator/auto_fix_patch.md", "applied": "proposed", "triggered_at": "<ISO8601>" }`
2. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/auto_fix_proposer.md`
3. Fill variables (pass **paths only** — Proposer sub-agent reads files directly):
   - `{spec_path}` = `{docs_path}spec.md`
   - `{changes_md_path}` = `{docs_path}changes.md`
   - `{verify_report_path}` = `{docs_path}verify_report.md`
   - `{failing_files_list}` = Orchestrator reads verify_report.md directly to extract file paths (explicit exception to §Architecture Principles #1 — path extraction only, no content analysis). After extraction:
     - Apply `validate_path(path, kind=file_reference)` to each path.
     - Violations: drop path + print `[harness] ⚠ Path validation failed: <path> — excluded from Proposer input`
     - Cap: maximum 5 paths. Excess paths dropped silently.
     - If 0 valid paths remain: print `[harness] ⚠ No valid file paths found — Proposer input will be empty`
   - `{output_path}` = `.harness/generator/auto_fix_patch.md`
4. **Dispatch Auto-fix Proposer sub-agent** with `model: model_config.advisor ?? "opus"`.
   - If `model_config.preset == "default"`, use `"opus"` (explicit upgrade — 2nd GATE UI will warn cost).
5. Parse return 1-line. Extract `confidence` level. If return format is non-standard (cannot parse confidence), treat as `confidence: Unknown` and print `[harness] ⚠ 1-line return parse failed — fallback: confidence Unknown`.
6. Verify `.harness/generator/auto_fix_patch.md` exists.
7. **Empty patch check**: verify `auto_fix_patch.md` contains at least one ```` ```diff ```` code block AND at least one `@@` hunk header.
   - If absent: skip Apply, print `[harness] ⚠ Patch file is empty or has no diff block — apply skipped`, return to HARD-GATE (Auto-fix hidden).

<HARD-GATE>
Show confidence level + 1-line summary from patch file.
Print before question: `[harness] ℹ Auto-fix model: {model_config.advisor ?? 'opus'}`
Ask via AskUserQuestion (in `user_lang`):
- header: "Auto-fix"
- question: "Proposed fix generated (confidence: {level}). [If confidence == Low: ⚠ Low confidence — review the diff carefully before applying.] Apply the patch?"
- options:
  - "Apply patch" / "Apply the proposed diff and re-run Layer 1 verification (retry counter unchanged)"
  - "Reject" / "Discard proposal, return to previous gate (Auto-fix option hidden)"
  - "Stop" / "Halt for manual intervention"
</HARD-GATE>

After 2nd HARD-GATE decision, set `verify.autofix_attempted = true` in state.json.

**If "Apply patch":**
1. Before applying: snapshot current state via `git stash` (if `has_git == true`) or copy changed files to `.harness/autofix_pre_apply/` (if `has_git == false`).
2. **Pre-apply path validation**: parse all `--- a/<path>` and `+++ b/<path>` headers from `auto_fix_patch.md` (metadata only — 4 header lines per hunk; hunk body is not parsed). Apply `validate_path(path, kind=diff_target)` to each path.
   - Print to user: `[harness] Applying patch to: <path list>`
   - If any path fails validation: reject Apply, print `[harness] ✗ Diff path validation failed: <path>`, return to HARD-GATE (Auto-fix hidden).
3. Apply unified diff from `.harness/generator/auto_fix_patch.md` using Edit tool.
   - If any hunk fails to apply: restore from snapshot, warn user "Apply failed — reverted to pre-apply state.", return to HARD-GATE (retries >= 3, Auto-fix hidden).
4. Update state.json: `autofix.applied → "applied"`. Reset `verify.layer1_result → null`.
5. Re-run Layer 1 Verify (retry counter `layer1_retries` unchanged — do NOT increment):
   - **PASS** → proceed to Step 6.
   - **FAIL** → update state.json: `autofix.applied → "stopped"`, `layer1_retries = min(layer1_retries, 3)` (clamp — see §State Machine I4). Return to FAIL retries >= 3 HARD-GATE (Auto-fix option hidden since `verify.autofix_attempted == true`).

**If "Reject":**
1. Update state.json: `autofix.applied → "rejected"`.
2. Return to FAIL retries >= 3 HARD-GATE (Auto-fix option hidden).

**Layer 2 FAIL path:** Auto-fix proposal does **NOT** apply to Layer 2 structural failures (Step 7). Mechanical diff cannot fix structural issues.

#### After Verify Phase

**If `run_style == "phase"` or (`run_style == "step"` and requested step was `verify`):** Inform user of result, halt.

**If `run_style == "auto"`:** Continue to Step 6.

---

### Step 6: Evaluate Phase (Layer 2 + Layer 3)

Update state.json: `phase → "evaluate_ready"`, `updated_at → now`.

Print: `[harness] Phase: Evaluate (Layer 2+3)`

Print: `  Dispatching evaluator sub-agent...`

1. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/evaluator/evaluator_prompt.md`
2. Prepare prompt:
   - `{spec_content}` from spec.md
   - `{changed_files_list}` — file paths only from changes.md, **strip all "reason" descriptions** (anchoring prevention)
   - `{test_available}`, `{build_cmd}`, `{test_cmd}`, `{round_num}`, `{scope}`, `{user_lang}`
   - `{qa_report_path}` = `{docs_path}qa_report.md`
   - `{verify_context}`:
     - If `verify.layer1_result == "PASS"`: `"Layer 1 PASSED — build/test/lint/type-check verified. See {docs_path}verify_report.md"`
     - If `verify.layer1_result == "FAIL"` (user chose Continue): `"Layer 1 FAILED (user proceeded despite failures) — see {docs_path}verify_report.md. Pay extra attention to build/test correctness."`
     - If verify skipped: `"Layer 1 was not executed for this session."`
   - **Do NOT include:** Generator reasoning, implementation plans, advisor reviews, or references to "Generator"/"AI"/"agent".
3. Update phase → `"evaluating"`, `updated_at → now`.
4. **Dispatch Evaluator sub-agent** using `subagent_type: "superpowers:code-reviewer"` if available.
   - Model: if preset ≠ "default", use `model_config.evaluator`.
5. Parse return — first line:
   - Contains `"PASS"` → `verify.layer2_result → "PASS"`. Print: `  ✓ {first line}`
   - Contains `"FAIL L2"` → `verify.layer2_result → "FAIL"`. Print: `  ✗ {first line}`
   - Contains `"FAIL L3"` → `verify.layer2_result → "PASS"` (Layer 2 passed). Print: `  ✗ {first line}`
   - Contains `"FAIL"` (no layer indicator) → treat as L3 FAIL. `verify.layer2_result → "PASS"`.
6. Update phase → `"evaluate_done"`, `updated_at → now`.

Print: `[harness] Evaluate complete.`

**If `run_style == "phase"` or (`run_style == "step"` and requested step was `evaluate`):** Inform user, halt.

**If `run_style == "auto"`:** Continue to Step 7.

---

### Step 7: Verdict & Loop

Read `qa_report.md`. Look for `"### Verdict: PASS"` or `"### Verdict: FAIL"`.
Also check `verify.layer2_result` from state.json to determine failing layer.

#### If PASS:

Update state.json: `phase → "completed"`, `updated_at → now`.
Print: `[harness] ✓ QA PASS — task complete.`
Proceed to Step 8.

#### If FAIL — Layer 2 (verify.layer2_result == "FAIL") and layer2_retries < 2:

Layer 2 failed. Auto-retry without user gate (same pattern as Layer 1 retry).

Increment `verify.layer2_retries` in state.json.
Print:
```
[harness] Evaluate FAIL (Layer 2) — retrying Generator (attempt {layer2_retries}/2)
  {first line from evaluator}
```

Launch **one implementation sub-agent** (retry, no re-plan/re-review) — same rules as Layer 1 retry:
- `single` → `generator_single.md`
- `standard` → `implementation_standard.md` (with existing plan.md + review_combined.md)
- `multi` → `implementation.md` (with existing plan.md + reviews)

Add `{verify_failure}` = evaluator 1-line FAIL, `{verify_report_path}` = `{docs_path}qa_report.md`.
Model: if preset ≠ "default", use `model_config.executor`.

Update phase → `"generating"`, `updated_at → now` (skip `generate_ready`).
After retry completes: phase → `"generate_done"`, `updated_at → now`, then **run full Verify → Evaluate pipeline** (Step 5 → Step 6 → Step 7).

#### If FAIL — Layer 2 and layer2_retries >= 2:

Print:
```
[harness] Evaluate FAIL (Layer 2) — max retries reached (2/2)
  Failing items: {summary from qa_report.md}
```

Ask via AskUserQuestion (in `user_lang`):
- header: "QA"
- question: "Layer 2 structural verification failed after 2 retries. [failing items]"
- options:
  - "Fix" / "Run next round"
  - "Accept as-is" / "Finish without fixing"

If "Fix": same as Layer 3 Fix below.
If "Accept as-is": phase → `"completed"`, proceed to Step 8.

#### If FAIL — Layer 3 (verify.layer2_result == "PASS") and rounds remaining (round < max_rounds):

Ask via AskUserQuestion (in `user_lang`):
- header: "QA"
- question: "QA result: FAIL (Layer 3). [failure summary from qa_report.md Fix Instructions]."
- options:
  - "Fix" / "Run next round to fix FAIL items"
  - "Accept as-is" / "Finish without fixing"

If "Fix":
- Increment `round`, reset `verify.layer1_retries → 0`, `verify.layer1_result → null`, `verify.layer2_result → null`, `verify.layer2_retries → 0`.
- Update `updated_at → now`.
- Go to Step 4 (Generate).

If "Accept as-is":
- Update phase → `"completed"`, `updated_at → now`.
- Proceed to Step 8.

#### If FAIL and max rounds reached:

Update phase → `"completed"`, `updated_at → now`.
Print: `[harness] Max rounds reached. Remaining issues in qa_report.md.`
Proceed to Step 8.

---

### Step 8: Cleanup & Finalize

#### Artifact Cleanup Safety Guard

Before deleting any output directory:

1. **Read `docs_path`** from state.json. If missing/null: reconstruct as `"docs/harness/<slug>/"`. Extract `<slug>` = last path segment before the trailing `/`.
2. **Validate slug**: If empty/null/whitespace → **ABORT**, warn user.
3. **Path depth check**: `docs_path` must be a relative path exactly one level below its parent directory. slug must NOT be `memory` (reserved), must NOT contain `..` or `/`, must NOT be `.`. **Always** verify: `Path(docs_path).resolve()` ⊆ `Path.cwd()` (symlink escape prevention — no `has_git` condition). If any fail → **ABORT**.
4. **Display before delete**: Print exact target path before executing.

**Full output base cleanup** (only on explicit user request):
1. List all subdirectories with file counts.
2. If `docs/harness/memory/` exists, warn separately: "Contains team knowledge from /memory skill."
3. Warn: "`docs/` is git-ignored — all artifacts permanently deleted."
4. Confirm via AskUserQuestion (yes/no).

#### If has_git == true:

Ask via AskUserQuestion (in `user_lang`):
- header: "Commit"
- question: "Implementation complete. Choose how to finish:"
- options:
  - "Commit code only (Recommended)" / "Clean artifacts, commit code changes only"
  - "Commit all" / "Commit everything including artifacts"
  - "No commit" / "Clean .harness/ only, keep changes in working tree"

Actions (apply Safety Guard before each delete):
- "Commit code only": delete `.harness/`, delete `{docs_path}`, stage + commit code
- "Commit all": delete `.harness/`, stage + commit `{docs_path}` + code
- "No commit": delete `.harness/` only

#### If has_git == false:

Inform user artifacts are in `{docs_path}`.
Delete `.harness/` only. No git operations.

---

## Model Selection

| Preset | executor | advisor | evaluator | verifier |
|--------|----------|---------|-----------|----------|
| default | (parent) | (parent) | (parent) | haiku (default) |
| all-opus | opus | opus | opus | haiku (default) |
| balanced | sonnet | opus | opus | haiku (default) |
| economy | haiku | sonnet | sonnet | haiku (default) |

### Planner Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Architect | advisor | (no override) | opus | opus | sonnet |
| Senior Developer | advisor | (no override) | opus | opus | sonnet |
| QA Specialist | advisor | (no override) | opus | opus | sonnet |

### Generator Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Lead Developer | executor | (no override) | opus | sonnet | haiku |
| Code Quality Advisor | advisor | (no override) | opus | opus | sonnet |
| Test & Stability Advisor | advisor | (no override) | opus | opus | sonnet |
| Combined Advisor | advisor | (no override) | opus | opus | sonnet |
| Generator (single) | executor | (no override) | opus | sonnet | haiku |

### Evaluator Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Evaluator | evaluator | (no override) | opus | opus | sonnet |

### Verify Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Verify (Layer 1) | verifier | haiku (default) | haiku (default) | haiku (default) | haiku (default) |

> **Verifier defaults to haiku across all presets.** Layer 1 only executes commands and parses exit codes — lowest-cost model is always sufficient. Override with `--verifier-model sonnet|opus` for sensitive mechanical verification (e.g., concurrency, complex test failures). Opt-in only. When set to `sonnet` or `opus`, a cost warning is shown in Setup Summary.

**Applying model config:** When launching any sub-agent, if `model_config.preset` ≠ `"default"`, pass `model` per the table. Sub-agents do NOT read model_config from state.json — the orchestrator passes the model at launch.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion available → use it
- If not available or fails → present as text with numbered options
- Every option: `label` (short) + `description` (specific)
- "Other" (free text) is automatically appended
- Translate all text to `user_lang`

## Architecture Principles

The following 5 principles are invariant constraints for the harness Orchestrator.

1. **Orchestrator reads no intermediate files.** Exceptions:
   - spec.md at plan gate
   - qa_report.md at verdict gate
   - verify_report.md path for user message
   - **verify_report.md failing-file extraction for Auto-fix Proposer dispatch**:
     Orchestrator reads verify_report.md to extract failing file paths only (no content analysis).
     Extracted paths pass through Path Validator (kind=file_reference) and are capped at 5.
     See §Step 5 — Auto-fix dispatch for the exact procedure.
   - Apply-before `--- a/` / `+++ b/` diff header lines (4 lines of metadata only — hunk body is delegated to Edit tool). This is NOT a violation of this principle.

2. **Auto-fix Proposer is the only sub-agent that directly Reads source files.** Other sub-agents receive content only through template variables.

3. **Paths only to sub-agents; never file contents** (ephemeral critiques/proposals at synthesis step excepted).

4. **Session-wide invariants** (see §State Machine — Auto-fix State Transition Table):
   - Auto-fix: at most 1 attempt per session (`verify.autofix_attempted` once-only — not reset on round increment).
   - Layer 1 retries: max 3. Do NOT reset after Auto-fix Apply.

5. **All external paths pass through Path Validator before use** (see §Path Validator below).

### Path Validator

Orchestrator internal conceptual function. Call sites: `--output-dir` parsing (Step 1.2), `{failing_files_list}` injection (Step 5), Edit tool unified diff Apply (Step 5), Session Recovery re-validation (Session Recovery).

```
validate_path(path, kind) where kind ∈ {output_dir, file_reference, diff_target}

  0. (kind == output_dir only) Empty string → halt "output-dir cannot be empty."
  1. Normalize: \ → / (OS-independent). UNC (\\server\share or //server/share) → halt.
  2. Absolute path: ^/ or ^[A-Za-z]:/ → halt.
  3. Segment-level ..: path.split("/") — any segment == ".." → halt (exact segment match, not substring).
  4. kind-specific:
     - output_dir:
         First segment (path.split("/")[0]) ∉ {memory, spec, planner, generator,
         evaluator, verify, harness, .harness, docs}.
     - file_reference (failing_files_list):
         (a) relative path, (b) no .. segment, (c) inside repo_path,
         (d) outside .harness/, docs/harness/*, memory/.
     - diff_target (unified diff --- a/ / +++ b/ headers):
         file_reference conditions + inside scope filter +
         outside .harness/, docs/harness/, memory/, .git/.
  5. On failure: return specific halt message describing the violation.
```

**Attack vector → Path Validator step mapping:**

| Attack vector | Blocked at step |
|---|---|
| `--output-dir .harness` | Step 4 (kind=output_dir, first segment reserved) |
| `--output-dir docs/../../etc` | Step 3 (segment `..` rejection) |
| `--output-dir \\server\share` | Step 1 (normalization + UNC rejection) |
| `--output-dir /absolute/path` | Step 2 (absolute path rejection) |
| `--output-dir memory/foo` | Step 4 (first segment reserved) |
| `--output-dir ` (empty) | Step 0 (empty string, kind=output_dir) |

## Key Rules

- **Never skip phases.** Always Plan → Generate → Verify → Evaluate.
- **Confirmation gates are non-negotiable.** No implicit approval.
- **Stay within scope.** Do not modify files outside scope.
- **Evaluator must be isolated.** Anchor-free input. Never pass Generator reasoning.
- **Planner proposals must be independent.** Never share one persona's work with another during proposal.
- **Generator advisors review the plan, not code.** Advisory before implementation.
- **Use available skills.** Search by keyword, not plugin name. Proceed without if none found.
- **User language.** All user-facing output in `user_lang`.
- **Intermediate outputs are ephemeral.** Only final artifacts preserved in `docs/`.
- **Orchestrator reads no intermediate files.** See §Architecture Principles for full exception list.
- **1-line return parsing.** Only first line of sub-agent return is used for state decisions.
