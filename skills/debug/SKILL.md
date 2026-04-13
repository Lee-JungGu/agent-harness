---
name: debug
description: Hypothesis-driven debugger with mandatory executable verification. Classifies build/compile vs runtime/logic errors, attempts reproduction, generates falsifiable hypotheses verified by code search, git history, and test execution. Quick mode (orchestrator only) or deep mode (2 specialist sub-agents + cross-verification). Use when facing a bug, unexpected behavior, or error that needs systematic root cause analysis.
---

# Agent Harness Debug

You are orchestrating a **hypothesis-driven debugging workflow** with mandatory executable verification at every step.

**Core principle:** Every hypothesis must be tested with real actions — code search, git blame, test execution, file reads. Pure reasoning-only conclusions are prohibited.

**Zero-setup:** No initialization required. Works with or without a git repository.

## Environment Detection

At startup, detect whether the current directory is inside a git repository:
```
git rev-parse --is-inside-work-tree 2>/dev/null
```
- If the command succeeds → `has_git = true`
- If the command fails → `has_git = false`

Store `has_git` in state.json. When `has_git == false`, skip all git operations (branch creation, git blame, git log). Use alternative strategies: file reads, Grep, directory traversal.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, hypothesis descriptions, report narrative, confirmation gate prompts and options.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (hypotheses.md, root_cause.md, fix_changes.md, debug_report.md), git branch names (if has_git).

## Standard Status Format

When displaying status, read `.harness/state.json` and print (in `user_lang`):
```
[debug]
  Error  : <error description, truncated to 60 chars>
  Mode   : <quick | deep>
  Model  : <model_config preset name>
  Phase  : <phase label>
  Branch : <branch>    ← omit this line if has_git == false
```
Phase labels: `setup` → "Setup", `reproducing` → "Reproducing error", `analyzing` → "Root cause analysis", `fixing` → "Applying fix", `completed` → "Completed"

## Session Recovery

Before starting a new debug session, check if `.harness/state.json` already exists **and** `state.json.skill` equals `"debug"`:

