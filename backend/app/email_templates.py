"""
HTML email rendering for Mainspring transactional email.

Produces email-client-safe HTML (table layout, inline styles, <=600px) plus a
matching plain-text body. Branding is driven by the tenant's shop identity
(name, address, phone, email, ABN). The accent colour is a parameter so a
per-tenant brand colour can be wired later without changing call sites.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Sequence

# Neutral, professional defaults that render well across Gmail/Outlook/Apple Mail.
_HEADER_BG = "#1f2937"
_HEADER_TEXT = "#ffffff"
_BODY_BG = "#f4f5f7"
_CARD_BG = "#ffffff"
_TEXT = "#1f2937"
_MUTED = "#6b7280"
_BORDER = "#e5e7eb"
_DEFAULT_ACCENT = "#c9772a"

# Lenient hex colour: #RGB, #RRGGBB or #RRGGBBAA.
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


@dataclass
class ShopInfo:
    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    abn: str | None = None
    logo_url: str | None = None
    brand_color: str | None = None


def _valid_hex(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned if cleaned and _HEX_COLOR_RE.match(cleaned) else None


def _resolve_accent(shop: ShopInfo, fallback: str) -> str:
    return _valid_hex(shop.brand_color) or fallback


def _esc(value: str | None) -> str:
    return html.escape((value or "").strip())


def _currency_symbol(currency: str) -> str:
    cur = (currency or "AUD").upper()
    return "$" if cur in ("AUD", "USD", "NZD", "CAD") else f"{currency} "


def _money(cents: int, currency: str) -> str:
    return f"{_currency_symbol(currency)}{int(cents) / 100:.2f}"


def _line_items_table(line_items: Sequence[dict], currency: str) -> str:
    if not line_items:
        return ""
    rows = []
    for li in line_items:
        desc = _esc(li.get("description") or "Item")
        qty = _esc(str(li.get("quantity", 1)))
        total_cents = int(li.get("total_price_cents") or 0)
        rows.append(
            f'<tr>'
            f'<td style="padding:8px 0;border-bottom:1px solid {_BORDER};font-size:14px;color:{_TEXT};">{desc}</td>'
            f'<td style="padding:8px 0;border-bottom:1px solid {_BORDER};font-size:14px;color:{_MUTED};text-align:center;white-space:nowrap;">x{qty}</td>'
            f'<td style="padding:8px 0;border-bottom:1px solid {_BORDER};font-size:14px;color:{_TEXT};text-align:right;white-space:nowrap;">{_money(total_cents, currency)}</td>'
            f'</tr>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin:8px 0 4px;">'
        f'<tr>'
        f'<th align="left" style="padding:0 0 6px;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:{_MUTED};">Description</th>'
        f'<th align="center" style="padding:0 0 6px;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:{_MUTED};">Qty</th>'
        f'<th align="right" style="padding:0 0 6px;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:{_MUTED};">Amount</th>'
        f'</tr>'
        + "".join(rows)
        + '</table>'
    )


def _totals_block(
    *,
    subtotal_cents: int | None,
    tax_cents: int | None,
    total_cents: int,
    currency: str,
    accent: str,
) -> str:
    rows = ""
    if subtotal_cents is not None and tax_cents:
        rows += (
            f'<tr><td style="padding:2px 0;font-size:13px;color:{_MUTED};">Subtotal</td>'
            f'<td style="padding:2px 0;font-size:13px;color:{_TEXT};text-align:right;">{_money(subtotal_cents, currency)}</td></tr>'
            f'<tr><td style="padding:2px 0;font-size:13px;color:{_MUTED};">GST</td>'
            f'<td style="padding:2px 0;font-size:13px;color:{_TEXT};text-align:right;">{_money(tax_cents, currency)}</td></tr>'
        )
    rows += (
        f'<tr><td style="padding:8px 0 0;font-size:16px;font-weight:700;color:{_TEXT};border-top:2px solid {accent};">Total</td>'
        f'<td style="padding:8px 0 0;font-size:16px;font-weight:700;color:{_TEXT};text-align:right;border-top:2px solid {accent};">{_money(total_cents, currency)}</td></tr>'
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;margin-top:4px;">' + rows + '</table>'
    )


def _cta_button(label: str, url: str, accent: str) -> str:
    safe_label = _esc(label)
    safe_url = html.escape(url, quote=True)
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 8px;">'
        '<tr><td align="center" bgcolor="' + accent + '" style="border-radius:8px;">'
        f'<a href="{safe_url}" target="_blank" '
        f'style="display:inline-block;padding:13px 30px;font-size:15px;font-weight:700;'
        f'color:#ffffff;text-decoration:none;border-radius:8px;">{safe_label}</a>'
        '</td></tr></table>'
    )


def _header(shop: ShopInfo, title: str) -> str:
    """Dark header bar with optional logo image above the shop name."""
    logo_url = (shop.logo_url or "").strip()
    logo_html = ""
    if logo_url:
        safe_src = html.escape(logo_url, quote=True)
        safe_alt = _esc(shop.name) or "Mainspring"
        logo_html = (
            f'<img src="{safe_src}" alt="{safe_alt}" '
            'style="display:block;max-height:40px;height:auto;border:0;outline:none;'
            'text-decoration:none;margin:0 0 10px;" />'
        )
    return (
        f'<td style="background:{_HEADER_BG};padding:22px 28px;">'
        + logo_html
        + f'<p style="margin:0;font-size:18px;font-weight:700;color:{_HEADER_TEXT};letter-spacing:.01em;">{_esc(shop.name) or "Mainspring"}</p>'
        + f'<p style="margin:4px 0 0;font-size:12px;color:#cbd5e1;letter-spacing:.08em;text-transform:uppercase;">{_esc(title)}</p>'
        + '</td>'
    )


def _footer(shop: ShopInfo) -> str:
    parts: list[str] = []
    contact_bits = [b for b in (shop.phone, shop.email) if b]
    if contact_bits:
        parts.append(" &nbsp;·&nbsp; ".join(_esc(b) for b in contact_bits))
    if shop.address:
        parts.append(_esc(shop.address).replace("\n", "<br/>"))
    if shop.abn:
        parts.append(f"ABN {_esc(shop.abn)}")
    inner = "<br/>".join(parts) if parts else ""
    return (
        f'<p style="margin:0;font-size:12px;line-height:18px;color:{_MUTED};">'
        f'<strong style="color:{_TEXT};">{_esc(shop.name) or "Mainspring"}</strong>'
        + (f'<br/>{inner}' if inner else "")
        + '</p>'
    )


def render_transactional_email(
    *,
    title: str,
    preheader: str,
    greeting: str,
    intro_html: str,
    shop: ShopInfo,
    cta_label: str | None = None,
    cta_url: str | None = None,
    line_items: Sequence[dict] | None = None,
    subtotal_cents: int | None = None,
    tax_cents: int | None = None,
    total_cents: int | None = None,
    currency: str = "AUD",
    note_html: str | None = None,
    accent: str = _DEFAULT_ACCENT,
) -> str:
    """Return a full responsive HTML email document."""
    # A valid tenant brand colour wins over the default/passed accent.
    accent = _resolve_accent(shop, accent)
    items_html = _line_items_table(line_items or [], currency)
    totals_html = (
        _totals_block(
            subtotal_cents=subtotal_cents,
            tax_cents=tax_cents,
            total_cents=total_cents,
            currency=currency,
            accent=accent,
        )
        if total_cents is not None
        else ""
    )
    cta_html = _cta_button(cta_label, cta_url, accent) if cta_label and cta_url else ""
    note_block = (
        f'<p style="margin:16px 0 0;font-size:13px;line-height:20px;color:{_MUTED};">{note_html}</p>'
        if note_html
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="x-apple-disable-message-reformatting"/>
<title>{_esc(title)}</title>
</head>
<body style="margin:0;padding:0;background:{_BODY_BG};">
<span style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;">{_esc(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BODY_BG};padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:{_CARD_BG};border-radius:12px;overflow:hidden;border:1px solid {_BORDER};">
  <tr>
    {_header(shop, title)}
  </tr>
  <tr>
    <td style="padding:28px;">
      <p style="margin:0 0 12px;font-size:16px;font-weight:600;color:{_TEXT};">{_esc(greeting)}</p>
      <div style="font-size:14px;line-height:22px;color:{_TEXT};">{intro_html}</div>
      {items_html}
      {totals_html}
      {cta_html}
      {note_block}
    </td>
  </tr>
  <tr>
    <td style="padding:20px 28px;border-top:1px solid {_BORDER};background:#fafafa;">
      {_footer(shop)}
    </td>
  </tr>
</table>
<p style="margin:14px 0 0;font-size:11px;color:{_MUTED};">Sent by Mainspring on behalf of {_esc(shop.name) or "your service provider"}.</p>
</td></tr>
</table>
</body>
</html>"""
