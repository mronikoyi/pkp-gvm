# PKP GVM — Continuous Lights, LED Panels, and Accessories

Photo Knowledge Pack for GVM (Great Video Maker) lighting equipment. This pack
provides canonical, evidence-backed technical data for GVM continuous lights,
LED panels, monolights, softbox modifiers, slider supports, and power accessories.

## Overview

- **Brand**: GVM
- **Categories**: Continuous Light, LED Panel, Softbox Modifier, Battery Power, Slider Support, Accessory
- **Format**: PKP 1.0
- **Languages**: en, fr
- **Catalog**: 414 products from official GVM discovery (shop.gvmled.com)

## Pilot Products

| Product | Category | Power | Key Spec (grounded) |
|---------|----------|-------|---------------------|
| SD300D | Continuous Light | 300 W | Bi-color COB, CRI 97+, Bluetooth APP control, cooling fan |
| 800D | LED Panel | 40 W | Bi-color and RGB; 2-light kits include 2× NP-F750 battery sets |
| Lantern Softbox 26 | Modifier | — | 26" Bowens-mount lantern, 270° beam, skirt set, quick release; hosts G100W / LS-P80S |

> Only specifications confirmed in official GVM sources (shop.gvmled.com product
> pages) are recorded. Values not published officially (e.g. lux output, CCT range
> endpoints, TLCI, DMX512) are intentionally omitted rather than estimated.

## Continuous Lighting Rules

- **Power and lux are kept separate.** No Watt-to-Lux conversion is ever performed.
- **Measurement conditions are preserved**: distance, CCT, reflector type, and
  power source are stored as fact conditions, never dropped.
- **AC/DC and battery operation are separate facts.** A light's AC-powered lux
  value is never merged with its battery-powered value.
- **"GVM claims" vs proven**: values are recorded as `SOURCE_CONFIRMED` only when
  confirmed against an official GVM source; they remain manufacturer claims
  unless independently verified.
- **No invented camera compatibility.** Compatibility relations only use
  `SUPPORTS_MODIFIER`, `REQUIRES_BATTERY`, and `SUPPORTS_GVM_MOUNT`.

## Build

```bash
npm run generate   # Generate modules from discovery data
npm run validate   # Validate all modules against schemas
npm run build      # Create deterministic .pkp archives
npm test           # Run lifecycle + packaging tests
```

## Repository Structure

```
pack-gvm/
├── schemas/          # JSON Schema definitions (11 schemas)
├── modules/          # PKP modules (brand-core, catalog, compatibility, light/, modifier/)
├── sources/          # Source and evidence records
├── coverage/         # Discovery and coverage tracking
├── tests/            # Lifecycle tests
├── tools/            # Generator, builder, validator, reports
├── reports/          # Generated validation and test reports
└── .photopack/       # Manifest
```

## License

Data: CC BY-NC 4.0. See [DATA-LICENSE.md](./DATA-LICENSE.md).
