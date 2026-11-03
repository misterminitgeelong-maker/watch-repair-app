# Native Android phone UI: match the Capacitor (web) phone view

Sam's decision (17 October 2026): keep the native app, but rebuild its phone screens to follow the Capacitor/web phone view, which he finds "much cleaner, easier to find things, everything isn't bunched together."

Reference: the web app at phone width (390x844), captured from `frontend/` against the local test backend. Screenshots are in the gallery.

## Patterns to copy

**Header (every screen).** A persistent app bar: Mainspring wordmark at the left, a search icon at the right that opens global search. Below it a large page title in the display serif (Instrument Serif) with a short accent underline. No crowded eyebrow labels.

**Bottom bar (five slots).** Home, Inbox, then one tab per enabled service line (Watch, Mobile; Shoe goes to More when there are three), then More. A one-service shop has only its own service tab. The tab is named for the service, not "Jobs".

**More.** A compact sheet over the page with a four-column grid of icon + label tiles (Shoe, Customers, Invoices, Reports, Stocktake/Inventory, Accounts, Database, Settings, What's new) and Sign out under it. No long list, no collapsible groups, no scrolling.

**Home.** Page title, one overview card (headline and a count of active jobs), a two-column grid of tappable tiles (label, big number, small caption: Active jobs, Customers, Quotes, Invoices, Work value, Team), then a Live Service Queue list of recent jobs with a status pill and date.

**Service screen (Watch repairs).** Title; Board / List toggle with Queue and Export buttons; one full-width primary button (New Job Ticket); sub-tabs Jobs | Catalogue; Active | Completed; one row with Search and Filters; the list or board; a floating "New Job" button at bottom right. Job cards in list view: job number large in the accent colour, title, customer, small status pill and "0d in shop", quote amount. One card per job with a 1px border and generous padding.

**Job detail.** Back link with Prev / Next at the right; title "#JOB-00008 · Crystal replacement" in the display serif; one row with the primary next-step button ("→ Collected") and a "..." overflow menu; the key facts as light label: value lines (Status pill, Priority, Quote, Created, In shop); a stepper of circles (Received, Quoted, Approved, In Workshop, Completed); tabs Details | Work Logs | Attachments (with Quotes/Money and Messages as further tabs); the content below in bordered cards.

**Customers.** Title; Merge duplicates and Add Customer buttons; search and a sort select; then one bordered row per customer: name in the accent colour, email, phone, added date.

**Spacing and feel.** Light grey page background, white bordered cards (1px border, no shadow), generous vertical whitespace, 16 to 20dp page padding, big touch targets, one primary action per screen.

## Web tokens (for an optional "Mainspring" appearance)

Background #F6F7F9, surface #FFFFFF, border #E2E6EA, text #12141A, muted #596068, accent #D2361B (red-orange), accent light #FDEAE6. Display font Instrument Serif; body font Plus Jakarta Sans.

## What native keeps that the web phone view lacks

Offline queue and banner, job photo thumbnails and hero photo, status colour pills, Repair queue swipe, Call/Text/Email shortcuts. Keep them where they do not add clutter.
