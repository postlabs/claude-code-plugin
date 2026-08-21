"""Tests for _common.box_issues — the shared box.yaml completeness gate.

One rule, three callers: offline_validate (build step), dough_publish (user
doughs) and kit_lifecycle install (kit flours). The engine's own rule covers
`en` per-key only and is skipped entirely when box.yaml is absent, which is
exactly the hole these tests pin shut.
"""
from __future__ import annotations

from _common import box_issues

DOUGH = {
    "id": "user.greeter",
    "inputs": {"topic": {"type": "string"}},
    "outputs": {"greeting": {"type": "string"}},
}


def _locale(name="Greeter", about="says hi", in_name="Topic", in_desc="what to greet",
            out_name="Greeting", out_desc="the produced line"):
    return {
        "name": name,
        "about": about,
        "inputs": {"topic": {"name": in_name, "description": in_desc}},
        "outputs": {"greeting": {"name": out_name, "description": out_desc}},
    }


def _complete():
    return {"en": _locale(), "ko": _locale(name="인사", about="인사말을 만든다")}


def codes(issues):
    return [i["code"] for i in issues]


def test_complete_box_passes():
    assert box_issues(DOUGH, _complete()) == []


def test_missing_file_is_a_single_actionable_issue():
    issues = box_issues(DOUGH, None)
    assert codes(issues) == ["box_missing"]
    # not a cascade of per-key noise behind an absent file
    assert "CREATION ONLY" in issues[0]["hint"]


def test_non_mapping_box_is_reported_not_crashed():
    assert codes(box_issues(DOUGH, ["en"])) == ["box_not_mapping"]


def test_en_only_box_fails_on_ko():
    issues = box_issues(DOUGH, {"en": _locale()})
    assert codes(issues) == ["box_locale_missing"]
    assert "`ko:`" in issues[0]["message"]


def test_ko_only_box_fails_on_en():
    issues = box_issues(DOUGH, {"ko": _locale()})
    assert codes(issues) == ["box_locale_missing"]
    assert "`en:`" in issues[0]["message"]


def test_locale_name_and_about_are_both_required():
    box = _complete()
    box["ko"]["name"] = ""
    del box["en"]["about"]
    assert sorted(codes(box_issues(DOUGH, box))) == [
        "box_about_missing", "box_name_missing"]


def test_per_key_labels_are_required_in_every_locale():
    box = _complete()
    del box["ko"]["inputs"]["topic"]["description"]
    box["en"]["outputs"]["greeting"]["name"] = "   "
    assert sorted(codes(box_issues(DOUGH, box))) == [
        "box_input_description_missing", "box_output_label_missing"]


def test_keys_absent_from_the_box_are_reported_per_locale():
    box = {"en": {"name": "G", "about": "a"}, "ko": {"name": "ㄱ", "about": "ㅇ"}}
    # topic + greeting, name + description, in en + ko
    assert len(box_issues(DOUGH, box)) == 8


def test_legacy_flat_string_entry_counts_as_a_name_only():
    """The engine normalizes `key: <label>` to {name: <label>}; so do we —
    the entry supplies the label but still owes a description."""
    box = _complete()
    box["en"]["inputs"]["topic"] = "Topic"
    assert codes(box_issues(DOUGH, box)) == ["box_input_description_missing"]


def test_dough_with_no_inputs_or_outputs_only_needs_locale_text():
    assert box_issues({"id": "user.x"}, {"en": {"name": "X", "about": "does x"},
                                         "ko": {"name": "엑스", "about": "엑스"}}) == []


def test_locales_are_overridable_for_callers_with_a_different_policy():
    assert box_issues(DOUGH, {"en": _locale()}, locales=("en",)) == []
