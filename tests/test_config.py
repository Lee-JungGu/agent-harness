"""Tests for config.py - HarnessConfig class."""

import pytest
import yaml
from pathlib import Path

from config import HarnessConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg(tmp_path):
    """HarnessConfig instance backed by a temp directory."""
    return HarnessConfig(config_dir=tmp_path)


@pytest.fixture
def cfg_with_repo(cfg):
    """HarnessConfig with one registered repo."""
    cfg.init()
    cfg.add_repo(
        name="my-backend",
        path="/c/workspace/my-backend",
        lang="java",
        test_cmd="./gradlew test",
        build_cmd="./gradlew build",
        default_scope="src/**",
    )
    return cfg


# ---------------------------------------------------------------------------
# init()
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_repos_yaml(self, cfg, tmp_path):
        cfg.init()
        repos_yaml = tmp_path / "repos.yaml"
        assert repos_yaml.exists()

    def test_repos_yaml_has_empty_repos_key(self, cfg, tmp_path):
        cfg.init()
        data = yaml.safe_load((tmp_path / "repos.yaml").read_text())
        assert data == {"repos": {}}

    def test_init_idempotent(self, cfg, tmp_path):
        cfg.init()
        cfg.init()  # second call should not raise
        data = yaml.safe_load((tmp_path / "repos.yaml").read_text())
        assert data == {"repos": {}}

    def test_creates_config_dir_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "dir"
        cfg = HarnessConfig(config_dir=nested)
        cfg.init()
        assert (nested / "repos.yaml").exists()


# ---------------------------------------------------------------------------
# load_repos()
# ---------------------------------------------------------------------------

class TestLoadRepos:
    def test_empty_after_init(self, cfg):
        cfg.init()
        assert cfg.load_repos() == {}

    def test_returns_registered_repos(self, cfg_with_repo):
        repos = cfg_with_repo.load_repos()
        assert "my-backend" in repos

    def test_repo_fields(self, cfg_with_repo):
        repo = cfg_with_repo.load_repos()["my-backend"]
        assert repo["path"] == "/c/workspace/my-backend"
        assert repo["lang"] == "java"
        assert repo["test_cmd"] == "./gradlew test"
        assert repo["build_cmd"] == "./gradlew build"
        assert repo["default_scope"] == "src/**"
        assert repo["test_available"] is True

    def test_load_repos_without_init_raises(self, cfg):
        with pytest.raises(FileNotFoundError):
            cfg.load_repos()


# ---------------------------------------------------------------------------
# add_repo()
# ---------------------------------------------------------------------------

class TestAddRepo:
    def test_add_repo_persisted_to_yaml(self, cfg, tmp_path):
        cfg.init()
        cfg.add_repo(name="svc", path="/tmp/svc", lang="python")
        data = yaml.safe_load((tmp_path / "repos.yaml").read_text())
        assert "svc" in data["repos"]

    def test_test_available_true_when_test_cmd_given(self, cfg):
        cfg.init()
        cfg.add_repo(name="svc", path="/tmp/svc", lang="python", test_cmd="pytest")
        repo = cfg.load_repos()["svc"]
        assert repo["test_available"] is True

    def test_test_available_false_when_no_test_cmd(self, cfg):
        cfg.init()
        cfg.add_repo(name="svc", path="/tmp/svc", lang="python")
        repo = cfg.load_repos()["svc"]
        assert repo["test_available"] is False

    def test_duplicate_name_raises_value_error(self, cfg):
        cfg.init()
        cfg.add_repo(name="svc", path="/tmp/svc", lang="python")
        with pytest.raises(ValueError, match="already registered"):
            cfg.add_repo(name="svc", path="/tmp/svc2", lang="java")

    def test_optional_fields_absent_when_not_provided(self, cfg):
        cfg.init()
        cfg.add_repo(name="svc", path="/tmp/svc", lang="python")
        repo = cfg.load_repos()["svc"]
        assert repo.get("test_cmd") is None
        assert repo.get("build_cmd") is None
        assert repo.get("default_scope") is None

    def test_multiple_repos_can_be_added(self, cfg):
        cfg.init()
        cfg.add_repo(name="alpha", path="/tmp/alpha", lang="python")
        cfg.add_repo(name="beta", path="/tmp/beta", lang="java")
        repos = cfg.load_repos()
        assert "alpha" in repos
        assert "beta" in repos


