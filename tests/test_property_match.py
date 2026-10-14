import pytest

from property_match import match, suggest
from test_check_invoices import KEY, check, fake_extract

MY_LABELS = ("Property unclear:", "No property:", "Wrong entity:")


def properties(text):
    return [p for p, _, _ in match(text)]


def my_flags(row):
    """This ticket's Flags only, so the run-level tests do not depend on the other checks."""
    return [f for f in (row["Flags"] or "").split("\n") if f.startswith(MY_LABELS)]


def labels(row):
    return [f[:f.index(":") + 1] for f in (row["Flags"] or "").split("\n") if f]


@pytest.mark.parametrize("file, reason", [
    ("01-clean.pdf", "Matched 'Kowhai House' in Reference, 'Kowhai House' in Site to Kowhai House"),
    ("05-alias.pdf", "Matched '12 Totara St' in Reference, '12 Totara St' in Site to Kowhai House"),
    ("12-job-management.pdf", "Matched 'Kōwhai House' in Site to Kowhai House"),
])
def test_invoice_suggests_the_answer_key_property_with_the_matched_text(tmp_path, file, reason):
    [row] = check(tmp_path, [file])
    assert row["Suggested property"] == KEY.loc[file, "expected_property"]
    assert row["Property reason"] == reason
    assert my_flags(row) == []


def extract_with(**source_text):
    """fake_extract with some fields' source text replaced. line_item=... replaces the first description."""
    def extract(pdf):
        out = fake_extract(pdf)
        for field, text in source_text.items():
            target = out["line_items"][0]["description"] if field == "line_item" else out[field]
            target["source_text"] = text
        return out
    return extract


def test_invoice_1_is_not_matched_to_the_property_in_its_buyer_address(tmp_path):
    # Buyer address is "Level 3, Matai Centre, 40 Rata Road": with Reference and Site blank, nothing matches.
    [row] = check(tmp_path, ["01-clean.pdf"], extract_with(reference=None, site=None))
    assert row["Suggested property"] is None
    assert row["Property reason"] is None
    assert row["Status"] == "Needs you"
    assert my_flags(row) == [
        "No property: no property in properties.csv matches the site text "
        "(searched first line item 'Replace emergency exit lights, level 2')."
    ]


def test_no_site_text_gives_no_property(tmp_path):
    [row] = check(tmp_path, ["01-clean.pdf"], extract_with(reference=None, site=None, line_item=None))
    assert row["Suggested property"] is None
    assert row["Status"] == "Needs you"
    assert my_flags(row) == ["No property: no site text (Reference, Site and first line item are all blank)."]


def test_invoice_17_kowhai_alone_is_property_unclear_listing_the_matches(tmp_path):
    file = "17-ambiguous-property.pdf"
    [row] = check(tmp_path, [file])
    assert row["Status"] == "Needs you"
    assert labels(row) == KEY.loc[file, "expected_flags"].split("; ")
    assert row["Suggested property"] is None
    assert row["Property reason"] is None
    assert my_flags(row) == [
        "Property unclear: the site text matches Kowhai House, Kowhai Court "
        "(found 'Kowhai' in Reference, part of a name only; 'Kowhai' in Site, part of a name only)."
    ]


def test_site_text_in_two_places_naming_different_properties_is_property_unclear(tmp_path):
    # "Matai Centre" is in #1's PDF (in the buyer address), so it passes the source text check.
    [row] = check(tmp_path, ["01-clean.pdf"], extract_with(site="Matai Centre"))
    assert row["Suggested property"] is None
    assert row["Status"] == "Needs you"
    assert my_flags(row) == [
        "Property unclear: the site text matches Kowhai House, Matai Centre "
        "(found 'Kowhai House' in Reference; 'Matai Centre' in Site)."
    ]


def test_part_of_a_name_matching_one_property_is_still_property_unclear(tmp_path):
    # "WO-30494 Rimu" is in #21's PDF, inside "WO-30494 Rimu Plaza".
    [row] = check(tmp_path, ["21-wrong-entity.pdf"], extract_with(reference="WO-30494 Rimu", site="Rimu"))
    assert row["Suggested property"] is None
    assert my_flags(row) == [
        "Property unclear: the site text matches Rimu Plaza "
        "(found 'Rimu' in Reference, part of a name only; 'Rimu' in Site, part of a name only)."
    ]


def test_invoice_21_buyer_is_not_the_property_entity(tmp_path):
    file = "21-wrong-entity.pdf"
    [row] = check(tmp_path, [file])
    assert row["Status"] == "Needs you"
    assert labels(row) == KEY.loc[file, "expected_flags"].split("; ")
    assert row["Suggested property"] == "Rimu Plaza"
    assert my_flags(row) == [
        "Wrong entity: the bill is addressed to Harbourline Property Holdings Limited, "
        "but Rimu Plaza's entity in properties.csv is Rimu Plaza Limited."
    ]


