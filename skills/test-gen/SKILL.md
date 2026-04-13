---
name: test-gen
description: Automated test generator with mutation-based quality verification. Generates unit and integration tests, runs them, and validates meaningfulness via simplified mutation testing. Supports coverage-gap detection and regression test generation from debug reports.
---

# Agent Harness Test-Gen

You are orchestrating an **automated test generation workflow** that writes real test code, executes it, and verifies quality through simplified mutation testing.

**Core principle:** Test code only. Never touch production code. Every generated test must be meaningful — mutation testing enforces this.

**V1 — Single mode only.** No mode selection UI. For large targets (4+ files), automatically delegate analysis and generation to sub-agents.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, report sections, confirmation gate prompts and options.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (analysis.md, test_changes.md, test_report.md), git branch names.

## Environment Detection

At startup, detect whether the current directory is inside a git repository:
```
git rev-parse --is-inside-work-tree 2>/dev/null
```
- If the command succeeds → `has_git = true`
- If the command fails → `has_git = false`

Store `has_git` in state.json. This flag controls whether git operations (branch creation) are performed.

## Standard Status Format

When displaying status, read `.harness/state.json` and print (in `user_lang`):
```
[test-gen]
  Target : <target>
  Model  : <preset>
  Phase  : <phase label>
  Branch : <branch>          ← omit this line if has_git == false
```
Phase labels: setup → "Setup", analyzing → "Analysis — identifying coverage gaps", generating → "Generation — writing test code", verifying → "Verification — running tests + mutation check", completed → "Completed"

## Argument Parsing

Parse `$ARGUMENTS` with the following grammar:

```
/test-gen <target> [--coverage-gap] [--regression <path>]
```

**Flags:**
- `<target>` — file path, directory path, or class/module name to generate tests for
- `--coverage-gap` — auto-find low-coverage areas within the target instead of testing everything
- `--regression <path>` — generate regression tests from an existing debug report at `<path>`

**Mutual exclusion:** `--coverage-gap` and `--regression` cannot be used together. If both are provided, immediately report the error (in `user_lang`) and stop:
```
[test-gen] Error: --coverage-gap and --regression are mutually exclusive. Use one flag at a time.
```

Store parsed values: `target`, `mode_flag` ("coverage-gap" | "regression" | null), `regression_report_path` (if --regression).

## Session Recovery

Before starting a new task, check if `.harness/state.json` already exists **and** `state.json.skill` equals `"test-gen"`:

1. If it exists and matches, print status in the standard format (including Model line from `model_config`), prefixed with `[test-gen] Previous session detected.`
2. Restore `model_config` from state.json. Apply it to all subsequent sub-agent launches.
3. Ask the user using AskUserQuestion (in `user_lang`):
     header: "Session"
     question: "[test-gen] Previous session detected. [print status in standard format]. Resume, restart, or stop?"
     options:
       - label: "Resume" / description: "Continue from {phase} where the previous session left off"
       - label: "Restart" / description: "Delete .harness/ and start from scratch"
       - label: "Stop" / description: "Delete .harness/ and halt"

   Actions per selection:
   - **Resume**: Jump to the step matching state.json phase:
     `setup` → Step 1 (re-run setup) |
     `analyzing` → Phase 1 |
     `generating` → Phase 2 |
     `verifying` → Phase 3 |
     `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist (or `state.json.skill` is not `"test-gen"`), proceed to Step 1 normally.

## Workflow

### Step 1: Setup

1. **Detect user language** from the target/arguments. Store as `user_lang`.
2. **Check mutual exclusion** — if both `--coverage-gap` and `--regression` are provided, report error and stop (see Argument Parsing above).
3. **Slugify the target:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.
4. **Detect environment** — run `git rev-parse --is-inside-work-tree 2>/dev/null`, store `has_git`.
5. **Auto-detect project language and test framework.** Scan the working directory:

   | Framework | Detection | Test file pattern | Run command | Mock library |
   |-----------|-----------|------------------|-------------|-------------|
   | Jest | `package.json` contains jest dependency | `*.test.ts`, `*.spec.ts` | `npx jest` | `jest.mock` |
   | Vitest | `package.json` contains vitest | `*.test.ts`, `*.spec.ts` | `npx vitest run` | `vi.mock` |
   | pytest | `pyproject.toml` or `conftest.py` present | `test_*.py`, `*_test.py` | `pytest` | `pytest.monkeypatch`, `unittest.mock` |
   | JUnit | `build.gradle` contains junit | `*Test.java` | `./gradlew test` | `Mockito` |
   | Go test | `go.mod` present | `*_test.go` | `go test ./...` | `testify/mock` |
   | RSpec | `Gemfile` contains rspec | `*_spec.rb` | `bundle exec rspec` | `rspec-mocks` |
   | Other | none of the above match | ask user | ask user | ask user |

   **If detection fails:** Ask the user using AskUserQuestion (in `user_lang`):
     header: "Framework"
     question: "Could not auto-detect test framework. Please specify:"
     options:
       - label: "Jest" / description: "JavaScript/TypeScript — npx jest"
       - label: "Vitest" / description: "JavaScript/TypeScript — npx vitest run"
       - label: "pytest" / description: "Python — pytest"
       - label: "JUnit" / description: "Java — ./gradlew test"
       - label: "Go test" / description: "Go — go test ./..."
       - label: "RSpec" / description: "Ruby — bundle exec rspec"
     If user cannot answer either (selects "Other" with no info): report "Cannot detect framework. Please set up a test framework and retry." and stop.

6. **Create directories:** `.harness/test-gen/`, `docs/harness/<slug>/`
7. **Create git branch (if has_git):** `git checkout -b harness/test-gen-<slug>`
8. **Model configuration selection:**
   If `--model-config <preset>` was passed, use it directly. Otherwise, use AskUserQuestion to ask the user (in `user_lang`):
     header: "Model"
     question: "Select model configuration for sub-agents:"
     options:
       - label: "default" / description: "Inherit parent model, no changes"
       - label: "all-opus" / description: "All sub-agents use Opus (highest quality)"
       - label: "balanced (Recommended)" / description: "Sonnet executors (cost-efficient)"
       - label: "economy" / description: "Haiku executors (max savings)"

   Store result as `model_config` object: `{ "preset": "<name>", "executor": "<model|null>" }`. For the `default` preset, store `{ "preset": "default" }`.

   **Model config is set once at session start and cannot be changed mid-session.** To change, restart the session.

9. **Write `.harness/state.json`** with fields:
   - `skill`: `"test-gen"` ← used for session recovery identification
   - `target`: the target argument
   - `slug`: `<slug>`
   - `mode`: `"single"`
   - `mode_flag`: `"coverage-gap"` | `"regression"` | `null`
   - `regression_report_path`: path string or `null`
   - `framework`: detected framework name
   - `test_file_pattern`: e.g. `"*.test.ts"`
   - `test_cmd`: e.g. `"npx jest"`
   - `mock_library`: e.g. `"jest.mock"`
   - `model_config`: from step 8
   - `user_lang`: from step 1
   - `has_git`: boolean
   - `repo_path`: working directory path
   - `branch`: `"harness/test-gen-<slug>"` or `null`
   - `docs_path`: `"docs/harness/<slug>/"`
   - `phase`: `"setup"`
   - `created_at`: ISO8601 timestamp

10. **Print setup summary** (in `user_lang`):
    ```
    [test-gen] Started!
      Target    : <target>
      Branch    : harness/test-gen-<slug>     ← omit if has_git == false
      Model     : <preset name>
      Framework : <framework>
      Test cmd  : <test_cmd>
      Mock lib  : <mock_library>
      Flag      : <--coverage-gap | --regression <path> | (none)>
    ```

### Phase 1: Analysis

Update state.json: `phase` → `"analyzing"`.

**Determine analysis scope:**

1. **Identify target files/functions.**
   - If `<target>` is a directory: collect all source files within it.
   - If `<target>` is a file: use that file.
   - If `<target>` is a class/module name: search for the file containing it.
   - Count unique source files. Store as `target_file_count`.

2. **Run coverage tool if available, else use static analysis fallback:**

   Try to run the framework's built-in coverage command:
   - Jest: `npx jest --coverage --coverageReporters=text`
   - Vitest: `npx vitest run --coverage`
   - pytest: `pytest --cov=<target> --cov-report=term-missing`
   - Go test: `go test ./... -coverprofile=coverage.out && go tool cover -func=coverage.out`
   - JUnit/RSpec: skip (static fallback only)

   If coverage tool runs successfully → use its output for gap analysis.

   If coverage tool is unavailable or fails → use **static analysis fallback**:
   - Scan for existing test files matching the source files (using `test_file_pattern`).
   - For each source file: check if a corresponding test file exists.
   - Within each test file: list which functions from the source are referenced.
   - Mark functions with no test references as "untested".
   - Show notice (in `user_lang`): "For accurate coverage analysis, install [coverage tool]. Using static analysis fallback — results may be approximate."

3. **--coverage-gap mode:** Filter analysis to only the lowest-coverage or untested functions. Prioritize functions with 0% coverage first, then those with <50%.

4. **--regression mode:**
   - Read the debug report at `regression_report_path`.
   - If file does not exist: Ask the user using AskUserQuestion (in `user_lang`):
       header: "Regression"
       question: "Debug report not found at {regression_report_path}. Provide bug details manually?"
       options:
         - label: "Describe bug" / description: "I will describe the bug and reproduction steps"
         - label: "Stop" / description: "Halt and locate the debug report first"
     If "Describe bug": collect from user via AskUserQuestion: (a) bug description, (b) reproduction steps, (c) expected vs actual behavior.
     If "Stop": halt.
   - Extract: root cause, reproduction conditions, affected functions.

5. **Dependency analysis + mocking strategy:**
   For each target function, inspect its imports/dependencies:

   | Dependency type | Default strategy |
   |----------------|-----------------|
   | DB (Repository, ORM, ActiveRecord) | Repository interface mock |
   | External API (HTTP client, fetch, axios) | HTTP client mock |
   | File system (fs, os.path, File) | Temp dir or fs mock |
   | Time (Date, Timer, time.Now) | Fake timers |
   | Environment vars (process.env, os.environ) | Test-specific env setup |

   Document the mocking strategy for each identified dependency.

6. **Generate edge cases + boundary values list** for each target function:
   - Null / empty / zero inputs
   - Maximum boundary values
   - Invalid type inputs (if applicable)
   - Error/exception paths

7. **Large target delegation:** If `target_file_count >= 4`, delegate coverage analysis to a sub-agent:
   - Read template: `{CLAUDE_PLUGIN_ROOT}/templates/test-gen/coverage_analyst.md`
   - Fill variables: `{target}`, `{framework}`, `{mock_library}`, `{repo_path}`, `{user_lang}`, `{output_path}`: `.harness/test-gen/analysis.md`
   - If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Coverage Analyst → executor role).
   - Launch sub-agent. Wait for completion.
   - Verify `.harness/test-gen/analysis.md` exists.

   If `target_file_count < 4`: write analysis directly to `.harness/test-gen/analysis.md` yourself.

8. **Write `.harness/test-gen/analysis.md`** with sections:
   ### Target Summary
   List of target files and functions to be tested.

   ### Coverage Status
   Existing coverage percentages (or static analysis findings). Mark untested functions.

   ### Mocking Strategy
   For each dependency: type, identified instances, chosen mock approach.

   ### Edge Cases & Boundary Values
   Per function: list of edge/boundary scenarios to test.

   ### Test Priority
   Ordered list: which functions to test first (by risk/complexity/coverage gap).

   (If --regression mode): add section:
   ### Regression Scenario
   Root cause summary, reproduction conditions, target functions.

9. Print status (in `user_lang`):
   ```
   [test-gen] Analysis complete.
     Target files : <N>
     Untested fns : <M>
     Dependencies : <K> identified
     Output       : .harness/test-gen/analysis.md
   ```

### HARD GATE — Test Scope Confirmation

<HARD-GATE>
Show analysis.md to the user and ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Scope"
  question: "Review the test scope and mocking strategy above. Confirm to generate test code."
  options:
    - label: "Proceed" / description: "Generate tests as analyzed"
    - label: "Modify" / description: "Adjust scope or mocking strategy, then re-confirm"
    - label: "Stop" / description: "Halt the workflow"

If user selects "Modify" or provides modification details via "Other": update analysis.md accordingly and re-present this question.
If user selects "Stop": halt the workflow.
Only "Proceed" advances to the Generation phase.
</HARD-GATE>

### Phase 2: Generation

Update state.json: `phase` → `"generating"`.

1. **Read `.harness/test-gen/analysis.md`** to get the full test scope.

2. **Large target delegation:** If `target_file_count >= 4`, delegate test writing to a sub-agent:
   - Read template: `{CLAUDE_PLUGIN_ROOT}/templates/test-gen/test_generator.md`
   - Fill variables: `{target}`, `{framework}`, `{mock_library}`, `{mocking_strategy}` (mocking section from analysis.md), `{analysis_content}` (full analysis.md content), `{user_lang}`, `{test_file_pattern}`
   - If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Test Generator → executor role).
   - Launch sub-agent. Wait for completion.

   If `target_file_count < 4`: write test files directly yourself.

3. **Write test files** following framework conventions:
   - **Happy path tests:** Normal input → expected output for each function.
   - **Edge case tests:** Each edge/boundary scenario from analysis.md.
   - **Error/exception tests:** Invalid inputs, dependency failures.
   - **Regression tests (if --regression mode):** Reproduce the exact bug scenario, assert the fix.
   - Apply the mocking strategy from analysis.md.
   - Place test files at paths matching `test_file_pattern` (alongside source files or in test/ directory, matching existing project conventions).
   - Each test must have at least 1 meaningful assertion. Never write `expect(true).toBe(true)` or equivalent trivial assertions.
   - Import and mock correctly per `mock_library` conventions.

4. **Write `docs/harness/<slug>/test_changes.md`** with sections:
   ### Test Files Created
   - List of created test file paths
   - Number of test cases per file

   ### Test Coverage Targets
   - Functions covered by the new tests
   - Expected coverage improvement

   ### Mocking Applied
   - Summary of mock patterns used

5. Print status (in `user_lang`):
   ```
   [test-gen] Generation complete.
     Test files : <N> created
     Test cases : <M> total
     Output     : docs/harness/<slug>/test_changes.md
   ```

### Phase 3: Verification

Update state.json: `phase` → `"verifying"`.

#### Step 1 — Execution

1. **Run generated tests:**
   Execute `test_cmd` (scoped to the new test files if possible, e.g. `npx jest <test_file>` or `pytest <test_file>`).

2. **If tests pass:** proceed to Step 2 (Meaningfulness).

3. **If tests fail:**
   - Analyze the error output.
   - Fix **TEST CODE ONLY** — never modify production source files.
   - Re-run the tests.
   - If still failing: fix again and re-run (max 2 retries total, i.e. up to 3 runs).
   - After 2 failed retries: report to user using AskUserQuestion (in `user_lang`):
       header: "Test Failure"
       question: "Tests still failing after 2 fix attempts. [error summary]. How to proceed?"
       options:
         - label: "Show errors" / description: "Display full error output for manual inspection"
         - label: "Stop" / description: "Halt — save partial results"
     Halt and write partial test_report.md with failure details.

#### Step 2 — Meaningfulness (Simplified Mutation Testing)

For each **new test** generated, perform mutation testing on its target function:

1. **Identify the key logic** in the production function (e.g. a conditional branch, a return value, a loop boundary).
2. **Apply one mutation** — choose the most impactful type:
   - **Condition inversion:** change `if (a > b)` → `if (a <= b)` (or `if (condition)` → `if (!condition)`)
   - **Return value change:** change `return result` → `return null` (or a wrong constant)
   - **Arithmetic operator change:** `+` → `-`, `*` → `/`
3. **Re-run only the test** targeting this mutated function.
4. **Evaluate:**
   - If the test **fails** after mutation → test is meaningful (catches the mutation). Mark as ✓ PASS.
   - If the test **still passes** after mutation → test is trivial (does not catch a key logic change). Mark as ⚠ TRIVIAL.
     - **Attempt to strengthen:** Rewrite the test to add a more specific assertion (1 try only).
     - Re-run with mutation — if it now fails, mark as ✓ STRENGTHENED.
     - If still passing: mark as ⚠ TRIVIAL (could not strengthen).
5. **Revert the mutation immediately** after evaluating each test. Never leave mutated code in place.

**Safety:** If mutation fails to apply (e.g. function is too short or too complex), skip mutation for that test and mark as ⚪ SKIPPED (mutation not applicable).

#### Output — Test Report

Write `docs/harness/<slug>/test_report.md` with sections:

### Test Execution Results
- Total tests run: N
- Passed: M
- Failed: K (if any)
- Test command used

### Mutation Testing Summary
| Test name | Target function | Mutation applied | Result |
|-----------|----------------|-----------------|--------|
| test_foo_returns_sum | add() | Return value → null | ✓ PASS |
| test_bar_empty | bar() | Condition inversion | ⚠ TRIVIAL |
| ... | ... | ... | ... |

### Quality Score
- Meaningful tests: N / Total
- Trivial tests (could not strengthen): K
- Skipped (not applicable): J
- **Overall quality: X%** (meaningful + strengthened / total non-skipped)

### Recommendations
- Any tests marked TRIVIAL: suggested improvements
- Coverage gaps still remaining (if any)

Print final status (in `user_lang`):
```
[test-gen] Verification complete.
  Tests passed  : <N>/<total>
  Quality score : <X>% meaningful
  Trivial tests : <K>
  Output        : docs/harness/<slug>/test_report.md
