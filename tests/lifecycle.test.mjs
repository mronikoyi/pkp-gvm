/**
 * GVM PKP lifecycle tests.
 */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

test("pack-gvm directory structure exists", async () => {
  const required = [
    "schemas/product.schema.json",
    "schemas/fact.schema.json",
    "schemas/compatibility.schema.json",
    "schemas/evidence.schema.json",
    "schemas/source.schema.json",
    "schemas/chunk.schema.json",
    "schemas/module.schema.json",
    "schemas/manifest.schema.json",
    "schemas/firmware-history.schema.json",
    "schemas/menu-path.schema.json",
    "schemas/operational-rule.schema.json",
    "modules/brand-core/module.json",
    "modules/catalog/module.json",
    "modules/catalog/products.json",
    "modules/compatibility/module.json",
    "modules/compatibility/relations.jsonl",
    ".photopack/manifest.json",
    "sources/sources.json",
    "package.json",
  ];
  for (const f of required) {
    await assert.doesNotReject(fs.access(path.join(root, f)), `Missing: ${f}`);
  }
});

test("manifest modules are consistent with actual module files", async () => {
  const manifest = JSON.parse(
    await fs.readFile(path.join(root, ".photopack", "manifest.json"), "utf8")
  );
  const declaredIds = new Set(manifest.modules.map((m) => m.id));

  assert.ok(declaredIds.has("gvm.brand-core"), "Missing brand-core");
  assert.ok(declaredIds.has("gvm.catalog"), "Missing catalog");
  assert.ok(declaredIds.has("gvm.compatibility"), "Missing compatibility");
});

test("catalog products have unique productIds", async () => {
  const catalog = JSON.parse(
    await fs.readFile(path.join(root, "modules", "catalog", "products.json"), "utf8")
  );
  const ids = new Set();
  for (const p of catalog.products) {
    assert.ok(!ids.has(p.productId), `Duplicate: ${p.productId}`);
    ids.add(p.productId);
  }
  assert.ok(ids.size > 0, "Catalog must have products");
});

test("all pilot productIds are in catalog", async () => {
  const catalog = JSON.parse(
    await fs.readFile(path.join(root, "modules", "catalog", "products.json"), "utf8")
  );
  const catalogIds = new Set(catalog.products.map((p) => p.productId));

  const pilotIds = [
    "gvm.light.sd300d",
    "gvm.light.800d",
    "gvm.modifier.lantern-softbox-26"
  ];
  for (const pid of pilotIds) {
    assert.ok(catalogIds.has(pid), `Pilot product ${pid} missing from catalog`);
  }
});

test("compatibility relations reference valid schema format", async () => {
  const relations = (await fs.readFile(
    path.join(root, "modules", "compatibility", "relations.jsonl"), "utf8"
  ))
    .split(/\r?\n/)
    .filter(Boolean)
    .map((l) => JSON.parse(l));

  for (const rel of relations) {
    assert.ok(
      typeof rel.subjectId === "string" && rel.subjectId.startsWith("gvm."),
      `Relation ${rel.relationId} must use subjectId starting with "gvm."`
    );
    assert.ok(
      typeof rel.objectId === "string" && rel.objectId.startsWith("gvm."),
      `Relation ${rel.relationId} must use objectId starting with "gvm."`
    );
  }
});

test("compatibility relation endpoints reference catalog products", async () => {
  const catalog = JSON.parse(
    await fs.readFile(path.join(root, "modules", "catalog", "products.json"), "utf8")
  );
  const catalogIds = new Set(catalog.products.map((p) => p.productId));
  const relations = (await fs.readFile(
    path.join(root, "modules", "compatibility", "relations.jsonl"), "utf8"
  ))
    .split(/\r?\n/)
    .filter(Boolean)
    .map((l) => JSON.parse(l));

  for (const rel of relations) {
    assert.ok(
      catalogIds.has(rel.subjectId),
      `Relation ${rel.relationId} subjectId ${rel.subjectId} must exist in catalog`
    );
    assert.ok(
      catalogIds.has(rel.objectId),
      `Relation ${rel.relationId} objectId ${rel.objectId} must exist in catalog`
    );
  }
});
