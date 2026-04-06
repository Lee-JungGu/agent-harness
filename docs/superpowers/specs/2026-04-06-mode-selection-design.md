# Single/Multi Mode Selection Design

v4.0.0의 다중 에이전트 페르소나와 v3.0.0의 단일 에이전트 방식을 사용자가 선택할 수 있도록 고도화한다.

## 배경

v4.0.0에서 Planner와 Generator에 다중 에이전트 페르소나가 도입되어 품질이 향상되었으나, 토큰 소비량이 ~1.7-2x 증가하는 단점이 있다. 단순하거나 소규모 작업에서는 단일 에이전트가 비용 대비 효율적이므로, 두 방식을 선택 가능하게 한다.

## 목표

- 사용자가 `single` / `multi` 모드를 선택하여 토큰 비용과 분석 깊이를 조절할 수 있게 한다.
- 기존 v4.0.0 Multi 모드는 변경 없이 유지한다.
- v3.0.0 Single 모드를 복원하여 경량 워크플로우를 제공한다.

## 스코프

### 변경 대상

| 파일 | 작업 |
|------|------|
| `skills/harness/SKILL.md` | 모드 선택 로직 + Step 2/4 조건부 분기 추가 |
| `templates/planner/planner_single.md` | 신규 — v3 `planner_prompt.md` 기반 복원 |
| `templates/generator/generator_single.md` | 신규 — v3 `generator_prompt.md` 기반 복원 |
| `README.md` | 모드 선택 옵션 문서화 |

### 변경 없음

| 파일 | 이유 |
|------|------|
| `templates/planner/architect.md` 외 Multi 템플릿 10개 | Multi 모드는 현행 유지 |
| `templates/evaluator/evaluator_prompt.md` | 모드와 독립적 |
| Step 3 (Spec Confirmation) | 모드 무관 |
| Step 5-7 (Evaluator, Verdict, Cleanup) | 모드 무관 |

## 접근 방식

### 1. 모드 선택 메커니즘

#### state.json 변경

`mode` 필드 추가:

```json
{
  "task": "...",
  "mode": "single",
  "user_lang": "ko",
  ...
}
```

허용 값: `"single"` | `"multi"`

#### 선택 흐름

1. **인자 파싱**: `--mode single` 또는 `--mode multi`가 있으면 mode를 바로 설정하고 질문 스킵
2. **인자 없으면**: Step 1 Setup 완료 직후, Step 2 진입 전에 질문:

```
[harness] 모드를 선택해 주세요:
  1. single — 단일 에이전트 (빠르고 토큰 절약)
  2. multi  — 다중 페르소나 (깊이 있는 분석, 토큰 ~1.7x)
> (1 / 2 / single / multi)
```

3. 선택값을 state.json에 저장하여 세션 복구 시에도 모드 유지

#### 세션 복구 시 표시

```
[harness] Previous session detected.
  Task   : <task>
  Mode   : <single | multi>
  Phase  : <phase label>
  Round  : <round> / <max_rounds>
  Branch : <branch>
```

### 2. Planner 분기 (Step 2)

SKILL.md의 Step 2에서 mode에 따라 분기:

#### Single 모드 (Step 2-S)

- `templates/planner/planner_single.md` 템플릿 사용
- 1 에이전트가 메인 컨텍스트에서 인라인 실행:
  - 코드베이스 탐색
  - brainstorming/writing-plans 스킬 검색 및 호출 (가능한 경우)
  - spec.md 작성
- 서브에이전트 없음
- `.harness/planner/` 디렉토리 불필요 (생성 스킵)

#### Multi 모드 (Step 2-M)

기존 v4.0.0 그대로:
- Step 2a: 3 독립 제안 (architect, senior_developer, qa_specialist) 병렬
- Step 2b: 3 교차비평 (cross_critique) 병렬
- Step 2c: 1 합성 (synthesis) → spec.md

#### 공통

Step 3 (Spec Confirmation)은 모드 무관하게 동일하게 실행.

### 3. Generator 분기 (Step 4)

SKILL.md의 Step 4에서 mode에 따라 분기:

