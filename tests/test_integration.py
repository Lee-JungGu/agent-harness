"""Integration tests: end-to-end harness workflow (programmatic, no subprocess)."""

import os
import sys
import subprocess
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixture: workspace — fake repo + HarnessConfig
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    """Create a fake git repo and a HarnessConfig pointing at a temp config dir."""
    # ---- fake repo ----
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("# main\n", encoding="utf-8")

    # git init + initial commit with explicit identity env vars
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True, env=env)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(repo_dir),
        check=True,
        capture_output=True,
        env=env,
    )

    # ---- HarnessConfig ----
    from config import HarnessConfig

    config_dir = tmp_path / "config"
    cfg = HarnessConfig(config_dir=config_dir)
    cfg.init()
    cfg.add_repo(
        name="test-repo",
        path=str(repo_dir),
        lang="python",
        test_cmd=None,
        build_cmd=None,
        default_scope="src/**/*.py",
    )

    return {
        "repo_dir": repo_dir,
        "config": cfg,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# Helper: create a standard HarnessState
# ---------------------------------------------------------------------------

def _make_state(harness_dir: Path, repo_dir: Path):
    from state import HarnessState

    return HarnessState.create(
        harness_dir=harness_dir,
        task="Add feature X",
        repo_name="test-repo",
        repo_path=str(repo_dir),
        scope="src/**/*.py",
        max_rounds=3,
        max_files=20,
        branch="feature/x",
    )


# ---------------------------------------------------------------------------
# Test 1: test_run_creates_planner_prompt
# ---------------------------------------------------------------------------

class TestRunCreatesPlannerPrompt:
    def test_run_creates_planner_prompt(self, workspace):
        """Render planner prompt, create state → state.phase == 'plan_ready' and
        planner_prompt_rendered.md exists."""
        from phases.planner import render_planner_prompt

        repo_dir: Path = workspace["repo_dir"]
        tmp_path: Path = workspace["tmp_path"]

        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir(parents=True, exist_ok=True)

        # Render planner prompt
        rendered_path = render_planner_prompt(
            harness_dir=str(harness_dir),
            task="Add feature X",
            repo_path=str(repo_dir),
            lang="python",
            scope="src/**/*.py",
        )

        # Create state
        state = _make_state(harness_dir, repo_dir)

        # Assertions
        assert state.phase == "plan_ready"
        assert Path(rendered_path).exists()
        assert (harness_dir / "planner_prompt_rendered.md").exists()


# ---------------------------------------------------------------------------
# Test 2: test_full_pass_workflow
# ---------------------------------------------------------------------------

class TestFullPassWorkflow:
    def test_full_pass_workflow(self, workspace):
        """End-to-end PASS workflow: plan_ready → gen_ready → eval_ready → completed."""
        from phases.planner import render_planner_prompt
        from phases.generator import render_generator_prompt
        from phases.evaluator import render_evaluator_prompt

        repo_dir: Path = workspace["repo_dir"]
        tmp_path: Path = workspace["tmp_path"]

        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir(parents=True, exist_ok=True)

        # Render planner prompt
        render_planner_prompt(
            harness_dir=str(harness_dir),
            task="Add feature X",
            repo_path=str(repo_dir),
            lang="python",
            scope="src/**/*.py",
        )

        # Create state at plan_ready
        state = _make_state(harness_dir, repo_dir)
        assert state.phase == "plan_ready"

        # --- Phase 1: Planner → Generator ---
        (harness_dir / "spec.md").write_text("# Spec\nAdd feature X.", encoding="utf-8")
        state.advance()
        assert state.phase == "gen_ready"

        # Render generator prompt
        gen_path = render_generator_prompt(
            harness_dir=str(harness_dir),
            round_num=state.round,
            scope=state.scope,
            max_files=state.max_files,
            test_available=False,
        )
        assert Path(gen_path).exists()
        assert (harness_dir / "generator_prompt_rendered.md").exists()

        # --- Phase 2: Generator → Evaluator ---
        (harness_dir / "changes.md").write_text("# Changes\n- implemented feature X", encoding="utf-8")
        state.advance()
        assert state.phase == "eval_ready"

        # Render evaluator prompt
        eval_path = render_evaluator_prompt(
            harness_dir=str(harness_dir),
            round_num=state.round,
            scope=state.scope,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        assert Path(eval_path).exists()
        assert (harness_dir / "evaluator_prompt_rendered.md").exists()

        # --- Phase 3: Evaluator PASS → completed ---
        (harness_dir / "qa_report.md").write_text(
            "## 종합 판정: PASS\n모든 항목이 기준을 충족합니다.\n", encoding="utf-8"
        )
        state.advance()
        assert state.phase == "completed"


# ---------------------------------------------------------------------------
# Test 3: test_fail_retry_workflow
# ---------------------------------------------------------------------------

class TestFailRetryWorkflow:
    def test_fail_retry_workflow(self, workspace):
        """FAIL on round 1 → retry → gen_ready round 2 → PASS → completed."""
        from phases.generator import render_generator_prompt
        from phases.evaluator import render_evaluator_prompt

        repo_dir: Path = workspace["repo_dir"]
        tmp_path: Path = workspace["tmp_path"]

        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir(parents=True, exist_ok=True)

        # Create state
        state = _make_state(harness_dir, repo_dir)

        # plan_ready → gen_ready
        (harness_dir / "spec.md").write_text("# Spec\nFix bug Y.", encoding="utf-8")
        state.advance()
        assert state.phase == "gen_ready"
        assert state.round == 1

        # gen_ready → eval_ready (round 1)
        (harness_dir / "changes.md").write_text("# Changes r1\n- attempted fix", encoding="utf-8")
        state.advance()
        assert state.phase == "eval_ready"

        # eval_ready → FAIL → gen_ready (round 2)
        (harness_dir / "qa_report.md").write_text(
            "## 종합 판정: FAIL\n### 수정 필요\n- Fix X\n", encoding="utf-8"
        )
        state.advance()
        assert state.phase == "gen_ready"
        assert state.round == 2

        # Round 2: render generator prompt (should include QA feedback)
        gen_path = render_generator_prompt(
            harness_dir=str(harness_dir),
            round_num=state.round,
            scope=state.scope,
            max_files=state.max_files,
            test_available=False,
        )
        assert Path(gen_path).exists()
        gen_content = (harness_dir / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        # Round 2 prompt should contain the previous QA feedback
        assert "Fix X" in gen_content

        # gen_ready → eval_ready (round 2)
        (harness_dir / "changes.md").write_text("# Changes r2\n- proper fix", encoding="utf-8")
        state.advance()
        assert state.phase == "eval_ready"

        # Render evaluator prompt for round 2
        eval_path = render_evaluator_prompt(
            harness_dir=str(harness_dir),
            round_num=state.round,
            scope=state.scope,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        assert Path(eval_path).exists()

        # eval_ready → PASS → completed (round 2)
        (harness_dir / "qa_report.md").write_text(
            "## 종합 판정: PASS\n수정이 완료되었습니다.\n", encoding="utf-8"
        )
        state.advance()
        assert state.phase == "completed"
        assert state.round == 2
