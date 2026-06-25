"""Tests for adda_dev.cli."""

from typer.testing import CliRunner

from adda_dev.cli import app

runner = CliRunner()


def test_run_no_args() -> None:
    """adda-dev run with no arguments exits 0."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0


def test_run_with_issue_id() -> None:
    """adda-dev run with an issue id exits 0."""
    result = runner.invoke(app, ["run", "42"])
    assert result.exit_code == 0
