# Remove Python Dependency - Pure SKILL.md Plugin

## Summary

agent-harness plugin에서 Python 의존성을 완전히 제거하고, superpowers 스킬처럼 순수 SKILL.md 기반으로 전환한다. Claude가 모든 워크플로우 로직(auto-detect, 상태 관리, 템플릿 해석, 페이즈 전환)을 직접 수행한다.

## Motivation

- Python이 설치되지 않은 환경에서 플러그인 사용 불가 (Windows Store 스텁 문제 등)
- superpowers와 같은 순수 스킬 기반 플러그인이 이식성과 유지보수 면에서 우수
- 외부 의존성(pyyaml) 제거로 설치 단순화

## Architecture

### Before

```
SKILL.md -> python harness.py -> config.py / state.py / renderer.py / phases/*.py
```

### After

```
SKILL.md -> Claude가 직접 수행 (bash + Read/Write/Glob 도구)
```

## Plugin Structure (After)

```
agent-harness/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── harness/
│       └── SKILL.md            # All workflow logic
├── templates/
│   ├── planner_prompt.md       # Claude reads and interprets directly
│   ├── generator_prompt.md
│   └── evaluator_prompt.md
└── README.md
```

### Deleted

- `harness.py`, `config.py`, `state.py`, `renderer.py`
- `phases/` directory (planner.py, generator.py, evaluator.py)
- `requirements.txt`
- `tests/` directory

## Responsibility Migration

| Python Module | After (Claude) |
|---------------|----------------|
| `config.auto_detect_repo()` | Claude scans with Glob for build files (build.gradle, pom.xml, package.json, etc.) |
| `state.json` read/write | Claude uses Read/Write tools for JSON |
| `_slugify()` | SKILL.md specifies rules, Claude generates slug |
| `git checkout -b` | Claude runs bash directly |
| `renderer.render_template()` | Claude reads template, interprets variables inline |
| Phase transition logic | State machine rules in SKILL.md |
| QA verdict parsing | Claude reads qa_report.md, judges PASS/FAIL |

## File Storage

### Working State (temporary)

```
<repo>/.harness/
  └── state.json
```

Cleaned up after task completion.

### Artifacts (persistent, per task)

```
<repo>/docs/harness/<task-slug>/
  ├── spec.md
  ├── changes.md
  └── qa_report.md
```

Commit is optional - user is asked at task completion.

## state.json Schema

```json
{
  "task": "string",
  "repo_name": "string",
  "repo_path": "string",
  "phase": "plan_ready | gen_ready | eval_ready | completed",
  "round": 1,
  "scope": "string",
  "max_rounds": 3,
  "max_files": 20,
  "branch": "harness/<slug>",
  "lang": "string",
  "test_cmd": "string | null",
  "build_cmd": "string | null",
  "docs_path": "docs/harness/<slug>/",
  "created_at": "ISO8601"
}
```

## State Machine

```
plan_ready  --[spec.md exists]-->  gen_ready
gen_ready   --[changes.md exists]--> eval_ready
eval_ready  --[qa_report PASS]--> completed
eval_ready  --[qa_report FAIL + rounds left]--> gen_ready (round++)
eval_ready  --[qa_report FAIL + max rounds]--> completed (with failure)
```

## Auto-Detection Rules

Claude scans the repo root for:

| File | Language | Test Command | Build Command |
|------|----------|-------------|---------------|
| `build.gradle` / `build.gradle.kts` | java | `./gradlew test` | `./gradlew build` |
| `pom.xml` | java | `mvn test` | `mvn compile` |
| `pyproject.toml` / `setup.py` | python | `pytest` | - |
| `package.json` | typescript/javascript | `npm test` | `npm run build` |
| `*.csproj` | csharp | `dotnet test` | `dotnet build` |
| `go.mod` | go | `go test ./...` | `go build ./...` |
| `Cargo.toml` | rust | `cargo test` | `cargo build` |

## Template Handling

Claude reads `{CLAUDE_PLUGIN_ROOT}/templates/<phase>_prompt.md` via Read tool, then interprets it with the current context variables. No rendered file is written - Claude processes the template inline.

## Workflow

1. User provides task
2. Claude scans codebase -> auto-detect lang/test/build
3. Create `.harness/state.json`, `docs/harness/<slug>/`, git branch
4. Read planner template -> execute Planner phase
5. Write `spec.md` to `docs/harness/<slug>/`
6. **HARD GATE: User confirms spec** (see Confirmation Gates below)
7. Advance state -> execute Generator phase
8. Write `changes.md` -> execute Evaluator phase
9. Write `qa_report.md` -> judge PASS/FAIL
10. FAIL + rounds left -> back to step 7
11. PASS or max rounds -> ask user about committing artifacts

## Confirmation Gates

Generator(구현) 단계는 토큰 소비가 크고 되돌리기 어렵다. 따라서 **명시적 확인 없이 절대 진행하지 않는다.**

### Gate 1: Spec 확인 (Planner -> Generator 전환)

spec.md 작성 후 반드시 사용자에게 보여주고 확인을 받는다.

**진행 가능한 응답 (이것만 허용):**
- "진행", "승인", "ㅇㅇ", "go", "proceed", "approve", "확인", "좋아", "넘어가"
- 또는 spec 수정 요청 후 재확인에서 위 응답

**진행 불가 — 반드시 재확인:**
- 모호한 응답: "음...", "글쎄", "괜찮은 것 같은데"
- 질문: "이거 맞아?", "이렇게 하면 되나?"
- 조건부: "~하면 괜찮을 것 같아"
- 무관한 응답 또는 주제 전환

모호한 경우 다음과 같이 재확인한다:
> "구현을 시작하면 토큰 소비가 크므로 명확한 확인이 필요합니다. spec 내용대로 구현을 진행할까요? (진행/수정/중단)"

### Gate 2: QA 실패 시 재시도 확인 (Evaluator -> Generator 재진입)

QA가 FAIL이고 라운드가 남아있을 때, 자동으로 재시도하지 않고 사용자에게 확인한다:
> "QA 결과 FAIL입니다. [실패 항목 요약]. 다음 라운드로 수정을 진행할까요? (진행/중단)"

## Key Rules (carried over)

- Never skip phases: Planner -> Generator -> Evaluator
- **Confirmation gates are non-negotiable** — no implicit approval, no proceeding on ambiguity
- Evaluator must be strict
- Git safety: auto-create branch
- Language matching: communicate in user's language
- Use available skills from any installed plugin

## Removed Features

- `repo add/list/update/remove` commands (replaced by auto-detect)
- `~/.agent-harness/repos.yaml` global config
- `.harness.yaml` per-repo config
- `--repo` flag (always auto-detect from current directory)
- Rendered prompt files (`*_rendered.md`) - Claude interprets inline
