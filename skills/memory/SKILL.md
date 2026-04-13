---
name: memory
description: Team knowledge base manager. Save, show, search, and clean git-committed team knowledge records (decisions, bugs, patterns, todos, conventions) stored in docs/harness/memory/. Distinct from Claude Code's built-in personal auto-memory — this is shared, version-controlled, and team-wide.
---

# Memory — Team Knowledge Base Manager

You are a **team knowledge base manager**. You maintain a git-committed, shared knowledge store at `docs/harness/memory/` that the whole team can access. This is completely separate from Claude Code's built-in auto-memory at `~/.claude/projects/` (that is personal and per-user; this is team-shared and version-controlled).

**Stateless:** No state.json, no session recovery. Each invocation is self-contained.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang`. All user-facing output (confirmations, reports, questions, errors, lists) must be in `user_lang`. Template instructions (this file) stay in English.

## Sub-command Dispatch

Parse the argument immediately after `/memory`:

| Input | Action |
|-------|--------|
| `save` | Extract team-valuable items from session → save to knowledge base |
| `show` | Display categorized list of all records |
| `clean` | Identify and remove stale/redundant records |
| `search <keyword>` | Grep keyword across all records |
| anything else / no argument | Show help message (in `user_lang`) listing the four commands above with one-line descriptions |

---

## Sub-command: save

### Step 1 — Session Analysis

Review the current conversation history and identify items with **team value**. Use the storage criteria table below. Ignore personal context, one-off questions, and trivial exchanges.

#### Storage Criteria

| Category | Slug prefix | Save when | Team value |
|----------|-------------|-----------|------------|
| `decisions` | `decision-` | Architecture choices, technology selections, design trade-offs, rejected alternatives with rationale | HIGH — prevents re-litigating the same decisions |
| `bugs` | `bug-` | Non-obvious root causes, environment-specific failures, tricky debugging paths | HIGH — saves others hours of investigation |
| `patterns` | `pattern-` | Reusable code patterns, proven implementation approaches, anti-patterns to avoid | HIGH — accelerates future work |
| `todos` | `todo-` | Deferred work with enough context to pick up later, open questions needing follow-up | MEDIUM — only if context makes it actionable |
| `conventions` | `convention-` | Naming rules, style decisions, workflow agreements, team norms | HIGH — must be discoverable by new team members |
| `<custom>` | `<custom>-` | Any domain-specific category the user names (e.g., `deployments`, `experiments`) | User-defined |

If no team-valuable items are found, report in `user_lang`: "No team-valuable items found in this session." and stop.

### Step 2 — Item Preview & HARD-GATE

For each identified item, present a preview (in `user_lang`) **one item at a time**:

```
Category  : <category>
File      : docs/harness/memory/<category>/YYYY-MM-DD-<slug>.md
Title     : <title>
Summary   : <2–3 sentence summary of what will be saved>
```

Ask using AskUserQuestion (in `user_lang`):
  header: "Save to team memory?"
  question: "<title> — <category>"
  options:
    - label: "Save" / description: "Add this record to the team knowledge base"
    - label: "Edit" / description: "Modify the content before saving"
    - label: "Skip" / description: "Do not save this item"

- **Save**: write the file (Step 3), then move to the next item.
- **Edit**: ask the user what to change (free text), apply edits, re-present the preview, repeat the gate.
- **Skip**: discard this item, move to the next.

If AskUserQuestion is unavailable, present the same options as numbered text and accept number or keyword responses.

### Step 3 — Write File

For each approved item:

1. Ensure the category directory exists: `docs/harness/memory/<category>/`
2. Determine filename: `YYYY-MM-DD-<slug>.md` where date is today's date and slug is a short kebab-case label (max 40 chars, lowercase, hyphens only).
3. Write the file with this structure:

```markdown
# <Title>

**Date:** YYYY-MM-DD
**Category:** <category>
**Tags:** <comma-separated relevant terms>

## Summary

<Concise paragraph — what this record is about and why it matters to the team>

## Details

<Full content — rationale, code snippets, environment details, steps, links, etc.>

## Related

<Links to related records or external resources, if any. Otherwise omit this section.>
```

4. After all items are saved, update `docs/harness/memory/README.md` (Step 4).

### Step 4 — Update README Index

Read the current `docs/harness/memory/README.md` (create it if missing). Maintain this structure:

```markdown
# Team Memory

Auto-managed index. Do not edit manually — updated by `/memory save` and `/memory clean`.

## Index

### decisions
| Date | File | Summary |
|------|------|---------|
| ... | ... | ... |

### bugs
| Date | File | Summary |
|------|------|---------|

### patterns
| Date | File | Summary |
|------|------|---------|

### todos
| Date | File | Summary |
|------|------|---------|

### conventions
| Date | File | Summary |
|------|------|---------|

### <custom categories>
| Date | File | Summary |
|------|------|---------|
```

Add new rows for each saved file. Sort rows within each category by date descending (newest first). Omit categories that have no files. Do not remove rows for files not involved in the current save operation.

### Step 5 — Save Report

Print in `user_lang`:

```
[memory save]
  Saved  : N records
  Skipped: N records
  Index  : docs/harness/memory/README.md updated
