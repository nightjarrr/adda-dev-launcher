"""
Docker contract translator: converts ContractSpec into ContractProcessParams for Docker CLI invocation.
"""

from pathlib import Path

from ..domain.contract import (
    CONTAINER_GID,
    CONTAINER_UID,
    CONTAINER_USERNAME,
    RUN_TMPFS_SIZE,
    TMPFS_MODE,
    ContractError,
    ContractProcessParams,
    ContractSpec,
    ContractTranslator,
)
from ..domain.llm import AnthropicBackend, DeepSeekBackend

_ETC_TIMEZONE: Path = Path("/etc/timezone")
_ETC_LOCALTIME: Path = Path("/etc/localtime")


def _detect_tz(tz_file: Path | None = None, localtime: Path | None = None) -> str:
    tz = tz_file if tz_file is not None else _ETC_TIMEZONE
    lt = localtime if localtime is not None else _ETC_LOCALTIME
    if tz.is_file():
        content = tz.read_text().strip()
        if content:
            return content
    if lt.is_symlink():
        resolved = lt.resolve()
        parts = resolved.parts
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] == "zoneinfo":
                return str(Path(*parts[i + 1 :]))
    raise ContractError(f"Cannot detect host timezone: {tz} is absent or empty, and {lt} is not a usable symlink")


def _build_env_args(spec: ContractSpec, tz: str) -> tuple[tuple[str, ...], dict[str, str]]:
    args: list[str] = []
    env: dict[str, str] = {}

    # Non-secret GitHub identity
    args += ["--env", f"GITHUB_OWNER={spec.github.owner}"]
    args += ["--env", f"GITHUB_REPO={spec.github.repo}"]

    # Secret: GitHub token — name only in args, value in env
    github_token = spec.github.get_secret()
    github_token_key = "GITHUB_TOKEN_"
    args += ["--env", github_token_key]
    env[github_token_key] = github_token

    # Non-secret: timezone and proxy
    args += ["--env", f"TZ={tz}"]
    args += ["--env", f"ADDA_DEV_PROXY_SOCKET={spec.proxy_socket}"]
    args += ["--env", f"ADDA_DEV_PROXY_PORT={spec.proxy_port}"]

    # Non-secret: backend label and credentials
    if isinstance(spec.backend, AnthropicBackend):
        args += ["--env", "ADDA_DEV_LLM_BACKEND=anthropic"]
        oauth_token = spec.backend.get_secret()
        oauth_key = "CLAUDE_CODE_OAUTH_TOKEN"
        args += ["--env", oauth_key]
        env[oauth_key] = oauth_token
    elif isinstance(spec.backend, DeepSeekBackend):
        args += ["--env", "ADDA_DEV_LLM_BACKEND=deepseek"]
        args += ["--env", f"ANTHROPIC_BASE_URL={spec.backend.base_url}"]
        ds_token = spec.backend.get_secret()
        ds_key = "ANTHROPIC_AUTH_TOKEN"
        args += ["--env", ds_key]
        env[ds_key] = ds_token
        args += ["--env", f"ANTHROPIC_MODEL={spec.backend.model}"]
        args += ["--env", f"ANTHROPIC_DEFAULT_OPUS_MODEL={spec.backend.opus_model}"]
        args += ["--env", f"ANTHROPIC_DEFAULT_SONNET_MODEL={spec.backend.sonnet_model}"]
        args += ["--env", f"ANTHROPIC_DEFAULT_HAIKU_MODEL={spec.backend.haiku_model}"]
        args += ["--env", f"CLAUDE_CODE_SUBAGENT_MODEL={spec.backend.subagent_model}"]
        args += ["--env", f"CLAUDE_CODE_EFFORT_LEVEL={spec.backend.effort_level}"]

    # Non-secret: traffic control and image reference
    args += ["--env", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"]
    args += ["--env", f"ADDA_DEV_RUNTIME_IMAGE={spec.image}"]

    if spec.issue_id is not None:
        args += ["--env", f"ISSUE_ID={spec.issue_id}"]

    return tuple(args), env


def _build_tmpfs_args(spec: ContractSpec) -> tuple[str, ...]:
    tail = f"mode={TMPFS_MODE},uid={CONTAINER_UID},gid={CONTAINER_GID}"
    run_opts = f"rw,nosuid,nodev,noexec,size={RUN_TMPFS_SIZE},{tail}"
    return (
        "--tmpfs",
        f"/workspace:rw,exec,nosuid,nodev,size={spec.tmpfs.workspace},{tail}",
        "--tmpfs",
        f"/tmp:rw,exec,nosuid,nodev,size={spec.tmpfs.tmp},{tail}",
        "--tmpfs",
        f"/home/{CONTAINER_USERNAME}:rw,exec,nosuid,nodev,size={spec.tmpfs.home},{tail}",
        "--tmpfs",
        f"/run:{run_opts}",
    )


class DockerContractTranslator(ContractTranslator):
    """Translates a ContractSpec into Docker CLI flags and subprocess env (ContractProcessParams)."""

    def translate(self, spec: ContractSpec) -> ContractProcessParams:
        tz = _detect_tz()
        env_args, secrets = _build_env_args(spec, tz)
        tmpfs_args = _build_tmpfs_args(spec)
        hardening_args = (
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--network",
            "none",
        )
        return ContractProcessParams(args=env_args + tmpfs_args + hardening_args, env=secrets)
