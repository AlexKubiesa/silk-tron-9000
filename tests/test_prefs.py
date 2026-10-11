"""Tests for restoring the prefs that skip the game's first-launch menus."""

import xml.etree.ElementTree as ET

from silk_tron.shared_memory import FIRST_LAUNCH_PREFS, ensure_first_launch_prefs


def read_prefs(path):
    return {
        pref.get("name"): (pref.get("type"), pref.text)
        for pref in ET.parse(path).getroot().iter("pref")
    }


def test_adds_missing_prefs_and_keeps_the_others(tmp_path):
    path = tmp_path / "prefs"
    path.write_text(
        '<unity_prefs version_major="1" version_minor="1">\n'
        '\t<pref name="M2H_lastLanguage" type="string">RU4=</pref>\n'
        '\t<pref name="VidOSSet" type="int">1</pref>\n'
        "</unity_prefs>"
    )

    assert ensure_first_launch_prefs(path)

    prefs = read_prefs(path)
    assert prefs["M2H_lastLanguage"] == ("string", "RU4=")
    for name in FIRST_LAUNCH_PREFS:
        assert prefs[name] == ("int", "1")
    assert ET.parse(path).getroot().get("version_major") == "1"


def test_does_not_write_when_prefs_are_already_set(tmp_path):
    path = tmp_path / "prefs"
    lines = "".join(f'\t<pref name="{name}" type="int">1</pref>\n' for name in FIRST_LAUNCH_PREFS)
    contents = f'<unity_prefs version_major="1" version_minor="1">\n{lines}</unity_prefs>'
    path.write_text(contents)

    assert not ensure_first_launch_prefs(path)
    assert path.read_text() == contents


def test_sets_prefs_that_are_zero(tmp_path):
    path = tmp_path / "prefs"
    path.write_text(
        '<unity_prefs version_major="1" version_minor="1">'
        '<pref name="GameLangSet" type="int">0</pref></unity_prefs>'
    )

    assert ensure_first_launch_prefs(path)
    assert read_prefs(path)["GameLangSet"] == ("int", "1")


def test_replaces_a_missing_or_corrupt_file(tmp_path):
    missing = tmp_path / "missing" / "prefs"
    corrupt = tmp_path / "prefs"
    corrupt.write_text('<unity_prefs version_major="1"><pref name="Vid')

    for path in (missing, corrupt):
        assert ensure_first_launch_prefs(path)
        prefs = read_prefs(path)
        assert set(prefs) == set(FIRST_LAUNCH_PREFS)
    assert not list(tmp_path.glob("*.tmp"))
