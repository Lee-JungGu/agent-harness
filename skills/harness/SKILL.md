---
name: harness
description: 3-Phase (Planner -> Generator -> Evaluator) development workflow. Use when starting feature work, bug fixes, or maintenance tasks that benefit from structured planning, implementation, and review.
---

# Agent Harness Workflow

You are orchestrating a 3-Phase development workflow.

**Zero-setup:** No initialization required. Auto-detects language, test commands, and build commands from the current directory.

## Workflow

When the user provides a task (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Slugify the task:** lowercase, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.

2. **Auto-detect language and commands.** Scan the repo root with Glob and check for these files:

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

3. **Create directories:**
   - `.harness/` (working state)
   - `docs/harness/<slug>/` (artifacts)

4. **Create git branch:**
   ```bash
   git checkout -b harness/<slug>
   ```

5. **Write `.harness/state.json`:**
   ```json
   {
     "task": "<user's task description>",
     "repo_name": "<directory name>",
     "repo_path": "<absolute path>",
     "phase": "plan_ready",
     "round": 1,
     "scope": "<user-provided scope or '(no limit)'>",
     "max_rounds": 3,
     "max_files": 20,
     "branch": "harness/<slug>",
     "lang": "<detected>",
     "test_cmd": "<detected or null>",
     "build_cmd": "<detected or null>",
     "docs_path": "docs/harness/<slug>/",
     "created_at": "<ISO8601>"
   }
   ```

6. **Print setup summary** to the user:
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
2. Interpret it with the current context (task, repo_path, lang, scope). Do NOT write a rendered file — process inline.
3. Follow the planner instructions:
   - Explore the codebase (CLAUDE.md, relevant files)
   - **Invoke a brainstorming skill** — search installed skills for "brainstorming" or "ideation" and invoke the first match
   - **Invoke a planning skill** — search installed skills for "writing-plans" or "plan" and invoke the first match
   - If no matching skill is found, proceed without it
   - Write `spec.md` to `docs/harness/<slug>/spec.md`
4. Update `.harness/state.json`: set phase to `"plan_ready"` (spec written, awaiting confirmation).

### Step 3: HARD GATE — Spec Confirmation

<HARD-GATE>
Show spec.md to the user and ask for explicit confirmation. Do NOT proceed to Generator until confirmed.

**Allowed responses (proceed only on these):**
"진행", "승인", "ㅇㅇ", "go", "proceed", "approve", "확인", "좋아", "넘어가", "yes", "ok", "lgtm"

**Ambiguous — must re-confirm:**
"음...", "글쎄", "괜찮은 것 같은데", questions, conditional statements, topic changes.

On ambiguity, respond:
> "구현을 시작하면 토큰 소비가 크므로 명확한 확인이 필요합니다. spec 내용대로 구현을 진행할까요? (진행/수정/중단)"

If user requests modifications, update spec.md and re-confirm. If user says "중단" or "stop", halt the workflow.
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
6. Write `docs/harness/<slug>/changes.md` listing all modified/created files.

### Step 5: Evaluator Phase

1. Update state.json: phase → `"eval_ready"`.
2. Read the evaluator template: `{CLAUDE_PLUGIN_ROOT}/templates/evaluator_prompt.md`
3. Interpret with context:
   - `spec_content`, `changes_content`: from docs/harness/<slug>/
   - `test_available`, `build_cmd`, `test_cmd`: from state.json
   - `round_num`, `scope`: from state.json
4. **Invoke evaluation skills** — search installed skills and invoke matches:
   - If tests fail: search for "systematic-debugging" or "debugging"
   - Search for "requesting-code-review" or "code-review"
   - Search for "verification-before-completion" or "verification"
   - If no matching skill is found, proceed without it
5. Follow the evaluator instructions:
   - Run tests if available
   - Code review against 5 criteria
   - Write `docs/harness/<slug>/qa_report.md` with PASS/FAIL verdict

### Step 6: Verdict & Loop

Read qa_report.md and determine verdict (look for "Verdict: PASS" or "Verdict: FAIL" or Korean equivalents).

**If PASS:**
- Update state.json: phase → `"completed"`
- Inform user: task complete
- Proceed to Step 7

**If FAIL and rounds remaining (round < max_rounds):**
- Do NOT automatically retry. Ask user:
  > "QA 결과 FAIL입니다. [failure summary]. 다음 라운드로 수정을 진행할까요? (진행/중단)"
- If user confirms: increment round in state.json, go back to Step 4
- If user stops: update phase to "completed", proceed to Step 7

**If FAIL and max rounds reached:**
- Update state.json: phase → `"completed"`
- Inform user of remaining issues
- Proceed to Step 7

### Step 7: Cleanup & Commit

Ask the user:
> "산출물(spec.md, changes.md, qa_report.md)을 커밋할까요? (커밋/스킵)"

- If commit: stage and commit `docs/harness/<slug>/` files
- Clean up `.harness/` directory (delete state.json and the directory)

### Status Check (anytime)

If user asks for status, read `.harness/state.json` and display:
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
- **Evaluator must be strict.** Do not hand-wave issues.
- **Git safety.** The workflow creates a branch automatically.
- **Use whatever skills are available.** Search installed skills by capability keyword (e.g. "brainstorming", "tdd", "code-review"), not by plugin name. If no match exists, proceed without it. Never fail because a specific plugin is missing.
- **Language matching.** Detect the language of the user's task description and communicate all progress updates, questions, and reports in that same language. Spec sections, QA criteria, and commit messages should also match the detected language.
