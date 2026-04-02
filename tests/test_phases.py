"""Tests for phases/planner.py, phases/generator.py, phases/evaluator.py."""

import sys
import pytest
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_planner():
    from phases.planner import render_planner_prompt
    return render_planner_prompt


def get_generator():
    from phases.generator import render_generator_prompt
    return render_generator_prompt


def get_evaluator():
    from phases.evaluator import render_evaluator_prompt
    return render_evaluator_prompt


# ---------------------------------------------------------------------------
# Planner tests
# ---------------------------------------------------------------------------

class TestRenderPlannerPrompt:
    def test_creates_rendered_file(self, tmp_path):
        """render_planner_prompt writes the rendered file to harness_dir."""
        render_planner_prompt = get_planner()
        result_path = render_planner_prompt(
            harness_dir=str(tmp_path),
            task="Fix the login bug",
            repo_path="/repo/myapp",
            lang="python",
            scope="src/auth/",
        )
        assert Path(result_path).exists()

    def test_returns_correct_output_path(self, tmp_path):
        """Return value is {harness_dir}/planner_prompt_rendered.md."""
        render_planner_prompt = get_planner()
        result_path = render_planner_prompt(
            harness_dir=str(tmp_path),
            task="Add feature X",
            repo_path="/repo",
            lang="typescript",
            scope=None,
        )
        expected = str(tmp_path / "planner_prompt_rendered.md")
        # Normalise separators for cross-platform comparison
        assert result_path.replace("\\", "/") == expected.replace("\\", "/")

    def test_rendered_content_contains_task(self, tmp_path):
        """Rendered file contains the task description."""
        render_planner_prompt = get_planner()
        render_planner_prompt(
            harness_dir=str(tmp_path),
            task="Implement OAuth2 integration",
            repo_path="/repo",
            lang="python",
            scope="src/",
        )
        content = (tmp_path / "planner_prompt_rendered.md").read_text(encoding="utf-8")
        assert "Implement OAuth2 integration" in content

    def test_rendered_content_contains_repo_and_lang(self, tmp_path):
        """Rendered file contains repo_path and lang."""
        render_planner_prompt = get_planner()
        render_planner_prompt(
            harness_dir=str(tmp_path),
            task="Some task",
            repo_path="/workspace/awesome-repo",
            lang="java",
            scope="src/main/",
        )
        content = (tmp_path / "planner_prompt_rendered.md").read_text(encoding="utf-8")
        assert "/workspace/awesome-repo" in content
        assert "java" in content

    def test_rendered_content_contains_scope(self, tmp_path):
        """Rendered file contains the scope when provided."""
        render_planner_prompt = get_planner()
        render_planner_prompt(
            harness_dir=str(tmp_path),
            task="Task",
            repo_path="/repo",
            lang="go",
            scope="pkg/api/",
        )
        content = (tmp_path / "planner_prompt_rendered.md").read_text(encoding="utf-8")
        assert "pkg/api/" in content

    def test_none_scope_uses_default(self, tmp_path):
        """When scope is None the rendered file contains '(제한 없음)'."""
        render_planner_prompt = get_planner()
        render_planner_prompt(
            harness_dir=str(tmp_path),
            task="Task",
            repo_path="/repo",
            lang="rust",
            scope=None,
        )
        content = (tmp_path / "planner_prompt_rendered.md").read_text(encoding="utf-8")
        assert "(제한 없음)" in content

    def test_no_unresolved_placeholders(self, tmp_path):
        """All known placeholders are resolved — none left as {variable}."""
        render_planner_prompt = get_planner()
        render_planner_prompt(
            harness_dir=str(tmp_path),
            task="My task",
            repo_path="/repo",
            lang="python",
            scope="src/",
        )
        content = (tmp_path / "planner_prompt_rendered.md").read_text(encoding="utf-8")
        for placeholder in ["{task_description}", "{repo_path}", "{lang}", "{scope}"]:
            assert placeholder not in content, f"Unresolved placeholder: {placeholder}"


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