```

### Cleanup & Commit

Ask the user using AskUserQuestion (in `user_lang`):
  header: "Commit"
  question: "Test generation complete. Choose how to finish:"
  options:
    - label: "Commit tests only (Recommended)" / description: "Clean up artifacts (.harness/, docs/harness/) then commit test files only"
    - label: "Commit all" / description: "Commit everything including artifacts (test_changes.md, test_report.md)"
    - label: "No commit" / description: "Clean up .harness/ only, do not commit (changes remain in working tree)"

Actions per selection:
- "Commit tests only": delete `.harness/` dir, delete `docs/harness/<slug>/` dir, stage and commit new test files
- "Commit all": delete `.harness/` dir, stage and commit test files + `docs/harness/<slug>/` files
- "No commit": delete `.harness/` dir only

**If has_git == false:** Skip this question entirely. Inform the user (in `user_lang`) that artifacts are saved in `docs/harness/<slug>/`. Clean up `.harness/` directory only. Do not attempt any git operations.

Update state.json: `phase` → `"completed"`.

### Status Check (anytime)

If the user asks for status at any point, print status in the standard format defined above.

## Smart Routing (after completion)

After successful completion, suggest related actions (in `user_lang`):
- **`/memory save`** — record testing decisions and patterns for future sessions
- **If trivial tests were found or production bugs uncovered during testing:** suggest `/debug` to investigate root causes

## Model Selection

Sub-agents run on different models depending on the selected `model_config` preset. All test-gen sub-agents use the executor role:

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Coverage Analyst | executor | (inherit) | opus | sonnet | haiku |
| Test Generator | executor | (inherit) | opus | sonnet | haiku |

**Applying model config:** When launching any sub-agent, if `model_config.preset` is not `"default"`, pass the `model` parameter according to the table above. Sub-agents must NOT directly access state.json to read model_config — the orchestrator passes the model parameter at launch time.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`

## Key Rules

- **NEVER modify production code.** Test code only. If a test fails due to a bug in the source, report it — do not fix the source.
- **Mutations must always be reverted.** Never leave mutated production code in place. Revert immediately after each mutation test.
- **--coverage-gap and --regression are mutually exclusive.** Error and stop if both are provided.
- **V1 has no mode selection.** Always single mode. Auto-delegate to sub-agents for 4+ file targets.
- **Confirmation gates are non-negotiable.** The HARD GATE after analysis must receive explicit "Proceed" before generation starts.
- **Trivial assertions are forbidden.** Every test must have at least 1 assertion that would fail if the target function's logic was broken.
- **Framework detection is required.** If the framework cannot be detected and the user cannot specify one, stop with a clear error message.
- **User language.** All user-facing output must be in `user_lang`. Re-detect on every user message.
- **Intermediate outputs are ephemeral.** `.harness/test-gen/analysis.md` is a working artifact. Final artifacts (test_changes.md, test_report.md) live in `docs/harness/<slug>/`.
