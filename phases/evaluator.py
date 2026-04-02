"""Evaluator phase: renders the evaluator prompt template."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from renderer import render_template, get_template_path


def render_evaluator_prompt(
    harness_dir: str,
    round_num: int,
    scope,
    test_available: bool,
    build_cmd,
    test_cmd,
) -> str:
    """Render the evaluator prompt template and write it to harness_dir.

    Args:
        harness_dir: Directory that contains spec.md and changes.md,
                     and where the rendered file will be written.
        round_num: Current round number (1-based).
        scope: File/directory scope string, or None for no restriction.
        test_available: Whether automated tests are available for this repo.
        build_cmd: Shell command to build the project, or None.
        test_cmd: Shell command to run tests, or None.

    Returns:
        Absolute path to the written rendered file.
    """
    harness = Path(harness_dir)

    spec_content = (harness / "spec.md").read_text(encoding="utf-8")
    changes_content = (harness / "changes.md").read_text(encoding="utf-8")

    variables = {
        "round_num": round_num,
        "spec_content": spec_content,
        "changes_content": changes_content,
        "test_available": str(test_available),
        "build_cmd": build_cmd if build_cmd is not None else "(없음)",
        "test_cmd": test_cmd if test_cmd is not None else "(없음)",
        "scope": scope if scope is not None else "(제한 없음)",
    }

    template_path = get_template_path("evaluator_prompt.md")
    rendered = render_template(template_path, variables)

    output_path = harness / "evaluator_prompt_rendered.md"
    output_path.write_text(rendered, encoding="utf-8")

    return str(output_path)