1. If it exists and matches, print status in the standard format (including Model line from `model_config`), prefixed with `[debug] Previous debug session detected.`
2. Restore `model_config` from state.json. Apply it to all subsequent sub-agent launches.
3. If `has_git` is not present in state.json (pre-existing session from older version), re-detect using the Environment Detection command and store the result.
4. Ask the user using AskUserQuestion (in `user_lang`):
     header: "Session"
     question: "[debug] Previous debug session detected. [print status in standard format]. Resume, restart, or stop?"
     options:
       - label: "Resume" / description: "Continue from {phase} where the previous session left off"
       - label: "Restart" / description: "Delete .harness/ and start from scratch"
       - label: "Stop" / description: "Delete .harness/ and halt"

   Actions per selection:
   - **Resume**: Jump to the phase matching state.json phase:
     `setup` → Step 1 |
     `reproducing` → Phase 0.7 |
     `analyzing` → Phase 1 (if `.harness/debug/hypotheses.md` exists, resume hypothesis loop; else restart Phase 1) |
     `fixing` → Phase 2 |
     `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist (or `state.json.skill` is not `"debug"`), proceed to Step 1 normally.

## Workflow

When the user describes a bug or error (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Detect user language** from the error description. Store as `user_lang`.
2. **Parse flags** from the user's input:
   - `--mode quick` or `--mode deep` → set mode directly, skip mode prompt
   - `--model-config <preset>` → set model_config directly, skip model prompt
   - `--attach <file>` → read the specified file as additional context (stack trace, log file, etc.)
3. **Slugify the error description:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 40 chars. Store as `<slug>`.
4. **Create directories:** `.harness/`, `.harness/debug/`, `docs/harness/<slug>/`
5. **Create git branch (if has_git):** `git checkout -b harness/debug-<slug>`. If `has_git == false`, skip this step entirely.
6. **Mode selection:**
   If `--mode quick` or `--mode deep` was passed, set mode and skip prompt. Otherwise, ask the user using AskUserQuestion (in `user_lang`):
     header: "Mode"
     question: "Select debug mode:"
     options:
       - label: "quick (Recommended)" / description: "Orchestrator runs hypothesis loop directly. Fast, ~1x tokens"
       - label: "deep" / description: "2 specialist sub-agents (Error Analyst + Code Archaeologist) + cross-verification. ~2x tokens. Deepest analysis"
7. **Model configuration selection (deep mode only):**
   If mode is `quick`, skip this step entirely (no sub-agents in quick mode).

   If `--model-config <preset>` was passed, use it directly. Otherwise, use AskUserQuestion to ask the user (in `user_lang`):
     header: "Model"
     question: "Select model configuration for sub-agents:"
     options:
       - label: "default" / description: "Inherit parent model, no changes"
       - label: "all-opus" / description: "All sub-agents use Opus (highest quality)"
       - label: "balanced (Recommended)" / description: "Sonnet executor + Opus advisor (cost-efficient)"
       - label: "economy" / description: "Haiku executor + Sonnet advisor (max savings)"

   **If "Other" selected:** Parse custom format `executor:<model>,advisor:<model>`. Validate each model name — only `opus`, `sonnet`, `haiku` are allowed (case-insensitive). If any model name is invalid, inform the user which value is invalid and re-ask for input (max 3 retries, then apply `balanced` as default). If parsing succeeds but is partial, fill missing roles with the `balanced` defaults (executor=sonnet, advisor=opus). Show the parsed result to the user and ask for confirmation before proceeding.

   **Model config is set once at session start and cannot be changed mid-session.** To change, restart the session.

   Store result as `model_config` object: `{ "preset": "<name>", "executor": "<model|null>", "advisor": "<model|null>" }`. For the `default` preset, store `{ "preset": "default" }`.

8. **Write `.harness/state.json`** with fields:
   - `skill`: `"debug"`
   - `phase`: `"setup"`
   - `mode`: `"quick"` or `"deep"`
   - `model_config`: (from step 7; for quick mode: `{ "preset": "default" }`)
   - `user_lang`
   - `has_git` (boolean)
   - `repo_path`: working directory path
   - `branch`: (if has_git: `"harness/debug-<slug>"`, else: null)
   - `error_description`: the user's original error description
   - `error_type`: null (set in Phase 0.5)
   - `slug`: `<slug>`
   - `docs_path`: `"docs/harness/<slug>/"`
   - `created_at`: ISO8601

9. **Print setup summary** (in `user_lang`):
   ```
   [debug] Debug session started!
     Directory : <path>
     Branch    : harness/debug-<slug>     ← omit if has_git == false
     Mode      : <quick | deep>
     Model     : <preset name>            ← omit if quick mode
   ```

### Phase 0.5: Error Type Classification

Classify the error into one of three types by examining the error description and any attached files:

| Type | Signals |
|------|---------|
| **build/compile** | Compiler error, syntax error, missing import, type mismatch at build time, linker error |
| **runtime** | Exception/panic at runtime, crash, segfault, unhandled promise rejection, null pointer during execution |
| **logic** | Wrong output, unexpected behavior, test failure, business logic bug, off-by-one |

1. Read the error description (and `--attach` file if provided). Classify the error type.
2. Update state.json: `error_type` → `"build"`, `"runtime"`, or `"logic"`.
3. Inform the user of the classification (in `user_lang`): `[debug] Error classified as: <type>`.

**Fast path for build/compile errors:**

If `error_type == "build"`:
- Skip Phase 0.7 (reproduction attempt) — build errors reproduce deterministically.
- Skip Phase 1 (hypothesis loop) — the compiler output is direct evidence.
- Analyze the compiler output directly: identify the exact line, error code, and cause.
- Write a simplified `docs/harness/<slug>/root_cause.md` with the build error, affected file:line, and proposed fix.
- Present a simplified HARD-GATE:
  <HARD-GATE>
  Ask the user using AskUserQuestion (in `user_lang`):
    header: "Build Fix"
    question: "Build error root cause identified: [brief description]. Proceed to fix?"
    options:
      - label: "Fix it" / description: "Apply the fix directly"
      - label: "Record only" / description: "Save root_cause.md and stop — fix manually"
      - label: "Stop" / description: "Halt without saving"

  - "Fix it" → go to Phase 2
  - "Record only" → write root_cause.md, update state.json phase → "completed", halt
  - "Stop" → halt
  </HARD-GATE>

**If `error_type == "runtime"` or `"logic"`:** Continue to Phase 0.7.

### Phase 0.7: Reproduction Attempt

**Goal:** Confirm the error can be reproduced, and document the exact conditions under which it occurs.

Update state.json: `phase` → `"reproducing"`.

1. **Identify reproduction strategy:**
   - If the project has a test command (detect from project files — see language detection table in Step 1), attempt test execution.
   - If the error comes with a specific input or command, attempt to run it.
   - If neither is available, switch to log/environment analysis strategy.

   **Language detection for test commands:**

   | File | Language | Test Command |
   |------|----------|-------------|
   | `build.gradle(.kts)` | java | `./gradlew test` |
   | `pom.xml` | java | `mvn test` |
   | `pyproject.toml` / `setup.py` | python | `pytest` |
   | `package.json` | typescript | `npm test` |
   | `*.csproj` | csharp | `dotnet test` |
   | `go.mod` | go | `go test ./...` |
   | `Cargo.toml` | rust | `cargo test` |

2. **Attempt reproduction:**
   - Run the test command or reproduction script.
   - Capture full output (stdout + stderr).

3. **Record result:**
   - **Success (error reproduced):** Write reproduction conditions to `.harness/debug/hypotheses.md`:
     ```
     ## Reproduction
     - Reproduction command: <command>
     - Reproduction output: <captured output (truncated if > 50 lines)>
     - Reproduction conditions: <environment, inputs, state>
     ```
     Inform the user (in `user_lang`): `[debug] Error reproduced. Proceeding to root cause analysis.`
   - **Failure (cannot reproduce):** Switch to log/environment analysis strategy:
     - Read available log files, config files, and environment variables.
     - Note in `.harness/debug/hypotheses.md`: "Could not reproduce directly. Proceeding with log/environment analysis."
     - Inform the user (in `user_lang`): `[debug] Could not reproduce directly. Switching to log/environment analysis strategy.`

4. Continue to Phase 1 regardless of reproduction outcome.

### Phase 1: Root Cause Analysis — Hypothesis Verification Loop

Update state.json: `phase` → `"analyzing"`.

---

## Falsification Rules (Core Differentiator)

Every hypothesis MUST be tested with executable verification actions. Pure reasoning-only falsification is **PROHIBITED**.

1. Write hypotheses to `.harness/debug/hypotheses.md` FIRST (physical separation from docs/).
2. For each hypothesis, formulate: **"If this hypothesis is WRONG, what evidence should exist in the code?"**
3. Execute **at least 1 verification action** per hypothesis:
   - Code search (Grep/Glob): check for specific patterns that should or should not exist
   - `git blame`/`git log`: check change history of the relevant file/function (only if has_git)
   - Test execution: run specific targeted tests to verify expected behavior
   - File read: check config files, environment variables, dependency versions
4. **Adjust confidence ONLY based on verification action results**, not reasoning.
5. Mark refuted hypotheses as `[REFUTED]` with the evidence that refuted them in hypotheses.md.

---

#### If mode == "quick": Phase 1-Q

1. **Generate 3 initial hypotheses** based on the error description, reproduction output, and codebase exploration. Assign each a confidence level: High / Medium / Low.

2. **Write all 3 hypotheses to `.harness/debug/hypotheses.md`** in this format:
   ```
   ## Hypothesis 1 — [ACTIVE] — High confidence
   **Claim:** <one-sentence hypothesis>
   **Falsification question:** If this is wrong, what evidence should exist?
   **Verification actions:** (to be executed)
   **Evidence:** (to be filled after verification)
   **Result:** (to be filled)

   ## Hypothesis 2 — [ACTIVE] — Medium confidence
   ...

   ## Hypothesis 3 — [ACTIVE] — Low confidence
   ...
   ```

3. **For each hypothesis (in confidence order, High first):**
   a. Formulate the falsification question: "If hypothesis N is wrong, X evidence should be visible."
   b. Execute at least 1 verification action (Grep, file read, git blame, test run).
   c. Record the verification action and its output in hypotheses.md.
   d. Adjust confidence or mark as `[REFUTED]` based on evidence.
   e. If a hypothesis is confirmed at High confidence → proceed to write root_cause.md.

4. **Loop termination conditions (max 3 rounds):**
   - **High confidence found:** Write root_cause.md and exit loop.
   - **All refuted, no new hypotheses:** Write root_cause.md with `confidence: "unknown"`, note that cause could not be determined from available evidence.
   - **Max 3 rounds reached:** Write root_cause.md with the highest-confidence surviving hypothesis, note uncertainty.

   Between rounds: generate up to 3 new hypotheses based on refutation evidence. Update hypotheses.md.

5. **Write `docs/harness/<slug>/root_cause.md`:**
   ```markdown
   # Root Cause Analysis

   ## Error Description
   <original error>

   ## Error Type
   <build | runtime | logic>

   ## Reproduction
   <reproduction conditions or "not reproduced — log/environment analysis">

   ## Root Cause
   <clear description of the root cause>

   ## Evidence
   <list of verification actions executed and their results>

   ## Confidence
   <High | Medium | Low | Unknown>

   ## Affected Locations
   <file:line references>

   ## Hypothesis History
   <brief summary of refuted hypotheses and why they were ruled out>
   ```

#### If mode == "deep": Phase 1-D

1. **Collect shared context** and save to `.harness/debug/context.md`:
   - Directory structure (top 3 levels)
   - Relevant file list (based on error description)
   - Reproduction output (from hypotheses.md)
   - Tech stack summary

2. **Launch Error Analyst and Code Archaeologist in parallel:**
   a. Read `{CLAUDE_PLUGIN_ROOT}/templates/debug/error_analyst.md`.
   b. Read `{CLAUDE_PLUGIN_ROOT}/templates/debug/code_archaeologist.md`.
   c. Fill template variables for each:
      - Error Analyst: `{error_description}`, `{stack_trace}` (from error or attached file), `{repo_path}`, `{user_lang}`, `{output_path}`: `.harness/debug/analysis_error_analyst.md`
      - Code Archaeologist: `{error_description}`, `{repo_path}`, `{user_lang}`, `{output_path}`: `.harness/debug/analysis_code_archaeologist.md`
   d. **Launch 2 sub-agents in parallel** using the Agent tool. Each receives its template only — no access to the other sub-agent's output (anchoring prevention). If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (both → advisor role).
   e. Wait for both to complete. Verify both analysis files exist.

3. **Launch Cross Verification:**
   a. Read `{CLAUDE_PLUGIN_ROOT}/templates/debug/cross_verification.md`.
   b. Read both analysis files from step 2.
   c. Fill template variables:
      - `{error_analyst_output}`: full content of `analysis_error_analyst.md`
      - `{archaeologist_output}`: full content of `analysis_code_archaeologist.md`
      - `{user_lang}`
      - `{root_cause_path}`: `docs/harness/<slug>/root_cause.md`
   d. **Launch 1 sub-agent** (Cross Verifier). If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Cross Verifier → advisor role).
   e. Wait for completion. Verify `docs/harness/<slug>/root_cause.md` exists.

4. Inform the user (in `user_lang`):
   ```
   [debug] Analysis complete.
     Analysts  : Error Analyst + Code Archaeologist (independent)
     Synthesis : Cross Verifier synthesized findings
     Output    : root_cause.md written
   ```

### HARD-GATE: Fix Decision

<HARD-GATE>
Read root_cause.md and present a summary to the user. Ask using AskUserQuestion (in `user_lang`):
  header: "Fix"
  question: "Root cause identified: [one-sentence summary from root_cause.md]. What would you like to do?"
  options:
    - label: "Fix it" / description: "Proceed to Phase 2 — apply a fix"
    - label: "Record cause only" / description: "Save root_cause.md and stop — fix manually later"
    - label: "Stop" / description: "Halt without saving anything"

- "Fix it" → Update state.json: phase → "fixing". Go to Phase 2.
- "Record cause only" → Update state.json: phase → "completed". Halt.
- "Stop" → Halt.
</HARD-GATE>

### Phase 2: Fix (Optional)

Update state.json: `phase` → `"fixing"`.

**Assess fix complexity:**

| Complexity | Criteria | Strategy |
|------------|----------|----------|
| Simple | Single file, < 20 lines, no architectural impact | Orchestrator applies directly |
| Complex | Multiple files, architectural change, or touches shared interfaces | Smart Routing → `/workflow` |

**Simple fix (orchestrator applies directly):**
1. Read `docs/harness/<slug>/root_cause.md`.
2. Apply the fix directly to the affected files.
3. Run the test command (if available) to verify the fix.
4. Write `docs/harness/<slug>/fix_changes.md`:
   ```markdown
   # Fix Changes

   ## Root Cause (summary)
   <one-sentence root cause from root_cause.md>

   ## Changes Applied
   | File | Lines Changed | Description |
   |------|--------------|-------------|
   | `path/to/file.ts` | 5 | Fixed null check in getUserData() |

   ## Verification
   - Test result: <passed N / failed N / no tests>
   - Verified by: <test execution output summary or manual code review>
   ```

**Complex fix (Smart Routing):**
1. Do NOT apply the fix directly.
2. Inform the user (in `user_lang`) that the fix requires a structured workflow:
   ```
   [debug] This fix is complex (multiple files / architectural change).
   Suggested next step: /workflow "Fix based on docs/harness/<slug>/root_cause.md"
   ```
   Translate the quoted suggestion text to `user_lang`.
3. Write `docs/harness/<slug>/fix_changes.md` noting that fix was deferred to `/workflow`.
4. Do NOT auto-invoke `/workflow`. Suggestion only.

### Phase 3: Prevention (Optional)

After Phase 2 completes (or if the user requests it), offer prevention steps.

Inform the user (in `user_lang`):
```
[debug] Fix applied. Running prevention analysis...
```

1. **Scan for same error pattern in other locations:**
   Use Grep to search the codebase for patterns similar to the root cause (same function, same anti-pattern, same import, etc.). Report any matches to the user.

2. **Suggest Smart Routing actions with concrete commands:**

   | Signal | Suggested Action |
   |--------|-----------------|
   | Root cause is a recurring anti-pattern | `/memory save "Anti-pattern: <description> — see docs/harness/<slug>/debug_report.md"`  |
   | Fix involved adding a new code path | `/test-gen --regression docs/harness/<slug>/debug_report.md` |
   | Root cause is a known risk area | Add a note to the project CLAUDE.md |

   These are **suggestions only** — do not auto-invoke other skills.

3. **Write `docs/harness/<slug>/debug_report.md`** (comprehensive final report):
   ```markdown
   # Debug Report

   ## Session Summary
   | Field | Value |
   |-------|-------|
   | Error | <description> |
   | Type  | <build / runtime / logic> |
   | Mode  | <quick / deep> |
   | Date  | <ISO8601> |

   ## Root Cause
   <full content from root_cause.md>

   ## Fix Applied
   <full content from fix_changes.md, or "Fix deferred to /workflow">

   ## Prevention
   ### Same Pattern Found Elsewhere
   <list of other locations with the same pattern, or "None found">

   ### Recommended Actions
   - <concrete suggested action 1>
   - <concrete suggested action 2>

   ## Hypothesis History
   <summary of all hypotheses tested, confirmed, and refuted>
   ```

4. Update state.json: `phase` → `"completed"`.

5. Print final summary (in `user_lang`):
   ```
   [debug] Debug session complete.
     Root cause : <one-sentence summary>
     Fix        : <"Applied directly" | "Deferred to /workflow" | "Not applied">
     Report     : docs/harness/<slug>/debug_report.md
   ```

### Status Check (anytime)

If the user asks for status, print status in the standard format defined above.

## Model Selection

Sub-agents (deep mode only) can run on different models depending on the selected `model_config` preset:

| Preset | executor | advisor |
|--------|----------|---------|
| default | (parent inherit) | (parent inherit) |
| all-opus | opus | opus |
| balanced | sonnet | opus |
| economy | haiku | sonnet |

### Deep Mode Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Error Analyst | advisor | (no override) | opus | opus | sonnet |
| Code Archaeologist | advisor | (no override) | opus | opus | sonnet |
| Cross Verifier | advisor | (no override) | opus | opus | sonnet |

**Applying model config:** When launching any sub-agent, if `model_config.preset` is not `"default"`, pass the `model` parameter according to the table above for that sub-agent. Sub-agents must NOT directly access state.json to read model_config — the orchestrator passes the model parameter at launch time.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`

