# Agent Harness

**Zero-setup, zero-dependency** 3-Phase development workflow for Claude Code with **selectable single-agent or multi-agent persona mode**.

No dependencies required. No Python, no pip, no build steps -- just install the plugin and go.

Inspired by Anthropic's [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps).

## Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **Workflow** | `/workflow <task>` | 3-Phase (Planner -> Generator -> Evaluator) development workflow. Single or multi-agent mode. |
| **Refactor** | `/refactor <target>` | Safe, behavior-preserving code structure improvement. Single, multi, or comprehensive mode. |
| **Migrate** | `/migrate <target> [--from v4 --to v5]` | Staged migration of frameworks, libraries, and dependencies. Single or multi-agent mode with WebSearch research. |
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

| Preset | Executor | Advisor | Evaluator | Use case |
|--------|----------|---------|-----------|----------|
| **default** | (parent) | (parent) | (parent) | No change, inherit parent model |
| **all-opus** | Opus | Opus | Opus | Maximum quality |
| **balanced** | Sonnet | Opus | Opus | Recommended — cost-efficient with quality judgment |
| **economy** | Haiku | Sonnet | Sonnet | Maximum savings, basic quality |

**Role mapping across all skills:**
- **Executor**: bulk work — analysis, code generation, proposals (cheaper model OK)
- **Advisor**: high-level judgment — plan review, safety checks (quality model needed)
- **Evaluator**: independent verification — always protected (never haiku)

Works with: workflow, refactor, migrate, code-review, codebase-audit. Presets are selected via numbered UI (AskUserQuestion) with `Other` for custom role mapping.

## Interactive UX

All user-facing prompts use **AskUserQuestion** — a numbered selection UI where you pick by number instead of typing keywords. Every prompt includes descriptive options and an automatic `Other` option for free text input.

Key interaction points:
- **Mode selection**: numbered options with token cost hints and auto-recommendation
- **Confirmation gates**: Proceed / Modify / Stop (replaces freeform text approval)
- **QA retry**: Fix / Accept as-is
- **Commit**: 3 options — "Commit code only" (recommended) / "Commit all with artifacts" / "No commit"
- **Session recovery**: Resume / Restart / Stop

Falls back to text-based input when AskUserQuestion is unavailable.

---

## workflow

Separates planning, implementation, and review into distinct phases with file-based handoffs. Each phase uses **specialized sub-agents with expert personas** that collaborate through structured debate and review patterns, eliminating single-agent blind spots.

```
/workflow  -> [Setup] Auto-detect + mode selection (single / standard / multi)
                        -> [Phase 1] Planner
                           single:   1 agent explores + writes spec.md
                           standard: 2 specialists propose independently
                                     -> Synthesis: merge into spec.md (no cross-critique)
                           multi:    3 specialists propose independently
                                     -> Cross-critique: each reviews others
                                     -> Synthesis: merge into spec.md
                        -> Confirmation Gate: user approves spec
                        -> [Phase 2] Generator
                           single:   1 agent implements code
                           standard: Lead Developer creates plan
                                     -> 1 combined advisor reviews plan
                                     -> Lead Developer codes with feedback
                           multi:    Lead Developer creates plan
                                     -> 2 advisors review plan in parallel
                                     -> Lead Developer codes with feedback
                        -> [Phase 3] Evaluator (isolated subagent): test + review
                        -> PASS -> Done / FAIL -> Back to Phase 2 (max N rounds)
```

Claude handles everything directly -- no external CLI, no wrapper scripts. The plugin skill guides Claude through each phase natively.

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

### How it works

1. You invoke the harness skill with a task description
2. **Setup**: Auto-detects language/test/build, detects your language, creates `.harness/state.json` and `docs/harness/<task-slug>/`, creates a `harness/*` git branch

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

#### Phase 3 -- Evaluator (Isolated)

Runs as an isolated sub-agent with research-backed bias reduction:

| Technique | Research Basis |
|-----------|---------------|
| **Context isolation** (separate subagent) | Agent-as-a-Judge (ICLR 2025): 90.44% human agreement vs 60.38% for inline evaluation |
| **Anchor-free input** (no Generator reasoning passed) | Anchoring bias research: LLMs anchor strongly to provided context |
| **Defect-assumption framing** ("assume defects, 2 pre-mortem hypotheses") | Pre-mortem (Brookings): reduces overconfidence |
| **Author neutralization** (no author identity disclosed) | PNAS 2025: LLMs favor LLM-generated content at 89% rate |
| **Risk-before-PASS** (identify key risks + verify with code evidence) | Confirmation bias: structural forced consideration of counterevidence |
| **Rubric decomposition** (5 criteria with inline sub-checks) | G-Eval, RocketEval: finer granularity reduces evaluation bias |

7. If FAIL, the user is asked whether to retry (up to max rounds)
8. On completion, the user is asked whether to commit the artifacts

### Token Cost vs. Quality Trade-off

| Mode | Best for | Token cost | Quality vs single |
|------|----------|------------|-------------------|
| **single** | Small bug fixes, simple features, quick iterations | Baseline | Baseline |
| **standard** | General features, API changes, moderate complexity | ~1.5x baseline | +60-70% |
| **multi** | Complex features, architectural changes, high-stakes code | ~2-2.5x baseline | +85-95% |

Higher modes use more tokens per run but have higher first-pass success rates, often reducing total cost by avoiding retry rounds. Standard mode is recommended for most tasks — it provides significant quality improvement at modest token cost.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| mode | (ask user) | `single` for fast/token-saving, `standard` for balanced analysis, `multi` for deep multi-agent analysis |
| model-config | (ask user) | `default` / `all-opus` / `balanced` / `economy` — see Model Configuration section |
| scope | auto-detected | Restrict file modifications to a pattern |
| max rounds | 3 | Maximum Generator/Evaluator retry cycles |
| max files | 20 | Maximum number of files that can be modified |

Example: `/workflow fix auth bug --mode single --model-config balanced --scope "src/auth/**"`

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
  qa_report.md                      # Evaluator output (preserved)
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
2. **Setup**: Auto-detects current version, researches target version, captures baseline tests, creates a `harness/migrate-*` git branch

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

## License

MIT

## Author

Jugger
