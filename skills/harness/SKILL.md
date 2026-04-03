---
name: harness
description: 3-Phase (Planner -> Generator -> Evaluator) development workflow. Use when starting feature work, bug fixes, or maintenance tasks that benefit from structured planning, implementation, and review.
---

# Agent Harness Workflow

You are orchestrating a 3-Phase development workflow.

**Zero-setup:** No initialization required. Auto-detects language, test commands, and build commands from the current directory.

## User Language Detection

Detect the user's language from their **most recent message** (the task description or latest reply). Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language:
- Progress updates, questions, confirmations, error messages
- Spec sections (headings and content), QA report narrative, commit messages
- Confirmation gate prompts and options

**Re-detection:** On every user message, check if the language has changed. If it has, update `user_lang` in state.json and switch all subsequent communication to the new language.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (spec.md, changes.md, qa_report.md), git branch names.

## Session Recovery

Before starting a new task, check if `.harness/state.json` already exists:

1. If it exists, read it and display the current state (in `user_lang` from state.json):
   ```
   [harness] Previous session detected.
     Task   : <task>
     Phase  : <phase label>
     Round  : <round> / <max_rounds>
     Branch : <branch>
   ```
2. Ask the user (in their language) whether to resume, restart, or stop:
   - **Resume**: Read the phase from state.json and jump to the corresponding step:
     - `plan_ready` → Check if spec.md exists in docs path. If yes, go to Step 3 (show spec and confirm). If no, go to Step 2 (re-run Planner).
     - `gen_ready` → Step 4 (Generator)
     - `eval_ready` → Step 5 (Evaluator)
     - `completed` → Treat as no active session. Inform the user and proceed to Step 1.
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist, proceed to Step 1 normally.

## Workflow

