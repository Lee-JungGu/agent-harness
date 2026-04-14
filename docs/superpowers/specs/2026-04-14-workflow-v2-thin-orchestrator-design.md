# Workflow V2: Thin Orchestrator + Mechanical Quality Gates

- **Date**: 2026-04-14
- **Status**: DRAFT (섹션 1-4 완료, 섹션 5-8 미작성)
- **Goal**: /workflow 스킬의 토큰 효율성 극대화 + 모델 품질 변동에 대한 구조적 내성 확보
- **Target**: agent-harness v8.0.0

---

## 배경 및 동기

### 외부 환경 변화
- Claude Code 사용자들 사이에서 **토큰 절약**에 대한 관심이 급증
- LLM 모델의 추론 능력이 시기에 따라 변동하는 현상 체감 증가 (Opus 포함)
- "AI 모델의 능력만 믿고 작업"하는 방식의 한계가 드러남

### agent-harness 내부 문제
- 현재 `/workflow`는 단일 세션에서 Plan → Generate → Evaluate 전체를 진행
- 서브에이전트를 사용하더라도 **결과 요약이 메인 세션에 누적**되어 후반부 토큰 비용 급증
- Evaluator가 "PASS" 판정을 내릴 때 LLM 판단에 전적으로 의존 → 모델 부진 시 가짜 PASS 위험

### 설계 목표
1. **토큰 40-60% 절감**: 오케스트레이터 컨텍스트를 ~15K 이하로 유지
2. **모델 품질 무관 최소 품질 보장**: 빌드/테스트/린트가 통과하는 코드만 커밋
3. **UX 유지**: 기본 사용 경험은 현재와 동일, 파워 유저에게 추가 옵션 제공
4. **기존 호환**: 아티팩트 구조(spec.md, changes.md, qa_report.md) 유지

---

## 섹션 1: 핵심 문제 정의

두 가지 독립적인 문제를 하나의 설계에서 동시에 해결한다.

### 문제 A — 토큰 비효율

오케스트레이터(메인 세션)에 컨텍스트가 누적되어 후반부 토큰 비용이 급증한다.

현재 토큰 프로필 (단일 세션 기준):
```
[Setup 5K] → [Plan 30K] → [Gate 35K] → [Generate 80K+] → [Gate 90K+] → [Evaluate 120K+]
                                                                ↑ 여기서부터 비용 급증
```

서브에이전트가 격리된 컨텍스트를 사용하더라도, 서브에이전트의 결과 요약(수백~수천 토큰)이 메인 세션에 반환되고 누적된다. Generator 단계에서 여러 파일을 수정하면서 컨텍스트가 폭발적으로 증가한다.

### 문제 B — 모델 품질 변동

현재 스킬은 "모델이 잘 판단할 것"이라는 전제에 의존하는 부분이 많다.

| 단계 | LLM이 판단하는 것 | 모델 품질 저하 시 위험 |
|------|------------------|---------------------|
| Planner | "요구사항을 충분히 분석했는가" | 얕은 분석, 엣지 케이스 누락 |
| Generator | "코드가 스펙을 충족하는가" | 플레이스홀더, 불완전 구현 |
| **Evaluator** | **"구현이 합격인가"** | **가짜 PASS (가장 치명적)** |

특히 Evaluator의 거짓 PASS가 가장 치명적이다. 모델이 "잘 된 것 같다"고 넘기면 불완전한 코드가 커밋된다.

### 해결 방향 (두 문제의 공통 해법)

> **"LLM의 판단에 의존하는 부분을 줄이고, 구조와 자동 검증으로 품질을 보장한다"**

- 토큰 → 오케스트레이터가 덜 생각하게 만들면 줄어든다
- 품질 → LLM 판단 대신 실행 가능한 검증(빌드, 테스트, lint)으로 대체하면 모델 능력에 덜 의존한다

---

## 섹션 2: Thin Orchestrator 아키텍처

### 현재 구조 (Fat Orchestrator)

