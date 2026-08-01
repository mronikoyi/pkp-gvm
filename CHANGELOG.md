# Changelog — PKP GVM

## 0.1.0 — Initial Pilot Release

- 414 products canonicalized from official GVM discovery (shop.gvmled.com feed + category indexes)
- 3 pilot modules: `gvm.light.sd300d`, `gvm.light.800d`, `gvm.modifier.lantern-softbox-26`
- Continuous lighting rules enforced: power vs lux kept separate, measurement conditions preserved, AC/DC vs battery kept separate
- Pilot fact encoding with measurement conditions (distance, CCT, reflector, power)
- GVM-specific schemas (LED_PANEL kind, ELECTRICAL/OPTICAL/PHOTOMETRIC/PHYSICAL/CONTROL fact categories, SUPPORTS_GVM_MOUNT predicate)
- Deterministic ZIP build pipeline
- Compatibility module with SUPPORTS_MODIFIER, REQUIRES_BATTERY, SUPPORTS_GVM_MOUNT relations
- Lifecycle tests (install, uninstall, modular reinstall, rollback)
