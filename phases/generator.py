"""Generator phase: renders the generator prompt template."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from renderer import render_template, get_template_path

_TDD_SKILL = "superpowers:test-driven-development"
_SUBAGENT_SKILL = "superpowers:subagent-driven-development"

_SKILL_WITH_TDD = (
    f"- `{_TDD_SKILL}` — write tests before (or alongside) implementation code\n"
    f"- `{_SUBAGENT_SKILL}` — break the work into independent sub-tasks"
)

_SKILL_WITHOUT_TDD = (
    f"- `{_SUBAGENT_SKILL}` — break the work into independent sub-tasks"
)

_TDD_INSTRUCTION = (
    f"3. **Use the `{_TDD_SKILL}` skill** — write or update tests before (or alongside) "
    f"implementation code so that correctness is verifiable."
)


def render_generator_prompt(
    harness_dir: str,
    round_num: int,
    scope,
    max_files: int,
    test_available: bool,
) -> str:
    """Render the generator prompt template and write it to harness_dir.

    Args:
        harness_dir: Directory that contains spec.md (and optionally qa_report.md)
                     and where the rendered file will be written.
        round_num: Current generation round number (1-based).
        scope: File/directory scope string, or None for no restriction.
        max_files: Maximum number of files the generator may modify/create.
        test_available: Whether automated tests are available for this repo.

    Returns:
        Absolute path to the written rendered file.
    """
    harness = Path(harness_dir)

    # Read spec.md
    spec_content = (harness / "spec.md").read_text(encoding="utf-8")

    # Read qa_report.md only for round 2+
    qa_feedback = "(첫 라운드 — QA 피드백 없음)"
    if round_num > 1:
        qa_report_path = harness / "qa_report.md"
        if qa_report_path.exists():
            qa_feedback = qa_report_path.read_text(encoding="utf-8")

    skill_instructions = _SKILL_WITH_TDD if test_available else _SKILL_WITHOUT_TDD
    tdd_instruction = _TDD_INSTRUCTION if test_available else ""

    variables = {
        "round_num": round_num,
        "spec_content": spec_content,
        "qa_feedback": qa_feedback,
        "scope": scope if scope is not None else "(제한 없음)",
        "max_files": max_files,
        "skill_instructions": skill_instructions,
        "tdd_instruction": tdd_instruction,
    }

    template_path = get_template_path("generator_prompt.md")
    rendered = render_template(template_path, variables)

    output_path = harness / "generator_prompt_rendered.md"
    output_path.write_text(rendered, encoding="utf-8")

    return str(output_path)
