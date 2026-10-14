"""Check 10 and the entity part of check 9 from CONTEXT.md: suggest the property from the site text."""
import csv
import re
import unicodedata
from pathlib import Path

with open(Path(__file__).parent / "properties.csv", newline="", encoding="utf-8") as f:
    PROPERTIES = list(csv.DictReader(f))


def fold(word):
    """'Kōwhai' -> 'kowhai': ignore case and macrons."""
    return "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c)).casefold()


def words(text):
    """Whole words as (folded word, position in text). Punctuation and spaces only separate words."""
    return [(fold(m.group()), m) for m in re.finditer(r"[^\W_]+", unicodedata.normalize("NFC", text))]


def starts(folded, target):
    """Where the word list target appears in folded, as whole words."""
    return [i for i in range(len(folded) - len(target) + 1) if target and folded[i:i + len(target)] == target]


def match(text):
    """[(property, matched text as printed, whole name?)] for every property in text.

    Whole name: a property's name or one of its other names, as whole words.
    Not whole: a leftover word that is only part of a property's name, such as 'Kowhai' alone.
    """
    text = unicodedata.normalize("NFC", text)
    found = words(text)
    folded = [w for w, _ in found]
    hits, used = [], set()
    for p in PROPERTIES:
        for name in [p["property"], *p["other_names"].split(";")]:
            target = [w for w, _ in words(name)]
            for i in starts(folded, target):
                hits.append((p["property"], text[found[i][1].start():found[i + len(target) - 1][1].end()], True))
                used.update(range(i, i + len(target)))
    for p in PROPERTIES:
        name = {w for w, _ in words(p["property"])}
        hits += [(p["property"], m.group(), False) for i, (w, m) in enumerate(found) if i not in used and w in name]
    return hits


def company(name):
    """Company name ignoring case, macrons, punctuation, spaces and 'Ltd'/'Limited', as check 6 does."""
    return [w for w, _ in words(name) if w not in ("ltd", "limited")]


def suggest(values, items):
    """Suggested property for one bill.

    values: field name -> value worked out from verified source text (str, date or Decimal), None if blank.
    items: [(description or None, amount Decimal or None)] per line item.
    Returns (property or None, reason or None, flags). Each Flag starts with its fixed label.
    Site text is only the Reference, the Site and the first line item, never the buyer or supplier details.
    """
    places = {"Reference": values["reference"], "Site": values["site"],
              "first line item": items[0][0] if items else None}
    if not any(places.values()):
        return None, None, ["No property: no site text (Reference, Site and first line item are all blank)."]
    address = [w for w, _ in words(values["buyer_identifier"] or "")]
    used_address = [f"{place} looks like the buyer's address ('{text}')" for place, text in places.items()
                    if text and starts([w for w, _ in words(text)], address)]
    if used_address:
        return None, None, [f"Property unclear: {'; '.join(used_address)}, so it was not used to pick the property."]
    # Part of a name counts only in Reference and Site. In a description it is too often an ordinary word.
    hits = [(place, *hit) for place, text in places.items() if text for hit in match(text)
            if hit[2] or place != "first line item"]
    if not hits:
        searched = ", ".join(f"{place} '{text}'" for place, text in places.items() if text)
        return None, None, [f"No property: no property in properties.csv matches the site text (searched {searched})."]
    matched = list(dict.fromkeys(p for _, p, _, _ in hits))  # in properties.csv order
    # Suggest only one property found by its whole name. A part of a name alone is never enough (stricter choice).
    if len(matched) > 1 or not any(whole for *_, whole in hits):
        found = "; ".join(dict.fromkeys(f"'{text}' in {place}" + ("" if whole else ", part of a name only")
                                        for place, _, text, whole in hits))
        return None, None, [f"Property unclear: the site text matches {', '.join(matched)} (found {found})."]
    [property] = matched
    found = ", ".join(f"'{text}' in {place}" for place, _, text, _ in hits)
    flags = []
    buyer = values["buyer_name"]
    entity = next(p["entity"] for p in PROPERTIES if p["property"] == property)
    if buyer and company(buyer) != company(entity):
        flags.append(f"Wrong entity: the bill is addressed to {buyer}, "
                     f"but {property}'s entity in properties.csv is {entity}.")
    return property, f"Matched {found} to {property}", flags
