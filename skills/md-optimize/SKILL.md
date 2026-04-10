---
name: md-optimize
description: Optimize CLAUDE.md and project .md files for token efficiency. Applies Dual-Zone model (Inline/Index), deduplication, and structural compression. Use on any project to reduce context token cost.
---

# MD Optimize

You are a **Markdown Token Optimizer**. You restructure a project's CLAUDE.md and .md files to minimize token consumption while preserving all semantic content.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang`. All user-facing output (confirmations, reports, errors) must be in `user_lang`. Template instructions (this file) stay in English.

## Exclusion List

Never modify: `.git/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `__pycache__/`, `.venv/`, `*.lock`, `.next/`, `.nuxt/`, `coverage/`, `.turbo/`, `.cache/`, `CHANGELOG.md`, `LICENSE.md`, `LICENSE`.

## Phase 1: Analysis

### 1a. Safety & Environment Check

1. Run `git status` in CWD. If not a git repo, ask the user using AskUserQuestion (in `user_lang`):
     header: "Git Warning"
     question: "This project is not managed by git. Automatic rollback not possible."
     options:
       - label: "Proceed" / description: "Continue without git safety net"
       - label: "Abort" / description: "Stop and set up git first"
   On "Abort": halt. On "Proceed": continue.
2. Check for uncommitted changes. If found, ask the user using AskUserQuestion (in `user_lang`):
     header: "Uncommitted"
     question: "Uncommitted changes detected."
     options:
       - label: "Continue" / description: "Proceed with uncommitted changes"
       - label: "Abort" / description: "Stop and commit/stash first"
   On "Abort": halt. On "Continue": proceed.
3. Search all `.md` files for the idempotency marker `<!-- managed by md-optimize -->`. If CLAUDE.md contains this marker, inform user: "This project was previously optimized. Re-running will refresh the optimization." Proceed normally (marker ensures idempotency).

### 1b. Smart Routing & Markdown Inventory

1. Glob `**/*.md` (excluding items in Exclusion List). List all found files with byte sizes.
2. Check if `CLAUDE.md` exists. If yes, read its content and note current size.
3. Evaluate project state and recommend action:

| State | Recommendation | Action |
|-------|---------------|--------|
| No .md files found | **Generate instead** | Use AskUserQuestion with situation context |
| Only CLAUDE.md exists and < 500 bytes | **Generate instead** | Use AskUserQuestion with situation context |
| CLAUDE.md exists and is comprehensive, .md files have redundancy | **Optimize** | Proceed with md-optimize (this skill) |
| CLAUDE.md is thin but other .md files are substantial | **Generate then optimize** | Use AskUserQuestion with situation context |
| No CLAUDE.md but other .md files exist | **Generate then optimize** | Use AskUserQuestion with situation context |

When the recommendation is not "Optimize" (i.e., generation may be needed), ask the user using AskUserQuestion (in `user_lang`):
  header: "Routing"
  question: "[situation description]. CLAUDE.md generation may be needed first."
  options:
    - label: "Switch: /md-generate" / description: "Run /md-generate first, then re-run /md-optimize"
    - label: "Continue" / description: "Proceed with optimization as-is"

If user selects "Switch: /md-generate": halt this skill. The user should then invoke `/md-generate` manually.
If user selects "Continue": proceed with optimization.

4. Estimate token count per file: `bytes / 4` for ASCII, `bytes / 3` for CJK-heavy content. Note: these are rough estimates; actual tokenization varies.

### 1c. Duplication Detection

Use `md5sum` (or `sha256sum` if unavailable) via Bash on each .md file. Group files by hash. Files with identical hashes are exact duplicates. For near-duplicates, compare headings structure only (not full content).

### 1d. CLAUDE.md Dual-Zone Classification

Scan existing CLAUDE.md (if any) and all .md content. Classify each piece of information:

| Zone | Criteria | Examples |
|------|----------|---------|
| **Inline** | Rules, constraints, conventions that MUST be in context at all times | "Never commit .env", "Use snake_case", "All API responses use JSON" |
| **Index** | Reference material, guides, detailed docs that can be loaded on-demand | Architecture overviews, API endpoint lists, setup guides, onboarding docs |

**Inline keyword safety net** — Content containing these keywords MUST stay Inline regardless of length: `never`, `always`, `must`, `forbidden`, `required` and their equivalents in the user's language (e.g., CJK constraint keywords). Apply case-insensitive matching.

## Phase 2: Confirmation Gate

<HARD-GATE>
Present to the user (in `user_lang`):

1. **Inline Zone preview**: Bulleted list of rules/conventions that will remain in CLAUDE.md body
2. **Index Zone preview**: Table of `| File | Path | Summary |` entries that will become index references
3. **Duplicate list**: Files identified as exact/near duplicates and proposed action (merge/remove)
4. **Estimated savings**: `(current_total_tokens - projected_total_tokens) / current_total_tokens * 100`%

Ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Optimize"
  question: "Review optimization plan above. This will restructure markdown files."
  options:
    - label: "Proceed" / description: "Apply the optimization plan as shown"
    - label: "Modify" / description: "Adjust zone assignments before proceeding"
    - label: "Stop" / description: "Abort optimization"

If user selects "Modify" or provides modification details via "Other": update zone assignments and re-present this question.
If user selects "Stop": halt.
Only "Proceed" advances to Phase 3.
</HARD-GATE>

## Phase 3: Execution (Sequential with Completion Check)

Execute in strict order. After each step, verify the output file exists and is non-empty. If any step fails, stop and advise: "Step N failed. Run `git checkout -- .` to restore all files, then retry."

### Step 3a: Create/Update Split Files

For each Index Zone item that needs a dedicated file:
- Create or update the target `.md` file at its designated path
- Preserve any existing frontmatter
- Add `<!-- managed by md-optimize -->` marker at the top of each managed file

### Step 3b: Rewrite CLAUDE.md

Structure the new CLAUDE.md as:

```
<!-- managed by md-optimize -->
# CLAUDE.md

## Rules & Conventions (Inline Zone)
[all Inline content — compressed, imperative style, no redundancy]

## Reference Index
| Topic | Path | Summary |
|-------|------|---------|
| ...   | ...  | ...     |
```

Apply token-efficient writing: short imperative sentences, tables over prose, remove filler words, collapse verbose lists.

### Step 3c: Clean Originals

For files whose content was fully migrated to CLAUDE.md Inline Zone or merged into another file:
- Delete only if 100% of content is preserved elsewhere
- Never delete files that contain non-migrated content

### Step 3d: Remove Duplicates

Delete exact-duplicate files (keep the one with the shortest path or most canonical name). Update any references to deleted files in remaining `.md` files.

## Phase 4: Evaluator (Isolated Sub-Agent)

An independent sub-agent reviews the optimized result **without access to the optimizer's classification reasoning**. This catches content loss, misclassification, and broken references that self-verification tends to miss.

### 4a. Sub-Agent Dispatch

Launch an isolated sub-agent with the following brief:

> You are an independent evaluator. A CLAUDE.md and related .md files have been restructured for token efficiency. Your job is to verify nothing was lost or broken. Assume defects exist — your job is to find them.

The sub-agent receives:
- The optimized CLAUDE.md and all modified/created .md files
- The git diff of all changes (before vs after)
- Full read access to the project files
- No Phase 1 analysis results, no optimizer reasoning

### 4b. Evaluation Criteria

The sub-agent checks each criterion and scores PASS / ISSUE:

| Criterion | Check | Method |
|-----------|-------|--------|
| **Content preservation** | No semantic information was lost during optimization | Compare git diff — every deleted line's meaning must exist in the new structure |
| **Zone correctness** | Inline items are truly must-know rules; Index items are truly reference material | Review each Inline item for constraint keywords; review each Index item for reference nature |
| **Path integrity** | Every path in Reference Index exists and is readable | Verify each path |
| **Link integrity** | All internal `[text](path)` links resolve to existing files | Check all links in modified files |
| **Marker consistency** | All managed files contain `<!-- managed by md-optimize -->` | Scan all modified files |
| **Frontmatter integrity** | Files with YAML frontmatter still parse correctly | Validate frontmatter syntax |
| **Keyword safety** | Content with constraint keywords (`never`, `always`, `must`, `forbidden`, `required` and user-language equivalents) is in Inline Zone | Search for keywords in Index files — any match is a misclassification |

### 4c. Evaluation Output

The sub-agent produces a structured report:

```
[md-optimize evaluator]
  PASS : N criteria
  ISSUE: N criteria

Issues found:
  1. [criterion] — [specific problem] — [suggested fix]
  2. ...

Content at risk:
  1. [content that may have been lost or misclassified]
  2. ...

Verdict: PASS | NEEDS_REVISION
```

### 4d. Revision Handling

- **PASS**: Proceed to Phase 5 (Report).
- **NEEDS_REVISION**: Ask the user using AskUserQuestion (in `user_lang`):
    header: "Fixes"
    question: "Evaluator found {N} issues."
    options:
      - label: "Fix all" / description: "Auto-fix all reported issues"
      - label: "Skip" / description: "Proceed without fixing"
    "Other" allows selective fix (user specifies which issues to fix).
  Apply fixes for each confirmed issue. Do not re-run the full evaluator — only verify the specific fixes were applied correctly.

## Phase 5: Report

Print final report (in `user_lang`):

```
[md-optimize] Optimization Complete
  Files scanned    : N
  Files modified   : N
  Files deleted    : N (duplicates/merged)
  Inline rules     : N items
  Index references : N entries
  Evaluator        : PASS | REVISED (N issues fixed)
  Token estimate   : before → after (−X%)
```

If any evaluation criterion has unresolved issues, append warnings.

## Safety Rules

- **Git-first**: Always verify git status before any write operation. Recommend commit/stash for dirty trees.
- **Idempotency**: `<!-- managed by md-optimize -->` marker prevents re-processing conflicts. On re-run, refresh existing optimization rather than duplicating.
- **No data loss**: Never delete content without verifying it exists elsewhere. When in doubt, keep the original.
- **Sequential execution**: Phase 3 steps run in order (a→b→c→d). Not atomic — on failure, guide user to `git checkout` for recovery.
- **Scope boundary**: Only modify `.md` files. Never modify source code, configs, or non-markdown files.
- **Sub-CLAUDE.md**: If subdirectories contain their own `CLAUDE.md`, treat as separate Inline Zones — do not merge into root CLAUDE.md. Add them to the Reference Index instead.
- **Batch sizing**: Process files in batches of min(10, file_count/3). Adjust based on average file size — larger files get smaller batches.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`