# ---------------------------------------------------------------------------
# remove_repo()
# ---------------------------------------------------------------------------

class TestRemoveRepo:
    def test_remove_existing_repo(self, cfg_with_repo):
        cfg_with_repo.remove_repo("my-backend")
        assert "my-backend" not in cfg_with_repo.load_repos()

    def test_remove_nonexistent_repo_raises(self, cfg):
        cfg.init()
        with pytest.raises(ValueError, match="not found"):
            cfg.remove_repo("ghost")

    def test_remove_one_leaves_others(self, cfg):
        cfg.init()
        cfg.add_repo(name="alpha", path="/tmp/alpha", lang="python")
        cfg.add_repo(name="beta", path="/tmp/beta", lang="java")
        cfg.remove_repo("alpha")
        repos = cfg.load_repos()
        assert "alpha" not in repos
        assert "beta" in repos


# ---------------------------------------------------------------------------
# update_repo()
# ---------------------------------------------------------------------------

class TestUpdateRepo:
    def test_update_lang(self, cfg_with_repo):
        cfg_with_repo.update_repo("my-backend", lang="kotlin")
        assert cfg_with_repo.load_repos()["my-backend"]["lang"] == "kotlin"

    def test_update_test_cmd_re_derives_test_available_true(self, cfg):
        cfg.init()
        cfg.add_repo(name="svc", path="/tmp/svc", lang="python")
        assert cfg.load_repos()["svc"]["test_available"] is False
        cfg.update_repo("svc", test_cmd="pytest")
        assert cfg.load_repos()["svc"]["test_available"] is True

    def test_update_removes_test_cmd_re_derives_test_available_false(self, cfg_with_repo):
        cfg_with_repo.update_repo("my-backend", test_cmd=None)
        assert cfg_with_repo.load_repos()["my-backend"]["test_available"] is False

    def test_update_nonexistent_repo_raises(self, cfg):
        cfg.init()
        with pytest.raises(ValueError, match="not found"):
            cfg.update_repo("ghost", lang="python")

    def test_update_persisted(self, cfg_with_repo, tmp_path):
        cfg_with_repo.update_repo("my-backend", build_cmd="./gradlew assemble")
        data = yaml.safe_load((tmp_path / "repos.yaml").read_text())
        assert data["repos"]["my-backend"]["build_cmd"] == "./gradlew assemble"

    def test_update_default_scope(self, cfg_with_repo):
        cfg_with_repo.update_repo("my-backend", default_scope="src/main/**")
        assert cfg_with_repo.load_repos()["my-backend"]["default_scope"] == "src/main/**"


# ---------------------------------------------------------------------------
# get_repo_config()
# ---------------------------------------------------------------------------

