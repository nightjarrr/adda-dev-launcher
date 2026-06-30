"""
Tests for adda_dev.infra.contract: DockerContractTranslator and _detect_tz.
"""

from pathlib import Path

import pytest

from adda_dev.domain.contract import (
    CONTAINER_USERNAME,
    PROXY_PORT,
    PROXY_SOCKET,
    RUN_TMPFS_SIZE,
    TMPFS_MODE,
    ContractError,
    ContractSpec,
)
from adda_dev.domain.llm import AnthropicBackend, DeepSeekBackend
from adda_dev.domain.tmpfs import TmpfsSizes
from adda_dev.infra.contract import DockerContractTranslator, _detect_tz
from tests.conftest import FakeSecretSource

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_anthropic_spec() -> ContractSpec:
    source = FakeSecretSource(
        {
            ("adda-dev:github", "gh-token"): "ghp_test",
            ("adda-dev:anthropic", "claude-key"): "claude_test",
        }
    )
    from adda_dev.domain.github import GitHub

    github = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    backend = AnthropicBackend(secret_name="claude-key", source=source)
    return ContractSpec(github=github, backend=backend, image="ghcr.io/test/adda:latest", tmpfs=TmpfsSizes())


def _make_deepseek_spec() -> ContractSpec:
    source = FakeSecretSource(
        {
            ("adda-dev:github", "gh-token"): "ghp_test",
            ("adda-dev:deepseek", "ds-key"): "ds_test",
        }
    )
    from adda_dev.domain.github import GitHub

    github = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    backend = DeepSeekBackend(
        secret_name="ds-key",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        opus_model="deepseek-chat",
        sonnet_model="deepseek-chat",
        haiku_model="deepseek-chat",
        subagent_model="deepseek-chat",
        effort_level="normal",
        source=source,
    )
    return ContractSpec(github=github, backend=backend, image="ghcr.io/test/adda:latest", tmpfs=TmpfsSizes())


def _translate(spec: ContractSpec, tmp_path: Path) -> object:
    tz_file = tmp_path / "timezone"
    tz_file.write_text("Europe/London\n")
    import adda_dev.infra.contract as _mod

    original = _mod._ETC_TIMEZONE
    _mod._ETC_TIMEZONE = tz_file
    try:
        return DockerContractTranslator().translate(spec)
    finally:
        _mod._ETC_TIMEZONE = original


# ---------------------------------------------------------------------------
# ContractSpec defaults
# ---------------------------------------------------------------------------


def test_contractspec_defaults_proxy_socket() -> None:
    spec = _make_anthropic_spec()
    assert spec.proxy_socket == PROXY_SOCKET


def test_contractspec_defaults_proxy_port() -> None:
    spec = _make_anthropic_spec()
    assert spec.proxy_port == PROXY_PORT


def test_contractspec_defaults_issue_id_none() -> None:
    spec = _make_anthropic_spec()
    assert spec.issue_id is None


# ---------------------------------------------------------------------------
# DockerContractTranslator — Anthropic backend
# ---------------------------------------------------------------------------