#### Single 모드 (Step 4-S)

- `templates/generator/generator_single.md` 템플릿 사용
- 1 에이전트가 서브에이전트로 실행:
  - spec.md 읽기
  - QA 피드백 반영 (Round 2+)
  - 스코프 사전 점검
  - TDD/parallel 스킬 검색 및 호출 (가능한 경우)
  - 코드 구현 + changes.md 작성
- 어드바이저 리뷰 없음
- `.harness/generator/` 디렉토리에 plan.md, review 파일 없음

#### Multi 모드 (Step 4-M)

기존 v4.0.0 그대로:
- Step 4a: Lead Developer가 plan.md 작성 (서브에이전트)
- Step 4b: 2 어드바이저 병렬 리뷰
- Step 4c: Lead Developer가 어드바이저 피드백 반영하여 구현 (서브에이전트)

#### 공통

Step 5-7 (Evaluator, Verdict, Cleanup)은 모드 무관하게 동일하게 실행.

### 4. 템플릿 파일 설계

#### `templates/planner/planner_single.md` (신규)

v3의 `planner_prompt.md`를 기반으로 복원. 변수:
- `{task_description}`, `{repo_path}`, `{lang}`, `{scope}`, `{user_lang}`

핵심 흐름:
1. 코드베이스 탐색
2. brainstorming 스킬 호출 (있으면)
3. writing-plans 스킬 호출 (있으면)
4. spec.md 작성 (Goal, Background, Scope, Approach, Completion Criteria, Risks)

#### `templates/generator/generator_single.md` (신규)

v3의 `generator_prompt.md`를 기반으로 복원. 변수:
- `{spec_content}`, `{qa_feedback}`, `{round_num}`, `{scope}`, `{max_files}`, `{user_lang}`, `{changes_path}`

핵심 흐름:
1. 스펙 읽기 + 스코프 사전 점검
2. TDD/parallel 스킬 호출 (있으면)
3. Round 2+: FAIL 항목만 수정
4. 코드 구현 + changes.md 작성

### 5. Setup 단계 변경 (Step 1)

Step 1의 변경 사항:

- **디렉토리 생성**: Single 모드일 때 `.harness/planner/`, `.harness/generator/` 생성을 스킵할 수 있으나, 단순화를 위해 모드 무관하게 생성해도 무방 (빈 디렉토리는 비용 없음)
- **state.json**: `mode` 필드 추가
- **Setup 요약 출력**에 모드 표시:

```
[harness] Task started!
  Repo     : <path>
  Branch   : harness/<slug>
  Mode     : <single | multi>
  Language : <lang>
  Test     : <test_cmd or "none">
  Build    : <build_cmd or "none">
  Scope    : <scope>
```

## 완료 기준

- [ ] `--mode single` 또는 `--mode multi` 인자로 모드 지정 가능
- [ ] 인자 없이 호출 시 Setup 직후 모드 선택 질문 표시
- [ ] Single 모드: Planner가 1 에이전트로 spec.md 작성
- [ ] Single 모드: Generator가 1 에이전트로 구현 + changes.md 작성
- [ ] Multi 모드: 기존 v4.0.0 워크플로우 그대로 동작
- [ ] state.json에 mode 필드 저장, 세션 복구 시 모드 유지 및 표시
- [ ] Evaluator, Verdict, Cleanup은 모드 무관하게 동일 동작
- [ ] README.md에 모드 선택 옵션 문서화
- [ ] Setup 요약 및 세션 복구 표시에 모드 정보 포함

## 리스크

- **Single 모드 품질 저하**: 단일 에이전트는 앵커링 편향 제거, 교차비평 등의 이점이 없으므로 복잡한 작업에서 스펙 품질이 낮을 수 있다. 모드 선택 안내 시 이 트레이드오프를 명시한다.
- **템플릿 동기화**: Single/Multi 템플릿이 별도 파일이므로, 향후 공통 로직 변경 시 양쪽 모두 반영해야 한다. Evaluator처럼 공유되는 부분은 이미 단일 파일이므로 문제없다.
