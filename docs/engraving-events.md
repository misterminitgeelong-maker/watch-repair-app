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

- **LightBurn:** build one medal template with text objects set to Variable Text →
  Merge/CSV (Name = column 0, Line2 = column 1, Place = column 2). Load the CSV in the
  Variable Text window and turn on *Auto Advance*, so each job sent moves to the next row.
- **xTool Studio:** use *Different design – batch processing*, add variables for the three
  text objects and import the CSV, mapping Name / Line2 / Place.

Re-export when new orders arrive; rows already engraved (counted with *Done*) drop off.

## API

Operator (signed in): `/v1/engraving/events`, `/events/{id}/queue`, `/events/{id}/orders`,
`/events/{id}/export.csv`, `/orders/{id}` (PATCH), `/orders/{id}/start`,
`/orders/{id}/medal-done`, `/orders/{id}/resend-ready`.

Public: `/v1/public/engraving/events/{token}` (GET, POST `/orders`),
`/v1/public/engraving/orders/{status_token}`.

SMS event name in `smslog`: `engraving_ready`.
