# Issue tracker: GitHub Issues

Tickets live as GitHub issues in `ashgaun/stonewood-invoice-checker`. Use the `gh` CLI for every operation. The feature spec stays in the repo at `.scratch/<feature-slug>/spec.md`.

## Conventions

- One issue per ticket. The title keeps its order number, e.g. `03 — The checks`. Work tickets in that numbered order.
- Triage state is a label (see `triage-labels.md`). Change it with `gh issue edit <n> --add-label <label> --remove-label <label>`.
- Blocking is a `**Blocked by:** #N` line in the body. A ticket is unblocked when every issue it lists is closed.
- Comments and conversation history go in issue comments: `gh issue comment <n> --body-file <file>`.
- A ticket is done when its commit is approved and made. Then close it with `gh issue close <n> --comment "Done in <sha>"`.

## When a skill says "publish to the issue tracker"

Create an issue with `gh issue create --title "<NN> — <title>" --body-file <file> --label <triage label>`. Write the body to a file first, so Markdown and non-ASCII text survive.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <n> --comments`. The user normally passes the issue number or URL.

## Wayfinding operations

Used by `/wayfinder`. The **map** has one **child** issue per ticket.

- **Map**: `.scratch/<effort>/map.md`, holding the Notes, Decisions-so-far and Fog body.
- **Child ticket**: a GitHub issue with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`).
- **Blocking**: a `**Blocked by:** #N, #N` line in the body. A ticket is unblocked when every issue it lists is closed.
- **Frontier**: open, unblocked, unassigned issues. The lowest number wins.
- **Claim**: `gh issue edit <n> --add-assignee @me` before any work.
- **Resolve**: comment the answer under an `## Answer` heading and close the issue. Then append a context pointer (gist + issue link) to the map's Decisions-so-far in `map.md`.
