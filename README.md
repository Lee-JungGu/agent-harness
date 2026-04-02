# Agent Harness

Agent Harness is a 3-Phase development workflow framework for Claude Code, designed to systematically guide AI-assisted development through planning, implementation, and evaluation cycles.

## Features

- **3-Phase Workflow**: Planner (spec) → Generator (code) → Evaluator (QA)
- **Repository Management**: Register and manage multiple project configurations
- **State Machine**: Tracks workflow state and prevents out-of-order operations
- **Guardrails**: Configurable limits on rounds, file changes, and scope
- **Git Integration**: Automatic branch creation and safety checks
- **Flexible Configuration**: CLI args override .harness.yaml, which overrides repos.yaml

## Install

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# 1. Initialize harness configuration directory
harness init

# 2. Register a repository
harness repo add --name my-project \
  --path /path/to/repo \
  --lang python \
  --test-cmd pytest

# 3. Start a new task (Phase 1: Planner)
harness run --repo my-project --task "Add user authentication"

# 4. After Claude writes spec.md, advance to Phase 2
harness next --repo-path /path/to/repo

# 5. After Claude writes changes.md, advance to Phase 3
harness next --repo-path /path/to/repo

# 6. After Claude writes qa_report.md, finalize
harness next --repo-path /path/to/repo

# 7. Check workflow status at any time
harness status --repo-path /path/to/repo
```

## Workflow Diagram

```
harness run         → [Phase 1: Planner]
                      Human provides task description
                      Claude writes spec.md to .harness/
                      ↓
harness next        → [Phase 2: Generator]
                      Claude implements changes
                      Claude writes changes.md to .harness/
                      ↓
harness next        → [Phase 3: Evaluator]
                      Claude runs tests/QA checks
                      Claude writes qa_report.md to .harness/
                      ↓
harness next        → Verdict?
                      PASS: Done, merge to main
                      FAIL: Back to Phase 2 (if rounds remain)
```

## CLI Reference

### init

Initialize the Agent Harness configuration directory at `~/.agent-harness/`.

```bash
harness init
```

**Output:**
- Creates `~/.agent-harness/repos.yaml` (global repository registry)
- Idempotent: safe to run multiple times

### repo

Manage registered repositories.

```bash
# Add a repository
harness repo add \
  --name my-project \
  --path /path/to/repo \
  --lang python \
  --test-cmd pytest \
  --build-cmd "python setup.py build" \
  --default-scope "src/**/*.py"

# List all registered repositories
harness repo list

# Update a repository configuration
harness repo update my-project --test-cmd "pytest -v"

# Remove a repository
harness repo remove my-project
```

**Arguments:**
- `--name` (required for add/remove/update): Repository identifier
- `--path` (required for add): Absolute path to repository
- `--lang` (required for add): Primary language (python, java, csharp, typescript, javascript, etc.)
- `--test-cmd`: Command to run tests (e.g., `pytest`, `./gradlew test`, `npm test`)
- `--build-cmd`: Command to build/compile (e.g., `./gradlew build`, `cargo build`)
- `--default-scope`: Default file scope pattern (e.g., `src/**/*.py`, `app/**/*.ts`)

### run

Start a new harness task (Phase 1: Planner).

```bash
# Using a registered repository
harness run --repo my-project --task "Add user authentication"

# Using a direct path (when repo not registered)
harness run --repo-path /path/to/repo \
  --lang python \
  --task "Implement REST API" \
  --scope "api/**/*.py" \
  --max-rounds 5 \
  --max-files 25 \
  --dry-run
```

**Arguments:**
- `--repo` or `--repo-path` (mutually exclusive, one required): Repository identifier or path
- `--task` (required): Clear description of the work to be done
- `--lang` (required with --repo-path): Primary language
- `--scope`: Override default file scope pattern for this task
- `--max-rounds`: Maximum evaluation cycles (default: 3)
- `--max-files`: Maximum files to modify (default: 20)
- `--dry-run`: Render planner prompt only, do not write state

**Output:**
- Creates `.harness/` directory in repository root
- Generates `.harness/harness_state.json` (workflow state)
- Renders `.harness/phase1_planner.md` (planner prompt for Claude)
- Creates feature branch: `harness/<task-slug>`

### next

Advance workflow to the next phase.

```bash
# Use current directory (if .harness/ exists)
harness next

# Specify repository path
harness next --repo-path /path/to/repo
```

**Behavior:**
- Detects current phase from `harness_state.json`
- Validates required input files (spec.md, changes.md, qa_report.md)
- Advances state machine and renders next phase prompt
- Prints instructions for Claude

**Phases:**
1. **Planner**: Waiting for spec.md → generates generator prompt
2. **Generator**: Waiting for changes.md → generates evaluator prompt
3. **Evaluator**: Waiting for qa_report.md → finalizes or loops to Phase 2

### status

Display current workflow status.

```bash
harness status
harness status --repo-path /path/to/repo
```

**Output:**
- Task description
- Repository name and path
- Current phase and round
- Scope and branch
- Max rounds

## Guardrails

Agent Harness enforces limits to prevent unbounded development:

| Guardrail | CLI Flag | Config Key | Default | Purpose |
|-----------|----------|-----------|---------|---------|
| File Scope | `--scope` | `default_scope` | (none) | Restrict Claude to specified files (glob pattern) |
| Max Rounds | `--max-rounds` | (N/A) | 3 | Evaluation cycles before FAIL verdict |
| Max Files | `--max-files` | (N/A) | 20 | Cumulative files to modify across all rounds |
| Dry Run | `--dry-run` | (N/A) | false | Render prompt only, don't commit state |

**Configuration Priority:** CLI > .harness.yaml > repos.yaml > Default

Example with guardrails:
```bash
harness run --repo my-project \
  --task "Bug fix: race condition in worker pool" \
  --scope "src/worker/**/*.py" \
  --max-rounds 2 \
  --max-files 5
