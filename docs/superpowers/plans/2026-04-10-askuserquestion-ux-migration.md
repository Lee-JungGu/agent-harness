# AskUserQuestion UX 전면 전환 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7개 SKILL.md 파일의 모든 사용자 문답(~36개 지점)을 AskUserQuestion 번호 선택으로 전환하고, Step 7 커밋 질문을 3가지 선택지로 개선한다.

**Architecture:** 각 SKILL.md에 "User Interaction 규칙" 공통 블록을 추가하고, 기존 텍스트 기반 문답을 AskUserQuestion 패턴으로 교체한다. 이미 모델 구성 선택에서 검증된 `AskUserQuestion 사용 가능 → 도구, else → 텍스트` 폴백 패턴을 전체 문답으로 확산한다.

**Tech Stack:** Markdown (SKILL.md 선언적 워크플로우), AskUserQuestion 도구 (Claude Code)

**Spec:** `docs/superpowers/specs/2026-04-10-askuserquestion-ux-migration-design.md`

---

## 공통 참조: AskUserQuestion 패턴

모든 태스크에서 사용하는 공통 패턴. 각 문답 지점에 이 패턴을 적용한다:

```markdown
Use AskUserQuestion to ask the user (in `user_lang`):
  header: "{짧은 라벨}"
  question: "{질문 텍스트}"
  options:
    - label: "{선택지1}" / description: "{설명1}"
    - label: "{선택지2}" / description: "{설명2}"
    ...
If AskUserQuestion is not available, present the same options as a text question and accept number or keyword responses.
```

## 공통 참조: User Interaction 규칙 블록

각 SKILL.md의 기존 규칙 섹션(예: `## Key Rules`) 직전에 삽입:

```markdown
## User Interaction Rules

All user-facing questions MUST use AskUserQuestion tool when available.
- If AskUserQuestion is available → use it (provides numbered selection UI)
- If AskUserQuestion is NOT available or fails → present the same options as text and accept number/keyword responses (case-insensitive)
- Every option must include a `label` (short name) and `description` (specific explanation)
- "Other" (free text input) is automatically appended by the framework
- Translate all question text, labels, and descriptions to `user_lang`
```

---

### Task 1: workflow/SKILL.md — Canonical Pattern (5 지점)

**Files:**
- Modify: `skills/workflow/SKILL.md`

이 태스크가 canonical pattern을 확립한다. 나머지 6개 태스크는 이 패턴을 따른다.

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

`skills/workflow/SKILL.md`를 읽고 다음 5개 문답 지점을 찾는다:
1. Session Recovery (약 38-49줄): "resume / restart / stop" 텍스트 선택
2. Mode selection (약 76줄): "(1) single (2) standard (3) multi" 텍스트 입력
3. Spec confirmation HARD-GATE (약 190-205줄): "go/proceed/approve/yes/ok/lgtm" 텍스트
4. QA FAIL retry (약 306-310줄): "proceed / stop" 텍스트
5. Step 7 Cleanup & Commit (약 312-316줄): "commit / skip" 텍스트

- [ ] **Step 2: User Interaction Rules 블록 추가**

`## Key Rules` 직전에 위의 "User Interaction Rules" 공통 블록을 삽입한다.

- [ ] **Step 3: Session Recovery 전환**

기존 세션 복구 질문을 AskUserQuestion으로 교체한다.

기존 패턴 (찾아서 교체):
```
Ask the user (in their language) whether to resume, restart, or stop:
```

새 패턴:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Session"
  question: "[harness] Previous session detected. [print status]. Resume, restart, or stop?"
  options:
    - label: "Resume" / description: "Continue from {phase} where the previous session left off"
    - label: "Restart" / description: "Delete .harness/ and start from scratch"
    - label: "Stop" / description: "Delete .harness/ and halt"
