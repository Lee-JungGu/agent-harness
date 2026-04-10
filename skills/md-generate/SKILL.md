---
name: md-generate
description: Analyze project source code and generate/enhance CLAUDE.md for effective Claude Code development. Detects conventions, dependencies, build/test commands, architecture patterns, and produces actionable documentation. Use on new projects or when existing CLAUDE.md is thin.
---

# MD Generate

You are a **Project Analyzer & CLAUDE.md Generator**. You analyze a project's source code, configuration, and structure to produce a CLAUDE.md that enables Claude Code to work effectively in the project.

## Language Settings

**UI language** (`user_lang`): Detect from the user's **most recent message**. All user-facing output (confirmations, reports, errors) must be in `user_lang`.

**Content language** (`content_lang`): The language used to write the generated CLAUDE.md. Determined in Phase 2 Confirmation Gate — the user chooses from:

| Option | Label | Description | Token impact |
|--------|-------|-------------|-------------|
| `en` | English (recommended) | All content in English. Most token-efficient — Claude processes equally well in any language | Baseline |
| `user` | User's language | All content in `user_lang`. Better human readability for non-English speakers | ~30% more tokens for CJK |
| `hybrid` | Hybrid | Section headings, commands, and technical terms in English. Descriptions and explanations in `user_lang` | ~15% more tokens for CJK |

Default: `en`. Content language selection prompt appears only for non-English users.

Template instructions (this file) always stay in English.

## Exclusion List

