---
name: code-review
description: Systematic, bias-free code review for PRs, branches, or file changes. 3-tier modes — quick (1 agent, 5-perspective checklist), deep (2 specialist sub-agents + synthesis), thorough (3 specialists + cross-verification + synthesis). Use for reviewing PRs, staged changes, or any diff.
---

# Code Review

You are orchestrating a **systematic, bias-free code review** with selectable depth.

**Zero-setup:** No initialization required. Accepts PR#, branch name, commit range, or file path.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang`.

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, the review report narrative.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), file names (review_report.md), field names in the report YAML header.

## Standard Status Format

When displaying status, print (in `user_lang`):
```
[code-review]
  Target : <PR#, branch, commit range, or file path>
  Mode   : <quick | deep | thorough>
  Model  : <model_config preset name>
  Phase  : <phase label>
  Scope  : <N files, M lines>
```
Phase labels: input_parse -> "Parsing input", diff_collect -> "Collecting diff", review -> "Reviewing", cross_verify -> "Cross-verifying", synthesis -> "Synthesizing", complete -> "Complete"

## Workflow

When the user provides a review target (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Input Parsing & Diff Collection

1. **Detect user language** from the input. Store as `user_lang`.
2. **Parse the review target** from the user's input. Supported formats:

   | Input | Detection | Command |
   |-------|-----------|---------|
   | `#123` or `PR #123` | PR number | `gh pr diff 123` |
   | `feature/foo` | Branch name | `git diff main...feature/foo` |
   | `abc1234..def5678` | Commit range | `git diff abc1234..def5678` |
   | `abc1234` | Single commit | `git show abc1234 --stat` then `git diff abc1234~1..abc1234` |
   | `src/foo.ts` | File path | `git diff HEAD -- src/foo.ts` |
   | `--staged` | Staged changes | `git diff --cached` |
   | (no argument) | Unstaged changes | `git diff` |

3. **Collect the diff.** Run the appropriate git/gh command. Capture the full unified diff output.

4. **Error handling:**
   - **Empty diff** -> Inform user (in `user_lang`): "No changes found for the given target. Nothing to review." Halt.
   - **PR not found** -> Inform user: "PR #N not found or not accessible. Verify the PR number and try again." Halt.
   - **Binary files** -> Note binary files in the diff. Skip them from review. Add a note to the report: "Binary files skipped: [list]".
   - **Diff > 2000 lines** -> Ask the user using AskUserQuestion (in `user_lang`):
       header: "Large Diff"
       question: "Large diff detected ({N} lines). Review quality may degrade."
       options:
         - label: "Proceed" / description: "Review the full diff as-is"
         - label: "Abort" / description: "Split into smaller chunks before reviewing"
     On "Abort", halt.

5. **Collect metadata** (used only for report header, NOT passed to reviewers in deep/thorough modes):
   - File list with line counts per file
   - Total lines added / removed
   - For PRs: PR title, PR number (but NOT PR description or commit messages -- these introduce anchoring bias)

6. **Slugify the target** for artifact path: lowercase, replace non-word chars with hyphens, truncate to 50 chars. Store as `<slug>`. Example: PR #123 -> `pr-123`, `feature/auth-fix` -> `feature-auth-fix`.

7. **Create artifact directory:** `docs/harness/<slug>/`

### Step 2: Mode Selection

1. **Scope-aware recommendation.** Count total diff lines and recommend:

   | Diff size | Recommended mode | Rationale |
   |-----------|-----------------|-----------|
   | < 100 lines | quick | Small change, single-pass sufficient |
   | 100-500 lines | deep | Medium change, benefits from specialist perspectives |
   | 500+ lines | thorough | Large change, needs comprehensive multi-angle review |

2. **Mode selection.** If `--mode quick`, `--mode deep`, or `--mode thorough` was passed, set mode and skip prompt. Otherwise, ask the user using AskUserQuestion (in `user_lang`):
     header: "Review Mode"
     question: "Select review depth: (Diff: {N} files, {M} lines)"
     options:
       - label: "quick" / description: "1 agent, 5-perspective checklist (~1x tokens)"
       - label: "deep" / description: "2 specialists + synthesis (~1.5x tokens)"
       - label: "thorough" / description: "3 specialists + cross-verification + synthesis (~2.5x tokens)"
     Add "(Recommended)" to the label of the auto-recommended mode based on the scope-aware recommendation table above.
3. **Model configuration selection (deep and thorough modes only):**
   If mode is `quick`, skip this step (no sub-agents used).

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

   **Persist to `.harness/model_config.json`** (code-review is stateless — no state.json). Create `.harness/` directory if needed.

### Step 3: Confirmation Gate (deep and thorough only)

<HARD-GATE>
For `deep` and `thorough` modes only. Skip this gate for `quick` mode.

Ask the user using AskUserQuestion (in `user_lang`):
  header: "Confirm"
  question: "{mode} review runs multiple sub-agents and uses more tokens."
  options:
    - label: "Proceed" / description: "Start {mode} review as selected"
    - label: "Switch to quick" / description: "Use single-agent quick review instead"
    - label: "Abort" / description: "Cancel the review"

On "Switch to quick": change mode to quick and proceed. On "Abort": halt.
</HARD-GATE>

### Step 4: Review Execution

Branch by mode:

#### Mode: quick -- Step 4-Q

Perform the review inline (no sub-agents). Apply the 5-perspective checklist below against the collected diff.

**Bias reduction (quick mode):** Even though quick mode uses a single pass, apply these:
- Do NOT read PR description or commit messages. Review code changes only.
- Assume defects exist. Your job is to find them, not to confirm correctness.
- Do not consider who wrote the code. Evaluate on merit alone.

**5-Perspective Checklist:**

For each changed file in the diff, evaluate:

**1. Correctness**
- Logic errors, off-by-one, null/undefined handling
- Edge cases not covered
- Type mismatches or incorrect type assertions
- Race conditions or concurrency issues
- API contract violations (wrong params, missing fields)

**2. Security**
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication/authorization gaps
- Sensitive data exposure (secrets, PII in logs)
- Input validation and sanitization
- Insecure defaults or configurations

**3. Performance**
- O(n^2) or worse in hot paths
- Unnecessary allocations or copies
- Missing caching opportunities
- N+1 queries or unoptimized DB access
- Blocking operations in async contexts

**4. Maintainability**
- Naming clarity (variables, functions, types)
- Code duplication introduced
- Overly complex logic (high cyclomatic complexity)
- Missing or misleading comments
- Violation of existing project conventions

**5. Testing**
- Are new behaviors covered by tests?
- Are edge cases tested?
- Test quality (meaningful assertions vs. trivial)
- Existing tests broken by the change?
- Missing integration or boundary tests

For each finding, record:
- **Severity**: Critical / Major / Minor / Suggestion
- **Category**: Correctness / Security / Performance / Maintainability / Testing
- **Location**: `file:line` (or line range)
- **Description**: What the issue is
- **Suggestion**: How to fix it (concrete, actionable)

After completing the checklist, proceed to Step 5 (Report Generation).

#### Mode: deep -- Step 4-D

##### Step 4-D1: Parallel Specialist Review (2 sub-agents)

1. Read two reviewer templates from `{CLAUDE_PLUGIN_ROOT}/templates/code-review/`:
   - `security_correctness_reviewer.md`
   - `architecture_maintainability_reviewer.md`

2. For each reviewer, fill template variables:
   - `{diff_content}`: the full unified diff
   - `{file_list}`: list of changed files with line counts
   - `{user_lang}`: detected user language
   - `{output_path}`: `.harness/code-review/review_<reviewer>.md`

3. **Create directory:** `.harness/code-review/`

4. **Launch 2 sub-agents in parallel** using the Agent tool. Each receives its reviewer template with the diff. Each writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Security & Correctness Reviewer, Architecture & Maintainability Reviewer → executor role).

   **Bias reduction applied to each sub-agent:**
   - **Context isolation**: each reviewer runs as a separate sub-agent with no shared state
   - **Anchor-free**: no PR description, commit messages, or author information -- code diff only
   - **Defect assumption**: template instructs "assume defects exist, find them"
   - **Author neutralization**: no author identity disclosed

