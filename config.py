"""config.py - HarnessConfig: manages ~/.agent-harness/repos.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPOS_YAML = "repos.yaml"
_HARNESS_YAML = ".harness.yaml"


class HarnessConfig:
    """Manages the agent-harness configuration directory and repos.yaml."""

    def __init__(self, config_dir: Path | str | None = None) -> None:
        if config_dir is None:
            self._config_dir = Path.home() / ".agent-harness"
        else:
            self._config_dir = Path(config_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _repos_path(self) -> Path:
        return self._config_dir / _REPOS_YAML

    def _read_yaml(self) -> dict:
        """Read repos.yaml and return its parsed contents."""
        if not self._repos_path.exists():
            raise FileNotFoundError(
                f"repos.yaml not found at {self._repos_path}. Run 'harness init' first."
            )
        data = yaml.safe_load(self._repos_path.read_text(encoding="utf-8")) or {}
        if "repos" not in data:
            data["repos"] = {}
        return data

    def _write_yaml(self, data: dict) -> None:
        """Write data back to repos.yaml."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._repos_path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    @staticmethod
    def _derive_test_available(fields: dict) -> bool:
        """test_available is True iff test_cmd is a non-empty string."""
        test_cmd = fields.get("test_cmd")
        return bool(test_cmd)

    @staticmethod
    def _load_harness_yaml(repo_path: str | Path) -> dict:
        """Load .harness.yaml from repo root if it exists; return empty dict otherwise."""
        harness_file = Path(repo_path) / _HARNESS_YAML
        if harness_file.exists():
            data = yaml.safe_load(harness_file.read_text(encoding="utf-8")) or {}
            return data
        return {}

    @staticmethod
    def _apply_cli_overrides(base: dict, cli_overrides: dict | None) -> dict:
        """
        Merge CLI overrides into base config (in-place copy).
        The "scope" key in cli_overrides maps to "default_scope".
        Only non-None values are applied.
        """
        if not cli_overrides:
            return base
        result = dict(base)
        for key, value in cli_overrides.items():
            if value is None:
                continue
            if key == "scope":
                result["default_scope"] = value
            else:
                result[key] = value
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Create config directory and empty repos.yaml (idempotent)."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        if not self._repos_path.exists():
            self._write_yaml({"repos": {}})

    def load_repos(self) -> dict[str, dict]:
        """Return all registered repos as a dict keyed by name."""
        data = self._read_yaml()
        return data.get("repos", {})

    def add_repo(
        self,
        name: str,
        path: str,
        lang: str,
        test_cmd: str | None = None,
        build_cmd: str | None = None,
        default_scope: str | None = None,
    ) -> None:
        """Register a new repository. Raises ValueError if name already exists."""
        data = self._read_yaml()
        repos = data["repos"]

        if name in repos:
            raise ValueError(f"Repository '{name}' is already registered.")

        entry: dict[str, Any] = {
            "path": path,
            "lang": lang,
            "test_cmd": test_cmd,
            "build_cmd": build_cmd,
            "default_scope": default_scope,
            "test_available": self._derive_test_available({"test_cmd": test_cmd}),
        }
        # Keep None values in the dict for explicit absence; YAML will store them as null.
        repos[name] = entry
        self._write_yaml(data)

    def remove_repo(self, name: str) -> None:
        """Remove a registered repository. Raises ValueError if not found."""
        data = self._read_yaml()
        repos = data["repos"]

        if name not in repos:
            raise ValueError(f"Repository '{name}' not found.")

        del repos[name]
        self._write_yaml(data)

    def update_repo(self, name: str, **kwargs: Any) -> None:
        """
        Update fields of a registered repo.
        Accepts: path, lang, test_cmd, build_cmd, default_scope.
        Re-derives test_available after update.
        Raises ValueError if repo not found.
        """
        data = self._read_yaml()
        repos = data["repos"]

        if name not in repos:
            raise ValueError(f"Repository '{name}' not found.")

        entry = repos[name]
        allowed = {"path", "lang", "test_cmd", "build_cmd", "default_scope"}
        for key, value in kwargs.items():
            if key in allowed:
                entry[key] = value

        # Re-derive test_available based on updated test_cmd
        entry["test_available"] = self._derive_test_available(entry)
        self._write_yaml(data)

    def get_repo_config(
        self,
        name: str,
        cli_overrides: dict | None = None,
    ) -> dict:
        """
        Return merged config for a registered repo using 3-layer merge:
          repos.yaml < .harness.yaml (in repo root) < CLI overrides.

        cli_overrides may contain a "scope" key which maps to "default_scope".
        Only non-None values in cli_overrides are applied.
        Raises ValueError if repo is not registered.
        """
        repos = self.load_repos()
        if name not in repos:
            raise ValueError(f"Repository '{name}' not found.")

        # Layer 1: repos.yaml base
        base = dict(repos[name])

        # Layer 2: .harness.yaml in repo root
        repo_path = base.get("path", "")
        harness_overrides = self._load_harness_yaml(repo_path)
        for key, value in harness_overrides.items():
            base[key] = value

        # Re-derive test_available after .harness.yaml merge
        base["test_available"] = self._derive_test_available(base)

        # Layer 3: CLI overrides
        base = self._apply_cli_overrides(base, cli_overrides)

        # Re-derive after CLI merge (cli might change test_cmd)
        base["test_available"] = self._derive_test_available(base)

        return base

    def build_adhoc_config(
        self,
        repo_path: str,
        lang: str,
        cli_overrides: dict | None = None,
    ) -> dict:
        """
        Build config for an unregistered repo (used with --repo-path).
        Applies .harness.yaml override from the repo root and CLI overrides.
        Does NOT require init() to have been called.
        """
        # Layer 1: base from arguments
        base: dict[str, Any] = {
            "path": repo_path,
            "lang": lang,
            "test_cmd": None,
            "build_cmd": None,
            "default_scope": None,
            "test_available": False,
        }

        # Layer 2: .harness.yaml in repo root
        harness_overrides = self._load_harness_yaml(repo_path)
        for key, value in harness_overrides.items():
            base[key] = value

        # Re-derive after harness.yaml
        base["test_available"] = self._derive_test_available(base)

        # Layer 3: CLI overrides
        base = self._apply_cli_overrides(base, cli_overrides)

        # Re-derive after CLI
        base["test_available"] = self._derive_test_available(base)

        return base
