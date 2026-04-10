---
name: migrate
description: Execute framework/library version upgrades, language transitions, and dependency replacements with staged execution and verification. Supports single-agent and multi-agent modes with WebSearch-based migration guide research, per-step test verification, and session recovery.
---

# Agent Harness Migrate

You are orchestrating a **staged migration workflow** with selectable single-agent or multi-agent mode. You help users upgrade frameworks, transition libraries, and replace dependencies safely — one breaking change at a time.

**Zero-setup:** No initialization required. Auto-detects language, versions, test commands, and build commands from the current directory.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, migration plan sections, QA report narrative, commit messages, confirmation gate prompts and options.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (migration_plan.md, changes.md, qa_report.md), git branch names.

## Standard Status Format

When displaying status, read `.harness/state.json` and print (in `user_lang`):
```
[harness:migrate]
  Target : <target> <from_version> → <to_version>
  Mode   : <single | multi>
  Model  : <model_config preset name>
  Phase  : <phase label>
  Step   : <current_step> / <total_steps> (if in execution phase)
  Branch : <branch>
```
Phase labels: setup → "Setup", analyze_ready → "Analysis — researching migration", plan_ready → "Planning — building migration plan", exec_ready → "Execution — applying changes", eval_ready → "Evaluator — verifying migration", completed → "Completed"

## Argument Parsing

Parse `$ARGUMENTS` with the following grammar:

```
/migrate <target> [--from <version>] [--to <version>] [--mode single|multi]
```

**Patterns:**
- Version upgrade: `/migrate react --from 17 --to 18`
- Replacement: `/migrate replace moment with dayjs`
- Implicit latest: `/migrate react --from 17` (auto-detect latest stable as --to)
- Fully implicit: `/migrate react` (auto-detect both --from and --to)

Store parsed values:
- `target`: the framework/library/dependency name (e.g. "react", "moment→dayjs")
- `from_version`: explicit or auto-detected
- `to_version`: explicit or auto-detected
- `migration_type`: "upgrade" | "replacement"

If the target contains "replace ... with ..." or "→", set `migration_type` to "replacement" and parse source/destination libraries.

## Version Auto-Detection

Detect the current version of `target` from project files:

| File | Detection Method |
|------|-----------------|
| `package.json` | `dependencies[target]` or `devDependencies[target]` — strip semver prefix (^, ~, >=) |
| `pyproject.toml` | `[project.dependencies]` or `[tool.poetry.dependencies]` — parse version specifier |
| `requirements.txt` | Line matching `target==<version>` or `target>=<version>` |
| `go.mod` | `require` block — match module path containing target |
| `Cargo.toml` | `[dependencies]` section — parse version string |
| `build.gradle(.kts)` | `implementation`, `api`, `compile` dependency declarations |
| `pom.xml` | `<dependency>` elements matching target in `<artifactId>` |
| `*.csproj` | `<PackageReference Include="target" Version="...">` |
| `Gemfile` | `gem 'target', '~> <version>'` |
| `composer.json` | `require[target]` — strip semver prefix |

**If --from not provided:** Use detected version. If detection fails, ask the user.
**If --to not provided:** Use WebSearch to find the latest stable version. If WebSearch fails, ask the user.
**If version is ambiguous** (e.g. multiple packages match target): List candidates and ask the user to choose.

## Session Recovery

Before starting a new task, check if `.harness/state.json` already exists:

1. If it exists, print status in the standard format (including Model line from `model_config`), prefixed with `[harness:migrate] Previous session detected.`
2. Restore `model_config` from state.json. Apply it to all subsequent sub-agent launches.
3. Ask the user (in their language) whether to resume, restart, or stop:
   - **Resume**: Jump to the step matching state.json phase:
     `setup` → Step 1 |
     `analyze_ready` → Step 2 |
     `plan_ready` → if migration_plan.md exists go to Step 3, else Step 2 |
     `exec_ready` → Step 4 (resume from `current_step` in state.json) |
     `eval_ready` → Step 5 |
     `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist, proceed to Step 1 normally.

## Smart Routing

Before proceeding, assess whether this skill is the right tool:

| User Intent | Better Skill | Action |
|-------------|-------------|--------|
| Deprecated patterns cleanup without version change | `/workflow` with refactoring task | Suggest: "This looks like a refactoring task rather than a migration. Use `/workflow <task>` instead? (switch / continue)" |
| Code state unclear, needs audit first | `/workflow` with audit task | Suggest: "Consider running a codebase audit first to understand the current state. Use `/workflow audit <target>` first? (switch / continue)" |
| Wants to adopt new API features (not upgrading) | `/workflow` with feature task | Suggest: "This looks like a feature addition. Use `/workflow <task>` instead? (switch / continue)" |

If the user chooses to switch, halt this skill.

## Scope-Aware Mode Selection

If `--mode` is not provided, auto-select based on migration complexity:

1. If only 1 breaking change detected → default to `single`
2. If 2+ breaking changes detected → default to `multi`
3. Always inform the user of the auto-selected mode and allow override

If `--mode single` or `--mode multi` was passed, use it directly.

## Workflow

When the user provides a migration target (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Detect user language** from the task description. Store as `user_lang`.
2. **Slugify the target:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. For replacements, use format `<from>-to-<to>`. Store as `<slug>`.
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

4. **Detect current version** of the target using the Version Auto-Detection table above. Store as `from_version`.
5. **Determine target version** from `--to` argument or via WebSearch for latest stable. Store as `to_version`.
6. **Validate versions:** If `from_version` == `to_version`, inform user "Already on target version" and halt. If `from_version` > `to_version`, warn about downgrade and ask for confirmation.
7. **Capture baseline test results:** If test command is available, run it and store output in `.harness/migrate/baseline_tests.txt`. Record pass/fail counts. If baseline tests are failing, report to user:
   > "Baseline tests are failing (N failures). Proceeding with migration may make it harder to identify migration-caused regressions. Continue anyway? (continue / fix-first / abort)"
   On fix-first: halt and suggest user fix tests first. On abort: halt.

8. **Create directories:** `.harness/`, `.harness/migrate/`, `docs/harness/<slug>/`
9. **Create git branch:** `git checkout -b harness/migrate-<slug>`
10. **Mode selection:** Apply Scope-Aware Mode Selection rules above. If auto-selected, inform user and allow override. Accept: "1", "2", "single", "multi" (case-insensitive).
11. **Model configuration selection:**
   If `--model-config <preset>` was passed, use it directly. Otherwise, ask the user (in `user_lang`):

   If AskUserQuestion tool is available, use it:
   ```
   AskUserQuestion(
     question: "Select model configuration for sub-agents:",
     options: ["default", "all-opus", "balanced", "economy", "Other"]
   )
   ```
   If AskUserQuestion is NOT available, present as a text question (in `user_lang`):
   > "Select model configuration for sub-agents:
   > (1) default — inherit parent model (no override)
   > (2) all-opus — all sub-agents use Opus
   > (3) balanced — Sonnet executor + Opus advisor/evaluator
   > (4) economy — Haiku executor + Sonnet advisor/evaluator
   > (5) Other — custom (format: executor:model,advisor:model,evaluator:model)
   > Select: (1-5 or preset name)"

   Accept: "1"-"5", preset names, or custom format (case-insensitive). Re-ask on unrecognized input.

   **If "Other" selected:** Parse custom format `executor:<model>,advisor:<model>,evaluator:<model>`. Validate each model name — only `opus`, `sonnet`, `haiku` are allowed (case-insensitive). If any model name is invalid, inform the user which value is invalid and re-ask for input (max 3 retries, then apply `balanced` as default). If parsing succeeds but is partial, fill missing roles with the `balanced` defaults (executor=sonnet, advisor=opus, evaluator=opus). Show the parsed result to the user and ask for confirmation before proceeding.

   **Model config is set once at session start and cannot be changed mid-session.** To change, restart the session.

   Store result as `model_config` object: `{ "preset": "<name>", "executor": "<model|null>", "advisor": "<model|null>", "evaluator": "<model|null>" }`. For the `default` preset, store `{ "preset": "default" }`.

12. **Write `.harness/state.json`** with fields: `skill` ("migrate"), `target`, `migration_type` ("upgrade"/"replacement"), `from_version`, `to_version`, `mode` ("single"/"multi"), `model_config` (from step 11), `user_lang`, `repo_name`, `repo_path`, `phase` ("setup"), `current_step` (0), `total_steps` (0), `branch` ("harness/migrate-<slug>"), `lang`, `test_cmd`, `build_cmd`, `baseline_test_pass_count`, `baseline_test_fail_count`, `docs_path` ("docs/harness/<slug>/"), `created_at` (ISO8601).
13. **Print setup summary** (in `user_lang`):
    ```
    [harness:migrate] Migration started!
      Target   : <target> <from_version> → <to_version>
      Type     : <upgrade | replacement>
      Repo     : <path>
      Branch   : harness/migrate-<slug>
      Mode     : <single | multi>
      Model    : <preset name>
      Language : <lang>
      Test     : <test_cmd or "none">
      Build    : <build_cmd or "none">
      Baseline : <pass_count> pass, <fail_count> fail
    ```

### Step 2: Analysis Phase

Read `mode` from state.json and branch accordingly.

#### If mode == "single": Step 2-S

1. Update state.json: phase → `"analyze_ready"`.
2. **Research the migration guide.** Use WebSearch to find the official migration guide for `target` from `from_version` to `to_version`. Search queries:
   - `"<target> migration guide <from_version> to <to_version>"`
   - `"<target> upgrade guide <from_version> <to_version> breaking changes"`
   - `"<target> changelog <to_version>"`
3. **If WebSearch succeeds:** Use WebFetch to read the migration guide page(s). Extract:
   - Breaking changes (list each with description)
   - Deprecated APIs and their replacements
   - New required configurations
   - Dependency version requirements (peer deps, minimum versions)
4. **If WebSearch fails or returns no useful results:** Fall back to local sources:
   - Read `CHANGELOG.md`, `MIGRATION.md`, `UPGRADE.md` in the project root or target package directory
   - Read `node_modules/<target>/CHANGELOG.md` (for JS/TS projects)
   - If no local sources available, inform user and ask them to provide migration guide URL or key breaking changes manually
5. **Scan the codebase** for affected code:
   - Search for imports/requires of the target library
   - Search for deprecated API usage patterns (from the breaking changes list)
   - Search for configuration files that reference the target
   - Identify all files that will need changes
6. **Build the migration plan** with breaking changes ordered by dependency (changes that others depend on go first). Write to `docs/harness/<slug>/migration_plan.md`:

   ```markdown
   ## Migration Plan: <target> <from> → <to>

   ### Summary
   <1-2 sentence overview>

   ### Breaking Changes
   For each breaking change:
   #### <N>. <Breaking Change Title>
   - **What changed:** <description>
   - **Affected files:** <list of files>
   - **Required action:** <what needs to change>
   - **Verification:** <how to verify this step>

   ### Dependency Updates
   <list of dependency version changes needed>

   ### Configuration Changes
   <list of config file updates needed>

   ### Execution Order
   <ordered list of steps, with dependencies noted>

   ### Risks
   <identified risks and mitigations>
   ```

7. Update state.json: phase → `"plan_ready"`, `total_steps` → number of breaking changes.
8. Write research notes to `.harness/migrate/research_external.md` and `.harness/migrate/research_internal.md`.
9. Print status in the standard format, prefixed with `[harness:migrate] Analysis complete.`

#### If mode == "multi": Step 2-M

##### Step 2a: External Research Analyst (Subagent)

1. Update state.json: phase → `"analyze_ready"`.
2. Read the external research template: `{CLAUDE_PLUGIN_ROOT}/templates/migrate/external_research_analyst.md`
3. Fill template variables: `{target}`, `{from_version}`, `{to_version}`, `{migration_type}`, `{lang}`, `{user_lang}`, `{output_path}`: `.harness/migrate/research_external.md`
4. **Launch 1 subagent** (External Research Analyst) using the Agent tool. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (External Research Analyst → executor role). This subagent uses WebSearch/WebFetch to research the migration guide and extract breaking changes, deprecated APIs, and version requirements.
5. Wait for completion. Verify `.harness/migrate/research_external.md` exists.

##### Step 2b: Codebase Impact Analyst (Subagent — parallel with 2a)

1. Read the codebase impact template: `{CLAUDE_PLUGIN_ROOT}/templates/migrate/codebase_impact_analyst.md`
2. Fill template variables: `{target}`, `{from_version}`, `{to_version}`, `{migration_type}`, `{repo_path}`, `{lang}`, `{user_lang}`, `{output_path}`: `.harness/migrate/research_internal.md`
3. **Launch 1 subagent** (Codebase Impact Analyst) in parallel with Step 2a. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Codebase Impact Analyst → executor role). This subagent scans the codebase for all usages of the target library, identifies affected files, and assesses impact.
4. Wait for completion. Verify `.harness/migrate/research_internal.md` exists.

**Launch Steps 2a and 2b in parallel.** Wait for both to complete before proceeding.

##### Step 2c: Synthesis → Migration Plan

1. Read the synthesis template: `{CLAUDE_PLUGIN_ROOT}/templates/migrate/synthesis.md`
2. Read both research outputs from `.harness/migrate/`.
3. Fill template variables: `{target}`, `{from_version}`, `{to_version}`, `{migration_type}`, `{user_lang}`, `{external_research}` (from research_external.md), `{internal_research}` (from research_internal.md), `{plan_path}`: `docs/harness/<slug>/migration_plan.md`
4. Follow the synthesis rules to produce `migration_plan.md` — merge external breaking changes with internal impact analysis, order by dependency, and assign step numbers.
5. Update state.json: phase → `"plan_ready"`, `total_steps` → number of breaking changes.
6. Inform the user (in `user_lang`):
   ```
   [harness:migrate] Analysis complete.
     External : Migration guide researched, <N> breaking changes found
     Internal : <M> affected files identified across codebase
     Plan     : <total_steps> migration steps ordered by dependency
   ```

### Step 3: HARD GATE — Migration Plan Confirmation

<HARD-GATE>
Show migration_plan.md to the user and ask for explicit confirmation (in `user_lang`). Do NOT proceed to Execution until confirmed.

**Allowed responses (proceed only on these — any language):**
"go", "proceed", "approve", "yes", "ok", "lgtm", and natural affirmatives in the user's language.

**Ambiguous — must re-confirm:**
Hesitation, questions, conditional statements, topic changes.

On ambiguity, respond in `user_lang` with a message equivalent to:
> "Migration execution modifies code one breaking change at a time and can be stopped at any step. Explicit confirmation is required. Proceed with the plan as written? (proceed / modify / stop)"

If user requests modifications, update migration_plan.md and re-confirm. If user stops, halt the workflow.
</HARD-GATE>

### Step 4: Execution Phase (Staged)

Read `mode` and `migration_plan` from state.json / migration_plan.md.

Update state.json: phase → `"exec_ready"`.

Execute each breaking change as an isolated step. For each step N (from `current_step + 1` to `total_steps`):

#### Step 4a: Apply Change

1. Update state.json: `current_step` → N.
2. Read the breaking change details for step N from migration_plan.md.
3. **Apply the changes:**
   - Update dependency version(s) if this step requires it
   - Modify affected source files according to the required action
   - Update configuration files if needed
4. **Log changes** — append to `docs/harness/<slug>/changes.md`:
   ```markdown
   ## Step <N>: <Breaking Change Title>

   ### Modified Files
   - path/to/file.ext — brief reason

   ### Created Files
   - (none, or list)

   ### Deleted Files
   - (none, or list)
   ```

#### Step 4b: Verify Step

1. **Build check:** If build command is available, run it. If build fails:
   - Attempt to fix build errors (up to 2 attempts).
   - If still failing after 2 attempts → stop execution, report to user with error details, and ask: "Build failed on step N. Fix manually and resume, or abort? (fix details shown above)"
2. **Test check:** If test command is available, run it. Compare results against baseline:
   - New test failures (not in baseline) → migration-caused regression
   - If regressions found → attempt to fix (up to 2 attempts)
   - If still failing after 2 attempts → stop execution, report regressions, and ask user
3. **Update state.json** with step completion status.

#### Step 4c: Migration Advisor Review (Multi Mode Only)

If `mode == "multi"`:

1. Read the migration advisor template: `{CLAUDE_PLUGIN_ROOT}/templates/migrate/migration_advisor.md`
2. Fill template variables: `{step_number}` (N), `{step_title}`, `{step_changes}` (changes made in this step only), `{build_result}`, `{test_result}`, `{previous_steps_summary}` (one-line summary of each completed step — NOT full details), `{remaining_steps}` (titles only), `{user_lang}`, `{output_path}`: `.harness/migrate/advisor_step_<N>.md`
3. **Launch 1 subagent** (Migration Advisor) to review this step. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Migration Advisor → advisor role). Lightweight review — only current step context + previous results summary.
4. Read advisor output. If advisor flags issues:
   - **Critical:** Stop and fix before proceeding
   - **Warning:** Log and continue, address in next step or during evaluation
   - **Info:** Log only

#### Step 4d: Step Completion

1. Print step completion (in `user_lang`):
   ```
   [harness:migrate] Step <N>/<total> complete: <title>
     Build  : PASS | FAIL
     Tests  : <pass_count> pass, <fail_count> fail (<regression_count> regressions)
     Advisor: <PASS | N issues> (multi mode only)
   ```
2. Proceed to next step, or if all steps complete, proceed to Step 5.

### Step 5: Evaluator Phase (Isolated Subagent)

1. Update state.json: phase → `"eval_ready"`.
2. Read the evaluator template: `{CLAUDE_PLUGIN_ROOT}/templates/migrate/evaluator.md`
3. **Prepare the subagent prompt.** Fill in: `{target}`, `{from_version}`, `{to_version}`, `{migration_type}`, `{migration_plan_content}` (from migration_plan.md — breaking changes list only, no research reasoning), `{changed_files_list}` (file paths only from changes.md — strip all "reason" descriptions), `{test_available}`, `{build_cmd}`, `{test_cmd}`, `{baseline_test_pass_count}`, `{baseline_test_fail_count}`, `{user_lang}`, `{qa_report_path}`: `docs/harness/<slug>/qa_report.md`.
   **Do NOT include:** Research notes, analyst reasoning, advisor reviews, why files were changed, or references to "Generator"/"AI"/"agent" as code author.
4. **Launch the Evaluator subagent** using the Agent tool. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Evaluator → evaluator role). Instruct it to write the QA report to `docs/harness/<slug>/qa_report.md`.
5. When the subagent returns, read `docs/harness/<slug>/qa_report.md` to get the verdict.

### Step 6: Verdict & Resolution

Read qa_report.md and determine verdict (look for "Verdict: PASS" or "Verdict: FAIL").

**If PASS:** Update state.json: phase → `"completed"`. Inform user: migration complete. Proceed to Step 7.

**If FAIL:** Do NOT auto-retry. Present failures to user and ask:
> "Migration verification: FAIL. [failure summary]. Options: (fix — attempt to fix issues / stop — accept current state / rollback — revert all changes)"
- **Fix:** Apply fixes based on evaluator's fix instructions, then re-run Step 5.
- **Stop:** phase → "completed", proceed to Step 7 with warnings.
- **Rollback:** `git checkout <original_branch>`, delete migration branch, clean up `.harness/`. Halt.

### Step 7: Cleanup & Commit

Ask the user (in `user_lang`) whether to commit the artifacts (migration_plan.md, changes.md, qa_report.md).
- If commit: stage and commit `docs/harness/<slug>/` files and all modified source files
- Clean up `.harness/` directory (delete state.json, migrate/, and the directory itself)

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
| External Research Analyst | executor | (no override) | opus | sonnet | haiku |
| Codebase Impact Analyst | executor | (no override) | opus | sonnet | haiku |

### Execution Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Migration Advisor | advisor | (no override) | opus | opus | sonnet |

### Evaluator Phase Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Evaluator | evaluator | (no override) | opus | opus | sonnet |

**Applying model config:** When launching any sub-agent, if `model_config.preset` is not `"default"`, pass the `model` parameter according to the table above for that sub-agent. Sub-agents must NOT directly access state.json to read model_config — the orchestrator passes the model parameter at launch time.

## Key Rules

- **Staged execution is non-negotiable.** One breaking change at a time. Verify before proceeding.
- **Never skip the analysis phase.** Always research → plan → confirm → execute.
- **Confirmation gates are non-negotiable.** No implicit approval, no proceeding on ambiguity.
- **Evaluator must be isolated.** Always run as a subagent with anchor-free input. Never pass research reasoning or advisor reviews to the Evaluator.
- **External + Internal analysts must be independent.** Never share one analyst's output with the other during the research phase (multi mode).
- **Migration Advisor is lightweight.** Only receives current step context + one-line summaries of previous steps. Never receives full research or full changes.
- **Baseline tests are the regression benchmark.** Only test failures that are NOT in the baseline count as migration regressions.
- **Stop on unrecoverable failure.** If a step cannot be fixed in 2 attempts, stop and report rather than continuing blindly.
- **Use whatever skills are available.** Search by capability keyword, not plugin name. If no match, proceed without it.
- **User language.** All user-facing output must be in `user_lang`. Re-detect on every user message.
- **Intermediate outputs are ephemeral.** Only final artifacts (migration_plan.md, changes.md, qa_report.md) are preserved in `docs/`.
- **WebSearch fallback.** If WebSearch/WebFetch fail, always fall back to local CHANGELOG/MIGRATION files before asking the user.
