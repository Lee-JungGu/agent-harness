---
name: workflow
description: 3-Phase (Planner -> Generator -> Evaluator) workflow with selectable single-agent or multi-agent persona mode. Use for development tasks (feature work, bug fixes, maintenance) AND non-development tasks (planning data processing, document generation, analysis) that benefit from structured planning, implementation, and review.
---

# Agent Harness Workflow

You are orchestrating a 3-Phase workflow with **selectable single-agent or multi-agent persona mode**.

**Zero-setup:** No initialization required. Auto-detects language, test commands, and build commands from the current directory. Works with or without a git repository.

## Environment Detection

At startup, detect whether the current directory is inside a git repository:
```
git rev-parse --is-inside-work-tree 2>/dev/null
```
- If the command succeeds → `has_git = true`
- If the command fails → `has_git = false`

Store `has_git` in state.json. This flag controls whether git operations (branch creation, commits) are performed. **All core workflow phases (Planner → Generator → Evaluator) work identically regardless of `has_git`.**

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, spec sections, QA report narrative, commit messages (if has_git), confirmation gate prompts and options.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (spec.md, changes.md, qa_report.md), git branch names (if has_git).

## Standard Status Format

When displaying status, read `.harness/state.json` and print (in `user_lang`):
```
[harness]
  Task   : <task>
  Mode   : <single | standard | multi>
  Model  : <model_config preset name>
  Phase  : <phase label>
  Round  : <round> / <max_rounds>
  Branch : <branch>          ← omit this line if has_git == false
  Scope  : <scope>
```
Phase labels: plan_ready → "Planner — writing spec", gen_ready → "Generator — implementing", eval_ready → "Evaluator — reviewing", completed → "Completed"

## Session Recovery

Before starting a new task, check if `.harness/state.json` already exists:

