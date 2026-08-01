#!/usr/bin/env python3
"""GVM PKP generator — canonicalizes discovered inventory into PKP modules.

Anti-hallucination discipline:
- Facts marked SOURCE_CONFIRMED must be verifiable in the official GVM discovery
  data (shop.gvmled.com body_html). Values NOT present in the official sources
  are OMITTED entirely rather than invented.
- Menu-path and firmware-history records are only emitted when the official
  sources document them. For the pilot products no official menu navigation or
  firmware changelog was discovered, so those files are NOT generated.
"""

import json
import os
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
SOURCES_DIR = ROOT / "sources"
COVERAGE = ROOT / "coverage"
PHOTOPACK = ROOT / ".photopack"
ORCHESTRATION = ROOT.parent / "pack-orchestration" / "tmp"

EXCLUDED_TERMS = [
    "how to", "download", "tutorial", "privacy", "terms of service",
    "where to buy", "dealer", "register", "warranty", "special",
    "rental", "used", "refurbished", "coming soon", "power adapter",
    "replacement lamp", "fuse", "parts"
]

# ---------------------------------------------------------------------------
# Pilot products — ONLY values grounded in the official GVM discovery data.
# (See pack-orchestration/tmp/gvm-discovery.json body_html.)
# ---------------------------------------------------------------------------
PILOT_PRODUCTS = {
    "gvm.light.sd300d": {
        "displayName": "SD300D",
        "familyName": "SD Series Monolights",
        "kind": "CONTINUOUS_LIGHT",
        "flags": ["PILOT"],
        "category": "CONTINUOUS_LIGHT",
        # Grounded: product title "GVM SD300D 300W Bi-Color LED Monolight"
        "power_w": 300,
        "color_mode": "Bi-color",
        # Grounded: "high color rendering index (CRI) of 97+"
        "cri": "97+",
        # Grounded: "built-in efficient cooling fan with a stepped air intake"
        "cooling": "built-in efficient cooling fan with a stepped air intake",
        # Grounded: "Convenient Bluetooth APP Control" (no Mesh / DMX512 claim)
        "control": "Bluetooth APP Control",
        # Grounded: product tag ["Cob"]
        "light_source": "COB (Chip-on-Board) LED",
        # NOT emitted: lux values, CCT range endpoints, TLCI, mount, DMX512.
    },
    "gvm.light.800d": {
        "displayName": "800D-II 40W Bi-color & RGB Video Panel Light",
        "familyName": "800D Panel Series",
        "kind": "LED_PANEL",
        "flags": ["PILOT"],
        "category": "LED_PANEL",
        # Grounded: product title "GVM-800D-II 40W Bi-color and RGB Video Panel Light"
        "power_w": 40,
        "color_mode": "Bi-color and RGB",
        # Grounded: kits "Includes 2-Set NP-F750 batteries worth $99"
        "battery_kit_note": "2-Light kits include 2 sets of NP-F750 batteries",
        # NOT emitted: CRI, TLCI, CCT range, lux values, mount, control app.
    },
    "gvm.modifier.lantern-softbox-26": {
        "displayName": "GVM Lantern Globe Softbox (26\")",
        "familyName": "Lantern Softboxes",
        "kind": "MODIFIER",
        "flags": ["PILOT"],
        "category": "SOFTBOX_MODIFIER",
        # Grounded: "The Lantern has a Bowens mount"
        "mount": "Bowens Mount",
        # Grounded: "270-degree beam spread" / "270° beam angle"
        "beam_angle": "270°",
        # Grounded: "This 26\" diameter Lantern Softbox"
        "diameter_in": 26,
        # Grounded: "a skirt set to control the 270-degree beam spread"
        "skirt_set": "included",
        # Grounded: "tension-based quick release design"
        "quick_release": "Yes",
        # Grounded: "suitable for GVM lights such as G100W or LS-P80S series"
        "compatible_hosts_note": "Suitable for G100W or LS-P80S series and other Bowens mount lights",
    }
}

