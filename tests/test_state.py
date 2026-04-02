"""Tests for HarnessState - state machine for harness workflow phases."""
import json
import os
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(tmp_path, **overrides):
    """Create a HarnessState in tmp_path with sensible defaults."""
    from state import HarnessState

    defaults = dict(
        harness_dir=tmp_path / ".harness",
        task="Add feature X",
        repo_name="my-repo",
        repo_path=str(tmp_path / "repo"),
        scope="src/**/*.py",
        max_rounds=3,
        max_files=20,
        branch="feature/x",
    )
    defaults.update(overrides)
    return HarnessState.create(**defaults)


# ---------------------------------------------------------------------------
# create() / load() / save()
# ---------------------------------------------------------------------------

class TestCreateAndLoad:
    def test_create_returns_harness_state(self, tmp_path):
        from state import HarnessState
        state = make_state(tmp_path)
        assert isinstance(state, HarnessState)

    def test_initial_phase_is_plan_ready(self, tmp_path):
        state = make_state(tmp_path)
        assert state.phase == "plan_ready"

    def test_initial_round_is_1(self, tmp_path):
        state = make_state(tmp_path)
        assert state.round == 1

    def test_create_writes_state_json(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        make_state(tmp_path, harness_dir=harness_dir)
        assert (harness_dir / "state.json").exists()

    def test_state_json_contains_expected_fields(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        make_state(tmp_path, harness_dir=harness_dir)
        data = json.loads((harness_dir / "state.json").read_text())
        for field in ("task", "repo_name", "repo_path", "phase", "round",
                      "scope", "max_rounds", "max_files", "branch", "created_at"):
            assert field in data, f"Missing field: {field}"

    def test_load_round_trips_state(self, tmp_path):
        from state import HarnessState
        harness_dir = tmp_path / ".harness"
        original = make_state(tmp_path, harness_dir=harness_dir, task="Round trip task")
        loaded = HarnessState.load(harness_dir)
        assert loaded.task == original.task
        assert loaded.phase == original.phase
        assert loaded.round == original.round
        assert loaded.repo_name == original.repo_name
        assert loaded.repo_path == original.repo_path
        assert loaded.scope == original.scope
        assert loaded.max_rounds == original.max_rounds
        assert loaded.max_files == original.max_files
        assert loaded.branch == original.branch

    def test_load_missing_file_raises(self, tmp_path):
        from state import HarnessState
        with pytest.raises(FileNotFoundError):
            HarnessState.load(tmp_path / ".harness_nonexistent")

    def test_save_persists_changes(self, tmp_path):
        from state import HarnessState
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        state.phase = "gen_ready"
        state.round = 2
        state.save()
        loaded = HarnessState.load(harness_dir)
        assert loaded.phase == "gen_ready"
        assert loaded.round == 2

    def test_created_at_is_iso_format(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        make_state(tmp_path, harness_dir=harness_dir)
        data = json.loads((harness_dir / "state.json").read_text())
        # ISO format: must contain T and be parseable
        from datetime import datetime
        dt = datetime.fromisoformat(data["created_at"])
        assert dt is not None

    def test_harness_dir_created_if_missing(self, tmp_path):
        harness_dir = tmp_path / "nested" / ".harness"
        make_state(tmp_path, harness_dir=harness_dir)
        assert harness_dir.exists()


# ---------------------------------------------------------------------------
# advance() — plan_ready -> gen_ready
# ---------------------------------------------------------------------------

class TestAdvancePlanReadyToGenReady:
    def test_advance_creates_gen_ready_when_spec_exists(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        (harness_dir / "spec.md").write_text("# Spec")
        state.advance()
        assert state.phase == "gen_ready"

    def test_advance_saves_new_phase(self, tmp_path):
        from state import HarnessState
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        (harness_dir / "spec.md").write_text("# Spec")
        state.advance()
        loaded = HarnessState.load(harness_dir)
        assert loaded.phase == "gen_ready"

    def test_advance_raises_if_spec_missing(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        # No spec.md created
        with pytest.raises(FileNotFoundError):
            state.advance()

    def test_advance_round_unchanged(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        (harness_dir / "spec.md").write_text("# Spec")
        state.advance()
        assert state.round == 1


# ---------------------------------------------------------------------------
# advance() — gen_ready -> eval_ready
# ---------------------------------------------------------------------------

class TestAdvanceGenReadyToEvalReady:
    def _make_gen_ready(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        (harness_dir / "spec.md").write_text("# Spec")
        state.advance()  # plan_ready -> gen_ready
        return state, harness_dir

    def test_advance_to_eval_ready_when_changes_exists(self, tmp_path):
        state, harness_dir = self._make_gen_ready(tmp_path)
        (harness_dir / "changes.md").write_text("# Changes")
        state.advance()
        assert state.phase == "eval_ready"

    def test_advance_raises_if_changes_missing(self, tmp_path):
        state, harness_dir = self._make_gen_ready(tmp_path)
        with pytest.raises(FileNotFoundError):
            state.advance()

    def test_advance_saves_eval_ready(self, tmp_path):
        from state import HarnessState
        state, harness_dir = self._make_gen_ready(tmp_path)
        (harness_dir / "changes.md").write_text("# Changes")
        state.advance()
        loaded = HarnessState.load(harness_dir)
        assert loaded.phase == "eval_ready"

    def test_advance_round_still_1(self, tmp_path):
        state, harness_dir = self._make_gen_ready(tmp_path)
        (harness_dir / "changes.md").write_text("# Changes")
        state.advance()
        assert state.round == 1


# ---------------------------------------------------------------------------
# advance() — eval_ready -> PASS verdict -> completed
# ---------------------------------------------------------------------------

class TestAdvanceEvalReadyPass:
    def _make_eval_ready(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        (harness_dir / "spec.md").write_text("# Spec")
        state.advance()  # plan_ready -> gen_ready
        (harness_dir / "changes.md").write_text("# Changes")
        state.advance()  # gen_ready -> eval_ready
        return state, harness_dir

    def test_pass_verdict_goes_to_completed(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path)
        (harness_dir / "qa_report.md").write_text("종합 판정: PASS\n", encoding="utf-8")
        state.advance()
        assert state.phase == "completed"

    def test_pass_verdict_english_fallback(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path)
        (harness_dir / "qa_report.md").write_text("Verdict: PASS\n", encoding="utf-8")
        state.advance()
        assert state.phase == "completed"

    def test_pass_verdict_saves_completed(self, tmp_path):
        from state import HarnessState
        state, harness_dir = self._make_eval_ready(tmp_path)
        (harness_dir / "qa_report.md").write_text("종합 판정: PASS\n", encoding="utf-8")
        state.advance()
        loaded = HarnessState.load(harness_dir)
        assert loaded.phase == "completed"

    def test_pass_does_not_increment_round(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path)
        (harness_dir / "qa_report.md").write_text("종합 판정: PASS\n", encoding="utf-8")
        state.advance()
        assert state.round == 1

    def test_advance_raises_if_qa_report_missing(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path)
        with pytest.raises(FileNotFoundError):
            state.advance()


# ---------------------------------------------------------------------------
# advance() — eval_ready -> FAIL verdict
# ---------------------------------------------------------------------------

class TestAdvanceEvalReadyFail:
    def _make_eval_ready(self, tmp_path, max_rounds=3):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir, max_rounds=max_rounds)
        (harness_dir / "spec.md").write_text("# Spec")
        state.advance()
        (harness_dir / "changes.md").write_text("# Changes")
        state.advance()
        return state, harness_dir

    def test_fail_below_max_rounds_goes_to_gen_ready(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=3)
        assert state.round == 1
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.phase == "gen_ready"

    def test_fail_increments_round(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=3)
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.round == 2

    def test_fail_at_max_rounds_goes_to_completed(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=1)
        assert state.round == 1
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.phase == "completed"

    def test_fail_at_max_rounds_does_not_increment_round(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=1)
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.round == 1

    def test_fail_english_fallback(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=3)
        (harness_dir / "qa_report.md").write_text("Verdict: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.phase == "gen_ready"
        assert state.round == 2

    def test_unparseable_verdict_defaults_to_fail(self, tmp_path):
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=3)
        (harness_dir / "qa_report.md").write_text("No verdict here.\n", encoding="utf-8")
        state.advance()
        assert state.phase == "gen_ready"
        assert state.round == 2

    def test_fail_saves_updated_state(self, tmp_path):
        from state import HarnessState
        state, harness_dir = self._make_eval_ready(tmp_path, max_rounds=3)
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        loaded = HarnessState.load(harness_dir)
        assert loaded.phase == "gen_ready"
        assert loaded.round == 2

    def test_multiple_fail_cycles(self, tmp_path):
        """Round 1 FAIL -> gen_ready(round=2) -> eval_ready -> FAIL -> gen_ready(round=3)."""
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir, max_rounds=3)
        (harness_dir / "spec.md").write_text("# Spec", encoding="utf-8")
        state.advance()  # -> gen_ready

        # Round 1
        (harness_dir / "changes.md").write_text("# Changes r1", encoding="utf-8")
        state.advance()  # -> eval_ready
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()  # -> gen_ready round=2
        assert state.phase == "gen_ready"
        assert state.round == 2

        # Round 2
        (harness_dir / "changes.md").write_text("# Changes r2", encoding="utf-8")
        state.advance()  # -> eval_ready
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()  # -> gen_ready round=3
        assert state.phase == "gen_ready"
        assert state.round == 3

    def test_fail_at_round_equals_max_goes_to_completed(self, tmp_path):
        """When round == max_rounds, FAIL should lead to completed."""
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir, max_rounds=2)
        (harness_dir / "spec.md").write_text("# Spec", encoding="utf-8")
        state.advance()

        # Round 1 FAIL -> gen_ready round=2
        (harness_dir / "changes.md").write_text("# Changes r1", encoding="utf-8")
        state.advance()
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.round == 2
        assert state.phase == "gen_ready"

        # Round 2 FAIL -> completed (round >= max_rounds)
        (harness_dir / "changes.md").write_text("# Changes r2", encoding="utf-8")
        state.advance()
        (harness_dir / "qa_report.md").write_text("종합 판정: FAIL\n", encoding="utf-8")
        state.advance()
        assert state.phase == "completed"


# ---------------------------------------------------------------------------
# advance() — completed phase (terminal, no further advance)
# ---------------------------------------------------------------------------

class TestAdvanceCompleted:
    def test_completed_phase_is_terminal(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        state.phase = "completed"
        state.save()
        # Should raise or at least not silently transition elsewhere
        with pytest.raises((ValueError, RuntimeError)):
            state.advance()


# ---------------------------------------------------------------------------
# _parse_qa_verdict()
# ---------------------------------------------------------------------------

class TestParseQaVerdict:
    def _make_eval_ready_state(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        state = make_state(tmp_path, harness_dir=harness_dir)
        state.phase = "eval_ready"
        state.save()
        return state, harness_dir

    def test_korean_pass(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("# Report\n종합 판정: PASS\n", encoding="utf-8")
        assert state._parse_qa_verdict() == "PASS"

    def test_korean_fail(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("# Report\n종합 판정: FAIL\n", encoding="utf-8")
        assert state._parse_qa_verdict() == "FAIL"

    def test_english_pass(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("Verdict: PASS\n", encoding="utf-8")
        assert state._parse_qa_verdict() == "PASS"

    def test_english_fail(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("Verdict: FAIL\n", encoding="utf-8")
        assert state._parse_qa_verdict() == "FAIL"

    def test_verdict_in_middle_of_text(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        content = "Some text before\n종합 판정: PASS\nSome text after\n"
        (harness_dir / "qa_report.md").write_text(content, encoding="utf-8")
        assert state._parse_qa_verdict() == "PASS"

    def test_case_insensitive_pass(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("종합 판정: pass\n", encoding="utf-8")
        assert state._parse_qa_verdict() == "PASS"

    def test_no_verdict_defaults_to_fail(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("No verdict here.\n", encoding="utf-8")
        assert state._parse_qa_verdict() == "FAIL"

    def test_empty_file_defaults_to_fail(self, tmp_path):
        state, harness_dir = self._make_eval_ready_state(tmp_path)
        (harness_dir / "qa_report.md").write_text("", encoding="utf-8")
        assert state._parse_qa_verdict() == "FAIL"
