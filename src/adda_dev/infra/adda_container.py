"""
AddaPrimaryContainerImpl adapter: pulls and runs the primary ADDA container, with guarded teardown.
"""

from ..domain.adda_container import AddaPrimaryContainer
from ..domain.contract import ContractSpec, ContractTranslator
from ..domain.session import Session
from ..domain.window import Window
from .container import ContainerEngine
from .process import CapturedOutputRunner, DefaultRunner
from .window import WindowedRunner


class AddaPrimaryContainerImpl(AddaPrimaryContainer):
    """AddaPrimaryContainer adapter that drives a ContainerEngine to pull and run the ADDA container."""

    def __init__(self, engine: ContainerEngine, translator: ContractTranslator) -> None:
        self._engine = engine
        self._translator = translator
        self._pull_runner = DefaultRunner()
        self._teardown_runner = CapturedOutputRunner()
        self._name: str | None = None

    # Public methods

    def start(self, session: Session, spec: ContractSpec, window: Window) -> None:
        """Translate spec, pull the image, and run the container interactively into the given window."""
        # Set name first so stop() covers post-start failures
        self._name = session.session_id
        params = self._translator.translate(spec)
        self._engine.pull(self._pull_runner, spec.image).wait()
        self._engine.run_it(WindowedRunner(window), spec.image, session.session_id, list(params.args), params.env, remove=True)

    def stop(self) -> None:
        """Stop and remove the primary container, best-effort."""
        if self._name is None:
            return
        name = self._name
        try:
            self._engine.stop(self._teardown_runner, name).wait()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._engine.rm(self._teardown_runner, name, force=True).wait()
        except Exception:  # noqa: BLE001
            pass
