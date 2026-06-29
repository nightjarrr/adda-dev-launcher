"""
Tests for domain/github.py: GitHub domain model.
Tests for infra/project.py: GitHubFileModel validation.
"""

import pytest

from adda_dev.domain.credentials import SecretError
from adda_dev.domain.github import GitHub
from adda_dev.infra.project import GitHubFileModel
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# GitHubFileModel — valid inputs
# ---------------------------------------------------------------------------


def _valid_github_data() -> dict[str, str]:
    return {"owner": "nightjarrr", "repo": "adda-dev-launcher", "secret_name": "demo-token"}


def test_github_file_model_valid_minimal() -> None:
    m = GitHubFileModel.model_validate(_valid_github_data())
    assert m.owner == "nightjarrr"
    assert m.repo == "adda-dev-launcher"
    assert m.secret_name == "demo-token"


def test_github_file_model_owner_with_dot_accepted() -> None:
    data = _valid_github_data()
    data["owner"] = "my.org"
    m = GitHubFileModel.model_validate(data)
    assert m.owner == "my.org"


def test_github_file_model_repo_with_dot_accepted() -> None:
    data = _valid_github_data()
    data["repo"] = "my.repo"
    m = GitHubFileModel.model_validate(data)
    assert m.repo == "my.repo"


# ---------------------------------------------------------------------------
# GitHubFileModel — invalid inputs
# ---------------------------------------------------------------------------


def test_github_file_model_bad_owner_rejected() -> None:
    data = _valid_github_data()
    data["owner"] = "bad/owner"
    with pytest.raises(Exception):
        GitHubFileModel.model_validate(data)


def test_github_file_model_bad_repo_rejected() -> None:
    data = _valid_github_data()
    data["repo"] = "bad repo"
    with pytest.raises(Exception):
        GitHubFileModel.model_validate(data)


def test_github_file_model_missing_owner_rejected() -> None:
    data = _valid_github_data()
    del data["owner"]
    with pytest.raises(Exception):
        GitHubFileModel.model_validate(data)


def test_github_file_model_missing_repo_rejected() -> None:
    data = _valid_github_data()
    del data["repo"]
    with pytest.raises(Exception):
        GitHubFileModel.model_validate(data)


def test_github_file_model_missing_secret_name_rejected() -> None:
    data = _valid_github_data()
    del data["secret_name"]
    with pytest.raises(Exception):
        GitHubFileModel.model_validate(data)


def test_github_file_model_extra_key_rejected() -> None:
    data = _valid_github_data()
    data["extra"] = "value"
    with pytest.raises(Exception):
        GitHubFileModel.model_validate(data)


# ---------------------------------------------------------------------------
# GitHub — domain model with injected FakeSecretSource
# ---------------------------------------------------------------------------


def test_github_get_secret_returns_value() -> None:
    fake = FakeSecretSource({("adda-dev:github", "demo-token"): "ghp_abc123"})
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="demo-token", source=fake)
    assert gh.get_secret() == "ghp_abc123"


def test_github_get_secret_raises_on_missing() -> None:
    fake = FakeSecretSource()
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="demo-token", source=fake)
    with pytest.raises(SecretError):
        gh.get_secret()


def test_github_service_namespace() -> None:
    assert GitHub._service == "adda-dev:github"


def test_github_frozen_dataclass() -> None:
    fake = FakeSecretSource()
    gh = GitHub(owner="a", repo="b", secret_name="k", source=fake)
    with pytest.raises(Exception):
        gh.owner = "changed"  # type: ignore[misc]
