# Agent Harness

**Zero-setup, zero-dependency** 3-Phase (Planner -> Generator -> Evaluator) development workflow for Claude Code.

No dependencies required. No Python, no pip, no build steps -- just install the plugin and go.

Inspired by Anthropic's [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps).

## What it does

Separates planning, implementation, and review into distinct phases with file-based handoffs. This prevents the "self-evaluation bias" where a single agent rates its own work too favorably, and enforces structured planning before coding.

```
/agent-harness:harness  -> [Phase 1] Planner: analyze task, write spec.md
                        -> [Phase 2] Generator: implement code, write changes.md
                        -> [Phase 3] Evaluator: test + review, write qa_report.md
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
| `build.gradle` / `build.gradle.kts` | Java/Kotlin | `gradlew test` | `gradlew build` |
| `pom.xml` | Java | `mvn test` | `mvn compile` |
| `pyproject.toml` | Python | `pytest` | - |
| `package.json` + `tsconfig.json` | TypeScript | `npm test` | `npm run build` |
| `package.json` (no TS) | JavaScript | `npm test` | `npm run build` |
| `*.csproj` / `*.sln` | C# | `dotnet test` | `dotnet build` |
| `go.mod` | Go | `go test ./...` | `go build ./...` |
| `Cargo.toml` | Rust | `cargo test` | `cargo build` |

## How it works

1. You invoke the harness skill with a task description
2. **Phase 1 -- Planner**: Claude explores the codebase, analyzes the task, and writes `spec.md` with a detailed implementation plan
3. **Phase 2 -- Generator**: Claude implements the code following the spec, and writes `changes.md` documenting what was done
4. **Phase 3 -- Evaluator**: Claude runs tests and performs code review, writes `qa_report.md` with a PASS/FAIL verdict
5. If FAIL, the workflow loops back to the Generator phase (up to N rounds)

State is tracked in `.harness/state.json`. The harness creates a `harness/*` git branch automatically.

### Evaluator Modes

- **Test + Code Review**: When test commands are detected, runs tests first then reviews code
- **Code Review Only**: When no tests are available, performs thorough code review against 5 criteria

### Plugin Compatibility

Prompt templates reference skills generically (e.g. "use a brainstorming skill if available") rather than requiring specific plugins. Works with superpowers, g-stack, or any plugin that provides similar skills.

### Guardrails

| Option | Default | Description |
|--------|---------|-------------|
| `--scope` | auto-detected | Restrict file modifications to a glob pattern |
| `--max-rounds` | 3 | Maximum Generator/Evaluator retry cycles |
| `--max-files` | 20 | Maximum number of files that can be modified |
| `--dry-run` | false | Run Planner only, no code changes |

### Per-repo override file

Create `.harness.yaml` in any repo root for persistent overrides:

```yaml
test_cmd: "./gradlew test --tests com.example.auth.*"
default_scope: "src/main/java/com/example/auth/**"
evaluator:
  review_focus: ["security", "performance"]
```

## License

MIT

## Author

Lee-JungGu
