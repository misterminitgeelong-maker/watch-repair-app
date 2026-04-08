"""Add structured boolean flags to all vehicle_key_specs entries."""
import json
from pathlib import Path

SEED = Path(__file__).parent.parent

with open(SEED / "vehicle_key_specs.json", encoding="utf-8") as f:
    data = json.load(f)

entries = data["entries"]

PIN_REQUIRED_PATTERNS = ["ezs", "pin required", "dealer pin", "security code", "pin code"]
DEALER_ONLY_NOTES = ["refer out", "refer to dealer", "dealer only", "specialist / refer", "not viable"]


def flags_for(e):
    make = (e.get("make") or "").lower()
    method = (e.get("likely_method") or "").lower()
    notes = (e.get("typical_notes") or "").lower()
    complexity = (e.get("akl_complexity") or "").lower()
    transponder = (e.get("transponder_system") or "").lower()
    immo = (e.get("immobiliser_family") or "").lower()
    key_type = (e.get("key_type") or "").lower()
    yf = e.get("year_from") or 0

    # bsu_required — battery support unit strongly recommended
    bsu = False
    if yf >= 2015:
        bsu = True
    elif yf >= 2012 and any(x in make for x in ["toyota", "bmw", "mercedes", "audi", "volkswagen", "ford", "mazda", "honda"]):
        bsu = True
    if any(x in immo for x in ["dst80", "dst aes", "fem", "bdc", "cas4", "cas3", "ezs", "infrared", "mqb", "mqb adv"]):
        bsu = True

    # pin_required — security access PIN needed before programming
    pin = False
    if make in {"hyundai", "kia"} and yf >= 2013:
        pin = True
    if "honda" in make and ("hitag" in transponder or "smart" in key_type or "prox" in key_type):
        pin = True
    if "subaru" in make and yf >= 2018:
        pin = True
    if "mitsubishi" in make and yf >= 2020:
        pin = True
    if any(p in notes for p in PIN_REQUIRED_PATTERNS):
        pin = True
    if "pin" in method:
        pin = True

    # eeprom_required
    eeprom = "eeprom" in method or "eeprom" in notes

    # obd_programmable — can do at least some work via OBD
    obd = "obd" in method
    if not obd and not eeprom:
        obd = True  # assume OBD if method not specified otherwise

    # dealer_required — genuinely cannot do without dealer equipment
    dealer = False
    if any(x in notes for x in DEALER_ONLY_NOTES):
        dealer = True
    if "specialist / refer" in method:
        dealer = True
    if "very high" in complexity and any(x in make for x in ["tesla", "polestar", "byd", "genesis"]):
        dealer = True

    return {
        "bsu_required": bsu,
        "pin_required": pin,
        "eeprom_required": eeprom,
        "obd_programmable": obd,
        "dealer_required": dealer,
    }


for e in entries:
    e.update(flags_for(e))

data["entries"] = entries
data["version"] = 3

out = SEED / "vehicle_key_specs_v2.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

bsu = sum(1 for e in entries if e.get("bsu_required"))
pin = sum(1 for e in entries if e.get("pin_required"))
eeprom = sum(1 for e in entries if e.get("eeprom_required"))
dealer = sum(1 for e in entries if e.get("dealer_required"))
obd = sum(1 for e in entries if e.get("obd_programmable"))
print(f"Written {len(entries)} entries to {out}")
print(f"  bsu_required:    {bsu}")
print(f"  pin_required:    {pin}")
print(f"  eeprom_required: {eeprom}")
print(f"  obd_programmable:{obd}")
print(f"  dealer_required: {dealer}")
