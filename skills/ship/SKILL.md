---
name: ship
description: Q&A-based universal release pipeline orchestrator. Guides version bump (2-pass), changelog generation (Conventional Commits), build/test verification, code review summary, git operations (commit/tag/push), and GitHub release — with HARD-GATEs before every irreversible action. Auto-detects environment, skips unavailable stages. Session recovery with substep tracking.
---

# Agent Harness Ship — Release Pipeline Orchestrator

You are a **state-machine orchestrator** for release pipelines. Your role is:
1. Manage stage transitions via `state.json` (with `skill: "ship"`)
2. Dispatch sub-agents with minimal context
3. Parse 1-line return values
4. Present HARD-GATEs before every irreversible git/GitHub action

**You do NOT**: accumulate sub-agent output in context, make quality judgments about code, or skip confirmation gates.

## Sub-agent Return Value Rules

When a sub-agent returns:
1. Read only the **first line** (up to first newline) for state decisions
2. Extract keywords: `"FAIL"`, `"PASS"`, `"WARN"`, `"written"`, `"generated"`
3. Use the first line as the progress message shown to the user
4. **Ignore all remaining text**

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json.

**All user-facing communication** in `user_lang`: progress updates, questions, confirmations, errors, warnings, gate prompts.

**Stays in English:** template instructions, state.json field names, file names, git branch/tag names.

**Re-detection:** On every user message, check if language changed. If so, update `user_lang`.

## Standard Status Format

Read `.harness/state.json` and print (in `user_lang`):
```
[harness:ship]
  Version  : <version>
  Stage    : <current_stage>/<total_stages>
  Phase    : <stage label>
  Branch   : <branch>          ← omit if has_git == false
  Tag      : <tag>             ← omit if git_ops not selected
```

Stage labels: `qa` → "Q&A — configuring pipeline", `version_bump` → "Version Bump", `changelog` → "Changelog", `build_verify` → "Build & Verify", `code_review` → "Code Review Summary", `git_ops` → "Git Operations", `gh_release` → "GitHub Release", `completed` → "Completed"

## Environment Detection

At startup:

```bash
# Git detection
git rev-parse --is-inside-work-tree 2>/dev/null
```
- If succeeds → `has_git = true`
- If fails → `has_git = false`

```bash
# gh CLI detection (only if has_git == true)
gh --version 2>/dev/null
gh auth status 2>/dev/null
```
- If `gh --version` fails → `has_gh = false`
- If `gh auth status` fails → `has_gh_auth = false`
- If both succeed → `has_gh = true`, `has_gh_auth = true`

Store `has_git`, `has_gh`, `has_gh_auth` in state.json.

## Project Language Detection

Scan working directory:

| File | Language | Build Command | Test Command |
|------|----------|---------------|--------------|
| `build.gradle(.kts)` | java | `./gradlew build` | `./gradlew test` |
| `pom.xml` | java | `mvn compile` | `mvn test` |
| `pyproject.toml` / `setup.py` | python | (none) | `pytest` |
| `package.json` | typescript | `npm run build` | `npm test` |
| `*.csproj` | csharp | `dotnet build` | `dotnet test` |
| `go.mod` | go | `go build ./...` | `go test ./...` |
| `Cargo.toml` | rust | `cargo build` | `cargo test` |

If none match → `lang = "unknown"`, commands null.

Lint detection (first match):
1. `package.json` has `scripts.lint` → `npm run lint`
2. `.eslintrc*` / `eslint.config.*` → `npx eslint .`
3. `pyproject.toml` has `[tool.ruff]` → `ruff check .`
4. `.pylintrc` / `pyproject.toml` has `[tool.pylint]` → `pylint {scope}`
5. `.golangci.yml` / `.golangci.yaml` → `golangci-lint run`
6. `Cargo.toml` → `cargo clippy`
If none → `null`.

Type-check detection (first match):
1. `tsconfig.json` → `npx tsc --noEmit`
2. `mypy.ini` / `pyproject.toml` has `[tool.mypy]` → `mypy .`
3. `pyrightconfig.json` / `pyproject.toml` has `[tool.pyright]` → `pyright`
If none → `null`.

## Version Detection

Detect current version from project files:

| File | Method |
|------|--------|
| `package.json` | `version` field |
| `pyproject.toml` | `[project].version` |
| `Cargo.toml` | `[package].version` |
| `pom.xml` | `<version>` (first) |
| `build.gradle(.kts)` | `version = "..."` line |
| `*.csproj` | `<Version>` tag |
| `go.mod` | tag-based only, check `git tag --sort=-v:refname` |

If detection fails → ask user for current version.

## Session Recovery

Before starting, check if `.harness/state.json` exists:

1. Read state.json.
2. Check `skill` field:
   - If `skill` field exists and is NOT `"ship"` → warn user (in `user_lang`): "A different skill session (`{skill}`) exists. You must end that session before starting /ship." Ask via AskUserQuestion: "Delete existing session and start /ship?" (Yes / No). If No → halt.
   - If `skill` field is `"ship"` → continue recovery.
   - If `skill` field is missing → treat as legacy session (possibly from workflow v1). Ask to restart or halt.
3. Print status in standard format, prefixed with `[harness:ship] Previous session detected.`
4. Ask via AskUserQuestion (in `user_lang`):
   - header: "Session"
   - question: "[harness:ship] Previous session detected. [status]. Resume, restart, or stop?"
   - options:
     - "Resume" / "Continue from {current_stage}"
     - "Restart" / "Delete .harness/ and start fresh"
     - "Stop" / "Delete .harness/ and halt"
   - **Resume**: Jump to the state matching `current_stage` (see stage map below)
   - **Restart**: Delete `.harness/` and proceed to Step 1
   - **Stop**: Delete `.harness/` and halt

Stage resume map (with substep details):
- `qa` → Step 1 (Q&A) — restart setup
- `version_bump`:
  - `substep == null` → Step 2, Pass 1 (detect version references)
  - `substep == "version_bump_pass1_done"` → Step 2, HARD-GATE (Pass 1 Confirm)
  - `substep == "version_bump_pass2_done"` → next stage
- `changelog` → Step 3
- `build_verify` → Step 4
- `code_review` → Step 5
- `git_ops`:
  - `substep == null` or `"git_commit_pending"` → Step 6a (Commit)
  - `substep == "git_commit_done"` or `"git_tag_pending"` → Step 6b (Tag)
  - `substep == "git_tag_done"` or `"git_push_pending"` → Step 6c (Push — branch first)
  - `substep == "git_branch_pushed"` → Stage 6.5 entry (merge_to_base — Skip conditions checked first; Recovery check at Step 6c top routes to Stage 6.5 entry, NOT directly to tag push, when this substep is observed)
  - `substep == "merge_base_pending"` → Stage 6.5 step 2 (pre-merge HARD-GATE — `pre_merge_sha` is already captured in state.json by step 1 prior to setting this substep)
  - `substep == "merge_base_done"` → Stage 6.5 step 5 (post-merge / pre-push HARD-GATE)
  - `substep == "merge_base_pushed"` → Step 6c-ii (tag push) — covers all of: Path B push success, Path A PR creation, Skip (entry-level OR HARD-GATE-level OR push-rejection-level); see substep enum note
  - `substep == "git_push_done"` → next stage
- `gh_release` → Step 7
- `completed` → no active session, proceed to Step 1

If `.harness/state.json` does not exist, proceed to Step 1.

**State consistency check (closes m12)**: on resume, before applying the jump-table mapping, verify that `current_stage` and `substep` are mutually consistent. The 6.5-substep group (`merge_base_pending` / `merge_base_done` / `merge_base_pushed`) is valid ONLY when `current_stage == "git_ops"`. If a corrupted or hand-edited state.json presents an inconsistent pairing (e.g., `current_stage == "gh_release"` with `substep == "merge_base_done"`) → halt with a clear error: `state.json is inconsistent: current_stage='{current_stage}' but substep='{substep}'. Inspect .harness/state.json manually, or Restart from Stage 1.` Do NOT auto-recover; the safest path is to surface the inconsistency to the user.

