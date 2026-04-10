# AskUserQuestion UX 전면 전환 설계

## 목표

agent-harness의 모든 SKILL.md(7개)에서 사용자 문답을 AskUserQuestion 도구 기반 번호 선택으로 전환하여, 타이핑 없이 선택지를 고를 수 있게 한다. 선택지는 구체적인 설명을 포함하고, 마지막에 Other(자유 입력)가 자동 추가된다.

## 배경

- 현재 모든 사용자 문답(~36개 지점)이 텍스트 기반 입력 (번호/키워드 파싱)
- model_config 선택에만 AskUserQuestion이 시범 적용된 상태
- 사용자 피드백: "타이핑으로 치는 것이 불편하다. 번호로 고를 수 있게 해달라"
- Step 7 커밋 질문: "아티팩트 포함 커밋 / 안 함" 2가지만 있어, "아티팩트 정리 + 코드만 커밋" 옵션이 없었음

## 대상 파일 (7개)

| 파일 | 전환 지점 | 비고 |
|------|----------|------|
| skills/workflow/SKILL.md | 5 | 세션 복구, 모드, spec 확인, QA 재시도, 커밋 |
| skills/refactor/SKILL.md | 8 | 세션 복구, 라우팅, 미커밋, 테스트 실패(2), 모드, 계획 확인, QA 재시도, 커밋 |
| skills/migrate/SKILL.md | 7 | 세션 복구, 라우팅, 테스트 실패, 모드, 계획 확인, QA 옵션, 커밋 (+버전 입력은 유지) |
| skills/code-review/SKILL.md | 3 | 모드, 큰 diff 경고, 확인 게이트 |
| skills/codebase-audit/SKILL.md | 3 | 범위 제안, 모드, 확인 게이트 |
| skills/md-generate/SKILL.md | 5 | git 경고, 라우팅, 언어 선택, Phase 2 확인, 평가자 수정 |
| skills/md-optimize/SKILL.md | 4 | git 경고, 라우팅, Phase 2 확인, 평가자 수정 |

## 설계

### 공통 규칙 (각 SKILL.md에 한 번 정의)

각 스킬의 기존 규칙 섹션(Key Rules 또는 동등 위치)에 다음을 추가:

```
## User Interaction 규칙

모든 사용자 문답은 AskUserQuestion 도구를 우선 사용한다.
- AskUserQuestion 도구가 사용 가능하면 → 도구로 질문 (번호 선택 UI)
- 도구가 없거나 호출 실패하면 → 동일한 선택지를 텍스트로 제시하고 번호/키워드 응답을 파싱
- 모든 선택지에는 label(짧은 이름)과 description(구체적 설명)을 포함
- 자유 텍스트 입력이 필요한 경우 "Other" 옵션으로 자동 지원됨
```

### 유형별 AskUserQuestion 정의

#### A. 모드 선택

각 스킬별로 모드명/설명이 다름. 자동 감지된 권장 모드의 label에 `(권장)` 접미사 추가.

**workflow:**
```
header: "모드 선택"
question: "워크플로우 모드를 선택하세요:"
options:
  - label: "standard (권장)" / description: "2명 전문가 분석 + 통합. ~1.5x 토큰"
  - label: "single" / description: "1명 에이전트. 빠르고 토큰 절약"
  - label: "multi" / description: "3명 전문가 + 교차 검토. ~2-2.5x 토큰"
```

**refactor:** (파일 수 기반 권장)
```
header: "모드 선택"
question: "리팩토링 모드를 선택하세요: (범위: N개 파일)"
options:
  - label: "single" / description: "순차 분석 + 실행. 빠르고 토큰 절약"
  - label: "multi" / description: "3명 분석가 + 교차 검토 + Safety Advisor"
  - label: "comprehensive" / description: "multi + 추가 검증. 대규모 리팩토링용"
```

**migrate:**
```
header: "모드 선택"
question: "마이그레이션 모드를 선택하세요:"
options:
  - label: "single" / description: "1명 에이전트. 단순 버전 업그레이드에 적합"
  - label: "multi" / description: "2명 분석가 + Migration Advisor. 복잡한 마이그레이션용"
```