```

동작 매핑은 기존과 동일:
- Resume → 해당 phase로 점프
- Restart → `.harness/` 삭제 후 Step 1
- Stop → `.harness/` 삭제 후 중단

- [ ] **Step 4: Mode selection 전환**

기존 mode 선택을 AskUserQuestion으로 교체한다.

기존 패턴:
```
ask the user (in `user_lang`) to choose: (1) single — fast, token-saving; (2) standard — balanced analysis, ~1.5x tokens; (3) multi — deep multi-agent analysis, ~2-2.5x tokens. Accept: "1", "2", "3", "single", "standard", "multi" (case-insensitive). Re-ask on unrecognized input.
```

새 패턴:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Mode"
  question: "Select workflow mode:"
  options:
    - label: "standard (Recommended)" / description: "2 specialists analyze + synthesize. ~1.5x tokens. Balanced depth"
    - label: "single" / description: "1 agent. Fast, token-saving. Best for simple tasks"
    - label: "multi" / description: "3 specialists + cross-critique. ~2-2.5x tokens. Deepest analysis"

If `--mode` was passed, skip the prompt (unchanged behavior).
```

- [ ] **Step 5: Spec confirmation HARD-GATE 전환**

HARD-GATE 섹션을 AskUserQuestion으로 교체한다.

기존 `<HARD-GATE>` 블록 전체를 교체:

```markdown
<HARD-GATE>
Show spec.md to the user and ask for explicit confirmation using AskUserQuestion (in `user_lang`):
  header: "Spec"
  question: "Review the spec above. Implementation consumes significant tokens. Confirm to proceed."
  options:
    - label: "Proceed" / description: "Start implementation as specified"
    - label: "Modify" / description: "Edit the spec, then re-confirm"
    - label: "Stop" / description: "Halt the workflow"

If user selects "Modify" or provides modification details via "Other": update spec.md and re-present this question.
If user selects "Stop": halt the workflow.
Only "Proceed" advances to the Generator phase.
</HARD-GATE>
```

- [ ] **Step 6: QA FAIL retry 전환**

기존 QA 실패 재시도 프롬프트를 교체한다.

기존 패턴:
```
"QA result: FAIL. [failure summary]. Proceed to next round? (proceed / stop)"
```

새 패턴:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "QA"
  question: "QA result: FAIL. [failure summary]."
  options:
    - label: "Fix" / description: "Run next round to fix FAIL items only"
    - label: "Accept as-is" / description: "Finish without fixing, keep current state"
```

- [ ] **Step 7: Step 7 Cleanup & Commit 전환 (핵심 개선)**

기존 Step 7의 커밋 질문을 3가지 선택지로 교체한다.

기존 패턴:
```
Ask the user (in `user_lang`) whether to commit the artifacts (spec.md, changes.md, qa_report.md).
- If commit: stage and commit `docs/harness/<slug>/` files
- Clean up `.harness/` directory
```

새 패턴:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Commit"
  question: "Implementation complete. Choose how to finish:"
  options:
    - label: "Commit code only (Recommended)" / description: "Clean up artifacts (.harness/, docs/harness/) then commit code changes only"
    - label: "Commit all" / description: "Commit everything including artifacts (spec.md, changes.md, qa_report.md)"
    - label: "No commit" / description: "Clean up .harness/ only, do not commit (changes remain in working tree)"

Actions:
- "Commit code only": delete `.harness/` dir, delete `docs/harness/<slug>/` dir, stage and commit remaining code changes
- "Commit all": delete `.harness/` dir, stage and commit `docs/harness/<slug>/` files + code changes
- "No commit": delete `.harness/` dir only
```

- [ ] **Step 8: 검증 및 커밋**

변경사항을 검증한다:
1. "User Interaction Rules" 블록이 Key Rules 직전에 있는지 확인
2. 5개 문답 지점 모두 AskUserQuestion 패턴으로 전환되었는지 확인
3. `--mode` CLI 인자 스킵 로직이 보존되었는지 확인
4. HARD-GATE 태그가 유지되었는지 확인
5. model_config 선택 (이미 AskUserQuestion 사용 중)은 변경하지 않았는지 확인