```
메인 세션 (오케스트레이터)
├── 사용자 대화 처리
├── Setup & 환경 감지
├── Planner 로직 실행 (또는 SubAgent 디스패치)
│   └── spec.md 생성 → 메인 세션에 결과 반환 & 누적
├── 사용자 승인 게이트
├── Generator 로직 실행 (또는 SubAgent 디스패치)
│   └── 코드 작성 → 메인 세션에 결과 반환 & 누적
├── 사용자 승인 게이트
├── Evaluator 로직 실행 (또는 SubAgent 디스패치)
│   └── qa_report.md → 메인 세션에 결과 반환 & 누적
└── Cleanup & Commit
```

**문제**: 서브에이전트를 사용하더라도, 서브에이전트의 결과 요약이 메인 세션에 계속 쌓인다. 오케스트레이터가 "다음에 뭘 할지", "결과가 좋은지"를 스스로 판단하는 비중이 크다.

### 제안 구조 (Thin Orchestrator)

```
메인 세션 (오케스트레이터) — 상태 머신으로만 동작
│
├── [1] Setup (직접 실행, ~5K)
│   환경 감지, state.json 생성
│   → state.json에 phase="plan_ready" 기록
│
├── [2] Dispatch: Plan (SubAgent)
│   입력: state.json + 사용자 태스크 설명만 전달
│   출력: spec.md 파일 기록 → 성공/실패만 반환
│   → 오케스트레이터는 "spec.md 생성됨" 1줄만 수신
│
├── [3] Gate: 사용자 승인
│   spec.md를 사용자에게 보여주고 승인 요청
│   → state.json에 phase="generate_ready" 기록
│
├── [4] Dispatch: Generate (SubAgent)
│   입력: state.json + spec.md만 전달 (이전 대화 없음)
│   출력: 코드 변경 + changes.md 기록 → 성공/실패만 반환
│   → 오케스트레이터는 "N개 파일 변경됨" 1줄만 수신
│
├── [5] Auto-Verify (SubAgent) ← 새로운 단계
│   입력: state.json + changes.md
│   실행: build → test → lint (LLM 판단 아님, 명령어 실행)
│   출력: verify_report.md (PASS/FAIL + 로그) → 결과만 반환
│
├── [6] Dispatch: Evaluate (SubAgent)
│   입력: state.json + spec.md + changes.md + verify_report.md
│   출력: qa_report.md → 결과만 반환
│
└── [7] Cleanup & Commit
```

### 핵심 변화 3가지

| 항목 | 현재 | 제안 |
|------|------|------|
| **오케스트레이터 역할** | 대화 관리 + 로직 실행 + 판단 | 상태 전이 + 디스패치 + 게이트만 |
| **서브에이전트 반환** | 결과 요약 (수백~수천 토큰) | 성공/실패 1줄 (파일에 상세 기록) |
| **단계 간 통신** | 메인 세션 컨텍스트 경유 | 파일 직접 참조 (spec.md → changes.md) |

### [5] Auto-Verify 단계 (신규)

LLM이 아니라 실제 명령어 실행(build, test, lint)으로 코드 품질을 기계적으로 검증하는 단계. 모델 품질과 무관하게 동작한다. 상세 설계는 섹션 3 참조.

### 예상 토큰 프로필

```
현재:  [Setup 5K] → [Plan 30K] → [Gate 35K] → [Generate 80K+] → [Gate 90K+] → [Evaluate 120K+]
                                                                    ↑ 여기서부터 비용 급증

제안:  [Setup 5K] → [Plan 5K→Sub] → [Gate 8K] → [Gen 5K→Sub] → [Verify 5K→Sub] → [Eval 5K→Sub]
       오케스트레이터 자체는 ~8-15K 범위에서 유지
```

### 서브에이전트 반환 규칙

오케스트레이터의 컨텍스트를 가볍게 유지하기 위한 핵심 규칙:

1. **서브에이전트는 상세 결과를 파일에 기록**한다 (spec.md, changes.md, verify_report.md, qa_report.md)
2. **오케스트레이터에 반환하는 값은 1-2줄 요약만** 허용한다:
   - Plan: `"spec.md 생성 완료 — acceptance criteria 3건, edge case 2건"`
   - Generate: `"4개 파일 변경 완료 — auth.ts, middleware.ts, routes.ts, auth.test.ts"`
   - Verify: `"PASS — build ✓, test 12/12 ✓, lint 0 errors"`
   - Evaluate: `"PASS — minor 1건 (qa_report.md 참조)"`