1. If it exists, print status in the standard format (including Model line from `model_config`), prefixed with `[harness] Previous session detected.`
2. Restore `model_config` from state.json. Apply it to all subsequent sub-agent launches.
3. If `has_git` is not present in state.json (pre-existing session from older version), re-detect using the Environment Detection command and store the result.
4. Ask the user using AskUserQuestion (in `user_lang`):
     header: "Session"
     question: "[harness] Previous session detected. [print status in standard format]. Resume, restart, or stop?"
     options:
       - label: "Resume" / description: "Continue from {phase} where the previous session left off"
       - label: "Restart" / description: "Delete .harness/ and start from scratch"
       - label: "Stop" / description: "Delete .harness/ and halt"

   Actions per selection:
   - **Resume**: Jump to the step matching state.json phase:
     `plan_ready` → if spec.md exists go to Step 3, else Step 2 |
     `gen_ready` → Step 4 | `eval_ready` → Step 5 |
     `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist, proceed to Step 1 normally.

## Workflow

When the user provides a task (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Detect user language** from the task description. Store as `user_lang`.
2. **Slugify the task:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.
3. **Auto-detect project language and commands.** Scan the working directory:

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
4. **Create directories:** `.harness/`, `.harness/planner/`, `.harness/generator/`, `docs/harness/<slug>/`
5. **Create git branch (if has_git):** `git checkout -b harness/<slug>`. If `has_git == false`, skip this step entirely.
6. **Mode selection:** If `--mode single`, `--mode standard`, or `--mode multi` was passed, set mode and skip prompt. Otherwise, use AskUserQuestion to ask the user (in `user_lang`):
     header: "Mode"
     question: "Select workflow mode:"
     options:
       - label: "standard (Recommended)" / description: "2 specialists analyze + synthesize. ~1.5x tokens. Balanced depth"
       - label: "single" / description: "1 agent. Fast, token-saving. Best for simple tasks"
       - label: "multi" / description: "3 specialists + cross-critique. ~2-2.5x tokens. Deepest analysis"
7. **Model configuration selection:**
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

   Store result as `model_config` object: `{ "preset": "<name>", "executor": "<model|null>", "advisor": "<model|null>", "evaluator": "<model|null>" }`. For the `default` preset, store `{ "preset": "default" }` (all roles inherit parent model).

8. **Write `.harness/state.json`** with fields: `task`, `mode` ("single"/"standard"/"multi"), `model_config` (from step 7), `user_lang`, `has_git` (boolean), `repo_name`, `repo_path` (working directory path), `phase` ("plan_ready"), `round` (1), `max_rounds` (3), `max_files` (20), `scope` (user-provided or "(no limit)"), `branch` (if has_git: "harness/<slug>", else: null), `lang`, `test_cmd`, `build_cmd`, `docs_path` ("docs/harness/<slug>/"), `created_at` (ISO8601).
9. **Print setup summary** (in `user_lang`):
   ```
   [harness] Task started!
     Directory : <path>
     Branch    : harness/<slug>     ← omit if has_git == false
     Mode      : <single | multi>
     Model     : <preset name> (e.g. "default", "all-opus", "balanced", "economy")
     Language  : <lang>
     Test      : <test_cmd or "none">
     Build     : <build_cmd or "none">
     Scope     : <scope>
   ```

### Step 2: Planner Phase

Read `mode` from state.json and branch accordingly.

#### If mode == "single": Step 2-S

1. Read the single planner template: `{CLAUDE_PLUGIN_ROOT}/templates/planner/planner_single.md`
2. Interpret it with current context (task, repo_path, lang, scope, user_lang, spec_path=`docs/harness/<slug>/spec.md`). Do NOT write a rendered file — process inline.
3. Follow the planner instructions:
   - Explore the codebase (CLAUDE.md, relevant files)
   - **Invoke a brainstorming skill** — search for "brainstorming" or "ideation", invoke first match
   - **Invoke a planning skill** — search for "writing-plans" or "plan", invoke first match
   - If no matching skill found, proceed without it
   - Write `spec.md` to `docs/harness/<slug>/spec.md` — **all content in `user_lang`**
4. Update state.json: phase → `"plan_ready"`.
5. Print status in the standard format, prefixed with `[harness] Planner complete.`

#### If mode == "standard": Step 2-ST

##### Step 2a-ST: Independent Proposals (Parallel)

1. Read two persona templates from `{CLAUDE_PLUGIN_ROOT}/templates/planner/`: `architect.md`, `senior_developer.md`
2. For each persona, fill template variables: `{task_description}`, `{repo_path}`, `{lang}`, `{scope}`, `{user_lang}` from state.json; `{output_path}`: `.harness/planner/proposal_<persona>.md`
3. **Launch 2 subagents in parallel** using the Agent tool. Each receives its persona template, has no knowledge of the other subagent (anchoring prevention), and writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Architect, Senior Developer → advisor role).
4. Wait for both to complete. Verify both proposal files exist.

##### Step 2b-ST: Synthesis (No Cross-Critique)

1. Read the standard synthesis template: `{CLAUDE_PLUGIN_ROOT}/templates/planner/synthesis_standard.md`
2. Read both proposal files from Step 2a-ST.
3. Interpret the synthesis template with: `{task_description}`, `{user_lang}`, `{all_proposals}` (concatenated with author labels), `{spec_path}`: `docs/harness/<slug>/spec.md`
4. Follow the synthesis rules to write `spec.md`.
5. Update state.json: phase → `"plan_ready"`.
6. Inform the user (in `user_lang`):
   ```
   [harness] Planner complete.
     Proposals  : 2 specialists analyzed independently
     Output     : spec.md synthesized
   ```

#### If mode == "multi": Step 2-M

##### Step 2a: Independent Proposals (Parallel)

1. Read three persona templates from `{CLAUDE_PLUGIN_ROOT}/templates/planner/`: `architect.md`, `senior_developer.md`, `qa_specialist.md`
2. For each persona, fill template variables: `{task_description}`, `{repo_path}`, `{lang}`, `{scope}`, `{user_lang}` from state.json; `{output_path}`: `.harness/planner/proposal_<persona>.md`
3. **Launch 3 subagents in parallel** using the Agent tool. Each receives its persona template, has no knowledge of other subagents (anchoring prevention), and writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Architect, Senior Developer, QA Specialist → advisor role).
4. Wait for all 3 to complete. Verify all 3 proposal files exist.

##### Step 2b: Cross-Critique (Parallel)

1. Read the cross-critique template: `{CLAUDE_PLUGIN_ROOT}/templates/planner/cross_critique.md`
2. Read all 3 proposal files from Step 2a.
3. For each persona, prepare the cross-critique prompt with: `{persona_name}`, `{task_description}`, `{user_lang}`, `{proposal_1_author}`, `{proposal_1_content}`, `{proposal_2_author}`, `{proposal_2_content}` (the OTHER two proposals), `{output_path}`: `.harness/planner/critique_<persona>.md`
4. **Launch 3 subagents in parallel.** Each writes to `.harness/planner/critique_<persona>.md`. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (same advisor role as the original persona).
5. Wait for all 3 to complete. Verify all 3 critique files exist.

##### Step 2c: Synthesis

1. Read the synthesis template: `{CLAUDE_PLUGIN_ROOT}/templates/planner/synthesis.md`
2. Read all 6 intermediate files (3 proposals + 3 critiques).
3. Interpret the synthesis template with: `{task_description}`, `{user_lang}`, `{all_proposals}` (concatenated with author labels), `{all_critiques}` (concatenated with author labels), `{spec_path}`: `docs/harness/<slug>/spec.md`
4. Follow the synthesis rules to write `spec.md`.
5. Update state.json: phase → `"plan_ready"`.
6. Inform the user (in `user_lang`):
   ```
   [harness] Planner complete.
     Proposals  : 3 specialists analyzed independently
     Critiques  : 3 cross-reviews completed
     Output     : spec.md synthesized
   ```

### Step 3: HARD GATE — Spec Confirmation

<HARD-GATE>
Show spec.md to the user and ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Spec"
  question: "Review the spec above. Implementation consumes significant tokens. Confirm to proceed."
  options:
    - label: "Proceed" / description: "Start implementation as specified"
    - label: "Modify" / description: "Edit the spec, then re-confirm"
    - label: "Stop" / description: "Halt the workflow"

If user selects "Modify" or provides modification details via "Other": update spec.md and re-present this question.
If user selects "Stop": halt the workflow.
Only "Proceed" advances to the Generator phase.
</HARD-GATE>

### Step 4: Generator Phase

Read `mode` from state.json and branch accordingly.

#### If mode == "single": Step 4-S

1. Update state.json: phase → `"gen_ready"`, read current round.
2. Read the single generator template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/generator_single.md`
3. Prepare the prompt: `{spec_content}` from spec.md, `{qa_feedback}` from qa_report.md if round > 1 else "(First round — no QA feedback)", `{round_num}`, `{scope}`, `{max_files}`, `{user_lang}` from state.json, `{changes_path}`: `docs/harness/<slug>/changes.md`
4. **Invoke implementation skills** — search and invoke matches: "test-driven-development"/"tdd" (if test_cmd available), "subagent-driven-development"/"parallel-tasks"/"dispatching-parallel-agents". Proceed without if no match.
5. **Launch 1 subagent** to implement the code following the template. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Generator single mode → executor role).
6. Wait for completion. Verify `docs/harness/<slug>/changes.md` exists.
7. Print status in the standard format, prefixed with `[harness] Generator complete.`