```bash
git add skills/workflow/SKILL.md
git commit -m "feat(workflow): convert all user prompts to AskUserQuestion

- Session recovery: resume/restart/stop numbered selection
- Mode selection: single/standard/multi with descriptions
- Spec confirmation: proceed/modify/stop (HARD-GATE preserved)
- QA retry: fix/accept-as-is
- Step 7 commit: 3 options (code-only/all/none) - key UX improvement"
```

---

### Task 2: refactor/SKILL.md (8 지점)

**Files:**
- Modify: `skills/refactor/SKILL.md`

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

`skills/refactor/SKILL.md`를 읽고 다음 8개 문답 지점을 찾는다:
1. Session Recovery: "resume / restart / stop"
2. Smart Routing: "계속 진행 / 전환"
3. Uncommitted changes warning: "commit / stash / proceed anyway"
4. Baseline test failure: "fix / proceed with known failures"
5. No test suite detected: "proceed / abort"
6. Mode selection: "(1) single (2) multi (3) comprehensive"
7. Plan confirmation HARD-GATE
8. Test regression halt: "revert step / manual fix / abort"
9. QA FAIL retry: "proceed / stop"
10. Step 7 Cleanup & Commit

주의: 4번과 5번은 조건 분기로 별도 상황. 총 8개 고유 문답이 있지만 테스트 관련이 2가지 시나리오.

- [ ] **Step 2: User Interaction Rules 블록 추가**

`## Key Rules` 직전에 공통 블록 삽입 (Task 1과 동일 텍스트).

- [ ] **Step 3: Session Recovery 전환**

Task 1 Step 3과 동일 패턴 적용.

- [ ] **Step 4: Smart Routing 전환**

기존 패턴: "계속 진행하시겠습니까? (진행 / 전환)"

새 패턴:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Routing"
  question: "[detected mismatch description]. A different skill may be more appropriate."
  options:
    - label: "Switch: /{suggested skill}" / description: "{why the suggested skill fits better}"
    - label: "Continue" / description: "Proceed with /refactor as planned"
```

- [ ] **Step 5: Uncommitted changes 전환**

기존 패턴: "커밋 또는 stash하시겠습니까? (커밋 / stash / 계속 진행)"

새 패턴:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Uncommitted"
  question: "Uncommitted changes detected."
  options:
    - label: "Commit first" / description: "Commit changes before starting refactoring"
    - label: "Stash first" / description: "Stash changes before starting refactoring"
    - label: "Proceed anyway" / description: "Continue with uncommitted changes in place"
```

- [ ] **Step 6: Baseline test failure / No test suite 전환**

테스트 실패 시:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Test Fail"
  question: "Baseline tests fail: {N} failures. Refactoring on a broken baseline makes regression detection unreliable."
  options:
    - label: "Fix first" / description: "Fix failing tests before starting refactoring"
    - label: "Proceed anyway" / description: "Continue with known test failures"
```

테스트 미검출 시:
```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "No Tests"
  question: "No test suite detected. Behavior preservation will be verified by code review only."
  options:
    - label: "Proceed" / description: "Start refactoring without test safety net"
    - label: "Abort" / description: "Stop and add tests first"
```

- [ ] **Step 7: Mode selection 전환**

```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Mode"
  question: "Select refactoring mode: (scope: {N} files)"
  options:
    - label: "single" / description: "Sequential analysis + execution. Fast, token-saving"
    - label: "multi" / description: "3 analysts + cross-critique + Safety Advisor"
    - label: "comprehensive" / description: "multi + additional verification. For large-scale refactoring"

