# Agent Harness Roadmap

## v8.x — Shipped

**v8.4.0** — Spec Skill Hardening + /ship merge-to-base

- **A+B+C+D — /spec Hardening**: Risk Auditor + Tech Constraint Analyst added to deep mode (4-analyst parallel synthesis), Spec Critic stage with 3-way gate + 1-round auto-revise, Convention Scan with `--reference` flag and has_git=false candidate file detection, qa_notes / critic_findings / conventions persistence to `{docs_path}` for slug-safe /spec → /workflow handoff (workflow Step 1.5 reuse, Step 2 variable injection into 4 planner templates, Step 8 cleanup protection).
  Token cost (deep mode): ~1.9x of base (analytic estimate from dispatch count: 5 calls deep vs 3 calls pre-8.4 + per-call content growth; live measurement deferred to follow-up smoke session). The estimate **includes** the Input Trust Model boilerplate (~7 lines / ~150 tokens) duplicated across 8 templates (4 planners + 4 spec analyst templates) for security clarity — this is a deliberate trade-off: ~1680 tokens of overhead per /spec deep run buys uniform prompt-injection guards on every sub-agent dispatch, judged worth it over a 1-line compressed form that risks ambiguity. Spec-time detection rate (coin-washer reproduce, analytic mapping of 4-analyst + Critic against original review_report.md): **Critical 5/7** (high-confidence catches C1+C2+C4+C5+C6; borderline C3+C7), **Major 6/12** (high-confidence M1+M2+M3+M4+M5+M14). False-positive on 2 known-good specs (`feature-coin-washer-improvements`, `qaas-411-reopen-fix` — analytic prediction): **Critical=0, Major≤1** each.
  See: `skills/spec/SKILL.md`, `templates/spec/{risk_auditor,tech_constraint_analyst,critic,synthesis}.md`, `templates/planner/*.md`
- **N2 — /ship Stage 6.5 merge_to_base**: Adds `develop → main` merge step before tag push (separate PR `harness/ship-merge-to-base` — added in companion plan if not yet merged). See `skills/ship/SKILL.md`.

**Breaking changes**: deep mode persona count 2 → 4 + Critic; /spec Phase 3 handoff CLI contract gains `--output-dir`; planner templates gain `{qa_discovery_notes}` / `{critic_findings}` placeholders (forked custom templates may render empty Discovery Notes silently).

---

**v8.3.0** — Ship version_bump auto-detection for `.claude-plugin/*.json`

- **N1 — `/ship` version_bump auto-detection for `.claude-plugin/*.json`**: Stage 2 (`version_bump`) now auto-detects version fields in `.claude-plugin/plugin.json` (top-level `$.version`) and `.claude-plugin/marketplace.json` (`$.metadata.version` + `$.plugins[*].version`) alongside the existing standard package manifests. Pass 2 uses JSON parsing on exact key paths to avoid regression where naive string replace would taint other fields (e.g., a `description` containing the same version string). Original line-ending (CRLF vs LF) and trailing-newline state are preserved.
  See: `skills/ship/SKILL.md §Step 2 Stage — version_bump (Pass 1 + Pass 2)`

---

**v8.2.0** — Ship security hardening: Safety Guard parity + tag-length bound

- **S1 — Ship Safety Guard parity with /workflow**: `.harness/` cleanup now performs unconditional symlink-escape check (`Path.resolve() ⊆ Path.cwd()`, no `has_git` gating) and prints the exact absolute target path before deletion, mirroring the `/workflow` Artifact Cleanup Safety Guard.
  See: `skills/ship/SKILL.md §Step 8 Cleanup (Safety Guard)`, `skills/workflow/SKILL.md §Step 8 Artifact Cleanup Safety Guard`
- **S2 — Tag-name length bound**: Tag regex tightened from `^v?[0-9a-zA-Z][0-9a-zA-Z._-]*$` to `^v?[0-9a-zA-Z][0-9a-zA-Z._-]{0,253}$` (254-char max), rejecting pathological large inputs.
  See: `skills/ship/SKILL.md §Step 6c Push (Input validation)`

---

**v8.1.0** — Release hardening: Path Validator + state invariants + schema parity

- **H1 — Verifier model flexibility**: Layer 1 Mechanical Verification primarily runs commands and parses exit codes, so haiku is sufficient by default. An opt-in override is provided for high-cost diagnosis (concurrency, complex test failures).
  See: `skills/workflow/SKILL.md §Step 1 Setup` (--verifier-model), `§Model Selection`
- **H2 — Auto-fix proposal**: When Layer 1 still fails after 3 retries, users may review an AI-proposed diff via a HARD-GATE-based single attempt. The same flow is added to `/refactor` for test regressions.
  See: `skills/workflow/SKILL.md §Step 5 Verify Phase`, `§Architecture Principles`
