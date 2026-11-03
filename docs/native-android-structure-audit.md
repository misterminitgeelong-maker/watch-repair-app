# Native Android: phone structure audit (17 October 2026)

Sam's feedback: tablet and computer feel very easy, the phone feels like it has moved backwards, and "a bunch of structure is missing".

## Why tablet feels easier

The tablet layout (width of 840dp or more) shows the same screens as the phone, but two at a time: the list on the left and the open record on the right, under a top bar with the main areas. Nothing is hunted for, because the list, filters and record are visible together. On a phone only one screen fits, so whatever structure the layout supplied for free has to be built into each screen.

## What the phone had lost

| Area | Missing on phone | Tablet or web behaviour |
|---|---|---|
| Job detail (watch, shoe) | One long Summary scroll: contact, rail, history, job card, custom fields, customer, watch details, money, notes, assignment all stacked. No sections. | Wide pane, everything visible at once; web groups into Details, Parts, Notes, Payments, History. |
| Job lists | Search, status tabs and service chips scroll away; no sort; no result count. | List stays put beside the record. Web list has sort and counts. |
| Today | A flat stack with no block titles and numbers that cannot be tapped. | Wide dashboard with visible blocks. |
| Customer detail | No quick Call/Text/Email; sections unlabelled. | Context panel beside the list. |
| Customers list | No alphabetical grouping or count. | Web table with sort and counts. |
| Inbox | Flat list, no day grouping or filters. | Web inbox groups by type. |
| Dispatch | Section counts and sticky filters missing. | Web has lanes and counts. |

## What was added in this pass

See the commit history on `claude/native-android-ux-f5shnd` for the details. In short:

- Watch and shoe job detail become segmented tabs: Overview, Work, Money, History, Messages, with a sticky action bar on every tab.
- Jobs hub header (search, tabs, chips) is sticky, with a result count and a Sort control.
- Customers list has alphabetical sticky headers and a count; Inbox groups by day and has filter chips; Dispatch sections get counts.
- Today is organised into labelled blocks (Shortcuts, Due today, Needs your attention, Money, Recent) with See all links, and the job counts open Jobs.
- Customer detail gets Call/Text/Email and tabbed or headed sections with counts.

## Still different from tablet and web

- Tablet shows list and record side by side; a phone cannot, so the sticky header and tabs stand in for it.
- Bulk actions do not exist on the backend for watch and shoe jobs.
- Mobile job detail already had a tabbed structure (Info, Vehicle & Key, Financial, Photos, Messages, Activity) and was left alone.
