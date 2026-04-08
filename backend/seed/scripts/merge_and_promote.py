"""Merge expanded blanks into v2 vehicle specs, promote all v2 files to production names."""
import json, shutil
from pathlib import Path

SEED = Path(__file__).parent.parent

# 1. Load vehicle_key_specs_v2 (has structured flags)
with open(SEED / "vehicle_key_specs_v2.json", encoding="utf-8") as f:
    specs = json.load(f)

# 2. Load expanded blanks
with open(SEED / "expanded_key_blanks.json", encoding="utf-8") as f:
    expanded = json.load(f)["entries"]

# Merge: index existing blanks by blank_reference, overwrite/add from expanded
existing_blanks = {b["blank_reference"]: b for b in (specs.get("key_blanks") or [])}
for b in expanded:
    existing_blanks[b["blank_reference"]] = b

# Convert machine profile fields to machine_profiles dict for consistency with existing structure
def normalise_blank(b):
    # If already has machine_profiles key, leave as-is
    if "machine_profiles" in b:
        return b
    mp = {}
    for field, label in [
        ("dolphin_xp005l", "Dolphin XP-005L"),
        ("condor_xc_mini_plus_ii", "Condor XC-Mini Plus II"),
        ("silca_alpha_pro", "Silca Alpha Pro"),
        ("silca_futura_pro", "Silca Futura Pro"),
    ]:
        v = b.pop(field, None)
        if v:
            mp[label] = v
    if mp:
        b["machine_profiles"] = mp
    return b

merged_blanks = [normalise_blank(b) for b in existing_blanks.values()]
merged_blanks.sort(key=lambda b: b.get("blank_reference", ""))

specs["key_blanks"] = merged_blanks
specs["version"] = 3

# 3. Promote vehicle_key_specs_v2 -> vehicle_key_specs.json (backup original first)
shutil.copy2(SEED / "vehicle_key_specs.json", SEED / "vehicle_key_specs_v1_backup.json")
with open(SEED / "vehicle_key_specs.json", "w", encoding="utf-8") as f:
    json.dump(specs, f, ensure_ascii=False, indent=2)
print(f"vehicle_key_specs.json: {len(specs['entries'])} entries, {len(merged_blanks)} blanks (v3)")

# 4. Promote known_issues_v2 -> known_issues.json
shutil.copy2(SEED / "known_issues.json", SEED / "known_issues_v1_backup.json")
shutil.copy2(SEED / "known_issues_v2.json", SEED / "known_issues.json")
with open(SEED / "known_issues.json", encoding="utf-8") as f:
    issues = json.load(f)
print(f"known_issues.json: {len(issues['entries'])} entries")

# 5. Also update cutting_profiles.json to include machine_profiles dict format
with open(SEED / "cutting_profiles.json", encoding="utf-8") as f:
    cp_data = json.load(f)
cp_entries = cp_data["entries"]
normalised_cp = []
for cp in cp_entries:
    cp = dict(cp)
    mp = {}
    for field, label in [
        ("dolphin_xp005l", "Dolphin XP-005L"),
        ("condor_xc_mini_plus_ii", "Condor XC-Mini Plus II"),
        ("silca_alpha_pro", "Silca Alpha Pro"),
        ("silca_futura_pro", "Silca Futura Pro"),
    ]:
        v = cp.get(field)
        if v:
            mp[label] = v
    if mp:
        cp["machine_profiles"] = mp
    normalised_cp.append(cp)
with open(SEED / "cutting_profiles.json", "w", encoding="utf-8") as f:
    json.dump({"entries": normalised_cp}, f, ensure_ascii=False, indent=2)
print(f"cutting_profiles.json: {len(normalised_cp)} entries (machine_profiles dict added)")

print("Done. All seed files promoted to production names.")