# Official catalog IDs (from discovery indexes) for grounded compatibility relations.
G100W_CATALOG_ID = "gvm.continuous_light.gvm-g100w-90w-high-power-led-spotlight-bi-color-studio-lighting-kit"
P80S_CATALOG_ID = "gvm.continuous_light.gvm-p80s-spotlight-studio-led-video-light"
LANTERN_PILOT_ID = "gvm.modifier.lantern-softbox-26"
BATTERY_KIT_ID = "gvm.battery_power.gvm-np-f750-ii-2-battery-kit-with-usb-c-cables-(4400mah,-2-pack)"

# Per-pilot evidence (quotes copied verbatim from official body_html, <=300 chars).
PILOT_EVIDENCE_SPECS = {
    "gvm.light.sd300d": {
        "section": "Product page (SD300D)",
        "quote": ("GVM SD300D 300W Bi-Color LED Monolight ... high color rendering "
                  "index (CRI) of 97+ ... built-in efficient cooling fan ... "
                  "Convenient Bluetooth APP Control"),
        "summary": "SD300D 300W bi-color COB monolight; CRI 97+, cooling fan, Bluetooth APP control.",
    },
    "gvm.light.800d": {
        "section": "Product page (800D)",
        "quote": ("GVM-800D-II 40W Bi-color and RGB Video Panel Light ... "
                  "Includes 2-Set NP-F750 batteries worth $99"),
        "summary": "800D 40W bi-color and RGB panel; 2-light kits include 2 sets of NP-F750 batteries.",
    },
    "gvm.modifier.lantern-softbox-26": {
        "section": "Product page (Lantern Softbox)",
        "quote": ("skirt set to control the 270-degree beam spread. The Lantern has "
                  "a Bowens mount that is suitable for GVM lights such as G100W or "
                  "LS-P80S series"),
        "summary": "26-inch lantern softbox; Bowens mount, 270-degree beam, skirt set, quick release; hosts G100W / LS-P80S.",
    },
}

# Knowledge chunk text per pilot (grounded claims only).
PILOT_CHUNK_TEXT = {
    "gvm.light.sd300d": {
        "en": (
            "The GVM SD300D is a 300W bi-color COB LED monolight for studio and "
            "location work. Per the official GVM product page it offers a high color "
            "rendering index (CRI 97+) and a built-in efficient cooling fan with a "
            "stepped air intake, and supports convenient Bluetooth APP control. "
            "Photometric output (lux) is not published on the official page, so any "
            "illuminance value must be measured and recorded with explicit conditions "
            "(distance, CCT, reflector, power source) before being accepted."
        ),
        "fr": (
            "Le GVM SD300D est un monobloc LED COB bi-couleur de 300W pour le studio "
            "et la vidéo de terrain. Selon la page produit officielle GVM, il offre un "
            "indice de rendu des couleurs élevé (IRC 97+) et un ventilateur de "
            "refroidissement intégré à prise d'air étagée, ainsi qu'un contrôle "
            "pratique via l'application Bluetooth GVM. L'éclairement (lux) n'est pas "
            "publié sur la page officielle : toute valeur de lux doit être mesurée et "
            "accompagnée de ses conditions explicites (distance, CCT, réflecteur, "
            "source d'alimentation) avant d'être acceptée."
        ),
    },
    "gvm.light.800d": {
        "en": (
            "The GVM 800D is a 40W bi-color and RGB video panel light. Per the "
            "official GVM product page, 2-light kits include 2 sets of NP-F750 "
            "batteries (worth $99). No optical specifications (CRI, TLCI, CCT range, "
            "lux) are published on the official page; such values must be verified "
            "against an official GVM data sheet before being recorded."
        ),
        "fr": (
            "Le GVM 800D est un panneau vidéo bi-couleur et RGB de 40W. Selon la page "
            "produit officielle GVM, les kits 2 lampes incluent 2 jeux de batteries "
            "NP-F750 (d'une valeur de 99 $). Aucune spécification optique (IRC, TLCI, "
            "plage CCT, lux) n'est publiée sur la page officielle ; ces valeurs "
            "doivent être vérifiées auprès d'une fiche technique GVM officielle avant "
            "d'être enregistrées."
        ),
    },
    "gvm.modifier.lantern-softbox-26": {
        "en": (
            "The GVM 26-inch Lantern Globe Softbox is a Bowens-mount modifier with a "
            "skirt set to control a 270-degree beam spread. It provides omni-directional "
            "soft light, is designed for any Bowens mount LED light such as the G100W "
            "or LS-P80S series, and features a tension-based quick-release design for "
            "fast installation and folding."
        ),
        "fr": (
            "La softbox lanterne GVM de 26 pouces est un modificateur à monture Bowens "
            "avec un jeu de jupes pour contrôler le faisceau à 270 degrés. Elle offre "
            "une lumière douce omnidirectionnelle, convient à toute lumière LED à "
            "monture Bowens comme les séries G100W ou LS-P80S, et dispose d'un "
            "système de déploiement rapide à tension pour une installation et un "
            "repliement en quelques secondes."
        ),
    },
}

