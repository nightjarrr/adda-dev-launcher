"""
Tests for adda_dev.infra.adda_container: AddaPrimaryContainerImpl.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adda_dev.domain.contract import ContractProcessParams, ContractSpec, ContractTranslator
from adda_dev.domain.session import Session
from adda_dev.domain.window import Window
from adda_dev.infra.adda_container import AddaPrimaryContainerImpl
from adda_dev.infra.process import ProcessHandle, ProcessRunError, ProcessRunner
from adda_dev.infra.window import WindowedRunner
from tests.conftest import FakeContainerEngine, FakeOutput

_TEST_SESSION_ID = "adda-dev-session-test1234"
_TEST_IMAGE = "ghcr.io/nightjarrr/adda-dev:v0.1.0"


def _make_session() -> Session:
    return Session(
        session_id=_TEST_SESSION_ID,
        project_name="p",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        runtime_dir=Path("/tmp/fake-session"),
        issue_id=None,
    )


def _make_spec() -> ContractSpec:
    from adda_dev.domain.github import GitHub
    from adda_dev.domain.llm import AnthropicProvider
    from adda_dev.domain.tmpfs import TmpfsSizes
    from tests.conftest import FakeSecretSource

    source = FakeSecretSource({("adda-dev:github", "gh-token"): "ghp_test", ("adda-dev:anthropic", "key"): "sk_test"})
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    provider = AnthropicProvider(secret_name="key", source=source)
    return ContractSpec(
        github=gh,
        provider=provider,
        image=_TEST_IMAGE,
        tmpfs=TmpfsSizes(),
        proxy_socket_host_path=Path("/tmp/fake-proxy.sock"),
    )


class _FakeHandle(ProcessHandle):
    def __init__(self) -> None:
        super().__init__([])

    def wait(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def stdout(self) -> str:
        return ""

    def stderr(self) -> str:
        return ""


class _FakeWindow(Window):
    """Window test double that records open/attach/close calls without running real processes."""

    def open(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        pass

    def attach(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FixedTranslator(ContractTranslator):
    """ContractTranslator that returns a fixed set of args and env."""

    def __init__(self, args: tuple[str, ...] = ("--fixed-arg",), env: dict[str, str] | None = None) -> None:
        self._params = ContractProcessParams(args=args, env=env or {"KEY": "val"})
        self.translate_calls: list[ContractSpec] = []

    def translate(self, spec: ContractSpec) -> ContractProcessParams:
        self.translate_calls.append(spec)
        return self._params


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl.start — engine calls
# ---------------------------------------------------------------------------


def test_addaprimarycontainer_start_calls_pull_with_spec_image() -> None:
    engine = FakeContainerEngine()
    translator = _FixedTranslator()
    impl = AddaPrimaryContainerImpl(engine, translator, FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    pull_calls = [c for c in engine.calls if c[0] == "pull"]
    assert len(pull_calls) == 1
    assert pull_calls[0][1] == _TEST_IMAGE


def test_addaprimarycontainer_start_calls_run_it() -> None:
    engine = FakeContainerEngine()
    translator = _FixedTranslator()
    impl = AddaPrimaryContainerImpl(engine, translator, FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    run_it_calls = [c for c in engine.calls if c[0] == "run_it"]
    assert len(run_it_calls) == 1


def test_addaprimarycontainer_start_run_it_name_equals_session_id() -> None:
    engine = FakeContainerEngine()
    translator = _FixedTranslator()
    impl = AddaPrimaryContainerImpl(engine, translator, FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    run_it_calls = [c for c in engine.calls if c[0] == "run_it"]
    _image, name, _args, _env, _cmd, _remove = run_it_calls[0][1]  # type: ignore[misc]
    assert name == _TEST_SESSION_ID


def test_addaprimarycontainer_start_run_it_remove_is_true() -> None:
    engine = FakeContainerEngine()
    translator = _FixedTranslator()
    impl = AddaPrimaryContainerImpl(engine, translator, FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    run_it_calls = [c for c in engine.calls if c[0] == "run_it"]
    _image, _name, _args, _env, _cmd, remove = run_it_calls[0][1]  # type: ignore[misc]
    assert remove is True


def test_addaprimarycontainer_start_run_it_uses_translator_args_and_env() -> None:
    engine = FakeContainerEngine()
    translator = _FixedTranslator(args=("--custom-arg", "--other"), env={"SECRET": "s"})
    impl = AddaPrimaryContainerImpl(engine, translator, FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    run_it_calls = [c for c in engine.calls if c[0] == "run_it"]
    _image, _name, args, env, _cmd, _remove = run_it_calls[0][1]  # type: ignore[misc]
    assert args == ["--custom-arg", "--other"]
    assert env == {"SECRET": "s"}


def test_addaprimarycontainer_start_calls_translate_with_spec() -> None:
    engine = FakeContainerEngine()
    translator = _FixedTranslator()
    impl = AddaPrimaryContainerImpl(engine, translator, FakeOutput())
    spec = _make_spec()
    impl.start(_make_session(), spec, _FakeWindow("w"))
    assert len(translator.translate_calls) == 1
    assert translator.translate_calls[0] is spec


def test_addaprimarycontainer_start_wraps_window_in_windowed_runner() -> None:
    """start() must wrap the caller's Window in a WindowedRunner and pass it to engine.run_it."""
    fake_window = _FakeWindow("w")
    captured_runners: list[ProcessRunner] = []

    class _CapturingEngine(FakeContainerEngine):
        def run_it(  # type: ignore[override]
            self,
            runner: ProcessRunner,
            image: str,
            name: str,
            args: list[str],
            env: dict[str, str] | None = None,
            cmd: list[str] | None = None,
            remove: bool = False,
        ) -> ProcessHandle:
            captured_runners.append(runner)
            self.calls.append(("run_it", (image, name, args, env, cmd, remove)))
            return _FakeHandle()

    engine = _CapturingEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.start(_make_session(), _make_spec(), fake_window)
    assert len(captured_runners) == 1
    assert isinstance(captured_runners[0], WindowedRunner)
    assert captured_runners[0]._window is fake_window


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl.stop — before start
# ---------------------------------------------------------------------------