3. **오케스트레이터는 파일 내용을 직접 읽지 않는다** — 사용자에게 보여줄 때만 Read 사용

---

## 섹션 3: Mechanical Quality Gates (3-Layer 검증 체계)

LLM 판단을 기계적 검증 → 구조화된 검증 → LLM 검증 순서로 계층화한다. 앞 단계에서 걸러질수록 모델 품질에 덜 의존한다.

### Layer 1: Mechanical Verification (LLM 불필요)

모델 품질과 완전히 무관하게 동작하는 기계적 검증.

```
Layer 1: Mechanical (LLM 불필요 — 모델 품질 무관)
  ├── build 통과 여부
  ├── test 통과 여부 (기존 테스트 + 새 테스트)
  ├── lint/type-check 통과 여부
  ├── TODO/FIXME/HACK 스캔 (불완전 구현 탐지)
  └── spec acceptance criteria 매칭 (Given/When/Then → 테스트 존재 확인)
```

**FAIL 시**: 즉시 Generator에 재시도 지시 (Evaluator 도달 전 차단). 구체적 에러 로그를 포함하여 전달.

#### Layer 1 실행 순서

```
1. build_cmd 실행 → FAIL 시 즉시 중단, 에러 로그 기록
2. test_cmd 실행 → FAIL 시 실패한 테스트 목록 기록
3. lint_cmd 실행 (있는 경우) → ERROR만 FAIL, WARNING은 기록만
4. type_check_cmd 실행 (있는 경우) → FAIL 시 에러 목록 기록
5. grep -rn "TODO\|FIXME\|HACK" <changed_files> → 발견 시 WARN (blocking 여부 설정 가능)
6. spec acceptance criteria 스캔:
   - spec.md에서 Given/When/Then 항목 추출
   - 각 항목에 대응하는 테스트 함수가 존재하는지 grep으로 확인
   - 매칭되지 않는 항목 → WARN (테스트 커버리지 부족 경고)
```

#### verify_report.md 출력 형식

```markdown
# Verify Report

- **timestamp**: 2026-04-14T15:30:00+09:00
- **result**: PASS | FAIL
- **phase**: layer1_mechanical

## Build
- command: `npm run build`
- result: PASS
- duration: 3.2s

## Test
- command: `npm test`
- result: PASS
- total: 42, passed: 42, failed: 0, skipped: 0
- duration: 8.1s

## Lint
- command: `npm run lint`
- result: PASS
- errors: 0, warnings: 2
- warnings:
  - src/auth.ts:15 — Unexpected any. Specify a different type. (@typescript-eslint/no-explicit-any)
  - src/auth.ts:23 — 'logger' is defined but never used. (@typescript-eslint/no-unused-vars)

## Type Check
- command: `npx tsc --noEmit`
- result: PASS

## Completeness Scan
- TODO/FIXME/HACK: 0 found in changed files
- Acceptance Criteria Coverage:
  - [✓] "사용자가 이메일/비밀번호로 로그인할 수 있다" → auth.test.ts:L12
  - [✓] "잘못된 비밀번호 시 에러 메시지 표시" → auth.test.ts:L28
  - [✗] "5회 실패 시 계정 잠금" → 테스트 미발견 (WARN)
```

### Layer 2: Structural Verification (LLM 사용, 판단 범위 좁힘)

LLM을 사용하되, open-ended 판단이 아닌 **구체적 체크리스트 기반** yes/no 검증.

```
Layer 2: Structural (LLM 사용하되, 판단 범위를 좁힘)
  ├── spec.md의 각 acceptance criteria별 개별 yes/no 체크
  │   → "이 코드가 criteria X를 충족하는가? 근거 파일:라인을 제시하라"
  ├── changes.md의 각 파일별 "이 파일의 변경 목적" 매칭
  │   → "이 변경이 spec의 어느 요구사항에 대응하는가?"
  ├── diff 기반 리뷰 (전체 코드가 아닌 변경분만)
  │   → 컨텍스트 최소화: 변경된 파일의 diff만 제공
  └── 구체적 질문 목록 (open-ended "잘 됐나?" 금지)
      → "에러 핸들링이 누락된 코드 경로가 있는가? 있다면 파일:라인을 제시하라"
```