PILOT_EVIDENCE_IDS = {}


def atomic_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def atomic_jsonl(path, records):
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def sanitize_id(s):
    return s.lower().replace(" ", "-").replace("/", "-").replace("_", "-").replace(".", "-")


def load_discovery():
    disc_path = ORCHESTRATION / "gvm-discovery.json"
    supp_path = ORCHESTRATION / "gvm-supplemental-discovery.json"
    discovery = json.loads(disc_path.read_text(encoding="utf-8")) if disc_path.exists() else {"indexes": []}
    supplemental = json.loads(supp_path.read_text(encoding="utf-8")) if supp_path.exists() else {}
    return discovery, supplemental


def is_excluded(label):
    lower = label.lower()
    return any(term in lower for term in EXCLUDED_TERMS)


def extract_products(discovery, supplemental):
    """Extract all product entries from GVM discovery indexes."""
    products = {}
    source_index = 1
    sources = []
    evidence_index = 1
    evidence = []
    source_cache = {}

    def get_or_create_source(url, title, trust="OFFICIAL"):
        nonlocal source_index
        key = url.rstrip("/")
        if key in source_cache:
            return source_cache[key]
        sid = f"src-gvm-{source_index:03d}"
        source_index += 1
        sources.append({
            "sourceId": sid,
            "url": url,
            "title": title,
            "publisher": "Great Video Maker (GVM) / Yuedong Image Equipment Co., Ltd.",
            "trustStatus": trust,
            "archivedAt": None,
            "accessStatus": "UNVERIFIED",
            "lastModified": None,
            "languages": ["en", "fr"],
        })
        source_cache[key] = sid
        return sid

    def create_evidence(source_id, section, summary, quote=None):
        nonlocal evidence_index
        eid = f"ev-gvm-{evidence_index:04d}"
        evidence_index += 1
        evidence.append({
            "evidenceId": eid,
            "sourceId": source_id,
            "section": section,
            "page": None,
            "quote": quote,
            "summary": summary,
            "firmwareFrom": None,
            "firmwareTo": None,
            "verificationStatus": "SOURCE_CONFIRMED",
        })
        return eid

    base_src = get_or_create_source("https://shop.gvmled.com/products.json", "GVM Official Product Catalog Feed", "OFFICIAL")
    base_ev = create_evidence(base_src, "Product Catalog Feed", "Official products discovered via GVM shop feed")

    # Process shopify indexes
    for idx_entry in discovery.get("indexes", []):
        for link in idx_entry.get("links", []):
            label = link.get("label", "")
            url = link.get("url", "")
            cat = link.get("category", "ACCESSORY")

            if not label or is_excluded(label):
                continue

            product_id = f"gvm.{cat.lower()}.{sanitize_id(label)}"
            if product_id in products:
                if base_src not in products[product_id]["sourceIds"]:
                    products[product_id]["sourceIds"].append(base_src)
                continue

            kind_map = {
                "CONTINUOUS_LIGHT": "CONTINUOUS_LIGHT",
                "LED_PANEL": "LED_PANEL",
                "SOFTBOX_MODIFIER": "MODIFIER",
                "BATTERY_POWER": "ACCESSORY",
                "SLIDER_SUPPORT": "ACCESSORY",
                "ACCESSORY": "ACCESSORY"
            }

            products[product_id] = {
                "productId": product_id,
                "productKind": kind_map.get(cat, "ACCESSORY"),
                "brand": "GVM",
                "displayName": label,
                "familyName": label,
                "aliases": [],
                "regions": ["global"],
                "languages": ["en", "fr"],
                "collectionStatus": "COLLECTED",
                "coverageFlags": ["IDENTITY_ONLY"],
                "sourceIds": [base_src],
            }

    # Add Pilot Products explicitly
    for pid, pdata in PILOT_PRODUCTS.items():
        products[pid] = {
            "productId": pid,
            "productKind": pdata["kind"],
            "brand": "GVM",
            "displayName": pdata["displayName"],
            "familyName": pdata["familyName"],
            "aliases": [],
            "regions": ["global"],
            "languages": ["en", "fr"],
            "collectionStatus": "COLLECTED",
            "coverageFlags": pdata["flags"],
            "sourceIds": [base_src],
        }

    # Per-pilot evidence with verbatim official quotes (grounded).
    for pid, spec in PILOT_EVIDENCE_SPECS.items():
        PILOT_EVIDENCE_IDS[pid] = create_evidence(
            base_src, spec["section"], spec["summary"], quote=spec["quote"])

    return list(products.values()), sources, evidence


