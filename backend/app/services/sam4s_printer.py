"""ESC/POS ticket printing for SAM4S (and other ESC/POS-compatible) network receipt printers.

SAM4S printers speak the standard Epson ESC/POS command set over a raw TCP
socket (the de-facto "JetDirect" style port 9100), the same protocol used by
most POS receipt printers. There is no vendor SDK involved — we just build the
byte stream and write it to the socket.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Optional

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
DOUBLE_SIZE = GS + b"!\x11"
NORMAL_SIZE = GS + b"!\x00"
FEED_AND_CUT = b"\n\n\n" + GS + b"V\x01"  # partial cut, after a little feed so the cut clears the text

# Default JetDirect-style raw ESC/POS port used by SAM4S and most network receipt printers.
DEFAULT_PORT = 9100

# Encode with the printer's native code page. Unicode punctuation (—, ’, etc.)
# has no cp437 slot, so fall back per-character to keep the rest of the line intact.
_ENCODING = "cp437"


def _text(s: str) -> bytes:
    return s.encode(_ENCODING, errors="replace")


def _line(s: str = "") -> bytes:
    return _text(s) + b"\n"


def _qr_code(data: str, module_size: int = 6) -> bytes:
    """Build the GS ( k command sequence to store and print a QR code (Epson ESC/POS standard)."""
    payload = _text(data)
    store_len = len(payload) + 3
    pL, pH = store_len & 0xFF, (store_len >> 8) & 0xFF
    return (
        GS + b"(k\x04\x00\x31\x41\x32\x00"                       # select model 2
        + GS + bytes([0x03, 0x00, 0x31, 0x43, module_size])       # module size
        + GS + bytes([0x03, 0x00, 0x31, 0x45, 0x31])              # error correction level M
        + GS + b"(k" + bytes([pL, pH]) + b"\x31\x50\x30" + payload  # store data
        + GS + b"(k\x03\x00\x31\x51\x30"                          # print stored data
    )


@dataclass
class Sam4sTicket:
    """One printable ticket — mirrors the fields already rendered onto the Niimbot label."""
    job_number: str
    customer_name: str
    item_title: str
    is_customer_copy: bool
    customer_phone: Optional[str] = None
    services: Optional[str] = None
    date_in: Optional[str] = None
    deposit_label: Optional[str] = None
    balance_label: Optional[str] = None
    qr_url: Optional[str] = None


def build_ticket_escpos(ticket: Sam4sTicket) -> bytes:
    out = bytearray()
    out += ALIGN_CENTER + BOLD_ON + DOUBLE_SIZE
    out += _line("MAINSPRING")
    out += NORMAL_SIZE
    out += _line("CUSTOMER COPY" if ticket.is_customer_copy else "WORKSHOP COPY")
    out += BOLD_OFF + _line("-" * 32)

    out += ALIGN_LEFT + BOLD_ON + DOUBLE_SIZE
    out += _line(f"#{ticket.job_number}")
    out += NORMAL_SIZE + BOLD_OFF

    out += BOLD_ON + _line(ticket.customer_name) + BOLD_OFF
    if ticket.customer_phone:
        out += _line(ticket.customer_phone)
    out += _line(ticket.item_title)
    if ticket.services:
        out += _line(ticket.services)
    if ticket.date_in:
        out += _line(f"Date in: {ticket.date_in}")
    if not ticket.is_customer_copy and ticket.deposit_label and ticket.balance_label:
        out += _line(f"Deposit: {ticket.deposit_label}   Balance: {ticket.balance_label}")

    if ticket.qr_url:
        out += _line("")
        out += ALIGN_CENTER
        out += _qr_code(ticket.qr_url)
        out += _line("Scan to track this repair" if ticket.is_customer_copy else "Open internal ticket")

    out += FEED_AND_CUT
    return bytes(out)


def build_tickets_escpos(tickets: list[Sam4sTicket]) -> bytes:
    out = bytearray(INIT)
    for ticket in tickets:
        out += build_ticket_escpos(ticket)
    return bytes(out)


class PrinterConnectionError(RuntimeError):
    """Raised when the SAM4S printer can't be reached or write fails."""


def send_to_printer(host: str, port: int, data: bytes, timeout: float = 5.0) -> None:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(data)
    except OSError as exc:
        raise PrinterConnectionError(f"Could not reach printer at {host}:{port} — {exc}") from exc
