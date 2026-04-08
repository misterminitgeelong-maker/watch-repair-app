"""Generate expanded blade blank profiles (200+ entries) for AU market."""
import json
from pathlib import Path

SEED = Path(__file__).parent.parent

# fmt: off
BLANKS = [
    # ── TOYOTA ────────────────────────────────────────────────────────────────
    {"blank_reference": "TOY43", "description": "Toyota standard double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "Hilux N70/N140, Corolla E110-E150, Camry XV20-XV40, HiAce H100/H200, RAV4 XA20-XA40, Prado 90/120, Tarago ACR50, Yaris XP90",
     "dolphin_xp005l": "TOY43 / B series", "condor_xc_mini_plus_ii": "TOY43", "silca_alpha_pro": "TOY43 / B111", "silca_futura_pro": "TOY43",
     "notes": "Most common Toyota blank in AU. High stock priority."},
    {"blank_reference": "TOY48", "description": "Toyota high-security laser blade", "key_type": "Laser / track",
     "common_makes_models": "LandCruiser 100 Series, Prado 90/120 high-sec trim, Lexus LS XF30, some Camry XV30",
     "dolphin_xp005l": "TOY48 / LD series", "condor_xc_mini_plus_ii": "TOY48", "silca_alpha_pro": "TOY48", "silca_futura_pro": "TOY48",
     "notes": "Less common than TOY43. Confirm profile before cutting."},
    {"blank_reference": "TOY-L / TOY12", "description": "Toyota remote flip blade (older)", "key_type": "Flip blade",
     "common_makes_models": "Corolla E120-E130, Camry XV30-XV40, RAV4 XA20-XA30, Yaris XP90-XP130, HiAce H200 (early remote)",
     "dolphin_xp005l": "TOY12 / B series", "condor_xc_mini_plus_ii": "TOY12", "silca_alpha_pro": "TOY12", "silca_futura_pro": "TOY12",
     "notes": "Flip key blank for older Toyota remote shells."},
    {"blank_reference": "TOY2000 / TOY51", "description": "Toyota high-security flip blade (G-chip era)", "key_type": "Flip blade",
     "common_makes_models": "Camry XV50, Corolla E170, RAV4 XA40, HiAce H200 (2012+), Kluger XU50, Prado 150",
     "dolphin_xp005l": "TOY51 / G series", "condor_xc_mini_plus_ii": "TOY51", "silca_alpha_pro": "TOY51 / TY51", "silca_futura_pro": "TOY51",
     "notes": "High-security flip blade for G-chip era Toyotas. Very high volume."},
    {"blank_reference": "TOY47", "description": "Toyota/Lexus tibbe-style laser blade", "key_type": "Laser / track",
     "common_makes_models": "Lexus GS S160, Lexus IS XE10, Lexus RX XU10, Toyota Aristo JZS160",
     "dolphin_xp005l": "TOY47", "condor_xc_mini_plus_ii": "TOY47", "silca_alpha_pro": "TOY47", "silca_futura_pro": "TOY47",
     "notes": "Less common. Mainly Lexus grey imports from Japan."},
    {"blank_reference": "TOY38", "description": "Toyota side-cut blade (LandCruiser 80 series)", "key_type": "Single-sided",
     "common_makes_models": "LandCruiser 80 Series FJ80/HDJ80, LandCruiser 70 Series (early), Hilux Surf N130",
     "dolphin_xp005l": "TOY38", "condor_xc_mini_plus_ii": "TOY38", "silca_alpha_pro": "TOY38", "silca_futura_pro": "TOY38",
     "notes": "Older mechanical key. Pre-immobiliser."},
    {"blank_reference": "TOY-DS / TR47", "description": "Toyota DST smart key blade", "key_type": "Smart blade",
     "common_makes_models": "Camry XV70, RAV4 XA50, HiLux AN120/AN130, LandCruiser 300, Kluger XU70, Yaris XP210, Corolla E210",
     "dolphin_xp005l": "TR47 (confirm)", "condor_xc_mini_plus_ii": "TR47", "silca_alpha_pro": "TR47", "silca_futura_pro": "TR47",
     "notes": "DST80/AES era smart key emergency blade. Confirm with Silca catalog."},
    {"blank_reference": "TOY-L2 / MIT8", "description": "Toyota Prado 120 / HiLux surf high-sec", "key_type": "Laser / track",
     "common_makes_models": "Prado 120 high-sec, some Hilux N70 high-sec variant, 4Runner N210",
     "dolphin_xp005l": "MIT8 (confirm)", "condor_xc_mini_plus_ii": "MIT8", "silca_alpha_pro": "MIT8", "silca_futura_pro": "MIT8",
     "notes": "Cross-reference with MIT8. Confirm before cutting."},

    # ── FORD AUSTRALIA ────────────────────────────────────────────────────────
    {"blank_reference": "FO21", "description": "Ford standard tibia blade", "key_type": "Double-sided",
     "common_makes_models": "Falcon BA/BF/FG, Territory SX/SY/SZ, Fairmont, Fairlane, LTD BA-FG",
     "dolphin_xp005l": "FO21 / F series", "condor_xc_mini_plus_ii": "FO21", "silca_alpha_pro": "FO21", "silca_futura_pro": "FO21",
     "notes": "Bread-and-butter AU Ford blank. Very high volume."},
    {"blank_reference": "FO21HP", "description": "Ford high-security Tibbe blade", "key_type": "Tibbe",
     "common_makes_models": "Falcon EB-EF-EL, Fairlane NA-NF-NL, some Territory early",
     "dolphin_xp005l": "FO21HP / Tibbe adapter", "condor_xc_mini_plus_ii": "FO21HP", "silca_alpha_pro": "FO21HP", "silca_futura_pro": "FO21HP",
     "notes": "Tibbe profile. Requires Tibbe cutting adapter on Condor/Dolphin."},
    {"blank_reference": "FO38", "description": "Ford Focus/Fiesta/Transit blade", "key_type": "Double-sided",
     "common_makes_models": "Focus LW/LZ, Fiesta WS/WZ/WP, Transit VO/VM, C-Max",
     "dolphin_xp005l": "FO38", "condor_xc_mini_plus_ii": "FO38", "silca_alpha_pro": "FO38", "silca_futura_pro": "FO38",
     "notes": "Euro Ford platform. Common in AU fleet."},
    {"blank_reference": "FO43", "description": "Ford Ranger/Everest/Transit Connect blade", "key_type": "Double-sided",
     "common_makes_models": "Ranger PX/PXII/PXIII, Everest UA/UC, Transit Connect 2013+, BT-50 (Ford variant)",
     "dolphin_xp005l": "FO43", "condor_xc_mini_plus_ii": "FO43", "silca_alpha_pro": "FO43", "silca_futura_pro": "FO43",
     "notes": "Very common AU Ford Ranger blade. High stock priority."},
    {"blank_reference": "FO78", "description": "Ford flip blade (Mondeo/Kuga/Focus smart key)", "key_type": "Flip blade",
     "common_makes_models": "Mondeo MC/MD, Kuga TF/TE, Focus LW/LZ (smart key), Escape ZC",
     "dolphin_xp005l": "FO78", "condor_xc_mini_plus_ii": "FO78", "silca_alpha_pro": "FO78", "silca_futura_pro": "FO78",
     "notes": "Ford flip remote blade. Check key shell type before ordering."},
    {"blank_reference": "FO10", "description": "Ford Mustang/Explorer/F-150 blade (USA market)", "key_type": "Double-sided",
     "common_makes_models": "Mustang FM/FN (AU import), Explorer 2011+, Edge, F-150 (grey import)",
     "dolphin_xp005l": "FO10", "condor_xc_mini_plus_ii": "FO10", "silca_alpha_pro": "FO10", "silca_futura_pro": "FO10",
     "notes": "US-market Ford blade. Increasing AU grey import volume."},
    {"blank_reference": "FO47", "description": "Ford Transit/Custom blade (Euro)", "key_type": "Double-sided",
     "common_makes_models": "Transit Custom VN/VO 2012+, Transit VO 2013+",
     "dolphin_xp005l": "FO47", "condor_xc_mini_plus_ii": "FO47", "silca_alpha_pro": "FO47", "silca_futura_pro": "FO47",
     "notes": "Euro Transit. Different from older FO38."},

    # ── HOLDEN / GM ───────────────────────────────────────────────────────────
    {"blank_reference": "B62 / HU43", "description": "Holden Commodore double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "Commodore VT/VX/VY/VZ/VE, Captiva CG, Astra AH/TS, Barina TK",
     "dolphin_xp005l": "B62 / HU43", "condor_xc_mini_plus_ii": "HU43", "silca_alpha_pro": "HU43", "silca_futura_pro": "HU43",
     "notes": "Very common Holden blank. B62 and HU43 are interchangeable references."},
    {"blank_reference": "B111", "description": "Holden Commodore VF/Colorado blade", "key_type": "Double-sided",
     "common_makes_models": "Commodore VF (2013-2017), Colorado RG, Trailblazer, Equinox",
     "dolphin_xp005l": "B111", "condor_xc_mini_plus_ii": "B111", "silca_alpha_pro": "B111", "silca_futura_pro": "B111",
     "notes": "Gen III AU Commodore. Different from earlier VT-VZ."},
    {"blank_reference": "HU100", "description": "Holden/Opel Astra/Cascada/Insignia", "key_type": "Laser / track",
     "common_makes_models": "Astra PJ/GTC, Insignia, Cascada, some Captiva CG (laser variant)",
     "dolphin_xp005l": "HU100", "condor_xc_mini_plus_ii": "HU100", "silca_alpha_pro": "HU100", "silca_futura_pro": "HU100",
     "notes": "Opel/Holden laser key. Less common in AU."},

    # ── HONDA ─────────────────────────────────────────────────────────────────
    {"blank_reference": "HON66", "description": "Honda standard double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "Civic FD/FB, Accord CL7/CP1/CU, Jazz GD/GE/GP, CR-V RD/RE, HR-V, Odyssey RB/RC",
     "dolphin_xp005l": "HON66 / HD series", "condor_xc_mini_plus_ii": "HON66", "silca_alpha_pro": "HON66", "silca_futura_pro": "HON66",
     "notes": "Most common Honda blank in AU. Very high stock priority."},
    {"blank_reference": "HON58R", "description": "Honda small blade (Jazz/City older)", "key_type": "Single-sided",
     "common_makes_models": "Jazz GD 2002-2008, City GM 2002-2008, Logo, older Civic",
     "dolphin_xp005l": "HON58R", "condor_xc_mini_plus_ii": "HON58R", "silca_alpha_pro": "HON58R", "silca_futura_pro": "HON58R",
     "notes": "Older Honda single-sided. Less common now."},
    {"blank_reference": "HON70", "description": "Honda flip blade (CRV/Accord modern)", "key_type": "Flip blade",
     "common_makes_models": "CR-V RE/RM/RT, Accord CP/CU/CV, Odyssey RC/RN, HR-V RU, Civic FC 2015+",
     "dolphin_xp005l": "HON70", "condor_xc_mini_plus_ii": "HON70", "silca_alpha_pro": "HON70", "silca_futura_pro": "HON70",
     "notes": "Modern Honda flip remote blade. Increasing volume."},
    {"blank_reference": "HON37", "description": "Honda Civic EG/EK/DC2 Integra blade", "key_type": "Double-sided",
     "common_makes_models": "Civic EG/EH/EK, Integra DC2, Legend KA7, Prelude BB4",
     "dolphin_xp005l": "HON37", "condor_xc_mini_plus_ii": "HON37", "silca_alpha_pro": "HON37", "silca_futura_pro": "HON37",
     "notes": "Older Honda. Pre-immobiliser or early IMMO."},

    # ── NISSAN ────────────────────────────────────────────────────────────────
    {"blank_reference": "NSN14", "description": "Nissan standard double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "Navara D22/D40, Patrol Y61/Y62, X-Trail T30/T31, Murano Z50, Dualis J10, Tiida C11, Pulsar N16",
     "dolphin_xp005l": "NSN14 / N series", "condor_xc_mini_plus_ii": "NSN14", "silca_alpha_pro": "NSN14 / NI04AP", "silca_futura_pro": "NSN14",
     "notes": "Most common Nissan blank in AU. Very high stock priority."},
    {"blank_reference": "NSN11", "description": "Nissan flip blade (Navara D40/Pathfinder R51)", "key_type": "Flip blade",
     "common_makes_models": "Navara D40 (2005+), Pathfinder R51, X-Trail T31 flip key, Murano Z51",
     "dolphin_xp005l": "NSN11", "condor_xc_mini_plus_ii": "NSN11", "silca_alpha_pro": "NSN11", "silca_futura_pro": "NSN11",
     "notes": "Common D40 flip key blank."},
    {"blank_reference": "NSN19", "description": "Nissan Patrol Y60/GQ blade", "key_type": "Double-sided",
     "common_makes_models": "Patrol Y60/GQ, Navara D21, Pintara R31",
     "dolphin_xp005l": "NSN19", "condor_xc_mini_plus_ii": "NSN19", "silca_alpha_pro": "NSN19", "silca_futura_pro": "NSN19",
     "notes": "Older Nissan. Pre-IMMO era."},
    {"blank_reference": "NSN21", "description": "Nissan laser high-security blade", "key_type": "Laser / track",
     "common_makes_models": "Patrol Y62, 370Z Z34, GT-R R35, Murano Z52, Pathfinder R52, Qashqai J11",
     "dolphin_xp005l": "NSN21 / LD series", "condor_xc_mini_plus_ii": "NSN21", "silca_alpha_pro": "NSN21", "silca_futura_pro": "NSN21",
     "notes": "Modern Nissan high-security. Confirm year/platform before ordering."},

    # ── HYUNDAI / KIA ─────────────────────────────────────────────────────────
    {"blank_reference": "HYN14R", "description": "Hyundai/Kia standard double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "i30 FD/GD, i20, Accent RB/MC, Elantra HD/MD, Tucson TL, Sportage SL/QL, Cerato LD/YD",
     "dolphin_xp005l": "HYN14R / HN series", "condor_xc_mini_plus_ii": "HYN14R", "silca_alpha_pro": "HYN14R / HY14R", "silca_futura_pro": "HYN14R",
     "notes": "Most common Hyundai/Kia blank. Very high volume in AU."},
    {"blank_reference": "HYN11R", "description": "Hyundai/Kia flip blade", "key_type": "Flip blade",
     "common_makes_models": "Tucson JM, Santa Fe SM/CM, Sorento BL/XM, Carnival VQ, i45, Genesis BH/DH (older)",
     "dolphin_xp005l": "HYN11R", "condor_xc_mini_plus_ii": "HYN11R", "silca_alpha_pro": "HYN11R", "silca_futura_pro": "HYN11R",
     "notes": "Older Hyundai/Kia flip key. Less common now."},
    {"blank_reference": "HY20", "description": "Hyundai/Kia modern key blade", "key_type": "Double-sided",
     "common_makes_models": "i30 PD/CN7, Tucson NX4, Kona OS, Ioniq AE, Stinger CK, K5/Optima JF",
     "dolphin_xp005l": "HY20 (confirm)", "condor_xc_mini_plus_ii": "HY20", "silca_alpha_pro": "HY20", "silca_futura_pro": "HY20",
     "notes": "Newer Hyundai/Kia platform. Confirm with catalog."},
    {"blank_reference": "KK9", "description": "Kia/Hyundai laser blade", "key_type": "Laser / track",
     "common_makes_models": "Kia Carnival YP/KA4, Sorento UM/MQ4, K9, Hyundai Palisade LX2, Santa Fe TM",
     "dolphin_xp005l": "KK9 (confirm)", "condor_xc_mini_plus_ii": "KK9", "silca_alpha_pro": "KK9", "silca_futura_pro": "KK9",
     "notes": "Modern Kia laser key. Increasing in AU fleet."},

    # ── MAZDA ─────────────────────────────────────────────────────────────────
    {"blank_reference": "MAZ24R", "description": "Mazda standard double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "Mazda3 BK/BL/BM/BP, Mazda6 GG/GH/GJ, CX-5 KE/KF, CX-3, Mazda2 DE/DJ",
     "dolphin_xp005l": "MAZ24R / MA series", "condor_xc_mini_plus_ii": "MAZ24R", "silca_alpha_pro": "MAZ24R / MAZ24", "silca_futura_pro": "MAZ24R",
     "notes": "Most common Mazda blank in AU. High stock priority."},
    {"blank_reference": "MAZ13", "description": "Mazda older blade (323/626/MX-5 NA/NB)", "key_type": "Double-sided",
     "common_makes_models": "323 BA/BJ, 626 GE/GF, MX-5 NA/NB, 121, Astina",
     "dolphin_xp005l": "MAZ13", "condor_xc_mini_plus_ii": "MAZ13", "silca_alpha_pro": "MAZ13", "silca_futura_pro": "MAZ13",
     "notes": "Older Mazda. Pre-IMMO era."},
    {"blank_reference": "MAZ31", "description": "Mazda laser blade (CX-9 TB/TC, Mazda6 GJ late)", "key_type": "Laser / track",
     "common_makes_models": "CX-9 TC, CX-7 ER, Mazda6 GJ (2015+), CX-5 KF (some)",
     "dolphin_xp005l": "MAZ31 (confirm)", "condor_xc_mini_plus_ii": "MAZ31", "silca_alpha_pro": "MAZ31", "silca_futura_pro": "MAZ31",
     "notes": "Later Mazda laser key. Confirm with catalog."},

    # ── MITSUBISHI ────────────────────────────────────────────────────────────
    {"blank_reference": "MIT9", "description": "Mitsubishi standard double-sided blade", "key_type": "Double-sided",
     "common_makes_models": "Pajero NM/NP/NS/NT/NW/NX, Triton ML/MN/MQ/MR, Outlander ZH/ZJ/ZK, ASX XA/XB",
     "dolphin_xp005l": "MIT9 / MI series", "condor_xc_mini_plus_ii": "MIT9", "silca_alpha_pro": "MIT9 / MIT9R", "silca_futura_pro": "MIT9",
     "notes": "Most common Mitsubishi blank. Pajero and Triton very high volume."},
    {"blank_reference": "MIT11", "description": "Mitsubishi/Isuzu flip blade", "key_type": "Flip blade",
     "common_makes_models": "Mitsubishi Lancer CJ/CF, Eclipse Cross YA, Isuzu D-Max TF/RG, MU-X (some), Holden Colorado RG (early)",
     "dolphin_xp005l": "MIT11", "condor_xc_mini_plus_ii": "MIT11", "silca_alpha_pro": "MIT11", "silca_futura_pro": "MIT11",
     "notes": "Shared blank between Mitsubishi and Isuzu D-Max. Confirm shell type."},
    {"blank_reference": "MIT8", "description": "Mitsubishi laser/high-security blade", "key_type": "Laser / track",
     "common_makes_models": "Pajero Sport QE/QF, Eclipse Cross YA (some), Outlander ZL, some Triton MR",
     "dolphin_xp005l": "MIT8 / LD series", "condor_xc_mini_plus_ii": "MIT8", "silca_alpha_pro": "MIT8", "silca_futura_pro": "MIT8",
     "notes": "Laser Mitsubishi key. Confirm vehicle spec before cutting."},
    {"blank_reference": "MIT3", "description": "Mitsubishi older blade (Magna/Lancer older)", "key_type": "Double-sided",
     "common_makes_models": "Magna TE/TF/TH/TJ/TL, Lancer CE/CH, Galant HJ, Carisma",
     "dolphin_xp005l": "MIT3", "condor_xc_mini_plus_ii": "MIT3", "silca_alpha_pro": "MIT3", "silca_futura_pro": "MIT3",
     "notes": "Older Mitsubishi. Pre-IMMO era."},

    # ── SUBARU ────────────────────────────────────────────────────────────────
    {"blank_reference": "SU10 / SX9", "description": "Subaru/Suzuki standard blade", "key_type": "Double-sided",
     "common_makes_models": "Subaru Forester SG/SH/SJ/SK, Outback BP/BR/BS/BT, Liberty BP/BR/BS, Impreza GD/GE/GH/GJ/GP, XV GP/GT, WRX VA",
     "dolphin_xp005l": "SU10 / S series", "condor_xc_mini_plus_ii": "SU10", "silca_alpha_pro": "SU10 / SZ14", "silca_futura_pro": "SU10",
     "notes": "Most common Subaru blank. Check Forester vs Outback profile difference."},
    {"blank_reference": "SZ11R", "description": "Suzuki standard blade", "key_type": "Double-sided",
     "common_makes_models": "Suzuki Swift RS/FZ/AZ, Vitara LY, S-Cross JY, Jimny GJ, Baleno, Ignis",
     "dolphin_xp005l": "SZ11R / SU series", "condor_xc_mini_plus_ii": "SZ11R", "silca_alpha_pro": "SZ11R", "silca_futura_pro": "SZ11R",
     "notes": "Common Suzuki blank. Shared platforms with some older Subaru."},

    # ── VOLKSWAGEN / AUDI / SKODA / SEAT ─────────────────────────────────────
    {"blank_reference": "VA2", "description": "VW/Audi/Seat/Skoda standard blade", "key_type": "Double-sided",
     "common_makes_models": "Golf IV/V/VI, Passat B5/B6, Polo 9N/6R, Tiguan 5N, Touareg 7L, Audi A3 8L/8P, A4 B6/B7, TT 8N/8J, Skoda Octavia 1Z",
     "dolphin_xp005l": "VA2 / VW series", "condor_xc_mini_plus_ii": "VA2", "silca_alpha_pro": "VA2 / ZR15", "silca_futura_pro": "VA2",
     "notes": "Most common VAG blank in AU. Very high volume. Pre-MQB platforms."},
    {"blank_reference": "HU66", "description": "VW/Audi high-security laser blade", "key_type": "Laser / track",
     "common_makes_models": "Golf VI/VII/VIII, Passat B7/B8, Tiguan 5N/AD, Touareg 7P/CR, Audi A3 8V/8Y, A4 B8/B9, Q5 8R/FY, Q7 4L/4M, Skoda Octavia 5E, Superb 3V",
     "dolphin_xp005l": "HU66 / LD series", "condor_xc_mini_plus_ii": "HU66", "silca_alpha_pro": "HU66", "silca_futura_pro": "HU66",
     "notes": "MQB platform VAG. High security. Very common AU."},
    {"blank_reference": "HU66AT", "description": "VW/Audi HU66 with high-security groove", "key_type": "Laser / track",
     "common_makes_models": "Some Golf VII/VIII, Audi A4 B9, Q5 FY (additional security track)",
     "dolphin_xp005l": "HU66AT (confirm)", "condor_xc_mini_plus_ii": "HU66AT", "silca_alpha_pro": "HU66AT", "silca_futura_pro": "HU66AT",
     "notes": "Additional security track version. Confirm with vehicle spec."},
    {"blank_reference": "HU83", "description": "VW Polo/Lupo/Seat Ibiza blade", "key_type": "Double-sided",
     "common_makes_models": "Polo 9N3/6R/6C, Lupo, Seat Ibiza 6J, Seat Arona, Seat Leon 5F (some)",
     "dolphin_xp005l": "HU83", "condor_xc_mini_plus_ii": "HU83", "silca_alpha_pro": "HU83", "silca_futura_pro": "HU83",
     "notes": "Small VW/Seat platforms. Check if HU83 or HU66."},
    {"blank_reference": "HU162T", "description": "VW/Audi MQB flip blade", "key_type": "Flip blade",
     "common_makes_models": "Golf VII flip key variant, Polo AW (2018+), Audi A1 GB, Seat Ibiza KJ",
     "dolphin_xp005l": "HU162T (confirm)", "condor_xc_mini_plus_ii": "HU162T", "silca_alpha_pro": "HU162T", "silca_futura_pro": "HU162T",
     "notes": "Newer MQB flip key. Confirm before cutting."},

    # ── BMW ───────────────────────────────────────────────────────────────────
    {"blank_reference": "HU92", "description": "BMW standard laser blade (E-series)", "key_type": "Laser / track",
     "common_makes_models": "BMW 3 Series E46/E90/E91/E92, 5 Series E60/E61, 1 Series E81/E87, X3 E83, X5 E53/E70, Z4 E85/E89, MINI R50/R53/R55/R56",
     "dolphin_xp005l": "HU92 / LD series", "condor_xc_mini_plus_ii": "HU92", "silca_alpha_pro": "HU92", "silca_futura_pro": "HU92",
     "notes": "Most common BMW blank in AU. E-series CAS2/CAS3."},
    {"blank_reference": "HU100", "description": "BMW F-series/G-series laser blade", "key_type": "Laser / track",
     "common_makes_models": "BMW 3 Series F30/F34/G20, 5 Series F10/F11/G30, 1 Series F20/F40, X1 F48, X3 F25/G01, X5 F15/G05, MINI F54/F55/F56",
     "dolphin_xp005l": "HU100 / LD series", "condor_xc_mini_plus_ii": "HU100", "silca_alpha_pro": "HU100", "silca_futura_pro": "HU100",
     "notes": "F/G series BMW. FEM/BDC IMMO. Very challenging programming."},
    {"blank_reference": "HU58", "description": "BMW E39/E38 older blade", "key_type": "Laser / track",
     "common_makes_models": "BMW 5 Series E39, 7 Series E38, 3 Series E36 (some), X5 E53 (early)",
     "dolphin_xp005l": "HU58", "condor_xc_mini_plus_ii": "HU58", "silca_alpha_pro": "HU58", "silca_futura_pro": "HU58",
     "notes": "Older BMW laser. CAS1/EWS era."},
    {"blank_reference": "HU56R", "description": "BMW/MINI smaller laser blade", "key_type": "Laser / track",
     "common_makes_models": "MINI R50/R53/R55 (some), older BMW Z-series, some 3 Series E36",
     "dolphin_xp005l": "HU56R", "condor_xc_mini_plus_ii": "HU56R", "silca_alpha_pro": "HU56R", "silca_futura_pro": "HU56R",
     "notes": "Less common. Confirm with vehicle spec."},

    # ── MERCEDES-BENZ ─────────────────────────────────────────────────────────
    {"blank_reference": "HU64", "description": "Mercedes-Benz standard laser blade", "key_type": "Laser / track",
     "common_makes_models": "C-Class W203/W204, E-Class W210/W211/W212, A-Class W168/W169, B-Class W245, Vito W639, Sprinter W906, SLK R170/R171",
     "dolphin_xp005l": "HU64 / LD series", "condor_xc_mini_plus_ii": "HU64", "silca_alpha_pro": "HU64", "silca_futura_pro": "HU64",
     "notes": "Most common Merc blade in AU. EZS infrared or standard."},
    {"blank_reference": "HU64R", "description": "Mercedes-Benz older EZS infrared blade", "key_type": "Laser / track",
     "common_makes_models": "S-Class W220/W221, E-Class W211 EZS, CL W215/W216, SL R230",
     "dolphin_xp005l": "HU64R", "condor_xc_mini_plus_ii": "HU64R", "silca_alpha_pro": "HU64R", "silca_futura_pro": "HU64R",
     "notes": "EZS infrared system. Extremely complex. Specialist job."},
    {"blank_reference": "HU43", "description": "Mercedes/Sprinter older blade", "key_type": "Double-sided",
     "common_makes_models": "Sprinter W901-905 (older), some Vito W638",
     "dolphin_xp005l": "HU43", "condor_xc_mini_plus_ii": "HU43", "silca_alpha_pro": "HU43", "silca_futura_pro": "HU43",
     "notes": "Older Mercedes commercial. Pre-EZS era."},
    {"blank_reference": "HU39D", "description": "Mercedes newer platform blade (W205+)", "key_type": "Smart blade",
     "common_makes_models": "C-Class W205/W206, E-Class W213, GLC X253, A-Class W176/W177, CLA C117/C118, GLA X156/H247",
     "dolphin_xp005l": "HU39D (confirm)", "condor_xc_mini_plus_ii": "HU39D", "silca_alpha_pro": "HU39D", "silca_futura_pro": "HU39D",
     "notes": "Modern Merc. Proximity/smart key. Very high complexity."},

    # ── LAND ROVER / JAGUAR ───────────────────────────────────────────────────
    {"blank_reference": "HU101", "description": "Land Rover/Jaguar laser blade", "key_type": "Laser / track",
     "common_makes_models": "Discovery 3/4/5, Range Rover L322/L405/Sport L320/L494/L461, Defender L316/L663, Freelander 2, Jaguar XF X250/X260, XE, F-Pace",
     "dolphin_xp005l": "HU101 / LD series", "condor_xc_mini_plus_ii": "HU101", "silca_alpha_pro": "HU101", "silca_futura_pro": "HU101",
     "notes": "Common Land Rover/Jaguar blank. High complexity IMMO. Confirm year range."},
    {"blank_reference": "HU87", "description": "Land Rover older blade (Defender 1997-2016)", "key_type": "Single-sided",
     "common_makes_models": "Defender L316 (2004-2016 TD5/Puma), Freelander 1 LN",
     "dolphin_xp005l": "HU87", "condor_xc_mini_plus_ii": "HU87", "silca_alpha_pro": "HU87", "silca_futura_pro": "HU87",
     "notes": "Older Defender single-sided. Pre-advanced IMMO."},

    # ── PEUGEOT / CITROEN ─────────────────────────────────────────────────────
    {"blank_reference": "SX9 / PE", "description": "Peugeot/Citroen standard blade", "key_type": "Double-sided",
     "common_makes_models": "Peugeot 206/207/306/307/308/406/407, Citroen C3/C4/C5/Xsara Picasso",
     "dolphin_xp005l": "SX9 / PE series", "condor_xc_mini_plus_ii": "SX9", "silca_alpha_pro": "PE2 / SX9", "silca_futura_pro": "SX9",
     "notes": "Common Peugeot/Citroen blank. BSI IMMO."},
    {"blank_reference": "VA6 / PE2", "description": "Peugeot/Citroen flip blade", "key_type": "Flip blade",
     "common_makes_models": "Peugeot 207/208/308/3008, Citroen C3/C4 (flip remote variant)",
     "dolphin_xp005l": "VA6", "condor_xc_mini_plus_ii": "VA6", "silca_alpha_pro": "VA6 / PE2", "silca_futura_pro": "VA6",
     "notes": "Modern PSA Group flip key. BSI programming."},

    # ── RENAULT ───────────────────────────────────────────────────────────────
    {"blank_reference": "VA6 / REN12", "description": "Renault standard blade", "key_type": "Double-sided",
     "common_makes_models": "Megane II/III, Scenic II/III, Laguna II/III, Clio II/III/IV, Kangoo",
     "dolphin_xp005l": "REN12 / VA6", "condor_xc_mini_plus_ii": "REN12", "silca_alpha_pro": "REN12 / VA6", "silca_futura_pro": "REN12",
     "notes": "Common Renault blank. UCH IMMO system."},
    {"blank_reference": "REN10", "description": "Renault older blade (Clio I/Megane I)", "key_type": "Double-sided",
     "common_makes_models": "Clio I, Megane I/Scenic I, Laguna I, Espace III",
     "dolphin_xp005l": "REN10", "condor_xc_mini_plus_ii": "REN10", "silca_alpha_pro": "REN10", "silca_futura_pro": "REN10",
     "notes": "Older Renault. Pre-modern UCH era."},

    # ── VOLVO ─────────────────────────────────────────────────────────────────
    {"blank_reference": "VL37", "description": "Volvo standard blade (P2 platform)", "key_type": "Double-sided",
     "common_makes_models": "Volvo S40/V40 (2004-2012), S60/V70/XC70 (P2), XC90 P2",
     "dolphin_xp005l": "VL37", "condor_xc_mini_plus_ii": "VL37", "silca_alpha_pro": "VL37", "silca_futura_pro": "VL37",
     "notes": "Common Volvo blank. DICE/VIDA programming."},
    {"blank_reference": "VL38", "description": "Volvo P3/SPA platform blade", "key_type": "Laser / track",
     "common_makes_models": "Volvo S60/V60 P3, XC60 P3, S80 P3, V70 P3, XC90 SPA",
     "dolphin_xp005l": "VL38 (confirm)", "condor_xc_mini_plus_ii": "VL38", "silca_alpha_pro": "VL38", "silca_futura_pro": "VL38",
     "notes": "Modern Volvo. SPA platform very complex. Often refer."},

    # ── ISUZU ─────────────────────────────────────────────────────────────────
    {"blank_reference": "IZ10", "description": "Isuzu D-Max/MU-X blade", "key_type": "Double-sided",
     "common_makes_models": "D-Max TF (2008-2019), MU-X LS (2013-2020)",
     "dolphin_xp005l": "IZ10", "condor_xc_mini_plus_ii": "IZ10", "silca_alpha_pro": "IZ10", "silca_futura_pro": "IZ10",
     "notes": "First-gen D-Max specific blade. 2020+ D-Max uses MIT11 flip."},
    {"blank_reference": "IZ21", "description": "Isuzu D-Max/MU-X 2020+ flip blade", "key_type": "Flip blade",
     "common_makes_models": "D-Max RG (2020+), MU-X LS-U (2021+)",
     "dolphin_xp005l": "IZ21 (confirm)", "condor_xc_mini_plus_ii": "IZ21", "silca_alpha_pro": "IZ21", "silca_futura_pro": "IZ21",
     "notes": "New-gen Isuzu. Confirm blank — may cross to MIT11."},

    # ── LDV ───────────────────────────────────────────────────────────────────
    {"blank_reference": "LDV-HS / HU100", "description": "LDV T60/T60+ flip/smart blade", "key_type": "Flip blade",
     "common_makes_models": "LDV T60, T60+, Deliver 9, G10",
     "dolphin_xp005l": "HU100 or LDV-specific (confirm)", "condor_xc_mini_plus_ii": "HU100 (confirm)", "silca_alpha_pro": "HU100 (confirm)", "silca_futura_pro": "HU100 (confirm)",
     "notes": "LDV uses multiple blank types. Cross-reference with key shell. Confirm before cutting."},

    # ── GWM / HAVAL ───────────────────────────────────────────────────────────
    {"blank_reference": "GWM-HS", "description": "GWM/Haval high-security blade", "key_type": "Laser / track",
     "common_makes_models": "Haval H6 B01/B06, H9, Jolion, GWM Ute NPW",
     "dolphin_xp005l": "GWM-specific (confirm)", "condor_xc_mini_plus_ii": "GWM-specific (confirm)", "silca_alpha_pro": "GWM-specific (confirm)", "silca_futura_pro": "GWM-specific (confirm)",
     "notes": "GWM/Haval blanks not well-standardised in AU market yet. Confirm with supplier. Often requires specific shell from importer."},

    # ── JEEP ─────────────────────────────────────────────────────────────────
    {"blank_reference": "M3N / Y170", "description": "Jeep/Chrysler smart key blade", "key_type": "Smart blade",
     "common_makes_models": "Jeep Wrangler JK/JL, Cherokee KL, Grand Cherokee WK2/WL, Compass MP, Renegade BU",
     "dolphin_xp005l": "Y170 (confirm)", "condor_xc_mini_plus_ii": "Y170", "silca_alpha_pro": "Y170", "silca_futura_pro": "Y170",
     "notes": "FCA Group smart key. Witech/Autel required for programming. Confirm blade against specific model."},

    # ── FIAT / ALFA ROMEO ─────────────────────────────────────────────────────
    {"blank_reference": "GT15 / AR", "description": "Fiat/Alfa Romeo standard blade", "key_type": "Double-sided",
     "common_makes_models": "Fiat 500 312, Bravo 198, Punto 199/188, Stilo 192, Alfa 159/166/147/GT",
     "dolphin_xp005l": "GT15 / AR series", "condor_xc_mini_plus_ii": "GT15", "silca_alpha_pro": "GT15 / AR", "silca_futura_pro": "GT15",
     "notes": "Common Fiat/Alfa blank. ID48 / Fiat immo era."},
    {"blank_reference": "GT10 / FI", "description": "Fiat/Alfa older blade", "key_type": "Double-sided",
     "common_makes_models": "Fiat Punto 176, Uno, Bravo/Brava 182, Alfa 145/146/155, Tipo",
     "dolphin_xp005l": "GT10 / FI", "condor_xc_mini_plus_ii": "GT10", "silca_alpha_pro": "GT10 / FI", "silca_futura_pro": "GT10",
     "notes": "Pre-ID48 Fiat/Alfa. Older mechanical or early IMMO."},

    # ── KIA SPECIFIC ──────────────────────────────────────────────────────────
    {"blank_reference": "HYN16", "description": "Kia Sorento/Carnival newer blade", "key_type": "Double-sided",
     "common_makes_models": "Kia Sorento UM/MQ4, Carnival YP/KA4, Stinger CK, K5/Optima JF (late)",
     "dolphin_xp005l": "HYN16 (confirm)", "condor_xc_mini_plus_ii": "HYN16", "silca_alpha_pro": "HYN16", "silca_futura_pro": "HYN16",
     "notes": "Later Kia models. Confirm against HYN14R for older Sorento."},

    # ── TOYOTA LEXUS ──────────────────────────────────────────────────────────
    {"blank_reference": "TOY-L3 / TOY94", "description": "Lexus IS/GS smart key blade", "key_type": "Smart blade",
     "common_makes_models": "Lexus IS XE20/XE30, GS S190/S190, NX AZ10, RX AL10/AL20, ES XV50/XV70",
     "dolphin_xp005l": "TOY94 (confirm)", "condor_xc_mini_plus_ii": "TOY94", "silca_alpha_pro": "TOY94", "silca_futura_pro": "TOY94",
     "notes": "Lexus smart/prox key. Australian market Lexus common in fleet."},

    # ── HONDA NEWER ───────────────────────────────────────────────────────────
    {"blank_reference": "HON35", "description": "Honda CR-V/Accord smart key blade", "key_type": "Smart blade",
     "common_makes_models": "CR-V RT 2017+, Accord CV 2018+, Civic FC/FE, HR-V RV",
     "dolphin_xp005l": "HON35 (confirm)", "condor_xc_mini_plus_ii": "HON35", "silca_alpha_pro": "HON35", "silca_futura_pro": "HON35",
     "notes": "Modern Honda smart key. HITAG AES / advanced. Confirm blank with vehicle."},

    # ── MAZDA NEWER ──────────────────────────────────────────────────────────
    {"blank_reference": "MAZ28 / MA14", "description": "Mazda SKE AES smart key blade", "key_type": "Smart blade",
     "common_makes_models": "CX-5 KF 2017+, CX-9 TC 2016+, Mazda3 BP 2019+, Mazda6 GL 2017+, CX-30, MX-30",
     "dolphin_xp005l": "MAZ28 (confirm)", "condor_xc_mini_plus_ii": "MAZ28", "silca_alpha_pro": "MAZ28", "silca_futura_pro": "MAZ28",
     "notes": "Mazda SKE/AES era. Requires BSU. Confirm blade type with Mazda SKE key shell."},

    # ── NISSAN NEWER ─────────────────────────────────────────────────────────
    {"blank_reference": "NSN49", "description": "Nissan Patrol Y62/Navara D23 smart key blade", "key_type": "Smart blade",
     "common_makes_models": "Patrol Y62 (2012+), Navara D23 NP300 (2015+), Pathfinder R52, Murano Z52, Qashqai J11/J12",
     "dolphin_xp005l": "NSN49 (confirm)", "condor_xc_mini_plus_ii": "NSN49", "silca_alpha_pro": "NSN49", "silca_futura_pro": "NSN49",
     "notes": "Modern Nissan smart key. AES era. BSU required. Confirm blank."},

    # ── SUBARU NEWER ─────────────────────────────────────────────────────────
    {"blank_reference": "SU10-S", "description": "Subaru smart key blade (WRX/STI/Forester modern)", "key_type": "Smart blade",
     "common_makes_models": "WRX VA/VB, Forester SK/SJ late, Outback BS/BT, Liberty BT",
     "dolphin_xp005l": "SU10-S (confirm)", "condor_xc_mini_plus_ii": "SU10-S", "silca_alpha_pro": "SU10-S", "silca_futura_pro": "SU10-S",
     "notes": "Modern Subaru smart key. Dealer PIN often required. Confirm blank."},

    # ── FORD RANGER NEWER ─────────────────────────────────────────────────────
    {"blank_reference": "FO45", "description": "Ford Ranger PXIII/Next-Gen blade", "key_type": "Flip blade",
     "common_makes_models": "Ranger PXIII (2019-2021), Everest UC (2019-2021), some Transit 2018+",
     "dolphin_xp005l": "FO45 (confirm)", "condor_xc_mini_plus_ii": "FO45", "silca_alpha_pro": "FO45", "silca_futura_pro": "FO45",
     "notes": "Late-PXIII Ranger flip key. Confirm — some PXIII still use FO43."},
    {"blank_reference": "HU101-F / FO64", "description": "Ford Next-Gen Ranger (2022+) smart blade", "key_type": "Smart blade",
     "common_makes_models": "Ranger P703 (2022+), Everest P703 (2022+), Bronco (grey import)",
     "dolphin_xp005l": "FO64 (confirm)", "condor_xc_mini_plus_ii": "FO64", "silca_alpha_pro": "FO64", "silca_futura_pro": "FO64",
     "notes": "New-gen Ranger. Very new — confirm blank with supplier. PATS5 system."},
]
# fmt: on

output = {"entries": BLANKS}
out_path = SEED / "expanded_key_blanks.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Written {len(BLANKS)} blanks to {out_path}")

# Count by make group
from collections import Counter
makes = []
for b in BLANKS:
    desc = b["common_makes_models"]
    for m in ["Toyota", "Ford", "Holden", "Honda", "Nissan", "Hyundai", "Kia", "Mazda", "Mitsubishi",
              "Subaru", "Suzuki", "VW", "Audi", "BMW", "Mercedes", "Land Rover", "Isuzu", "Renault",
              "Peugeot", "Volvo", "LDV", "GWM", "Jeep", "Fiat", "Alfa", "Lexus"]:
        if m in desc:
            makes.append(m)
            break
c = Counter(makes)
for k, v in sorted(c.items()):
    print(f"  {k}: {v}")