**code-review:** (diff 크기 기반 권장)
```
header: "리뷰 모드"
question: "코드 리뷰 깊이를 선택하세요: (Diff: N 파일, M 줄)"
options:
  - label: "quick" / description: "1명 리뷰어. 5-perspective 체크리스트. 빠른 피드백"
  - label: "deep" / description: "2명 전문가 + 종합. ~1.5x 토큰"
  - label: "thorough" / description: "3명 전문가 + 교차 검증 + 종합. ~2.5x 토큰"
```

**codebase-audit:** (파일 수 기반 권장)
```
header: "감사 모드"
question: "코드베이스 감사 모드를 선택하세요: (N개 파일)"
options:
  - label: "quick" / description: "1명 분석가. 빠른 구조 파악"
  - label: "deep" / description: "2명 분석가 + 통합. ~1.5x 토큰"
  - label: "thorough" / description: "3명 분석가 + 교차 비평 + 통합. ~2.5x 토큰"
```

#### B. 확인 게이트 (HARD-GATE)

모든 확인 게이트에 동일 패턴 적용. HARD-GATE 의미론 유지 — "진행"만 다음 단계로 넘어감.

**workflow spec 확인:**
```
header: "Spec 확인"
question: "spec.md를 확인하셨나요? 구현에 상당한 토큰이 소요됩니다."
options:
  - label: "진행" / description: "spec 대로 구현을 시작합니다"
  - label: "수정 필요" / description: "spec을 수정한 후 다시 확인합니다"
  - label: "중단" / description: "워크플로우를 중단합니다"
```

**refactor 계획 확인 (multi/comprehensive 추가 경고):**
```
header: "계획 확인"
question: "리팩토링 계획을 확인하셨나요? multi 모드는 ~{N}x 토큰을 사용합니다."
options:
  - label: "진행" / description: "계획대로 리팩토링을 시작합니다"
  - label: "수정 필요" / description: "계획을 수정한 후 다시 확인합니다"
  - label: "single로 전환" / description: "single 모드로 전환하여 토큰을 절약합니다"
  - label: "중단" / description: "리팩토링을 중단합니다"
```

**code-review 확인:**
```
header: "리뷰 확인"
question: "{모드} 리뷰는 여러 서브에이전트를 실행합니다."
options:
  - label: "진행" / description: "{모드} 리뷰를 시작합니다"
  - label: "quick으로 전환" / description: "quick 모드로 전환합니다"
  - label: "중단" / description: "리뷰를 중단합니다"
```

**codebase-audit 확인:**
```
header: "감사 확인"
question: "{모드} 모드는 quick 대비 ~{비용}x 토큰을 사용합니다."
options:
  - label: "진행" / description: "{모드} 감사를 시작합니다"
  - label: "{낮은 모드}로 전환" / description: "더 가벼운 모드로 전환합니다"
  - label: "중단" / description: "감사를 중단합니다"
```

**migrate 계획 확인:**
```
header: "계획 확인"
question: "마이그레이션 계획을 확인하셨나요?"
options:
  - label: "진행" / description: "계획대로 단계별 마이그레이션을 시작합니다"
  - label: "수정 필요" / description: "계획을 수정한 후 다시 확인합니다"
  - label: "중단" / description: "마이그레이션을 중단합니다"
```

**md-generate Phase 2 확인:**
```
header: "생성 확인"
question: "분석 결과를 확인하셨나요? CLAUDE.md를 생성/업데이트합니다."
options:
  - label: "진행" / description: "분석 결과대로 CLAUDE.md를 생성합니다"
  - label: "수정 필요" / description: "섹션 구성을 조정한 후 다시 확인합니다"
  - label: "중단" / description: "생성을 중단합니다"
```

**md-optimize Phase 2 확인:**
```
header: "최적화 확인"
question: "최적화 계획을 확인하셨나요? 마크다운 파일을 재구성합니다."
options:
  - label: "진행" / description: "계획대로 최적화를 실행합니다"
  - label: "수정 필요" / description: "존 할당을 조정한 후 다시 확인합니다"
  - label: "중단" / description: "최적화를 중단합니다"
```

#### C. Step 7 커밋 (핵심 개선)

```
header: "커밋"
question: "구현이 완료되었습니다. 커밋 방법을 선택하세요:"
options:
  - label: "코드만 커밋 (권장)" / description: "아티팩트(.harness/, docs/harness/) 정리 후 코드 변경만 커밋"
  - label: "전체 커밋" / description: "아티팩트(spec.md, changes.md, qa_report.md) 포함 전체 커밋"
  - label: "커밋 안 함" / description: ".harness/ 정리만 하고 커밋하지 않음"
```

