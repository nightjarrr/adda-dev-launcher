"""
RichOutput: Rich-backed implementation of the Output port.
"""

from rich.console import Console


# Typer creates its own Console instances internally via rich_utils._get_rich_console()
# with no injection point, so this Console cannot be shared with Typer's rendering.
# The divergence is cosmetic only — no content loss or terminal-state conflicts in a
# sequential CLI. If Rich Live or Progress displays are added later, coordination with
# Typer's output will be needed.
class RichOutput:
    def __init__(self) -> None:
        self._console = Console()

    def info(self, message: str) -> None:
        self._console.print(message)

    def warning(self, message: str) -> None:
        self._console.print(f"[yellow]Warning:[/yellow] {message}")

    def error(self, exc: Exception) -> None:
        self._console.print(f"[red]Error:[/red] {exc}")
