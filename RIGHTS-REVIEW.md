# Rights Review — PKP GVM

## Sources

- GVM official shop product feed: `https://shop.gvmled.com/products.json`
- GVM official category indexes (continuous lights, LED panels, accessories, slider support, softbox modifiers, battery power)
- GVM supplemental discovery data captured from official pages

All data was extracted from publicly accessible official GVM sources for the
purpose of private collection, extraction, and packaging.

## Redistribution Risk

Redistribution risk is **accepted by the repository owner** for the private
collection/extraction/packaging workflow described in the orchestration run
state. Public publication of GVM product data remains the responsibility of the
user.

## Data Status

- **Facts**: recorded as "GVM claims" where only official marketing/spec values
  exist; verification status `SOURCE_CONFIRMED` means the value was confirmed
  against an official GVM source, not independently measured.
- **Compatibility**: relations use `SUPPORTS_MODIFIER`, `REQUIRES_BATTERY`,
  `SUPPORTS_GVM_MOUNT`; no invented camera compatibility is asserted.
- **Exclusions**: firmware binaries, full manuals, cookies, caches, and other
  sensitive temporaries are excluded from the repository and archives.

## License

- Schemas and tooling: MIT License ([LICENSE](./LICENSE))
- Factual data: CC BY-NC 4.0 ([DATA-LICENSE.md](./DATA-LICENSE.md))