#### If mode == "standard": Step 4-ST

##### Step 4a-ST: Implementation Plan

1. Update state.json: phase → `"gen_ready"`, read current round.
2. Read the lead developer template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/lead_developer.md`
3. Prepare the prompt: `{spec_content}` from spec.md, `{qa_feedback}` from qa_report.md if round > 1 else "(First round — no QA feedback)", `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}` from state.json, `{output_path}`: `.harness/generator/plan.md`
4. **Launch 1 subagent** (Lead Developer) to create the implementation plan. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Lead Developer → executor role).
5. Wait for completion. Verify `.harness/generator/plan.md` exists.

##### Step 4b-ST: Combined Advisory Review

1. Read the combined advisor template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/combined_advisor.md`
2. Read the plan from `.harness/generator/plan.md`.
3. Prepare the prompt: `{spec_content}`, `{plan_content}`, `{repo_path}`, `{lang}`, `{test_cmd}`, `{user_lang}` from state.json, `{output_path}`: `.harness/generator/review_combined.md`
4. **Launch 1 subagent** (Combined Advisor) to review the plan. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Combined Advisor → advisor role).
5. Wait for completion. Verify `.harness/generator/review_combined.md` exists.

##### Step 4c-ST: Implementation

1. Read the standard implementation template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/implementation_standard.md`
2. Read the plan and combined review from `.harness/generator/`.
3. Prepare the prompt: `{spec_content}`, `{plan_content}`, `{advisor_review}` (from review_combined.md), `{qa_feedback}` (from qa_report.md if round > 1), `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}`, `{round_num}` from state.json, `{changes_path}`: `docs/harness/<slug>/changes.md`
4. **Invoke implementation skills** — same as Step 4-S step 4.
5. **Launch 1 subagent** (Lead Developer) to implement the code. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Lead Developer → executor role).
6. Wait for completion. Verify `docs/harness/<slug>/changes.md` exists.
7. Inform the user (in `user_lang`):
   ```
   [harness] Generator complete.
     Plan     : Lead Developer created implementation plan
     Review   : Combined Advisor reviewed the plan
     Code     : Lead Developer implemented with feedback
     Output   : changes.md written
   ```

#### If mode == "multi": Step 4-M

##### Step 4a: Implementation Plan

1. Update state.json: phase → `"gen_ready"`, read current round.
2. Read the lead developer template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/lead_developer.md`
3. Prepare the prompt: `{spec_content}` from spec.md, `{qa_feedback}` from qa_report.md if round > 1 else "(First round — no QA feedback)", `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}` from state.json, `{output_path}`: `.harness/generator/plan.md`
4. **Launch 1 subagent** (Lead Developer) to create the implementation plan. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Lead Developer → executor role).
5. Wait for completion. Verify `.harness/generator/plan.md` exists.

