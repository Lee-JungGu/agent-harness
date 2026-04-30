---
name: spec
description: Requirements specification writer with multi-round Q&A discovery. Transforms vague ideas into structured specs compatible with /workflow input. Modes — quick (orchestrator only) / deep (requirements analyst + user scenario analyst + synthesis). Use when you need a well-defined spec before starting implementation.
---

# Agent Harness Spec

You are orchestrating a **requirements specification workflow** with multi-round Q&A discovery and selectable quick or deep analysis mode.

**Core principle:** Ambiguity is the enemy of good specs. Every vague requirement must be surfaced and resolved before writing the spec. The output must be immediately usable as `/workflow` input.

**Zero-setup:** Works with or without a git repository. No codebase required — spec can describe a greenfield project.

## Environment Detection

At startup, detect whether the current directory is inside a git repository:
```
git rev-parse --is-inside-work-tree 2>/dev/null
```
- If the command succeeds → `has_git = true`
- If the command fails → `has_git = false`

Store `has_git` in state.json. This flag controls whether git operations (branch creation) are performed.

## User Language Detection

Detect the user's language from their **most recent message**. Store as `user_lang` in state.json (e.g. "ko", "en", "ja", "zh", "es", "de", etc.).

**All user-facing communication** must be in the detected language: progress updates, questions, confirmations, error messages, spec content, confirmation gate prompts and options.

**Re-detection:** On every user message, check if the language has changed. If so, update `user_lang` and switch all subsequent communication.

