"""
AddaPrimaryContainerImpl adapter: pulls and runs the primary ADDA container, with guarded teardown.
"""

import json
import time
from collections.abc import Callable

from ..common import Output
from ..domain.adda_container import AddaPrimaryContainer
from ..domain.contract import ContractSpec, ContractTranslator
from ..domain.session import Session
from ..domain.window import Window
from .container import ContainerEngine
from .process import CapturedOutputRunner
from .window import WindowedRunner

_INTERACTIVE_SHELL_CMD = "/usr/local/libexec/adda-dev-runtime/bootstrap/open-interactive-shell.sh"
_CONTAINER_READY_ATTEMPTS = 300  # 30 s at 100 ms intervals
_CONTAINER_READY_INTERVAL_S = 0.1


class AddaPrimaryContainerImpl(AddaPrimaryContainer):
    """AddaPrimaryContainer adapter that drives a ContainerEngine to pull and run the ADDA container."""

    def __init__(
        self,
        engine: ContainerEngine,
        translator: ContractTranslator,
        output: Output,
        cmd_override: tuple[str, ...] = (),
        sleep: Callable[[float], object] = time.sleep,
    ) -> None:
        self._engine = engine
        self._translator = translator
        self._output = output
        self._cmd_override = cmd_override
        self._sleep = sleep
        self._pull_runner = CapturedOutputRunner()
        self._teardown_runner = CapturedOutputRunner()
        self._name: str | None = None

    # Public methods

    def start(self, session: Session, spec: ContractSpec, window: Window) -> None:
        """Translate spec, pull the image if needed, and run the container interactively into the given window."""
        # Set name first so stop() covers post-start failures
        self._name = session.session_id
        params = self._translator.translate(spec)
        with self._output.step("ADDA Dev Runtime") as s:
            if spec.image.endswith(":local"):
                s.done(f"local {spec.image}")
            else:
                self._engine.pull(self._pull_runner, spec.image).raise_if_failed(f"Pulling {spec.image} failed")
                s.done(f"pulled {spec.image}")
        self._engine.run_it(
            WindowedRunner(window),
            spec.image,
            session.session_id,
            list(params.args),
            params.env,
            cmd=list(self._cmd_override) or None,
            remove=True,
        )

    def stop(self) -> None:
        """Stop and remove the primary container, best-effort."""
        if self._name is None:
            return
        name = self._name
        try:
            with self._output.step("ADDA Dev Runtime") as s:
                self._engine.stop(self._teardown_runner, name).wait()
                s.done("stopped")
        except Exception:  # noqa: BLE001
            pass
        try:
            self._engine.rm(self._teardown_runner, name, force=True).wait()
        except Exception:  # noqa: BLE001
            pass

    def exec_interactive_shell(self, window: Window) -> None:
        """Open an interactive shell in the running container into the given window."""
        if self._name is None:
            return
        with self._output.step("ADDA Dev Runtime shell") as s:
            self._wait_for_running(self._name)
            self._engine.exec_it(WindowedRunner(window), self._name, [_INTERACTIVE_SHELL_CMD])
            s.done("ready")

    # Private methods

    def _wait_for_running(self, name: str) -> None:
        """Poll inspect until the container reports Running=true or attempts are exhausted."""
        for _ in range(_CONTAINER_READY_ATTEMPTS):
            handle = self._engine.inspect(self._teardown_runner, name)
            if handle.wait() == 0:
                try:
                    data = json.loads(handle.stdout())
                    state = data[0].get("State", {}) if isinstance(data, list) and data else {}
                    if state.get("Running", False):
                        return
                except Exception:  # noqa: BLE001
                    pass
            self._sleep(_CONTAINER_READY_INTERVAL_S)