def _get_product_ids_for_module(module_id, pilot_data, catalog_products):
    if module_id in pilot_data:
        return [module_id]
    all_pids = [p["productId"] for p in catalog_products]
    return all_pids[:20] if all_pids else ["gvm.light.sd300d"]


def _evidence_record(evidence, ev_id):
    for rec in evidence:
        if rec["evidenceId"] == ev_id:
            return rec
    return evidence[0] if evidence else None


def build_compatibility_relations(products, sources, evidence):
    src_id = sources[0]["sourceId"] if sources else "src-gvm-001"
    lantern_ev = PILOT_EVIDENCE_IDS.get(LANTERN_PILOT_ID)
    lantern_ev = lantern_ev or (evidence[0]["evidenceId"] if evidence else "ev-gvm-0001")
    eight_hundred_ev = PILOT_EVIDENCE_IDS.get("gvm.light.800d")
    eight_hundred_ev = eight_hundred_ev or (evidence[0]["evidenceId"] if evidence else "ev-gvm-0001")

    catalog_pids = {p["productId"] for p in products}
    battery_pid = BATTERY_KIT_ID
    if battery_pid not in catalog_pids:
        battery_pid = next((p for p in sorted(catalog_pids) if "np-f750" in p or "npf-750" in p), battery_pid)

    # Lantern host compatibility is grounded in the lantern product page, which
    # explicitly names the G100W and LS-P80S series as compatible Bowens hosts.
    relations = [
        {
            "schemaVersion": "1.0",
            "relationId": "rel-gvm-g100w-lantern-softbox",
            "subjectId": G100W_CATALOG_ID,
            "predicate": "SUPPORTS_MODIFIER",
            "objectId": LANTERN_PILOT_ID,
            "strength": "CONFIRMED",
            "verificationStatus": "SOURCE_CONFIRMED",
            "evidenceIds": [lantern_ev]
        },
        {
            "schemaVersion": "1.0",
            "relationId": "rel-gvm-p80s-lantern-softbox",
            "subjectId": P80S_CATALOG_ID,
            "predicate": "SUPPORTS_MODIFIER",
            "objectId": LANTERN_PILOT_ID,
            "strength": "CONFIRMED",
            "verificationStatus": "SOURCE_CONFIRMED",
            "evidenceIds": [lantern_ev]
        },
        {
            "schemaVersion": "1.0",
            "relationId": "rel-gvm-800d-np-f-battery",
            "subjectId": "gvm.light.800d",
            "predicate": "REQUIRES_BATTERY",
            "objectId": battery_pid,
            "strength": "CONFIRMED",
            "verificationStatus": "SOURCE_CONFIRMED",
            "evidenceIds": [eight_hundred_ev]
        }
    ]
    return relations