Auto-detected recommendation: add "(Recommended)" to the label of the suggested mode based on file count (<3 → single, 3-10 → multi, 10+ → comprehensive).
If `--mode` was passed, skip the prompt.
```

- [ ] **Step 8: Plan confirmation HARD-GATE 전환**

```markdown
<HARD-GATE>
Show refactor_plan.md to the user and ask using AskUserQuestion (in `user_lang`):
  header: "Plan"
  question: "Review the refactoring plan above. {mode} mode uses ~{N}x tokens vs single."
  options:
    - label: "Proceed" / description: "Start refactoring as planned"
    - label: "Modify" / description: "Edit the plan, then re-confirm"
    - label: "Switch to single" / description: "Switch to single mode to save tokens"
    - label: "Stop" / description: "Halt the refactoring"

Only "Proceed" advances to execution.
</HARD-GATE>
```

- [ ] **Step 9: Test regression halt 전환**

```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Regression"
  question: "Test regression detected (Step {N}). Failed: {test name}. This test passed at baseline."
  options:
    - label: "Revert step" / description: "Revert this step's changes and proceed to next"
    - label: "Manual fix" / description: "Fix the issue manually, then continue"
    - label: "Abort refactoring" / description: "Stop refactoring and keep current state"
```

- [ ] **Step 10: QA FAIL retry + Step 7 Commit 전환**

QA retry: Task 1 Step 6과 동일 패턴.
Step 7 commit: Task 1 Step 7과 동일 패턴 (3가지 선택지).

- [ ] **Step 11: 검증 및 커밋**

모든 문답 지점이 전환되었는지 확인. model_config 선택(이미 AskUserQuestion)은 미변경 확인.

```bash
git add skills/refactor/SKILL.md
git commit -m "feat(refactor): convert all user prompts to AskUserQuestion

- Session recovery, smart routing, uncommitted changes warning
- Baseline test failure/no-test scenarios
- Mode selection with auto-recommendation
- Plan confirmation (HARD-GATE), test regression halt
- QA retry, Step 7 commit (3 options)"
```

---

### Task 3: migrate/SKILL.md (7 지점 + 버전 감지 조건부)

**Files:**
- Modify: `skills/migrate/SKILL.md`

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

8개 문답 지점:
1. Session Recovery
2. Smart Routing
3. Version detection (조건부 — 감지 성공 시 AskUserQuestion, 실패 시 텍스트 유지)
4. Baseline test failure
5. Mode selection: "(1) single (2) multi"
6. Migration plan confirmation HARD-GATE
7. Build/test failure halt
8. QA FAIL options: "fix / stop / rollback" (3가지)
9. Step 7 Cleanup & Commit

- [ ] **Step 2: User Interaction Rules 블록 추가**

- [ ] **Step 3: Session Recovery + Smart Routing 전환**

Task 2와 동일 패턴.

- [ ] **Step 4: Version detection 조건부 전환**

기존 패턴: "현재 버전을 입력하세요:" / "대상 버전을 입력하세요:" (자유 텍스트)

새 패턴: 감지된 버전이 있을 때만 AskUserQuestion:
```markdown
If current version was auto-detected:
  Ask using AskUserQuestion (in `user_lang`):
    header: "Version"
    question: "Current version detected as {detected_version}."
    options:
      - label: "Use {detected_version}" / description: "Use the auto-detected version"
      - label: "Enter manually" / description: "Type a different version number"
  If "Enter manually" or "Other": ask as text "Enter current version:"

If current version was NOT detected:
  Ask as text: "Enter current version:" (no AskUserQuestion — free text input required)

Same pattern for target version.
```

- [ ] **Step 5: Baseline test failure 전환**

```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Test Fail"
  question: "Baseline tests are failing ({N} failures). Identifying migration-caused regressions will be difficult."
  options:
    - label: "Continue" / description: "Proceed with migration despite test failures"
    - label: "Fix first" / description: "Fix tests before starting migration"
    - label: "Abort" / description: "Cancel the migration"
```

- [ ] **Step 6: Mode selection 전환**

```markdown
Ask the user using AskUserQuestion (in `user_lang`):
  header: "Mode"
  question: "Select migration mode:"
  options:
    - label: "single" / description: "1 agent. Best for simple version upgrades"
    - label: "multi" / description: "2 analysts + Migration Advisor. For complex migrations"

