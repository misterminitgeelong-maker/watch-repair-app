"""Australian GST calculation shared by the watch-repair and Mobile Services (auto-key) quote/invoice flows."""

GST_RATE = 0.10


def compute_gst_amounts(entered_cents: int, gst_enabled: bool, gst_inclusive: bool) -> tuple[int, int, int]:
    """Given the total of the entered line-item prices, return (subtotal_cents, tax_cents, total_cents).

    subtotal_cents is always GST-exclusive and total_cents is always what the customer pays,
    so total_cents == subtotal_cents + tax_cents in every case.
    """
    if not gst_enabled:
        return entered_cents, 0, entered_cents
    if gst_inclusive:
        # entered_cents already includes GST; back it out.
        total_cents = entered_cents
        subtotal_cents = int(round(entered_cents / (1 + GST_RATE)))
        tax_cents = total_cents - subtotal_cents
        return subtotal_cents, tax_cents, total_cents
    # entered_cents is GST-exclusive; add GST on top.
    tax_cents = int(round(entered_cents * GST_RATE))
    return entered_cents, tax_cents, entered_cents + tax_cents