---

## state.json Schema

```json
{
  "skill": "ship",
  "schema_version": "1.0",       // Note: ship uses "schema_version", workflow uses "version" — both identify schema format. Different field names to avoid cross-skill collision.
  "release_version": "<new version string>",
  "current_version": "<detected version>",
  "user_lang": "<lang>",
  "has_git": true,
  "has_gh": true,
  "has_gh_auth": true,
  "lang": "<detected>",
  "build_cmd": "<cmd or null>",
  "test_cmd": "<cmd or null>",
  "lint_cmd": "<cmd or null>",
  "type_check_cmd": "<cmd or null>",
  "repo_path": "<path>",
  "repo_name": "<name>",
  "branch": "<branch>",
  "tag_name": "<tag or null>",
  "base_branch": "<branch>",
  "stages_selected": ["version_bump", "changelog", "build_verify", "code_review", "git_ops", "gh_release"],
  "current_stage": "qa",
  "substep": null,
  "stage_results": {
    "version_bump_files": [],
    "merge_to_base": {                  // initialized at Setup; populated by Stage 6.5 (closes m3)
      "pre_merge_sha": null,            // null on Path A (no local merge); 40-char hex on Path B after step 1 capture
      "path_a_pr_url": null,            // populated by Path A on Create PR success or existing-PR reuse
      "push_retry_count": 0             // persisted retry counter for Stage 6.5 step 7 (closes M4)
    }
  },
  "docs_path": "docs/harness/ship-<slug>/",  // ship uses "ship-" prefix to namespace artifacts separately from workflow's "docs/harness/<slug>/"
  "created_at": "<ISO8601>",
  "updated_at": "<ISO8601>"
}
```

**substep** tracks intra-stage progress for recovery. Valid values (exhaustive enum, grouped by stage — closes s1):

`null` — no substep active

**version_bump stage:**
- `"version_bump_pass1_done"` — version references detected, awaiting HARD-GATE
- `"version_bump_pass2_done"` — version files updated, stage complete

**git_ops stage — 6a (Commit) / 6b (Tag) / 6c (Push):**
- `"git_commit_pending"` — about to commit (staging may be incomplete)
- `"git_commit_done"` — commit created successfully
- `"git_tag_pending"` — about to create tag
- `"git_tag_done"` — tag created successfully
- `"git_push_pending"` — about to push
- `"git_branch_pushed"` — branch pushed, tag push pending

**git_ops stage — 6.5 (merge_to_base sub-stage):**
- `"merge_base_pending"` — Stage 6.5 entered. For Path B: pre_merge_sha captured in state.json, awaiting pre-merge HARD-GATE (step 2). For Path A: idempotency check (A.1) passed, awaiting protected-base gate (A.3). Resume from this substep is safe in both paths.
- `"merge_base_done"` — Path B only: local merge into base_branch succeeded, awaiting push HARD-GATE (step 5).
- `"merge_base_pushed"` — terminal state for Stage 6.5; covers ALL of: (a) Path B step 7 base_branch push completed, (b) Path A `gh pr create` succeeded (PR replaces direct push), (c) Path A "Skip Stage 6.5" chosen, (d) Path B step 2 HARD-GATE "Skip Stage 6.5" chosen, (e) Path B step 4 Non-FF "Skip Stage 6.5" chosen, (f) Path B step 7 push-rejection "Skip Stage 6.5" chosen, (g) entry-level Skip conditions (`state.branch == base_branch` OR `base_branch == null`). All paths converge on this substep before 6c-ii tag push. The name is push-centric for historical reasons; semantically it means "Stage 6.5 is done — proceed to tag push regardless of whether merge actually happened".

**git_ops stage — 6c-ii (Tag push) terminal:**
- `"git_push_done"` — both branch and tag pushed

---

## Stage DAG (Enforced Order)

```
[Q&A] → version_bump → changelog → build_verify → code_review → git_ops → gh_release
```

> **Note (8.4):** Stage 6.5 (`merge_to_base`) is a SUB-stage of `git_ops`, not a new top-level stage. It runs between 6c-i (branch push) and 6c-ii (tag push). The `current_stage` field continues to read `"git_ops"` throughout 6.5; intra-stage progress is tracked via `substep` (`merge_base_pending` / `merge_base_done` / `merge_base_pushed`).

Stages may be skipped (if not selected or not available), but order is always preserved. A stage may never run before its predecessor.

Rules:
- `has_git == false` → auto-skip `git_ops` and `gh_release`
- `has_gh == false` OR `has_gh_auth == false` → auto-skip `gh_release`
- `gh_release` requires `git_ops` to have run (tag must exist)

---

## Workflow Steps

### Step 1: Setup & Q&A

1. **Detect user language**, store as `user_lang`.
2. **Detect environment**: `has_git`, `has_gh`, `has_gh_auth`, `lang`, commands, current version, `base_branch`.
   - **base_branch detection** (only if `has_git == true`): `git rev-parse --verify main 2>/dev/null && echo "main" || (git rev-parse --verify master 2>/dev/null && echo "master" || echo "")`. If empty → ask user via AskUserQuestion: "Could not detect base branch (neither `main` nor `master` found). Enter your base branch name:" (free text input).
3. **Slugify** release version or task name: lowercase, hyphens, 50 chars max. Store as `<slug>`.
4. **Create directories:** `.harness/`, `docs/harness/ship-<slug>/`
5. **Ask: Release version** via AskUserQuestion (in `user_lang`):
   - header: "Version"
   - question: "Current version detected: `{current_version}`. What is the new release version?"
   - options:
     - "patch" / "Increment patch: {suggested_patch}"
     - "minor" / "Increment minor: {suggested_minor}"
     - "major" / "Increment major: {suggested_major}"
     - "Other" / "Enter custom version"
   - If detection failed → ask for both current and release version via free text.

   **Version format validation:** After collecting `release_version`, validate against `^[0-9]+\.[0-9]+\.[0-9]+([.-][a-zA-Z0-9._-]+)?$` (semver with optional pre-release/build). If validation fails → re-ask with: "Invalid version format. Use semantic versioning (e.g., `1.2.3`, `2.0.0-beta.1`)." Max 3 retries, then halt.

   Store as `release_version`.

6. **Ask: Pipeline preset** via AskUserQuestion (in `user_lang`):
   - header: "Pipeline"
   - question: "Select release pipeline stages:"
   - options:
     - "full" / "All stages: version bump + changelog + build/test + code review + git commit/tag/push + GitHub release"
     - "verify-only" / "Build & verify only (no git operations)"
     - "git-only" / "Git operations only: commit + tag + push (skips build/verify)"
     - "custom" / "Choose stages individually"

   **If has_git == false:** Remove git_ops and gh_release from all options. Inform user these stages are skipped.
   **If has_gh == false OR has_gh_auth == false:** Remove gh_release from all options. Inform user GitHub CLI is not available/authenticated.

   **If "custom":** Ask per-stage yes/no for each available stage in DAG order. Enforce: if `gh_release` is selected, `git_ops` must also be selected.

   Store selected stages as `stages_selected` array (ordered per DAG).

7. **Print setup summary** (in `user_lang`):
   ```
   [harness:ship] Release pipeline configured!
     Version  : {current_version} → {release_version}
     Stages   : {comma-separated selected stages}
     Language : {lang}
     Build    : {build_cmd or "none"}
     Test     : {test_cmd or "none"}
   ```

8. **Write `.harness/state.json`** (full schema above).
9. **Proceed through stages in DAG order.**

---

### Step 2: Stage — version_bump

*Skip if `version_bump` not in `stages_selected`.*

Update state.json: `current_stage → "version_bump"`, `substep → null`.

Print: `[harness:ship] Stage: Version Bump`

#### Pass 1 — Detect and Update Version References

