"""adda-dev CLI entry point."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """ADDA Dev Runtime launcher."""


@app.command()
def run(
    issue_id: int | None = typer.Argument(None, help="GitHub issue number to work on"),
) -> None:
    """Start the ADDA Dev Runtime."""
