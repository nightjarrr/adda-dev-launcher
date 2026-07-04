"""
RichOutput: Rich-backed implementation of the Output port.
"""

import time
from types import TracebackType
from typing import Literal

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from ..common import StepContext

_SPINNER_NAME = "dots"


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
        from rich.panel import Panel

        body = Text()
        body.append(str(exc.args[0]) if exc.args else str(exc))
        if hasattr(exc, "details"):
            for label, content in exc.details:
                body.append(f"\n\n{label}\n", style="dim")
                body.append(content)
        self._console.print(Panel(body, title="[bold red]Error[/bold red]", border_style="red", title_align="left"))

    def blank(self) -> None:
        self._console.print()

    def ruler(self, title: str = "", *, pad: bool = True) -> None:
        if pad:
            self._console.print()
        width = self._console.width or 80
        prefix = "─── "
        if title:
            suffix = " " + "─" * max(0, width - len(prefix) - len(title) - 2)
            t = Text()
            t.append(prefix, style="dim")
            t.append(title, style="bold")
            t.append(suffix, style="dim")
            self._console.print(t)
        else:
            self._console.rule(style="dim")
        if pad:
            self._console.print()

    def kv(self, key: str, value: str | tuple[str, ...]) -> None:
        rendered_value = " · ".join(value) if isinstance(value, tuple) else value
        key_col = (key[:31] + "…") if len(key) > 32 else key.ljust(32)
        width = self._console.width or 80
        # 2 indent + 32 key + 2 separator = 36 chars before value
        max_value_len = width - 36
        if max_value_len > 0 and len(rendered_value) > max_value_len:
            rendered_value = rendered_value[: max_value_len - 1] + "…"
        self._console.print(f"  [bold]{key_col}[/bold]  {rendered_value}", highlight=False)

    def step(self, label: str) -> StepContext:
        return _RichStepContext(label, self._console)


class _RichStepContext(StepContext):
    """Rich Live spinner context manager for a named step."""

    def __init__(self, label: str, console: Console) -> None:
        self._label = label
        self._console = console
        self._t0: float = 0.0
        self._live: Live | None = None
        self._done_called: bool = False

    def __enter__(self) -> _RichStepContext:
        self._t0 = time.monotonic()
        spinner = Spinner(_SPINNER_NAME)

        def _render() -> Text:
            elapsed = time.monotonic() - self._t0
            frame = spinner.render(time.monotonic())
            label_col = (self._label[:31] + "…") if len(self._label) > 32 else self._label.ljust(32)
            t = Text()
            t.append("  ")
            t.append_text(Text.from_markup(f"[green]{frame}[/green]"))
            t.append(f"  {elapsed:>8.1f}s  {label_col}")
            return t

        self._live = Live(
            _render(),
            console=self._console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.__enter__()
        return self

    def done(self, detail: str) -> None:
        self._done_called = True
        elapsed = time.monotonic() - self._t0
        if self._live is not None:
            self._live.__exit__(None, None, None)
            self._live = None
        self._print_row("✓", "green", elapsed, detail)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        if self._done_called:
            # done() already closed Live and printed the row; nothing to do
            return False
        elapsed = time.monotonic() - self._t0
        if self._live is not None:
            self._live.__exit__(exc_type, exc_val, exc_tb)
            self._live = None
        if exc_val is not None:
            detail = str(exc_val.args[0]) if exc_val.args else str(exc_val)
            self._print_row("✗", "red", elapsed, detail)
        return False

    def _print_row(self, mark: str, color: str, elapsed: float, detail: str) -> None:
        width = self._console.width or 80
        label_col = (self._label[:31] + "…") if len(self._label) > 32 else self._label.ljust(32)
        elapsed_str = f"{elapsed:>8.1f}s"
        # 2 indent + 1 mark + 2 sep + 8 elapsed + 2 sep + 32 label + 2 sep = 49 chars before detail
        max_detail = width - 49
        if max_detail > 0 and len(detail) > max_detail:
            detail = detail[: max_detail - 1] + "…"
        t = Text()
        t.append("  ")
        t.append(mark, style=color)
        t.append(f"  {elapsed_str}  {label_col}  {detail}")
        self._console.print(t)
