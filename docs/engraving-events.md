# Engraving Events

On-the-spot medal engraving at sporting meets (e.g. Little Athletics). Parents order
from their phone by scanning the stall's QR code, the operator works a live queue,
the laser text comes from a CSV export, and the parent is told when it's ready.

## Flow

1. **Engraving Events → New event.** Set the name, date, price per medal (default $15),
   minutes per medal (drives the wait estimate) and whether to text parents.
2. **QR → Print sign.** Put the sign on the stall. It links to `/engrave/<token>`.
3. **Parents order.** Name (max 24 chars), second line (max 28), place, quantity and an
   optional mobile, with a live medal preview and a spelling check. They pay at the stall.
   They land on `/engrave/o/<status token>`, which shows their order number, place in the
   queue and wait, and refreshes itself.
4. **Operator queue** (`/engraving/<event id>`, refreshes every 8 s):
   - *Start* puts an order on the laser (only one at a time).
   - *Done — next medal* counts medals; on the last one the order goes to **Ready** and the
     parent is texted once (SMS on, mobile given).
   - Tick *Paid* when they pay; *Collected* also marks it paid.
   - *Walk-up order* for people who order at the table. *Pause orders* stops new QR orders.
5. **Export CSV for laser** — one row per medal still to engrave, in queue order:
   `Name,Line2,Place,Order,Medal`.

## Laser setup

Pick your laser software next to **Export for laser** (the choice is remembered on that
device) and, if you like, **Next 10** / **Next 20** to export only the next round of medals.
All exports are one row per medal still to engrave, in queue order.

| Software | File | Notes |
| --- | --- | --- |
| **xTool** | CSV with a header row | Blank cells become a space, because xTool skips a row with a blank cell. |
| **LightBurn** | CSV with **no** header row | LightBurn counts every line as a row (rows and columns start at 0). |
| **EZCad2** | Zip of `names.txt`, `line2.txt`, `places.txt` | EZCad2 reads TXT or old-format XLS, not CSV. One value per line. |
| **Plain CSV** | CSV with a header row | `Name,Line2,Place,Order,Medal` |

- **xTool Studio / XCS:** choose *Different design – batch processing*, add text variables for
  the three text objects, then import the CSV and map Name / Line2 / Place. Some models need the
  conveyor or slide extension for batch mode; check xTool's guide for your model.
- **LightBurn:** build one medal template with text objects set to Variable Text →
  Merge/CSV (Name = `%0`, Line2 = `%1`, Place = `%2`). Browse to the file, turn on *Auto Advance*
  and, for a start row of 0, click Reset on the first run.
- **EZCad2:** three text objects, each reading its own TXT file (one line per medal). Turn
  *Auto Reset* on, or the list restarts from the top and engraves duplicates.

None of these programs is documented to re-read a file you have already loaded. Work in rounds:
export **Next 10**, load it once, engrave the round, then export and load the next one.
Medals counted with *Done* drop off the next export. This has not been tested on real lasers.

## API

Operator (signed in): `/v1/engraving/events`, `/events/{id}/queue`, `/events/{id}/orders`,
`/events/{id}/export.csv`, `/events/{id}/export?software=xtool|lightburn|ezcad2|csv&limit=`, `/orders/{id}` (PATCH), `/orders/{id}/start`,
`/orders/{id}/medal-done`, `/orders/{id}/resend-ready`.

Public: `/v1/public/engraving/events/{token}` (GET, POST `/orders`),
`/v1/public/engraving/orders/{status_token}`.

SMS event name in `smslog`: `engraving_ready`.

## Bunches of medals and tear-off tickets

A parent bringing several medals orders them all in one go: **Add another medal** on the order form (up to 10 different medals, each with its own name, second line, place and quantity). Each medal still gets its own order number (A-005, A-006…) so the laser queue and CSV are unchanged, but they share one mobile number and one status page that lists the whole bunch.

**Tear-off tickets.** The stall keeps a pile of numbered two-part tickets (use **Ticket sheet** on the queue page to print them, then cut them). The parent takes one, types its number into the form (required), keeps one half and puts the other half in the tub with the medals. The ticket number is shown in the queue, can be searched, and is blocked from reuse while a bunch is still in progress (it frees up once collected or cancelled).

**At collection.** Search the queue by order number, ticket number, name or the last 4 digits of the mobile. **Collect all** marks every ready medal in the bunch collected at once. **Print ticket** (printer icon on an order) prints a slip listing the whole bunch, with unpaid amount and mobile ending, if you want a printed copy for the tub as well.

## Paying by card

Parents can pay from their order status page ("Pay $X by card"). One payment covers the order and any medals ordered with it. It uses the shop's own Stripe Connect account, the same as Mobile Services invoices, so card fees come out of the shop's Stripe balance. The order flips to Paid when Stripe's Connect webhook reports the payment; the queue then shows "Paid ... by card". Paying at the stall still works and is the fallback. Turn it off per event with the "pay by card online" setting. It only shows when the shop has finished card payment setup and `ENABLE_STRIPE_INVOICE_CHECKOUT` is on.
