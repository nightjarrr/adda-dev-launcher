"""
Tests for tmpfs.py: TmpfsSizes defaults and validation, TmpfsOverride optional fields.
"""

import pytest

from adda_dev.tmpfs import TmpfsOverride, TmpfsSizes

# ---------------------------------------------------------------------------
# TmpfsSizes — defaults
# ---------------------------------------------------------------------------


def test_tmpfs_sizes_defaults() -> None:
    sizes = TmpfsSizes()
    assert sizes.home == "512m"
    assert sizes.workspace == "256m"
    assert sizes.tmp == "256m"


def test_tmpfs_sizes_custom_values() -> None:
    sizes = TmpfsSizes(home="1g", workspace="512m", tmp="128m")
    assert sizes.home == "1g"
    assert sizes.workspace == "512m"
    assert sizes.tmp == "128m"


# ---------------------------------------------------------------------------
# TmpfsSizes — size format validator (valid values)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "512m",
        "1g",
        "256M",
        "1G",
        "1024k",
        "1024K",
        "2048b",
        "2048B",
        "1024",  # no unit = bytes
        "0",
    ],
)
def test_tmpfs_sizes_valid_size_formats(value: str) -> None:
    sizes = TmpfsSizes(home=value)
    assert sizes.home == value


# ---------------------------------------------------------------------------
# TmpfsSizes — size format validator (invalid values)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "512mb",  # double unit
        "1gb",
        "-1m",  # negative
        "m",  # no digits
        "1 m",  # space
        "1.5g",  # decimal
        "",
    ],
)
def test_tmpfs_sizes_invalid_size_formats(value: str) -> None:
    with pytest.raises(Exception):
        TmpfsSizes(home=value)


# ---------------------------------------------------------------------------
# TmpfsSizes — extra fields rejected
# ---------------------------------------------------------------------------


def test_tmpfs_sizes_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        TmpfsSizes.model_validate({"home": "512m", "workspace": "256m", "tmp": "256m", "extra": "1g"})


# ---------------------------------------------------------------------------
# TmpfsOverride — all optional, defaults to None
# ---------------------------------------------------------------------------


def test_tmpfs_override_all_none() -> None:
    override = TmpfsOverride()
    assert override.home is None
    assert override.workspace is None
    assert override.tmp is None


def test_tmpfs_override_partial() -> None:
    override = TmpfsOverride(workspace="2g")
    assert override.home is None
    assert override.workspace == "2g"
    assert override.tmp is None


def test_tmpfs_override_all_set() -> None:
    override = TmpfsOverride(home="1g", workspace="2g", tmp="512m")
    assert override.home == "1g"
    assert override.workspace == "2g"
    assert override.tmp == "512m"


def test_tmpfs_override_invalid_size_rejected() -> None:
    with pytest.raises(Exception):
        TmpfsOverride(home="1gb")


def test_tmpfs_override_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        TmpfsOverride.model_validate({"home": "512m", "extra": "1g"})