- **Release hardening** (post-review): `## Architecture Principles` section, `## Path Validator` single-source path validation (applies to `--output-dir`, `{failing_files_list}`, unified diff, Safety Guard), Auto-fix State Transition Table with invariants I1–I4 (once-only, retry clamp, session-resume entry point), `/workflow` ↔ `/refactor` schema parity (`verify.autofix_attempted` nested, reader-union backward compat), 2nd HARD-GATE UX unified across skills.
  See: `skills/workflow/SKILL.md §Architecture Principles`, `§Path Validator`, `§State Machine`
- **L2 — ROADMAP**: This file. Transparent planning and decision log.
- **L3 — `--output-dir` flag**: Supports monorepo/CI scenarios requiring artifacts outside the default `docs/harness/`. Path validation rules live in the Path Validator single source.
  See: `skills/workflow/SKILL.md §Step 1 Setup` (--output-dir), `§Architecture Principles §Path Validator`
- **M2 — `.github/` templates**: `bug_report.yml`, `feature_request.yml`, `question.yml` issue templates + `PULL_REQUEST_TEMPLATE.md` to lower contribution barrier.
- **M2 — Marketplace description**: `plugin.json` and `marketplace.json` descriptions updated with value-proposition language and "multi-agent" keywords.
- **M1 (partial) — README text demo**: "At a Glance" section with before/after examples, terminal output sample, token cost table expansion.

---

**v8.0.0** — Thin Orchestrator + 3-Layer Quality Gates

- Thin Orchestrator: state-machine orchestrator that passes paths only to sub-agents (no accumulation), 1-line return parsing, 40–60% token savings vs fat orchestrator
- 3-layer quality gates: Layer 1 mechanical (build/test/lint/type-check/TODO scan), Layer 2 structural (criterion mapping, scope validation), Layer 3 LLM judgment (bias-reduced, context-isolated)
- `state.json v2.0`: interrupt-safe session recovery, round-based retry loop, run-style (auto/phase/step)
- Convention scanner sub-agent, multi-mode planner (single/standard/multi), phase-mode execution

---

## v8.3+ — Planned

Items deferred from v8.1 / v8.2 with rationale:

| Item | Reason deferred | Notes |
|------|----------------|-------|
| **M4 — Custom persona override** (`templates/user-override/`) | Variable contract definition required first; ROI analysis pending real usage data | Architect/Senior split: Senior recommended deferral. Minimum viable: `.harness/templates/` project-level override only |
| **M3 — Template compression** | Senior measured actual templates: avg 46 lines, max 185 lines (~2–3k tokens). Feedback premise of "8–12k tokens" did not match measurements | Re-evaluate after v8.1 usage data |
| **L1 — External CLI wrapper** | Claude Code's `/skill` invocation already functions as CLI; separate repo adds maintenance burden disproportionate to value | Reconsider if community demand emerges |
| **N2 — `/ship` merge-to-base-branch step** | Discovered during v8.3.0 release: `/ship` Setup auto-detects `base_branch` (`main`/`master`) but Stage 6 (`git_ops`) only commits/tags/pushes on the current branch. There is no step that merges the release branch into `base_branch`, leaving `main` lag in develop→main GitFlow setups (v8.1.0/v8.2.0/v8.3.0 all initially shipped without `main` reflecting the release). Tag points to the release branch's commit, so a pure tag-based release still works, but consumers tracking `main` see no update. | Add Stage 6.5 `merge_to_base` (skipped if `current_branch == base_branch` or `base_branch` not detected): try `git merge --ff-only` first; on non-ff, prompt user with merge-style options (no-ff merge / rebase-then-ff / skip / stop). HARD-GATE before any merge. Push `base_branch` after success. Should run BEFORE tag push so the tag includes the merge commit when applicable, OR after — needs design decision (current pattern = tag on release branch, `main` no-ff merge after, both pushed; tag remains on release branch lineage). |

### Residual review gaps (post-v8.1 verification)

Verified residual items from `/ship` skill review (`docs/harness/unstaged-changes/review_report_final.md`). Critical/Correctness items from v8.1 were resolved in `11c4d5e`. **S1 and S2 shipped in v8.2.0** (see Shipped section above). **N1 shipped in v8.3.0** (`.claude-plugin/*.json` auto-detect, see Shipped section above). No further residual review gaps remain at this time.

---

## Non-Goals

Explicitly out of scope for agent-harness regardless of version:

- **Non-Claude LLM support**: agent-harness is designed for Claude Code's tool ecosystem (AskUserQuestion, sub-agents). Supporting OpenAI/Gemini/local models would require a different architecture.
- **Git-free-only dedicated CLI**: git-free mode is already supported (auto-detected). A separate non-git CLI adds complexity without proportional benefit.
- **Automatic code application without HARD-GATE**: All AI-generated diffs require explicit user confirmation before apply. Auto-apply is permanently out of scope.
- **Internet-dependent features as required dependencies**: WebSearch is used opportunistically (migrate skill). No feature should fail hard when offline.
