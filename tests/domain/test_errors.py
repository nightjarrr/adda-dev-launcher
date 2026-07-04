"""
Tests for domain error classes: AddaDevError, ProxyError, ContainerError.
"""

from adda_dev.common import AddaDevError
from adda_dev.domain.adda_container import ContainerError
from adda_dev.domain.proxy import ProxyError

# ---------------------------------------------------------------------------
# AddaDevError — details bag and __str__
# ---------------------------------------------------------------------------


def test_addadeverror_details_empty_by_default() -> None:
    exc = AddaDevError("base message")
    assert exc.details == []


def test_addadeverror_str_message_only_when_no_details() -> None:
    exc = AddaDevError("base message")
    assert str(exc) == "base message"


def test_addadeverror_str_includes_detail_sections() -> None:
    exc = AddaDevError("base message")
    exc.details.append(("label1", "content1"))
    result = str(exc)
    assert "--- label1 ---" in result
    assert "content1" in result


def test_addadeverror_str_multiple_details_all_included() -> None:
    exc = AddaDevError("msg")
    exc.details.append(("a", "alpha"))
    exc.details.append(("b", "beta"))
    result = str(exc)
    assert "--- a ---" in result
    assert "alpha" in result
    assert "--- b ---" in result
    assert "beta" in result


# ---------------------------------------------------------------------------
# ProxyError — details population and __str__
# ---------------------------------------------------------------------------


def test_proxyerror_details_populated_with_stdout_and_stderr() -> None:
    exc = ProxyError("proxy failed", stdout="OUT", stderr="ERR")
    labels = [label for label, _ in exc.details]
    assert "stdout" in labels
    assert "stderr" in labels


def test_proxyerror_details_content_matches_streams() -> None:
    exc = ProxyError("proxy failed", stdout="OUT", stderr="ERR")
    content_map = dict(exc.details)
    assert content_map["stdout"] == "OUT"
    assert content_map["stderr"] == "ERR"


def test_proxyerror_str_includes_stdout_section() -> None:
    exc = ProxyError("proxy failed", stdout="OUT", stderr="ERR")
    result = str(exc)
    assert "--- stdout ---" in result
    assert "OUT" in result


def test_proxyerror_str_includes_stderr_section() -> None:
    exc = ProxyError("proxy failed", stdout="OUT", stderr="ERR")
    result = str(exc)
    assert "--- stderr ---" in result
    assert "ERR" in result


def test_proxyerror_str_message_only_when_no_streams() -> None:
    exc = ProxyError("only message")
    assert str(exc) == "only message"
    assert "stdout" not in str(exc)
    assert "stderr" not in str(exc)


def test_proxyerror_empty_stdout_not_added_to_details() -> None:
    exc = ProxyError("msg", stdout="", stderr="ERR")
    labels = [label for label, _ in exc.details]
    assert "stdout" not in labels
    assert "stderr" in labels


def test_proxyerror_empty_stderr_not_added_to_details() -> None:
    exc = ProxyError("msg", stdout="OUT", stderr="")
    labels = [label for label, _ in exc.details]
    assert "stdout" in labels
    assert "stderr" not in labels


# ---------------------------------------------------------------------------
# ContainerError — details population and __str__
# ---------------------------------------------------------------------------


def test_containererror_details_populated_with_stdout_and_stderr() -> None:
    exc = ContainerError("pull failed", stdout="OUT", stderr="ERR")
    labels = [label for label, _ in exc.details]
    assert "stdout" in labels
    assert "stderr" in labels


def test_containererror_details_content_matches_streams() -> None:
    exc = ContainerError("pull failed", stdout="OUT", stderr="ERR")
    content_map = dict(exc.details)
    assert content_map["stdout"] == "OUT"
    assert content_map["stderr"] == "ERR"


def test_containererror_str_includes_stdout_section() -> None:
    exc = ContainerError("pull failed", stdout="OUT", stderr="ERR")
    result = str(exc)
    assert "--- stdout ---" in result
    assert "OUT" in result


def test_containererror_str_includes_stderr_section() -> None:
    exc = ContainerError("pull failed", stdout="OUT", stderr="ERR")
    result = str(exc)
    assert "--- stderr ---" in result
    assert "ERR" in result


def test_containererror_str_message_only_when_no_streams() -> None:
    exc = ContainerError("only message")
    assert str(exc) == "only message"
    assert "stdout" not in str(exc)
    assert "stderr" not in str(exc)


def test_containererror_empty_stdout_not_added_to_details() -> None:
    exc = ContainerError("msg", stdout="", stderr="ERR")
    labels = [label for label, _ in exc.details]
    assert "stdout" not in labels
    assert "stderr" in labels


def test_containererror_empty_stderr_not_added_to_details() -> None:
    exc = ContainerError("msg", stdout="OUT", stderr="")
    labels = [label for label, _ in exc.details]
    assert "stdout" in labels
    assert "stderr" not in labels


def test_containererror_is_addadeverror() -> None:
    exc = ContainerError("msg")
    assert isinstance(exc, AddaDevError)