```

## Repository Management

### Registration

Register a repository once, then reference by name in `harness run`:

```bash
harness repo add --name backend \
  --path /home/user/projects/backend \
  --lang python \
  --test-cmd pytest \
  --default-scope "app/**/*.py"

harness run --repo backend --task "Add caching layer"
```

### Location

Repository registry stored at: **`~/.agent-harness/repos.yaml`**

Example repos.yaml:
```yaml
repos:
  backend:
    path: /home/user/projects/backend
    lang: python
    test_cmd: pytest
    build_cmd: null
    default_scope: app/**/*.py
    test_available: true
  frontend:
    path: /home/user/projects/frontend
    lang: typescript
    test_cmd: npm test
    build_cmd: npm run build
    default_scope: src/**/*.ts
    test_available: true
```

## Configuration Priority

Agent Harness applies configuration in this order (later overrides earlier):

1. **Default**: Built-in defaults (max_rounds=3, max_files=20)
2. **repos.yaml**: `~/.agent-harness/repos.yaml` global registry
3. **.harness.yaml**: `.harness.yaml` in repo root (optional, local overrides)
4. **CLI Arguments**: Command-line flags (highest priority)

Example with all layers:

```yaml
# repos.yaml
repos:
  myapp:
    path: /path/to/myapp
    lang: python
    test_cmd: pytest
    default_scope: src/**/*.py
```

```yaml
# /path/to/myapp/.harness.yaml (optional override)
max_rounds: 5
max_files: 25
```

```bash
# CLI args (final override)
harness run --repo myapp --task "..." --max-rounds 2 --scope "src/core/**/*.py"
```

Result: max_rounds=2 (CLI wins), default_scope="src/core/**/*.py" (CLI wins), test_cmd=pytest (from repos.yaml)

## Workflow Output

After each phase, Claude writes documentation to `.harness/`:

```
.harness/
├── harness_state.json          # State machine (internal)
├── phase1_planner.md           # Planner prompt (for Claude, Phase 1)
├── spec.md                     # Spec output (Claude writes, human reviews)
├── phase2_generator.md         # Generator prompt (Phase 2)
├── changes.md                  # Implementation plan (Claude writes)
├── phase3_evaluator.md         # Evaluator prompt (Phase 3)
└── qa_report.md                # QA results & verdict (Claude writes)
```

## Examples

### Example 1: Fix a Bug in Python Project

```bash
harness repo add --name myapp --path ~/projects/myapp --lang python --test-cmd pytest

harness run --repo myapp --task "Fix race condition in database connection pool" --scope "src/db/**/*.py" --max-rounds 2

# Claude opens new session, reads phase1_planner.md, writes spec.md
harness next --repo-path ~/projects/myapp

# Claude reads phase2_generator.md, writes changes.md and commits
harness next --repo-path ~/projects/myapp

# Claude reads phase3_evaluator.md, runs tests, writes qa_report.md
harness next --repo-path ~/projects/myapp

# If PASS: Done. If FAIL and rounds remain: back to Phase 2
```

### Example 2: Add Feature with Dry Run

```bash
harness run --repo my-project \
  --task "Add dark mode toggle" \
  --dry-run

# Renders prompt without creating .harness/ state
# Useful for previewing the prompt before committing
```

### Example 3: Ad-Hoc Task (No Pre-Registration)

```bash
harness run --repo-path /tmp/experimental-repo \
  --lang rust \
  --task "Optimize hot loop with SIMD" \
  --max-rounds 1
```

## Troubleshooting

### ".harness/ already exists"

The workflow is already in progress. Use `harness next` to continue, or delete `.harness/` to start fresh.

```bash
harness status --repo-path /path/to/repo
harness next --repo-path /path/to/repo
```

### "repos.yaml not found"

Initialize the configuration directory:

```bash
harness init
```

### ".harness/ not found"

Ensure you're running `harness next` or `harness status` from the correct repository directory, or use `--repo-path`:

```bash
harness status --repo-path /path/to/repo
```

### Missing phase prompt files

Claude must write the required output file (spec.md, changes.md, qa_report.md) before advancing. Check `.harness/` directory for existing files.

## Architecture

- **harness.py**: CLI entry point and command handlers
- **config.py**: Repository registry and configuration loading
- **state.py**: Workflow state machine and phase management
- **phases/**: Phase prompts (planner, generator, evaluator)
- **renderer.py**: Template rendering utilities

Agent Harness is designed to be extended with additional phases, guardrails, and integrations.