**핵심**: "이 코드가 좋은가?"가 아니라, "이 구체적 항목이 충족되었는가?"를 묻는다. 모델 능력이 떨어져도 좁은 범위의 yes/no 질문에는 상대적으로 정확하게 답할 수 있다.

**체크리스트 중 하나라도 NO**: 해당 항목만 구체적으로 재작업 지시 (전체 재생성 아님).

### Layer 3: LLM Judgment (최후 방어선)

기존 Evaluator의 역할. Layer 1,2를 통과한 코드만 도달하므로 신뢰도가 높다.

```
Layer 3: LLM Judgment (기존 Evaluator — 최후 방어선)
  ├── anchor-free input (Generator 자기평가 미제공)
  ├── defect-assumption framing ("결함이 있다고 가정하고 찾아라")
  ├── 반드시 파일:라인 번호 인용 (근거 없는 판단 차단)
  └── pre-mortem ("이 코드가 프로덕션에서 실패한다면 원인은?")
```

### 모델 품질 수준별 시나리오

```
모델 품질 정상:  Layer 1 (통과) → Layer 2 (통과) → Layer 3 (정밀 검증) = 고품질
모델 품질 저하:  Layer 1 (여기서 50%+ 걸림) → Layer 2 (추가 필터) → Layer 3 (가짜 PASS 가능하나, 기계적으로 검증된 코드) = 중품질 유지
모델 품질 심각:  Layer 1 (대부분 FAIL → 재시도 루프) → 최대 재시도 초과 시 사용자에게 수동 개입 요청
```

### Generator 재시도 메커니즘

Layer 1,2에서 실패 시 무조건 재시도가 아닌, **구체적 피드백 기반 재시도**.

```
[Generator SubAgent]
  → 코드 작성 완료
  
[Auto-Verify SubAgent] (Layer 1)
  → build FAIL: "src/auth.ts:42 — TypeError: Property 'token' does not exist"
  → 실패 로그를 그대로 포함하여 Generator에 전달

[Generator SubAgent — retry #1] (새로운 서브에이전트, 이전 실패 컨텍스트 오염 없음)
  입력: spec.md + 이전 changes.md + "build 실패: src/auth.ts:42 TypeError..." 
  → 구체적 에러만 수정 (전체 재작성 아님)

[Auto-Verify SubAgent] (Layer 1)
  → build PASS, test PASS, lint WARN (non-blocking)
  → Layer 2로 진행
```

재시도 시 **새로운 서브에이전트**가 실행되므로 이전 실패의 컨텍스트 오염 없이 신선한 상태에서 에러만 수정한다. 이것도 Thin Orchestrator의 이점이다.

### 최대 재시도 정책

| Layer | 최대 재시도 | 초과 시 행동 |
|-------|-----------|------------|
| Layer 1 | 3회 | 사용자에게 수동 개입 요청 (빌드/테스트 에러 로그 제공) |
| Layer 2 | 2회 | 실패 항목 표시 후 사용자 판단 요청 |
| Layer 3 | 기존과 동일 | Fix/Accept 선택지 제공 |

---

## 섹션 4: UX 설계 — 편의성과 유연성의 균형

### 설계 원칙

```
"그냥 잘 되게 해줘"  ←────────────────→  "각 단계를 내가 컨트롤하고 싶어"
   대다수 사용자                              파워 유저 / 토큰 민감 사용자
```

기본은 심플하게, 필요하면 세밀하게 컨트롤 가능해야 한다.

### 실행 모드 3가지

#### 모드 1: Auto (기본값) — 현재 UX와 동일한 경험

```bash
/workflow "사용자 인증 기능 추가"
```

- 한 번 실행하면 Plan → Verify → Generate → Verify → Evaluate 전체 진행
- 확인 게이트(spec 승인)는 기존과 동일하게 유지
- 내부적으로는 Thin Orchestrator + 서브에이전트로 토큰 최적화
- **사용자 관점에서는 현재와 차이 없음** (내부만 효율화)

