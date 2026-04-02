"""HarnessState - state machine for harness workflow phases.

Phase transitions:
  plan_ready  --[spec.md exists]--> gen_ready
  gen_ready   --[changes.md exists]--> eval_ready
  eval_ready  --[qa_report.md, verdict=PASS]--> completed
  eval_ready  --[qa_report.md, verdict=FAIL, round < max_rounds]--> gen_ready (round++)
  eval_ready  --[qa_report.md, verdict=FAIL, round >= max_rounds]--> completed

State is persisted as JSON in <harness_dir>/state.json.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path


# Valid phases in order (completed is terminal)
_VALID_PHASES = {"plan_ready", "gen_ready", "eval_ready", "completed"}

# Required file for each phase to advance
_REQUIRED_FILES = {
    "plan_ready": "spec.md",
    "gen_ready": "changes.md",
    "eval_ready": "qa_report.md",
}


class HarnessState:
    """State machine tracking the current phase and round of a harness task."""

    def __init__(
        self,
        harness_dir: Path,
        task: str,
        repo_name: str,
        repo_path: str,
        phase: str,
        round: int,
        scope: str,
        max_rounds: int,
        max_files: int,
        branch: str,
        created_at: str,
    ):
        self.harness_dir = Path(harness_dir)
        self.task = task
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.phase = phase
        self.round = round
        self.scope = scope
        self.max_rounds = max_rounds
        self.max_files = max_files
        self.branch = branch
        self.created_at = created_at

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        harness_dir,
        task: str,
        repo_name: str,
        repo_path: str,
        scope: str,
        max_rounds: int,
        max_files: int,
        branch: str,
    ) -> "HarnessState":
        """Create a new HarnessState, write state.json, and return the instance."""
        harness_dir = Path(harness_dir)
        harness_dir.mkdir(parents=True, exist_ok=True)

        state = cls(
            harness_dir=harness_dir,
            task=task,
            repo_name=repo_name,
            repo_path=str(repo_path),
            phase="plan_ready",
            round=1,
            scope=scope,
            max_rounds=max_rounds,
            max_files=max_files,
            branch=branch,
            created_at=datetime.now().isoformat(),
        )
        state.save()
        return state

    @classmethod
    def load(cls, harness_dir) -> "HarnessState":
        """Load HarnessState from <harness_dir>/state.json."""
        harness_dir = Path(harness_dir)
        state_file = harness_dir / "state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"state.json not found in {harness_dir}")

        data = json.loads(state_file.read_text(encoding="utf-8"))
        return cls(
            harness_dir=harness_dir,
            task=data["task"],
            repo_name=data["repo_name"],
            repo_path=data["repo_path"],
            phase=data["phase"],
            round=data["round"],
            scope=data["scope"],
            max_rounds=data["max_rounds"],
            max_files=data["max_files"],
            branch=data["branch"],
            created_at=data["created_at"],
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist current state to <harness_dir>/state.json."""
        self.harness_dir.mkdir(parents=True, exist_ok=True)
        state_file = self.harness_dir / "state.json"
        data = {
            "task": self.task,
            "repo_name": self.repo_name,
            "repo_path": self.repo_path,
            "phase": self.phase,
            "round": self.round,
            "scope": self.scope,
            "max_rounds": self.max_rounds,
            "max_files": self.max_files,
            "branch": self.branch,
            "created_at": self.created_at,
        }
        state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def advance(self) -> None:
        """Advance to the next phase based on current state and required files.

        Raises:
            FileNotFoundError: Required file for the current phase is missing.
            ValueError: Called on a terminal (completed) phase.
        """
        if self.phase == "completed":
            raise ValueError("Cannot advance from terminal phase 'completed'.")

        required = _REQUIRED_FILES.get(self.phase)
        if required:
            required_path = self.harness_dir / required
            if not required_path.exists():
                raise FileNotFoundError(
                    f"Required file '{required}' not found in {self.harness_dir} "
                    f"(current phase: {self.phase})"
                )

        if self.phase == "plan_ready":
            self.phase = "gen_ready"

        elif self.phase == "gen_ready":
            self.phase = "eval_ready"

        elif self.phase == "eval_ready":
            verdict = self._parse_qa_verdict()
            if verdict == "PASS":
                self.phase = "completed"
            else:
                # FAIL
                if self.round >= self.max_rounds:
                    self.phase = "completed"
                else:
                    self.round += 1
                    self.phase = "gen_ready"

        self.save()

    # ------------------------------------------------------------------
    # QA verdict parsing
    # ------------------------------------------------------------------

    def _parse_qa_verdict(self) -> str:
        """Parse qa_report.md for the QA verdict.

        Supports:
          - Korean: "종합 판정: PASS" / "종합 판정: FAIL"
          - English fallback: "Verdict: PASS" / "Verdict: FAIL"

        Returns "PASS" or "FAIL". Defaults to "FAIL" if unparseable.
        """
        qa_report = self.harness_dir / "qa_report.md"
        if not qa_report.exists():
            return "FAIL"

        content = qa_report.read_text(encoding="utf-8")

        # Korean pattern first
        match = re.search(r"종합\s*판정\s*:\s*(PASS|FAIL)", content, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # English fallback
        match = re.search(r"Verdict\s*:\s*(PASS|FAIL)", content, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Default to FAIL
        return "FAIL"

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"HarnessState(phase={self.phase!r}, round={self.round}, "
            f"task={self.task!r}, repo={self.repo_name!r})"
        )