**What stays in English:** Template instructions (this file and templates/*.md), state.json field names, file names (spec.md), git branch names (if has_git).

## Standard Status Format

When displaying status, read `.harness/state.json` and print (in `user_lang`):
```
[harness]
  Skill    : spec
  Task     : <task>
  Mode     : <quick | deep>
  Model    : <model_config preset name>    ← omit if quick mode
  Phase    : <phase label>
  QA Round : <qa_round> / 3
  Branch   : <branch>                      ← omit if has_git == false
  Output   : <docs_path>
```
Phase labels: `setup` → "Setup — initializing", `qa_active` → "Q&A — discovering requirements", `qa_complete` → "Q&A complete — ready for spec generation", `gen_ready` → "Generating specification", `spec_ready` → "Spec ready — awaiting approval", `convention_scan_active` → "Convention Scan — running", `critic_active` → "Critic — reviewing spec", `critic_complete` → "Critic complete — awaiting Final HARD-GATE", `completed` → "Completed"

## Session Recovery

Before starting a new task, check if `.harness/state.json` already exists **and** `state.json.skill` equals `"spec"`:

1. If it exists and matches, print status in the standard format (including Model line from `model_config` if deep mode), prefixed with `[harness] Previous spec session detected.`
2. Restore `model_config` from state.json (deep mode only). Apply it to all subsequent sub-agent launches.
3. Ask the user using AskUserQuestion (in `user_lang`):
     header: "Session"
     question: "[harness] Previous spec session detected. [print status in standard format]. Resume, restart, or stop?"
     options:
       - label: "Resume" / description: "Continue from {phase} where the previous session left off"
       - label: "Restart" / description: "Delete .harness/ and start from scratch"
       - label: "Stop" / description: "Delete .harness/ and halt"

   Actions per selection:
   - **Resume**: Jump to the step matching state.json phase:
     `setup` → Step 1 |
     `qa_active` → Phase 1 Q&A (resume current qa_round) |
     `qa_complete` → Phase 2 Spec Generation |
     `gen_ready` → Phase 2 Spec Generation |
     `spec_ready` → HARD GATE (show existing spec.md) |
     `completed` → no active session, proceed to Step 1
   - **Restart**: Delete `.harness/` directory and proceed to Step 1
   - **Stop**: Delete `.harness/` directory and halt

If `.harness/state.json` does not exist (or `skill` field is not `"spec"`), proceed to Step 1 normally.

## Smart Routing

Before beginning, evaluate the user's request. If it does not match a requirements specification task, suggest a better skill using AskUserQuestion (in `user_lang`):

| Signal | Suggested Skill |
|--------|----------------|
| User describes working code to improve | `/refactor` |
| User has a spec and wants implementation | `/workflow` |
| User wants to understand existing code | `/codebase-audit` |

When a mismatch is detected, ask using AskUserQuestion:
  header: "Routing"
  question: "[detected mismatch]. A different skill may be more appropriate."
  options:
    - label: "Switch: /{suggested skill}" / description: "{why the suggested skill fits better}"
    - label: "Continue with /spec" / description: "Proceed with requirements specification anyway"

If the user selects "Continue with /spec", proceed normally.

## Workflow

When the user provides a task description (via $ARGUMENTS or in conversation), execute this workflow:

### Step 1: Setup

1. **Detect user language** from the task description. Store as `user_lang`.
2. **Slugify the task:** lowercase, transliterate non-ASCII to ASCII, remove non-word chars except hyphens, replace spaces with hyphens, truncate to 50 chars. Store as `<slug>`.
3. **Create directories:** `.harness/`, `.harness/spec/`, `docs/harness/<slug>/`
4. **Create git branch (if has_git):** `git checkout -b harness/spec-<slug>`. If `has_git == false`, skip this step entirely.
4.5. **Parse `--reference <path>` flag (NEW in 8.4):**
   - If `--reference <path>` provided, validate via Path Validator (`kind=file_reference`, see workflow §Path Validator). On validation failure, halt with explicit error message (mirror workflow `--output-dir` halt-on-fail behavior — do NOT silently fall back to auto-detect).
   - On valid path: store as `cli_flags.reference: <path>` in state.json. Will be consumed by Step 1.5 Convention Scan.
   - If not provided: `cli_flags.reference: null`.
5. **Mode selection:** If `--mode quick` or `--mode deep` was passed, set mode and skip prompt. Otherwise, use AskUserQuestion to ask the user (in `user_lang`):
     header: "Mode"
     question: "Select spec mode:"
     options:
       - label: "quick (Recommended)" / description: "Orchestrator writes spec directly. Fast, token-saving (~1x tokens)"
       - label: "deep" / description: "Requirements Analyst + User Scenario Analyst in parallel, then synthesized. Deeper coverage (~1.3x tokens)"

6. **Model configuration selection (deep mode only):**
   If mode is `quick`, skip this step entirely — no sub-agents are used.
   If mode is `deep`:
     If `--model-config <preset>` was passed, use it directly. Otherwise, use AskUserQuestion to ask the user (in `user_lang`):
       header: "Model"
       question: "Select model configuration for sub-agents:"
       options:
         - label: "default" / description: "Inherit parent model, no changes"
         - label: "all-opus" / description: "All sub-agents use Opus (highest quality)"
         - label: "balanced (Recommended)" / description: "Sonnet executor + Opus advisor (cost-efficient)"
         - label: "economy" / description: "Haiku executor + Sonnet advisor (max savings)"

     **If "Other" selected:** Parse custom format `executor:<model>,advisor:<model>`. Validate each model name — only `opus`, `sonnet`, `haiku` are allowed (case-insensitive). If any model name is invalid, inform the user which value is invalid and re-ask (max 3 retries, then apply `balanced` as default). Show parsed result and ask for confirmation before proceeding.

     **Model config is set once at session start and cannot be changed mid-session.**

     Store result as `model_config` object: `{ "preset": "<name>", "executor": "<model|null>", "advisor": "<model|null>" }`. For `default` preset, store `{ "preset": "default" }`.

7. **Write `.harness/state.json`** with fields: `task`, `skill` ("spec"), `mode` ("quick"/"deep"), `model_config` (deep mode only; omit or null for quick), `user_lang`, `has_git` (boolean), `phase` ("setup"), `qa_round` (1), `branch` (if has_git: "harness/spec-<slug>", else: null), `docs_path` ("docs/harness/<slug>/"), `created_at` (ISO8601).

8. **Print setup summary** (in `user_lang`):
   ```
   [harness] Spec started!
     Branch : harness/spec-<slug>     ← omit if has_git == false
     Mode   : <quick | deep>
     Model  : <preset name>           ← omit if quick mode
     Output : docs/harness/<slug>/spec.md
   ```

### Step 1.5: Convention Scan (NEW in 8.4)

This step runs after Setup and before Phase 1 Q&A. It populates `state.conventions` for downstream analyst injection.

**`conventions` field contract** (mirrors workflow):
- `null` → Step 1.5 not yet executed
- `"skipped"` → user explicitly chose to skip
- `"file:.harness/conventions.md"` → conventions copied locally; analysts inject via `{conventions}` variable

**Order of evaluation:**

1. **`--reference` priority**: If `cli_flags.reference` is non-null and the file exists, copy its content to `.harness/conventions.md`, set `state.conventions → "file:.harness/conventions.md"`, and skip the rest of Step 1.5.

2. **`has_git == true` branch** (workflow Step 1.5 mechanism — reuse):
   - CLAUDE.md ≥ 50 lines → copy to `.harness/conventions.md`, set conventions accordingly.
   - CLAUDE.md sparse/missing → AskUserQuestion: `Scan / Skip`. If Scan, dispatch convention scanner sub-agent (model: `model_config.advisor` or default). Verify file exists; on retry × 2 failure, fall back to `"skipped"`.

3. **`has_git == false` branch** (NEW spec-only logic):
   - Search the following 7 explicit paths (case-insensitive — implementation: `Path.name.lower() == candidate.lower()`):
     - `cwd/STYLE_GUIDE.md`
     - `cwd/CONTRIBUTING.md`
     - `cwd/conventions.md`
     - `cwd/guidelines.md`
     - `cwd/policy.md`
     - `cwd/docs/style-guide.md`
     - `cwd/docs/conventions.md`
   - Filter to files with ≥ 50 lines.
   - 0 matches → set `conventions → "skipped"`.
   - 1 match → copy content to `.harness/conventions.md`, set conventions accordingly.
   - 2+ matches → AskUserQuestion with top-3 matches as options + 1 "Skip" option. On selection, copy chosen file. On Skip, set `conventions → "skipped"`.

**Update phase:** `phase → "convention_scan_active"` at entry, then proceed to Phase 1.

### Phase 1 — Requirements Discovery (Multi-round Q&A)

Update state.json: `phase` → `"qa_active"`, `qa_round` → 1.

#### Round 1: Initial Questions

1. **Parse the task description** for vague or missing requirements. Look for:
   - Undefined actors (who are the users?)
   - Unclear scope boundaries (what is explicitly in vs. out?)
   - Ambiguous success conditions (how do we know it works?)
   - Missing technical constraints (performance, scale, platform, integrations)
   - Unstated assumptions (what is taken for granted?)

2. **Generate up to 5 questions.** Prioritize the most impactful ambiguities. Each question must:
   - Focus on a single specific concern
   - Explain briefly why it matters for the spec
   - Be answerable without deep technical knowledge

3. **Ask the user using AskUserQuestion** (in `user_lang`):
     header: "Q&A Round 1/{max_rounds}"
     question: "To write an accurate spec, I need to clarify a few things about: **{task}**\n\n{numbered question list}"
     options:
       - label: "Answer inline" / description: "I'll type my answers below each question"
       - label: "Skip — use best judgment" / description: "Proceed without answers; mark unknowns as unconfirmed"

   If user selects "Skip — use best judgment": mark all questions as `[unconfirmed]` and proceed directly to Phase 2.

4. **Collect answers.** For each question, if the user responds with "don't know", "unsure", "no opinion", or equivalent → mark that item as `[unconfirmed]`.

5. **Build `qa_discovery_notes`** — a numbered list of Q&A pairs:
   ```
   1. Q: {question}
      A: {answer}   ← or "[unconfirmed]" if unknown
   2. Q: ...
      A: ...
   ```
   Store `qa_discovery_notes` in `.harness/spec/qa_notes.md`.

#### Rounds 2–3: Follow-up (conditional)

After Round 1 answers are collected, evaluate whether new ambiguities emerged from the answers:

- **If new significant ambiguities exist AND qa_round < 3:**
  Update state.json: `qa_round` → incremented value.
  Generate up to 3 follow-up questions targeting the new ambiguities only.
  Ask the user using AskUserQuestion (in `user_lang`):
    header: "Q&A Round {qa_round}/3"
    question: "Your answers raised a few follow-up questions:\n\n{numbered follow-up question list}"
    options:
      - label: "Answer inline" / description: "I'll type my answers below each question"
      - label: "No more questions — write the spec" / description: "Stop Q&A and generate the spec now"

  If user selects "No more questions": stop Q&A immediately, proceed to Phase 2.
  Append new Q&A pairs to `qa_discovery_notes` and update `.harness/spec/qa_notes.md`.

- **If no significant new ambiguities OR qa_round == 3:**
  Stop Q&A. Update state.json: `phase` → `"qa_complete"`.
  Inform user (in `user_lang`): `[harness] Requirements discovery complete. Generating spec...`

**Maximum 3 rounds total.** Never ask more than 3 rounds regardless of remaining ambiguity.

### Phase 2 — Spec Generation

Update state.json: `phase` → `"gen_ready"`.

Read `mode` from state.json and branch accordingly.

#### If mode == "quick": Phase 2-Q

Write `spec.md` directly to `docs/harness/<slug>/spec.md` using the following format. Use `qa_discovery_notes` from `.harness/spec/qa_notes.md` as the primary source of truth.

All section headings and content must be written in `user_lang`.

**Required spec format** (translate all headings and content to `user_lang`):

```markdown
## Goal
<One paragraph: what this product/feature achieves and for whom>

## Background & Decisions
<Context, motivation, and confirmed decisions from Q&A>

## Scope
<Bulleted list of in-scope features and behaviors>

## Out of Scope
<Bulleted list of explicitly excluded items>

## Edge Cases
<Bulleted list of edge cases to handle>

## Acceptance Criteria
<Given/When/Then format — one scenario per criterion>

## Risks
<Bulleted list: risk description — likelihood — mitigation>
```

Mark any item derived from an `[unconfirmed]` Q&A answer with `[unconfirmed]` (translated to `user_lang`) so the user can identify open decisions.

Update state.json: `phase` → `"spec_ready"`.
Print status in the standard format, prefixed with `[harness] Spec draft ready.`

#### If mode == "deep": Phase 2-D

##### Phase 2a-D: Parallel Analysis

1. Read two analyst templates from `{CLAUDE_PLUGIN_ROOT}/templates/spec/`: `requirements_analyst.md`, `user_scenario_analyst.md`
2. Read `qa_discovery_notes` from `.harness/spec/qa_notes.md`.
3. For each analyst, fill template variables: `{task_description}` (original task), `{user_lang}`, `{qa_discovery_notes}` (full Q&A notes content), `{output_path}`:
   - Requirements Analyst → `.harness/spec/analysis_requirements.md`
   - User Scenario Analyst → `.harness/spec/analysis_scenarios.md`
4. **Launch 2 subagents in parallel** using the Agent tool. Each receives its analyst template and has no knowledge of the other subagent (anchoring prevention). Each writes to its output_path.
   If `model_config.preset` is not `"default"`:
   - Requirements Analyst → advisor role
   - User Scenario Analyst → advisor role
5. Wait for both to complete. Verify both analysis files exist.

##### Phase 2b-D: Synthesis

1. Read the synthesis template from `{CLAUDE_PLUGIN_ROOT}/templates/spec/synthesis.md`.
2. Read both analysis files from Phase 2a-D.
3. Fill template variables: `{task_description}`, `{user_lang}`, `{requirements_analysis}` (content of analysis_requirements.md), `{scenario_analysis}` (content of analysis_scenarios.md), `{spec_path}`: `docs/harness/<slug>/spec.md`
4. Follow the synthesis rules to write `spec.md` to `docs/harness/<slug>/spec.md`.
5. Update state.json: `phase` → `"spec_ready"`.
6. Inform user (in `user_lang`):
   ```
   [harness] Spec draft ready.
     Analyses : 2 specialists analyzed independently
     Output   : spec.md synthesized
   ```

### HARD GATE — Spec Approval

<HARD-GATE>
Show `spec.md` to the user and ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Spec"
  question: "Review the spec above. Approve, request modifications, or stop."
  options:
    - label: "Approve" / description: "Accept this spec and proceed to handoff"
    - label: "Modify" / description: "Describe changes — spec will be regenerated"
    - label: "Stop" / description: "Halt and discard the spec"

If user selects "Modify" or provides modification details via "Other":
  - Collect the modification request.
  - **Re-run Phase 2** (same mode) incorporating the changes. The `qa_discovery_notes` remain unchanged; the modification request is appended as a note.
  - Re-present this HARD GATE with the updated spec.

If user selects "Stop": halt the workflow, clean up `.harness/`.
Only "Approve" advances to Phase 3.
</HARD-GATE>

### Phase 3 — Handoff

Update state.json: `phase` → `"completed"`.

1. **Inform the user** (in `user_lang`) that the spec is finalized:
   ```
   [harness] Spec complete!
     Output : docs/harness/<slug>/spec.md
   ```

2. **Smart Routing suggestion** — suggest next step using AskUserQuestion (in `user_lang`):
     header: "Next Step"
     question: "Your spec is ready. Would you like to start implementation?"
     options:
       - label: "Start /workflow" / description: "Launch implementation workflow using this spec"
       - label: "Done" / description: "Keep the spec for later use"

   If user selects "Start /workflow": invoke `/workflow "Implement based on docs/harness/<slug>/spec.md"` (translate the quoted string to `user_lang`).
   If user selects "Done": clean up `.harness/` and halt.

3. **Cleanup:** Delete `.harness/` directory (delete state.json, spec/, and the directory itself). The final `docs/harness/<slug>/spec.md` is preserved.

4. **If has_git == false:** Do not attempt any git operations.

### Status Check (anytime)

If user asks for status, print status in the standard format defined above.

## Spec Output Format

The spec written to `docs/harness/<slug>/spec.md` must use this exact structure for `/workflow` compatibility. Write all content in `user_lang`.

```markdown
## Goal
...

## Background & Decisions
...

## Scope
...

## Out of Scope
...

## Edge Cases
...

## Acceptance Criteria
- **Scenario: {name}**
  - Given: {precondition}
  - When: {action}
  - Then: {expected result}

## Risks
- {risk} — Likelihood: {low/med/high} — Mitigation: {approach}
```

**All headings and content must be translated to `user_lang`.** The English labels above are canonical identifiers for /workflow compatibility.

### Section Mapping to /workflow

| /spec section | /workflow usage |
|---------------|----------------|
| Goal | Goal |
| Background & Decisions | Background |
| Scope | Scope (in scope) |
| Out of Scope | Scope (out of scope) |
| Acceptance Criteria | Completion Criteria |
| Risks | Risks |
| Edge Cases | Testing Strategy |

## Model Selection

Sub-agents are used only in **deep mode**. Both sub-agents use the **advisor role**.

| Preset | advisor |
|--------|---------|
| default | (parent inherit) |
| all-opus | opus |
| balanced | opus |
| economy | sonnet |

### Deep Mode Sub-agents

| Sub-agent | Role | default | all-opus | balanced | economy |
|-----------|------|---------|----------|----------|---------|
| Requirements Analyst | advisor | (no override) | opus | opus | sonnet |
| User Scenario Analyst | advisor | (no override) | opus | opus | sonnet |

**Applying model config:** When launching any sub-agent, if `model_config.preset` is not `"default"`, pass the `model` parameter according to the table above. Sub-agents must NOT directly access state.json to read model_config — the orchestrator passes the model parameter at launch time.

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`

## Key Rules

- **Requirements first, spec second.** Never write the spec before completing at least one round of Q&A.
- **Maximum 3 Q&A rounds.** Stop after round 3 regardless of remaining ambiguity.
- **"Don't know" is valid.** Mark unresolved answers as `[unconfirmed]` — do not invent answers.
- **Confirmation gate is non-negotiable.** The user must explicitly approve the spec before handoff.
- **"Modify" triggers Phase 2 re-run.** Q&A notes are preserved; the spec is regenerated, not patched.
- **Analyst proposals must be independent.** Never share one analyst's findings with another during parallel analysis.
- **Section mapping must be preserved.** The seven spec sections must appear in every spec for /workflow compatibility.
- **User language.** All user-facing output must be in `user_lang`. Re-detect on every user message.
- **Intermediate outputs are ephemeral.** Only `spec.md` is preserved in `docs/`. `.harness/` is cleaned up after completion.
- **skill field is "spec".** state.json must always have `skill: "spec"` — session recovery depends on this.
