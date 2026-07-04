"""
Tests for adda_dev.infra.output: RichOutput and _RichStepContext.
"""

import io

import pytest
from rich.console import Console

from adda_dev.infra.output import RichOutput, _RichStepContext


def _make_console() -> tuple[Console, io.StringIO]:
    """Return a Console that writes to a StringIO buffer for inspection."""
    buf = io.StringIO()
    console = Console(file=buf, width=80, highlight=False, markup=False)
    return console, buf


def _make_output() -> tuple[RichOutput, io.StringIO]:
    """Return a RichOutput whose console writes to a StringIO buffer."""
    output = RichOutput.__new__(RichOutput)
    buf = io.StringIO()
    output._console = Console(file=buf, width=80, highlight=False, markup=False)  # type: ignore[attr-defined]
    return output, buf


# ---------------------------------------------------------------------------
# RichOutput — basic methods
# ---------------------------------------------------------------------------


def test_richoutput_init_creates_instance() -> None:
    # Exercises the __init__ path that creates Console()
    output = RichOutput()
    assert output._console is not None  # type: ignore[attr-defined]


def test_richoutput_info_writes_message() -> None:
    output, buf = _make_output()
    output.info("hello world")
    assert "hello world" in buf.getvalue()


def test_richoutput_warning_writes_message() -> None:
    output, buf = _make_output()
    output.warning("watch out")
    assert "watch out" in buf.getvalue()


def test_richoutput_error_writes_exception() -> None:
    output, buf = _make_output()
    output.error(ValueError("bad value"))
    assert "bad value" in buf.getvalue()


def test_richoutput_error_renders_panel_border() -> None:
    output, buf = _make_output()
    output.error(ValueError("something went wrong"))
    # Panel renders with box-drawing characters — check for the title or border chars
    content = buf.getvalue()
    assert "something went wrong" in content


def test_richoutput_error_with_details_renders_label_sections() -> None:
    from adda_dev.common import AddaDevError

    exc = AddaDevError("pull failed")
    exc.details.append(("stdout", "line from stdout"))
    exc.details.append(("stderr", "error line"))
    output, buf = _make_output()
    output.error(exc)
    content = buf.getvalue()
    assert "pull failed" in content
    assert "stdout" in content
    assert "line from stdout" in content
    assert "stderr" in content
    assert "error line" in content


def test_richoutput_error_plain_exception_no_details_section() -> None:
    output, buf = _make_output()
    output.error(RuntimeError("plain error"))
    content = buf.getvalue()
    assert "plain error" in content
    # A plain RuntimeError has no details attribute — no label sections expected
    assert "--- " not in content


def test_richoutput_blank_writes_newline() -> None:
    output, buf = _make_output()
    output.blank()
    # A blank line means the buffer has at least a newline
    assert "\n" in buf.getvalue()


# ---------------------------------------------------------------------------
# RichOutput.ruler
# ---------------------------------------------------------------------------


def test_richoutput_ruler_with_title_emits_title() -> None:
    output, buf = _make_output()
    output.ruler("My Section")
    assert "My Section" in buf.getvalue()


def test_richoutput_ruler_no_title_emits_line() -> None:
    output, buf = _make_output()
    output.ruler()
    # Without title uses console.rule which emits a horizontal line
    assert len(buf.getvalue()) > 0


def test_richoutput_ruler_pad_true_emits_extra_newlines() -> None:
    output, buf = _make_output()
    output.ruler("test", pad=True)
    # pad=True means two extra print() calls (leading + trailing blank)
    content = buf.getvalue()
    assert content.count("\n") >= 3


def test_richoutput_ruler_pad_false_no_extra_newlines() -> None:
    output, buf = _make_output()
    output.ruler("test", pad=False)
    content = buf.getvalue()
    # Only the ruler line itself — fewer newlines than pad=True
    assert content.count("\n") < 3


# ---------------------------------------------------------------------------
# RichOutput.kv
# ---------------------------------------------------------------------------


def test_richoutput_kv_string_value_written() -> None:
    output, buf = _make_output()
    output.kv("Project", "my-project")
    assert "my-project" in buf.getvalue()


def test_richoutput_kv_tuple_value_joined_with_separator() -> None:
    output, buf = _make_output()
    output.kv("Tmpfs", ("home 1g", "tmp 512m"))
    content = buf.getvalue()
    assert "home 1g" in content
    assert "tmp 512m" in content