"코드만 커밋" 선택 시:
1. `.harness/` 디렉토리 삭제
2. `docs/harness/<slug>/` 디렉토리 삭제
3. 코드 변경사항만 stage & commit

"전체 커밋" 선택 시:
1. `.harness/` 디렉토리 삭제
2. `docs/harness/<slug>/` 파일들 + 코드 변경사항 stage & commit

"커밋 안 함" 선택 시:
1. `.harness/` 디렉토리 삭제
2. 커밋하지 않음 (변경사항은 working tree에 유지)

#### D. QA 재시도

**workflow/refactor:**
```
header: "QA 결과"
question: "QA 결과: FAIL. [실패 요약]"
options:
  - label: "수정 진행" / description: "FAIL 항목만 수정하는 다음 라운드를 실행합니다"
  - label: "현재 상태로 완료" / description: "수정 없이 현재 상태로 마무리합니다"
```

**migrate (3가지 옵션):**
```
header: "QA 결과"
question: "마이그레이션 검증: FAIL. [실패 요약]"
options:
  - label: "수정 시도" / description: "문제를 수정합니다"
  - label: "현재 상태 수락" / description: "수정 없이 현재 상태를 수락합니다"
  - label: "롤백" / description: "모든 변경사항을 되돌립니다"
```

#### E. 세션 복구

```
header: "세션 복구"
question: "[harness] 이전 세션이 감지되었습니다. [상태 표시]"
options:
  - label: "재개" / description: "이전 세션의 {phase}부터 이어서 진행합니다"
  - label: "재시작" / description: ".harness/ 삭제 후 처음부터 시작합니다"
  - label: "중단" / description: ".harness/ 삭제 후 종료합니다"
```

#### F. 경고/확인

**미커밋 변경사항 (refactor, md-generate, md-optimize):**
```
header: "미커밋 변경"
question: "미커밋 변경사항이 감지되었습니다."
options:
  - label: "커밋 후 진행" / description: "변경사항을 커밋한 후 스킬을 실행합니다"
  - label: "Stash 후 진행" / description: "변경사항을 stash한 후 스킬을 실행합니다"
  - label: "그대로 진행" / description: "미커밋 상태로 계속 진행합니다"
```

**기본 테스트 실패 (refactor — 실패 시):**
```
header: "테스트 실패"
question: "기본 테스트가 실패합니다: N개 실패."
options:
  - label: "먼저 수정" / description: "실패한 테스트를 수정한 후 리팩토링을 시작합니다"
  - label: "그대로 진행" / description: "알려진 실패 상태로 리팩토링을 진행합니다"
```

**기본 테스트 미검출 (refactor — 테스트 없을 때):**
```
header: "테스트 없음"
question: "테스트 스위트가 감지되지 않았습니다. 코드 리뷰만으로 검증합니다."
options:
  - label: "진행" / description: "테스트 없이 리팩토링을 시작합니다"
  - label: "중단" / description: "리팩토링을 중단합니다"
```

**기본 테스트 실패 (migrate):**
```
header: "테스트 실패"
question: "기본 테스트가 실패 중입니다 (N 실패). 마이그레이션 회귀 파악이 어려울 수 있습니다."
options:
  - label: "계속 진행" / description: "실패 상태로 마이그레이션을 진행합니다"
  - label: "먼저 수정" / description: "테스트를 수정한 후 마이그레이션을 시작합니다"
  - label: "중단" / description: "마이그레이션을 중단합니다"
```

**큰 diff 경고 (code-review):**
```
header: "큰 Diff"
question: "큰 diff가 감지됨 (N 줄). 리뷰 품질이 저하될 수 있습니다."
options:
  - label: "진행" / description: "전체 diff를 리뷰합니다"
  - label: "중단" / description: "더 작은 범위로 나누어 리뷰합니다"
```

**테스트 회귀 중단 (refactor):**
```
header: "테스트 회귀"
question: "테스트 회귀 감지 (Step N). 실패: {테스트명}."
options:
  - label: "단계 되돌리기" / description: "이 단계의 변경을 되돌리고 다음 단계로 진행합니다"
  - label: "수동 수정" / description: "직접 수정한 후 계속 진행합니다"
  - label: "리팩토링 중단" / description: "리팩토링을 중단하고 현재 상태를 유지합니다"
```