5. Wait for both to complete. Verify both review files exist.

##### Step 4-D2: Synthesis (main agent)

Proceed to Step 5 (Report Generation). The main agent reads both review files and synthesizes into the final report. No synthesis sub-agent -- the main agent handles this directly to keep costs down.

#### Mode: thorough -- Step 4-T

##### Step 4-T1: Parallel Specialist Review (3 sub-agents)

1. Read three reviewer templates from `{CLAUDE_PLUGIN_ROOT}/templates/code-review/`:
   - `security_correctness_reviewer.md`
   - `architecture_design_reviewer.md`
   - `dx_maintainability_reviewer.md`

2. For each reviewer, fill template variables:
   - `{diff_content}`: the full unified diff
   - `{file_list}`: list of changed files with line counts
   - `{user_lang}`: detected user language
   - `{output_path}`: `.harness/code-review/review_<reviewer>.md`

3. **Create directory:** `.harness/code-review/`

4. **Launch 3 sub-agents in parallel** using the Agent tool. Each receives its reviewer template. Each writes to its output_path. If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (all three reviewers → executor role).

   Same bias reduction as deep mode (context isolation, anchor-free, defect assumption, author neutralization).

5. Wait for all 3 to complete. Verify all 3 review files exist.

##### Step 4-T2: Cross-Verification (3 sub-agents)