def test_richoutput_kv_long_key_truncated_with_ellipsis() -> None:
    output, buf = _make_output()
    long_key = "A" * 33
    output.kv(long_key, "val")
    content = buf.getvalue()
    assert "…" in content


def test_richoutput_kv_long_value_truncated_with_ellipsis() -> None:
    output, buf = _make_output()
    # Console width is 80; after key+indent that leaves ~44 chars; use a very long value
    output.kv("Key", "X" * 200)
    content = buf.getvalue()
    assert "…" in content


# ---------------------------------------------------------------------------
# RichOutput.step — returns a context manager
# ---------------------------------------------------------------------------


def test_richoutput_step_returns_step_context() -> None:
    from adda_dev.common import StepContext

    output, _ = _make_output()
    ctx = output.step("my step")
    assert isinstance(ctx, StepContext)


# ---------------------------------------------------------------------------
# _RichStepContext — success path
# ---------------------------------------------------------------------------


def test_richstepcontext_done_prints_check_mark() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with ctx as s:
        s.done("all good")
    assert "✓" in buf.getvalue()


def test_richstepcontext_done_prints_label() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with ctx as s:
        s.done("all good")
    assert "my step" in buf.getvalue()


def test_richstepcontext_done_prints_detail() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with ctx as s:
        s.done("all good")
    assert "all good" in buf.getvalue()


def test_richstepcontext_done_long_label_truncated() -> None:
    console, buf = _make_console()
    long_label = "L" * 40
    ctx = _RichStepContext(long_label, console)
    with ctx as s:
        s.done("detail")
    assert "…" in buf.getvalue()


def test_richstepcontext_done_long_detail_truncated() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with ctx as s:
        s.done("D" * 200)
    assert "…" in buf.getvalue()


def test_richstepcontext_exit_after_done_is_noop() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with ctx as s:
        s.done("done")
    # Only one ✓ should appear (no duplicate output from __exit__)
    assert buf.getvalue().count("✓") == 1


# ---------------------------------------------------------------------------
# _RichStepContext — failure path (exception in body)
# ---------------------------------------------------------------------------


def test_richstepcontext_exception_prints_cross_mark() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with pytest.raises(RuntimeError):
        with ctx:
            raise RuntimeError("boom")
    assert "✗" in buf.getvalue()


def test_richstepcontext_exception_prints_error_message() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    with pytest.raises(RuntimeError):
        with ctx:
            raise RuntimeError("something broke")
    assert "something broke" in buf.getvalue()


def test_richstepcontext_exception_propagates() -> None:
    console, _ = _make_console()
    ctx = _RichStepContext("my step", console)
    with pytest.raises(ValueError, match="propagated"):
        with ctx:
            raise ValueError("propagated")


def test_richstepcontext_exception_uses_args0_not_full_str() -> None:
    # AddaDevError.__str__() returns multi-line text when details are present.
    # __exit__ must print only args[0] (the bare message), not str(exc_val).
    from adda_dev.common import AddaDevError

    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    exc = AddaDevError("bare message")
    exc.details.append(("--- stderr ---", "lots of extra detail"))
    with pytest.raises(AddaDevError):
        with ctx:
            raise exc
    content = buf.getvalue()
    assert "bare message" in content
    # The multi-line detail block must NOT appear in the step row
    assert "lots of extra detail" not in content


# ---------------------------------------------------------------------------
# _RichStepContext — __exit__ without exception and without done()
# ---------------------------------------------------------------------------


def test_richstepcontext_exit_without_exception_no_error_mark() -> None:
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    # Exit cleanly without calling done() — not a typical usage but must not raise
    ctx.__enter__()
    ctx.__exit__(None, None, None)
    assert "✗" not in buf.getvalue()


def test_richstepcontext_done_without_enter_does_not_raise() -> None:
    # Calls done() with _live=None (the False branch of if self._live is not None in done())
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    ctx._t0 = 0.0  # type: ignore[attr-defined]
    ctx.done("result")
    assert "✓" in buf.getvalue()


def test_richstepcontext_exit_without_enter_does_not_raise() -> None:
    # Calls __exit__ with _live=None (the False branch of if self._live is not None in __exit__)
    console, buf = _make_console()
    ctx = _RichStepContext("my step", console)
    ctx._t0 = 0.0  # type: ignore[attr-defined]
    ctx.__exit__(None, None, None)
    # No mark should be printed since there is no exception
    assert "✗" not in buf.getvalue()
