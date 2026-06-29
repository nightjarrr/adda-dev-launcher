"""
Tests for tmpfs.py: TmpfsSizes defaults and validation, TmpfsOverride optional fields,
TmpfsSizes.with_override merge logic.
"""

import pytest

from adda_dev.domain.tmpfs import TmpfsOverride, TmpfsSizes

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
# TmpfsSizes.with_override — None override returns self
# ---------------------------------------------------------------------------


def test_tmpfs_sizes_with_override_none_returns_self() -> None:
    sizes = TmpfsSizes(home="1g", workspace="512m", tmp="256m")
    result = sizes.with_override(None)
    assert result is sizes


# ---------------------------------------------------------------------------
# TmpfsSizes.with_override — partial override merges per-field
# ---------------------------------------------------------------------------


def test_tmpfs_sizes_with_override_partial_workspace_only() -> None:
    sizes = TmpfsSizes(home="1g", workspace="512m", tmp="256m")
    override = TmpfsOverride(workspace="2g")
    result = sizes.with_override(override)
    assert result.home == "1g"
    assert result.workspace == "2g"
    assert result.tmp == "256m"


def test_tmpfs_sizes_with_override_partial_home_only() -> None:
    sizes = TmpfsSizes(home="512m", workspace="256m", tmp="128m")
    override = TmpfsOverride(home="4g")
    result = sizes.with_override(override)
    assert result.home == "4g"
    assert result.workspace == "256m"
    assert result.tmp == "128m"


def test_tmpfs_sizes_with_override_partial_tmp_only() -> None:
    sizes = TmpfsSizes(home="512m", workspace="256m", tmp="128m")
    override = TmpfsOverride(tmp="64m")
    result = sizes.with_override(override)
    assert result.home == "512m"
    assert result.workspace == "256m"
    assert result.tmp == "64m"


# ---------------------------------------------------------------------------
# TmpfsSizes.with_override — full override replaces all fields
# ---------------------------------------------------------------------------


def test_tmpfs_sizes_with_override_full() -> None:
    sizes = TmpfsSizes(home="512m", workspace="256m", tmp="256m")
    override = TmpfsOverride(home="2g", workspace="1g", tmp="512m")
    result = sizes.with_override(override)
    assert result.home == "2g"
    assert result.workspace == "1g"
    assert result.tmp == "512m"


def test_tmpfs_sizes_with_override_full_returns_new_instance() -> None:
    sizes = TmpfsSizes()
    override = TmpfsOverride(home="2g", workspace="1g", tmp="512m")
    result = sizes.with_override(override)
    assert result is not sizes


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
