# 04 — Property matching

**What to build:** check 10 and the entity part of check 9 from `CONTEXT.md`. Search only the site text (Reference, first line of the description, site or job block), never the buyer or supplier address. Match whole words against each property and its other names, ignoring case, macrons, punctuation and extra spaces. No fuzzy matching. One match: suggest it with the reason ("Matched 'Kowhai Hse' in Reference to Kowhai House"). Several matches, places that disagree, or none: Flag. When a property matched, flag a buyer name that does not match its entity; skip this when no property matched.

Includes the helpers: property name normalising and matching.

**Blocked by:** 02 — One invoice end to end. Runs in parallel with 03.

**Status:** ready-for-agent

## Tests to write first
Seam 2 (helpers):
- "Kōwhai House", "KOWHAI HOUSE." and "Kowhai  House" all match Kowhai House.
- An other name ("Kowhai Hse", a street address) matches its property.
- "Kowhai" alone matches several properties.
- Whole words only: a name inside a longer word does not match.
- No match returns nothing, never the closest property.

Seam 1 (`run` through `review.xlsx`, fake `extract` from the answer key):
- #1, #5 and #12 suggest the answer key's property, with a reason naming the matched text.
- #1 is not matched to the property in its buyer address.
- #17 is **Needs you** with `Property unclear:` listing the matching properties.
- Site text in two places naming different properties gives `Property unclear:`.
- No site text gives `No property:`.
- #21 gets `Wrong entity:` naming the buyer and the property's entity.

## Acceptance criteria
- [ ] Every invoice's suggested property matches the answer key, or the invoice is **Needs you**. No invoice gets a different property.
- [ ] #21 matches the answer key's Flag labels.
- [ ] All tests pass with no network access.
