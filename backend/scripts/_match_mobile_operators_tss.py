"""One-off: match Mobile Services franchisees to TSS shop numbers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.minit_shops import parse_minit_shops_xlsx_detailed

TSS_PATH = Path(r"c:\Users\samme\Downloads\TSS Dec25 Report (1).xlsx")

# From Mobile Services Franchisees 2026.docx (mobile operator cards, images 31-40)
FRANCHISEES = [
    ("Baldivis", "baldivis@mmms.au", "0481000411", "WA"),
    ("Bribie Island", "bribie@mmms.au", "0401001308", "QLD"),
    ("Broadbeach", "broadbeach@mmms.au", "0451533456", "QLD"),
    ("Burwood", "burwood@mmms.au", "0477738814", "NSW"),
    ("Corporate", "testms@mmms.au", "0415547330", None),
    ("Dapto", "dapto@mmms.au", "0421829661", "NSW"),
    ("Hervey Bay", "hervey.bay@mmms.au", "0481219535", "QLD"),
    ("Kotara", "kotara@mmms.au", "0405951490", "NSW"),
    ("Lismore", "lismore@mmms.au", "0418227422", "NSW"),
    ("Maroochydore", "maroochydore@mmms.au", "0401709953", "QLD"),
    ("Nambour", "nambour@mmms.au", "0490447704", "QLD"),
    ("Noosa", "noosa@mmms.au", "0407965962", "QLD"),
    ("Queanbeyan", "queanbeyan@mmms.au", "0431616319", "NSW"),
    ("Salisbury Downs", "salisbury@mmms.au", "0404744648", "SA"),
    ("Sunnybank Hills", "sunnybank@mmms.au", "0407584643", "QLD"),
    ("Townsville", "townsville@mmms.au", "0407539539", "QLD"),
    ("Werribee", "werribee@mmms.au", "0450171280", "VIC"),
    ("Cairns", "smithfield@mmms.au", "0401822807", "QLD"),
    ("Casuarina", "casuarina@mmms.au", "0889272977", "NT"),
    ("Ingle Farm", "mount.barker@mmms.au", "0423707295", "SA"),
    ("Warringah", None, "0438338540", "NSW"),
    ("Narellan", "narellan@mmms.au", "0403727103", "NSW"),
    ("Sylvia Park", "auckland@mmms.nz", "0276611611", "NZ"),
    ("North City", "porirua@mmms.nz", "0800782575", "NZ"),
    ("The Base Hamilton", "hamilton@mmms.nz", "02102399777", "NZ"),
    ("Johnsonville", "mount.wellington@mmms.nz", "0211782575", "NZ"),
]

# Extra search tokens from email local-part
EMAIL_ALIASES = {
    "smithfield": "Cairns",
    "mount.barker": "Ingle Farm",
    "mount.wellington": "Johnsonville",
    "auckland": "Sylvia Park",
    "porirua": "North City",
    "hamilton": "The Base Hamilton",
    "sunnybank": "Sunnybank Hills",
    "hervey.bay": "Hervey Bay",
}


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def main() -> None:
    parsed = parse_minit_shops_xlsx_detailed(TSS_PATH)
    shops = parsed.shops
    print(f"TSS: {len(shops)} shops from sheet {parsed.sheet_name}\n")

    mobile_kw = [s for s in shops if "mobile" in s.name.lower()]
    print(f"Rows with 'mobile' in name: {len(mobile_kw)}")
    for s in mobile_kw:
        print(f"  #{s.shop_number:>6} {s.name:45} {s.area or '':18} {s.region or ''}")
    print()

    print("=== Franchisee -> TSS shop number match ===")
    print(f"{'Franchisee':<22} {'Email':<22} {'TSS #':<8} {'TSS name':<35} {'Area':<15} {'Match'}")
    print("-" * 110)

    unmatched: list[str] = []
    matched: list[tuple] = []

    for label, email, phone, region in FRANCHISEES:
        tokens = [_norm(w) for w in label.replace("/", " ").split() if len(w) > 2]
        if email:
            local = email.split("@")[0].lower()
            if local in EMAIL_ALIASES:
                tokens.extend(_norm(w) for w in EMAIL_ALIASES[local].split() if len(w) > 2)
            tokens.append(_norm(local.replace(".", "")))

        hits = []
        for s in shops:
            hay = _norm(f"{s.name} {s.area or ''}")
            score = sum(1 for t in tokens if t in hay)
            if score > 0 and (region is None or (s.region or "").upper() == region or region in (s.area or "").upper()):
                hits.append((score, s))
            elif score >= 2:
                hits.append((score, s))
        hits.sort(key=lambda x: (-x[0], x[1].shop_number))

        if hits:
            best = hits[0][1]
            how = f"name/area token score {hits[0][0]}"
            if len(hits) > 1 and hits[1][0] == hits[0][0]:
                how += " (ambiguous)"
            matched.append((label, best.shop_number, best.name, how))
            print(
                f"{label:<22} {(email or '-'):<22} {best.shop_number:<8} {best.name[:35]:<35} {(best.area or '')[:15]:<15} {how}"
            )
        else:
            unmatched.append(label)
            print(f"{label:<22} {(email or '-'):<22} {'—':<8} {'NO MATCH':<35} {'':15} ")

    print(f"\nMatched: {len(matched)} / {len(FRANCHISEES)}")
    if unmatched:
        print("Unmatched:", ", ".join(unmatched))

    # Show shop numbers in 39xx range (operator convention?)
    op_range = [s for s in shops if s.shop_number.startswith("39") or s.shop_number.startswith("38")]
    print(f"\nTSS shops with shop # 38xx/39xx: {len(op_range)}")
    for s in sorted(op_range, key=lambda x: int(x.shop_number))[:40]:
        print(f"  #{s.shop_number} {s.name} | {s.area} | {s.region}")
    if len(op_range) > 40:
        print(f"  ... and {len(op_range) - 40} more")


if __name__ == "__main__":
    main()
