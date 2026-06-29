"""
Tests for infra/project.py: _build_github, load_project.
"""

from pathlib import Path

import pytest

from adda_dev.domain.github import GitHub
from adda_dev.domain.project import ProjectNotFoundError
from adda_dev.infra.config import ProjectDefaults
from adda_dev.infra.project import GitHubFileModel, _build_github, load_project
from adda_dev.infra.store import InvalidFileNameError
from tests.conftest import FakeSecretSource

_DEFAULTS = ProjectDefaults()
_FAKE = FakeSecretSource()

# ---------------------------------------------------------------------------
# _build_github
# ---------------------------------------------------------------------------


def test_build_github_creates_github_domain_model() -> None:
    fake = FakeSecretSource()
    file = GitHubFileModel(owner="acme", repo="tool", secret_name="token")
    gh = _build_github(file, fake)
    assert isinstance(gh, GitHub)
    assert gh.owner == "acme"
    assert gh.repo == "tool"
    assert gh.secret_name == "token"
    assert gh.source is fake


# ---------------------------------------------------------------------------
# load_project — source is threaded through to GitHub
# ---------------------------------------------------------------------------


def test_load_project_threads_source_to_github(tmp_path: Path) -> None:
    fake = FakeSecretSource()
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "proj.toml").write_text(
        'image = "img:v1"\nbackend = "anthropic"\n[github]\nowner = "a"\nrepo = "b"\nsecret_name = "k"\n'
    )
    proj = load_project("proj", _DEFAULTS, fake, config_dir=tmp_path)
    assert proj.github.source is fake


# ---------------------------------------------------------------------------
# load_project — ProjectNotFoundError when file missing
# ---------------------------------------------------------------------------


def test_load_project_missing_raises_project_not_found_error(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    with pytest.raises(ProjectNotFoundError, match="nonexistent"):
        load_project("nonexistent", _DEFAULTS, _FAKE, config_dir=tmp_path)


# ---------------------------------------------------------------------------
# load_project — InvalidFileNameError for bad name
# ---------------------------------------------------------------------------


def test_load_project_bad_name_raises_invalid_file_name_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidFileNameError):
        load_project("bad.name", _DEFAULTS, _FAKE, config_dir=tmp_path)