def test_no_invoice_gets_a_different_property_than_the_answer_key(tmp_path):
    files = [f for f in KEY.index if f not in ("09-quote.pdf", "10-statement.pdf")]  # not bills, ticket 03
    for row in check(tmp_path, files):
        file, suggested = row["File"], row["Suggested property"]
        expected_flags = KEY.loc[file, "expected_flags"].split("; ")
        assert suggested in (KEY.loc[file, "expected_property"], None), file
        if suggested is None:
            assert row["Status"] == "Needs you", file
            assert {f[:f.index(":") + 1] for f in my_flags(row)} & {"Property unclear:", "No property:"}, file
        # No Flag of this ticket where the answer key expects none, e.g. no Wrong entity without a buyer (#7, #18).
        assert {f[:f.index(":") + 1] for f in my_flags(row)} <= set(expected_flags), file


@pytest.mark.parametrize("text", ["Kōwhai House", "KOWHAI HOUSE.", "Kowhai  House"])
def test_case_macrons_punctuation_and_spaces_are_ignored(text):
    assert match(text) == [("Kowhai House", text.rstrip("."), True)]


@pytest.mark.parametrize("text, name, property", [
    ("WO-30440 Kowhai Hse", "Kowhai Hse", "Kowhai House"),
    ("WO-30440 12 Totara St", "12 Totara St", "Kowhai House"),
    ("Lobby, 88 Miro Road", "88 Miro Road", "Kowhai Court"),
])
def test_other_name_matches_its_property(text, name, property):
    assert match(text) == [(property, name, True)]


def test_part_of_a_property_name_matches_every_property_with_that_word():
    assert match("WO-30482 Kowhai") == [("Kowhai House", "Kowhai", False), ("Kowhai Court", "Kowhai", False)]


@pytest.mark.parametrize("text, hits", [
    ("Kowhaihouse", []),
    ("Rimuplaza level 2", []),
    ("Unit 112 Totara Stream", []),
    ("Matai Centres", [("Matai Centre", "Matai", False)]),  # 'Matai' is a whole word, 'Centres' is not 'Centre'
])
def test_a_name_inside_a_longer_word_does_not_match(text, hits):
    assert match(text) == hits


@pytest.mark.parametrize("text", ["Kowhia Hosue", "Totara Lane", "Replace emergency exit lights, level 2", ""])
def test_no_match_returns_nothing_never_the_closest_property(text):
    assert match(text) == []


def test_part_of_a_name_inside_a_whole_name_is_not_a_second_match():
    assert properties("WO-30418 Kowhai House") == ["Kowhai House"]


def test_site_that_is_the_buyer_address_is_property_unclear(tmp_path):
    # #12's buyer address names Matai Centre. Used as the Site, it must not become the property.
    address = "Level 3, Matai Centre, 40 Rata Road, Wellington 6011"
    [row] = check(tmp_path, ["12-job-management.pdf"], extract_with(site=address))
    assert row["Status"] == "Needs you"
    assert row["Suggested property"] is None
    assert row["Property reason"] is None
    assert my_flags(row) == [f"Property unclear: Site looks like the buyer's address ('{address}'), "
                             "so it was not used to pick the property."]


@pytest.mark.parametrize("file", ["02-wrong-gst.pdf", "13-xero-newer.pdf", "16-future-date.pdf"])
def test_bare_property_name_that_is_also_in_the_buyer_address_still_matches(tmp_path, file):
    [row] = check(tmp_path, [file])
    assert row["Suggested property"] == "Matai Centre"
    assert my_flags(row) == []


def bill(reference=None, site=None, item=None, buyer_name=None, buyer_identifier=None):
    values = {"reference": reference, "site": site, "buyer_name": buyer_name, "buyer_identifier": buyer_identifier}
    return values, [(item, None)]


@pytest.mark.parametrize("reference, site, item, property", [
    ("WO-30501 Kowhai House", None, "Sand and polish rimu floorboards", "Kowhai House"),
    (None, "Kowhai House", "Service data centre cooling units", "Kowhai House"),
    ("Matai Centre", None, "Food court: replace grease trap", "Matai Centre"),
])
def test_part_of_a_name_in_the_first_line_item_does_not_count(reference, site, item, property):
    suggested, _, flags = suggest(*bill(reference, site, item))
    assert (suggested, flags) == (property, [])


def test_line_item_with_only_part_of_a_name_is_no_property():
    assert suggest(*bill(item="Clear house drains")) == (None, None, [
        "No property: no property in properties.csv matches the site text "
        "(searched first line item 'Clear house drains')."
    ])


def test_ltd_and_limited_are_the_same_in_the_entity_check():
    _, _, flags = suggest(*bill(reference="WO-30418 Kowhai House", buyer_name="Harbourline Property Holdings Ltd"))
    assert flags == []
