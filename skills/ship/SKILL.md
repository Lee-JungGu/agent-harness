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
  - `substep == "git_branch_pushed"` → Step 6c-ii (tag push only)
  - `substep == "git_push_done"` → next stage
- `gh_release` → Step 7
- `completed` → no active session, proceed to Step 1

If `.harness/state.json` does not exist, proceed to Step 1.

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
    "version_bump_files": []
  },
  "docs_path": "docs/harness/ship-<slug>/",  // ship uses "ship-" prefix to namespace artifacts separately from workflow's "docs/harness/<slug>/"
  "created_at": "<ISO8601>",
  "updated_at": "<ISO8601>"
}
```

**substep** tracks intra-stage progress for recovery. Valid values (exhaustive enum):
- `null` — no substep active
- `"version_bump_pass1_done"` — version references detected, awaiting HARD-GATE
- `"version_bump_pass2_done"` — version files updated, stage complete
- `"git_commit_pending"` — about to commit (staging may be incomplete)
- `"git_commit_done"` — commit created successfully
- `"git_tag_pending"` — about to create tag
- `"git_tag_done"` — tag created successfully
- `"git_push_pending"` — about to push
- `"git_branch_pushed"` — branch pushed, tag push pending
- `"git_push_done"` — both branch and tag pushed

---

## Stage DAG (Enforced Order)

```
[Q&A] → version_bump → changelog → build_verify → code_review → git_ops → gh_release
```

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

Update all detected version references. For each file:
- Read the file, replace `{current_version}` with `{release_version}`.
- Write the file back.
- Verify the replacement succeeded (re-read and confirm).

Update state.json: `substep → "version_bump_pass2_done"`, `stage_results.version_bump_files → [list of modified file paths]`.

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

**Input validation:** Verify `branch` matches `^[a-zA-Z0-9/_.-]+$` and `tag_name` (if not null) matches `^v?[0-9a-zA-Z][0-9a-zA-Z._-]*$`. If either fails → print error, halt (state corruption).

**Recovery check:** If resuming from `git_push_pending` or `git_branch_pushed`:
- Check if branch already pushed: `git log origin/{branch}..{branch} --oneline` — if empty, branch is up-to-date → skip to tag push.
- Check if tag already pushed: `git ls-remote origin refs/tags/{tag_name}` — if non-empty, tag exists on remote → skip tag push.
- Skip already-completed operations and update substep accordingly.

<HARD-GATE>
Ask via AskUserQuestion (in `user_lang`):
- header: "Git Push"
- question: "IRREVERSIBLE: This will push branch `{branch}` and tag `{tag_name}` to remote `{remote}`. Cannot be undone without force-push."
- options:
  - "Push" / "Push branch and tag to remote"
  - "Skip push" / "Skip pushing to remote"
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
  - "Skip" / "Skip branch push, continue to tag push"
  - "Stop" / "Halt pipeline"
If "Manual" → update substep → `"git_branch_pushed"`, proceed to tag push.

On success → update substep → `"git_branch_pushed"`.

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
1. Verify `.harness/state.json` exists and `skill` field is `"ship"`. If not → do NOT delete, warn user.
2. Verify `.harness/` is a direct child of the current working directory (resolve absolute path, confirm depth).
3. Delete `.harness/` directory.
4. Inform user artifacts are in `docs/harness/ship-<slug>/` if any were created.

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
