# Changelog

All notable changes to agent-harness are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

## [8.4.0] — 2026-05-06

### Added

- **/spec deep mode now dispatches 4 analysts in parallel**: Requirements + UserScenario + RiskAuditor (NEW) + TechConstraint (NEW). Risk and TechConstraint analysts catch security, concurrency, schema, and operational issues that previously surfaced only in /workflow review cycles (coin-washer Critical 5/7 reproducible at spec-time, target verified per Phase 7 smoke test).
- **/spec Critic stage**: cold review of synthesized spec.md classifies findings as Critical/Major/Minor with `[C*]/[M*]/[m*]` IDs. Critical or Major findings trigger a 3-way gate (Auto-revise / Modify / Approve as-is). Auto-revise re-runs synthesis with `{critic_findings}` injection (max 1 round; 2nd round offers Approve/Stop only — no oscillation).
- **/spec Convention Scan (Step 1.5)**: scans CLAUDE.md (has_git=true, mirrors workflow) and 7 candidate files (has_git=false: STYLE_GUIDE.md, CONTRIBUTING.md, conventions.md, guidelines.md, policy.md, docs/style-guide.md, docs/conventions.md, case-insensitive). New `--reference <path>` CLI flag overrides auto-detect.
- **/spec Phase 3 persists `qa_notes.md`, `critic_findings.md`, `conventions.md`** to `{docs_path}` before cleanup. /workflow Step 1.5 auto-reuses persisted conventions; Step 2 injects `{qa_discovery_notes}` + `{critic_findings}` into all 4 planner templates (architect, senior_developer, qa_specialist, planner_single). /workflow Step 8 "Commit code only" preserves the 3 artifacts in the commit.

### Changed

- **/spec Phase 3 invokes `/workflow`** with explicit `--output-dir docs/harness/<slug>/ "Implement based on {docs_path}spec.md"` (was: `/workflow "Implement based on docs/harness/<slug>/spec.md"`). The `--output-dir` is required to ensure /workflow's `docs_path` matches /spec's `docs_path` — without it, /workflow re-slugifies the task string and silently picks a different directory.
- **`templates/spec/synthesis.md`** now accepts 5 input variables (was 2): `{requirements_analysis}`, `{scenario_analysis}`, `{risk_analysis}`, `{tech_constraint_analysis}`, `{critic_findings}`. Synthesis Instructions updated from "two analyses" to "four analyses (and Critic findings if revising)".
- **All 4 planner templates** (architect.md, senior_developer.md, qa_specialist.md, planner_single.md) now include `## Discovery Notes from Spec Phase` section with `{qa_discovery_notes}` + `{critic_findings}` placeholders.
- **/spec state.json schema** adds 3 fields: `cli_flags.reference`, `conventions`, `critic`. Pre-8.4 sessions resume with these fields defaulted to `null` via `state.get(field, default)` pattern. **Important**: /spec's backward-compat policy intentionally diverges from /workflow's soft-default — /spec halts at Phase 2a-D step 3 if `state.conventions` is null on resume, forcing user Restart or manual fix (silent degradation would produce lower-quality specs without user awareness).

### Breaking

- **Persona count change in /spec deep mode** (2 → 4 + Critic). Token cost increases approx 1.9x for deep runs (estimated; measured value TBD per Phase 7 smoke test — ROADMAP entry will be updated with the actual multiplier after smoke test). The legacy 2-analyst behavior is no longer accessible in 8.4 (no `--legacy-deep` flag — defer to 8.5 if user feedback warrants).
- **/spec → /workflow handoff CLI contract changed**. Users of automation scripts that wrap /spec output strings should update to expect `--output-dir docs/harness/<slug>/` in the invocation. The task description string also changed from `"Implement based on docs/harness/<slug>/spec.md"` (absolute-looking) to `"Implement based on {docs_path}spec.md"` (placeholder form documenting the assembly contract).
- **Planner templates**: forked custom planner templates that omit the new `{qa_discovery_notes}` / `{critic_findings}` placeholders will silently render an empty Discovery Notes section. Recommended: update fork to include the placeholders (see `templates/planner/architect.md` for reference).