When the user provides a task (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Detect user language** from the task description. Store as `user_lang`.

2. **Slugify the task:** lowercase, transliterate non-ASCII to ASCII if possible, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.

3. **Auto-detect project language and commands.** Scan the repo root with Glob and check for these files:

   | File | Language | Test Command | Build Command |
   |------|----------|-------------|---------------|
   | `build.gradle` or `build.gradle.kts` | java | `./gradlew test` | `./gradlew build` |
   | `pom.xml` | java | `mvn test` | `mvn compile` |
   | `pyproject.toml` or `setup.py` | python | `pytest` | (none) |
   | `package.json` | typescript | `npm test` | `npm run build` |
   | `*.csproj` | csharp | `dotnet test` | `dotnet build` |
   | `go.mod` | go | `go test ./...` | `go build ./...` |
   | `Cargo.toml` | rust | `cargo test` | `cargo build` |

   If none match, set language to "unknown", test/build commands to null.

4. **Create directories:**
   - `.harness/` (working state)
   - `docs/harness/<slug>/` (artifacts)

5. **Create git branch:**
   ```bash
   git checkout -b harness/<slug>
   ```

6. **Write `.harness/state.json`:**
   ```json
   {
     "task": "<user's task description>",
     "user_lang": "<detected language code>",
     "repo_name": "<directory name>",
     "repo_path": "<absolute path>",
     "phase": "plan_ready",
     "round": 1,
     "scope": "<user-provided scope or '(no limit)'>",
     "max_rounds": 3,
     "max_files": 20,
     "branch": "harness/<slug>",
     "lang": "<detected project language>",
     "test_cmd": "<detected or null>",
     "build_cmd": "<detected or null>",
     "docs_path": "docs/harness/<slug>/",
     "created_at": "<ISO8601>"
   }
   ```

7. **Print setup summary** to the user (in `user_lang`):
   ```
   [harness] Task started!
     Repo     : <path>
     Branch   : harness/<slug>
     Language : <lang>
     Test     : <test_cmd or "none">
     Build    : <build_cmd or "none">
     Scope    : <scope>
   ```

### Step 2: Planner Phase

1. Read the planner template: `{CLAUDE_PLUGIN_ROOT}/templates/planner_prompt.md`
2. Interpret it with the current context (task, repo_path, lang, scope, user_lang). Do NOT write a rendered file — process inline.
3. Follow the planner instructions:
   - Explore the codebase (CLAUDE.md, relevant files)
   - **Invoke a brainstorming skill** — search installed skills for "brainstorming" or "ideation" and invoke the first match
   - **Invoke a planning skill** — search installed skills for "writing-plans" or "plan" and invoke the first match
   - If no matching skill is found, proceed without it
   - Write `spec.md` to `docs/harness/<slug>/spec.md` — **all content in `user_lang`**
4. Update `.harness/state.json`: set phase to `"plan_ready"` (spec written, awaiting confirmation).

### Step 3: HARD GATE — Spec Confirmation

<HARD-GATE>
Show spec.md to the user and ask for explicit confirmation (in `user_lang`). Do NOT proceed to Generator until confirmed.

**Allowed responses (proceed only on these — any language):**
"go", "proceed", "approve", "yes", "ok", "lgtm", and natural affirmatives in the user's language.

**Ambiguous — must re-confirm:**
Hesitation, questions, conditional statements, topic changes.

On ambiguity, respond in `user_lang` with a message equivalent to:
> "Implementation consumes significant tokens. Explicit confirmation is required. Proceed with the spec as written? (proceed / modify / stop)"

If user requests modifications, update spec.md and re-confirm. If user stops, halt the workflow.
</HARD-GATE>

### Step 4: Generator Phase

1. Update state.json: phase → `"gen_ready"`, read current round.
2. Read the generator template: `{CLAUDE_PLUGIN_ROOT}/templates/generator_prompt.md`
3. Interpret with context:
   - `spec_content`: read from `docs/harness/<slug>/spec.md`
   - `qa_feedback`: read from `docs/harness/<slug>/qa_report.md` if round > 1, else "(First round — no QA feedback)"
   - `round_num`, `scope`, `max_files`: from state.json
   - If test_cmd is available, include TDD instructions; otherwise skip
4. **Invoke implementation skills** — search installed skills and invoke matches:
   - If test_cmd available: search for "test-driven-development" or "tdd"
   - Search for "subagent-driven-development", "parallel-tasks", or "dispatching-parallel-agents"
   - If no matching skill is found, proceed without it
5. Follow the generator instructions — implement code changes.
   - The generator template includes a **scope pre-check step**: before writing any code, list planned files and verify they match the scope pattern. If scope is "(no limit)", skip this check.
6. Write `docs/harness/<slug>/changes.md` listing all modified/created files.

### Step 5: Evaluator Phase (Isolated Subagent)

The Evaluator runs as an **isolated subagent** to reduce self-evaluation bias. The subagent has a separate context and does not see the Generator's intermediate reasoning.

1. Update state.json: phase → `"eval_ready"`.
2. Read the evaluator template: `{CLAUDE_PLUGIN_ROOT}/templates/evaluator_prompt.md`
3. **Prepare the subagent prompt.** Construct the prompt by filling in the evaluator template with:
   - `spec_content`: read from `docs/harness/<slug>/spec.md`
   - `changed_files_list`: file paths only from `docs/harness/<slug>/changes.md` — **strip all "reason" descriptions** to prevent anchoring
   - `test_available`, `build_cmd`, `test_cmd`: from state.json
   - `round_num`, `scope`: from state.json
   - `user_lang`: from state.json — the subagent must write the QA report in this language
   - `qa_report_path`: `docs/harness/<slug>/qa_report.md` — tell the subagent exactly where to write the report

   **Do NOT include:**
   - The Generator's reasoning or decision process
   - Why specific files were changed
   - Any reference to "Generator", "AI", or "agent" as the code author

4. **Launch the Evaluator subagent** using the Agent tool:
   - Pass the prepared prompt
   - Use `subagent_type: "superpowers:code-reviewer"` if available, otherwise use default
   - Instruct the subagent to write the QA report to `docs/harness/<slug>/qa_report.md`

5. When the subagent returns, read `docs/harness/<slug>/qa_report.md` to get the verdict.

### Step 6: Verdict & Loop

Read qa_report.md and determine verdict (look for "Verdict: PASS" or "Verdict: FAIL").

**If PASS:**
- Update state.json: phase → `"completed"`
- Inform user (in `user_lang`): task complete
- Proceed to Step 7

**If FAIL and rounds remaining (round < max_rounds):**
- Do NOT automatically retry. Ask user (in `user_lang`) with a message equivalent to:
  > "QA result: FAIL. [failure summary]. Proceed to next round? (proceed / stop)"
- If user confirms: increment round in state.json, go back to Step 4
- If user stops: update phase to "completed", proceed to Step 7

**If FAIL and max rounds reached:**
- Update state.json: phase → `"completed"`
- Inform user of remaining issues (in `user_lang`)
- Proceed to Step 7

### Step 7: Cleanup & Commit

Ask the user (in `user_lang`) whether to commit the artifacts (spec.md, changes.md, qa_report.md).

- If commit: stage and commit `docs/harness/<slug>/` files
- Clean up `.harness/` directory (delete state.json and the directory)

### Status Check (anytime)

If user asks for status, read `.harness/state.json` and display (in `user_lang`):
```
[harness]
  Task   : <task>
  Phase  : <phase label>
  Round  : <round> / <max_rounds>
  Branch : <branch>
  Scope  : <scope>
```

Phase labels: plan_ready → "Planner — writing spec", gen_ready → "Generator — implementing", eval_ready → "Evaluator — reviewing", completed → "Completed"

## Key Rules

- **Never skip phases.** Always Planner → Generator → Evaluator.
- **Confirmation gates are non-negotiable.** No implicit approval, no proceeding on ambiguity.
- **Stay within scope.** Do not modify files outside the specified scope.
- **Evaluator must be isolated.** Always run as a subagent with anchor-free input. Never pass Generator reasoning to the Evaluator.
- **Git safety.** The workflow creates a branch automatically.
- **Use whatever skills are available.** Search installed skills by capability keyword (e.g. "brainstorming", "tdd", "code-review"), not by plugin name. If no match exists, proceed without it. Never fail because a specific plugin is missing.
- **User language.** All user-facing output (messages, spec, reports) must be in `user_lang`. Re-detect on every user message. Templates and internal state stay in English.