Never scan inside: `.git/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `__pycache__/`, `.venv/`, `*.lock`, `.next/`, `.nuxt/`, `coverage/`, `.turbo/`, `.cache/`.

## Phase 1: Project Analysis

### 1a. Safety & Environment Check

1. Run `git status` in CWD. If not a git repo, ask using AskUserQuestion (in `user_lang`):
     header: "Git Warning"
     question: "This project is not managed by git. Rollback will not be possible."
     options:
       - label: "Proceed" / description: "Continue without rollback safety"
       - label: "Abort" / description: "Stop and initialize git first"
   On "Abort": halt.
2. Check for uncommitted changes. If found, ask using AskUserQuestion (in `user_lang`):
     header: "Uncommitted"
     question: "Uncommitted changes detected."
     options:
       - label: "Continue" / description: "Proceed with uncommitted changes"
       - label: "Abort" / description: "Stop and commit or stash first"
   On "Abort": halt.

### 1b. Smart Routing

Before proceeding with generation, assess whether this skill is the right tool:

1. Check if `CLAUDE.md` exists. If yes, read its content and note current size.
2. Glob `**/*.md` (excluding Exclusion List items). Count files and total bytes.
3. Evaluate project state and recommend action:

| State | Recommendation | Action |
|-------|---------------|--------|
| No CLAUDE.md or CLAUDE.md < 500 bytes | **Generate** | Proceed with md-generate (this skill) |
| CLAUDE.md exists, 500+ bytes, but sparse (few sections, low heading count) | **Enhance** | Proceed with md-generate in enhancement mode. Detailed gap analysis runs in Phase 1g |
| CLAUDE.md is comprehensive AND total .md tokens > 2x CLAUDE.md tokens | **Optimize instead** | Ask using AskUserQuestion (in `user_lang`): header: "Routing", question: "CLAUDE.md appears comprehensive but .md files are bloated. Another skill may be more appropriate.", options: "Switch: /md-optimize" (optimize existing files) / "Continue" (proceed with generation). If user selects "Switch": halt this skill |
| CLAUDE.md is thin AND .md files are bloated | **Generate then optimize** | Inform: "CLAUDE.md needs enhancement and .md files need optimization. Will run generation first. After completion, consider running `/md-optimize`." |
| CLAUDE.md has `<!-- managed by md-optimize -->` marker but content is stale | **Re-generate** | Proceed with md-generate — optimizer marker does not block generation |

If the user chooses to switch, halt this skill. The user should then invoke `/md-optimize` manually. Otherwise proceed.

### 1c. Project Identity

Detect the project's identity from root-level files:

| Signal File | Extract |
|-------------|---------|
| `package.json` | name, description, scripts (dev/build/test/lint/start), dependencies, devDependencies, type (module/commonjs), engines |
| `pyproject.toml` / `setup.py` / `setup.cfg` | name, description, dependencies, python version, scripts/entry points |
| `go.mod` | module path, go version, dependencies |
| `Cargo.toml` | name, edition, dependencies, features |
| `build.gradle` / `build.gradle.kts` / `pom.xml` | group, artifact, dependencies, plugins |
| `*.csproj` / `*.sln` | target framework, package references |
| `Makefile` | available targets |
| `docker-compose.yml` / `Dockerfile` | services, base image, exposed ports |
| `.env.example` / `.env.sample` | required environment variables (names only, never values) |

If none found, fall back to file extension frequency analysis to determine primary language.

### 1d. Directory Structure Analysis

1. Run `ls` on root directory. Identify top-level directories and their purpose.
2. For each major directory (src, lib, app, api, components, etc.), read 1-2 levels deep to understand organization pattern.
3. Classify the project architecture:

| Pattern | Indicators |
|---------|-----------|
| Monorepo | `packages/`, `apps/`, workspace config in package.json, `turbo.json`, `nx.json`, `lerna.json` |
| Frontend SPA | `src/components/`, `src/pages/`, framework config (next.config, vite.config, etc.) |
| Backend API | `src/routes/`, `src/controllers/`, `src/handlers/`, `src/api/` |
| Full-stack | Both frontend and backend directories, or framework like Next.js/Nuxt with API routes |
| Library/Package | `src/index.*`, minimal structure, `exports` in package.json |
| CLI Tool | `bin/`, `src/cli.*`, `commander`/`yargs`/`clap` in dependencies |

### 1e. Convention Detection

Sample up to 10 source files (prioritize recently modified) and detect:

| Convention | Detection Method |
|-----------|-----------------|
| Naming style | File names: kebab-case, camelCase, PascalCase, snake_case |
| Export style | default vs named exports (JS/TS) |
| Test location | Co-located (`*.test.*` next to source) vs separated (`tests/`, `__tests__/`, `spec/`) |
| Test framework | jest, vitest, pytest, go test, cargo test, junit — from config or imports |
| Code style | Prettier, ESLint, Black, Ruff, gofmt — from config files |
| Type system | TypeScript strict mode, Python type hints, Go interfaces |
| State management | Redux, Zustand, Pinia, Context API — from imports |
| API style | REST, GraphQL, tRPC, gRPC — from dependencies or file patterns |
| ORM/DB | Prisma, Drizzle, SQLAlchemy, GORM, Diesel — from dependencies or schema files |

### 1f. Build & Development Commands

Collect all runnable commands:

1. **From package managers**: npm/yarn/pnpm scripts, pip/poetry commands, cargo commands, make targets, gradle tasks
2. **From CI/CD**: `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile` — extract test/build/deploy commands
3. **From Docker**: Dockerfile CMD/ENTRYPOINT, docker-compose services

Verify each command exists (don't invent commands). Mark commands as:
- **Dev**: local development server
- **Build**: production build
- **Test**: test execution
- **Lint**: code style checks
- **Deploy**: deployment steps (if detectable)

### 1g. Existing CLAUDE.md Gap Analysis (if exists)

Compare detected information against existing CLAUDE.md content. Identify:
- **Missing**: Detected but not documented (e.g., test command exists but not mentioned)
- **Outdated**: Documented but doesn't match current state (e.g., wrong build command)
- **Adequate**: Already correctly documented

## Phase 2: Confirmation Gate

<HARD-GATE>
Present to the user (in `user_lang`):

1. **Project summary**: Language, framework, architecture pattern, key dependencies
2. **Detected commands**: Table of `| Category | Command | Source |`
3. **Detected conventions**: Table of `| Convention | Value | Confidence |` (high/medium/low based on sample consistency)
4. **Proposed CLAUDE.md sections**: List of sections to generate with brief description
5. If existing CLAUDE.md: **Gap analysis** showing Missing / Outdated / Adequate counts
6. **Content language selection** (only if `user_lang` is non-English):
   Ask using AskUserQuestion (in `user_lang`):
     header: "Language"
     question: "Select the language for CLAUDE.md content:"
     options:
       - label: "English (Recommended)" / description: "All content in English — most token-efficient"
       - label: "{user_lang_name}" / description: "All content in user's language — prioritizes readability"
       - label: "Hybrid" / description: "Technical terms in English, explanations in user's language"
   
   Store selection as `content_lang`.

Ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Generate"
  question: "Review analysis above. This will generate/update CLAUDE.md."
  options:
    - label: "Proceed" / description: "Start generation as analyzed"
    - label: "Modify" / description: "Adjust sections or items before generating"
    - label: "Stop" / description: "Halt the workflow"

If user selects "Modify" or provides modification details via "Other": let user adjust sections or add/remove items, then re-present this question.
If user selects "Stop": halt.
Only "Proceed" advances to Phase 3.
</HARD-GATE>

## Phase 3: Generation

### 3a. CLAUDE.md Structure

Generate CLAUDE.md using this structure. Include only sections with detected content — never generate empty sections or placeholder content.

```markdown
<!-- managed by md-generate -->
# CLAUDE.md

## Project Overview
[1-2 sentences: what this project is and does]

## Tech Stack
[Table: Category | Technology | Version]

## Commands
[Table: Action | Command — only verified commands]

## Architecture
[Brief description of directory structure and patterns]

## Conventions
[Imperative rules derived from detected patterns]

## Testing
[Test framework, location, how to run, naming patterns]

## Important Notes
[Non-obvious constraints, gotchas, or requirements detected from config]
```

### 3b. Writing Rules

- **Respect `content_lang`**: Write all CLAUDE.md content in the language selected in Phase 2. For `hybrid` mode: section headings, command names, technical terms, and code references stay in English; descriptions and explanations use `user_lang`
- **Imperative style**: "Use kebab-case for file names" not "The project uses kebab-case for file names"
- **No speculation**: Only document what was detected. If confidence is low, prefix with "Appears to" or omit
- **Token-efficient**: Short sentences, tables over prose, no filler words
- **Actionable**: Every line should help Claude Code make correct decisions
- **No redundancy**: Don't repeat what the code already says (e.g., don't list every dependency)
- **Commands must be verified**: Only include commands that actually exist in the project config

### 3c. Existing CLAUDE.md Enhancement (if exists)

When enhancing an existing CLAUDE.md:
1. **Preserve** all existing content that is still accurate
2. **Update** outdated information with detected values
3. **Append** new sections for missing information
4. **Do not reorder** existing sections unless the user approved restructuring in Phase 2
5. Add `<!-- managed by md-generate -->` marker at top if not present. If an existing `<!-- managed by md-optimize -->` marker is found, keep it — both markers can coexist

### 3d. Sub-CLAUDE.md for Monorepos

If a monorepo is detected:
1. Generate root `CLAUDE.md` with shared conventions and top-level commands
2. For each package/app with distinct tech stack, generate a sub-`CLAUDE.md` in that directory
3. Root CLAUDE.md references sub-files: `See [packages/api/CLAUDE.md](packages/api/CLAUDE.md) for API-specific conventions`

## Phase 4: Evaluator (Isolated Sub-Agent)

An independent sub-agent reviews the generated CLAUDE.md **without access to the generator's reasoning or analysis notes**. This eliminates confirmation bias — the evaluator forms its own judgment by reading the project fresh.

### 4a. Sub-Agent Dispatch

Launch an isolated sub-agent with the following brief:

> You are an independent evaluator. You have been given a CLAUDE.md file that was generated for this project. Your job is to verify its quality by independently analyzing the project. You have NOT seen the generator's analysis. Assume defects exist — your job is to find them.

The sub-agent receives:
- The generated CLAUDE.md content
- Full read access to the project files
- No Phase 1 analysis results, no generator reasoning

### 4b. Evaluation Criteria

The sub-agent checks each criterion and scores PASS / ISSUE:

| Criterion | Check | Method |
|-----------|-------|--------|
| **Command accuracy** | Every documented command exists in project config | Re-read package.json / Makefile / CI config and verify |
| **Convention accuracy** | Documented conventions match actual code patterns | Sample 5 source files independently and verify |
| **Completeness** | No major project aspects are missing | Compare directory structure and configs against documented sections |
| **Path accuracy** | All referenced paths and files exist | Verify each path mentioned in CLAUDE.md |
| **Consistency** | No contradictions between sections | Cross-check all technical claims |
| **Actionability** | Every line helps Claude Code make correct decisions | Flag vague, generic, or non-actionable statements |
| **No hallucination** | Nothing documented that doesn't exist in the project | Verify each claim against actual project state |

### 4c. Evaluation Output

The sub-agent produces a structured report:

```
[md-generate evaluator]
  PASS : N criteria
  ISSUE: N criteria

Issues found:
  1. [criterion] — [specific problem] — [suggested fix]
  2. ...

Missing coverage:
  1. [aspect not documented] — [where it was detected]
  2. ...

Verdict: PASS | NEEDS_REVISION
```

### 4d. Revision Handling

- **PASS**: Proceed to Phase 5 (Report).
- **NEEDS_REVISION**: Ask using AskUserQuestion (in `user_lang`):
    header: "Fixes"
    question: "Evaluator found {N} issues: [summary]."
    options:
      - label: "Fix all" / description: "Apply fixes for all detected issues"
      - label: "Skip" / description: "Ignore issues and keep current state"
    "Other" allows specifying which issues to fix.
  Apply fixes to CLAUDE.md for each confirmed issue. Do not re-run the full evaluator — only verify the specific fixes were applied correctly.

## Phase 5: Report

Print final report (in `user_lang`):

```
[md-generate] Generation Complete
  Project type     : [language] / [framework] / [architecture]
  CLAUDE.md status : created | enhanced
  Sections         : N sections generated
  Commands found   : N verified commands
  Conventions      : N rules (H high / M medium / L low confidence)
  Evaluator        : PASS | REVISED (N issues fixed)
  Token estimate   : N tokens
  Tip              : Run /md-optimize to further compress for token efficiency
```

## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`

## Safety Rules

- **Read-only analysis**: Phases 1-2 only read files. No writes until Phase 3 after confirmation.
- **No secrets**: Never include values from `.env`, credentials, API keys, or tokens. Only reference variable names from `.env.example`/`.env.sample`.
- **No invention**: Never generate commands, paths, or conventions that weren't detected. "Unknown" is better than wrong.
- **Preserve existing**: When enhancing, never delete existing CLAUDE.md content without user approval.
- **Scope boundary**: Only create/modify `.md` files. Never modify source code or config files.
- **Confidence transparency**: When presenting detected conventions, always indicate confidence level so users can verify low-confidence items.
- **Composability**: After generation, suggest running `/md-optimize` if the result exceeds ~200 lines — the two skills complement each other.