### N2 Companion (separate PR `harness/ship-merge-to-base`)

- **/ship Stage 6.5 (`merge_to_base`)** — merges current release branch into `base_branch` BEFORE tag push, with branch protection detection, `pre_merge_sha` rollback support, and substep-level recovery. See separate plan: `docs/superpowers/plans/2026-04-30-ship-merge-to-base-n2-plan.md`.

## [8.3.0] — 2026-04-30

### Added

- **feat(ship): auto-detect `.claude-plugin/*.json` version fields in Stage 2** — `/ship` Stage 2 (`version_bump`) now identifies version references in `.claude-plugin/plugin.json` (top-level `$.version`) and `.claude-plugin/marketplace.json` (`$.metadata.version` and `$.plugins[*].version` for each plugin entry) alongside the existing standard package manifests (`package.json`, `pyproject.toml`, etc.). Pass 2 applies updates via JSON parsing on these key paths, preserving the original line-ending convention (CRLF vs LF) and avoiding the regression where naive string replace would taint coincidentally-equal version strings in other fields (e.g., `description: "Initial 8.2.0 release notes…"`). Resolves residual gap N1 from v8.2.0.
- **feat(md-optimize): add `.gitignore`-aware exclusion to scan/index/safety** — `/md-optimize` Phase 1b now runs `git rev-parse --is-inside-work-tree` and excludes gitignored paths via per-path `git check-ignore --quiet`, preventing the Reference Index from emitting broken references for files that exist locally but not on teammates' machines or in CI. Phase 4 evaluator gains a "Gitignore safety" row, and Safety Rules adds a "Gitignore-aware" bullet (precedence-resolved against the Sub-CLAUDE.md rule: gitignore-aware wins). Non-git projects fall back to the existing Exclusion List with bit-identical behaviour.

### Documentation

- **docs(readme): add `/ship` skill section and Skills table entry** — README's Skills table now lists all 12 skills (previously 11), and a dedicated `## ship` section documents the 6-stage pipeline, auto-detection signals, HARD-GATE matrix, safety guards (including v8.2.0 hardening), and session-recovery substep model.
- **docs(roadmap)**: rename `v8.2+` → `v8.3+` Planned section and adjust scope (added then resolved the `/ship` version_bump auto-detect item; dropped non-development items).

## [8.2.0] — 2026-04-29

### Fixed

- **fix(ship): align `.harness/` cleanup Safety Guard with `/workflow` parity** — Add explicit symlink-escape verification (`Path('.harness').resolve() ⊆ Path.cwd().resolve()`, unconditional), insert "Display target before delete" step that prints the exact absolute path, route every validation failure through ABORT with a translated user warning, and specify symlink-vs-target deletion semantics in Item 5 (`is_symlink()` short-circuit removes the link itself, regular directories use `follow_symlinks=False`). Adds a `Path(...)` pseudocode-portability note for cross-platform agent execution. Resolves residual gap S1 and review #7 (PARTIAL).
- **fix(ship): bound tag-name regex length to strict 254 characters** — Change `tag_name` validation from `^v?[0-9a-zA-Z][0-9a-zA-Z._-]*$` to `^(v[0-9a-zA-Z][0-9a-zA-Z._-]{0,252}|[0-9a-zA-Z][0-9a-zA-Z._-]{0,253})$` to reject pathological tag inputs (e.g. 10k-char strings). Alternation form enforces a strict 254-char hard cap regardless of optional `v` prefix (the simpler `^v?[0-9a-zA-Z][0-9a-zA-Z._-]{0,253}$` would have allowed 255 chars when `v` is present). Resolves residual gap S2 and review N-8 (length bound only; consecutive-dot / trailing-dot hardening deferred).