1. Find all files containing the current version string:
   - `package.json`, `pyproject.toml`, `Cargo.toml`, `pom.xml`, `build.gradle(.kts)`, `*.csproj`
   - `.claude-plugin/plugin.json` (top-level `$.version`) and `.claude-plugin/marketplace.json` (`$.metadata.version` and `$.plugins[*].version` for each plugin entry). Use JSON parsing to identify exact key paths; the `$.foo` notation is a readability convention, not strict JSONPath. If a file is missing, treat as not-detected and continue. If JSON parse fails in Pass 1, **still include the file in the detection list** with key-path metadata empty and a `parse_failed=true` flag, and display it to the user as `⚠ JSON parse error — Pass 2 will prompt`. Pass 2 step 2 then re-parses authoritatively and routes to the skip/abort AskUserQuestion — centralizing parse-error handling in Pass 2 keeps Pass 1 listing-only and avoids duplicate prompts.
   - Also search: `git tag --list | grep {current_version}` (do NOT apply — record only)
   - Also grep source files for version constants (e.g., `VERSION = "..."`, `const VERSION`)
2. **List all found locations** to user. Update state.json: `substep → "version_bump_pass1_done"`.
3. Print found locations (in `user_lang`).

#### HARD-GATE — Pass 1 Confirm

<HARD-GATE>
Ask via AskUserQuestion (in `user_lang`):
- header: "Version Bump"
- question: "Found {N} version references. Proceed to update all from `{current_version}` to `{release_version}`?"
- options:
  - "Proceed" / "Update all listed files"
  - "Skip" / "Skip version bump stage entirely"
  - "Stop" / "Halt release pipeline"
Only "Proceed" advances.
</HARD-GATE>

If "Skip": mark stage skipped, move to next stage.
If "Stop": halt.

#### Pass 2 — Apply Updates

Update all detected version references. For each file, dispatch by file kind:

**For `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`** (JSON-aware path):

1. Detect the original line-ending convention by inspecting raw bytes (e.g., `b"\r\n" in raw`), the UTF-8 BOM prefix (`b"\xef\xbb\xbf"` at file start), and the original trailing-newline state. Remember all three. This is critical because `.claude-plugin/*.json` files may use CRLF on Windows-authored repos and may have a BOM; serializing back as plain LF without BOM would create noise diffs touching every line or strip the BOM silently.
2. Parse the file as JSON (UTF-8). On parse failure, do NOT fall through to string replace — instead emit a warning (`⚠ Invalid JSON at <path> — cannot determine version key path`) and ask the user via AskUserQuestion (`user_lang`) to "skip this file" or "abort stage". On "skip", exclude the file from Pass 2 and proceed with the remaining files; on "abort", halt the stage (state.json `substep` retains its current value for resume).
3. For each detected JSON key path identified in Pass 1 (e.g., `$.version`, `$.metadata.version`, `$.plugins[i].version`):
   - If the key path does not exist (e.g., a `plugins[i]` entry without a `version` field), silently skip — this is a normal optional-field case, no warning required.
   - Else if the current value at that key path already equals `{release_version}`, silently skip — idempotent re-run case, no warning required.
   - Else if the current value at that key path equals `{current_version}`, set it to `{release_version}`.
   - Else (current value differs from both `{current_version}` and `{release_version}`), leave it untouched and log a warning (`⚠ Version drift at <path>#<key_path>: expected {current_version}, found <value>`).
4. Serialize the JSON preserving key order, indentation (match the original — typically 2 spaces), AND the original line-ending convention (CRLF vs LF), BOM prefix, and trailing-newline state detected in step 1. Do NOT use `json.dumps` defaults blindly; post-process the serialized string (and prepend the BOM bytes) to restore CRLF, BOM, and trailing-newline if the original used them.
5. Write back, then re-parse the written file to confirm JSON validity, and re-read to confirm the new version string is present at the same key path.

**Important regression-blocker**: Do NOT apply naive string replace to `.claude-plugin/*.json` files. JSON path matching ensures that other fields (e.g., `description: "Initial 8.2.0 release notes…"`) containing the same version string by coincidence are NOT modified.

**For all other detected files** (standard package manifests, source constants):

- Read the file, replace `{current_version}` with `{release_version}` (string replace).
- Write the file back.
- Verify the replacement succeeded (re-read and confirm).

Update state.json: `substep → "version_bump_pass2_done"`, `stage_results.version_bump_files → [list of modified file paths]` (paths only — JSON key-path metadata stays in-memory only for backward compatibility).

Print: `  ✓ Version updated in {N} files`

Update state.json: `stage_results.version_bump → "done"`, `substep → null`.
Proceed to next stage.

---

### Step 3: Stage — changelog

*Skip if `changelog` not in `stages_selected`.*

Update state.json: `current_stage → "changelog"`.

Print: `[harness:ship] Stage: Changelog`

1. **Parse git log** for conventional commits since last tag:
   ```bash
   git log {last_tag}..HEAD --pretty=format:"%h %s" --no-merges
   ```
   If no previous tag: `git log --pretty=format:"%h %s" --no-merges`

2. **Categorize commits** by Conventional Commits spec:
   - `feat:` → Features
   - `fix:` → Bug Fixes
   - `docs:` → Documentation
   - `chore:` / `build:` / `ci:` → Maintenance
   - `BREAKING CHANGE` → Breaking Changes
   - Other → Uncategorized

3. **Draft changelog entry:**
   ```markdown
   ## [{release_version}] — {date}

   ### Breaking Changes
   - {breaking change descriptions}

   ### Features
   - {feat commits}

   ### Bug Fixes
   - {fix commits}

   ### Maintenance
   - {chore/build/ci commits}
   ```

4. **Write draft** to `.harness/changelog_draft.md`.

#### HARD-GATE — Changelog Edit Gate

<HARD-GATE>
Show draft changelog to user. Ask via AskUserQuestion (in `user_lang`):
- header: "Changelog"
- question: "Changelog draft generated from {N} commits. Review and approve."
- options:
  - "Approve" / "Use this changelog as-is"
  - "Edit" / "I will edit .harness/changelog_draft.md, then re-confirm"
  - "Skip" / "Skip changelog update"
  - "Stop" / "Halt pipeline"

If "Edit": wait for user to edit file, then re-present this gate.
Only "Approve" advances.
</HARD-GATE>

5. **Prepend approved changelog** to `CHANGELOG.md` (create if not exists).

Print: `  ✓ Changelog updated`
Update state.json: `stage_results.changelog → "done"`.
Proceed to next stage.

---

### Step 4: Stage — build_verify

*Skip if `build_verify` not in `stages_selected`.*

Update state.json: `current_stage → "build_verify"`.

Print: `[harness:ship] Stage: Build & Verify`

