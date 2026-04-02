#!/usr/bin/env python3
"""Agent Harness - 3-Phase development workflow for Claude Code."""

import argparse
import io
import os
import re
import subprocess
import sys
from pathlib import Path

# Ensure stdout/stderr use UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _slugify(text: str) -> str:
    """Lowercase, remove non-word chars, replace spaces with hyphens, truncate to 50 chars."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:50]


def cmd_init(args):
    """Initialize ~/.agent-harness/ directory."""
    from config import HarnessConfig
    config = HarnessConfig()
    config.init()
    print(f"[init] Initialized: {config._config_dir}")
    print(f"[init] repos.yaml: {config._repos_path}")
    print("[init] Register repos with: harness repo add --name <name> --path <path> --lang <lang>")


def cmd_repo(args):
    """Manage registered repositories."""
    from config import HarnessConfig
    config = HarnessConfig()

    if args.repo_action == "add":
        try:
            config.add_repo(
                name=args.name,
                path=args.path,
                lang=args.lang,
                test_cmd=args.test_cmd,
                build_cmd=args.build_cmd,
                default_scope=args.default_scope,
            )
            print(f"[repo add] Registered '{args.name}' ({args.path})")
        except ValueError as e:
            print(f"[repo add] Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.repo_action == "list":
        repos = config.load_repos()
        if not repos:
            print("[repo list] No repositories registered.")
            return
        for name, info in repos.items():
            marker = "[+]" if info.get("test_available") else "[-]"
            lang = info.get("lang", "?")
            path = info.get("path", "?")
            print(f"  {marker} {name}  ({lang})  {path}")

    elif args.repo_action == "update":
        kwargs = {}
        if args.path is not None:
            kwargs["path"] = args.path
        if args.lang is not None:
            kwargs["lang"] = args.lang
        if args.test_cmd is not None:
            kwargs["test_cmd"] = args.test_cmd
        if args.build_cmd is not None:
            kwargs["build_cmd"] = args.build_cmd
        if args.default_scope is not None:
            kwargs["default_scope"] = args.default_scope
        try:
            config.update_repo(args.name, **kwargs)
            print(f"[repo update] Updated '{args.name}'")
        except ValueError as e:
            print(f"[repo update] Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.repo_action == "remove":
        try:
            config.remove_repo(args.name)
            print(f"[repo remove] Removed '{args.name}'")
        except ValueError as e:
            print(f"[repo remove] Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_run(args):
    """Start a new harness task."""
    from config import HarnessConfig
    from state import HarnessState
    from phases.planner import render_planner_prompt

    config = HarnessConfig()

    # 1. Load repo config
    if args.repo:
        try:
            repo_cfg = config.get_repo_config(
                args.repo,
                cli_overrides={"scope": args.scope},
            )
        except ValueError as e:
            print(f"[run] Error: {e}", file=sys.stderr)
            sys.exit(1)
        repo_path = Path(repo_cfg["path"])
        repo_name = args.repo
    else:
        # --repo-path provided
        repo_path = Path(args.repo_path)
        lang = args.lang or ""
        if not lang:
            print("[run] Error: --lang is required when using --repo-path", file=sys.stderr)
            sys.exit(1)
        repo_cfg = config.build_adhoc_config(
            repo_path=str(repo_path),
            lang=lang,
            cli_overrides={"scope": args.scope},
        )
        repo_name = repo_path.name

    # 2. Validate repo_path exists
    if not repo_path.exists():
        print(f"[run] Error: repo path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    # 3. Check .harness/ doesn't already exist
    harness_dir = repo_path / ".harness"
    if harness_dir.exists():
        print(
            f"[run] Error: .harness/ already exists in {repo_path}\n"
            "  Use `harness next` to continue, or delete .harness/ to start fresh.",
            file=sys.stderr,
        )
        sys.exit(1)

    # 4. Create .harness/ directory
    harness_dir.mkdir(parents=True)

    # 5. Git safety: checkout new branch
    slug = _slugify(args.task)
    branch_name = f"harness/{slug}"
    try:
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[run] Warning: git checkout -b {branch_name} failed: {result.stderr.strip()}")
            branch_name = "(unknown)"
    except Exception as e:
        print(f"[run] Warning: git not available: {e}")
        branch_name = "(unknown)"

    # 6. Create HarnessState
    scope = repo_cfg.get("default_scope") or "(제한 없음)"
    state = HarnessState.create(
        harness_dir=harness_dir,
        task=args.task,
        repo_name=repo_name,
        repo_path=str(repo_path),
        scope=scope,
        max_rounds=args.max_rounds,
        max_files=args.max_files,
        branch=branch_name,
    )

    # 7. Render planner prompt
    rendered_path = render_planner_prompt(
        harness_dir=str(harness_dir),
        task=args.task,
        repo_path=str(repo_path),
        lang=repo_cfg.get("lang", ""),
        scope=repo_cfg.get("default_scope"),
    )

    if args.dry_run:
        print(f"[run] --dry-run: planner prompt rendered to {rendered_path}")
        print("[run] No state written. Exiting.")
        return

    # 8. Print formatted output with instructions
    print(f"[run] Task started!")
    print(f"  Repo     : {repo_path}")
    print(f"  Branch   : {branch_name}")
    print(f"  Task     : {args.task}")
    print(f"  Scope    : {scope}")
    print(f"  Rounds   : {args.max_rounds} max")
    print(f"  .harness : {harness_dir}")
    print()
    print(f"[run] Planner prompt rendered: {rendered_path}")
    print()
    print("Next steps:")
    print("  1. Open a new Claude Code session in the repo directory")
    print(f"  2. Feed the planner prompt: {rendered_path}")
    print("  3. Claude will write spec.md to .harness/")
    print(f"  4. Run `harness next --repo-path {repo_path}` to advance to the generator phase")


def cmd_next(args):
    """Advance to the next phase."""
    from config import HarnessConfig
    from state import HarnessState
    from phases.generator import render_generator_prompt
    from phases.evaluator import render_evaluator_prompt

    # 1. Find .harness/ in args.repo_path or cwd
    base_path = Path(args.repo_path) if args.repo_path else Path.cwd()
    harness_dir = base_path / ".harness"
    if not harness_dir.exists():
        print(f"[next] Error: .harness/ not found in {base_path}", file=sys.stderr)
        sys.exit(1)

    # 2. Load state
    try:
        state = HarnessState.load(harness_dir)
    except FileNotFoundError as e:
        print(f"[next] Error: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. If completed, print message and return
    if state.phase == "completed":
        print("[next] Task is already completed. Nothing to advance.")
        return

    # 4. Load repo config (try by name, fallback to adhoc)
    config = HarnessConfig()
    try:
        repo_cfg = config.get_repo_config(state.repo_name)
    except Exception:
        repo_cfg = config.build_adhoc_config(
            repo_path=state.repo_path,
            lang="",
        )

    # 5. Call state.advance() (handle FileNotFoundError)
    try:
        state.advance()
    except FileNotFoundError as e:
        print(f"[next] Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[next] Error: {e}", file=sys.stderr)
        sys.exit(1)

    # 6. Based on new state
    scope = state.scope
    test_available = repo_cfg.get("test_available", False)
    build_cmd = repo_cfg.get("build_cmd")
    test_cmd = repo_cfg.get("test_cmd")

    if state.phase == "gen_ready":
        rendered_path = render_generator_prompt(
            harness_dir=str(harness_dir),
            round_num=state.round,
            scope=scope if scope != "(제한 없음)" else None,
            max_files=state.max_files,
            test_available=test_available,
        )
        print(f"[next] Advanced to Generator phase (round {state.round}/{state.max_rounds})")
        print(f"  Generator prompt: {rendered_path}")
        print()
        print("Next steps:")
        print("  1. Open a new Claude Code session in the repo directory")
        print(f"  2. Feed the generator prompt: {rendered_path}")
        print("  3. Claude will write changes.md to .harness/")
        print(f"  4. Run `harness next --repo-path {base_path}` to advance to QA")

    elif state.phase == "eval_ready":
        rendered_path = render_evaluator_prompt(
            harness_dir=str(harness_dir),
            round_num=state.round,
            scope=scope if scope != "(제한 없음)" else None,
            test_available=test_available,
            build_cmd=build_cmd,
            test_cmd=test_cmd,
        )
        print(f"[next] Advanced to Evaluator phase (round {state.round}/{state.max_rounds})")
        print(f"  Evaluator prompt: {rendered_path}")
        print()
        print("Next steps:")
        print("  1. Open a new Claude Code session in the repo directory")
        print(f"  2. Feed the evaluator prompt: {rendered_path}")
        print("  3. Claude will write qa_report.md to .harness/")
        print(f"  4. Run `harness next --repo-path {base_path}` to finalize")

    elif state.phase == "completed":
        # Parse verdict from qa_report.md
        verdict = state._parse_qa_verdict()
        print(f"[next] Task completed!")
        if verdict == "PASS":
            print("  Result: PASS - All QA checks passed.")
        else:
            print(f"  Result: FAIL - Reached max rounds ({state.max_rounds}) without passing QA.")
        print(f"  Branch : {state.branch}")
        print(f"  Task   : {state.task}")


def cmd_status(args):
    """Show current harness status."""
    from state import HarnessState

    # 1. Load state from .harness/
    base_path = Path(args.repo_path) if args.repo_path else Path.cwd()
    harness_dir = base_path / ".harness"
    if not harness_dir.exists():
        print(f"[status] Error: .harness/ not found in {base_path}", file=sys.stderr)
        sys.exit(1)

    try:
        state = HarnessState.load(harness_dir)
    except FileNotFoundError as e:
        print(f"[status] Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Phase labels
    phase_labels = {
        "plan_ready": "Phase 1 (Planner) \u2014 spec.md \uc791\uc131 \ub300\uae30",
        "gen_ready": "Phase 2 (Generator) \u2014 \uad6c\ud604 \ub300\uae30",
        "eval_ready": "Phase 3 (Evaluator) \u2014 QA \uac80\uc99d \ub300\uae30",
        "completed": "\uc644\ub8cc",
    }
    phase_label = phase_labels.get(state.phase, state.phase)

    # 2. Print status
    print(f"[status]")
    print(f"  Task   : {state.task}")
    print(f"  Repo   : {state.repo_name}  ({state.repo_path})")
    print(f"  Phase  : {phase_label}")
    print(f"  Round  : {state.round} / {state.max_rounds}")
    print(f"  Scope  : {state.scope}")
    print(f"  Branch : {state.branch}")


def main():
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Agent Harness - 3-Phase development workflow for Claude Code"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize harness config directory")

    # repo
    repo_parser = subparsers.add_parser("repo", help="Manage repositories")
    repo_sub = repo_parser.add_subparsers(dest="repo_action", required=True)

    repo_add = repo_sub.add_parser("add", help="Register a repository")
    repo_add.add_argument("--name", required=True, help="Repository name")
    repo_add.add_argument("--path", required=True, help="Absolute path to repository")
    repo_add.add_argument("--lang", required=True, help="Primary language (python, java, csharp, typescript, etc.)")
    repo_add.add_argument("--test-cmd", default=None, help="Test command (e.g., 'pytest', './gradlew test')")
    repo_add.add_argument("--build-cmd", default=None, help="Build command (e.g., './gradlew build')")
    repo_add.add_argument("--default-scope", default=None, help="Default file scope pattern")

    repo_sub.add_parser("list", help="List registered repositories")

    repo_update = repo_sub.add_parser("update", help="Update a repository")
    repo_update.add_argument("name", help="Repository name")
    repo_update.add_argument("--path", default=None)
    repo_update.add_argument("--lang", default=None)
    repo_update.add_argument("--test-cmd", default=None)
    repo_update.add_argument("--build-cmd", default=None)
    repo_update.add_argument("--default-scope", default=None)

    repo_rm = repo_sub.add_parser("remove", help="Remove a repository")
    repo_rm.add_argument("name", help="Repository name")

    # run
    run_parser = subparsers.add_parser("run", help="Start a new task")
    run_group = run_parser.add_mutually_exclusive_group(required=True)
    run_group.add_argument("--repo", help="Registered repository name")
    run_group.add_argument("--repo-path", help="Direct path to repository")
    run_parser.add_argument("--task", required=True, help="Task description")
    run_parser.add_argument("--lang", default=None, help="Language (required with --repo-path)")
    run_parser.add_argument("--scope", default=None, help="File scope pattern")
    run_parser.add_argument("--max-rounds", type=int, default=3, help="Max build/QA rounds (default: 3)")
    run_parser.add_argument("--max-files", type=int, default=20, help="Max files to modify (default: 20)")
    run_parser.add_argument("--dry-run", action="store_true", help="Planner only, no code changes")

    # next
    next_parser = subparsers.add_parser("next", help="Advance to next phase")
    next_parser.add_argument("--repo-path", default=None, help="Path to repo with active .harness/")

    # status
    status_parser = subparsers.add_parser("status", help="Show current task status")
    status_parser.add_argument("--repo-path", default=None, help="Path to repo with active .harness/")

    args = parser.parse_args()
    commands = {
        "init": cmd_init,
        "repo": cmd_repo,
        "run": cmd_run,
        "next": cmd_next,
        "status": cmd_status,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