#### 모드 2: Phase (단계별 실행) — 세션 분리로 토큰 극한 절약

```bash
/workflow plan "사용자 인증 기능 추가"     ← 세션 1: spec.md 생성 후 종료
/workflow generate                         ← 세션 2: spec.md 읽고 구현 후 종료
/workflow evaluate                         ← 세션 3: 평가 후 종료
```

- 각 단계가 독립 세션으로 실행 가능
- `state.json`에 현재 phase가 기록되어 있으므로 다음 단계를 자동 인식
- 세션 사이에 사용자가 spec.md를 직접 편집할 수도 있음
- **토큰 절약 극대화** — 각 세션이 최소 컨텍스트로 시작

#### 모드 3: Step (개별 단계 지정) — 특정 단계만 재실행

```bash
/workflow verify                           ← Layer 1 기계적 검증만 재실행
/workflow evaluate                         ← 평가만 재실행 (코드 수정 후)
```

- 이미 진행된 워크플로우의 특정 단계만 다시 실행
- Generate 후 수동으로 코드를 수정하고, verify만 돌리는 경우
- Evaluate 결과가 불만족스러워 코드 수정 후 재평가하는 경우

### 모드 선택 CLI 패턴

```bash
/workflow "태스크 설명"           → Auto 모드 (기본)
/workflow --phase plan "설명"    → Phase 모드로 plan만 실행
/workflow plan "설명"            → Phase 모드 (위와 동일, --phase 생략 가능)
/workflow generate               → 이전 plan 결과를 이어서 generate
/workflow verify                 → Step 모드 — verify만 실행
```

`state.json`이 이미 존재하면:

```bash
/workflow                        → state.json의 phase를 읽고 다음 단계 자동 제안
                                   "Plan이 완료되어 있습니다. Generate를 진행할까요?"
```

### 상태 전이 다이어그램

```
         ┌──────────────────────── Auto 모드: 자동 진행 ────────────────────────┐
         │                                                                      │
    plan_ready ──→ planning ──→ plan_done ──→ [사용자 승인] ──→ generate_ready
                                                   │
                                              Phase 모드:                    
                                              세션 종료 가능                   
                                                   │
    generate_ready ──→ generating ──→ generate_done ──→ verify_ready
                                                            │
    verify_ready ──→ verifying(L1) ──→ verify_done ──→ evaluate_ready
                          │                                 │
                     FAIL → retry                     Phase 모드:
                     (최대 3회)                        세션 종료 가능
                                                            │
    evaluate_ready ──→ evaluating(L2+L3) ──→ evaluate_done ──→ [사용자 확인]
                                                                     │
                                                          ┌──── Fix (재시도)
                                                          └──── Accept → cleanup
```

**Phase 모드 세션 종료 지점**: `plan_done`, `verify_done` 시점에서 자연스럽게 세션이 종료될 수 있고, 다음 세션에서 이어서 진행.

**Auto 모드 게이트**: `plan_done` 시점의 사용자 승인 게이트만 유지. 나머지는 자동 진행하되, Layer 1 실패 시 자동 재시도 후 최대 횟수 초과 시에만 사용자에게 질문.

### 진행 상황 표시

Thin Orchestrator가 각 서브에이전트 디스패치 시 간결한 상태 메시지를 출력:

```
[workflow] Phase: Plan
  Dispatching planner sub-agent...
  ✓ spec.md generated (3 acceptance criteria, 2 edge cases)

[workflow] Phase: Generate  
  Dispatching generator sub-agent...
  ✓ 4 files changed (auth.ts, middleware.ts, routes.ts, auth.test.ts)

[workflow] Phase: Verify (Layer 1 — Mechanical)
  build... ✓
  test...  ✓ (12 passed, 0 failed)
  lint...  ✓ (0 errors, 2 warnings)
  scan...  ✓ (no TODO/FIXME in new code)

[workflow] Phase: Evaluate (Layer 2+3)
  Dispatching evaluator sub-agent...
  ✓ PASS — 1 minor suggestion (see qa_report.md)
```

