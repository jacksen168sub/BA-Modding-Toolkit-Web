# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub
#
# Tests for the vendored kernel filename parser (app/services/naming.py).

import pytest

from app.services.naming import (
    parse_filename,
    display_name_from_core,
    get_category_prefix,
)
from app.routers.tasks import extract_character_name, _extract_character_from_filename


# (filename, expected core)
CORE_CASES = [
    # Modern JP format: res_type is the numeric token after the date.
    (
        "assets-_mx-spinecharacters-ch0808_spr-mxdependency-textures-2077-08-08_12345678.bundle",
        "ch0808_spr",
    ),
    # Legacy JP format: res_type is a text token before the date.
    (
        "assets-_mx-spinecharacters-ch0808_spr-_mxprolog-2024-11-18_textures_12345678.bundle",
        "ch0808_spr",
    ),
    (
        "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all_793614109.bundle",
        "yuuka_home",
    ),
    # New in v2.9.2: the prologgroup- preload prefix and the npcs category.
    (
        "prologgroup-assets-_mx-npcs-shun_spr-_mxprolog-2025-01-02_textures_11111111.bundle",
        "shun_spr",
    ),
    # New in v2.9.2: the _home_gl suffix must survive parsing.
    (
        "assets-_mx-spinelobbies-ch0808_home_gl-_mxload-2025-03-04_001_assets_22222222.bundle",
        "ch0808_home_gl",
    ),
    (
        "assets-_mx-characters-ch0808-_mxdependency-2024-01-01_003_assets_33333333.bundle",
        "ch0808",
    ),
    # Scatter asset without a date.
    ("ch0808_spr.skel", "ch0808_spr"),
]


@pytest.mark.parametrize("filename,expected_core", CORE_CASES)
def test_parse_filename_core(filename, expected_core):
    assert parse_filename(filename).core == expected_core


def test_parse_filename_modern_keeps_full_core():
    """Regression: the old regexes hard-required `-_mxdependency` (leading underscore)
    and returned the whole stem for the `-mxdependency` (hyphen) form."""
    parsed = parse_filename(
        "assets-_mx-spinecharacters-ch0808_spr-mxdependency-textures-2077-08-08_12345678.bundle"
    )
    assert parsed.category == "spinecharacters"
    assert parsed.core == "ch0808_spr"
    assert parsed.res_type == "textures"
    assert parsed.date == "2077-08-08"
    assert parsed.crc == "12345678"


def test_parse_filename_prologgroup_npcs_category():
    parsed = parse_filename(
        "prologgroup-assets-_mx-npcs-shun_spr-_mxprolog-2025-01-02_textures_11111111.bundle"
    )
    assert parsed.category == "npcs"
    assert parsed.core == "shun_spr"


def test_parse_filename_home_gl_suffix_preserved():
    parsed = parse_filename(
        "assets-_mx-spinelobbies-ch0808_home_gl-_mxload-2025-03-04_001_assets_22222222.bundle"
    )
    assert parsed.core == "ch0808_home_gl"


@pytest.mark.parametrize(
    "core,expected",
    [
        ("ch0808_spr", "ch0808(spr)"),
        ("yuuka_home", "yuuka(home)"),
        ("ch0808", "ch0808"),
    ],
)
def test_display_name_from_core(core, expected):
    assert display_name_from_core(core) == expected


@pytest.mark.parametrize(
    "core,expected_prefix",
    [
        ("ch0808_spr", "assets-_mx-spinecharacters-"),
        ("yuuka_home", "assets-_mx-spinelobbies-"),
        ("ch0808_home_gl", "assets-_mx-spinelobbies-"),
        ("ch0808", "assets-_mx-characters-"),
    ],
)
def test_get_category_prefix(core, expected_prefix):
    assert get_category_prefix(core) == expected_prefix


# --- router helpers that delegate to the vendored parser ---

@pytest.mark.parametrize(
    "filename,expected",
    [
        (
            "assets-_mx-spinecharacters-ch0808_spr-mxdependency-textures-2077-08-08_12345678.bundle",
            "ch0808(spr)",
        ),
        (
            "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all_793614109.bundle",
            "yuuka(home)",
        ),
    ],
)
def test_extract_character_name(filename, expected):
    assert extract_character_name(filename) == expected


def test_extract_character_name_returns_unknown_without_mx_marker():
    assert extract_character_name("plain_file.bundle") == "unknown"
    assert extract_character_name("") == "unknown"


def test_extract_character_from_filename_returns_core():
    assert (
        _extract_character_from_filename(
            "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all_793614109.bundle"
        )
        == "yuuka_home"
    )