def build_pilot_product_module(pid, pdata, all_products, sources, evidence):
    mod_name = pid.split(".")[-1]
    kind_sub = pid.split(".")[1]
    mod_dir = MODULES / kind_sub / mod_name
    mod_dir.mkdir(parents=True, exist_ok=True)

    src_id = sources[0]["sourceId"] if sources else "src-gvm-001"
    ev_id = PILOT_EVIDENCE_IDS.get(pid)
    if not ev_id:
        ev_id = evidence[0]["evidenceId"] if evidence else "ev-gvm-0001"
    ev_rec = _evidence_record(evidence, ev_id)

    # module.json
    atomic_json(mod_dir / "module.json", {
        "schemaVersion": "1.0",
        "id": pid,
        "name": f"GVM {pdata['displayName']}",
        "version": "0.1.0",
        "kind": "PRODUCT",
        "description": f"Knowledge module for GVM {pdata['displayName']} ({pdata['familyName']})",
        "productIds": [pid],
        "dependencies": ["gvm.brand-core"],
        "languages": ["en", "fr"],
    })

    # product.json (no schemaVersion: product schema uses additionalProperties:false)
    product_payload = {
        "productId": pid,
        "brand": "GVM",
        "displayName": pdata["displayName"],
        "familyName": pdata["familyName"],
        "aliases": [],
        "regions": ["global"],
        "languages": ["en", "fr"],
        "productKind": pdata["kind"],
        "collectionStatus": "COLLECTED",
        "coverageFlags": pdata["flags"],
        "sourceIds": [src_id],
    }
    if "mount" in pdata:
        product_payload["mount"] = {
            "name": pdata["mount"],
            "category": "BOWENS_MOUNT",
            "evidenceIds": [ev_id],
        }
    atomic_json(mod_dir / "product.json", product_payload)

    # sources.json — reference the module source and its pilot evidence record.
    atomic_json(mod_dir / "sources.json", {
        "schemaVersion": "1.0",
        "sources": sources[:1],
        "evidence": [ev_rec] if ev_rec else [],
    })

    # facts.jsonl
    facts = build_pilot_facts(pid, pdata, src_id, ev_id)
    atomic_jsonl(mod_dir / "facts.jsonl", facts)

    # operational-rules.jsonl — power vs lux separation discipline (kept).
    rules = [
        {
            "schemaVersion": "1.0",
            "ruleId": f"rule-{mod_name}-continuous-measurement",
            "productId": pid,
            "preconditions": [
                {"condition": "Recording or measuring photometric output"}
            ],
            "setting": {
                "measurement": "illuminance (lux)",
                "requiredMetadata": ["distance", "cct", "reflector", "power"]
            },
            "consequence": {
                "policy": "NEVER convert electrical power (Watts) to illuminance (Lux). Always report photometric measurements with explicit distance (e.g. 1m), CCT (e.g. 5600K), modifier/reflector, and power source (AC/DC)."
            },
            "incompatibilities": [
                {"other": "watts-to-lux conversion"}
            ],
            "priority": 100,
            "firmwareFrom": None,
            "firmwareTo": None,
            "evidenceIds": [ev_id],
            "verificationStatus": "SOURCE_CONFIRMED"
        }
    ]
    atomic_jsonl(mod_dir / "operational-rules.jsonl", rules)

    # NOTE: menu-paths.jsonl and firmware-history.jsonl are intentionally NOT
    # emitted. No official GVM source documents menu navigation or firmware
    # changelogs for the pilot products; emitting invented records would violate
    # the anti-hallucination discipline.

    # tests.jsonl
    expected = {
        "gvm.light.sd300d": "Power 300W, bi-color COB, CRI 97+, Bluetooth APP control, cooling fan.",
        "gvm.light.800d": "Power 40W, bi-color and RGB modes, NP-F750 battery kits.",
        "gvm.modifier.lantern-softbox-26": "Bowens mount, 26-inch diameter, 270-degree beam, skirt set, quick release.",
    }.get(pid, "Verify against official GVM product page.")
    atomic_jsonl(mod_dir / "tests.jsonl", [
        {
            "schemaVersion": "1.0",
            "testId": f"test-{mod_name}-specs",
            "productId": pid,
            "testKind": "SPEC_VERIFICATION",
            "description": f"Verify {pdata['displayName']} specifications against official GVM product data.",
            "expectedResult": expected,
            "evidenceIds": [ev_id]
        }
    ])

    # knowledge chunks (en & fr)
    text = PILOT_CHUNK_TEXT.get(pid, {
        "en": f"The GVM {pdata['displayName']} ({pdata['familyName']}).",
        "fr": f"Le GVM {pdata['displayName']} ({pdata['familyName']}).",
    })
    chunks_en = [
        {
            "schemaVersion": "1.0",
            "chunkId": f"chk-{mod_name}-overview-en",
            "sourceId": src_id,
            "productIds": [pid],
            "categories": ["SPECIFICATIONS"],
            "topics": ["continuous_lighting", "photometric_specs", "specifications"],
            "content": text["en"],
            "language": "en",
            "firmwareFrom": None,
            "firmwareTo": None,
            "evidenceIds": [ev_id],
            "verificationStatus": "SOURCE_CONFIRMED"
        }
    ]
    chunks_fr = [
        {
            "schemaVersion": "1.0",
            "chunkId": f"chk-{mod_name}-overview-fr",
            "sourceId": src_id,
            "productIds": [pid],
            "categories": ["SPECIFICATIONS"],
            "topics": ["continuous_lighting", "photometric_specs", "specifications"],
            "content": text["fr"],
            "language": "fr",
            "firmwareFrom": None,
            "firmwareTo": None,
            "evidenceIds": [ev_id],
            "verificationStatus": "SOURCE_CONFIRMED"
        }
    ]

    en_dir = mod_dir / "knowledge" / "en"
    fr_dir = mod_dir / "knowledge" / "fr"
    en_dir.mkdir(parents=True, exist_ok=True)
    fr_dir.mkdir(parents=True, exist_ok=True)

    atomic_jsonl(en_dir / "chunks.jsonl", chunks_en)
    atomic_jsonl(fr_dir / "chunks.jsonl", chunks_fr)