오케스트레이터가 출력하는 건 이 상태 메시지뿐이므로 컨텍스트가 가볍게 유지된다.

### 기존 /workflow과의 관계

기존 워크플로우를 대체하는 것이 아니라 **실행 엔진을 교체**하는 접근:

| 항목 | 변경 사항 |
|------|----------|
| 사용자 인터페이스 | 동일 (+ phase 옵션 추가) |
| 확인 게이트 | 동일 |
| 아티팩트 구조 | 동일 (spec.md, changes.md, qa_report.md) + verify_report.md 추가 |
| state.json | 확장 (phase 세분화 + verify 결과 필드 추가) |
| 내부 실행 | Fat Orchestrator → Thin Orchestrator + Mechanical Gates |

---

## 섹션 5: 서브에이전트 핸드오프 설계 (TODO)

> **이 섹션은 미작성 상태입니다.** 다음 세션에서 설계를 이어가야 합니다.

### 작성해야 할 내용

각 서브에이전트가 받는 입력과 출력의 구체적 형태를 정의한다.

#### 5.1 Plan SubAgent
- **입력**: state.json (환경 정보), 사용자 태스크 설명, 모드(single/standard/multi)
- **출력**: spec.md (acceptance criteria 포함), 오케스트레이터 반환값 (1줄 요약)
- **고려사항**: 기존 planner 템플릿(architect, senior_developer, qa_specialist) 재활용 방안
- **프롬프트 구조**: state.json에서 필요한 필드만 추출하여 서브에이전트 프롬프트에 포함

#### 5.2 Generate SubAgent
- **입력**: state.json + spec.md (파일 경로 전달, 내용은 서브에이전트가 직접 Read)
- **출력**: 코드 변경 + changes.md, 오케스트레이터 반환값 (1줄 요약)
- **고려사항**: 기존 generator 템플릿(lead_developer, advisors) 재활용 방안
- **retry 시 입력**: spec.md + 이전 changes.md + verify_report.md (실패 로그)

#### 5.3 Verify SubAgent
- **입력**: state.json (build_cmd, test_cmd, lint_cmd), changes.md (변경 파일 목록)
- **출력**: verify_report.md, 오케스트레이터 반환값 (PASS/FAIL + 1줄)
- **고려사항**: LLM 판단 최소화 — 대부분 Bash 명령어 실행으로 구성
- **설계 결정 필요**: lint_cmd, type_check_cmd 자동 감지 전략 (현재는 build_cmd, test_cmd만 감지)

#### 5.4 Evaluate SubAgent
- **입력**: state.json + spec.md + changes.md + verify_report.md
- **출력**: qa_report.md, 오케스트레이터 반환값 (PASS/FAIL + 1줄)
- **고려사항**: Layer 2 체크리스트를 프롬프트에 포함하는 방법
- **설계 결정 필요**: Layer 2와 Layer 3을 하나의 서브에이전트에서 실행할지, 분리할지

---

## 섹션 6: state.json 확장 설계 (TODO)

> **이 섹션은 미작성 상태입니다.**

### 작성해야 할 내용

#### 6.1 현재 state.json 필드 (v7.0.0)
```json
{
  "task": "...",
  "mode": "single|standard|multi",
  "model_config": { "preset": "...", "executor": "...", "advisor": "...", "evaluator": "..." },
  "user_lang": "ko",
  "has_git": true,
  "repo_name": "...",
  "repo_path": "...",
  "phase": "plan_ready|planning|generate_ready|generating|completed",
  "round": 1,
  "max_rounds": 3,
  "max_files": 20,
  "scope": "...",
  "branch": "harness/<slug>",
  "lang": "typescript",
  "test_cmd": "npm test",
  "build_cmd": "npm run build",
  "docs_path": "docs/harness/<slug>/",
  "created_at": "..."
}
```

#### 6.2 추가해야 할 필드
- `execution_mode`: "auto" | "phase" | "step" — 실행 모드
- `lint_cmd`: 린트 명령어 (자동 감지 또는 사용자 지정)
- `type_check_cmd`: 타입 체크 명령어
- `verify_result`: Layer 1 검증 결과 요약
- `verify_retries`: 현재 재시도 횟수
- `phase` 확장: plan_ready → planning → plan_done → generate_ready → generating → generate_done → verify_ready → verifying → verify_done → evaluate_ready → evaluating → evaluate_done → completed

