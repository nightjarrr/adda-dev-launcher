"""
Envoy sidecar adapter: renders config, manages the Envoy container lifecycle.
"""

import importlib.resources
import json
import os
import time
from pathlib import Path, PurePosixPath

from ..common import Output
from ..domain.container import ContainerEngine
from ..domain.process import ProcessRunner
from ..domain.proxy import ProxyError, ProxySidecar

# Single source of truth for the Envoy-internal socket path.
ENVOY_SOCKET_CONTAINER_PATH: str = "/run/adda-dev-proxy/proxy.sock"

_ENVOY_SOCKET_CONTAINER_DIR: str = str(PurePosixPath(ENVOY_SOCKET_CONTAINER_PATH).parent)
_ENVOY_SOCKET_FILENAME: str = PurePosixPath(ENVOY_SOCKET_CONTAINER_PATH).name

_ENVOY_CONFIG_CONTAINER_PATH: str = "/etc/adda-dev/envoy.yaml"
_ENVOY_TMPFS_SPEC: str = "rw,nosuid,nodev,noexec,size=16m"

_POLL_ATTEMPTS: int = 100
_POLL_INTERVAL_S: float = 0.1


def render_envoy_config(socket_container_path: str) -> str:
    """Read the bundled Envoy config template and substitute the socket path placeholder."""
    template_ref = importlib.resources.files("adda_dev") / "data" / "envoy.yaml.template"
    template = template_ref.read_text(encoding="utf-8")
    return template.replace("__ENVOY_SOCKET_PATH__", socket_container_path)


class EnvoySidecar(ProxySidecar):
    """ProxySidecar adapter that starts an Envoy container as the egress proxy."""

    def __init__(
        self,
        engine: ContainerEngine,
        runner: ProcessRunner,
        envoy_image: str,
        output: Output,
        *,
        sleep: object = time.sleep,
        attempts: int = _POLL_ATTEMPTS,
        interval: float = _POLL_INTERVAL_S,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._envoy_image = envoy_image
        self._output = output
        self._sleep = sleep
        self._attempts = attempts
        self._interval = interval
        self._container_name: str | None = None

    # Public methods

    def start(self, runtime_dir: Path) -> Path:
        """Start the Envoy sidecar and return the host socket path when Envoy is ready."""
        socket_dir = runtime_dir / "proxy_socket"
        socket_dir.mkdir(mode=0o700)

        config_text = render_envoy_config(ENVOY_SOCKET_CONTAINER_PATH)
        config_path = runtime_dir / "envoy.yaml"
        config_path.write_text(config_text, encoding="utf-8")
        config_path.chmod(0o600)

        host_socket = socket_dir / _ENVOY_SOCKET_FILENAME

        self._engine.pull(self._runner, self._envoy_image).wait()

        name = f"adda-dev-envoy-{runtime_dir.name}"
        args = self._build_args(socket_dir, config_path)
        cmd = ["-c", _ENVOY_CONFIG_CONTAINER_PATH]

        handle = self._engine.run_d(self._runner, self._envoy_image, name, args, cmd=cmd, remove=False)
        if handle.wait() != 0:
            raise ProxyError(f"Envoy container failed to start: {handle.stderr().strip()}")
        self._container_name = name

        return self._poll_ready(host_socket)

    def stop(self) -> None:
        """Stop and remove the Envoy container, best-effort."""
        if self._container_name is None:
            return
        name = self._container_name
        try:
            self._engine.stop(self._runner, name).wait()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._engine.rm(self._runner, name, force=True).wait()
        except Exception:  # noqa: BLE001
            pass

    # Private methods

    def _build_args(self, socket_dir: Path, config_path: Path) -> list[str]:
        """Build Docker run arguments for the Envoy container."""
        return [
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            f"/tmp:{_ENVOY_TMPFS_SPEC}",
            "--mount",
            f"type=bind,source={config_path},target={_ENVOY_CONFIG_CONTAINER_PATH},readonly",
            "--mount",
            f"type=bind,source={socket_dir},target={_ENVOY_SOCKET_CONTAINER_DIR}",
        ]

    def _poll_ready(self, host_socket: Path) -> Path:
        """Poll until the Envoy Unix socket appears, the container exits, or attempts are exhausted."""
        for _ in range(self._attempts):
            if host_socket.is_socket():
                self._output.info("Envoy proxy ready.")
                return host_socket
            if self._container_exited():
                logs = self._capture_logs()
                raise ProxyError(f"Envoy exited before creating the proxy socket\n{logs}")
            self._sleep(self._interval)  # type: ignore[operator]

        logs = self._capture_logs()
        raise ProxyError(f"Proxy socket not ready after {self._attempts} attempts\n{logs}")

    def _container_exited(self) -> bool:
        """Return True if the Envoy container has stopped running."""
        try:
            handle = self._engine.inspect(self._runner, self._container_name or "")
            if handle.wait() != 0:
                return True
            data = json.loads(handle.stdout())
            state = data[0].get("State", {}) if isinstance(data, list) and data else {}
            return not state.get("Running", True)
        except Exception:  # noqa: BLE001
            return True

    def _capture_logs(self) -> str:
        """Capture Envoy container logs; return empty string on failure."""
        try:
            handle = self._engine.logs(self._runner, self._container_name or "")
            handle.wait()
            return handle.stdout() + handle.stderr()
        except Exception:  # noqa: BLE001
            return ""
