# Native Android: final pre-Play walkthrough (18 October 2026)

Build: branch `claude/native-android-ux-f5shnd` at the commit that adds this file. Emulator phone (1080x2400), tablet size simulated with `wm size` (portrait and landscape), light and dark phone setting, 200% font. Demo shop data. Full on-device suite: 274 tests, 0 failures; unit tests pass.

## Found and fixed

- **More tab reopened the last tool instead of the More sheet.** After opening Customers from More, tapping More went back to Customers, and Home could also bring a tool back. More now always opens the sheet, tools opened from More replace the current tab, and Home always shows Home. New test `moreAlwaysOpensTheSheetEvenAfterOpeningATool`.
- **Status bar icons vanished when the phone was in dark mode.** The default Mainspring look is light only, so white system icons sat on a light page. System bar icons now follow the app theme.
- **200% font:** More tiles broke words mid-word ("Custo mers"), the bottom bar labels touched, kanban columns were too narrow. More now uses two columns at large text, the bottom bar text is capped at 125%, and boards widen with the text.
- Reports: "Quarter" was clipped in the period switch. Inventory still had the old header and eyebrow. Watch, Shoe, Mobile and All jobs titles sat further in than other titles. All fixed.
- Earlier today: login search tag, locked intake fields, multi-watch button text, Mobile job detail test, settings dialog test.

## Checked and fine

Sign-in (Option A), Home dashboard, Inbox, Watch board and list, hold-to-move menu with Undo, Mobile board, Shoe list, job detail (Details, Work Logs, Attachments), Customers, Quotes, Invoices, Reports, Inventory, More sheet, Settings and appearance, New intake chooser, tablet landscape (top navigation, all seven Mobile stages visible).

## Still open

- Push notifications need the Firebase `google-services.json`.
- Not tried on a real phone: fingerprint prompt, camera/photo capture, Niimbot label printing, TalkBack, share sheet.
- Server side of the 90-day session must be deployed (PR #49 is merged to main; deploy status not checked) before the app benefits.
- "+ New Quote" is a stub; Launch checklist has 4 items, the web has 5; Merge duplicates only shows instructions; Shoe Saved views were removed; "+ Log Work" is not on the boards.
- The New intake chooser screen (before the wizard) still has the older look.
- Job list cards have a small red "x" delete button for owners and managers next to the watch icon. It asks for confirmation, but it is easy to confuse with "close".
- The Settings screen shows the shop slug in the session line.
- Tablet portrait below 840dp wide uses the phone layout. No real tablet was tested.
- Release build, signing, Play listing and Data safety form are covered by `docs/native-android-release-readiness.md` and the Play assets already in the repo; the APK Sam installs is a debug build.

## Checklist for Sam's real phone

1. Install the APK over the old one, open it. You should see the new cream sign-in screen. Sign in with your real account.
2. Turn on More > Settings > "Unlock with fingerprint, face or PIN". Close the app, wait 30 seconds, open it: the fingerprint prompt should appear. Try the phone PIN fallback.
3. Run one full job: Home > New intake > Watch, add a customer and a watch, create the ticket. Open it, move it through the stages, add a work log and a photo, create the quote, then the invoice, record a payment.
4. Hold-to-move on each board: Watch, Shoe and Mobile. Hold a ticket, choose Move to, pick a stage, then tap Undo. Move one to "No go" and check it asks for a reason.
5. Offline: switch on airplane mode, move a ticket, check the "saved offline" message and the banner. Turn airplane mode off and check it syncs.
6. Settings > Display > Font size: largest. Check Home, Watch, More and a job.
7. Turn on TalkBack: swipe through Home, the bottom bar, the More sheet and a board ticket. Check the "Move to" action is offered on a ticket.
8. Phone in dark mode: the clock and battery icons should stay readable.
9. Sign out and back in. Check the shop ID is remembered.