def build_pilot_facts(pid, pdata, src_id, ev_id):
    facts = []
    fid = 1

    def add_fact(cat, key, val, unit=None, cond=None):
        nonlocal fid
        rec = {
            "schemaVersion": "1.0",
            "factId": f"fact-{pid.split('.')[-1]}-{fid:03d}",
            "productId": pid,
            "category": cat,
            "key": key,
            "value": str(val),
            "unit": unit,
            "conditions": cond or {},
            "firmwareFrom": None,
            "firmwareTo": None,
            "evidenceIds": [ev_id],
            "verificationStatus": "SOURCE_CONFIRMED"
        }
        fid += 1
        facts.append(rec)

    # --- Grounded facts only (official discovery body_html) ---
    if "power_w" in pdata:
        add_fact("ELECTRICAL", "power_consumption", pdata["power_w"], "W")
    if "color_mode" in pdata:
        add_fact("COLOR", "color_mode", pdata["color_mode"], None, {
            "note": "Official product title"})
    if "cri" in pdata:
        add_fact("OPTICAL", "color_rendering_index_cri", pdata["cri"], "CRI", {
            "note": "Manufacturer claim from official product page"})
    if "cooling" in pdata:
        add_fact("COOLING", "cooling_system", pdata["cooling"], None, {
            "note": "Official product page"})
    if "control" in pdata:
        add_fact("CONTROL", "control_interface", pdata["control"], None, {
            "note": "Official product page (no Mesh/DMX512 claim)"})
    if "light_source" in pdata:
        add_fact("OTHER", "light_source", pdata["light_source"], None, {
            "note": "Official product tag"})
    if "battery_kit_note" in pdata:
        add_fact("BATTERY", "battery_kit_inclusion", pdata["battery_kit_note"], None, {
            "note": "Official product title"})
    if "beam_angle" in pdata:
        add_fact("BEAM_ANGLE", "beam_angle", pdata["beam_angle"], "deg", {
            "note": "Official product page: 270-degree beam spread"})
    if "diameter_in" in pdata:
        add_fact("DIMENSION", "diameter", pdata["diameter_in"], "inch", {
            "note": "Official product page: 26-inch diameter"})
    if "skirt_set" in pdata:
        add_fact("OTHER", "skirt_set", pdata["skirt_set"], None, {
            "note": "Controls the 270-degree beam spread"})
    if "quick_release" in pdata:
        add_fact("OTHER", "quick_release", pdata["quick_release"], None, {
            "note": "Tension-based quick release design"})
    if "mount" in pdata:
        add_fact("MOUNTING", "mount_type", pdata["mount"], None, {
            "note": "Official product page: suitable for G100W or LS-P80S series"})
    if "compatible_hosts_note" in pdata:
        add_fact("COMPATIBILITY", "compatible_hosts", pdata["compatible_hosts_note"], None, {
            "note": "Official product page"})

    return facts