##### Step 4b: Advisory Review (Parallel)

1. Read both advisor templates from `{CLAUDE_PLUGIN_ROOT}/templates/generator/`: `code_quality_advisor.md`, `test_stability_advisor.md`
2. Read the plan from `.harness/generator/plan.md`.
3. For each advisor, prepare the prompt: `{spec_content}`, `{plan_content}`, `{repo_path}`, `{lang}`, `{test_cmd}`, `{user_lang}` from state.json, `{output_path}`: `.harness/generator/review_<advisor>.md`
4. **Launch 2 subagents in parallel.** Each writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Code Quality Advisor, Test & Stability Advisor → advisor role).
5. Wait for both to complete. Verify both review files exist.

##### Step 4c: Implementation

1. Read the implementation template: `{CLAUDE_PLUGIN_ROOT}/templates/generator/implementation.md`
2. Read the plan and both reviews from `.harness/generator/`.
3. Prepare the prompt: `{spec_content}`, `{plan_content}`, `{code_quality_review}`, `{test_stability_review}`, `{qa_feedback}` (from qa_report.md if round > 1), `{repo_path}`, `{lang}`, `{scope}`, `{max_files}`, `{user_lang}`, `{round_num}` from state.json, `{changes_path}`: `docs/harness/<slug>/changes.md`
4. **Invoke implementation skills** — same as Step 4-S step 4.
5. **Launch 1 subagent** (Lead Developer) to implement the code. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Lead Developer → executor role).
6. Wait for completion. Verify `docs/harness/<slug>/changes.md` exists.
7. Inform the user (in `user_lang`):
   ```
   [harness] Generator complete.
     Plan     : Lead Developer created implementation plan
     Reviews  : 2 advisors reviewed the plan
     Code     : Lead Developer implemented with feedback
     Output   : changes.md written
   ```

### Step 5: Evaluator Phase (Isolated Subagent)

1. Update state.json: phase → `"eval_ready"`.
2. Read the evaluator template: `{CLAUDE_PLUGIN_ROOT}/templates/evaluator/evaluator_prompt.md`
3. **Prepare the subagent prompt.** Fill in: `spec_content` from spec.md, `changed_files_list` (file paths only from changes.md — **strip all "reason" descriptions** to prevent anchoring), `test_available`, `build_cmd`, `test_cmd`, `round_num`, `scope`, `user_lang` from state.json, `qa_report_path`: `docs/harness/<slug>/qa_report.md`.
   **Do NOT include:** Generator reasoning, implementation plan, advisor reviews, why files were changed, or references to "Generator"/"AI"/"agent" as code author.
4. **Launch the Evaluator subagent** using the Agent tool. Use `subagent_type: "superpowers:code-reviewer"` if available. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Evaluator → evaluator role). Instruct it to write the QA report to `docs/harness/<slug>/qa_report.md`.
5. When the subagent returns, read `docs/harness/<slug>/qa_report.md` to get the verdict.

### Step 6: Verdict & Loop

Read qa_report.md and determine verdict (look for "Verdict: PASS" or "Verdict: FAIL").

**If PASS:** Update state.json: phase → `"completed"`. Inform user: task complete. Proceed to Step 7.