1. Read the cross-verification template: `{CLAUDE_PLUGIN_ROOT}/templates/code-review/cross_verification.md`

2. Read all 3 review files from Step 4-T1.

3. For each reviewer, prepare the cross-verification prompt with:
   - `{reviewer_name}`: the reviewer's identity (same as their original role)
   - `{diff_content}`: the full unified diff (so they can re-check specific claims)
   - `{review_1_author}`, `{review_1_content}`: first OTHER reviewer's findings
   - `{review_2_author}`, `{review_2_content}`: second OTHER reviewer's findings
   - `{user_lang}`: detected user language
   - `{output_path}`: `.harness/code-review/crossverify_<reviewer>.md`

4. **Launch 3 sub-agents in parallel.** If `model_config.preset` is not `"default"`, pass `model` parameter per the Model Selection table (Cross-Verification → advisor role). Each reads the other two reviewers' findings and verifies:
   - Are the reported findings real? (validate against actual diff)
   - Are there findings they missed that the others caught?
   - Are severity ratings appropriate?
   - Any false positives?

5. Wait for all 3 to complete. Verify all 3 cross-verification files exist.

##### Step 4-T3: Synthesis (main agent)

Proceed to Step 5 (Report Generation). The main agent reads all 6 files (3 reviews + 3 cross-verifications) and synthesizes into the final report.

### Step 5: Report Generation

The main agent synthesizes all findings into `docs/harness/<slug>/review_report.md`.

#### For quick mode:
Use the findings collected during the inline 5-perspective checklist.

#### For deep mode:
1. Read both review files from `.harness/code-review/`.
2. Merge findings. Deduplicate (same file:line, same issue -> keep the more detailed one).
3. Resolve severity disagreements: if reviewers disagree on severity, take the higher severity.

#### For thorough mode:
1. Read all 6 files from `.harness/code-review/` (3 reviews + 3 cross-verifications).
2. Merge findings. Deduplicate.
3. Cross-verification adjustments:
   - If a finding was confirmed by cross-verification -> keep, note "verified"
   - If a finding was flagged as false positive by cross-verification -> downgrade or remove, note rationale
   - If cross-verification raised new findings -> add them
4. Resolve severity using cross-verification consensus.

#### Report Format

Write the report to `docs/harness/<slug>/review_report.md` in **{user_lang}** (except the Assessment line value which stays in English for programmatic parsing):

```markdown
# Code Review Report

| Field | Value |
|-------|-------|
| Target | <PR#, branch, commit range, or file path> |
| Mode | <quick / deep / thorough> |
| Files | <N files> |
| Lines | +<added> / -<removed> |
| Date | <ISO8601 date> |

## Assessment: APPROVE | REQUEST_CHANGES | COMMENT

## Summary

<2-4 sentence overview of the review findings in user_lang>

## Findings

### Critical

| # | File:Line | Category | Description | Suggestion |
|---|-----------|----------|-------------|------------|
| 1 | `path/file.ts:42` | Security | <description> | <suggestion> |

### Major

| # | File:Line | Category | Description | Suggestion |
|---|-----------|----------|-------------|------------|
| 1 | `path/file.ts:15-20` | Correctness | <description> | <suggestion> |

### Minor

| # | File:Line | Category | Description | Suggestion |
|---|-----------|----------|-------------|------------|
| 1 | `path/file.ts:88` | Maintainability | <description> | <suggestion> |

### Suggestions

| # | File:Line | Category | Description | Suggestion |
|---|-----------|----------|-------------|------------|
| 1 | `path/file.ts:100` | Performance | <description> | <suggestion> |

## Statistics

| Severity | Count |
|----------|-------|
| Critical | N |
| Major | N |
| Minor | N |
| Suggestion | N |
| **Total** | **N** |

## Files Reviewed

| File | Lines Changed | Findings |
|------|--------------|----------|
| `path/file.ts` | +10 / -3 | 2 |

## Notes

- Binary files skipped: [list, if any]
- [any other notes]
```

