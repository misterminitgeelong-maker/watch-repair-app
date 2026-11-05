# Minit network messaging

Approved design: [Figma messaging concept](https://www.figma.com/design/7rov3ZZ8byxPpJzb3fSOVV).

## Product behaviour

The existing Messages entry point now opens four connected views: Chats, Shop directory,
Announcements and State hubs. Both the shop route (`/messages`) and HQ route
(`/minit/messages`) use the same workspace.

- **Chats:** shared shop direct conversations plus the shop's state hub. Staff names and
  shop names identify senders. State conversations support replies, pins, and stock
  requests that the requesting shop or moderator can resolve and reopen.
- **Shop directory:** signed-up, active sites in the selected network, searchable by name,
  number and state, with state/type filters. The shop's own state appears first.
  Interstate direct messaging remains available.
- **Announcements:** network and state updates, pinned notices, training and important
  categories, unread filters, expandable text, and explicit per-shop receipt confirmation.
  Reading and confirming are separate actions; polling does not mark an announcement read.
- **State hubs:** VIC, NSW, QLD, WA, SA, TAS, ACT, NT, plus NZ. Each shop automatically
  accesses its assigned hub; other states are listed without exposing their conversations.
- **Files:** Photo and Attach file work for state and direct messages. Up to five PNG,
  JPEG, WebP or PDF files, 5 MiB each and 10 MiB combined. Message and files commit
  atomically. Authenticated downloads recheck current conversation membership.
- **Small screens:** one chat pane at a time, a back button, two-column hub cards,
  wrapping filters and a sticky composer. Desktop conversations have a collapsible
  information panel rather than a permanently occupied third column.

The colour accents are restrained: Minit navy/red, green for Victoria, and distinct pale
state/category labels. The app's fonts and theme tokens remain in use.

## Identity and access

Membership comes from `ParentAccountSite`, not logos, typed slugs, billing plans,
matching emails or dispatch-only consent. This feature does not link accounts,
grant support access, change operational reporting scope, or combine customer records.

A site's linked `Region.code` is authoritative; its existing `minit_region` is used
when no region row is linked. Recognised state names and prefixes such as VIC SOUTH,
QLD WEST and NZ NORTH map to their state hub. Unknown/unassigned values do not grant
a default state. Support Office should correct those assignments using existing shop
administration.

| Account | State chat | Announcement publishing |
| --- | --- | --- |
| Shop staff | Their shop's assigned state | None |
| HQ admin | Every state in that network | Whole network or a selected state |
| Regional manager | State associated with their explicit region grant | That state only |
| Unscoped HQ viewer | Read all states | None |
| Support impersonation session | Blocked | Blocked |

Direct conversations remain private to their two sites. Shop colleagues share messages,
unread state and announcement confirmations. This is a shop inbox, not private staff
messaging. Current membership is checked on every community request and file download;
an unlinked shop cannot keep using a saved state-hub URL. Posting and moderation checks
are server-side.

## Storage and API

Migration `20261103_network_community` adds five tables:

- `statehubmessage`: network/state, sender site/user, body, reply target, kind, pin and resolution timestamps.
- `statehubread`: one last-rendered message timestamp per network/state/site.
- `networkannouncement`: audience, category, title/body, author, pin and confirmation setting.
- `announcementreceipt`: unique announcement/site read and confirmation receipt.
- `networkmessageattachment`: message association, file metadata and binary content.

Small chat files live in the database so a message cannot be committed without its
attachments and storage remains consistent across API replicas. This increases backup
size; larger-file use should move behind an authenticated object-storage adapter.

New endpoints live under `/v1/network-community`: networks, hubs, cursor-paginated
hub messages, multipart posts, moderation, explicit read markers, paginated announcements,
publishing, receipts and protected attachment downloads. Existing
`/v1/network-messages` routes remain compatible and accept an optional parent-network
filter. Contact responses include state and shop number; direct message responses include
attachment metadata and conversation ID.

State read markers advance only through the latest message actually rendered, so a new
arrival between fetch and acknowledgement stays unread. History cursors use timestamp
plus UUID ordering, including messages with equal timestamps. A shop's read marker never
moves backward. Announcement receipt inserts are idempotent under concurrent staff use.

Chats poll every 15 seconds, hub counts every 30 seconds and announcements every 30
seconds. Direct inbox alerts continue working. State unread badges and announcement
receipts are in the messaging workspace; this change does not send email or phone push
notifications. Direct history retains the existing latest-200-message window; state chat
has a Load earlier messages control. Pins can be filtered within loaded state history.

## Rollout and validation

1. Review the branch and CI results.
2. Back up the database using the existing backup process.
3. Run `alembic upgrade head` with the deployment's normal pre-deploy step.
4. Build and deploy the backend and frontend together.
5. Verify with two shops in one state, one interstate shop, HQ and a regional manager.
6. Confirm state assignments, shared unread/receipt behaviour, interstate DMs, file
   downloads and blocked access after unlinking.

No demonstration shops, messages or announcements are seeded. No existing account links
are changed. A rollback to the previous UI can leave the new tables intact; downgrading
the migration removes new community messages, files and receipts, so export/backup that
data before any schema downgrade.

Focused validation:

```sh
cd backend
python -m pytest tests/test_network_community.py -q
python -m alembic upgrade head
python scripts/check_migrations.py
cd ../frontend
npm run typecheck
npm test -- src/pages/NetworkMessagingPage.test.tsx
npm run build
```

Run the backend suite against the repository's dedicated PostgreSQL test database as
well as SQLite. The new tests cover state/network isolation, regional publishing scope,
shop-shared read and confirmation markers, replies/pins/stock resolution, equal-timestamp
pagination, support-session denial, signup readiness and protected files.