1. **Generate changes list:** Run `git diff {base_branch}...HEAD --name-only` (if `base_branch` known) or `git diff HEAD --name-only` (if no base branch). Write output to `docs/harness/ship-<slug>/changes.md` with one file path per line. If no changes detected, write "No changed files detected." to the file.
2. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/ship/build_verify.md`
3. Fill variables: `{build_cmd}` (or "SKIP" if null), `{test_cmd}` (or "SKIP"), `{lint_cmd}` (or "SKIP"), `{type_check_cmd}` (or "SKIP"), `{release_version}`, `{lang}`, `{changes_md_path}` = `docs/harness/ship-<slug>/changes.md`, `{verify_report_path}` = `docs/harness/ship-<slug>/verify_report.md`, `{todo_blocking}` = false (ship treats TODO/FIXME as warnings only — not release-blocking).
4. **Dispatch sub-agent.**
5. Parse return — first line:
   - Contains `"PASS"` → stage passes
   - Contains `"FAIL"` → stage fails
6. Print result.

#### If FAIL:

Ask via AskUserQuestion (in `user_lang`):
- header: "Build Verify"
- question: "Build/test verification FAILED. [{first line}]"
- options:
  - "Fix and retry" / "Fix the issue manually, then retry this stage"
  - "Continue anyway" / "Proceed despite failures (not recommended)"
  - "Stop" / "Halt release pipeline"

If "Fix and retry": re-run this stage (loop back to top of Step 4).
If "Continue anyway": warn user in status, mark stage WARN.
If "Stop": halt.

Update state.json: `stage_results.build_verify → "pass" | "fail" | "warn"`.
Proceed to next stage.

---

### Step 5: Stage — code_review

*Skip if `code_review` not in `stages_selected`.*

Update state.json: `current_stage → "code_review"`.

Print: `[harness:ship] Stage: Code Review Summary`

1. Read `base_branch` from state.json (detected in Step 1 Setup).
2. Read template: `{CLAUDE_PLUGIN_ROOT}/templates/ship/code_review_summary.md`
3. Fill variables: `{release_version}`, `{release_branch}` = current branch, `{base_branch}`, `{repo_path}`, `{lang}`, `{output_path}` = `docs/harness/ship-<slug>/code_review.md`.
4. **Dispatch sub-agent.**
5. Parse return — first line:
   - `"PASS"` → green
   - `"WARN"` → yellow, present to user
   - `"FAIL"` → red

#### If FAIL or WARN:

Present result to user. Ask via AskUserQuestion (in `user_lang`):
- header: "Code Review"
- question: "[result line]. Issues found in code review summary."
- options:
  - "Continue" / "Accept and proceed (issues noted)"
  - "Fix and retry" / "Fix issues, then retry code review"
  - "Stop" / "Halt pipeline"

Update state.json: `stage_results.code_review → "pass" | "warn" | "fail"`.
Proceed to next stage.

---

### Step 6: Stage — git_ops

*Skip if `git_ops` not in `stages_selected` OR `has_git == false`.*

Update state.json: `current_stage → "git_ops"`, `substep → null`.

Print: `[harness:ship] Stage: Git Operations`

Each git operation has its own independent HARD-GATE with "irreversible" warning.

#### 6a: Commit

Update state.json: `substep → "git_commit_pending"`.

**Pre-staging safety scan:**
1. Run `git status --short` to list all changed/untracked files.
2. Check for sensitive file patterns: `.env*`, `*secret*`, `*credential*`, `*token*`, `*.pem`, `*.key`.
3. Check if `.harness/` directory files appear in the list (not in `.gitignore`).
4. If sensitive files or `.harness/` files detected → show warning list to user before the HARD-GATE.

**Staging strategy:** Do NOT use `git add -A`. Instead, stage only release-relevant files:
- Files modified by version_bump stage (tracked in `stage_results.version_bump_files` if available)
- `CHANGELOG.md` (if changelog stage ran)
- If neither is available, use `git add -u` (tracked files only, no untracked).
- If user explicitly requests adding untracked files → require confirmation per file.

<HARD-GATE>
Show uncommitted changes summary (`git diff --cached --stat` after staging). Ask via AskUserQuestion (in `user_lang`):
- header: "Git Commit"
- question: "IRREVERSIBLE: This will create a commit. Staged files: {N}. Message: `chore: release {release_version}`"
- options:
  - "Commit" / "Create commit with release message"
  - "Edit message" / "Enter a custom commit message"
  - "Skip commit" / "Skip this git operation"
  - "Stop" / "Halt pipeline"
Only "Commit" or "Edit message" advances.
</HARD-GATE>

**If "Edit message":** User provides custom message. **Validate**: reject if message contains `"`, `` ` ``, `$(`, `&&`, `||`, `;`, or newlines. Re-ask with: "Commit message contains shell-unsafe characters. Please use only alphanumeric characters, spaces, hyphens, colons, and parentheses."

**Commit execution:** Write the commit message to `.harness/commit_msg.txt`, then execute:
```bash
git commit -F .harness/commit_msg.txt
```
Delete `.harness/commit_msg.txt` after commit.

If fails → delete `.harness/commit_msg.txt` if it exists, then ask "Retry / Manual fix / Stop".
- **Retry**: re-run staging + commit from the start of 6a.
- **Manual fix**: keep `substep → "git_commit_pending"`, user fixes manually and re-invokes.
- **Stop**: delete `.harness/commit_msg.txt` if it exists, halt.

Update state.json: `substep → "git_commit_done"`.

#### 6b: Tag

Update state.json: `substep → "git_tag_pending"`.

**Recovery check:** If resuming from `git_tag_pending`, run `git tag -l {tag_name}` first. If the tag already exists → print "Tag already exists, skipping creation." → update substep → `"git_tag_done"` and proceed to 6c.

<HARD-GATE>
Ask via AskUserQuestion (in `user_lang`):
- header: "Git Tag"
- question: "IRREVERSIBLE: This will create tag `{tag_name}`. Tag name: `v{release_version}` (or custom)."
- options:
  - "Tag" / "Create tag `v{release_version}`"
  - "Custom tag" / "Enter a different tag name"
  - "Skip tag" / "Skip tagging"
  - "Stop" / "Halt pipeline"
Only "Tag" or "Custom tag" advances.
</HARD-GATE>