#### Assessment Logic

Determine the assessment based on findings:

| Condition | Assessment |
|-----------|-----------|
| Any Critical findings | REQUEST_CHANGES |
| 3+ Major findings | REQUEST_CHANGES |
| 1-2 Major findings | COMMENT |
| Only Minor / Suggestion | APPROVE |
| No findings | APPROVE |

**Keep `## Assessment: APPROVE`, `## Assessment: REQUEST_CHANGES`, or `## Assessment: COMMENT` exactly as shown (English, on one line).** Parsed programmatically.

### Step 6: Smart Routing

After presenting the report, suggest next actions based on findings (in `user_lang`):

| Finding pattern | Suggestion |
|----------------|------------|
| Critical/Major correctness or security bugs | "Consider `/workflow` to fix these issues systematically" |
| Structural/architectural issues | "Consider `/workflow` to refactor the affected components" |
| Minor style/convention issues | "These can be addressed in a follow-up commit" |
| No significant findings | "Code looks good. No action needed." |

These are suggestions only -- do not auto-invoke other skills.

### Step 7: Cleanup

1. Print the final report summary (in `user_lang`):
   ```
   [code-review] Review Complete
     Target     : <target>
     Mode       : <mode>
     Assessment : <APPROVE / REQUEST_CHANGES / COMMENT>
     Findings   : N critical, N major, N minor, N suggestions
     Report     : docs/harness/<slug>/review_report.md
   ```

2. Clean up temporary files: delete `.harness/code-review/` directory and `.harness/model_config.json` (if they exist). Remove `.harness/` if empty.

3. Report file is preserved at `docs/harness/<slug>/review_report.md`.

## Model Selection

Sub-agents (deep and thorough modes only) can run on different models depending on the selected `model_config` preset. The presets map each role (executor, advisor, evaluator) to a model:

| Preset | executor | advisor | evaluator |
|--------|----------|---------|-----------|
| default | (parent inherit) | (parent inherit) | (parent inherit) |
| all-opus | opus | opus | opus |
| balanced | sonnet | opus | opus |
| economy | haiku | sonnet | sonnet |

Each sub-agent is assigned a role. The following table defines the concrete model for every sub-agent under each preset:

### Deep Mode Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Security & Correctness Reviewer | executor | (no override) | opus | sonnet | haiku |
| Architecture & Maintainability Reviewer | executor | (no override) | opus | sonnet | haiku |

### Thorough Mode Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Security & Correctness Reviewer | executor | (no override) | opus | sonnet | haiku |
| Architecture & Design Reviewer | executor | (no override) | opus | sonnet | haiku |
| DX & Maintainability Reviewer | executor | (no override) | opus | sonnet | haiku |
| Cross-Verification (per reviewer) | advisor | (no override) | opus | opus | sonnet |

**Applying model config:** When launching any sub-agent, if `model_config.preset` is not `"default"`, pass the `model` parameter according to the table above for that sub-agent. Sub-agents must NOT directly access `.harness/model_config.json` — the orchestrator passes the model parameter at launch time.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`

## Key Rules

- **Read-only.** Never modify source code. Never create git branches. Only output is the review report.
- **No anchoring.** In deep/thorough modes, never pass PR descriptions, commit messages, or author identity to reviewer sub-agents. Code diff only.
- **Defect assumption.** All reviewers start from "assume defects exist" -- not "confirm correctness."
- **Author neutralization.** Never mention or consider who wrote the code. Review on merit.
- **Context isolation.** In deep/thorough modes, each reviewer sub-agent is independent. No shared state between reviewers.
- **User language.** All user-facing output in `user_lang`. Re-detect on every message.
- **Intermediate outputs are ephemeral.** Only `review_report.md` is preserved in `docs/harness/<slug>/`.
- **Binary files.** Skip with a note, never attempt to review binary content.
- **Confirmation gate.** Required for deep/thorough modes. Quick mode proceeds directly.
- **Assessment line format.** Must be `## Assessment: APPROVE`, `## Assessment: REQUEST_CHANGES`, or `## Assessment: COMMENT` -- English only, one line, no translation. Parsed programmatically.
