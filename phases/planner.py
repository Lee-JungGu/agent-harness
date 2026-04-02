"""Planner phase: renders the planner prompt template."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from renderer import render_template, get_template_path


def render_planner_prompt(harness_dir: str, task: str, repo_path: str, lang: str, scope) -> str:
    """Render the planner prompt template and write it to harness_dir.

    Args:
        harness_dir: Directory where the rendered file will be written.
        task: Task description string.
        repo_path: Path to the target repository.
        lang: Programming language of the repository.
        scope: File/directory scope string, or None for no restriction.

    Returns:
        Absolute path to the written rendered file.
    """
    variables = {
        "task_description": task,
        "repo_path": repo_path,
        "lang": lang,
        "scope": scope if scope is not None else "(제한 없음)",
    }

    template_path = get_template_path("planner_prompt.md")
    rendered = render_template(template_path, variables)

    output_path = Path(harness_dir) / "planner_prompt_rendered.md"
    output_path.write_text(rendered, encoding="utf-8")

    return str(output_path)
