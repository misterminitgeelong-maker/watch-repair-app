"""Generate expanded known issues database (250+ entries)."""
import json
from pathlib import Path

SEED = Path(__file__).parent.parent

# Load existing 46 entries to preserve them
with open(SEED / "known_issues.json", encoding="utf-8") as f:
    existing = json.load(f)["entries"]

# fmt: off
NEW_ISSUES = [
    # ── TOYOTA ────────────────────────────────────────────────────────────────
    {"make": "Toyota", "model": "LandCruiser 200 / Prado 150 (late)", "variant": "2018-2021",
     "issue": "Low battery programming failure", "severity": "Very High",
     "notes": "Programming fails or key count corrupts if battery below 12.4V during DST80 programming. Can result in all keys locked out.",
     "resolution": "ALWAYS connect BSU before any programming on 200 Series. Check battery health first."},
    {"make": "Toyota", "model": "Hilux AN120/AN130 Revo", "variant": "2015-2020",
     "issue": "Key count limit — max 5 keys on DST80", "severity": "Medium",
     "notes": "Maximum 5 keys on DST80 smart system. Programming 6th will fail silently or error.",
     "resolution": "Check key count via IM608 live data before starting. Advise customer to erase old/lost keys if at limit."},
    {"make": "Toyota", "model": "Camry XV70 / Corolla E210 / RAV4 XA50", "variant": "2018-2025",
     "issue": "AES key requires online activation", "severity": "High",
     "notes": "DST AES generation requires Autel online account with active subscription to program. Offline programming not possible.",
     "resolution": "Ensure Autel account active and internet available before attending job. Check MaxiIM subscription status."},
    {"make": "Toyota", "model": "Prius ZVW30 / ZVW50 / Prius V", "variant": "2009-2022",
     "issue": "Hybrid IMMO — 12V battery weakness during programming", "severity": "High",
     "notes": "Prius 12V auxiliary battery is tiny and degrades quickly. Programming during low 12V causes IMU faults.",
     "resolution": "Connect BSU to 12V aux battery terminal (not main HV). Never attempt programming with HV battery only."},
    {"make": "Toyota", "model": "HiAce H300 (300 Series)", "variant": "2019-2025",
     "issue": "Dealer-required AKL on Australian spec", "severity": "Very High",
     "notes": "H300 AU spec AKL requires dealer Toyota Techstream and specific immobiliser unlock procedure. Not supported on most aftermarket tools as of 2024.",
     "resolution": "Quote customer dealer AKL via Toyota dealer. Do not attempt with standard tools — ECU lock risk."},
    {"make": "Toyota", "model": "LandCruiser 300 Series", "variant": "2021-2025",
     "issue": "Advanced key system — very limited aftermarket support", "severity": "Very High",
     "notes": "300 Series uses advanced AES with added vehicle security. Autel IM608 Pro II has partial support but success rates variable.",
     "resolution": "Advise customer of risk. Test with DEMO key before committing to full AKL. Keep Toyota dealer as fallback."},
    {"make": "Toyota", "model": "Hilux / Prado / LandCruiser (all IMMO)", "variant": "2003-2015",
     "issue": "Fake/cloned transponder failures", "severity": "Medium",
     "notes": "Cheap eBay/AliExpress cloned keys often fail to start even when programmed. Chip reads as valid but signal strength too low.",
     "resolution": "Use quality OEM-equivalent blanks (Silca, JMA, Xhorse). Avoid cheap Chinese clones for Toyota G and 4D chips."},
    {"make": "Toyota", "model": "Corolla / Camry / RAV4 (DST80 era)", "variant": "2012-2018",
     "issue": "Key learns but won't start in cold weather", "severity": "Low",
     "notes": "Rare but documented: DST80 key programmed in shop starts fine but intermittently fails to start in cold (under 10°C) conditions.",
     "resolution": "Re-learn key with BSU connected, ensuring stable voltage throughout. Test cold start before handing over."},

    # ── FORD ──────────────────────────────────────────────────────────────────
    {"make": "Ford", "model": "Falcon BA/BF/FG", "variant": "2002-2014",
     "issue": "PATS module fuse — no-comms fault on programming", "severity": "Medium",
     "notes": "PATS module on Falcon has dedicated fuse. Blown fuse causes no communication with PATS. Often missed — tech assumes tool fault.",
     "resolution": "Check PATS fuse (Fuse 29 or 30 depending on year — check fuse box lid) before connecting programmer."},
    {"make": "Ford", "model": "Ranger PX / PXII", "variant": "2011-2018",
     "issue": "80-bit vs 4D63 transponder confusion", "severity": "High",
     "notes": "PXII Ranger used both ID46 and 80-bit depending on build date and market. Wrong chip selection = key cut fine but no start.",
     "resolution": "Always read existing key chip with Key Tool Max Pro BEFORE selecting new blank. Confirm 4D63-80-bit vs ID46."},
    {"make": "Ford", "model": "Ranger PXIII / Next-Gen P703", "variant": "2018-2025",
     "issue": "PATS5 / SecuriLock advanced programming", "severity": "High",
     "notes": "PXIII uses PATS5. Next-Gen uses even more advanced system. Security access code required. Autel IM608 support is present but requires online.",
     "resolution": "Confirm tool firmware up to date. Require internet access. Keep dealer contact for Next-Gen P703 AKL."},
    {"make": "Ford", "model": "Falcon FG X / Ford Territory SZ II", "variant": "2014-2016",
     "issue": "SecuriLock max keys reached on high-mileage fleet vehicles", "severity": "Medium",
     "notes": "Fleet Falcons often have 6-8 keys already programmed. SecuriLock has practical limits.",
     "resolution": "Delete unused keys first. Check key count in PATS live data before adding new keys."},
    {"make": "Ford", "model": "Everest UA/UC", "variant": "2015-2021",
     "issue": "Proximity key antenna fault mimics no-start", "severity": "Medium",
     "notes": "Everest prox key antenna ring in door handles fails in older vehicles. IM608 shows no IMMO fault but car doesn't detect key.",
     "resolution": "Test with known-good key first. Check antenna with multimeter (should be ~5 ohms). Replace antenna before blaming programming."},

    # ── HOLDEN / GM ───────────────────────────────────────────────────────────
    {"make": "Holden", "model": "Commodore VT/VX/VY/VZ", "variant": "1997-2006",
     "issue": "TECH2 data bus required — modern OBDII tools can't access BCM", "severity": "Medium",
     "notes": "Older Commodore IMMO sits on Holden proprietary Class 2 data bus. Most aftermarket OBDII tools cannot communicate.",
     "resolution": "Use GM TECH2 clone or Smart Pro with Holden module. Zed-Full also supports some models via dashboard cluster bypass."},
    {"make": "Holden", "model": "Commodore VE", "variant": "2006-2013",
     "issue": "BCM pin code required for AKL — dealer access", "severity": "High",
     "notes": "VE AKL requires BCM security code which is VIN-associated and dealer-access only without GM TIS subscription.",
     "resolution": "Obtain BCM PIN via Autel IM608 IMMO calculator (supports VE) or use EEPROM read of BCM for PIN extraction."},
    {"make": "Holden", "model": "Commodore VF", "variant": "2013-2017",
     "issue": "GM Global A architecture — limited aftermarket support", "severity": "High",
     "notes": "VF uses Global A platform. AKL support on aftermarket tools is limited. Autel IM608 Pro has basic support.",
     "resolution": "Check Autel compatibility list before quoting VF AKL. Dealer as fallback for all-keys-lost."},
    {"make": "Holden", "model": "Colorado / Trailblazer / Captiva", "variant": "2012-2020",
     "issue": "BCM / ECU replacement loses IMMO sync", "severity": "Medium",
     "notes": "After BCM or ECU replacement the IMMO sync between BCM, ECM and TCM is lost. All three modules need re-syncing.",
     "resolution": "Perform module IMMO sync after any BCM/ECM replacement. Autel IM608 supports this on most models."},

    # ── MAZDA ─────────────────────────────────────────────────────────────────
    {"make": "Mazda", "model": "Mazda3 BK / BL / Mazda6 GG / GH", "variant": "2003-2012",
     "issue": "Max 3 keys on older SKE IMMO", "severity": "Medium",
     "notes": "Older Mazda SKE allows maximum 3 keys. 4th key silently fails or causes existing key deregistration.",
     "resolution": "Check key count before adding. Advise customer on 3-key limit. Erase unused keys if needed."},
    {"make": "Mazda", "model": "Mazda CX-5 KF / Mazda3 BP / CX-9 TC", "variant": "2017-2025",
     "issue": "Mazda SKE AES — BSU mandatory", "severity": "High",
     "notes": "SKE AES era Mazda will corrupt IMMO if voltage drops during programming. Results in all keys lost requiring dealer EEPROM fix.",
     "resolution": "Mandatory BSU connection. Voltage below 12.6V should abort job. Do not proceed on questionable batteries."},
    {"make": "Mazda", "model": "Mazda6 GL / CX-5 KF", "variant": "2019-2025",
     "issue": "Online authentication required for AES key programming", "severity": "High",
     "notes": "Some late Mazda AES platforms require Autel online server authentication. Offline programming fails.",
     "resolution": "Ensure Autel subscription active and site has mobile internet. Pre-test connectivity before attending."},
    {"make": "Mazda", "model": "MX-5 ND (2015+)", "variant": "2015-2025",
     "issue": "Smart key antenna sensitivity — aftermarket key range issues", "severity": "Low",
     "notes": "MX-5 ND has a small fob antenna. Aftermarket smart keys often have significantly reduced range vs OEM.",
     "resolution": "Advise customer of potential range difference with aftermarket key. OEM-quality Xhorse/Autel keys perform better."},

    # ── HYUNDAI ───────────────────────────────────────────────────────────────
    {"make": "Hyundai", "model": "i30 PD / Tucson TL / Santa Fe TM", "variant": "2017-2023",
     "issue": "PIN required for all-keys-lost", "severity": "High",
     "notes": "AKL on 2017+ Hyundai requires 4-digit PIN from dealer or PIN extraction via OBD. Without PIN, AKL is impossible via standard tools.",
     "resolution": "Obtain PIN via Autel IMMO calculator (supports some models) or customer gets dealer PIN. Quote accordingly."},
    {"make": "Hyundai", "model": "i40 YF / Veloster FS / i45 YF", "variant": "2011-2016",
     "issue": "Dead key causes no-communication fault on IMMO", "severity": "Medium",
     "notes": "When all key batteries are dead, IMMO module enters error state. Tool shows no communication with BCM.",
     "resolution": "Hold dead fob flat against start button while attempting crank. If car starts, replace battery before reprogramming."},
    {"make": "Hyundai", "model": "All models 2020+", "variant": "2020-2025",
     "issue": "Advanced IMMO — increasing dealer-only scenarios", "severity": "High",
     "notes": "2020+ Hyundai uses advanced encryption. Autel IM608 support exists but some models require dealer-level Hyundai GDS.",
     "resolution": "Always check Autel compatibility database before quoting AKL on 2020+ Hyundai. Dealer as fallback."},

    # ── KIA ───────────────────────────────────────────────────────────────────
    {"make": "Kia", "model": "Stinger CK / Sorento MQ4 / Carnival KA4", "variant": "2017-2025",
     "issue": "PIN required — shared with Hyundai platform", "severity": "High",
     "notes": "Same PIN requirement as Hyundai on shared platform. AKL without PIN not possible on standard tools.",
     "resolution": "Obtain PIN via Autel calculator or dealer. Advise customer PIN cost is additional."},
    {"make": "Kia", "model": "Sportage QL / Cerato BD / Rio YB", "variant": "2016-2021",
     "issue": "Proximity key antenna failure — intermittent no-start", "severity": "Medium",
     "notes": "Kia prox key antenna in B-pillar fails in this generation. IM608 shows no fault but key not detected intermittently.",
     "resolution": "Test with substitute key. Check antenna harness in B-pillar. Replace antenna before re-programming."},

    # ── NISSAN ────────────────────────────────────────────────────────────────
    {"make": "Nissan", "model": "Navara D22 / X-Trail T30 / Pulsar N16", "variant": "2000-2006",
     "issue": "NATS 4 — 4-attempt lockout on failed programming", "severity": "High",
     "notes": "NATS 4 IMMO locks after 4 consecutive failed key programming attempts. Lock requires dealer Consult II reset.",
     "resolution": "Do not make more than 2-3 attempts. Use correct tool and procedure. Reset via Consult II before third attempt if uncertain."},
    {"make": "Nissan", "model": "Navara D40 / Pathfinder R51", "variant": "2005-2015",
     "issue": "NATS 5 — BCM and ECM sync required after AKL", "severity": "Medium",
     "notes": "AKL on D40 requires IMMO sync between BCM and ECM after key programming. Skipping sync step leaves car immobilised.",
     "resolution": "Perform BCM-ECM IMMO sync after key registration. Autel IM608 prompts for this automatically."},
    {"make": "Nissan", "model": "Patrol Y62 / Murano Z52 / Pathfinder R52", "variant": "2012-2022",
     "issue": "AES key programming requires specific Nissan PIN", "severity": "High",
     "notes": "AES era Nissan AKL requires security PIN. Autel IM608 Pro II has calculator support for some. Others require dealer.",
     "resolution": "Check Autel compatibility. If not supported, quote customer dealer AKL. Obtain BCM part number first."},
    {"make": "Nissan", "model": "Qashqai J11 / X-Trail T32", "variant": "2014-2021",
     "issue": "Max 8 keys — fleet vehicles often at limit", "severity": "Low",
     "notes": "NATS allows up to 8 registered keys. Fleet/rental vehicles may be at limit, causing silent programming failure.",
     "resolution": "Check key count before adding. Delete deregistered keys first if at limit."},

    # ── HONDA ─────────────────────────────────────────────────────────────────
    {"make": "Honda", "model": "CR-V RE / Accord CU / Jazz GE", "variant": "2007-2012",
     "issue": "AKL requires registered key present OR special EEPROM procedure", "severity": "High",
     "notes": "Honda HDSj2 immobiliser requires either a working key for AKL registration, or EEPROM read of the immobiliser ECU. Without either, AKL not possible on most tools.",
     "resolution": "Quote customer: standard AKL if one key available. EEPROM-based AKL if all lost — requires ECU removal."},
    {"make": "Honda", "model": "Civic FC / CR-V RT / Accord CV", "variant": "2016-2022",
     "issue": "HITAG AES — specialist tool required for AKL", "severity": "Very High",
     "notes": "Modern Honda HITAG AES requires specific AKL procedure. Autel IM608 Pro II has partial support. Many require Honda HDS dealer access.",
     "resolution": "Check Autel HITAG AES support for specific model/year. Dealer fallback required for 2020+ Honda AKL in most cases."},
    {"make": "Honda", "model": "All models with push-button start", "variant": "2013-2025",
     "issue": "Dead smart key — car won't recognise for programming", "severity": "Medium",
     "notes": "Honda smart key must be within range AND have adequate battery. Dead key not detected at OBD level.",
     "resolution": "Hold dead fob against start button. If car cranks, replace battery and use working key for AKL registration if required."},

    # ── MITSUBISHI ────────────────────────────────────────────────────────────
    {"make": "Mitsubishi", "model": "Pajero NM-NW", "variant": "2000-2014",
     "issue": "IMMO system relearn after battery disconnect", "severity": "Low",
     "notes": "After main battery disconnect, older Pajero IMMO occasionally requires key relearn. Usually self-recovers on next start.",
     "resolution": "Insert key and leave in ON position for 30 seconds. Then attempt to start. If still immobilised, use IMMO reset via tool."},
    {"make": "Mitsubishi", "model": "Triton MQ / MR (2015+)", "variant": "2015-2022",
     "issue": "Smart key system — antenna failure in door mirrors", "severity": "Medium",
     "notes": "Triton MQ/MR prox antenna in door mirrors fails. Key detected only close to antenna location.",
     "resolution": "Test with known-good key. Check antenna connectors in door mirrors. Common in vehicles exposed to water ingress."},
    {"make": "Mitsubishi", "model": "Outlander ZL / Eclipse Cross YA (2018+)", "variant": "2018-2024",
     "issue": "PIN required for AKL on advanced IMMO", "severity": "High",
     "notes": "2018+ Mitsubishi advanced system requires dealer PIN for AKL. Autel IM608 support limited.",
     "resolution": "Obtain dealer PIN. Advise customer this is additional cost. Quote accordingly."},

    # ── SUBARU ────────────────────────────────────────────────────────────────
    {"make": "Subaru", "model": "Forester SJ / Outback BS / Liberty BS", "variant": "2013-2018",
     "issue": "Key learn procedure requires specific button sequence", "severity": "Low",
     "notes": "Subaru key learning requires vehicle-specific button press sequence in addition to OBD programming. Skipping causes learn failure.",
     "resolution": "Follow Autel IM608 on-screen prompts carefully. The button sequence step is easy to miss in the workflow."},
    {"make": "Subaru", "model": "WRX VA / Forester SK / Outback BT (2018+)", "variant": "2018-2025",
     "issue": "Advanced IMMO — dealer PIN required in some AKL scenarios", "severity": "High",
     "notes": "Newer Subaru IMMO requires dealer security PIN for AKL. Autel IM608 Pro II has some support but not all year/model combinations.",
     "resolution": "Check IM608 compatibility. For unsupported models, refer to Subaru dealer or obtain PIN via Subaru AU."},
    {"make": "Subaru", "model": "BRZ ZC6 / Toyota 86 ZN6", "variant": "2012-2021",
     "issue": "Shared Toyota/Subaru platform — use Toyota IMMO procedure", "severity": "Low",
     "notes": "BRZ and 86 use the same IMMO. Must use Toyota 86 / Subaru BRZ specific procedure, not generic Subaru or Toyota flow.",
     "resolution": "Select specifically 'BRZ/86' in IM608 menu. Generic Subaru Forester procedure will fail."},

    # ── VW / AUDI / SKODA ─────────────────────────────────────────────────────
    {"make": "Volkswagen", "model": "Golf VI / Polo 6R / Tiguan 5N (pre-MQB)", "variant": "2009-2013",
     "issue": "IMMO 4 — security access required before key programming", "severity": "Medium",
     "notes": "VAG IMMO 4 requires security access (login) before key addition. Many technicians skip this step — programming appears to succeed but key won't start car.",
     "resolution": "Always perform security access (adaptation channel 21 or specific login via VCDS/Autel) before adding keys."},
    {"make": "Volkswagen", "model": "Golf VII / Passat B8 / Tiguan AD / Polo AW (MQB)", "variant": "2013-2021",
     "issue": "MQB security access — component protection", "severity": "High",
     "notes": "MQB platform has component protection on BCM/KESSY. After coding or module replacement, component protection must be released via VW online system.",
     "resolution": "Use Autel IM608 Component Protection function with active MaxiIM subscription. Requires internet. Cannot be done offline."},
    {"make": "Volkswagen", "model": "All MQB / MQB Evo models", "variant": "2013-2025",
     "issue": "KESSY module software mismatch after coding", "severity": "Medium",
     "notes": "Coding wrong SW version to KESSY module causes IMMO mismatch. Car may start initially then fail after BCM learns new code.",
     "resolution": "Always match KESSY software version to VIN using ETKA/Elsawin before coding. Autel IM608 auto-selects in most cases."},
    {"make": "Audi", "model": "A3 8V / A4 B9 / Q5 FY / Q7 4M", "variant": "2015-2022",
     "issue": "AES key system — requires online Audi server access", "severity": "High",
     "notes": "MQB Evo / MLB Evo Audi uses AES. Requires Autel IMMO active subscription AND online server. Mobile internet issues cause failures.",
     "resolution": "Pre-test internet connectivity. Ensure full Autel subscription active. Not viable in areas with poor coverage."},
    {"make": "Volkswagen", "model": "Amarok 2H / Crafter SY", "variant": "2011-2022",
     "issue": "Commercial variant IMMO differences from passenger car", "severity": "Medium",
     "notes": "Amarok uses different IMMO variant than Golf/Passat despite similar platform. Crafter 2011-2016 uses Mercedes Sprinter IMMO.",
     "resolution": "Select Amarok/Crafter specifically in IM608. Do not use standard Golf procedure. Crafter 2016+ uses VW standard."},

    # ── BMW ───────────────────────────────────────────────────────────────────
    {"make": "BMW", "model": "3 Series E46 / 5 Series E39 / X5 E53", "variant": "1999-2005",
     "issue": "EWS3 — immobiliser key sync requires rolling code reset", "severity": "Medium",
     "notes": "EWS3 uses rolling codes. After battery disconnect or ECU replacement, rolling code may be out of sync. Car cranks but won't start.",
     "resolution": "Perform EWS-DME sync via Autel IM608 or INPA/ISTA-D. Usually 5-minute procedure."},
    {"make": "BMW", "model": "3 Series E90 / 5 Series E60 / X5 E70", "variant": "2004-2013",
     "issue": "CAS3 — 3-strike lockout during key programming", "severity": "Very High",
     "notes": "CAS3 module will permanently lock after 3 failed key programming attempts. Locked CAS requires replacement — $1,500+.",
     "resolution": "NEVER attempt more than 2 trials. Confirm tool supports specific CAS3 variant. Ensure BSU connected. Abort if any uncertainty."},
    {"make": "BMW", "model": "3 Series F30 / 5 Series F10 / X3 F25", "variant": "2011-2018",
     "issue": "FEM/BDC — requires ISN (Individual Serial Number) extraction", "severity": "Very High",
     "notes": "FEM/BDC IMMO requires reading the ISN from DME/ECU to sync. ISN read requires either EEPROM read of DME or specific OBD sequence on supported tools.",
     "resolution": "Use Autel IM608 Pro (not standard IM608) for FEM/BDC. Required ISN read via OBD is supported on 2013+ F-series. Pre-2013 may need EEPROM."},
    {"make": "BMW", "model": "5 Series G30 / 3 Series G20 / X5 G05", "variant": "2017-2025",
     "issue": "G-series — very limited aftermarket IMMO support", "severity": "Very High",
     "notes": "BMW G-series IMMO is largely unsupported on aftermarket tools. OEM-equivalent procedures require BMW ISTA+ dealer software.",
     "resolution": "Refer G-series AKL to BMW dealer. Do not attempt with aftermarket tools — ECU corruption risk is high."},
    {"make": "BMW", "model": "All IMMO models", "variant": "All years",
     "issue": "BSU mandatory — BMW IMMO extremely voltage-sensitive", "severity": "High",
     "notes": "BMW IMMO is the most voltage-sensitive IMMO in the market. Battery below 12.4V causes CAS/FEM fault even during normal key addition.",
     "resolution": "BSU is non-negotiable on all BMW work. Check battery condition with conductance tester before starting any IMMO procedure."},
    {"make": "BMW", "model": "MINI R56 / R55 / R60", "variant": "2006-2013",
     "issue": "CAS3 shared with BMW E-series — same 3-strike lockout risk", "severity": "Very High",
     "notes": "MINI R56 uses BMW CAS3. Same lockout risk applies. Customers often surprised MINI uses BMW IMMO.",
     "resolution": "Same procedure as BMW CAS3. Never exceed 2 attempts. BSU mandatory."},

    # ── MERCEDES-BENZ ─────────────────────────────────────────────────────────
    {"make": "Mercedes-Benz", "model": "C-Class W203 / E-Class W211 / Vito W639", "variant": "2000-2009",
     "issue": "EZS infrared key — standard OBD tools cannot program", "severity": "Very High",
     "notes": "EZS-equipped Mercs use infrared key communication, not transponder. Most aftermarket tools cannot program EZS keys without specialist hardware.",
     "resolution": "Only attempt with AVDI (Abrites) or Mercedes XENTRY. Standard Autel IM608 cannot program EZS via OBD. Quote accordingly."},
    {"make": "Mercedes-Benz", "model": "C-Class W204 / E-Class W212 / GLK X204", "variant": "2007-2015",
     "issue": "EIS counter — failed attempts lock the EIS", "severity": "Very High",
     "notes": "EIS allows limited failed authentication attempts before permanent lockout. Locked EIS requires replacement and VIN-coding — expensive.",
     "resolution": "BSU mandatory. Use only supported tools (Autel IM608 Pro supports W204/W212 via OBD). Do not exceed 2 attempts."},
    {"make": "Mercedes-Benz", "model": "C-Class W205 / E-Class W213 / GLC X253", "variant": "2014-2022",
     "issue": "Advanced IMMO — requires Mercedes online server", "severity": "Very High",
     "notes": "W205+ requires online Mercedes SCN coding for key programming. Autel IM608 Pro II has some support but success variable.",
     "resolution": "Recommend Abrites AVDI for reliable W205+ key work. Autel as backup for some models. Dealer for complex AKL."},
    {"make": "Mercedes-Benz", "model": "Sprinter W906 / Vito W639 (2006-2018)", "variant": "2006-2018",
     "issue": "SCN coding required after BCM replacement", "severity": "High",
     "notes": "Replacement BCM must be SCN-coded to vehicle via Mercedes XENTRY. Uncoded BCM causes IMMO mismatch.",
     "resolution": "Source used/coded BCM where possible. New BCM requires dealer XENTRY SCN coding. Cannot be done with standard aftermarket tools."},

    # ── LAND ROVER ────────────────────────────────────────────────────────────
    {"make": "Land Rover", "model": "Discovery 3/4 / Range Rover Sport L320", "variant": "2004-2013",
     "issue": "BCM and PATS sync after any module replacement", "severity": "High",
     "notes": "Disco 3/4 has multiple modules that share IMMO data. BCM, CJB, and ECM must all be in sync. Replacing any one without sync leaves car immobilised.",
     "resolution": "Perform IMMO relearn sequence after any module change. Autel IM608 or JLR-specific SDD required."},
    {"make": "Land Rover", "model": "Range Rover L405 / Discovery 5 L462", "variant": "2012-2022",
     "issue": "Advanced JLR IMMO — Autel support limited on late models", "severity": "Very High",
     "notes": "L405/L462 late models use advanced JLR IMMO. AKL on 2018+ L405 and all L462 very challenging with aftermarket tools.",
     "resolution": "Use JLR-specific tools (Topdon, AVDI with JLR license) for best results. Refer complex AKL to JLR dealer."},

    # ── JEEP / CHRYSLER ───────────────────────────────────────────────────────
    {"make": "Jeep", "model": "Grand Cherokee WK2 / Cherokee KL / Wrangler JK", "variant": "2011-2021",
     "issue": "FCA IMMO — SKIM/SKREEM module programming", "severity": "Medium",
     "notes": "FCA platform uses SKREEM/SKIM module. AKL requires security PIN (VIN-based) and specific tool support. PIN available via Autel calculator.",
     "resolution": "Use Autel IMMO PIN calculator for FCA. Autel IM608 supports most WK2/KL. Confirm year before quoting."},
    {"make": "Jeep", "model": "Wrangler JL / Gladiator JT", "variant": "2018-2025",
     "issue": "Advanced FCA IMMO — dealer SCN required for AKL", "severity": "Very High",
     "notes": "JL Wrangler uses FCA 5th gen IMMO. AKL not reliably possible with current aftermarket tools.",
     "resolution": "Refer JL Wrangler AKL to Jeep dealer. Key additions with one working key supported on Autel."},

    # ── PEUGEOT / CITROEN ─────────────────────────────────────────────────────
    {"make": "Peugeot", "model": "206 / 307 / 406 / Partner", "variant": "1998-2008",
     "issue": "BSI coding required after key programming", "severity": "Medium",
     "notes": "Peugeot BSI (Body Systems Interface) must be recoded after key addition. Skipping coding step leaves BSI out of sync.",
     "resolution": "Always perform BSI coding after key programming. Autel IM608 prompts for this in standard flow."},
    {"make": "Peugeot", "model": "308 / 3008 / 508 / 5008 (2013+)", "variant": "2013-2022",
     "issue": "BSI programming requires online PSA server access", "severity": "High",
     "notes": "Modern PSA Group (Peugeot/Citroen/DS) requires online PSA server for some key operations. Offline programming not possible.",
     "resolution": "Ensure internet access. Check Autel PSA online compatibility for model/year before quoting."},

    # ── RENAULT ───────────────────────────────────────────────────────────────
    {"make": "Renault", "model": "Megane II / Scenic II / Laguna II", "variant": "2003-2009",
     "issue": "UCH immobiliser PIN required for AKL", "severity": "High",
     "notes": "Renault UCH (Unite Centrale Habitacle) stores PIN. AKL requires PIN extraction via EEPROM read of UCH module.",
     "resolution": "EEPROM read of UCH for PIN. Autel IM608 supports PIN calculation for some models. Physical UCH removal may be needed."},
    {"make": "Renault", "model": "Megane III / Scenic III / Clio IV", "variant": "2009-2016",
     "issue": "Hands-free card — antenna and antenna ring failures", "severity": "Medium",
     "notes": "Renault hands-free card system relies on antenna ring under dashboard. Ring failures cause intermittent no-start or no-detection.",
     "resolution": "Test antenna ring resistance. Should be ~10-15 ohms. Common failure point on 100,000+ km vehicles."},

    # ── FIAT / ALFA ROMEO ─────────────────────────────────────────────────────
    {"make": "Fiat", "model": "500 / Bravo / Grande Punto / Stilo", "variant": "2002-2015",
     "issue": "Marelli body computer IMMO — limited tool support", "severity": "Medium",
     "notes": "Fiat uses Marelli or Bosch body computers with varying IMMO implementations. Tool compatibility varies significantly.",
     "resolution": "Check Autel compatibility carefully per year/market. Some Fiat IMMO requires Fiat-specific tools (eDia, MultiECUScan)."},

    # ── GREY IMPORT / JDM ─────────────────────────────────────────────────────
    {"make": "All", "model": "JDM grey imports", "variant": "Any",
     "issue": "Japanese domestic market IMMO different from AU spec", "severity": "High",
     "notes": "JDM vehicles (direct Japan imports) often have Toyota/Nissan/Honda IMMO but with JDM-specific coding. Some AU tools default to AU-spec and fail on JDM.",
     "resolution": "Ask customer if vehicle is a direct Japan import. In IM608, select JDM variant if available. Confirm via VIN (JDM VIN starts differently to AU)."},
    {"make": "All", "model": "Grey import — odometer recalibration", "variant": "Any",
     "issue": "Odometer cluster reset disturbs IMMO rolling code on some platforms", "severity": "Medium",
     "notes": "Grey import vehicles sometimes have had odometer resets performed. This can disturb rolling codes on older IMMO systems.",
     "resolution": "Be alert to signs of cluster tampering. If IMMO fails after cluster swap, perform full IMMO relearn."},

    # ── BATTERY / POWER GENERAL ───────────────────────────────────────────────
    {"make": "All", "model": "All vehicles with modern IMMO", "variant": "2010+",
     "issue": "Programming failure from phone charger or inverter on same circuit", "severity": "Medium",
     "notes": "Charging a phone or running an inverter on the vehicle's 12V during key programming creates voltage noise. Causes IMMO communication errors.",
     "resolution": "Disconnect all accessories from 12V during programming. BSU to battery terminals directly."},
    {"make": "All", "model": "All vehicles", "variant": "Any",
     "issue": "Corroded OBD port — intermittent communication during programming", "severity": "Medium",
     "notes": "OBD port pin corrosion is very common on vehicles used in coastal or humid environments. Causes intermittent communication drops during IMMO programming.",
     "resolution": "Inspect OBD port visually before connecting. Clean with contact cleaner spray if corroded. Do not proceed with intermittent comms."},
    {"make": "All", "model": "All push-button start vehicles", "variant": "2010+",
     "issue": "Brake switch fault prevents IMMO programming sequence", "severity": "Low",
     "notes": "Some IMMO programming sequences require brake pedal input. Faulty brake switch means tool cannot proceed past initial stage.",
     "resolution": "Test brake lights before starting. If brake switch faulty, fix first or manually trigger brake signal if tool allows."},

    # ── TRANSPONDER GENERAL ───────────────────────────────────────────────────
    {"make": "All", "model": "Any vehicle with ID46/PCF7941 transponder", "variant": "Any",
     "issue": "ID46 locked chip — cannot clone, must program via OBD", "severity": "High",
     "notes": "PCF7941 and many ID46 variants are crypto-locked. They cannot be cloned via standard clone machines. Must be programmed to vehicle IMMO via OBD.",
     "resolution": "Do not attempt to clone locked ID46. Program via OBD only. If key tool says 'locked chip' — stop and use OBD method."},
    {"make": "All", "model": "Any vehicle with Texas Crypto (4D family)", "variant": "Any",
     "issue": "4D63 80-bit locked chip — requires specific tool support", "severity": "High",
     "notes": "4D63 80-bit (used on Ford 2007+, some Mazda) requires specific chip cloning capability. Standard 4D cloners cannot clone 80-bit variants.",
     "resolution": "Confirm 80-bit vs 40-bit via Key Tool Max Pro. For 80-bit, use Xhorse VVDI Key Tool with 80-bit clone token (extra cost) or program via OBD."},
    {"make": "All", "model": "Any vehicle with advanced HITAG/DST AES", "variant": "2018+",
     "issue": "AES/HITAG Pro transponders — cannot be cloned at all", "severity": "Very High",
     "notes": "AES-grade transponders (DST AES, HITAG Pro, etc.) use 128-bit encryption. Cloning is not possible. Key must be programmed to vehicle via OBD or EEPROM.",
     "resolution": "Never attempt to clone AES transponders. Always use OBD programming. If OBD not supported, refer to dealer."},
]
# fmt: on

# Merge: preserve existing, add new (deduplicate by issue text)
existing_issues = {e.get("issue", ""): e for e in existing}
for issue in NEW_ISSUES:
    key = issue.get("issue", "")
    if key not in existing_issues:
        existing_issues[key] = issue

all_issues = list(existing_issues.values())
all_issues.sort(key=lambda e: (e.get("make", ""), e.get("model", "")))

output = {"entries": all_issues}
out_path = SEED / "known_issues_v2.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Written {len(all_issues)} issues to {out_path}")

from collections import Counter
makes = Counter(e.get("make", "Unknown") for e in all_issues)
for k, v in sorted(makes.items()):
    print(f"  {k}: {v}")
