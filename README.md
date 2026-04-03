# Agent Harness

**Zero-setup, zero-dependency** 3-Phase (Planner -> Generator -> Evaluator) development workflow for Claude Code.

No dependencies required. No Python, no pip, no build steps -- just install the plugin and go.

Inspired by Anthropic's [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps).

## What it does

Separates planning, implementation, and review into distinct phases with file-based handoffs. The Evaluator runs as an **isolated subagent** with research-backed bias reduction techniques to prevent the "self-evaluation bias" where a single agent rates its own work too favorably.

```
/agent-harness:harness  -> [Phase 1] Planner: analyze task, write spec.md
                        -> Confirmation Gate: user approves spec before proceeding
                        -> [Phase 2] Generator: implement code, write changes.md
                        -> [Phase 3] Evaluator (isolated subagent): test + review, write qa_report.md
                        -> PASS -> Done / FAIL -> Back to Phase 2 (max N rounds)
```

Claude handles everything directly -- no external CLI, no wrapper scripts. The plugin skill guides Claude through each phase natively.

## Install

```bash
claude plugin marketplace add Lee-JungGu/agent-harness
claude plugin install agent-harness@agent-harness-marketplace
```

## Usage

Once installed, use in any Claude Code session:

```
/agent-harness:harness fix login timeout bug
```

That's it. No initialization, no repo registration, no configuration files needed. The harness auto-detects your project language, test commands, and build commands from project files.

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

## How it works

1. You invoke the harness skill with a task description
2. **Setup**: Auto-detects language/test/build, detects your language, creates `.harness/state.json` and `docs/harness/<task-slug>/`, creates a `harness/*` git branch
3. **Phase 1 -- Planner**: Claude explores the codebase, analyzes the task, and writes `spec.md`
4. **Confirmation Gate**: Claude shows the spec and waits for explicit user approval before proceeding. Ambiguous responses are re-confirmed.
5. **Phase 2 -- Generator**: Claude implements the code following the spec, with scope pre-verification before writing code
6. **Phase 3 -- Evaluator** (isolated subagent): Runs as a separate agent with anchor-free input, performs pre-mortem analysis, tests, and structured code review with bias reduction techniques. Writes `qa_report.md` with a PASS/FAIL verdict
7. If FAIL, the user is asked whether to retry (up to max rounds)
8. On completion, the user is asked whether to commit the artifacts

### Evaluator Bias Reduction

The Evaluator uses 6 research-backed techniques to reduce self-evaluation bias:

| Technique | Research Basis |
|-----------|---------------|
| **Context isolation** (separate subagent) | Agent-as-a-Judge (ICLR 2025): 90.44% human agreement vs 60.38% for inline evaluation |
| **Anchor-free input** (no Generator reasoning passed) | Anchoring bias research: LLMs anchor strongly to provided context |
| **Defect-assumption framing** ("assume defects exist") | Pre-mortem (Brookings): reduces overconfidence |
| **Author neutralization** (no author identity disclosed) | PNAS 2025: LLMs favor LLM-generated content at 89% rate |
| **PASS-before-rebuttal** (must list problems before PASS) | Confirmation bias: structural forced consideration of counterevidence |
| **Rubric decomposition** (2-3 sub-checks per criterion) | G-Eval, RocketEval: finer granularity reduces evaluation bias |

### Session Recovery

If a session is interrupted, the harness detects the existing `.harness/state.json` on next invocation and offers to resume from where you left off.

### File Structure

```
.harness/
  state.json                    # Working state (temporary, cleaned up after completion)

docs/harness/<task-slug>/
  spec.md                       # Planner output
  changes.md                    # Generator output
  qa_report.md                  # Evaluator output
```

### Confirmation Gates

The Generator phase consumes significant tokens and is hard to undo. The harness enforces **explicit user confirmation** before proceeding:

- **Spec approval**: Only clear affirmatives are accepted. Ambiguous responses trigger re-confirmation.
- **QA retry**: When the Evaluator reports FAIL, the harness asks the user before starting another round.

### Language Support

The harness communicates in the **user's language** -- automatically detected from the task description. All templates are written in English for token efficiency and global compatibility, but all user-facing output (messages, spec, QA reports) is generated in the detected language. Language changes mid-conversation are also detected.

### Options

You can pass options in conversation when invoking the harness:

| Option | Default | Description |
|--------|---------|-------------|
| scope | auto-detected | Restrict file modifications to a pattern |
| max rounds | 3 | Maximum Generator/Evaluator retry cycles |
| max files | 20 | Maximum number of files that can be modified |

Example: `/agent-harness:harness fix auth bug --scope "src/auth/**" --max-rounds 5`

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

## License

MIT

## Author

Lee-JungGu
