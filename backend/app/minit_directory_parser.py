"""Parse the "Organisation Graph" HTML export (Mister Minit IT's internal directory
tool) into plain Python data.

The export is a bundled, minified JS app with the org data embedded directly in the
script as a JS object literal — not JSON (bare identifier keys, backtick-quoted
strings) — assigned to some minifier-chosen variable, e.g. ``var Pe={entities:[...
],relationships:[...]}``. This module locates that literal structurally (by the
``entities``/``relationships`` shape, not by variable name, since the name changes
between exports) and parses it with a small hand-written recursive-descent parser —
deliberately not a full JS parser, just enough for this shape: objects with bare or
backtick keys, backtick strings, arrays, numbers, booleans, and null.

No Node/JS runtime involved, so this runs anywhere the Python backend does
(including the production container, which has no Node).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_ENTITIES_MARKER = re.compile(r"\{entities:\[")

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "0": "\0",
    "`": "`",
    "'": "'",
    '"': '"',
    "\\": "\\",
    "$": "$",
}

_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


class DirectoryParseError(ValueError):
    pass


def _skip_ws(text: str, i: int) -> int:
    n = len(text)
    while i < n and text[i] in " \t\r\n":
        i += 1
    return i


def _parse_backtick_string(text: str, i: int) -> tuple[str, int]:
    assert text[i] == "`"
    i += 1
    out: list[str] = []
    n = len(text)
    while i < n:
        c = text[i]
        if c == "`":
            return "".join(out), i + 1
        if c == "\\":
            i += 1
            if i >= n:
                break
            esc = text[i]
            if esc == "u":
                hex4 = text[i + 1 : i + 5]
                out.append(chr(int(hex4, 16)))
                i += 5
                continue
            if esc == "x":
                hex2 = text[i + 1 : i + 3]
                out.append(chr(int(hex2, 16)))
                i += 3
                continue
            out.append(_ESCAPES.get(esc, esc))
            i += 1
            continue
        out.append(c)
        i += 1
    raise DirectoryParseError(f"Unterminated backtick string starting near index {i}")


def _parse_value(text: str, i: int):
    i = _skip_ws(text, i)
    c = text[i]
    if c == "{":
        return _parse_object(text, i)
    if c == "[":
        return _parse_array(text, i)
    if c == "`":
        return _parse_backtick_string(text, i)
    if text.startswith("JSON.parse(", i):
        # A handful of fields (e.g. a locality/geocode cache) are emitted as
        # JSON.parse(`...`) expressions rather than plain literals. We don't need
        # their contents, but must consume the expression correctly to keep
        # parsing the rest of the object.
        inner, i = _parse_backtick_string(text, i + len("JSON.parse("))
        i = _skip_ws(text, i)
        if i >= len(text) or text[i] != ")":
            raise DirectoryParseError(f"Expected ')' closing JSON.parse( at index {i}")
        return json.loads(inner), i + 1
    if text.startswith("true", i):
        return True, i + 4
    if text.startswith("false", i):
        return False, i + 5
    if text.startswith("null", i):
        return None, i + 4
    m = _NUMBER_RE.match(text, i)
    if m:
        s = m.group(0)
        val = float(s) if ("." in s or "e" in s or "E" in s) else int(s)
        return val, m.end()
    raise DirectoryParseError(f"Unexpected token at index {i}: {text[i:i+30]!r}")


def _parse_object(text: str, i: int) -> tuple[dict, int]:
    assert text[i] == "{"
    i = _skip_ws(text, i + 1)
    obj: dict = {}
    if text[i] == "}":
        return obj, i + 1
    while True:
        i = _skip_ws(text, i)
        if text[i] == "`":
            key, i = _parse_backtick_string(text, i)
        else:
            m = _IDENT_RE.match(text, i)
            if not m:
                raise DirectoryParseError(f"Expected object key at index {i}: {text[i:i+30]!r}")
            key = m.group(0)
            i = m.end()
        i = _skip_ws(text, i)
        if text[i] != ":":
            raise DirectoryParseError(f"Expected ':' after key {key!r} at index {i}")
        i = _skip_ws(text, i + 1)
        value, i = _parse_value(text, i)
        obj[key] = value
        i = _skip_ws(text, i)
        if text[i] == ",":
            i = _skip_ws(text, i + 1)
            continue
        if text[i] == "}":
            return obj, i + 1
        raise DirectoryParseError(f"Expected ',' or '}}' at index {i}: {text[i:i+30]!r}")


def _parse_array(text: str, i: int) -> tuple[list, int]:
    assert text[i] == "["
    i = _skip_ws(text, i + 1)
    arr: list = []
    if text[i] == "]":
        return arr, i + 1
    while True:
        value, i = _parse_value(text, i)
        arr.append(value)
        i = _skip_ws(text, i)
        if text[i] == ",":
            i = _skip_ws(text, i + 1)
            continue
        if text[i] == "]":
            return arr, i + 1
        raise DirectoryParseError(f"Expected ',' or ']' at index {i}: {text[i:i+30]!r}")


def extract_org_graph(html_text: str) -> dict:
    """Find and parse the ``{entities:[...],relationships:[...]}`` literal embedded
    in an Organisation Graph HTML export. Raises DirectoryParseError if not found."""
    m = _ENTITIES_MARKER.search(html_text)
    if not m:
        raise DirectoryParseError("Could not find an embedded entities graph in this file")
    obj, _end = _parse_object(html_text, m.start())
    if "entities" not in obj or "relationships" not in obj:
        raise DirectoryParseError("Parsed object is missing 'entities' or 'relationships'")
    return obj


# ── Typed views over the raw graph ──────────────────────────────────────────────


@dataclass
class DirectoryShop:
    id: str
    shop_number: str
    name: str
    ownership: str  # "Franchised" | "Company-owned" | ""
    status: str  # "Open" | "Closed"
    area_code: str = ""
    area: str = ""
    region: str = ""
    country: str = ""
    phone: str = ""
    address: str = ""
    shop_email: str = ""
    franchisee_id: str | None = None


@dataclass
class DirectoryFranchisee:
    id: str
    full_name: str
    business_name: str = ""
    email: str = ""
    mobile: str = ""
    shop_ids: list[str] = field(default_factory=list)

    @property
    def is_multi_site(self) -> bool:
        return len(self.shop_ids) > 1


@dataclass
class DirectoryData:
    shops: list[DirectoryShop]
    franchisees: list[DirectoryFranchisee]


def _fields_to_dict(entity: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in entity.get("fields", []) or []:
        label = f.get("label")
        if label is not None and label not in out:  # first occurrence wins
            out[label] = f.get("value", "")
    return out


def build_directory(graph: dict) -> DirectoryData:
    entities = {e["id"]: e for e in graph.get("entities", [])}

    shops: dict[str, DirectoryShop] = {}
    franchisees: dict[str, DirectoryFranchisee] = {}

    for eid, e in entities.items():
        kind = e.get("kind")
        fv = _fields_to_dict(e)
        if kind == "shop":
            shops[eid] = DirectoryShop(
                id=eid,
                shop_number=(fv.get("Shop Number") or "").strip(),
                name=(fv.get("Shop Name") or e.get("label") or "").strip(),
                ownership=fv.get("Ownership", ""),
                status=fv.get("Status", ""),
                area_code=fv.get("Area Code", ""),
                area=fv.get("Area", ""),
                region=fv.get("Region", ""),
                country=fv.get("Country", ""),
                phone=fv.get("Phone", ""),
                address=fv.get("Address", ""),
                shop_email=fv.get("Shop Email", ""),
            )
        elif kind == "franchisee":
            franchisees[eid] = DirectoryFranchisee(
                id=eid,
                full_name=(fv.get("Franchisee") or e.get("label") or "").strip(),
                business_name=fv.get("Business Name", ""),
                email=(fv.get("Email") or "").strip().lower(),
                mobile=fv.get("Mobile", ""),
            )

    for rel in graph.get("relationships", []):
        if rel.get("kind") != "operates":
            continue
        franchisee = franchisees.get(rel.get("from"))
        shop = shops.get(rel.get("to"))
        if franchisee and shop:
            franchisee.shop_ids.append(shop.id)
            shop.franchisee_id = franchisee.id

    return DirectoryData(shops=list(shops.values()), franchisees=list(franchisees.values()))
