# Agent Harness

**Zero-setup, zero-dependency** multi-agent workflow harness for Claude Code with **3-layer quality gates** and **selectable single-agent or multi-agent persona mode**. Works for development tasks and non-development tasks (planning, document generation, analysis) alike.

No dependencies required. No Python, no pip, no build steps — just install the plugin and go.

Inspired by Anthropic's [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps).

> Demo GIF coming soon — see [ROADMAP.md](ROADMAP.md#v82--planned).

## At a Glance

### Before / After

**Without agent-harness:** You write a prompt, Claude implements changes, you run tests manually, find regressions, prompt again. No structured retry, no isolation, no audit trail.

**With agent-harness:**
```
/workflow "add rate limiting to the API"
```
→ Two specialists (Architect + Senior Dev) propose plans independently  
→ Synthesis produces `spec.md` — you review and approve  
→ Lead Dev + Advisor implement code, write `changes.md`  
→ Layer 1: build ✓ test 42/42 ✓ lint 0e/2w ✓ (auto-retry on fail, up to 3x)  
→ Layer 2 + 3: isolated LLM evaluator reviews against spec, produces `qa_report.md`  
→ PASS → you choose commit / no-commit

### Terminal Output Sample

```
[harness] Task started!
  Directory : /workspace/my-api
  Branch    : harness/add-rate-limiting-to-the-api
  Mode      : standard
  Model     : balanced
  Verifier  : haiku
  Style     : auto
  Language  : typescript
  Test      : npm test
  Build     : npm run build
  Lint      : npm run lint
  TypeCheck : npx tsc --noEmit
  Scope     : (no limit)
  Output    : docs/harness/add-rate-limiting-to-the-api/

[harness] Phase: Verify (Layer 1 — Mechanical)
[harness] Verify (Layer 1) complete.
  Result : PASS — build ✓, test 42/42 ✓, lint 0e/2w, scan 0 TODO

[harness] ✓ QA PASS — task complete.
```

### Token Cost vs. Quality

| Mode | Best for | Token cost | First-pass success rate |
|------|----------|------------|------------------------|
| **single** | Small fixes, quick iterations | Baseline | ~60% *(estimated)* |
| **standard** | General features, API changes | ~1.5x baseline *(estimated)* | ~80% *(estimated)* |
| **multi** | Complex features, architecture | ~2-2.5x baseline *(estimated)* | ~90% *(estimated)* |

Higher modes cost more per run but save total cost by reducing retry rounds. Standard is recommended for most tasks.

> *(estimated)*: Figures are estimates based on internal dogfooding. A measurement benchmark harness is planned for v8.2+.

## Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **Workflow** | `/workflow <task>` | 3-Phase (Planner -> Generator -> Evaluator) workflow. Single or multi-agent mode. Works with or without git. |
| **Refactor** | `/refactor <target>` | Safe, behavior-preserving code structure improvement. Single, multi, or comprehensive mode. |
| **Migrate** | `/migrate <target> [--from v4 --to v5]` | Staged migration of frameworks, libraries, and dependencies. Single or multi-agent mode with WebSearch research. |
| **Debug** | `/debug <error>` | Hypothesis-driven debugging with mandatory executable verification. Quick or deep (2-agent cross-verification) mode. |
| **Spec** | `/spec <requirement>` | Multi-round Q&A requirements specification. Output directly compatible with `/workflow` input. Quick or deep mode. |
| **Test Gen** | `/test-gen <target>` | Automated test generation with mutation-based quality verification. Supports coverage-gap and regression modes. |
| **Memory** | `/memory <cmd>` | Team knowledge base (save/show/clean/search). Git-committed, team-shared decisions, patterns, and conventions. |
| **Codebase Audit** | `/codebase-audit` | Systematic codebase analysis with 3-tier mode (quick/deep/thorough) for team onboarding. |
| **Code Review** | `/code-review <target>` | Systematic, bias-free code review. Quick (1 agent), deep (2 specialists), or thorough (3 specialists + cross-verification). |
| **MD Optimize** | `/md-optimize` | Optimize CLAUDE.md and project `.md` files for token efficiency. |
| **MD Generate** | `/md-generate` | Analyze project and generate/enhance CLAUDE.md for effective Claude Code development. |

## Install

```bash
claude plugin marketplace add Jugger0716/agent-harness
claude plugin install agent-harness@agent-harness-marketplace
```

## Quick Start

```
/workflow fix login timeout bug                    # asks for mode + model config
/workflow fix login timeout bug --mode single      # fast, token-saving
/workflow fix login timeout bug --mode standard    # balanced analysis, ~1.5x tokens
/workflow fix login timeout bug --mode multi       # deep multi-agent analysis, ~2-2.5x tokens
/workflow fix bug --model-config balanced          # Sonnet executor + Opus advisor (cost-efficient)

/workflow plan "add user auth"                     # phase mode: plan only, end session
/workflow generate                                 # phase mode: resume from plan, generate only
/workflow verify                                   # step mode: mechanical verification only
/workflow evaluate                                 # step mode: evaluation only

/workflow draft product requirements spec           # works without git too (non-dev tasks)

/debug "NullPointerException in UserController"    # hypothesis-driven debugging
/debug --mode deep --attach error.log              # 2-agent cross-verification

/spec "Add payment retry on failure"               # multi-round Q&A -> structured spec
/spec --mode deep                                  # 2 analysts (requirements + user scenario)

/test-gen src/auth/                                # generate tests for directory
/test-gen --coverage-gap                           # auto-find low-coverage areas
/test-gen --regression docs/harness/slug/debug_report.md  # regression tests from debug

/memory save                                       # save team-valuable decisions from session
/memory show                                       # list all team knowledge records
/memory clean                                      # remove stale/completed records
/memory search authentication                      # search across knowledge base

/codebase-audit                                    # auto-recommends mode based on project size
/codebase-audit --mode thorough                    # comprehensive multi-agent analysis
/codebase-audit --scope "src/**" --incremental     # analyze only changes in src/

/code-review #123                                  # review PR, asks for mode
/code-review feature/auth --mode deep              # review branch diff, deep mode
/code-review --staged --mode quick                 # review staged changes, quick

/refactor extract auth logic from UserController    # asks for mode
/refactor reduce coupling in src/services/ --mode single
/refactor restructure data layer --mode comprehensive

/migrate react --from 17 --to 18                   # staged React migration
/migrate replace moment with dayjs                 # library replacement
/migrate nextjs                                    # auto-detect versions

/md-optimize                                       # optimize markdown files
/md-generate                                       # analyze project & generate CLAUDE.md
```

## Model Configuration (Advisor Strategy)

Inspired by Anthropic's [Advisor Strategy](https://claude.com/blog/the-advisor-strategy), sub-agents can run on different models to optimize cost vs. quality. Select a preset at startup or via `--model-config`:

| Preset | Executor | Advisor | Evaluator | Verifier | Use case |
|--------|----------|---------|-----------|----------|----------|
| **default** | (parent) | (parent) | (parent) | Haiku | No change, inherit parent model |
| **all-opus** | Opus | Opus | Opus | Haiku | Maximum quality |
| **balanced** | Sonnet | Opus | Opus | Haiku | Recommended — cost-efficient with quality judgment |
| **economy** | Haiku | Sonnet | Sonnet | Haiku | Maximum savings, basic quality |

> **Verifier defaults to Haiku** — Layer 1 Mechanical Verification only executes commands and parses exit codes. Override with `--verifier-model sonnet|opus` for sensitive mechanical verification (e.g., concurrency failures, complex test diagnostics). Not recommended for routine use — Haiku is sufficient in the vast majority of cases.

**Role mapping across all skills:**
- **Executor**: bulk work — analysis, code generation, proposals (cheaper model OK)
- **Advisor**: high-level judgment — plan review, safety checks (quality model needed)
- **Evaluator**: independent verification — always protected (never haiku)

Works with: workflow, refactor, migrate, debug, spec, test-gen, code-review, codebase-audit. Presets are selected via numbered UI (AskUserQuestion) with `Other` for custom role mapping.

## Interactive UX

All user-facing prompts use **AskUserQuestion** — a numbered selection UI where you pick by number instead of typing keywords. Every prompt includes descriptive options and an automatic `Other` option for free text input.

Key interaction points:
- **Mode selection**: numbered options with token cost hints and auto-recommendation
- **Confirmation gates**: Proceed / Modify / Stop (replaces freeform text approval)
- **QA retry**: Fix / Accept as-is
- **Commit**: 3 options — "Commit code only" (recommended) / "Commit all with artifacts" / "No commit" (git environments only; non-git environments skip commit)
- **Session recovery**: Resume / Restart / Stop

Falls back to text-based input when AskUserQuestion is unavailable.

---

## workflow

**Thin Orchestrator** architecture — the orchestrator manages state transitions and dispatches sub-agents with minimal context (~8-15K tokens). Sub-agents return 1-line summaries; detailed results are written to files. This achieves **40-60% token savings** compared to fat orchestrator designs while maintaining quality through **3-layer mechanical quality gates**.

```
/workflow  -> [Setup] Auto-detect + mode/style selection
                        -> [Plan] Planner sub-agent
                           single:   1 agent explores + writes spec.md
                           standard: 2 specialists propose -> Synthesis
                           multi:    3 specialists -> Cross-critique -> Synthesis
                        -> Confirmation Gate: user approves spec
                        -> [Generate] Generator sub-agent
                           single:   1 agent implements code
                           standard: Lead Dev plan -> Combined Advisor -> Implementation
                           multi:    Lead Dev plan -> 2 Advisors parallel -> Implementation
                        -> [Verify] Layer 1 Mechanical (build/test/lint/type-check/TODO scan)
                           FAIL -> auto-retry Generator (max 3x)
                        -> [Evaluate] Layer 2 Structural + Layer 3 LLM Judgment
                           L2 FAIL -> auto-retry (max 2x)
                           L3 FAIL -> user Fix/Accept (max N rounds)
                        -> PASS -> Cleanup & Commit
```

Claude handles everything directly -- no external CLI, no wrapper scripts.

### Auto-Detection

The harness detects language, test, and build commands from your project files:

| Detected File | Language | Test Command | Build Command |
|--------------|----------|-------------|---------------|
| `build.gradle` / `build.gradle.kts` | Java/Kotlin | `./gradlew test` | `./gradlew build` |
| `pom.xml` | Java | `mvn test` | `mvn compile` |
| `pyproject.toml` / `setup.py` | Python | `pytest` | - |
| `package.json` | TypeScript/JavaScript | `npm test` | `npm run build` |
| `*.csproj` | C# | `dotnet test` | `dotnet build` |
| `go.mod` | Go | `go test ./...` | `go build ./...` |
| `Cargo.toml` | Rust | `cargo test` | `cargo build` |

Additionally, lint and type-check commands are auto-detected:

| Detected File / Config | Lint Command | Type-Check Command |
|------------------------|-------------|-------------------|
| `package.json` scripts.lint | `npm run lint` | — |
| `.eslintrc*` / `eslint.config.*` | `npx eslint .` | — |
| `tsconfig.json` | — | `npx tsc --noEmit` |
| `pyproject.toml` [tool.ruff] | `ruff check .` | — |
| `pyproject.toml` [tool.mypy] / `mypy.ini` | — | `mypy .` |
| `.golangci.yml` | `golangci-lint run` | — |
| `Cargo.toml` | `cargo clippy` | — |

Override with `--lint-cmd` or `--type-check-cmd` if auto-detection is inaccurate.

### How it works

1. You invoke the harness skill with a task description
2. **Setup**: Auto-detects language/test/build, detects your language, creates `.harness/state.json` and `docs/harness/<task-slug>/`, creates a `harness/*` git branch (skipped if not in a git repository)

#### Phase 1 -- Planner (Multi-Agent)

> **Standard mode** uses only the Architect and Senior Developer personas (no QA Specialist, no cross-critique). See the full mode comparison in the Token Cost table above.

Three specialist personas analyze the task **independently and in parallel**:

| Persona | Focus |
|---------|-------|
| **System Architect** | Structure, scalability, dependency management, long-term design |
| **Senior Developer** | Implementation feasibility, practical constraints, hidden complexity |
| **QA Specialist** | Failure modes, edge cases, boundary conditions, error handling |

After independent proposals, each specialist **cross-critiques** the other two proposals. The orchestrator then **synthesizes** all 6 documents (3 proposals + 3 critiques) into a single `spec.md` using majority-rule and evidence-based decision criteria.

**Why this works:** Independent proposals eliminate anchoring bias. Cross-critique surfaces disagreements. Synthesis preserves the strongest ideas from all perspectives.

4. **Confirmation Gate**: Claude shows the spec and waits for explicit user approval before proceeding. Ambiguous responses are re-confirmed.

#### Phase 2 -- Generator (Lead + Advisors)

> **Standard mode** uses a single Combined Advisor (merged Code Quality + Test & Stability perspectives) instead of two separate advisors.

A single Lead Developer owns the implementation for code coherence, supported by an advisory panel:

| Persona | Role | Timing |
|---------|------|--------|
| **Lead Developer** | Creates implementation plan, then implements code | Sequential |
| **Code Quality Advisor** | Reviews plan for anti-patterns, SOLID violations, consistency | Before implementation |
| **Test & Stability Advisor** | Reviews plan for runtime risks, error handling gaps, test coverage | Before implementation |

The advisory review happens **before code is written**, catching issues when they're cheap to fix rather than expensive to rework.

#### Verify -- Mechanical Quality Gates (Layer 1)

After code generation, a mechanical verification step runs **before** the LLM evaluator:

| Check | Criteria | On Failure |
|-------|----------|-----------|
| **Build** | Exit code 0 | Stop, retry Generator |
| **Test** | All tests pass | Record failures, continue |
| **Lint** | No errors (warnings OK) | Record errors, continue |
| **Type Check** | Exit code 0 | Record errors, continue |
| **TODO/FIXME scan** | Completeness markers in changed files | Warning (configurable) |

If Layer 1 fails, the Generator is automatically retried up to 3 times with concrete error logs — no user intervention needed. This catches **50%+ of issues** without using LLM judgment.

#### Evaluate -- Structural + LLM Verification (Layer 2 + 3)

Runs as an isolated sub-agent with 2-layer evaluation:

**Layer 2 — Structural Verification** (narrow YES/NO checks):
- Each acceptance criterion: satisfied? `file:line` evidence required
- Each changed file: maps to a spec requirement? Unmapped = scope violation
- Test coverage per criterion, diff-based risk review (error handling, resource leaks, security)
- If any check fails → FAIL immediately, skip Layer 3, auto-retry up to 2 times

**Layer 3 — LLM Judgment** (only if Layer 2 passes):

Runs with research-backed bias reduction:

| Technique | Research Basis |
|-----------|---------------|
| **Context isolation** (separate subagent) | Agent-as-a-Judge (ICLR 2025): 90.44% human agreement vs 60.38% for inline evaluation |
| **Anchor-free input** (no Generator reasoning passed) | Anchoring bias research: LLMs anchor strongly to provided context |
| **Defect-assumption framing** ("assume defects, 2 pre-mortem hypotheses") | Pre-mortem (Brookings): reduces overconfidence |
| **Author neutralization** (no author identity disclosed) | PNAS 2025: LLMs favor LLM-generated content at 89% rate |
| **Risk-before-PASS** (identify key risks + verify with code evidence) | Confirmation bias: structural forced consideration of counterevidence |
| **Rubric decomposition** (5 criteria with inline sub-checks) | G-Eval, RocketEval: finer granularity reduces evaluation bias |

7. If Layer 1 FAIL → auto-retry Generator (max 3). If Layer 2 FAIL → auto-retry (max 2). If Layer 3 FAIL → user asked whether to fix (up to max rounds)
8. On completion, the user is asked whether to commit the artifacts

### Token Cost vs. Quality Trade-off

| Mode | Best for | Token cost | Quality vs single |
|------|----------|------------|-------------------|
| **single** | Small bug fixes, simple features, quick iterations | Baseline | Baseline |
| **standard** | General features, API changes, moderate complexity | ~1.5x baseline | +60-70% |
| **multi** | Complex features, architectural changes, high-stakes code | ~2-2.5x baseline | +85-95% |

Higher modes use more tokens per run but have higher first-pass success rates, often reducing total cost by avoiding retry rounds. Standard mode is recommended for most tasks — it provides significant quality improvement at modest token cost.

### Execution Styles

| Style | Usage | Behavior |
|-------|-------|----------|
| **auto** (default) | `/workflow "task"` | Full pipeline, user gates at spec approval and FAIL only |
| **phase** | `/workflow plan "task"` then `/workflow generate` | Each phase ends session; resume in next session for max token savings |
| **step** | `/workflow verify` or `/workflow evaluate` | Execute single step only |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| mode | (ask user) | `single` for fast/token-saving, `standard` for balanced analysis, `multi` for deep multi-agent analysis |
| model-config | (ask user) | `default` / `all-opus` / `balanced` / `economy` — see Model Configuration section |
| scope | auto-detected | Restrict file modifications to a pattern |
| max rounds | 3 | Maximum Generator/Evaluator retry cycles |
| max files | 20 | Maximum number of files that can be modified |
| lint-cmd | auto-detected | Override lint command |
| type-check-cmd | auto-detected | Override type-check command |
| `--verifier-model <model>` | `haiku` | Override Layer 1 Verifier model. Allowed: `haiku`, `sonnet`, `opus`. Cost warning shown for sonnet/opus. |
| `--output-dir <path>` | `docs/harness` | Override output directory base for spec, changes, verify, and QA reports. Relative path from repo root. Disallows: absolute paths, `..`, reserved names (`memory`, `spec`, `planner`, `generator`). |

Example: `/workflow fix auth bug --mode single --model-config balanced --scope "src/auth/**"`
Example: `/workflow add caching --output-dir build/harness --verifier-model sonnet`

### Git-Free Mode

The workflow automatically detects whether the current directory is a git repository. When running outside a git repo (e.g., for planning data processing, document generation, or analysis tasks), git operations (branch creation, commits) are skipped entirely. All core phases (Planner → Generator → Evaluator) work identically. Artifacts are saved to `docs/harness/<slug>/`.

### Session Recovery

If a session is interrupted, the harness detects the existing `.harness/state.json` on next invocation and offers to resume from where you left off.

### Confirmation Gates

The Generator phase consumes significant tokens and is hard to undo. The harness enforces **explicit user confirmation** before proceeding:

- **Spec approval**: Only clear affirmatives are accepted. Ambiguous responses trigger re-confirmation.
- **QA retry**: When the Evaluator reports FAIL, the harness asks the user before starting another round.

### Language Support

The harness communicates in the **user's language** -- automatically detected from the task description. All templates are written in English for token efficiency and global compatibility, but all user-facing output (messages, spec, QA reports) is generated in the detected language.

### File Structure

```
.harness/
  state.json                        # Working state (temporary)
  planner/
    proposal_architect.md           # Architect's independent proposal
    proposal_senior_developer.md    # Senior Developer's independent proposal
    proposal_qa_specialist.md       # QA Specialist's independent proposal
    critique_architect.md           # Architect's cross-critique
    critique_senior_developer.md    # Senior Developer's cross-critique
    critique_qa_specialist.md       # QA Specialist's cross-critique
  generator/
    plan.md                         # Lead Developer's implementation plan
    review_code_quality.md          # Code Quality Advisor's review
    review_test_stability.md        # Test & Stability Advisor's review

docs/harness/<task-slug>/
  spec.md                           # Planner output (preserved)
  changes.md                        # Generator output (preserved)
  verify_report.md                  # Layer 1 verification results (overwritten each run)
  qa_report.md                      # Evaluator output — Layer 2 + Layer 3 (preserved)
```

### Plugin Compatibility

The harness discovers skills by **capability keyword** (e.g. "brainstorming", "tdd", "code-review"), not by plugin name. It works with any installed plugin that provides matching skills:

| Phase | Searches for | Example matches |
|-------|-------------|-----------------|
| Planner | "brainstorming", "ideation" | superpowers:brainstorming, any brainstorming skill |
| Planner | "writing-plans", "plan" | superpowers:writing-plans, any planning skill |
| Generator | "test-driven-development", "tdd" | superpowers:test-driven-development |
| Generator | "subagent-driven-development", "parallel-tasks" | superpowers:subagent-driven-development |
| Evaluator | "systematic-debugging", "debugging" | superpowers:systematic-debugging |
| Evaluator | "requesting-code-review", "code-review" | superpowers:requesting-code-review |
| Evaluator | "verification-before-completion", "verification" | superpowers:verification-before-completion |

If no matching skill is found, the harness proceeds without it. No specific plugin is required.

---

## refactor

Safe, behavior-preserving code structure improvement. Separates impact analysis, atomic execution with safety checks, and isolated verification into distinct phases. "Same behavior, better structure."

```
/refactor  -> [Setup] Auto-detect + git safety + baseline tests + mode selection
                        -> [Phase 1] Impact Analysis
                           single:        1 agent analyzes + writes refactor_plan.md
                           multi:         2 specialists analyze independently
                                          -> Synthesis: merge into refactor_plan.md
                           comprehensive: 3 specialists analyze independently
                                          -> Cross-verification: each reviews others
                                          -> Synthesis: merge into refactor_plan.md
                        -> Confirmation Gate: user approves plan
                        -> [Phase 2] Execution (atomic steps)
                           single:              1 agent applies changes step-by-step
                           multi/comprehensive:  Safety Advisor reviews each step
                                                 -> Execute + test after each
                           On test failure: STOP immediately (no auto-fix)
                        -> [Phase 3] Verification (isolated subagent)
                           Compare tests with baseline -> PASS/FAIL
```

### Modes

| Mode | Best for | Analysis | Execution | Token cost |
|------|----------|----------|-----------|------------|
| **single** | File/function level (< 3 files) | 1 agent | 1 agent, step-by-step | 1x |
| **multi** | Module level (3-10 files) | 2 analysts + synthesis | Lead Dev + Safety Advisor | ~1.7x |
| **comprehensive** | Architecture level (10+ files) | 3 analysts + cross-verify + synthesis | Lead Dev + Safety Advisor | ~2.5x |

### Core Principles

- **Atomic changes**: One refactoring step at a time
- **Test after each step**: Run full test suite between every change
- **Stop on failure**: No auto-fix. Report and ask the user
- **Baseline capture**: Snapshot test results before starting

### Phase 1 — Impact Analysis

Analysts examine the target code independently:

| Persona | Focus | Modes |
|---------|-------|-------|
| **Structural Analyst** | Dependencies, coupling, cohesion, complexity | multi, comprehensive |
| **Risk Analyst** | Impact scope, breakage risk, test coverage gaps | multi, comprehensive |
| **Feasibility Analyst** | Framework constraints, practical blockers, hidden deps | comprehensive only |

**comprehensive** adds cross-verification: each analyst reviews the other two analyses before synthesis, catching assumptions that synthesis alone would miss.

### Phase 2 — Execution

Changes are applied one step at a time with mandatory testing between each:

| Event | Action |
|-------|--------|
| Step complete, tests pass | Continue to next step |
| Step complete, new test failure | **STOP**. Report regression. User decides: revert / fix / abort |
| Safety Advisor says STOP (multi/comprehensive) | Report to user. Skip / modify / abort |
| No test suite available | Code review for behavior equivalence instead |

### Phase 3 — Verification (Isolated)

Runs as an isolated sub-agent with the same bias-reduction techniques as workflow:
- **Context isolation** (separate subagent)
- **Anchor-free input** (no execution reasoning passed)
- **Baseline comparison** (tests compared against captured baseline)
- **Behavior-first criteria** (behavior preservation is the primary criterion)

### Error Handling

| Scenario | Action |
|----------|--------|
| No test suite | Warn + proceed with code review only |
| No tests cover target | Suggest writing tests first |
| Baseline tests failing | Report + ask user (fix first or proceed) |
| Test regression mid-refactor | Stop immediately, report, user decides |

### Smart Routing

| Finding | Suggestion |
|---------|-----------|
| User wants new features | `/workflow` |
| Version/dependency issues | `/migrate` |
| Needs codebase understanding first | `/codebase-audit` |

### Session Recovery

If a session is interrupted, the harness detects the existing `.harness/state.json` on next invocation and offers to resume from where you left off.

### File Structure

```
.harness/
  state.json                        # Working state (temporary)
  context.md                        # Shared context (multi/comprehensive)
  refactor/
    analysis_structural.md          # Structural Analyst's analysis
    analysis_risk.md                # Risk Analyst's analysis
    analysis_feasibility.md         # Feasibility Analyst's analysis (comprehensive)
    critique_structural.md          # Cross-verification (comprehensive)
    critique_risk.md                # Cross-verification (comprehensive)
    critique_feasibility.md         # Cross-verification (comprehensive)
    baseline_tests.txt              # Captured baseline test output

docs/harness/<slug>/
  refactor_plan.md                  # Analysis output (preserved)
  changes.md                        # Execution output (preserved)
  qa_report.md                      # Verification output (preserved)
```

---

## migrate

Executes framework/library version upgrades, language transitions, and dependency replacements using a staged approach — one breaking change at a time with build/test verification at every step.

```
/migrate <target>  -> [Setup] Auto-detect versions + mode selection
                       -> [Phase 1] Analysis
                          single: 1 agent researches guide + scans codebase
                          multi:  External Research Analyst (WebSearch)
                                  + Codebase Impact Analyst (parallel)
                                  -> Synthesis: merge into migration_plan.md
                       -> Confirmation Gate: user approves plan
                       -> [Phase 2] Staged Execution
                          Per breaking change:
                            1. Apply change
                            2. Build check
                            3. Test check (compare vs baseline)
                            4. Migration Advisor review (multi only)
                          On failure -> stop + report
                       -> [Phase 3] Evaluator (isolated subagent)
                          Full test suite vs baseline
                          Deprecated API scan (codebase-wide)
                          Version consistency check
                       -> PASS -> Done / FAIL -> Fix / Stop / Rollback
```

### How it works

1. You invoke the migrate skill with a target and optional version range
2. **Setup**: Auto-detects current version, researches target version, captures baseline tests, saves original branch name, creates a `harness/migrate-*` git branch

#### Phase 1 -- Analysis

| Mode | Agents | What happens |
|------|--------|-------------|
| **single** | 1 agent | Researches migration guide via WebSearch, scans codebase for affected files, builds migration plan |
| **multi** | 2 analysts | External Research Analyst + Codebase Impact Analyst work in parallel, then synthesize into migration plan |

The analysis phase produces a `migration_plan.md` with ordered steps — one per breaking change — each listing affected files and concrete actions.

**WebSearch fallback:** If WebSearch fails, the skill falls back to local CHANGELOG/MIGRATION files in the project or package directory.

3. **Confirmation Gate**: The migration plan is shown to the user for explicit approval before any code changes.

#### Phase 2 -- Staged Execution

Each breaking change is applied as an isolated step:

| Action | What happens | On failure |
|--------|-------------|------------|
| Apply change | Update deps, modify code, update config | — |
| Build check | Run build command | 2 fix attempts, then stop |
| Test check | Run tests, compare against baseline | 2 fix attempts, then stop |
| Advisor review | Migration Advisor reviews step (multi only) | Critical → stop, Warning → continue |

The key insight: **baseline test failures are excluded from regression detection.** Only NEW failures after migration count as regressions.

#### Phase 3 -- Evaluator (Isolated)

Runs as an isolated sub-agent with migration-specific checks:

| Check | Purpose |
|-------|---------|
| **Full test suite** | Compare against baseline — any new failures? |
| **Deprecated API scan** | Codebase-wide search for old patterns that should have been migrated |
| **Version consistency** | No conflicting versions, peer dep mismatches, or duplicate packages |
| **Code correctness** | New API usage follows correct patterns from migration guide |

### Version Auto-Detection

| File | Detection |
|------|-----------|
| `package.json` | dependencies / devDependencies |
| `pyproject.toml` | project.dependencies / tool.poetry.dependencies |
| `go.mod` | require block |
| `Cargo.toml` | dependencies section |
| `build.gradle(.kts)` | dependency declarations |
| `pom.xml` | dependency elements |
| `*.csproj` | PackageReference elements |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| --from | auto-detect | Source version |
| --to | auto-detect (latest stable) | Target version |
| --mode | auto (1 BC → single, 2+ → multi) | `single` for fast, `multi` for thorough |

### File Structure

```
.harness/
  state.json                          # Working state (temporary)
  migrate/
    research_external.md              # External research output
    research_internal.md              # Codebase impact analysis
    baseline_tests.txt                # Baseline test output
    advisor_step_1.md                 # Per-step advisor review (multi)
    advisor_step_2.md                 # ...

docs/harness/<slug>/
  migration_plan.md                   # Analysis output (preserved)
  changes.md                          # Execution log (preserved)
  qa_report.md                        # Evaluator output (preserved)
```

### Session Recovery

If a session is interrupted, the harness detects the existing `.harness/state.json` on next invocation and offers to resume — including mid-execution recovery (resumes from the last completed step).

---

## debug

Hypothesis-driven debugger with mandatory executable verification actions. Classifies error types, attempts reproduction, generates falsifiable hypotheses, and verifies them through code search, git history, and test execution.

```
/debug  -> [Setup] Error info collection + error type classification + mode selection
                    -> [Phase 0.5] Error Type Classification
                       build/compile: fast path -> simplified HARD-GATE -> Fix
                       runtime/logic: -> Phase 0.7
                    -> [Phase 0.7] Reproduction Attempt
                       success: record conditions, proceed
                       failure: switch to log/environment analysis
                    -> [Phase 1] Root Cause Analysis (Hypothesis Loop)
                       quick: orchestrator generates 3 hypotheses
                              -> falsification (executable actions only)
                              -> loop until High confidence or max 3 rounds
                       deep:  Error Analyst + Code Archaeologist (parallel)
                              -> Cross Verification (synthesize)
                    -> HARD-GATE: Fix it / Record only / Stop
                    -> [Phase 2] Fix (optional, simple fixes only)
                    -> [Phase 3] Prevention (optional, pattern scan + smart routing)
```

### Core: Falsification Rules

Every hypothesis must be tested with **executable verification actions** -- pure reasoning-only falsification is prohibited:

1. **Physical separation**: Write hypotheses to `.harness/debug/hypotheses.md` before verification
2. **Falsification question**: "If this hypothesis is WRONG, what evidence should exist in the code?"
3. **Executable actions required** (at least 1 per hypothesis):
   - Code search (Grep/Glob) -- check for specific patterns
   - `git blame`/`git log` -- check change history
   - Test execution -- verify expected behavior
   - File read -- check configs, env vars
4. **Confidence adjusted only from evidence**, not reasoning
5. **Refuted hypotheses marked `[REFUTED]`** with evidence in hypotheses.md

### Error Type Fast Path

| Type | Signals | Action |
|------|---------|--------|
| **build/compile** | Compiler error, syntax error, missing import | Skip hypothesis loop -- compiler output is direct evidence |
| **runtime** | Exception at runtime, crash, null pointer | Reproduction attempt -> hypothesis loop |
| **logic** | Wrong output, test failure, off-by-one | Reproduction attempt -> hypothesis loop |

### Modes

| Mode | Agents | Process | Token cost |
|------|--------|---------|------------|
| **quick** | Orchestrator only | Direct hypothesis loop | ~1x |
| **deep** | Error Analyst + Code Archaeologist + Cross Verifier | Independent parallel analysis -> cross-verification | ~1.7x |

### Smart Routing (after completion)

| Signal | Suggested next step |
|--------|-------------------|
| Complex fix needed | `/workflow "Fix based on docs/harness/<slug>/root_cause.md"` |
| Regression test needed | `/test-gen --regression docs/harness/<slug>/debug_report.md` |
| Pattern to record | `/memory save` |

### Output

```
docs/harness/<slug>/
  root_cause.md      # Root cause + evidence + confidence
  fix_changes.md     # Fix details (if applied)
  debug_report.md    # Comprehensive report (root cause + fix + prevention)
```

---

## spec

Transforms vague or incomplete requirements into structured, actionable specifications through **multi-round Q&A discovery**. Output is directly compatible with `/workflow` input via section mapping.

```
/spec  -> [Setup] mode selection (quick / deep)
                  -> [Phase 1] Requirements Discovery (Multi-round Q&A)
                     Round 1: parse vague requirements -> generate up to 5 questions
                     Round 2-3: follow-up questions from new ambiguities (conditional)
                     Max 3 rounds. "Don't know" -> [unconfirmed]
                  -> [Phase 2] Spec Generation
                     quick: orchestrator writes spec directly
                     deep:  Requirements Analyst + User Scenario Analyst (parallel)
                            -> Synthesis
                  -> HARD-GATE: Approve / Modify (re-generate) / Stop
                  -> [Phase 3] Handoff: suggest /workflow with spec path
```

### Core: Multi-round Q&A

The key differentiator from `/workflow`'s Planner phase:

| Feature | /workflow Planner | /spec |
|---------|------------------|-------|
| Input | Clear requirements | Vague/incomplete requirements |
| Q&A | None | **Up to 3 rounds** with follow-up questions |
| Approach section | Included (implementation-focused) | Not included (implementation is /workflow's job) |
| Acceptance criteria | Brief checklist | **Given/When/Then format** |
| Out of Scope | Brief in Scope section | **Dedicated section** |
| Refinement | One-shot | **Modify -> regenerate loop** |

### Spec Output Format

Seven canonical sections, all translated to `user_lang`:

```
Goal -> Background & Decisions -> Scope -> Out of Scope ->
Edge Cases -> Acceptance Criteria (Given/When/Then) -> Risks
```

Maps directly to `/workflow` input: Goal->Goal, Background->Background, Scope->Scope, Acceptance Criteria->Completion Criteria, Risks->Risks, Edge Cases->Testing Strategy.

### Modes

| Mode | Agents | Token cost |
|------|--------|------------|
| **quick** | Orchestrator only | ~0.5x |
| **deep** | Requirements Analyst + User Scenario Analyst + Synthesis | ~1.3x |

---

## test-gen

Automated test generator that writes real test code, executes it, and validates meaningfulness through **simplified mutation testing**. Supports framework auto-detection, dependency-aware mocking, and regression test generation from debug reports.

```
/test-gen  -> [Setup] Framework detection + model config
                      -> [Phase 1] Analysis
                         Coverage scan (tool or static fallback)
                         + dependency analysis + mocking strategy
                         + edge case/boundary value enumeration
                      -> HARD-GATE: confirm scope + mocking strategy
                      -> [Phase 2] Generation
                         Unit tests (happy path + edge cases)
                         + integration tests (if needed)
                         + regression tests (if --regression)
                      -> [Phase 3] Verification
                         Step 1: Execute tests (up to 2 fix retries, test code only)
                         Step 2: Mutation testing (condition inversion, return change)
                                 -> trivial tests flagged + strengthen attempt
```

### Framework Auto-Detection

| Framework | Detection | Test pattern | Mock library |
|-----------|-----------|-------------|-------------|
| Jest | package.json jest dep | `*.test.ts` | jest.mock |
| Vitest | package.json vitest | `*.test.ts` | vi.mock |
| pytest | pyproject.toml / conftest.py | `test_*.py` | monkeypatch / unittest.mock |
| JUnit | build.gradle junit | `*Test.java` | Mockito |
| Go test | go.mod | `*_test.go` | testify/mock |
| RSpec | Gemfile rspec | `*_spec.rb` | rspec-mocks |

### Mocking Strategy (auto-detected per dependency)

| Dependency | Default strategy |
|-----------|-----------------|
| DB (Repository, ORM) | Repository interface mock |
| External API (HTTP) | HTTP client mock |
| File system | Temp dir or fs mock |
| Time (Date, Timer) | Fake timers |
| Environment vars | Test-specific env |

### Mutation Testing (Phase 3 quality verification)

After tests pass, each test is verified for meaningfulness:
1. Mutate target function (condition inversion, return value change, arithmetic swap)
2. Re-run test -- if it still passes, the test is **trivial** (doesn't catch real logic changes)
3. Attempt to strengthen trivial tests (1 try)
4. Revert mutation immediately after each check
5. Report quality score: meaningful / total non-skipped tests

### Flags

| Flag | Description |
|------|-------------|
| `--coverage-gap` | Auto-find and test low-coverage areas |
| `--regression <path>` | Generate regression tests from a debug report |

`--coverage-gap` and `--regression` are mutually exclusive.

### Key Rules

- **Never modify production code** -- test code only
- **Mutations always reverted** -- never leave mutated code in place
- **No trivial assertions** -- every test must have meaningful assertions

---

## memory

Team knowledge base manager. Saves, searches, and maintains **git-committed, team-shared** records of decisions, patterns, bugs, and conventions. Completely separate from Claude Code's built-in personal auto-memory.

```
/memory save     -> analyze session -> extract team-valuable items -> per-item HARD-GATE -> save
/memory show     -> scan docs/harness/memory/ -> categorized list
/memory clean    -> identify stale records -> backup -> per-item HARD-GATE -> delete
/memory search   -> grep keyword across all records
```

### How it differs from built-in auto-memory

| | Built-in auto-memory | /memory |
|-|---------------------|---------|
| **Location** | `~/.claude/projects/` | `docs/harness/memory/` |
| **Scope** | Personal, per-user | **Team-shared, git-committed** |
| **Content** | Session context, preferences | Decisions, patterns, bugs, conventions |
| **Index** | MEMORY.md | `docs/harness/memory/README.md` |
| **CLAUDE.md** | Managed by built-in | **Never touched** |

### Categories

| Category | When to save | Team value |
|----------|-------------|------------|
| `decisions` | Architecture choices, technology selections | Prevents re-litigating decisions |
| `bugs` | Non-obvious root causes, tricky debugging paths | Saves investigation time |
| `patterns` | Reusable patterns, proven approaches, anti-patterns | Accelerates future work |
| `todos` | Deferred work with context to pick up later | Enables work handoff |
| `conventions` | Naming rules, style decisions, team norms | Discoverable by new members |

Custom categories can be added freely.

### Safety

- **Per-item HARD-GATE** on both save and delete -- nothing happens without explicit confirmation
- **Backup before delete** -- `.harness/memory_backup/<timestamp>/` created before any cleanup
- **Date parse safety** -- unparseable dates excluded from staleness checks

---

## codebase-audit

A standalone utility skill that systematically analyzes project structure, dependencies, and patterns for team onboarding and codebase understanding.

```
/codebase-audit
/codebase-audit --mode deep --scope "src/**"
/codebase-audit --incremental
```

**What it does:**
- **Structure analysis**: Maps directory layout, module boundaries, entry points, and architecture patterns
- **Dependency analysis** (deep+): Internal module dependencies, circular references, external package health
- **Pattern detection** (deep+): Design patterns, naming conventions, anti-patterns, consistency assessment
- **Complexity hotspots** (deep+): Top 10 files ranked by complexity indicators
- **Incremental mode**: Reuses prior audit, analyzes only changed files since last run

### Modes

| Mode | Agents | Best for | Token cost |
|------|--------|----------|------------|
| **quick** | 1 sequential | Small projects, quick overview | 1x |
| **deep** | 2 parallel + synthesis | Mid-size projects, general analysis | ~1.5x |
| **thorough** | 3 parallel + cross-verification + synthesis | Large/legacy projects, team onboarding | ~2.5x |

Mode is auto-recommended based on file count (< 30: quick, 30-200: deep, 200+: thorough) but can be overridden with `--mode`.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| mode | (recommended) | `quick` for overview, `deep` for detailed analysis, `thorough` for comprehensive |
| scope | (full project) | Restrict analysis to a glob pattern |
| incremental | off | Reuse prior audit, analyze only changed files |

### Output

Report saved to `docs/harness/<slug>/audit_report.md` with sections:
- Project Overview, Module Map
- Dependency Graph (deep+), Pattern Analysis (deep+)
- Complexity Hotspots top 10 (deep+)
- Recommended Next Steps (smart routing to other skills)
- Metadata (git HEAD, date, mode — enables incremental)

### Smart Routing

After analysis, suggests relevant next steps based on findings:
- Anti-patterns detected -> `/refactor`
- Outdated versions -> `/migrate`
- No CLAUDE.md -> `/md-generate`

**Safety features**: Read-only (never modifies source code), no git branches created, confirmation gate for deep/thorough modes.

---

## code-review

A standalone review skill that performs systematic, bias-free code reviews on PRs, branches, commits, or file diffs.

```
/code-review #123                    # review a PR
/code-review feature/auth            # review branch diff vs main
/code-review abc1234..def5678        # review commit range
/code-review --staged                # review staged changes
/code-review #123 --mode thorough    # force thorough mode
```

**What it does:**
- **3-tier depth control**: quick (1 agent, 5-perspective checklist), deep (2 specialist sub-agents + synthesis), thorough (3 specialists + cross-verification + synthesis)
- **Bias reduction**: context isolation, anchor-free input (no PR descriptions/commit messages), defect-assumption framing, author neutralization
- **Smart scope routing**: recommends review depth based on diff size (< 100 lines -> quick, 100-500 -> deep, 500+ -> thorough)
- **Structured findings**: each finding has severity (Critical/Major/Minor/Suggestion), category, file:line, description, and concrete fix suggestion
- **Smart routing**: suggests next actions based on findings (e.g., `/workflow` for critical fixes)

### Modes

| Mode | Sub-agents | Process | Token cost |
|------|-----------|---------|------------|
| **quick** | 0 (inline) | 5-perspective checklist | ~1x |
| **deep** | 2 | Security & Correctness + Architecture & Maintainability -> synthesis | ~1.5x |
| **thorough** | 3 + 3 | Security & Correctness + Architecture & Design + DX & Maintainability -> cross-verification -> synthesis | ~2.5x |

### Deep Mode

Two specialist reviewers analyze the diff independently and in parallel:

| Reviewer | Focus |
|----------|-------|
| **Security & Correctness** | Vulnerabilities, logic errors, input validation, error handling |
| **Architecture & Maintainability** | Design patterns, code organization, testing, performance, naming |

The main agent synthesizes both reviews into a unified report, deduplicating findings and resolving severity disagreements.

### Thorough Mode

Three specialist reviewers analyze independently and in parallel, then cross-verify each other's findings:

| Reviewer | Focus |
|----------|-------|
| **Security & Correctness** | Vulnerabilities, logic errors, input validation, error handling |
| **Architecture & Design** | System structure, abstractions, coupling, API design, scalability |
| **DX & Maintainability** | Readability, naming, testing, performance, conventions |

After initial review, three cross-verification sub-agents validate each other's findings against the actual diff -- confirming real issues, flagging false positives, and catching missed problems. The main agent then synthesizes all 6 documents.

### Bias Reduction Techniques

| Technique | Applies to | Purpose |
|-----------|-----------|---------|
| Context isolation (separate sub-agents) | deep, thorough | Each reviewer forms independent judgment |
| Anchor-free input (no PR description/commit messages) | all modes | Prevents framing bias from author's narrative |
| Defect-assumption framing | all modes | "Assume defects, find them" vs. "confirm correctness" |
| Author neutralization | all modes | No author identity -> merit-based review |
| Cross-verification | thorough | Catches false positives and missed issues |

### Output

Review report saved to `docs/harness/<slug>/review_report.md` with:
- **Assessment**: APPROVE / REQUEST_CHANGES / COMMENT (deterministic from findings)
- **Findings table**: severity, category, file:line, description, suggestion
- **Statistics**: finding counts by severity
- **Smart routing**: suggests next actions based on finding patterns

### Language Support

Communicates in the user's language. Report content is in the detected language. Assessment line (`## Assessment: APPROVE/REQUEST_CHANGES/COMMENT`) stays in English for programmatic parsing.

---

## md-generate

A standalone utility skill that analyzes your project and generates/enhances CLAUDE.md for effective Claude Code development.

```
/md-generate
```

**What it does:**
- **Project analysis**: Detects language, framework, architecture pattern, dependencies, and conventions from source code
- **Command discovery**: Finds and verifies build/test/lint/dev commands from package configs and CI/CD
- **Convention detection**: Samples source files to detect naming, testing, code style, and architecture patterns
- **Gap analysis**: If CLAUDE.md already exists, identifies missing/outdated information and enhances it
- **Monorepo support**: Generates root + sub-CLAUDE.md files for monorepo workspaces

**Safety features**: Read-only analysis until confirmed, no secrets exposure, no speculative content, preserves existing CLAUDE.md content.

**Composability**: Run `/md-generate` first to create content, then `/md-optimize` to compress for token efficiency.

---

## md-optimize

A standalone utility skill that optimizes your project's CLAUDE.md and markdown files for token efficiency.

```
/md-optimize
```

**What it does:**
- **Dual-Zone CLAUDE.md model**: Splits CLAUDE.md into Inline Zone (rules that must always be in context) and Index Zone (reference paths to detailed docs)
- **Deduplication**: Hash-based exact-match detection across all `.md` files
- **Token compression**: Removes redundancy, compresses verbose prose, generates before/after token savings report
- **Smart Routing**: Detects project state and suggests `/md-generate` when CLAUDE.md is missing or thin

**Safety features**: Git-based rollback, HARD GATE confirmation before any changes, YAML frontmatter preservation, idempotency markers for safe re-runs.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full roadmap with rationale.

- **v8.1** (Shipped): Path Validator single source, Auto-fix State Transition Table (invariants I1–I4), `--verifier-model` flexibility, `--output-dir` flag, Auto-fix proposal for Layer 1 failures (both `/workflow` and `/refactor`), `.github/` contribution templates
- **v8.2+**: Custom persona override (`templates/user-override/`), GIF demo, external CLI wrapper

---

## License

MIT

## Author

Jugger
