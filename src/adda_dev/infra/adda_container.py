"""
AddaPrimaryContainerImpl adapter: pulls and runs the primary ADDA container, with guarded teardown.
"""

from ..common import Output
from ..domain.adda_container import AddaPrimaryContainer, ContainerError
from ..domain.contract import ContractSpec, ContractTranslator
from ..domain.session import Session
from ..domain.window import Window
from .container import ContainerEngine
from .process import CapturedOutputRunner
from .window import WindowedRunner


class AddaPrimaryContainerImpl(AddaPrimaryContainer):
    """AddaPrimaryContainer adapter that drives a ContainerEngine to pull and run the ADDA container."""

    def __init__(
        self,
        engine: ContainerEngine,
        translator: ContractTranslator,
        output: Output,
        cmd_override: tuple[str, ...] = (),
    ) -> None:
        self._engine = engine
        self._translator = translator
        self._output = output
        self._cmd_override = cmd_override
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
                handle = self._engine.pull(self._pull_runner, spec.image)
                if handle.wait() != 0:
                    raise ContainerError("Pull failed", stdout=handle.stdout().strip(), stderr=handle.stderr().strip())
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