def test_addaprimarycontainer_stop_before_start_is_noop() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.stop()  # must not raise; _name is None
    assert not any(c[0] in ("stop", "rm") for c in engine.calls)


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl.stop — after start
# ---------------------------------------------------------------------------


def test_addaprimarycontainer_stop_after_start_calls_stop_then_rm() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    impl.stop()
    ops = [c[0] for c in engine.calls]
    assert "stop" in ops
    assert "rm" in ops


def test_addaprimarycontainer_stop_rm_uses_force_true() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    impl.stop()
    rm_calls = [c for c in engine.calls if c[0] == "rm"]
    assert rm_calls
    name, force = rm_calls[0][1]  # type: ignore[misc]
    assert force is True
    assert name == _TEST_SESSION_ID


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl.stop — exception swallowing
# ---------------------------------------------------------------------------


class _RaisingStopEngine(FakeContainerEngine):
    """Engine whose stop() raises; rm() succeeds."""

    def stop(self, runner: ProcessRunner, name: str) -> ProcessHandle:  # type: ignore[override]
        raise RuntimeError("stop failed")


class _RaisingRmEngine(FakeContainerEngine):
    """Engine whose stop() succeeds but rm() raises."""

    def rm(self, runner: ProcessRunner, name: str, force: bool = False) -> ProcessHandle:  # type: ignore[override]
        raise RuntimeError("rm failed")


def test_addaprimarycontainer_stop_swallows_stop_exception() -> None:
    impl = AddaPrimaryContainerImpl(_RaisingStopEngine(), _FixedTranslator(), FakeOutput())
    impl._name = _TEST_SESSION_ID  # set name directly to skip start()
    impl.stop()  # must not raise


def test_addaprimarycontainer_stop_swallows_rm_exception() -> None:
    impl = AddaPrimaryContainerImpl(_RaisingRmEngine(), _FixedTranslator(), FakeOutput())
    impl._name = _TEST_SESSION_ID  # set name directly to skip start()
    impl.stop()  # must not raise


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl — cmd_override
# ---------------------------------------------------------------------------


def test_addaprimarycontainer_cmd_override_forwarded_to_run_it() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput(), cmd_override=("echo", "hi"))
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    run_it_calls = [c for c in engine.calls if c[0] == "run_it"]
    _image, _name, _args, _env, cmd, _remove = run_it_calls[0][1]  # type: ignore[misc]
    assert cmd == ["echo", "hi"]


def test_addaprimarycontainer_cmd_default_is_none_in_run_it() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    run_it_calls = [c for c in engine.calls if c[0] == "run_it"]
    _image, _name, _args, _env, cmd, _remove = run_it_calls[0][1]  # type: ignore[misc]
    assert cmd is None


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl — :local image pull skip
# ---------------------------------------------------------------------------


