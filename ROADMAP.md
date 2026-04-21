# Agent Harness Roadmap

## v8.x — Shipped

**v8.0.0** — Thin Orchestrator + 3-Layer Quality Gates

- Thin Orchestrator: state-machine orchestrator that passes paths only to sub-agents (no accumulation), 1-line return parsing, 40–60% token savings vs fat orchestrator
- 3-layer quality gates: Layer 1 mechanical (build/test/lint/type-check/TODO scan), Layer 2 structural (criterion mapping, scope validation), Layer 3 LLM judgment (bias-reduced, context-isolated)
- `state.json v2.0`: interrupt-safe session recovery, round-based retry loop, run-style (auto/phase/step)
- Convention scanner sub-agent, multi-mode planner (single/standard/multi), phase-mode execution

---

## v8.1 — In Progress (current)

Features being implemented in this release cycle:

- **H1 — Verifier model flexibility**: Layer 1 Mechanical Verification primarily runs commands and parses exit codes, so haiku is sufficient by default. An opt-in override is provided for high-cost diagnosis (concurrency, complex test failures).
  See: `skills/workflow/SKILL.md §Step 1 Setup` (--verifier-model), `§Model Selection`
- **H2 — Auto-fix proposal**: When Layer 1 still fails after 3 retries, users may review an AI-proposed diff via a HARD-GATE-based single attempt. The same flow is added to `/refactor` for test regressions.
  See: `skills/workflow/SKILL.md §Step 5 Verify Phase`, `§Architecture Principles`
- **L2 — ROADMAP**: This file. Transparent planning and decision log.
- **L3 — `--output-dir` flag**: Supports monorepo/CI scenarios requiring artifacts outside the default `docs/harness/`. Path validation rules live in the Path Validator single source.
  See: `skills/workflow/SKILL.md §Step 1 Setup` (--output-dir), `§Architecture Principles §Path Validator`
- **M2 (partial) — `.github/` templates**: `bug_report.yml`, `feature_request.yml`, `question.yml` issue templates + `PULL_REQUEST_TEMPLATE.md` to lower contribution barrier.
- **M2 (partial) — Marketplace description**: `plugin.json` and `marketplace.json` descriptions updated with value-proposition language and "multi-agent" keywords.
- **M1 (partial) — README text demo**: "At a Glance" section with before/after examples, terminal output sample, token cost table expansion.

---

## v8.2+ — Planned

Items deferred from v8.1 with rationale:

| Item | Reason deferred | Notes |
|------|----------------|-------|
| **M4 — Custom persona override** (`templates/user-override/`) | Variable contract definition required first; ROI analysis pending real usage data | Architect/Senior split: Senior recommended deferral. Minimum viable: `.harness/templates/` project-level override only |
| **M3 — Template compression** | Senior measured actual templates: avg 46 lines, max 185 lines (~2–3k tokens). Feedback premise of "8–12k tokens" did not match measurements | Re-evaluate after v8.1 usage data |
| **L1 — External CLI wrapper** | Claude Code's `/skill` invocation already functions as CLI; separate repo adds maintenance burden disproportionate to value | Reconsider if community demand emerges |
| **M1 (remaining) — GIF/asciinema demo** | AI cannot record terminal sessions or produce binary media | **Manual action required**: user must record with asciinema/VHS and add to README |
| **M2 (remaining) — Stars/Forks growth, X/Reddit posts, Discussion replies** | AI cannot perform social or community actions | **Manual action required** |

---

## Non-Goals

Explicitly out of scope for agent-harness regardless of version:

- **Non-Claude LLM support**: agent-harness is designed for Claude Code's tool ecosystem (AskUserQuestion, sub-agents). Supporting OpenAI/Gemini/local models would require a different architecture.
- **Git-free-only dedicated CLI**: git-free mode is already supported (auto-detected). A separate non-git CLI adds complexity without proportional benefit.
- **Automatic code application without HARD-GATE**: All AI-generated diffs require explicit user confirmation before apply. Auto-apply is permanently out of scope.
- **Internet-dependent features as required dependencies**: WebSearch is used opportunistically (migrate skill). No feature should fail hard when offline.
