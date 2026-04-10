---
name: refactor
description: Safe, behavior-preserving code structure improvement with 3-tier mode (single/multi/comprehensive). Atomic changes, test after each step, stop on failure. Use when improving code structure without changing behavior.
---

# Agent Harness Refactor

You are orchestrating a 3-Phase refactoring workflow with **selectable single, multi, or comprehensive mode**.

**Core principle:** Same behavior, better structure. Every change must preserve existing behavior. Tests are the safety net.

**Zero-setup:** No initialization required. Auto-detects language, test commands, and build commands from the current directory.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, plan sections, QA report narrative, commit messages, confirmation gate prompts and options.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (refactor_plan.md, changes.md, qa_report.md), git branch names.

## Standard Status Format

When displaying status, read `.harness/state.json` and print (in `user_lang`):
```
[harness]
  Skill  : refactor
  Target : <target>
  Mode   : <single | multi | comprehensive>
  Model  : <model_config preset name>
  Phase  : <phase label>
  Branch : <branch>
  Scope  : <scope>
```
Phase labels: plan_ready → "Analyzer — writing refactor plan", gen_ready → "Executor — applying changes", eval_ready → "Verifier — checking behavior preservation", completed → "Completed"

## Session Recovery

Before starting a new task, check if `.harness/state.json` already exists **and** `state.json.skill` equals `"refactor"`:

