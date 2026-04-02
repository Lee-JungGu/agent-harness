---
name: harness
description: 3-Phase (Planner -> Generator -> Evaluator) development workflow. Use when starting feature work, bug fixes, or maintenance tasks that benefit from structured planning, implementation, and review.
---

# Agent Harness Workflow

You are orchestrating a 3-Phase development workflow using the Agent Harness CLI.

**Zero-setup:** No initialization or repo registration required. The harness auto-detects language, test commands, and build commands from the current directory.

## Workflow

When the user provides a task (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Start the task

Run from the current working directory:

```bash
python {CLAUDE_PLUGIN_ROOT}/harness.py run --task "$ARGUMENTS"
```

Optional flags: `--scope "<pattern>"`, `--max-rounds 3`, `--max-files 20`, `--dry-run`

The harness will:
- Auto-detect language and test/build commands
- Create `.harness/` directory with state tracking
- Create a git branch `harness/<task-slug>`
- Render the Planner prompt

### Step 2: Execute Phase 1 (Planner)

Read `.harness/planner_prompt_rendered.md` and follow its instructions to:
1. Explore the codebase (CLAUDE.md, relevant files)
2. Write `.harness/spec.md` (goal, background, scope, approach, completion criteria, risks)
3. Use brainstorming/planning skills if available in any installed plugin

**Show spec.md to the user for confirmation before proceeding.**

### Step 3: Advance to Phase 2 (Generator)

```bash
python {CLAUDE_PLUGIN_ROOT}/harness.py next
```

Read `.harness/generator_prompt_rendered.md` and follow its instructions to:
1. Implement the code changes according to spec
2. Stay within scope, respect max files limit
3. Write `.harness/changes.md` listing all modified/created files
4. Use TDD/testing skills if available

### Step 4: Advance to Phase 3 (Evaluator)

```bash
python {CLAUDE_PLUGIN_ROOT}/harness.py next
```

Read `.harness/evaluator_prompt_rendered.md` and follow its instructions to:
1. Run tests if available (auto-detected build + test commands)
2. Code review all changed files against 5 criteria
3. Write `.harness/qa_report.md` with PASS/FAIL verdict
4. Use code review/verification skills if available

### Step 5: Check result

```bash
python {CLAUDE_PLUGIN_ROOT}/harness.py next
```

- PASS: task complete. Inform the user.
- FAIL + rounds remaining: go back to Step 3 (Generator re-runs with QA feedback).
- FAIL + max rounds reached: inform the user of remaining issues.

### Status check (anytime)

```bash
python {CLAUDE_PLUGIN_ROOT}/harness.py status
```

## Key Rules

- **Never skip phases.** Always Planner -> Generator -> Evaluator.
- **Confirm spec with user** before proceeding to Generator.
- **Stay within scope.** Do not modify files outside the specified scope.
- **Evaluator must be strict.** Do not hand-wave issues.
- **Git safety.** The harness creates a branch automatically.
- **Use whatever skills are available.** Don't require specific plugins — use matching skills from any installed plugin.
- **Language matching.** Detect the language of the user's task description and communicate all progress updates, questions, and reports in that same language. Spec sections, QA criteria, and commit messages should also match the detected language.