#### 6.3 설계 결정 필요
- lint_cmd 자동 감지 전략 (package.json scripts 탐색? .eslintrc 존재 여부?)
- type_check_cmd 자동 감지 (tsconfig.json → `npx tsc --noEmit`, pyright 등)
- verify_result에 어디까지 저장할지 (전체 로그? 요약만?)

---

## 섹션 7: 기존 스킬 적용 가능성 (TODO)

> **이 섹션은 미작성 상태입니다.**

### 작성해야 할 내용

Thin Orchestrator + Mechanical Quality Gates 패턴을 다른 스킬에도 적용할 수 있는지 분석.

#### 적용 가능 스킬
- `/refactor` — Generator + Verify 루프 직접 적용 가능 (행동 보존 = 테스트 통과)
- `/migrate` — 단계별 Verify 이미 존재, Layer 체계로 강화 가능
- `/test-gen` — 생성된 테스트 자체의 실행 검증 (이미 mutation testing으로 일부 커버)
- `/debug` — hypothesis 검증에 Mechanical Verify 적용 가능

#### 적용 어려운 스킬
- `/spec` — 코드 생성이 아닌 문서 생성, Mechanical Verify 대상 없음
- `/code-review` — 읽기 전용 스킬, 검증 대상 없음
- `/codebase-audit` — 분석 스킬, 검증 대상 없음

#### 공통 패턴 추출
- Thin Orchestrator 패턴을 공유 가이드로 추출하여 모든 스킬이 참조할 수 있도록 할지
- 각 스킬에 인라인으로 포함할지
- 결정 필요

---

## 섹션 8: 마이그레이션 계획 (TODO)

> **이 섹션은 미작성 상태입니다.**

### 작성해야 할 내용

현재 `/workflow` v7.0.0에서 v2 (Thin Orchestrator)로의 전환 계획.

#### 고려사항
- 기존 state.json과의 호환성 (진행 중인 세션이 있을 수 있음)
- 기존 템플릿 재활용 vs 신규 작성
- 점진적 전환 가능 여부 (한 번에 전환 vs 단계적 도입)
- 테스트 전략: v1과 v2의 동일 태스크 결과 비교

---

## 다음 세션 작업 가이드

### 완료된 섹션 (1-4)
1. ✅ 핵심 문제 정의 (토큰 비효율 + 모델 품질 변동)
2. ✅ Thin Orchestrator 아키텍처 (상태 머신 + 서브에이전트 + 파일 핸드오프)
3. ✅ Mechanical Quality Gates (3-Layer 검증 체계 + 재시도 메커니즘)
4. ✅ UX 설계 (Auto/Phase/Step 3모드 + 상태 전이 + 진행 표시)

### 미완료 섹션 (5-8)
5. ❌ 서브에이전트 핸드오프 설계 — 각 서브에이전트의 입력/출력/프롬프트 구체화
6. ❌ state.json 확장 설계 — 새 필드 정의, lint/type-check 자동 감지 전략
7. ❌ 기존 스킬 적용 가능성 — refactor, migrate 등에 패턴 확장 분석
8. ❌ 마이그레이션 계획 — v7 → v2 전환 전략

### 설계 결정이 필요한 항목 (섹션 5-8 작업 시 판단)
1. Layer 2와 Layer 3을 하나의 서브에이전트에서 실행할지, 분리할지
2. lint_cmd, type_check_cmd 자동 감지 전략
3. verify_report.md에 전체 로그를 저장할지, 요약만 저장할지
4. Thin Orchestrator 패턴을 공유 가이드로 추출할지, 각 스킬에 인라인 포함할지
5. v1→v2 전환을 한 번에 할지, 단계적으로 도입할지

### 이어서 작업하는 방법

```bash
# 이 설계 문서를 읽고 섹션 5부터 이어서 작업
# 파일 경로: docs/superpowers/specs/2026-04-14-workflow-v2-thin-orchestrator-design.md
```