If `--mode` was passed, skip the prompt.
```

- [ ] **Step 7: Plan confirmation HARD-GATE + Build/test failure 전환**

Plan confirmation:
```markdown
<HARD-GATE>
Ask using AskUserQuestion (in `user_lang`):
  header: "Plan"
  question: "Review the migration plan above. Each step is applied one at a time and can be stopped anytime."
  options:
    - label: "Proceed" / description: "Start staged migration as planned"
    - label: "Modify" / description: "Edit the plan, then re-confirm"
    - label: "Stop" / description: "Halt the migration"
</HARD-GATE>
```

Build/test failure:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Build Fail"
  question: "Build/test failed at Step {N}. See error details above."
  options:
    - label: "Manual fix & resume" / description: "Review errors, fix manually, then continue"
    - label: "Abort" / description: "Stop the migration"
```

- [ ] **Step 8: QA FAIL options (3가지) + Step 7 Commit 전환**

QA 실패 (migrate는 3가지):
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "QA"
  question: "Migration verification: FAIL. [failure summary]."
  options:
    - label: "Fix" / description: "Attempt to fix the issues"
    - label: "Accept" / description: "Accept current state as-is"
    - label: "Rollback" / description: "Revert all migration changes"
```

Step 7: Task 1 Step 7과 동일 패턴.

- [ ] **Step 9: 검증 및 커밋**

```bash
git add skills/migrate/SKILL.md
git commit -m "feat(migrate): convert all user prompts to AskUserQuestion

- Session recovery, smart routing, version detection (conditional)
- Baseline test failure, mode selection
- Plan confirmation (HARD-GATE), build/test failure halt
- QA options (fix/accept/rollback), Step 7 commit (3 options)"
```

---

### Task 4: code-review/SKILL.md (3 지점)

**Files:**
- Modify: `skills/code-review/SKILL.md`

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

3개 문답 지점:
1. Large diff warning (약 60줄): "proceed / abort"
2. Mode selection (약 72-94줄): "(1) quick (2) deep (3) thorough"
3. Confirmation gate for deep/thorough (약 126-140줄): "proceed / switch to quick / stop"

- [ ] **Step 2: User Interaction Rules 블록 추가**

`## Key Rules` 직전에 공통 블록 삽입.

- [ ] **Step 3: Large diff warning 전환**

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Large Diff"
  question: "Large diff detected ({N} lines). Review quality may degrade for very large diffs."
  options:
    - label: "Proceed" / description: "Review the full diff"
    - label: "Abort" / description: "Split into smaller chunks and review separately"
```

- [ ] **Step 4: Mode selection 전환**

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Review Mode"
  question: "Select review depth: (Diff: {N} files, {M} lines)"
  options:
    - label: "quick" / description: "1 reviewer, 5-perspective checklist. Fast feedback"
    - label: "deep" / description: "2 specialists + synthesis. ~1.5x tokens"
    - label: "thorough" / description: "3 specialists + cross-verification + synthesis. ~2.5x tokens"

Auto-detected recommendation: add "(Recommended)" based on diff size (<100 lines → quick, 100-500 → deep, 500+ → thorough).
If `--mode` was passed, skip.
```

- [ ] **Step 5: Confirmation gate 전환**

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Confirm"
  question: "{mode} review runs multiple sub-agents and uses more tokens."
  options:
    - label: "Proceed" / description: "Start {mode} review"
    - label: "Switch to quick" / description: "Use quick mode instead (saves tokens)"
    - label: "Abort" / description: "Cancel the review"
```

- [ ] **Step 6: 검증 및 커밋**

```bash
git add skills/code-review/SKILL.md
git commit -m "feat(code-review): convert all user prompts to AskUserQuestion

