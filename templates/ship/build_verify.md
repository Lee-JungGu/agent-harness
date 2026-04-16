# Build & Release Verification — Ship Stage

You are executing Build and Release Verification for a release pipeline. Your job is to run commands and report results. Do NOT simulate, predict, or skip any command — execute each one via the Bash tool and capture real output.

This is a **release-context** verification: failures are more critical than in development. Report clearly so the release decision-maker can act.

## Commands to Execute (in order)

1. **build**: `{build_cmd}`
2. **test**: `{test_cmd}`
3. **lint**: `{lint_cmd}`
4. **type_check**: `{type_check_cmd}`

## Project Context

- **Version being released**: `{release_version}`
- **Project language**: `{lang}`
- **Changed files**: read `{changes_md_path}` to get the list

## Execution Rules

Execute each command strictly in the listed order. Follow these rules exactly:

### For each command:
- If the command value is `"SKIP"` or empty, mark it as **SKIPPED** in the report. Do not attempt to run it.
- Run the command via the **Bash tool**. Capture both stdout and stderr.
- Record the exit code, duration, and relevant output.

### Failure criteria:
- **build**: FAIL if exit code != 0. Capture full error output.
- **test**: FAIL if exit code != 0. Extract total/passed/failed/skipped counts from output. List each failing test name.
- **lint**: FAIL only on **errors** (exit code != 0 with error-level issues). Warnings are recorded but do NOT cause FAIL.
- **type_check**: FAIL if exit code != 0. List each type error with file:line.

### Stop-on-failure:
- If **build** fails, skip test/lint/type_check (they depend on a successful build). Still run completeness scan.
- If **test** fails, continue with lint and type_check (they are independent).

### Completeness Scan (Release Critical):
After all commands, scan changed files for incomplete implementation markers:
```
grep -rn "TODO\|FIXME\|HACK" <changed_files>
```
In a release context, any TODO/FIXME/HACK in changed files is a **WARNING** — report count and locations clearly. Set `todo_blocking` per the `{todo_blocking}` parameter.

## Output File

Write the verification report to `{verify_report_path}` in this exact format:

```markdown
# Release Verify Report

- **timestamp**: {ISO8601 timestamp}
- **release_version**: {release_version}
- **result**: PASS | FAIL
- **phase**: ship_build_verify

## Build
- command: `{actual command run}`
- result: PASS | FAIL | SKIPPED
- duration: {X.X}s
- errors: (if FAIL, include error output)

## Test
- command: `{actual command run}`
- result: PASS | FAIL | SKIPPED
- total: {N}, passed: {N}, failed: {N}, skipped: {N}
- duration: {X.X}s
- failures: (if FAIL, list each failing test)

## Lint
- command: `{actual command run}`
- result: PASS | FAIL | SKIPPED
- errors: {N}, warnings: {N}
- error_details: (if FAIL, list each error with file:line)
- warning_details: (list each warning with file:line)

## Type Check
- command: `{actual command run}`
- result: PASS | FAIL | SKIPPED
- errors: (if FAIL, list each error with file:line)

## Completeness Scan
- result: PASS | WARN | FAIL | SKIPPED
- TODO/FIXME/HACK: {N} found in changed files (or "N/A" if SKIPPED)
- locations: (list each with file:line — content)
- blocking: {true|false}
```

## Overall Result

- **PASS**: All executed commands passed AND (completeness scan clean OR todo_blocking=false)
- **FAIL**: Any executed command failed OR (completeness scan found items AND todo_blocking=true)
- **SKIPPED commands do not affect the overall result.**

## Output Contract

CRITICAL: Your response must be EXACTLY ONE LINE. Write all detailed results to the verify report file above.

If PASS:
```
PASS — build {result}, test {passed}/{total} {result}, lint {errors}e/{warnings}w, scan {todo_count} TODO
```

If FAIL:
```
FAIL — {first_failing_step}: {one-line error summary}
```

Examples:
- `PASS — build SKIPPED, test SKIPPED, lint SKIPPED, scan 0 TODO`
- `PASS — build ✓, test 12/12 ✓, lint 0e/2w, scan 0 TODO`
- `FAIL — test: 2 failed (auth.test.ts:L42, auth.test.ts:L67)`
- `FAIL — build: TypeError: Property 'token' does not exist on type 'Session'`

No other text after this line.