class TestRenderGeneratorPrompt:
    def _write_spec(self, harness_dir: Path, text: str = "# Spec\nDo the thing."):
        (harness_dir / "spec.md").write_text(text, encoding="utf-8")

    def test_creates_rendered_file(self, tmp_path):
        """render_generator_prompt writes the rendered file to harness_dir."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        result_path = render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope="src/",
            max_files=10,
            test_available=True,
        )
        assert Path(result_path).exists()

    def test_returns_correct_output_path(self, tmp_path):
        """Return value is {harness_dir}/generator_prompt_rendered.md."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        result_path = render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            max_files=5,
            test_available=False,
        )
        expected = str(tmp_path / "generator_prompt_rendered.md")
        assert result_path.replace("\\", "/") == expected.replace("\\", "/")

    def test_round1_no_feedback(self, tmp_path):
        """Round 1 without qa_report.md uses the default 'first round' message."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            max_files=10,
            test_available=False,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "(첫 라운드 — QA 피드백 없음)" in content

    def test_round2_reads_qa_report(self, tmp_path):
        """Round 2+ reads qa_report.md and includes it in the rendered prompt."""
        self._write_spec(tmp_path)
        qa_content = "## QA Report\nFix the login bug."
        (tmp_path / "qa_report.md").write_text(qa_content, encoding="utf-8")
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=2,
            scope=None,
            max_files=10,
            test_available=False,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "Fix the login bug." in content

    def test_round2_missing_qa_report_uses_default(self, tmp_path):
        """Round 2 without qa_report.md falls back to default message."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=2,
            scope=None,
            max_files=10,
            test_available=False,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "(첫 라운드 — QA 피드백 없음)" in content

    def test_test_available_true_includes_tdd(self, tmp_path):
        """When test_available=True the rendered prompt mentions TDD skill."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            max_files=10,
            test_available=True,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "test-driven-development" in content

    def test_test_available_false_no_tdd(self, tmp_path):
        """When test_available=False the rendered prompt does NOT mention TDD skill."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            max_files=10,
            test_available=False,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "test-driven-development" not in content

    def test_rendered_content_contains_spec(self, tmp_path):
        """Rendered file contains the spec content."""
        spec_text = "# My Spec\nDo something important."
        self._write_spec(tmp_path, spec_text)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            max_files=10,
            test_available=False,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "Do something important." in content

    def test_rendered_content_contains_round_num(self, tmp_path):
        """Rendered file contains the round number."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=3,
            scope=None,
            max_files=10,
            test_available=False,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "3" in content

    def test_no_unresolved_placeholders(self, tmp_path):
        """All known placeholders are resolved."""
        self._write_spec(tmp_path)
        render_generator_prompt = get_generator()
        render_generator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope="src/",
            max_files=5,
            test_available=True,
        )
        content = (tmp_path / "generator_prompt_rendered.md").read_text(encoding="utf-8")
        for placeholder in [
            "{round_num}", "{spec_content}", "{qa_feedback}",
            "{scope}", "{max_files}", "{skill_instructions}",
        ]:
            assert placeholder not in content, f"Unresolved placeholder: {placeholder}"


# ---------------------------------------------------------------------------
# Evaluator tests
# ---------------------------------------------------------------------------

class TestRenderEvaluatorPrompt:
    def _write_files(self, harness_dir: Path, spec: str = "# Spec", changes: str = "## Changes"):
        (harness_dir / "spec.md").write_text(spec, encoding="utf-8")
        (harness_dir / "changes.md").write_text(changes, encoding="utf-8")

    def test_creates_rendered_file(self, tmp_path):
        """render_evaluator_prompt writes the rendered file to harness_dir."""
        self._write_files(tmp_path)
        render_evaluator_prompt = get_evaluator()
        result_path = render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope="src/",
            test_available=True,
            build_cmd="make build",
            test_cmd="pytest",
        )
        assert Path(result_path).exists()

    def test_returns_correct_output_path(self, tmp_path):
        """Return value is {harness_dir}/evaluator_prompt_rendered.md."""
        self._write_files(tmp_path)
        render_evaluator_prompt = get_evaluator()
        result_path = render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        expected = str(tmp_path / "evaluator_prompt_rendered.md")
        assert result_path.replace("\\", "/") == expected.replace("\\", "/")

    def test_rendered_content_contains_spec(self, tmp_path):
        """Rendered file contains the spec content."""
        self._write_files(tmp_path, spec="# Critical Spec\nMust do this.")
        render_evaluator_prompt = get_evaluator()
        render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        content = (tmp_path / "evaluator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "Must do this." in content

    def test_rendered_content_contains_changes(self, tmp_path):
        """Rendered file contains the changes content."""
        self._write_files(tmp_path, changes="## Round 1 Changes\n- added auth.py")
        render_evaluator_prompt = get_evaluator()
        render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        content = (tmp_path / "evaluator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "added auth.py" in content

    def test_with_tests_available(self, tmp_path):
        """When test_available=True rendered file contains 'true' and commands."""
        self._write_files(tmp_path)
        render_evaluator_prompt = get_evaluator()
        render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            test_available=True,
            build_cmd="make build",
            test_cmd="pytest -v",
        )
        content = (tmp_path / "evaluator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "True" in content
        assert "make build" in content
        assert "pytest -v" in content

    def test_without_tests_uses_default_cmds(self, tmp_path):
        """When build_cmd/test_cmd are None the rendered file contains '(없음)'."""
        self._write_files(tmp_path)
        render_evaluator_prompt = get_evaluator()
        render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        content = (tmp_path / "evaluator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "(없음)" in content

    def test_none_scope_uses_default(self, tmp_path):
        """When scope is None the rendered file contains '(제한 없음)'."""
        self._write_files(tmp_path)
        render_evaluator_prompt = get_evaluator()
        render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=1,
            scope=None,
            test_available=False,
            build_cmd=None,
            test_cmd=None,
        )
        content = (tmp_path / "evaluator_prompt_rendered.md").read_text(encoding="utf-8")
        assert "(제한 없음)" in content

    def test_no_unresolved_placeholders(self, tmp_path):
        """All known placeholders are resolved."""
        self._write_files(tmp_path)
        render_evaluator_prompt = get_evaluator()
        render_evaluator_prompt(
            harness_dir=str(tmp_path),
            round_num=2,
            scope="src/",
            test_available=True,
            build_cmd="make",
            test_cmd="pytest",
        )
        content = (tmp_path / "evaluator_prompt_rendered.md").read_text(encoding="utf-8")
        for placeholder in [
            "{round_num}", "{spec_content}", "{changes_content}",
            "{test_available}", "{build_cmd}", "{test_cmd}", "{scope}",
        ]:
            assert placeholder not in content, f"Unresolved placeholder: {placeholder}"