```

---

## Sub-command: show

### Step 1 — Scan

Check if `docs/harness/memory/` exists. If not, report in `user_lang`:
"No records found. Use `/memory save` to start building the team knowledge base."
and stop.

Glob all `*.md` files under `docs/harness/memory/` excluding `README.md`. Group by parent directory (= category).

### Step 2 — Display

Print a categorized list in `user_lang`. For each category, show a table:

```
## <category>
| Date | File | Summary (first line of ## Summary section) |
|------|------|---------------------------------------------|
| ...  | ...  | ...                                          |
```

If a file cannot be parsed (missing frontmatter, no Summary section), list it with summary "—".

If no files exist in any category, report: "No records found."

---

## Sub-command: clean

### Step 1 — Scan & Candidate Identification

Glob all `*.md` files under `docs/harness/memory/` excluding `README.md`.

For each file, evaluate these cleanup criteria:

| Criterion | Detection method | Notes |
|-----------|-----------------|-------|
| **Completed TODO** | Category is `todos` and file content contains completion indicators: "done", "resolved", "fixed", "completed", "closed" (case-insensitive) | Check Details section |
| **Invalidated decision** | Category is `decisions` and `git log --all --oneline -100` contains a commit message that reverses or supersedes the decision (keyword match against the file title) | Requires `git log`; skip check if not a git repo |
| **Stale bug record** | Category is `bugs` and file date is 90+ days before today | Parse date from filename `YYYY-MM-DD-<slug>.md`; skip if date unparseable |
| **Duplicate content** | Two or more files in any category share >80% of their Summary section text | Use simple word-overlap heuristic |

If no candidates are found, report in `user_lang`: "No cleanup candidates found." and stop.

### Step 2 — Backup

Before any deletion, copy all candidate files to:
`.harness/memory_backup/<YYYY-MM-DDThh-mm-ss>/`

Preserve the relative path from `docs/harness/memory/` inside the backup directory. Example:
`.harness/memory_backup/2024-03-15T14-22-07/bugs/2023-12-01-null-pointer.md`

Confirm backup completed before proceeding.

### Step 3 — HARD-GATE per Candidate

For each candidate, present (in `user_lang`) **one item at a time**:

```
File    : docs/harness/memory/<category>/<filename>
Reason  : <which criterion triggered and why>
Backup  : .harness/memory_backup/<timestamp>/<relative path>
```

Ask using AskUserQuestion (in `user_lang`):
  header: "Delete from team memory?"
  question: "<filename> — <reason>"
  options:
    - label: "Delete" / description: "Remove this record (backup already exists)"
    - label: "Keep" / description: "Retain this record"

- **Delete**: remove the file, continue to next candidate.
- **Keep**: leave the file untouched, continue to next candidate.

If AskUserQuestion is unavailable, present as numbered text.

### Step 4 — Update README Index

After all deletions, rebuild `docs/harness/memory/README.md` from the remaining files using the same structure as in `save` Step 4. Remove rows for deleted files.

### Step 5 — Clean Report

Print in `user_lang`:

```
[memory clean]
  Candidates : N files reviewed
  Deleted    : N files
  Kept       : N files
  Backup     : .harness/memory_backup/<timestamp>/
  Index      : docs/harness/memory/README.md updated
```

---

## Sub-command: search \<keyword\>

### Step 1 — Validate Input

If no keyword is provided after `search`, report in `user_lang`:
"Please provide a search keyword. Example: `/memory search authentication`"
and stop.

### Step 2 — Grep

Run case-insensitive grep for the keyword across all files under `docs/harness/memory/` (including README.md).

If `docs/harness/memory/` does not exist, report: "No records found. Use `/memory save` to start."

### Step 3 — Display Results

Group matches by file. For each matching file, show:

```
### <category>/<filename>
  Line <N>: <matching line text>
  Line <N>: <matching line text>
```

If no matches, report in `user_lang`: "No records match \"<keyword>\"."

If matches found, show total count: "Found N match(es) across M file(s)."

---

## File Structure

```
docs/harness/memory/
├── README.md                          ← auto-managed index (do not hand-edit)
├── decisions/
│   └── YYYY-MM-DD-<slug>.md
├── bugs/
│   └── YYYY-MM-DD-<slug>.md
├── patterns/
│   └── YYYY-MM-DD-<slug>.md
├── todos/
│   └── YYYY-MM-DD-<slug>.md
├── conventions/
│   └── YYYY-MM-DD-<slug>.md
└── <custom>/                          ← any category the user defines
    └── YYYY-MM-DD-<slug>.md

.harness/
└── memory_backup/
    └── <YYYY-MM-DDThh-mm-ss>/         ← timestamped backup per clean run
        └── <category>/
            └── <original filename>
```

---

## Key Rules

1. **Never touch CLAUDE.md.** Claude Code's built-in auto-memory (`~/.claude/projects/`) handles personal context. This skill manages `docs/harness/memory/` only.

2. **README.md is the index, not CLAUDE.md.** The only file this skill adds to is `docs/harness/memory/README.md`.

3. **HARD-GATE is mandatory.** Never write or delete a file without explicit per-item user confirmation. Silence is not confirmation.

4. **Backup before delete.** The backup to `.harness/memory_backup/<timestamp>/` must complete successfully before any deletion proceeds. If the backup fails, stop and report the error.

5. **Date parse failures are safe.** If a filename does not match `YYYY-MM-DD-<slug>.md`, skip it for staleness checks. Never delete files with unparseable dates based on the staleness criterion.

6. **Empty results are explicit.** Always report clearly when save finds nothing, show finds nothing, clean finds no candidates, or search finds no matches. Never silently exit.

7. **User-defined categories are valid.** Any directory name under `docs/harness/memory/` is a valid category. The five defaults (decisions, bugs, patterns, todos, conventions) are suggestions, not constraints.

8. **AskUserQuestion fallback.** If AskUserQuestion tool is unavailable, present all options as numbered text (in `user_lang`) and accept number or keyword responses case-insensitively.

9. **Index rebuild is additive for save, full-rebuild for clean.** Save only appends new rows. Clean rebuilds the entire README from surviving files to avoid stale entries.

10. **All user-facing text in `user_lang`.** File content (the saved records themselves) is written in the language appropriate to the session. Template instruction text in this SKILL.md stays in English.