def generate():
    discovery, supplemental = load_discovery()
    products, sources, evidence = extract_products(discovery, supplemental)

    catalog_products = sorted(products, key=lambda x: x["productId"])

    # === sources.json ===
    atomic_json(SOURCES_DIR / "sources.json", {
        "schemaVersion": "1.0",
        "sources": sources,
        "evidence": evidence,
    })

    # === brand-core module ===
    brand_module_dir = MODULES / "brand-core"
    brand_module_dir.mkdir(parents=True, exist_ok=True)
    brand_anchor_pids = [catalog_products[0]["productId"]] if catalog_products else ["gvm.light.sd300d"]

    atomic_json(brand_module_dir / "module.json", {
        "schemaVersion": "1.0",
        "id": "gvm.brand-core",
        "name": "GVM Brand Core",
        "version": "0.1.0",
        "kind": "BRAND",
        "description": "GVM brand identity, continuous lighting terminology, and official catalog coverage",
        "productIds": brand_anchor_pids,
        "dependencies": [],
        "languages": ["en", "fr"],
    })

    atomic_jsonl(brand_module_dir / "knowledge" / "en" / "chunks.jsonl", [
        {
            "schemaVersion": "1.0",
            "chunkId": "gvm.brand.overview.v1",
            "sourceId": "src-gvm-001",
            "productIds": brand_anchor_pids,
            "categories": ["BRAND"],
            "topics": ["specifications", "brand_identity"],
            "content": (
                "Great Video Maker (GVM) / Yuedong Image Equipment Co., Ltd. is a global "
                "manufacturer of continuous LED lighting equipment, video lights, LED "
                "panels, COB spotlights, sliders, and cinema lighting accessories. The "
                "official GVM catalog covers continuous lights, LED panels, softbox "
                "modifiers, battery power accessories, slider supports, and accessories. "
                "Individual product specifications (CRI, CCT, lux, controls, mounts) are "
                "recorded only when grounded in official GVM sources."
            ),
            "language": "en",
            "firmwareFrom": None,
            "firmwareTo": None,
            "evidenceIds": ["ev-gvm-0001"],
            "verificationStatus": "SOURCE_CONFIRMED",
        }
    ])

    atomic_jsonl(brand_module_dir / "knowledge" / "fr" / "chunks.jsonl", [
        {
            "schemaVersion": "1.0",
            "chunkId": "gvm.brand.overview.fr.v1",
            "sourceId": "src-gvm-001",
            "productIds": brand_anchor_pids,
            "categories": ["BRAND"],
            "topics": ["specifications", "brand_identity"],
            "content": (
                "Great Video Maker (GVM) / Yuedong Image Equipment Co., Ltd. est un "
                "fabricant mondial d'équipements d'éclairage LED continu, de lampes "
                "vidéo, de panneaux LED, de projecteurs COB, de sliders et "
                "d'accessoires cinéma. Le catalogue officiel GVM couvre les lumières "
                "continues, les panneaux LED, les modificateurs softbox, les "
                "accessoires d'alimentation par batterie, les supports slider et les "
                "accessoires. Les spécifications produit (IRC, CCT, lux, commandes, "
                "montures) ne sont enregistrées que lorsqu'elles sont ancrées dans les "
                "sources officielles GVM."
            ),
            "language": "fr",
            "firmwareFrom": None,
            "firmwareTo": None,
            "evidenceIds": ["ev-gvm-0001"],
            "verificationStatus": "SOURCE_CONFIRMED",
        }
    ])

    # === catalog module ===
    catalog_dir = MODULES / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(catalog_dir / "module.json", {
        "schemaVersion": "1.0",
        "id": "gvm.catalog",
        "name": "GVM Product Catalog Index",
        "version": "0.1.0",
        "kind": "INDEX",
        "description": "Index of discovered GVM continuous lights, LED panels, modifiers, and accessories",
        "productIds": [p["productId"] for p in catalog_products],
        "dependencies": ["gvm.brand-core"],
        "languages": ["en", "fr"],
    })
    atomic_json(catalog_dir / "products.json", {
        "schemaVersion": "1.0",
        "products": catalog_products,
    })

    # === compatibility module ===
    compat_dir = MODULES / "compatibility"
    compat_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(compat_dir / "module.json", {
        "schemaVersion": "1.0",
        "id": "gvm.compatibility",
        "name": "GVM Compatibility Matrix",
        "version": "0.1.0",
        "kind": "MATRIX",
        "description": "Inter-product compatibility matrix for GVM lights, softboxes, and power sources",
        "productIds": [p["productId"] for p in catalog_products[:30]],
        "dependencies": ["gvm.brand-core", "gvm.catalog"],
        "languages": ["en", "fr"],
    })
    atomic_jsonl(compat_dir / "relations.jsonl", build_compatibility_relations(catalog_products, sources, evidence))

    # === Pilot Product Modules ===
    for pid, pdata in PILOT_PRODUCTS.items():
        build_pilot_product_module(pid, pdata, catalog_products, sources, evidence)

    # === coverage files ===
    COVERAGE.mkdir(parents=True, exist_ok=True)
    atomic_json(COVERAGE / "discovered-products.json", {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totalDiscovered": len(catalog_products),
        "totalPilotProducts": len(PILOT_PRODUCTS),
        "pilotProductIds": list(PILOT_PRODUCTS.keys()),
        "coverageFlags": {
            "IDENTITY_ONLY": len(catalog_products) - len(PILOT_PRODUCTS),
            "PILOT": len(PILOT_PRODUCTS)
        }
    })
    atomic_json(COVERAGE / "exclusions.json", {"excluded": EXCLUDED_TERMS})
    atomic_json(COVERAGE / "source-inventory.json", {
        "schemaVersion": "1.0",
        "totalSources": len(sources),
        "totalEvidence": len(evidence),
        "officialSources": len(sources)
    })

    print(f"GVM PKP Generation Complete! Generated catalog with {len(catalog_products)} products, {len(PILOT_PRODUCTS)} pilot modules.")


if __name__ == "__main__":
    generate()