def _make_local_spec() -> ContractSpec:
    from adda_dev.domain.github import GitHub
    from adda_dev.domain.llm import AnthropicProvider
    from adda_dev.domain.tmpfs import TmpfsSizes
    from tests.conftest import FakeSecretSource

    source = FakeSecretSource({("adda-dev:github", "gh-token"): "ghp_test", ("adda-dev:anthropic", "key"): "sk_test"})
    gh = GitHub(owner="nightjarrr", repo="adda-dev-launcher", secret_name="gh-token", source=source)
    provider = AnthropicProvider(secret_name="key", source=source)
    return ContractSpec(
        github=gh,
        provider=provider,
        image="ghcr.io/nightjarrr/adda-dev:local",
        tmpfs=TmpfsSizes(),
        proxy_socket_host_path=Path("/tmp/fake-proxy.sock"),
    )


def test_addaprimarycontainer_start_skips_pull_for_local_image() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.start(_make_session(), _make_local_spec(), _FakeWindow("w"))
    pull_calls = [c for c in engine.calls if c[0] == "pull"]
    assert len(pull_calls) == 0


def test_addaprimarycontainer_start_emits_step_for_local_image() -> None:
    engine = FakeContainerEngine()
    output = FakeOutput()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), output)
    impl.start(_make_session(), _make_local_spec(), _FakeWindow("w"))
    assert any(label == "ADDA Dev Runtime" and detail is not None and "local" in detail for label, detail in output.step_calls)


def test_addaprimarycontainer_start_pulls_for_non_local_image() -> None:
    engine = FakeContainerEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    pull_calls = [c for c in engine.calls if c[0] == "pull"]
    assert len(pull_calls) == 1
    assert pull_calls[0][1] == _TEST_IMAGE


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl — pull failure
# ---------------------------------------------------------------------------


class _FailingPullHandle(_FakeHandle):
    def wait(self) -> int:
        return 1

    def stderr(self) -> str:
        return "manifest unknown"


class _FailingPullEngine(FakeContainerEngine):
    """Engine whose pull() returns a handle with non-zero exit code."""

    def pull(self, runner: ProcessRunner, image: str) -> ProcessHandle:  # type: ignore[override]
        self.calls.append(("pull", image))
        return _FailingPullHandle()


def test_addaprimarycontainer_start_raises_process_run_error_on_pull_failure() -> None:
    engine = _FailingPullEngine()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), FakeOutput())
    with pytest.raises(ProcessRunError) as exc_info:
        impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    assert _TEST_IMAGE in str(exc_info.value.args[0])


# ---------------------------------------------------------------------------
# AddaPrimaryContainerImpl.exec_interactive_shell
# ---------------------------------------------------------------------------


class _RunningInspectHandle(_FakeHandle):
    """ProcessHandle whose stdout() returns a container Running=true JSON payload."""

    def stdout(self) -> str:
        import json

        return json.dumps([{"State": {"Running": True}}])


class _RunningInspectEngine(FakeContainerEngine):
    """Engine that reports the container as running on inspect."""

    def inspect(self, runner: ProcessRunner, name: str) -> _RunningInspectHandle:  # type: ignore[override]
        self.calls.append(("inspect", name))
        return _RunningInspectHandle()


def test_addaprimarycontainerimpl_exec_interactive_shell_calls_exec_it_when_running() -> None:
    from adda_dev.infra.adda_container import _INTERACTIVE_SHELL_CMD

    engine = _RunningInspectEngine()
    output = FakeOutput()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), output, sleep=lambda _: None)
    impl.start(_make_session(), _make_spec(), _FakeWindow("w"))
    impl.exec_interactive_shell(_FakeWindow("shell"))
    exec_it_calls = [c for c in engine.calls if c[0] == "exec_it"]
    assert len(exec_it_calls) == 1
    name, cmd = exec_it_calls[0][1]  # type: ignore[misc]
    assert name == _TEST_SESSION_ID
    assert cmd == [_INTERACTIVE_SHELL_CMD]
    assert ("ADDA Dev Runtime shell", "ready") in output.step_calls


def test_addaprimarycontainerimpl_exec_interactive_shell_before_start_is_noop() -> None:
    engine = _RunningInspectEngine()
    output = FakeOutput()
    impl = AddaPrimaryContainerImpl(engine, _FixedTranslator(), output, sleep=lambda _: None)
    impl.exec_interactive_shell(_FakeWindow("shell"))
    exec_it_calls = [c for c in engine.calls if c[0] == "exec_it"]
    assert len(exec_it_calls) == 0
    assert output.step_calls == []