def test_dockercontracttranslator_anthropic_github_owner_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "GITHUB_OWNER=nightjarrr" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_github_repo_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "GITHUB_REPO=adda-dev-launcher" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_github_token_name_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "GITHUB_TOKEN_" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_github_token_value_not_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "ghp_test" not in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_github_token_value_in_env(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert params.env["GITHUB_TOKEN_"] == "ghp_test"  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_tz_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "TZ=Europe/London" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_proxy_socket_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert f"ADDA_DEV_PROXY_SOCKET={PROXY_SOCKET}" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_proxy_port_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert f"ADDA_DEV_PROXY_PORT={PROXY_PORT}" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_backend_label_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "ADDA_DEV_LLM_BACKEND=anthropic" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_oauth_token_name_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "CLAUDE_CODE_OAUTH_TOKEN" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_oauth_token_value_not_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "claude_test" not in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_oauth_token_value_in_env(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert params.env["CLAUDE_CODE_OAUTH_TOKEN"] == "claude_test"  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_disable_traffic_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_anthropic_runtime_image_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "ADDA_DEV_RUNTIME_IMAGE=ghcr.io/test/adda:latest" in params.args  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# DockerContractTranslator — DeepSeek backend
# ---------------------------------------------------------------------------


def test_dockercontracttranslator_deepseek_backend_label_in_args(tmp_path: Path) -> None:
    params = _translate(_make_deepseek_spec(), tmp_path)
    assert "ADDA_DEV_LLM_BACKEND=deepseek" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_deepseek_base_url_in_args(tmp_path: Path) -> None:
    params = _translate(_make_deepseek_spec(), tmp_path)
    assert "ANTHROPIC_BASE_URL=https://api.deepseek.com" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_deepseek_auth_token_name_in_args(tmp_path: Path) -> None:
    params = _translate(_make_deepseek_spec(), tmp_path)
    assert "ANTHROPIC_AUTH_TOKEN" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_deepseek_auth_token_value_not_in_args(tmp_path: Path) -> None:
    params = _translate(_make_deepseek_spec(), tmp_path)
    assert "ds_test" not in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_deepseek_auth_token_value_in_env(tmp_path: Path) -> None:
    params = _translate(_make_deepseek_spec(), tmp_path)
    assert params.env["ANTHROPIC_AUTH_TOKEN"] == "ds_test"  # type: ignore[union-attr]


def test_dockercontracttranslator_deepseek_model_vars_in_args(tmp_path: Path) -> None:
    params = _translate(_make_deepseek_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    assert "ANTHROPIC_MODEL=deepseek-chat" in args
    assert "ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-chat" in args
    assert "ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-chat" in args
    assert "ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-chat" in args
    assert "CLAUDE_CODE_SUBAGENT_MODEL=deepseek-chat" in args
    assert "CLAUDE_CODE_EFFORT_LEVEL=normal" in args


# ---------------------------------------------------------------------------
# DockerContractTranslator — tmpfs mounts
# ---------------------------------------------------------------------------


def test_dockercontracttranslator_tmpfs_workspace_mount_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    assert any("/workspace:" in a and "rw,exec,nosuid,nodev" in a for a in args)


def test_dockercontracttranslator_tmpfs_tmp_mount_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    assert any("/tmp:" in a and "rw,exec,nosuid,nodev" in a for a in args)


def test_dockercontracttranslator_tmpfs_home_mount_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    assert any(f"/home/{CONTAINER_USERNAME}:" in a and "rw,exec,nosuid,nodev" in a for a in args)


def test_dockercontracttranslator_tmpfs_run_mount_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    assert any(
        a.startswith("/run:") and f"size={RUN_TMPFS_SIZE}" in a and f"mode={TMPFS_MODE}" in a and "noexec" in a for a in args
    )


def test_dockercontracttranslator_tmpfs_workspace_size_reflects_spec(tmp_path: Path) -> None:
    source = FakeSecretSource(
        {
            ("adda-dev:github", "gh-token"): "ghp_test",
            ("adda-dev:anthropic", "claude-key"): "claude_test",
        }
    )
    from adda_dev.domain.github import GitHub

    github = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    backend = AnthropicBackend(secret_name="claude-key", source=source)
    spec = ContractSpec(github=github, backend=backend, image="img", tmpfs=TmpfsSizes(workspace="1024m"))
    params = _translate(spec, tmp_path)
    args = params.args  # type: ignore[union-attr]
    assert any("/workspace:" in a and "size=1024m" in a for a in args)


# ---------------------------------------------------------------------------
# DockerContractTranslator — hardening
# ---------------------------------------------------------------------------


def test_dockercontracttranslator_hardening_cap_drop_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    idx = list(args).index("--cap-drop")
    assert args[idx + 1] == "ALL"


def test_dockercontracttranslator_hardening_no_new_privileges_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    idx = list(args).index("--security-opt")
    assert args[idx + 1] == "no-new-privileges"


def test_dockercontracttranslator_hardening_read_only_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert "--read-only" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_hardening_network_none_in_args(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    args = params.args  # type: ignore[union-attr]
    idx = list(args).index("--network")
    assert args[idx + 1] == "none"


# ---------------------------------------------------------------------------
# DockerContractTranslator — optional vars
# ---------------------------------------------------------------------------


def test_dockercontracttranslator_issue_id_in_args_when_set(tmp_path: Path) -> None:
    source = FakeSecretSource(
        {
            ("adda-dev:github", "gh-token"): "ghp_test",
            ("adda-dev:anthropic", "claude-key"): "claude_test",
        }
    )
    from adda_dev.domain.github import GitHub

    github = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    backend = AnthropicBackend(secret_name="claude-key", source=source)
    spec = ContractSpec(github=github, backend=backend, image="img", tmpfs=TmpfsSizes(), issue_id=42)
    params = _translate(spec, tmp_path)
    assert "ISSUE_ID=42" in params.args  # type: ignore[union-attr]


def test_dockercontracttranslator_issue_id_absent_when_none(tmp_path: Path) -> None:
    params = _translate(_make_anthropic_spec(), tmp_path)
    assert not any("ISSUE_ID" in a for a in params.args)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TZ detection
# ---------------------------------------------------------------------------


def test_detect_tz_reads_etc_timezone_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tz_file = tmp_path / "timezone"
    tz_file.write_text("America/New_York\n")
    monkeypatch.setattr("adda_dev.infra.contract._ETC_TIMEZONE", tz_file)
    assert _detect_tz(tz_file=tz_file) == "America/New_York"


def test_detect_tz_follows_localtime_symlink_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    zoneinfo_dir = tmp_path / "usr" / "share" / "zoneinfo" / "Europe"
    zoneinfo_dir.mkdir(parents=True)
    zone_file = zoneinfo_dir / "Berlin"
    zone_file.write_text("")
    symlink = tmp_path / "localtime"
    symlink.symlink_to(zone_file)
    absent = tmp_path / "no-timezone"
    monkeypatch.setattr("adda_dev.infra.contract._ETC_TIMEZONE", absent)
    monkeypatch.setattr("adda_dev.infra.contract._ETC_LOCALTIME", symlink)
    assert _detect_tz(tz_file=absent, localtime=symlink) == "Europe/Berlin"


def test_detect_tz_follows_localtime_symlink_macos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    zoneinfo_dir = tmp_path / "var" / "db" / "timezone" / "zoneinfo" / "America"
    zoneinfo_dir.mkdir(parents=True)
    zone_file = zoneinfo_dir / "Los_Angeles"
    zone_file.write_text("")
    symlink = tmp_path / "localtime"
    symlink.symlink_to(zone_file)
    absent = tmp_path / "no-timezone"
    monkeypatch.setattr("adda_dev.infra.contract._ETC_TIMEZONE", absent)
    monkeypatch.setattr("adda_dev.infra.contract._ETC_LOCALTIME", symlink)
    assert _detect_tz(tz_file=absent, localtime=symlink) == "America/Los_Angeles"


def test_detect_tz_raises_when_no_timezone_file_and_no_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absent_tz = tmp_path / "no-timezone"
    absent_lt = tmp_path / "no-localtime"
    monkeypatch.setattr("adda_dev.infra.contract._ETC_TIMEZONE", absent_tz)
    monkeypatch.setattr("adda_dev.infra.contract._ETC_LOCALTIME", absent_lt)
    with pytest.raises(ContractError):
        _detect_tz(tz_file=absent_tz, localtime=absent_lt)


def test_detect_tz_raises_when_localtime_is_regular_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absent_tz = tmp_path / "no-timezone"
    plain_file = tmp_path / "localtime"
    plain_file.write_text("not a symlink")
    monkeypatch.setattr("adda_dev.infra.contract._ETC_TIMEZONE", absent_tz)
    monkeypatch.setattr("adda_dev.infra.contract._ETC_LOCALTIME", plain_file)
    with pytest.raises(ContractError):
        _detect_tz(tz_file=absent_tz, localtime=plain_file)
