# Release Code Review Summary

You are generating a **Release Code Review Summary** — a focused diff analysis to verify the release is safe and well-formed. Your job is to examine what changed, verify file paths exist, and surface any release-blocking concerns.

This is NOT a full code review. Focus only on release-readiness: correctness of the diff, missing files, obvious bugs, security issues.

## Release Context

- **Version**: `{release_version}`
- **Branch**: `{release_branch}`
- **Repo**: `{repo_path}`
- **Lang**: `{lang}`

## Instructions

1. **Get the diff** — run `git diff {base_branch}...{release_branch} --stat` to see what changed. Then run `git diff {base_branch}...{release_branch}` for full diff (limit to first 500 lines if very large, note truncation).

2. **Verify file paths** — for each file in the diff:
   - Confirm the file actually exists (not accidentally deleted or misnamed)
   - Check for leftover conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
   - Check for debug artifacts (`console.log`, `print(`, `debugger;`, `binding.pry`)

3. **Assess the diff** — analyze from a release-readiness lens:
   - Are there obviously broken imports or references?
   - Are new dependencies added? If so, are they in the lock file?
   - Are version strings consistent (package.json, constants, etc.)?
   - Any hardcoded secrets, tokens, or credentials?
   - Are error handlers present for new code paths?

4. **Write the summary** to `{output_path}`:

```markdown
# Release Code Review Summary

- **version**: {release_version}
- **timestamp**: {ISO8601 timestamp}
- **verdict**: PASS | FAIL | WARN

## Diff Statistics
- Files changed: {N}
- Insertions: +{N}
- Deletions: -{N}

## File Path Verification
- All files verified: YES | NO
- Missing files: (list if any)
- Conflict markers found: YES (list files) | NO
- Debug artifacts found: YES (list files:line) | NO

## Release-Readiness Assessment
- Broken imports/references: YES (details) | NONE
- New dependencies: YES (list) | NONE — lock file updated: YES | NO | N/A
- Version string consistency: OK | MISMATCH (details)
- Hardcoded secrets: NONE | FOUND (FAIL — details)
- Error handling coverage: ADEQUATE | GAPS (details)

## Issues Found
(List each issue with severity: BLOCKING | WARNING | INFO)

## Release Recommendation
{one paragraph: safe to release / concerns to address}
```

## Verdict Rules

- **PASS**: No blocking issues, all files verified, no conflict markers, no secrets
- **FAIL**: Any of: conflict markers found, hardcoded secrets, missing files, broken imports
- **WARN**: Non-blocking concerns found (debug artifacts, missing lock file update, etc.)

## Output Contract

CRITICAL: Your response must be EXACTLY ONE LINE. Write all details to the output file above.

If PASS:
```
PASS — {N} files changed, no blocking issues
```

If FAIL:
```
FAIL — {blocking_issue_count} blocking issue(s): {first issue one-liner}
```

If WARN:
```
WARN — {N} files changed, {warning_count} concern(s): {first concern one-liner}
```

No other text after this line.