class TestGetRepoConfig:
    def test_returns_repos_yaml_fields(self, cfg_with_repo):
        config = cfg_with_repo.get_repo_config("my-backend")
        assert config["lang"] == "java"
        assert config["test_cmd"] == "./gradlew test"

    def test_nonexistent_repo_raises(self, cfg):
        cfg.init()
        with pytest.raises(ValueError, match="not found"):
            cfg.get_repo_config("ghost")

    def test_cli_override_scope_maps_to_default_scope(self, cfg_with_repo):
        config = cfg_with_repo.get_repo_config("my-backend", cli_overrides={"scope": "lib/**"})
        assert config["default_scope"] == "lib/**"

    def test_harness_yaml_overrides_repos_yaml(self, cfg_with_repo, tmp_path):
        repo_root = Path("/c/workspace/my-backend")
        harness_yaml = tmp_path / "harness_repo_root"
        harness_yaml.mkdir()
        harness_file = harness_yaml / ".harness.yaml"
        harness_file.write_text(yaml.dump({"lang": "kotlin", "test_cmd": "./gradlew testKotlin"}))

        # Patch the repo path to our temp dir
        cfg_with_repo.update_repo("my-backend", path=str(harness_yaml))
        config = cfg_with_repo.get_repo_config("my-backend")
        assert config["lang"] == "kotlin"
        assert config["test_cmd"] == "./gradlew testKotlin"

    def test_cli_overrides_win_over_harness_yaml(self, cfg_with_repo, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".harness.yaml").write_text(yaml.dump({"default_scope": "src/**"}))
        cfg_with_repo.update_repo("my-backend", path=str(repo_root))

        config = cfg_with_repo.get_repo_config("my-backend", cli_overrides={"scope": "lib/**"})
        assert config["default_scope"] == "lib/**"

    def test_no_cli_overrides(self, cfg_with_repo):
        config = cfg_with_repo.get_repo_config("my-backend")
        assert config["default_scope"] == "src/**"

    def test_harness_yaml_partial_override(self, cfg_with_repo, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        # Only override lang; test_cmd should come from repos.yaml
        (repo_root / ".harness.yaml").write_text(yaml.dump({"lang": "groovy"}))
        cfg_with_repo.update_repo("my-backend", path=str(repo_root))

        config = cfg_with_repo.get_repo_config("my-backend")
        assert config["lang"] == "groovy"
        assert config["test_cmd"] == "./gradlew test"

    def test_cli_overrides_none_does_not_override(self, cfg_with_repo):
        config = cfg_with_repo.get_repo_config("my-backend", cli_overrides={"scope": None})
        # None value should not override existing default_scope
        assert config["default_scope"] == "src/**"


# ---------------------------------------------------------------------------
# build_adhoc_config()
# ---------------------------------------------------------------------------

class TestBuildAdhocConfig:
    def test_basic_adhoc_config(self, cfg):
        cfg.init()
        config = cfg.build_adhoc_config(repo_path="/tmp/myrepo", lang="python")
        assert config["path"] == "/tmp/myrepo"
        assert config["lang"] == "python"

    def test_test_available_false_no_test_cmd(self, cfg):
        cfg.init()
        config = cfg.build_adhoc_config(repo_path="/tmp/myrepo", lang="python")
        assert config["test_available"] is False

    def test_harness_yaml_applied_in_adhoc(self, cfg, tmp_path):
        repo_root = tmp_path / "adhoc_repo"
        repo_root.mkdir()
        (repo_root / ".harness.yaml").write_text(
            yaml.dump({"test_cmd": "pytest", "default_scope": "src/**"})
        )
        config = cfg.build_adhoc_config(repo_path=str(repo_root), lang="python")
        assert config["test_cmd"] == "pytest"
        assert config["test_available"] is True
        assert config["default_scope"] == "src/**"

    def test_cli_overrides_applied_in_adhoc(self, cfg):
        cfg.init()
        config = cfg.build_adhoc_config(
            repo_path="/tmp/myrepo",
            lang="python",
            cli_overrides={"scope": "app/**"},
        )
        assert config["default_scope"] == "app/**"

    def test_cli_overrides_win_over_harness_yaml_in_adhoc(self, cfg, tmp_path):
        repo_root = tmp_path / "adhoc_repo"
        repo_root.mkdir()
        (repo_root / ".harness.yaml").write_text(yaml.dump({"default_scope": "src/**"}))
        config = cfg.build_adhoc_config(
            repo_path=str(repo_root),
            lang="python",
            cli_overrides={"scope": "tests/**"},
        )
        assert config["default_scope"] == "tests/**"

    def test_adhoc_does_not_require_init(self, cfg):
        # build_adhoc_config should work even without init()
        config = cfg.build_adhoc_config(repo_path="/tmp/myrepo", lang="typescript")
        assert config["lang"] == "typescript"