## Key Rules

- **Falsification rules are non-negotiable.** Every hypothesis must be verified by at least one executable action (Grep, file read, git blame, test run). Pure reasoning-only falsification is prohibited.
- **Never skip reproduction attempt for runtime/logic errors.** Always attempt Phase 0.7 before Phase 1.
- **Hypothesis verification loop is bounded.** Maximum 3 rounds. If no high-confidence hypothesis after 3 rounds, write root_cause.md with `Confidence: Unknown`.
- **Fix phase: never auto-chain to /workflow.** Only suggest. The user must explicitly invoke `/workflow`.
- **Deep mode: analysts are isolated.** Code Archaeologist must NOT read Error Analyst output (anchoring prevention). Each sub-agent runs independently.
- **All permanent artifacts go to docs/harness/.** Temporary files (.harness/debug/) are ephemeral and cleaned up at session end.
- **Build errors get the fast path.** Skip reproduction and hypothesis loop for build/compile errors. Compiler output is direct evidence.
- **Confirmation gates are non-negotiable.** No implicit approval. The Fix Decision HARD-GATE requires explicit user choice before any code modification.
- **User language.** All user-facing output must be in `user_lang`. Re-detect on every user message.
- **has_git == false fallback.** When git is unavailable, replace `git blame`/`git log` verification actions with file reads, Grep pattern searches, and dependency version checks.
- **State persistence.** Always write state.json before starting any phase. If the skill is interrupted, Session Recovery must be able to resume from the last recorded phase.