- Large diff warning, mode selection with auto-recommendation
- Confirmation gate for deep/thorough modes"
```

---

### Task 5: codebase-audit/SKILL.md (3 지점)

**Files:**
- Modify: `skills/codebase-audit/SKILL.md`

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

3개 문답 지점:
1. Scope suggestion (약 65-74줄): "proceed full scan / set scope"
2. Mode selection (약 76-93줄): "(1) quick (2) deep (3) thorough"
3. Confirmation gate for deep/thorough (약 111-124줄)

- [ ] **Step 2: User Interaction Rules 블록 추가**

- [ ] **Step 3: Scope suggestion 전환**

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Scope"
  question: "Project has {N} files. Narrowing scope produces faster, more focused analysis."
  options:
    - label: "Use suggested scope" / description: "Limit analysis to {suggested_scope}"
    - label: "Full scan" / description: "Analyze the entire project"

"Other" allows user to type a custom scope pattern.
```

- [ ] **Step 4: Mode selection 전환**

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Audit Mode"
  question: "Select audit mode: ({N} files in scope)"
  options:
    - label: "quick" / description: "1 analyst. Fast structure overview"
    - label: "deep" / description: "2 analysts + synthesis. ~1.5x tokens"
    - label: "thorough" / description: "3 analysts + cross-critique + synthesis. ~2.5x tokens"

Auto-recommendation based on file count (<30 → quick, 30-200 → deep, 200+ → thorough).
If `--mode` was passed, skip.
```

- [ ] **Step 5: Confirmation gate 전환**

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Confirm"
  question: "{mode} mode uses ~{cost}x tokens compared to quick mode."
  options:
    - label: "Proceed" / description: "Start {mode} audit"
    - label: "Switch to {lower mode}" / description: "Use a lighter mode to save tokens"
    - label: "Abort" / description: "Cancel the audit"
```

- [ ] **Step 6: 검증 및 커밋**

```bash
git add skills/codebase-audit/SKILL.md
git commit -m "feat(codebase-audit): convert all user prompts to AskUserQuestion

- Scope suggestion, mode selection with auto-recommendation
- Confirmation gate for deep/thorough modes"
```

---

### Task 6: md-generate/SKILL.md (5 지점)

**Files:**
- Modify: `skills/md-generate/SKILL.md`

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

5개 문답 지점:
1. Git status warning (약 34-35줄): non-git / uncommitted
2. Smart routing (약 45-52줄): "switch to /md-optimize / continue"
3. Content language selection (약 136-143줄): "English / user language / Hybrid"
4. Phase 2 confirmation HARD-GATE (약 128-151줄)
5. Evaluator fixes (약 260-263줄): "fix / skip"

- [ ] **Step 2: User Interaction Rules 블록 추가**

md-generate에는 `## Key Rules` 섹션이 없을 수 있으므로, 파일 말미 또는 적절한 규칙 섹션 근처에 삽입.

- [ ] **Step 3: Git status warning 전환**

Non-git:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Git Warning"
  question: "This project is not managed by git. Rollback will not be possible."
  options:
    - label: "Proceed" / description: "Continue without rollback safety"
    - label: "Abort" / description: "Stop and initialize git first"
```

Uncommitted:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Uncommitted"
  question: "Uncommitted changes detected."
  options:
    - label: "Continue" / description: "Proceed with uncommitted changes"
    - label: "Abort" / description: "Stop and commit/stash changes first"
```

- [ ] **Step 4: Smart routing + Language selection 전환**

Smart routing:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Routing"
  question: "{situation description}. Another skill may be more appropriate."
  options:
    - label: "Switch: /md-optimize" / description: "Optimize existing .md files for token efficiency"
    - label: "Continue" / description: "Proceed with CLAUDE.md generation"
```

Language selection:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Language"
  question: "Select the language for CLAUDE.md content:"
  options:
    - label: "English (Recommended)" / description: "Claude understands English best for instructions"
    - label: "{user_lang_name}" / description: "Write in your language"
    - label: "Hybrid" / description: "Technical terms in English, explanations in your language"
```

- [ ] **Step 5: Phase 2 confirmation + Evaluator fixes 전환**