**If FAIL and rounds remaining (round < max_rounds):** Do NOT auto-retry. Ask the user using AskUserQuestion (in `user_lang`):
  header: "QA"
  question: "QA result: FAIL. [failure summary]."
  options:
    - label: "Fix" / description: "Run next round to fix FAIL items only"
    - label: "Accept as-is" / description: "Finish without fixing, keep current state"

If user selects "Fix": increment round, go to Step 4. If user selects "Accept as-is": phase → "completed", go to Step 7.

**If FAIL and max rounds reached:** phase → `"completed"`. Inform user of remaining issues. Proceed to Step 7.

### Step 7: Cleanup & Finalize

#### Artifact Cleanup Safety Guard

Before deleting any `docs/harness/` subdirectory, these checks are **mandatory**:

1. **Validate slug**: Read `docs_path` from `.harness/state.json`, extract `<slug>` (last path segment). If `<slug>` is empty, null, or whitespace → **ABORT** cleanup and warn user (in `user_lang`): "Cannot determine delete target — slug is empty."
2. **Path depth check**: Delete target must match pattern `docs/harness/<non-empty-slug>/` — exactly one level below `docs/harness/`. **NEVER** delete `docs/harness/` itself during normal cleanup. Additionally: slug must **NOT** be `memory` (reserved for `/memory` skill), must **NOT** contain `..` or `/`, and must **NOT** be a single dot `.`. If any of these conditions fail → **ABORT** and warn user.
3. **Display before delete**: Print the exact delete target path (e.g., `docs/harness/my-task/`) to the user before executing. Do not silently delete.

**Full `docs/harness/` cleanup (only when user explicitly requests):**
If the user explicitly asks to delete the **entire** `docs/harness/` directory:
1. List all subdirectories with their file counts
2. If `docs/harness/memory/` exists, list it **separately** with warning: "This directory contains team knowledge managed by `/memory` skill."
3. Warn (in `user_lang`): "`docs/` is git-ignored — all session artifacts will be permanently deleted and **cannot be recovered**."
4. Ask confirmation via AskUserQuestion (yes/no) — only proceed on explicit "Yes, delete all"

**If has_git == true:**
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Commit"
  question: "Implementation complete. Choose how to finish:"
  options:
    - label: "Commit code only (Recommended)" / description: "Clean up artifacts (.harness/, docs/harness/<slug>/) then commit code changes only"
    - label: "Commit all" / description: "Commit everything including artifacts (spec.md, changes.md, qa_report.md)"
    - label: "No commit" / description: "Clean up .harness/ only, do not commit (changes remain in working tree)"

Actions per selection (apply Safety Guard before each delete):
- "Commit code only": delete `.harness/` dir, delete `docs/harness/<slug>/` dir (**only** this slug dir — verify via guard), stage and commit remaining code changes
- "Commit all": delete `.harness/` dir, stage and commit `docs/harness/<slug>/` files + code changes
- "No commit": delete `.harness/` dir only

**If has_git == false:**
Inform the user that artifacts are saved in `docs/harness/<slug>/` (spec.md, changes.md, qa_report.md).
- Clean up `.harness/` directory (delete state.json, planner/, generator/, and the directory itself)
- Do NOT attempt any git operations.

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
| Generator (single mode) | executor | (no override) | opus | sonnet | haiku |

### Evaluator Phase Sub-agents

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

- **Never skip phases.** Always Planner → Generator → Evaluator.
- **Confirmation gates are non-negotiable.** No implicit approval, no proceeding on ambiguity.
- **Stay within scope.** Do not modify files outside the specified scope.
- **Evaluator must be isolated.** Always run as a subagent with anchor-free input. Never pass Generator reasoning to the Evaluator.
- **Planner proposals must be independent.** Never share one persona's proposal with another during the proposal phase.
- **Generator advisors review the plan, not the code.** Advisory input happens before implementation.
- **Use whatever skills are available.** Search by capability keyword, not plugin name. If no match, proceed without it.
- **User language.** All user-facing output must be in `user_lang`. Re-detect on every user message.
- **Intermediate outputs are ephemeral.** Only final artifacts (spec.md, changes.md, qa_report.md) are preserved in `docs/`.
- **Mode selection.** If `--mode` provided, use it. Otherwise ask (3 options: single, standard, multi). Store in state.json; preserve across session recovery.
