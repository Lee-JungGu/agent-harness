# Agent Harness

3-Phase (Planner -> Generator -> Evaluator) development workflow for Claude Code.

Inspired by Anthropic's [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps).

## What it does

Separates planning, implementation, and review into distinct phases with file-based handoffs. This prevents the "self-evaluation bias" where a single agent rates its own work too favorably, and enforces structured planning before coding.

```
harness run     -> [Phase 1] Planner: analyze task, write spec.md
harness next    -> [Phase 2] Generator: implement code, write changes.md
harness next    -> [Phase 3] Evaluator: test + review, write qa_report.md
harness next    -> PASS -> Done / FAIL -> Back to Phase 2 (max N rounds)
```

## Install as Claude Code Plugin

```bash
claude plugin marketplace add Lee-JungGu/agent-harness
claude plugin install agent-harness@agent-harness-marketplace
```

Then use in any Claude Code session:

```
/agent-harness:harness fix login timeout bug
```

## Quick Start (Zero-Setup)

No initialization or repo registration required. Just run from any project directory:

```bash
# From your project directory
cd /path/to/your-project

# Start a task (language, test/build commands are auto-detected)
python /path/to/agent-harness/harness.py run --task "Add rate limiting to login API"

# After each phase, advance to the next
python /path/to/agent-harness/harness.py next
python /path/to/agent-harness/harness.py next
python /path/to/agent-harness/harness.py next  # PASS -> done / FAIL -> retry

# Check status anytime
python /path/to/agent-harness/harness.py status
```

### Auto-Detection

The harness detects language, test, and build commands from your project files:

| Detected File | Language | Test Command | Build Command |
|--------------|----------|-------------|---------------|
| `build.gradle` / `build.gradle.kts` | Java/Kotlin | `gradlew test` | `gradlew build` |
| `pom.xml` | Java | `mvn test` | `mvn compile` |
| `pyproject.toml` / `requirements.txt` | Python | `pytest` | - |
| `package.json` + `tsconfig.json` | TypeScript | `npm test` | `npm run build` |
| `package.json` (no TS) | JavaScript | `npm test` | `npm run build` |
| `*.csproj` / `*.sln` | C# | `dotnet test` | `dotnet build` |
| `go.mod` | Go | `go test ./...` | `go build ./...` |
| `Cargo.toml` | Rust | `cargo test` | `cargo build` |

If auto-detection doesn't match your setup, override with `--lang` or register the repo (see Advanced Usage).

## CLI Reference

| Command | Description |
|---------|-------------|
| `run --task "..."` | Start a new task in current directory (auto-detects everything) |
| `run --repo <name> --task "..."` | Start using a registered repo |
| `run --repo-path <path> --task "..."` | Start in a specific directory |
| `next` | Advance to next phase (uses current directory) |
| `next --repo-path <path>` | Advance in a specific directory |
| `status` | Show current task status |
| `status --repo-path <path>` | Show status for a specific directory |

### Guardrails

| Option | Default | Description |
|--------|---------|-------------|
| `--scope` | auto-detected | Restrict file modifications to a glob pattern |
| `--max-rounds` | 3 | Maximum Generator/Evaluator retry cycles |
| `--max-files` | 20 | Maximum number of files that can be modified |
| `--dry-run` | false | Run Planner only, no code changes |

## How it works

1. `harness run` auto-detects your repo, creates `.harness/` directory, a git branch, and renders the Planner prompt
2. Claude Code reads the prompt, explores the codebase, writes `spec.md`
3. `harness next` advances the state machine, renders the Generator prompt
4. Claude Code implements the code, writes `changes.md`
5. `harness next` renders the Evaluator prompt
6. Claude Code runs tests + code review, writes `qa_report.md` with PASS/FAIL
7. `harness next` parses the verdict: PASS completes, FAIL loops back to Generator

State is tracked in `.harness/state.json`. The harness creates a `harness/*` git branch automatically.

### Evaluator Modes

- **Test + Code Review**: When test commands are detected, runs tests first then reviews code
- **Code Review Only**: When no tests are available, performs thorough code review against 5 criteria

### Plugin Compatibility

Prompt templates reference skills generically (e.g. "use a brainstorming skill if available") rather than requiring specific plugins. Works with superpowers, g-stack, or any plugin that provides similar skills.

## Advanced Usage

### Register repos for custom settings

Optional. Only needed if auto-detection doesn't match or you want saved presets:

```bash
python harness.py repo add \
  --name my-backend \
  --path /path/to/my-backend \
  --lang java \
  --test-cmd "./gradlew test --tests com.example.auth.*" \
  --build-cmd "./gradlew build" \
  --default-scope "src/main/java/com/example/auth/**"

python harness.py repo list
python harness.py repo update my-backend --test-cmd "./gradlew test"
python harness.py repo remove my-backend
```

### Per-repo override file

Create `.harness.yaml` in any repo root for persistent overrides:

```yaml
test_cmd: "./gradlew test --tests com.example.auth.*"
default_scope: "src/main/java/com/example/auth/**"
evaluator:
  review_focus: ["security", "performance"]
```

### Configuration priority

CLI arguments > `.harness.yaml` (repo root) > `~/.agent-harness/repos.yaml` (registered repos)

## Project Structure

```
agent-harness/
├── .claude-plugin/
│   ├── plugin.json           # Claude Code plugin manifest
│   └── marketplace.json      # Marketplace manifest
├── skills/
│   └── harness/
│       └── SKILL.md          # Plugin skill definition
├── harness.py                # CLI entry point
├── config.py                 # Config management + auto-detection
├── state.py                  # Phase state machine
├── renderer.py               # Template rendering
├── phases/
│   ├── planner.py            # Phase 1 prompt generation
│   ├── generator.py          # Phase 2 prompt generation
│   └── evaluator.py          # Phase 3 prompt generation
├── templates/
│   ├── planner_prompt.md
│   ├── generator_prompt.md
│   └── evaluator_prompt.md
└── tests/                    # 122 tests
```