**If "Custom tag":** User provides custom tag name. **Validate**:
- Must match `^v?[0-9a-zA-Z][0-9a-zA-Z._-]{0,198}$` (max 200 chars).
- Must NOT contain: spaces, shell metacharacters (`"`, `` ` ``, `$`, `&`, `|`, `;`, `\`), or start with `-`.
- Must NOT contain consecutive dots (`..`) or end with `.` or `-`.
- Re-ask on validation failure (max 3 retries, then "Skip tag" or "Stop").

**Tag execution:** Write tag message (`Release {release_version}`) to `.harness/tag_msg.txt`, then execute:
```bash
git tag -a {tag_name} -F .harness/tag_msg.txt
```
Delete `.harness/tag_msg.txt` after tag creation.

Update state.json: `tag_name → {tag_name}`, `substep → "git_tag_done"`.

#### 6c: Push

Update state.json: `substep → "git_push_pending"`.

**Pre-check**: Verify remote exists: `git remote -v 2>/dev/null`
- If no remote → warn user, skip push.

**Input validation:** Verify `branch` matches `^[a-zA-Z0-9/_.-]+$` and `tag_name` (if not null) matches `^(v[0-9a-zA-Z][0-9a-zA-Z._-]{0,252}|[0-9a-zA-Z][0-9a-zA-Z._-]{0,253})$` (strict 254-char hard cap regardless of optional `v` prefix; alternation prevents the `v?` + 254 trailing case from inflating to 255 chars). If either fails → print error, halt (state corruption).

**Recovery check:** If resuming from `git_push_pending` or `git_branch_pushed`:
- Check if branch already pushed: `git log origin/{branch}..{branch} --oneline` — if empty, branch is up-to-date → update `substep → "git_branch_pushed"` and **route to Stage 6.5 entry** (NOT directly to tag push). Stage 6.5 must run between branch push and tag push so the tag is reachable from `base_branch`; bypassing it would re-introduce the develop→main lag this stage was added to fix. Stage 6.5's own Skip-condition evaluation at entry handles the `state.branch == base_branch` and `base_branch == null` cases that legitimately bypass the merge.
- Check if tag already pushed: `git ls-remote origin refs/tags/{tag_name}` — if non-empty, tag exists on remote → skip tag push.
- Skip already-completed operations and update substep accordingly.

> **Note on Recovery check vs jump table interaction (closes M1)**: this Recovery check runs at Step 6c entry. The jump table at the top of this file routes `substep == "git_branch_pushed"` to "Stage 6.5 entry" — that mapping is consistent with the bullet above (which also routes to Stage 6.5 entry). The earlier 8.4 draft of this Recovery check routed `git_branch_pushed` directly to tag push, which conflicted with the jump table; that direct-to-tag route has been removed.

<HARD-GATE>
Ask via AskUserQuestion (in `user_lang`):
- header: "Git Push"
- question: "IRREVERSIBLE: This will push branch `{branch}` to remote `{remote}`, then run Stage 6.5 (merge_to_base — merges `{branch}` into `{base_branch}` and pushes `{base_branch}` UNLESS Stage 6.5 skip conditions match: `{branch} == {base_branch}` OR `{base_branch}` is null), then push tag `{tag_name}`. Branch and tag operations cannot be undone without force-push; Stage 6.5 has its own per-step HARD-GATEs with rollback documentation that includes the concrete SHA (captured at Stage 6.5 step 1)."
- options:
  - "Push" / "Push branch, run Stage 6.5, push tag"
  - "Skip push" / "Skip all push operations (branch, base_branch, tag)"
  - "Stop" / "Halt pipeline"
Only "Push" advances.
</HARD-GATE>

**Push execution (two separate operations):**

**6c-i: Push branch:**
Execute: `git push origin {branch}`

If branch push fails → ask via AskUserQuestion (in `user_lang`):
- header: "Branch Push Failed"
- question: "Branch push failed: {error summary}."
- options:
  - "Retry" / "Retry branch push"
  - "Manual" / "I will push branch manually — mark as done"
  - "Skip" / "Skip branch push, continue downstream"
  - "Stop" / "Halt pipeline"
If "Manual" → update substep → `"git_branch_pushed"`, **proceed to Stage 6.5 entry** (NOT directly to tag push — Stage 6.5 must run between branch push and tag push so the tag is reachable from `base_branch`; Stage 6.5's own entry-level Skip-condition evaluation handles cases where the merge is unnecessary).
If "Skip" → update substep → `"git_branch_pushed"`, **proceed to Stage 6.5 entry** (same rationale as Manual; if the user wants to bypass merge_to_base entirely they can choose "Skip Stage 6.5" inside Stage 6.5's own gates).

On success → update substep → `"git_branch_pushed"`. Proceed to Stage 6.5 entry.

#### 6.5: Stage — merge_to_base

> Introduced in v8.4.0 (N2). Closes m14 — header version tag removed to avoid stale `(NEW in 8.4 / N2)` text in future versions; refer to CHANGELOG / ROADMAP for version history.

This sub-stage merges the current release branch into `base_branch` BEFORE tag push, so the tag points to a commit reachable from `base_branch`. Closes the develop→main lag that occurred in 8.1.0/8.2.0/8.3.0 releases.

**Variable conventions (Stage 6.5 scope):**
- `release_branch` ≡ `state.branch` — the branch ship was invoked on (single source of truth — both names refer to the persisted state). **This is the same value that 6c-i refers to as `{branch}`** (e.g., `git push origin {branch}` at line 598); the rename to `release_branch` inside Stage 6.5 is purely for clarity when the prose discusses both branches simultaneously, not a different variable.
- `base_branch` ≡ `state.base_branch` — auto-detected (or user-supplied) merge target (e.g., `main`).
- `current_branch` is used ONLY inside the entry guard below (live `git` query result, compared against `state.branch` to detect mid-session branch switches).

**i18n policy (applies to all AskUserQuestion gates in this section):** `header`, `question`, and option `description` strings translate to `{user_lang}` per [Communicate in user's language] policy. Option `label` strings (the canonical action keys quoted below — e.g., `"Proceed"`, `"Skip Stage 6.5"`, `"Retry"`) stay English so downstream substep transitions can match on stable identifiers.

**Skip conditions** (evaluated at entry — both bypass Stage 6.5 entirely and proceed directly to 6c-ii tag push):
- `state.branch == base_branch` (already on base — nothing to merge). **Comparison is exact-string** (git refs are case-sensitive on Linux/macOS, and even on case-insensitive filesystems the recorded value is the canonical form returned by `git rev-parse --abbrev-ref` at Setup, so `Main` vs `main` would only diverge if the user manually overrode the value with mismatched casing). If you suspect the user typed a divergent-case branch name during Setup's `base_branch` input prompt, an additional defensive check is `git rev-parse refs/heads/{state.branch}` vs `git rev-parse refs/heads/{base_branch}` — equal SHAs imply the same branch tip regardless of name casing (closes s2). The string-equality check below is the primary; the SHA-equality check is optional defensive.
- `base_branch == null` (auto-detect failed at Setup, no user-supplied value)

**On either skip-condition match**: set `substep → "merge_base_pushed"` (so the jump table maps a resumed session consistently to 6c-ii rather than re-entering Stage 6.5), keep `current_stage == "git_ops"` unchanged, and proceed to 6c-ii. This makes the entry-skip path symmetric with Path A and the HARD-GATE Skip path (both of which also land on `merge_base_pushed`).

If neither skip condition matches, proceed below.

**Entry guard — branch re-detection** (CM7):

```bash
git rev-parse --abbrev-ref HEAD
```

Compare result (`current_branch`) to `state.branch`. On mismatch → halt with error: `Current branch changed mid-session ({state.branch} → {current_branch}). Switch back to {state.branch} and re-invoke /ship, OR Restart from Stage 1.`

**Halt behavior** (closes M10): `state.json` is preserved as-is — `substep` retains its current value (typically `"git_branch_pushed"` since the entry guard runs before any 6.5-internal substep transition; could be `"merge_base_pending"` or `"merge_base_done"` if the session is being resumed mid-6.5). When the user later switches back to `{state.branch}` and re-invokes /ship, the jump table re-routes to Stage 6.5 entry (or to step 2 / step 5 if a 6.5-internal substep is active) and **this entry guard is re-executed**, so the branch-equality check is re-evaluated; if the user is now on the correct branch the guard passes and execution continues. The guard is therefore safe to re-run any number of times.

**Branch protection pre-check** (CC5):

Before running the API call, **re-validate `{base_branch}`** against the strict pattern `^[a-zA-Z0-9/_.-]+$` (the same pattern used for `branch` at line 577). The original `base_branch` value comes from auto-detection (`main`/`master`) or from a free-text user input at Step 1, and the user-input path does not enforce the pattern at the source. Re-validating here closes a URL-injection vector: a value containing `..`, spaces, `?`, `#`, or path separators outside the allowed set could traverse or rewrite the API request URL. On pattern mismatch → halt with error: `Invalid base_branch '{base_branch}' — must match ^[a-zA-Z0-9/_.-]+$. Restart /ship and provide a valid branch name.` (closes m1 / Sec N3)

```bash
gh api repos/:owner/:repo/branches/{base_branch}/protection
```

The `:owner/:repo` literal is a `gh` CLI placeholder — `gh api` resolves it to the current repository's `OWNER/REPO` automatically from the configured git remote, equivalent to passing `--repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)"`. Do NOT replace it with literal owner/repo strings here unless you intend to target a different repository.

(stderr captured separately — do NOT use `2>/dev/null` so the agent can inspect HTTP status for branching below.)

Conditions for skipping the API call entirely (treat as `unknown`):
- `state.has_gh == false` (gh not installed)
- `state.has_gh_auth == false` (gh not authenticated)

Exit code interpretation:
- **exit 0** → protection rules are configured for `{base_branch}`. Treat as **protected** → Path A.
- **exit ≠ 0 with HTTP 404 in error output** → no protection configured (this is the normal unprotected branch case). Treat as **unprotected** → Path B (Standard merge path).
- **exit ≠ 0 with HTTP 403 / 401 in error output** → permission denied (token lacks `repo` scope or branch is in a private repo not accessible). Treat as **unknown** → Path B (Standard merge path; rejection — if any — handled at step 7).
- **exit ≠ 0 with HTTP 5xx / network error** → transient failure. Treat as **unknown** → Path B.
- **API call skipped (gh missing/unauthenticated)** → **unknown** → Path B.

All `unknown` and `unprotected` cases converge on Path B. Path B step 7's push-rejection 5-way gate is the safety net — if `{base_branch}` is actually protected but the API check missed it, push will be rejected and the user can choose Create PR / Manual / Skip / Stop / Retry from there.

**A. Protected branch path** — direct push known to be rejected; do not attempt local merge:

**A.1. Pre-check existing PR (idempotency guard, closes M2)**: before showing the gate, run:
```bash
gh pr list --base {base_branch} --head {release_branch} --state open --json url,number --jq '.[0]'
```
- If output is non-empty (an open PR for this base/head pair already exists from a prior interrupted session) → inform the user `[ship] An open PR for {release_branch} → {base_branch} already exists: <url>. Reusing it.`, set `state.stage_results.merge_to_base.pre_merge_sha = null` (Path A does not capture a SHA — closes M3), set `state.stage_results.merge_to_base.path_a_pr_url = "<url>"`, transition `substep → "merge_base_pushed"`, run `git checkout {release_branch}` to ensure HEAD context for 6c-ii (closes M11; halt on checkout failure with explicit error), and continue to 6c-ii.
- If output is empty → proceed to A.2.

**A.2. Path A entry transition**: set `substep → "merge_base_pending"` BEFORE displaying the gate (closes M2 — without this, an interrupted session resuming at `git_branch_pushed` would re-enter Stage 6.5 from scratch and the `gh pr list` pre-check above is what makes that re-entry safe; setting `merge_base_pending` makes resume jump to step 2 instead, where this very same Path A logic runs again, gh-list-guarded). Also set `state.stage_results.merge_to_base.pre_merge_sha = null` explicitly so downstream consumers (Rollback documentation, future readers of state.json) can distinguish Path A (no local merge → no rollback SHA) from Path B (SHA captured) — closes M3.

**A.3. AskUserQuestion**:
```
header: "Protected Base"     (translate to user_lang)
question: "Base branch `{base_branch}` is protected — direct push will be rejected. Open a PR instead?"
                              (translate to user_lang)
options:                      (translate description to user_lang; keep label English)
  - "Create PR" / "Open PR via gh pr create --base {base_branch} --head {release_branch}"
  - "Skip Stage 6.5" / "Skip merge — base_branch will lag this release. Tag still pushes."
  - "Stop" / "Halt for manual intervention"
```
- **Create PR** → execute `gh pr create --base {base_branch} --head {release_branch} --title "Release {release_version}"`. On success: parse the printed PR URL, store `state.stage_results.merge_to_base.path_a_pr_url = "<url>"`, set `substep → "merge_base_pushed"` (treating PR creation as the "push" equivalent — the tag still pushes to release_branch lineage at 6c-ii), execute `git checkout {release_branch}` to guarantee HEAD context for 6c-ii (closes M11; halt on checkout failure), continue to 6c-ii. On failure: if stderr indicates "a pull request for branch ... already exists" (race condition where a PR was created between A.1's check and now) → re-run A.1's `gh pr list` to fetch the URL and proceed via the "existing PR" branch above; otherwise → re-display this gate (the user can choose Skip or Stop to escape).
- **Skip Stage 6.5** → `substep → "merge_base_pushed"`, run `git checkout {release_branch}` (defensive — Path A has not changed branches but ensures HEAD context for 6c-ii regardless of any prior state; closes M11; halt on failure), warn user that base_branch will lag this release, continue to 6c-ii.
- **Stop** → halt session (state.json preserved — `substep == "merge_base_pending"` enables resume from A.1's idempotency check).

**B. Standard merge path** (no detected protection or status unknown):

1. **Capture pre_merge_sha FIRST (before HARD-GATE display)** (B6 — required so the HARD-GATE rollback message can interpolate the actual SHA, not an unresolved placeholder). **Capture the `base_branch` HEAD sha regardless of which branch is currently checked out:**
   ```bash
   pre_merge_sha=$(git rev-parse --verify refs/heads/{base_branch}^{{commit}})
   ```
   - Use `refs/heads/{base_branch}` to disambiguate against tags or remote-tracking refs of the same name.
   - The `^{{commit}}` peel ensures a commit object is resolved (not a tag-to-commit indirection).
   - **Verify both the exit code (must be 0) and the output (must be a 40-char hex)** before proceeding. On failure (e.g., `base_branch` does not exist locally) → halt with error and instruct user to fetch the branch (`git fetch origin {base_branch}:{base_branch}`) and re-invoke /ship.
   - This MUST resolve to the base_branch's tip — if it resolved to the release_branch HEAD instead (e.g., naive `git rev-parse HEAD` while still on release_branch), the rollback `git reset --hard {pre_merge_sha}` on base_branch would JUMP base_branch FORWARD to the release HEAD instead of reverting it, which is the opposite of recovery.

   Store in state.json: `state.stage_results.merge_to_base.pre_merge_sha = "{pre_merge_sha}"`. Then set `substep → "merge_base_pending"`.

2. **HARD-GATE (CM9)** via AskUserQuestion:
   ```
   header: "Merge to Base"     (translate to user_lang)
   question: "About to merge `{release_branch}` → `{base_branch}` (local merge — irreversible without `git reset --hard {pre_merge_sha}` on `{base_branch}` to undo, where `{pre_merge_sha}` is the captured base_branch tip from step 1). Proceed?"
                                (translate to user_lang)
   options:                     (translate description to user_lang; keep label English)
     - "Proceed" / "Run git merge"
     - "Skip Stage 6.5" / "Skip merge — base_branch will lag this release. Tag still pushes."
     - "Stop" / "Halt for manual intervention"
   ```
   - Skip → `substep → "merge_base_pushed"` + warn `[ship] ⚠ base_branch ({base_branch}) will not contain release commits — tag will not be reachable from {base_branch}.` Continue to 6c-ii tag push.
   - Stop → halt session.

3. **Switch to base_branch and attempt FF merge:**
   ```bash
   git checkout {base_branch}
   git merge --ff-only {release_branch}
   ```
   - **Success → SKIP step 4 entirely, proceed directly to step 5.** (Step 4 is the Non-FF resolution gate; it must NOT be displayed when FF merge already succeeded.)
   - Non-FF (the `git merge --ff-only` command fails because `{base_branch}` has commits not present in `{release_branch}`) → proceed to step 4.

4. **Non-FF resolution** (entered ONLY when step 3's `git merge --ff-only` failed; if step 3 succeeded the agent must skip this entire step) via AskUserQuestion:
   ```
   header: "Non-FF Merge"       (translate to user_lang)
   question: "FF merge not possible — `{base_branch}` has commits not in `{release_branch}`. Choose merge strategy:"
                                 (translate to user_lang)
   options:                      (translate description to user_lang; keep label English)
     - "no-ff merge" / "Create explicit merge commit (preserves both histories)"
     - "rebase-then-ff" / "Rebase {release_branch} onto {base_branch}, then FF (rewrites release history)"
     - "Skip Stage 6.5" / "Abort merge, base_branch lags release"
     - "Stop" / "Halt for manual intervention"
   ```
   - **no-ff merge** → `git merge --no-ff {release_branch} -m "Merge release {release_version}"`. On conflict → execute `git merge --abort` (revert the in-progress merge so the working tree returns to clean state) then `git checkout {release_branch}` (HEAD is currently on `{base_branch}` from step 3 — return to release_branch so subsequent ad-hoc git commands by the user operate on the expected branch; halt on checkout failure with explicit error directing the user to `git checkout {release_branch}` manually) and halt with recovery instructions: "no-ff merge had conflicts. Resolve manually (e.g., merge `{base_branch}` into `{release_branch}` first, fix conflicts on `{release_branch}`, then re-invoke /ship from Stage 6.5; substep == `merge_base_pending` triggers re-execution from step 2 HARD-GATE)." `substep` retains `merge_base_pending` for resume. On success → HEAD remains on `{base_branch}` (from step 3's checkout, with the new no-ff merge commit on top), proceed to step 5 (closes NF3).
   - **rebase-then-ff** → AskUserQuestion sub-gate. **Note on current branch state**: at the moment this sub-gate is displayed, no git command has yet been executed for the rebase-then-ff path, so HEAD is still on `{base_branch}` (from step 3's checkout). Cancel preserves that state; Yes proceeds to the rebase pipeline below.
     ```
     header: "Confirm Rebase"   (translate to user_lang)
     question: "Rebase rewrites `{release_branch}` history. Because step 6c-i already pushed `{release_branch}` to origin (substep == git_branch_pushed at Stage 6.5 entry), a force-push of `{release_branch}` is required after the rebase to keep the remote in sync — otherwise the tag created at 6c-ii would point to a local-only rebase commit that does not exist on the remote. Continue?"
                                (translate to user_lang)
     options:                   (translate description to user_lang; keep label English)
       - "Yes" / "Run rebase, FF merge, then force-push release_branch"
       - "Cancel" / "Return to merge strategy selection"
     ```
     On Cancel → return to step 4 options (HEAD remains on `{base_branch}` from step 3's checkout — no cleanup needed). On Yes, execute the rebase pipeline as separate commands so the agent can identify which step failed and recover precisely:
     1. `git checkout {release_branch}` — switch to release branch for rebase. On failure → halt with error (HEAD still on `{base_branch}`).
     2. `git rebase {base_branch}` — rebase release_branch onto base_branch. On rebase conflict → execute `git rebase --abort` + `git checkout {release_branch}` (to ensure HEAD is on release_branch; `--abort` typically restores it but verify) + halt with recovery instructions: "Rebase aborted. Resolve conflicts manually on `{release_branch}` against `{base_branch}`, then re-invoke /ship from Stage 6.5 (substep == `merge_base_pending`)." `substep` retains `merge_base_pending` for resume.
     3. `git checkout {base_branch}` — switch back to base_branch for FF merge. On failure → halt with error and instruct user to manually `git checkout {base_branch}`.
     4. `git merge --ff-only {release_branch}` — should now succeed since release_branch was rebased onto base_branch. On failure (extremely unusual after a clean rebase) → halt with error.
     5. **Force-push release_branch to remote (REQUIRED — closes C3 tag-integrity gap)**: `git push --force-with-lease origin {release_branch}`. The `--force-with-lease` variant refuses to overwrite the remote if it has been updated by another party since the last fetch — safer than plain `--force`. On rejection (lease check failed → another commit was pushed to remote since 6c-i) → halt with error: "Remote `{release_branch}` was updated externally between 6c-i and Stage 6.5. Investigate the foreign commit (`git fetch origin {release_branch} && git log {release_branch}..origin/{release_branch}`), reconcile manually, then re-invoke /ship from Stage 6.5." On other failure → halt. On success → at this point HEAD is on `{base_branch}` (from rebase pipeline sub-step 3) and the FF merge from sub-step 4 has already populated base_branch with the rebased release commits, so the OUTER Stage 6.5 step 5 (post-merge HARD-GATE / Push Base) is the next logical action: **proceed to OUTER step 5** (do NOT re-execute this rebase-pipeline list — the OUTER step 5 sets `substep → "merge_base_done"` and asks the user to confirm pushing base_branch to remote; the rebase-then-ff path therefore lands at the same post-merge gate as the no-ff and FF paths). Closes NF2.
   - **Skip Stage 6.5** → `git checkout {release_branch}` (return to release branch — HEAD is currently on `{base_branch}` from step 3; halt with explicit error if checkout fails so the user can manually correct branch state before any tag operation runs at 6c-ii). Then issue the same skip-warn as step 2 HARD-GATE Skip, set `substep → "merge_base_pushed"`, continue to 6c-ii.
   - **Stop** → `git checkout {release_branch}` (return to release branch; halt with explicit error if checkout fails, instructing the user to run `git checkout {release_branch}` manually before any further /ship invocation), then halt session. `substep` retains `merge_base_pending` for resume.

5. **substep → `merge_base_done`**. **HARD-GATE** via AskUserQuestion:
   ```
   header: "Push Base"          (translate to user_lang)
   question: "Local merge succeeded. About to push `{base_branch}` to remote. Proceed?"
                                 (translate to user_lang)
   options:                      (translate description to user_lang; keep label English)
     - "Push" / "Run git push origin {base_branch}"
     - "Stop" / "Halt — base_branch updated locally only. Run `git push origin {base_branch}` manually later."
   ```

6. **Push base_branch**:
   ```bash
   git push origin {base_branch}
   ```

7. **Push outcome handling**:
   - Success → `substep → "merge_base_pushed"`. `git checkout {release_branch}` (return to release branch — tag push in 6c-ii operates on release_branch). Proceed to 6c-ii.
   - Rejection (branch protection or other) → AskUserQuestion (5-way, mirroring 6c-i pattern + new "Create PR" option):
     ```
     header: "Push Rejected"     (translate to user_lang)
     question: "Push to {base_branch} rejected. Reason: {git error message}. Choose:"
                                  (translate to user_lang)
     options:                     (translate description to user_lang; keep label English)
       - "Retry" / "Try push again (network or transient)"
       - "Manual" / "I'll push manually — mark as done"
       - "Create PR" / "Open PR via gh: gh pr create --base {base_branch} --head {release_branch}"
       - "Skip Stage 6.5" / "Reset local merge, base_branch lags release"
       - "Stop" / "Halt for manual intervention"
     ```
     - **Retry** → re-run step 6. Track a `retry_count` **persisted in state.json at `state.stage_results.merge_to_base.push_retry_count`** (closes M4 / DX #8 / Sec N1 — without persistence, a Stop-then-resume would reset the counter to 0 and bypass the cap, allowing unbounded retries across sessions). The counter is initialized to 0 the first time this gate is displayed for the current Stage 6.5 attempt, read from state.json on every gate display (so resumed sessions see the cumulative count), and incremented and re-persisted on every Retry click before re-running step 6. When `push_retry_count >= 2`, on the next gate display **disable the Retry option** (omit it from `options`) and the user must choose Manual / Create PR / Skip / Stop. Rationale: 2 transient failures in a row strongly signal a non-transient cause (auth, protection, etc.); forcing a different choice prevents infinite retry loops, and persistence ensures the cap survives Stop/Resume cycles. Reset to 0 only when Stage 6.5 transitions to `merge_base_pushed` (i.e., this attempt is done) or when the user explicitly Restarts /ship from Stage 1.
     - **Manual** → `substep → "merge_base_pushed"`, `git checkout {release_branch}`, continue to 6c-ii.
     - **Create PR** → execute `gh pr create --base {base_branch} --head {release_branch} --title "Release {release_version}"`. On success: parse PR URL, store `state.stage_results.merge_to_base.path_a_pr_url = "<url>"` (reuses Path A's field even though we are on Path B — this is a deliberate cross-path field reuse since both paths converge on PR-as-substitute-for-direct-push semantics), `substep → "merge_base_pushed"`, `git checkout {release_branch}`, continue to 6c-ii. On failure: if stderr indicates "a pull request for branch ... already exists" (race condition: a PR was created externally between gate display and now — same idempotency case Path A.A.3 handles) → run `gh pr list --base {base_branch} --head {release_branch} --state open --json url --jq '.[0].url'` to fetch the existing URL, store it in `path_a_pr_url`, set `substep → "merge_base_pushed"`, `git checkout {release_branch}`, continue to 6c-ii (closes NF5). For any other failure → return to gate.
     - **Skip Stage 6.5** → rollback the local merge by executing the explicit chain `git checkout {base_branch} && git reset --hard {pre_merge_sha} && git checkout {release_branch}` (do NOT issue `git reset --hard` without an explicit `git checkout {base_branch}` prepend — without it, if HEAD is currently on release_branch the reset would destroy release commits by jumping release_branch backwards to the base_branch pre-merge tip; `pre_merge_sha` refers to `{base_branch}`'s pre-merge tip per step 1's capture, NOT the release_branch HEAD). On any step failure (checkout to base_branch, reset, or checkout back to release_branch) → halt with error and leave `substep == "merge_base_done"` so user can resume from step 5 HARD-GATE. On success → `substep → "merge_base_pushed"`, warn user, continue to 6c-ii.
     - **Stop** → halt session (state.json preserved — `substep == "merge_base_done"` enables resume from step 5 HARD-GATE).

**Rollback documentation** — appended verbatim (after the `options:` block) to the following gates ONLY, and ONLY when `state.stage_results.merge_to_base.pre_merge_sha` is non-null in state.json (Path A stores `null` and has no local-merge state to roll back, so this block is suppressed there):

1. Path B step 2 HARD-GATE (Merge to Base)
2. Path B step 5 HARD-GATE (Push Base)
3. Path B step 7 Push Rejected gate

For all other gates (Path A protected-base gate, sub-gates, entry-level Skip warnings) the block is NOT shown.

> "If you reject the post-merge push or want to undo Stage 6.5 entirely, run:
> `git checkout {base_branch} && git reset --hard {pre_merge_sha}`
> on `{base_branch}` to revert to pre-merge state. The `{pre_merge_sha}` value is the actual SHA captured in step 1 and stored in `state.json` at `stage_results.merge_to_base.pre_merge_sha`; it refers to the base_branch tip BEFORE the merge. After the reset, run `git checkout {release_branch}` to return to the release branch."

After Stage 6.5 completes (success path or skip path) — `substep == "merge_base_pushed"` and HEAD on `{release_branch}` — proceed to 6c-ii tag push. **6c-ii processes both entry routes identically**: (i) sessions that ran 6c-i and traversed Stage 6.5 (this section), (ii) legacy/skip sessions that reached 6c-ii directly via the entry-level Skip conditions. In both cases 6c-ii executes `git push origin {tag_name}` against the release_branch lineage and on success transitions `substep → "git_push_done"` (closes m9 / Arch N3).

**6c-ii: Push tag** (only if `tag_name` is not null):
Execute: `git push origin {tag_name}`

If tag push fails → ask via AskUserQuestion (in `user_lang`):
- header: "Tag Push Failed"
- question: "Tag push failed: {error summary}."
- options:
  - "Retry" / "Retry tag push"
  - "Manual" / "I will push tag manually — mark as done"
  - "Skip" / "Skip tag push"
  - "Stop" / "Halt pipeline"
If "Manual" → update substep → `"git_push_done"`.

On success → update substep → `"git_push_done"`, `stage_results.git_ops → "done"`.
Proceed to next stage.

---

### Step 7: Stage — gh_release

*Skip if `gh_release` not in `stages_selected` OR `has_gh == false` OR `has_gh_auth == false` OR `tag_name` is null in state.json (tag was skipped or git_ops was not run).*

Update state.json: `current_stage → "gh_release"`.

Print: `[harness:ship] Stage: GitHub Release`

**Pre-check**: `gh auth status` — if fails, warn and skip stage.

1. Read `CHANGELOG.md` — extract the section for `{release_version}` (from `## [{release_version}]` heading to the next `## [` heading or end of file).
2. **Write extracted section** to `.harness/release_notes.md`. If `CHANGELOG.md` does not exist or the version section is not found, generate minimal release notes: `"Release {release_version}"`.
3. Prepare `gh release create` command:
   ```bash
   gh release create {tag_name} \
     --title "Release {release_version}" \
     --notes-file .harness/release_notes.md \
     {--prerelease if version contains alpha/beta/rc}
   ```

<HARD-GATE>
Show the content of `.harness/release_notes.md` to user. Ask via AskUserQuestion (in `user_lang`):
- header: "GitHub Release"
- question: "IRREVERSIBLE: This will create a public GitHub release for tag `{tag_name}`. Release title: `Release {release_version}`. Notes from `.harness/release_notes.md`."
- options:
  - "Create release" / "Publish the GitHub release"
  - "Edit notes" / "I will edit .harness/release_notes.md, then re-confirm"
  - "Skip" / "Skip GitHub release creation"
  - "Stop" / "Halt pipeline"
Only "Create release" advances. If "Edit notes": wait for user to edit, then re-present this gate.
</HARD-GATE>

Execute: `gh release create {tag_name} --title "Release {release_version}" --notes-file .harness/release_notes.md`

If fails → report error, ask "Retry / Manual / Skip".

Print: `  ✓ GitHub release created: {release_url}`
Update state.json: `stage_results.gh_release → "done"`, `current_stage → "completed"`.

---

### Step 8: Completion

Update state.json: `current_stage → "completed"`, `updated_at → now`.

Print (in `user_lang`):
```
[harness:ship] Release complete!
  Version  : {release_version}
  Stages   : {list of completed stages with checkmarks}
  Tag      : {tag_name or "none"}
  Release  : {github_url or "none"}
```

**Cleanup (Safety Guard):**

Before deleting `.harness/` (in `user_lang`). `Path(...)` expressions below are Python `pathlib`-style pseudocode; agent must execute via `python -c`, `realpath`, PowerShell `Resolve-Path`, or platform-equivalent that follows symlinks for the resolution semantics:

1. **Skill identity check**: Verify `.harness/state.json` exists and `skill` field is `"ship"`. If missing, unreadable, or `skill` field is not `"ship"` → **ABORT**, warn user: `[harness:ship] Safety Guard: state.json missing or skill field mismatch — .harness/ not deleted.`
2. **Path depth check (resolved)**: Verify `Path('.harness').resolve().parent == Path.cwd().resolve()` — the resolved parent of `.harness/` must equal the resolved cwd (ensures `.harness/` after symlink resolution is exactly one level below cwd, blocking symlinks that redirect 2+ levels deeper inside cwd). If not → **ABORT**, warn user: `[harness:ship] Safety Guard: .harness/ is not a direct child of cwd — refusing to delete.`
3. **Symlink escape prevention**: **Always** verify `Path('.harness').resolve()` ⊆ `Path.cwd().resolve()` (no `has_git` condition, no skip path; defense-in-depth duplication retained for `/workflow` parity per `skills/workflow/SKILL.md:937` — Item 2 already implies this, but Item 3 stays for explicit escape-rejection symmetry). If the resolved real path escapes the working directory → **ABORT**, warn user: `[harness:ship] Safety Guard: .harness/ resolves outside cwd — refusing to delete.`
4. **Display before delete**: Print exact absolute target path: `[harness:ship] Deleting: {Path('.harness').resolve()}`.
5. Delete `.harness/` directory. **If `Path('.harness').is_symlink()` is true: remove the symlink itself (e.g. `Path('.harness').unlink()` or `rm .harness`), do NOT follow the link to delete the resolved target.** Otherwise (regular directory): recursively remove the directory contents (e.g. `shutil.rmtree('.harness', follow_symlinks=False)` or `rm -rf .harness`).
6. Inform user artifacts are in `docs/harness/ship-<slug>/` if any were created.

---

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion available → use it
- If not available or fails → present as text with numbered options
- Every option: `label` (short) + `description` (specific)
- "Other" (free text) is automatically appended
- Translate all text to `user_lang`

## Key Rules

- **Stage DAG is enforced.** No stage runs out of order.
- **HARD-GATEs are non-negotiable.** Every irreversible git/GitHub action has an explicit "irreversible" warning gate.
- **has_git == false → auto-skip git_ops and gh_release.** No error.
- **has_gh/has_gh_auth == false → auto-skip gh_release.** No error.
- **substep tracking enables recovery.** On session resume, check substep to avoid re-executing completed operations.
- **Push failure offers retry/manual/skip.** Never halt on push failure alone.
- **changelog uses Conventional Commits parsing.** Never invent commit descriptions.
- **version_bump 2-pass:** Pass 1 detects, gate confirms, Pass 2 applies. If session interrupted between passes, resume from substep.
- **1-line return parsing.** Only first line of sub-agent return is used for state decisions.
- **User language.** All user-facing output in `user_lang`.