**빌드/테스트 실패 (migrate):**
```
header: "빌드 실패"
question: "Step N에서 빌드/테스트가 실패했습니다."
options:
  - label: "수동 수정 후 재개" / description: "오류를 확인하고 수정한 후 계속 진행합니다"
  - label: "중단" / description: "마이그레이션을 중단합니다"
```

**git 비관리 경고 (md-generate, md-optimize):**
```
header: "Git 경고"
question: "이 프로젝트는 git으로 관리되지 않습니다. 롤백이 불가능합니다."
options:
  - label: "진행" / description: "롤백 안전성 없이 진행합니다"
  - label: "중단" / description: "작업을 중단합니다"
```

#### G. 스마트 라우팅

```
header: "스킬 전환"
question: "[상황 설명]. 다른 스킬이 더 적합할 수 있습니다."
options:
  - label: "전환: /{추천 스킬}" / description: "{추천 스킬 설명}"
  - label: "계속 진행" / description: "현재 스킬로 계속 진행합니다"
```

#### H. 특수 케이스

**codebase-audit 범위 제안:**
```
header: "범위 설정"
question: "프로젝트에 N개 파일이 있습니다. 범위를 좁히면 더 빠르고 정확합니다."
options:
  - label: "제안 범위 적용" / description: "{감지된 범위}로 제한하여 분석합니다"
  - label: "전체 스캔" / description: "전체 프로젝트를 분석합니다"
```
Other로 사용자가 직접 범위 입력 가능.

**md-generate 언어 선택:**
```
header: "콘텐츠 언어"
question: "CLAUDE.md 콘텐츠의 언어를 선택하세요:"
options:
  - label: "English (권장)" / description: "Claude가 가장 잘 이해하는 영어로 작성"
  - label: "{사용자 언어}" / description: "사용자의 언어로 작성"
  - label: "Hybrid" / description: "기술 용어는 영어, 설명은 사용자 언어"
```

**md-generate/md-optimize 평가자 수정:**
```
header: "평가자 수정"
question: "평가자가 {N}개 이슈를 발견했습니다: [이슈 목록]"
options:
  - label: "전체 수정" / description: "모든 이슈를 자동 수정합니다"
  - label: "수정 안 함" / description: "이슈를 무시하고 현재 상태를 유지합니다"
```
Other로 "1,3번만 수정" 같은 선택적 수정 지정 가능.

**migrate 버전 감지:** AskUserQuestion 대상에서 **제외**. 버전 번호는 자유 텍스트 입력이 필수이므로 기존 패턴 유지. 단, 자동 감지된 버전이 있으면 선택지로 제안:
```
header: "버전 확인"
question: "현재 버전이 {감지된 버전}으로 감지되었습니다."
options:
  - label: "{감지된 버전} 사용" / description: "감지된 버전을 사용합니다"
  - label: "직접 입력" / description: "다른 버전을 직접 입력합니다"
```
감지 실패 시 기존 텍스트 입력 유지.

## 전환 대상에서 제외

- **migrate 버전 입력** (감지 실패 시): 자유 텍스트 입력 필수
- **codebase-audit 증분 모드 알림**: 상태 알림이지 선택이 아님

## 완료 기준

- [ ] 7개 SKILL.md에 "User Interaction 규칙" 공통 블록 추가
- [ ] workflow: 5개 문답 지점 AskUserQuestion 전환
- [ ] refactor: 8개 문답 지점 AskUserQuestion 전환
- [ ] migrate: 7개 문답 지점 AskUserQuestion 전환 (+버전 감지 조건부)
- [ ] code-review: 3개 문답 지점 AskUserQuestion 전환
- [ ] codebase-audit: 3개 문답 지점 AskUserQuestion 전환
- [ ] md-generate: 5개 문답 지점 AskUserQuestion 전환
- [ ] md-optimize: 4개 문답 지점 AskUserQuestion 전환
- [ ] Step 7 커밋 질문: 3가지 선택지 (코드만 커밋(권장)/전체 커밋/커밋 안 함)
- [ ] 모든 AskUserQuestion에 텍스트 폴백 패턴 포함
- [ ] 모든 선택지에 label + description 포함
- [ ] 동적 권장 모드에 (권장) 접미사 추가
- [ ] 템플릿(templates/**/*.md) 무변경