1. If it exists and matches, print status in the standard format (including Model line from `model_config`), prefixed with `[harness] Previous refactor session detected.`
2. Restore `model_config` from state.json. Apply it to all subsequent sub-agent launches.
3. Ask the user using AskUserQuestion (in `user_lang`):
     header: "Session"
     question: "[harness] Previous refactor session detected. [print status in standard format]. Resume, restart, or stop?"
     options:
       - label: "Resume" / description: "Continue from {phase} where the previous session left off"
       - label: "Restart" / description: "Delete .harness/ and start from scratch"
       - label: "Stop" / description: "Delete .harness/ and halt"

   Actions per selection:
   - **Resume**: Jump to the step matching state.json phase:
     `plan_ready` → if refactor_plan.md exists go to Step 3, else Step 2 |
     `gen_ready` → Step 4 | `eval_ready` → Step 5 |
     `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist (or belongs to a different skill), proceed to Step 1 normally.

## Smart Routing

Before beginning, evaluate the user's request. If it does not match a refactoring task, suggest a better skill using AskUserQuestion (in `user_lang`):

| Signal | Suggested Skill |
|--------|----------------|
| User describes a new feature or bug fix | `/workflow` |
| User mentions version upgrades, dependency changes, or migration | `/migrate` |
| User wants to understand the codebase before refactoring | `/codebase-audit` |

When a mismatch is detected, ask using AskUserQuestion:
  header: "Routing"
  question: "[detected mismatch]. A different skill may be more appropriate."
  options:
    - label: "Switch: /{suggested skill}" / description: "{why the suggested skill fits better}"
    - label: "Continue" / description: "Proceed with refactor anyway"

If the user selects "Continue", proceed with refactoring.

## Workflow

When the user provides a refactoring target (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Detect user language** from the target description. Store as `user_lang`.
2. **Slugify the target:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.
3. **Auto-detect project language and commands.** Scan the repo root:

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

4. **Git safety check:** Run `git status`. If there are uncommitted changes, ask using AskUserQuestion (in `user_lang`):
     header: "Uncommitted"
     question: "Uncommitted changes detected."
     options:
       - label: "Commit first" / description: "Stage and commit current changes before refactoring"
       - label: "Stash first" / description: "Run git stash to save changes temporarily"
       - label: "Proceed anyway" / description: "Continue with dirty working tree (risky)"
   If user selects "Commit first": stage and commit. If "Stash first": `git stash`. If "Proceed anyway": continue with warning noted.

5. **Create directories:** `.harness/`, `.harness/refactor/`, `docs/harness/<slug>/`
6. **Create git branch:** `git checkout -b harness/refactor-<slug>`

7. **Capture baseline test results:**
   - If `test_cmd` is available, run it and save output to `.harness/refactor/baseline_tests.txt`.
   - Record: total tests, passed, failed, skipped.
   - **If baseline tests are failing:**
     Ask using AskUserQuestion (in `user_lang`):
       header: "Test Fail"
       question: "Baseline tests fail: {N} failures."
       options:
         - label: "Fix first" / description: "Halt refactoring and fix failing tests before proceeding"
         - label: "Proceed anyway" / description: "Continue with known failures (evaluator will ignore them)"
     If user selects "Fix first": halt and suggest `/workflow fix failing tests`. If "Proceed anyway": store baseline failures in state.json as `baseline_failures` so the evaluator can distinguish pre-existing failures from regressions.
   - **If no test command detected:**
     Ask using AskUserQuestion (in `user_lang`):
       header: "No Tests"
       question: "No test suite detected. Behavior preservation will be verified by code review only."
       options:
         - label: "Proceed" / description: "Continue without test verification, rely on code review"
         - label: "Abort" / description: "Halt refactoring until tests are available"
     If user selects "Abort": halt. If "Proceed": set `test_available` to false and continue (verification will rely on code review only).

8. **Mode selection:** If `--mode single`, `--mode multi`, or `--mode comprehensive` was passed, set mode and skip prompt. Otherwise:
   - **Scope-aware recommendation:** Count files affected by the refactoring target.
     - < 3 files → recommend `single`
     - 3-10 files → recommend `multi`
     - 10+ files or architecture-level → recommend `comprehensive`
   - Ask the user using AskUserQuestion (in `user_lang`):
       header: "Mode"
       question: "Select refactoring mode: (scope: {N} files)"
       options:
         - label: "single (Recommended)" / description: "1 agent, fast (~1x tokens)" ← add "(Recommended)" to the auto-recommended mode's label instead
         - label: "multi" / description: "2 analysts + safety advisor (~1.7x tokens)"
         - label: "comprehensive" / description: "3 analysts + cross-verification + safety advisor (~2.5x tokens)"
     Add "(Recommended)" to whichever mode the scope-aware recommendation selects; omit it from the others.

9. **Model configuration selection:**
   If `--model-config <preset>` was passed, use it directly. Otherwise, use AskUserQuestion to ask the user (in `user_lang`):
     header: "Model"
     question: "Select model configuration for sub-agents:"
     options:
       - label: "default" / description: "Inherit parent model, no changes"
       - label: "all-opus" / description: "All sub-agents use Opus (highest quality)"
       - label: "balanced (Recommended)" / description: "Sonnet executor + Opus advisor/evaluator (cost-efficient)"
       - label: "economy" / description: "Haiku executor + Sonnet advisor/evaluator (max savings)"

   **If "Other" selected:** Parse custom format `executor:<model>,advisor:<model>,evaluator:<model>`. Validate each model name — only `opus`, `sonnet`, `haiku` are allowed (case-insensitive). If any model name is invalid, inform the user which value is invalid and re-ask for input (max 3 retries, then apply `balanced` as default). If parsing succeeds but is partial, fill missing roles with the `balanced` defaults (executor=sonnet, advisor=opus, evaluator=opus). Show the parsed result to the user and ask for confirmation before proceeding.

   **Model config is set once at session start and cannot be changed mid-session.** To change, restart the session.

   Store result as `model_config` object: `{ "preset": "<name>", "executor": "<model|null>", "advisor": "<model|null>", "evaluator": "<model|null>" }`. For the `default` preset, store `{ "preset": "default" }`.

10. **Shared context collection (multi/comprehensive only):**
   Collect project context once and save to `.harness/context.md`:
   - Directory structure (top 3 levels)
   - Dependency info (package files content)
   - Tech stack summary
   - Files in scope (list with brief descriptions)
   This avoids duplicate codebase scans by sub-agents.

11. **Write `.harness/state.json`** with fields: `skill` ("refactor"), `target`, `mode` ("single"/"multi"/"comprehensive"), `model_config` (from step 9), `user_lang`, `repo_name`, `repo_path`, `phase` ("plan_ready"), `round` (1), `max_rounds` (3), `scope` (user-provided or "(no limit)"), `branch` ("harness/refactor-<slug>"), `lang`, `test_cmd`, `build_cmd`, `test_available` (true/false), `baseline_test_results` (summary string), `baseline_failures` (list of known-failing tests, or []), `docs_path` ("docs/harness/<slug>/"), `created_at` (ISO8601).
12. **Print setup summary** (in `user_lang`):
    ```
    [harness] Refactor started!
      Repo     : <path>
      Branch   : harness/refactor-<slug>
      Mode     : <single | multi | comprehensive>
      Model    : <preset name>
      Language : <lang>
      Test     : <test_cmd or "none">
      Build    : <build_cmd or "none">
      Baseline : <N tests passing, M failing or "no tests">
      Scope    : <scope>
    ```

### Step 2: Phase 1 — Impact Analysis

Read `mode` from state.json and branch accordingly.

#### If mode == "single": Step 2-S

1. Explore the codebase — read the target files and their dependents/dependencies. Understand the current structure, coupling, and cohesion.
2. Analyze the refactoring target:
   - What structural problems exist? (coupling, cohesion, complexity, duplication)
   - What is the impact scope? (which files depend on the target, which files does the target depend on)
   - What tests cover the target code?
   - What is the safest order of changes?
3. Write `refactor_plan.md` to `docs/harness/<slug>/refactor_plan.md` with the following sections (translate headings to `user_lang`):

   ### Goal
   What structural improvement is being achieved? One or two sentences.

   ### Current State Analysis
   What structural problems exist in the target code? Be specific with file paths and line ranges.

   ### Impact Scope
   Which files will be directly modified? Which files are indirectly affected (dependents)?

   ### Refactoring Steps
   Ordered list of atomic changes. Each step must:
   - Be independently testable
   - Preserve behavior after completion
   - Include: step number, description, files affected, expected test impact
   Use GitHub-flavored Markdown checkboxes:
   - [ ] Step 1: <description> — files: <list> — test: <expected result>
   - [ ] Step 2: ...

   ### Test Coverage Assessment
   Which tests cover the target? Are there gaps? If gaps exist, recommend writing tests first.

   ### Risks
   What could go wrong? For each risk: likelihood, impact, mitigation.

4. Update state.json: phase → `"plan_ready"`.
5. Print status in the standard format, prefixed with `[harness] Analysis complete.`

#### If mode == "multi": Step 2-M

##### Step 2a-M: Shared Context

If `.harness/context.md` was not created in Setup (e.g., resuming from session recovery), create it now following the same collection procedure as Step 1.9.

##### Step 2b-M: Independent Analysis (Parallel)

1. Read two analyst templates from `{CLAUDE_PLUGIN_ROOT}/templates/refactor/`: `structural_analyst.md`, `risk_analyst.md`
2. For each analyst, fill template variables: `{target_description}`, `{repo_path}`, `{lang}`, `{scope}`, `{user_lang}`, `{context}` (from .harness/context.md), `{test_cmd}`, `{baseline_test_results}` from state.json; `{output_path}`: `.harness/refactor/analysis_<analyst>.md`
3. **Launch 2 subagents in parallel** using the Agent tool. Each receives its analyst template and context.md, has no knowledge of the other subagent (anchoring prevention), and writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Structural Analyst, Risk Analyst → executor role).
4. Wait for both to complete. Verify both analysis files exist.

##### Step 2c-M: Synthesis

1. Read the synthesis template: `{CLAUDE_PLUGIN_ROOT}/templates/refactor/synthesis.md`
2. Read both analysis files from Step 2b-M.
3. Interpret the synthesis template with: `{target_description}`, `{user_lang}`, `{all_analyses}` (concatenated with author labels), `{plan_path}`: `docs/harness/<slug>/refactor_plan.md`, `{test_cmd}`, `{baseline_test_results}`
4. Follow the synthesis rules to write `refactor_plan.md`.
5. Update state.json: phase → `"plan_ready"`.
6. Inform the user (in `user_lang`):
   ```
   [harness] Analysis complete.
     Analyses   : 2 specialists analyzed independently
     Output     : refactor_plan.md synthesized
   ```

#### If mode == "comprehensive": Step 2-C

##### Step 2a-C: Shared Context

Same as Step 2a-M.

##### Step 2b-C: Independent Analysis (Parallel)

1. Read three analyst templates from `{CLAUDE_PLUGIN_ROOT}/templates/refactor/`: `structural_analyst.md`, `risk_analyst.md`, `feasibility_analyst.md`
2. For each analyst, fill template variables: same as Step 2b-M, plus `{output_path}`: `.harness/refactor/analysis_<analyst>.md`
3. **Launch 3 subagents in parallel.** Each receives its analyst template and context.md, has no knowledge of other subagents, and writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Structural Analyst, Risk Analyst, Feasibility Analyst → executor role).
4. Wait for all 3 to complete. Verify all 3 analysis files exist.

##### Step 2c-C: Cross-Verification (Parallel)

1. Read the cross-critique template: `{CLAUDE_PLUGIN_ROOT}/templates/refactor/cross_critique.md`
2. Read all 3 analysis files from Step 2b-C.
3. For each analyst, prepare the cross-critique prompt with: `{analyst_name}`, `{target_description}`, `{user_lang}`, `{analysis_1_author}`, `{analysis_1_content}`, `{analysis_2_author}`, `{analysis_2_content}` (the OTHER two analyses), `{output_path}`: `.harness/refactor/critique_<analyst>.md`
4. **Launch 3 subagents in parallel.** Each writes to `.harness/refactor/critique_<analyst>.md`. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (advisor role — cross-critique requires critical judgment).
5. Wait for all 3 to complete. Verify all 3 critique files exist.

##### Step 2d-C: Synthesis

1. Read the synthesis template: `{CLAUDE_PLUGIN_ROOT}/templates/refactor/synthesis.md`
2. Read all 6 intermediate files (3 analyses + 3 critiques).
3. Interpret the synthesis template with: `{target_description}`, `{user_lang}`, `{all_analyses}` (concatenated with author labels), `{all_critiques}` (concatenated with author labels — pass empty string `""` if multi mode), `{plan_path}`: `docs/harness/<slug>/refactor_plan.md`, `{test_cmd}`, `{baseline_test_results}`
4. Follow the synthesis rules to write `refactor_plan.md`.
5. Update state.json: phase → `"plan_ready"`.
6. Inform the user (in `user_lang`):
   ```
   [harness] Analysis complete.
     Analyses        : 3 specialists analyzed independently
     Cross-reviews   : 3 cross-verifications completed
     Output          : refactor_plan.md synthesized
   ```

### Step 3: HARD GATE — Plan Confirmation

<HARD-GATE>
Show refactor_plan.md to the user and ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Plan"
  question: "Review the plan. {mode} mode uses ~{N}x tokens."
  options:
    - label: "Proceed" / description: "Start execution as planned"
    - label: "Modify" / description: "Edit the plan, then re-confirm"
    - label: "Switch to single" / description: "Reduce scope to single-agent mode (~1x tokens)"
    - label: "Stop" / description: "Halt the workflow"

If user selects "Modify" or provides modification details via "Other": update refactor_plan.md and re-present this question.
If user selects "Switch to single": update mode in state.json to "single" and re-present this question.
If user selects "Stop": halt the workflow.
Only "Proceed" advances to the Execution phase.
</HARD-GATE>

### Step 4: Phase 2 — Execution

Read `mode` from state.json and branch accordingly.

**Core execution principles (all modes):**
- **Atomic changes:** Execute one refactoring step at a time from the plan.
- **Test after each step:** Run `test_cmd` after every step. Compare with baseline.
- **Stop on failure:** If any test that was passing in baseline now fails, STOP IMMEDIATELY. Do NOT attempt auto-fix. Report the failure and ask the user.
- **No tests available:** If `test_available` is false, perform manual code review of behavior equivalence after each step instead of running tests.

#### If mode == "single": Step 4-S

1. Update state.json: phase → `"gen_ready"`, read current round.
2. For each step in refactor_plan.md (in order):
   a. Announce the step (in `user_lang`): `[harness] Step N: <description>`
   b. Execute the refactoring change.
   c. Run `test_cmd` (if available). Compare results with baseline.
   d. **If new test failure:**
      Ask using AskUserQuestion (in `user_lang`):
        header: "Regression"
        question: "Test regression detected (Step {N}). Failed: {test}."
        options:
          - label: "Revert step" / description: "Undo this step, mark as failed, continue to next step"
          - label: "Manual fix" / description: "Pause for manual fix, then re-run tests"
          - label: "Abort refactoring" / description: "Stop all refactoring and go to cleanup"
      If "Revert step": undo the step, mark it as failed in changes.md, continue to next step.
      If "Manual fix": wait for user to fix, then re-run tests.
      If "Abort refactoring": go to Step 7 (cleanup).
   e. If tests pass (or no tests): mark step as done, continue.
3. After all steps complete, write `docs/harness/<slug>/changes.md` with sections:
   - Round {round_num} Changes
   - Completed Steps (with checkbox status from plan)
   - Modified Files — path + brief reason
   - Created Files (if any)
   - Deleted Files (if any)
   - Test Results After Each Step (summary)
4. Print status in the standard format, prefixed with `[harness] Execution complete.`

#### If mode == "multi" or mode == "comprehensive": Step 4-MC

##### Step 4a-MC: Execution with Safety Advisor

1. Update state.json: phase → `"gen_ready"`, read current round.
2. For each step in refactor_plan.md (in order):
   a. Announce the step (in `user_lang`): `[harness] Step N: <description>`
   b. Read the safety advisor template: `{CLAUDE_PLUGIN_ROOT}/templates/refactor/safety_advisor.md`
   c. Prepare the safety advisor prompt: `{step_number}`, `{step_description}`, `{files_affected}`, `{refactor_plan_content}` (full plan for context), `{repo_path}`, `{lang}`, `{test_cmd}`, `{user_lang}`, `{previous_steps_summary}` (what was already done)
   d. **Launch 1 subagent** (Safety Advisor) to review the proposed step BEFORE execution. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Safety Advisor → advisor role). The Safety Advisor:
      - Verifies the step preserves behavior
      - Identifies any behavioral side effects
      - Gives GO / CAUTION / STOP recommendation
   e. **If Safety Advisor says STOP:** Report to user with explanation. Ask: (skip step / modify step / abort)
   f. **If Safety Advisor says CAUTION:** Report concerns to user. Ask: (proceed with caution / skip step / abort)
   g. **If Safety Advisor says GO (or user overrides):** Execute the refactoring change.
   h. Run `test_cmd` (if available). Compare results with baseline.
   i. **If new test failure:** Same handling as Step 4-S.2.d.
   j. If tests pass: mark step as done, continue.
3. After all steps complete, write `docs/harness/<slug>/changes.md` with sections:
   - Round {round_num} Changes
   - Completed Steps (with checkbox status)
   - Safety Advisor Assessments (per step: GO/CAUTION/STOP + brief note)
   - Modified Files — path + brief reason
   - Created Files (if any)
   - Deleted Files (if any)
   - Test Results After Each Step (summary)
4. Inform the user (in `user_lang`):
   ```
   [harness] Execution complete.
     Steps    : N/M completed
     Safety   : Safety Advisor reviewed each step
     Tests    : All passing (or: N regressions detected)
     Output   : changes.md written
   ```

### Step 5: Phase 3 — Verification (Isolated Subagent)

1. Update state.json: phase → `"eval_ready"`.
2. Read the evaluator template: `{CLAUDE_PLUGIN_ROOT}/templates/refactor/evaluator.md`
3. **Prepare the subagent prompt.** Fill in: `{refactor_plan_content}` (structural goals only — strip implementation details), `{changed_files_list}` (file paths only from changes.md — **strip all reasoning** to prevent anchoring), `{test_available}`, `{build_cmd}`, `{test_cmd}`, `{baseline_test_results}`, `{baseline_failures}` (pre-existing failures to ignore), `{round_num}`, `{scope}`, `{user_lang}` from state.json, `{qa_report_path}`: `docs/harness/<slug>/qa_report.md`.
   **Do NOT include:** Execution reasoning, safety advisor assessments, why files were changed, or references to "Generator"/"AI"/"agent" as code author.
4. **Launch the Evaluator subagent** using the Agent tool. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Evaluator → evaluator role). Instruct it to write the QA report to `docs/harness/<slug>/qa_report.md`.
5. When the subagent returns, read `docs/harness/<slug>/qa_report.md` to get the verdict.

### Step 6: Verdict & Loop

Read qa_report.md and determine verdict (look for "Verdict: PASS" or "Verdict: FAIL").

**If PASS:** Update state.json: phase → `"completed"`. Inform user: refactoring complete, behavior preserved. Proceed to Step 7.

**If FAIL and rounds remaining (round < max_rounds):** Do NOT auto-retry. Ask the user using AskUserQuestion (in `user_lang`):
  header: "QA"
  question: "QA result: FAIL. [failure summary]."
  options:
    - label: "Fix" / description: "Run next round to fix FAIL items only"
    - label: "Accept as-is" / description: "Finish without fixing, keep current state"
If user selects "Fix": increment round, go to Step 4. If "Accept as-is": phase → "completed", go to Step 7.

**If FAIL and max rounds reached:** phase → `"completed"`. Inform user of remaining issues. Proceed to Step 7.

### Step 7: Cleanup & Commit

Ask the user using AskUserQuestion (in `user_lang`):
  header: "Commit"
  question: "Implementation complete. Choose how to finish:"
  options:
    - label: "Commit code only (Recommended)" / description: "Clean up artifacts (.harness/, docs/harness/) then commit code changes only"
    - label: "Commit all" / description: "Commit everything including artifacts (refactor_plan.md, changes.md, qa_report.md)"
    - label: "No commit" / description: "Clean up .harness/ only, do not commit (changes remain in working tree)"

Actions per selection:
- "Commit code only": delete `.harness/` dir, delete `docs/harness/<slug>/` dir, stage and commit remaining code changes
- "Commit all": delete `.harness/` dir, stage and commit `docs/harness/<slug>/` files + code changes
- "No commit": delete `.harness/` dir only

### Status Check (anytime)

If user asks for status, print status in the standard format defined above.

## Model Selection

Sub-agents can run on different models depending on the selected `model_config` preset. The presets map each role (executor, advisor, evaluator) to a model:

| Preset | executor | advisor | evaluator |
|--------|----------|---------|-----------|
| default | (parent inherit) | (parent inherit) | (parent inherit) |
| all-opus | opus | opus | opus |
| balanced | sonnet | opus | opus |
| economy | haiku | sonnet | sonnet |

Each sub-agent is assigned a role. The following table defines the concrete model for every sub-agent under each preset:

### Analysis Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Structural Analyst | executor | (no override) | opus | sonnet | haiku |
| Risk Analyst | executor | (no override) | opus | sonnet | haiku |
| Feasibility Analyst | executor | (no override) | opus | sonnet | haiku |
| Cross-Critique (per analyst) | advisor | (no override) | opus | opus | sonnet |

### Execution Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Safety Advisor | advisor | (no override) | opus | opus | sonnet |

### Verification Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Evaluator | evaluator | (no override) | opus | opus | sonnet |

**Applying model config:** When launching any sub-agent, if `model_config.preset` is not `"default"`, pass the `model` parameter according to the table above for that sub-agent. Sub-agents must NOT directly access state.json to read model_config — the orchestrator passes the model parameter at launch time.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`

## Key Rules

- **Behavior preservation is non-negotiable.** Every change must keep existing tests passing. Stop immediately on regression.
- **Atomic changes only.** One refactoring step at a time. Test between each. Never batch multiple refactoring operations.
- **Confirmation gates are non-negotiable.** No implicit approval, no proceeding on ambiguity.
- **Stay within scope.** Do not modify files outside the specified scope.
- **Evaluator must be isolated.** Always run as a subagent with anchor-free input. Never pass execution reasoning to the Evaluator.
- **Analyst proposals must be independent.** Never share one analyst's findings with another during the analysis phase.
- **Safety Advisor reviews before execution, not after.** Advisory input happens before each step is applied.
- **Use whatever skills are available.** Search by capability keyword, not plugin name. If no match, proceed without it.
- **User language.** All user-facing output must be in `user_lang`. Re-detect on every user message.
- **Intermediate outputs are ephemeral.** Only final artifacts (refactor_plan.md, changes.md, qa_report.md) are preserved in `docs/`.
- **Mode selection.** If `--mode` provided, use it. Otherwise recommend based on scope and ask. Store in state.json; preserve across session recovery.
- **No auto-fix on test failure.** Report the failure, give the user options. Never attempt to fix a regression automatically.