Phase 2 confirmation:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Generate"
  question: "Review analysis above. This will generate/update CLAUDE.md."
  options:
    - label: "Proceed" / description: "Generate CLAUDE.md based on analysis"
    - label: "Modify" / description: "Adjust sections before generating"
    - label: "Stop" / description: "Cancel generation"
```

Evaluator fixes:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Fixes"
  question: "Evaluator found {N} issues: [issue list summary]."
  options:
    - label: "Fix all" / description: "Auto-fix all discovered issues"
    - label: "Skip" / description: "Keep current state, ignore issues"

"Other" allows specifying which issues to fix (e.g., "fix 1,3 only").
```

- [ ] **Step 6: 검증 및 커밋**

```bash
git add skills/md-generate/SKILL.md
git commit -m "feat(md-generate): convert all user prompts to AskUserQuestion

- Git status warning, smart routing
- Content language selection, Phase 2 confirmation
- Evaluator fixes with selective fix option"
```

---

### Task 7: md-optimize/SKILL.md (4 지점)

**Files:**
- Modify: `skills/md-optimize/SKILL.md`

- [ ] **Step 1: 파일 읽기 및 문답 지점 파악**

4개 문답 지점:
1. Git status warning (약 20-24줄): non-git / uncommitted
2. Smart routing (약 32-40줄): "switch to /md-generate / continue"
3. Phase 2 confirmation HARD-GATE (약 59-75줄)
4. Evaluator fixes (약 169-170줄)

- [ ] **Step 2: User Interaction Rules 블록 추가**

- [ ] **Step 3: Git status warning + Smart routing 전환**

Task 6과 동일 패턴. Smart routing의 전환 대상만 `/md-generate`로 변경:

```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Routing"
  question: "{situation description}. CLAUDE.md generation may be needed first."
  options:
    - label: "Switch: /md-generate" / description: "Generate CLAUDE.md first, then optimize"
    - label: "Continue" / description: "Proceed with optimization"
```

- [ ] **Step 4: Phase 2 confirmation + Evaluator fixes 전환**

Phase 2 confirmation:
```markdown
Ask using AskUserQuestion (in `user_lang`):
  header: "Optimize"
  question: "Review optimization plan above. This will restructure markdown files."
  options:
    - label: "Proceed" / description: "Execute the optimization plan"
    - label: "Modify" / description: "Adjust zone assignments before optimizing"
    - label: "Stop" / description: "Cancel optimization"
```

Evaluator fixes: Task 6과 동일 패턴.

- [ ] **Step 5: 검증 및 커밋**

```bash
git add skills/md-optimize/SKILL.md
git commit -m "feat(md-optimize): convert all user prompts to AskUserQuestion

- Git status warning, smart routing
- Phase 2 confirmation, evaluator fixes"
```

---

### Task 8: Cross-skill 일관성 검증

**Files:**
- Read: 7개 SKILL.md 파일 모두

- [ ] **Step 1: User Interaction Rules 블록 일관성 확인**

7개 파일 모두에 동일한 "User Interaction Rules" 블록이 있는지 grep으로 확인:

```bash
grep -l "User Interaction Rules" skills/*/SKILL.md | wc -l
```
Expected: 7

- [ ] **Step 2: Step 7 커밋 옵션 일관성 확인**

Step 7이 있는 스킬(workflow, refactor, migrate)에서 3가지 선택지가 동일한지 확인:

```bash
grep -A5 "Commit code only" skills/workflow/SKILL.md skills/refactor/SKILL.md skills/migrate/SKILL.md
```

- [ ] **Step 3: 텍스트 폴백 일관성 확인**

모든 AskUserQuestion 지시문에 "If AskUserQuestion is not available" 폴백이 명시되어 있는지 확인. 공통 블록에서 한 번 정의하므로 각 개별 지점에는 필요 없지만, 공통 블록이 모든 파일에 있으면 OK.

- [ ] **Step 4: 최종 검증 완료**

모든 검증 통과 시 완료. 문제 발견 시 해당 파일 수정 후 amend 또는 추가 커밋.
