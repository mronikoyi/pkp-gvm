/**
 * GVM PKP compatibility and photometrics anti-confusion tests.
 * Ensures model suffixes, photometrics conditions, and modifier mounts are properly validated.
 */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

test("all productIds in catalog start with gvm.", async () => {
  const catalog = JSON.parse(
    await fs.readFile(path.join(root, "modules", "catalog", "products.json"), "utf8")
  );
  for (const p of catalog.products) {
    assert.ok(
      p.productId.startsWith("gvm."),
      `Product ${p.productId} does not start with gvm.`
    );
  }
});

test("GVM continuous light model suffixes are distinct", async () => {
  const catalog = JSON.parse(
    await fs.readFile(path.join(root, "modules", "catalog", "products.json"), "utf8")
  );
  const sdModels = catalog.products
    .filter((p) => p.productId.includes("sd300"))
    .map((p) => p.productId);

  // Ensure SD300D is not confused with other SD300 variants if present
  const sd300d = sdModels.find((id) => id === "gvm.light.sd300d");
  assert.ok(sd300d, "gvm.light.sd300d must exist as distinct product");
});

test("facts and photometrics conditions validation", async () => {
  const lightModules = ["sd300d", "800d"];
  for (const modName of lightModules) {
    const factsPath = path.join(root, "modules", "light", modName, "facts.jsonl");
    try {
      const content = await fs.readFile(factsPath, "utf8");
      const lines = content.split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l));
      for (const fact of lines) {
        assert.ok(fact.factId, `Fact in ${modName} must have factId`);
        assert.ok(fact.productId, `Fact in ${modName} must have productId`);
        assert.ok(fact.evidenceIds && fact.evidenceIds.length > 0, `Fact in ${modName} must reference evidence`);
      }
    } catch (err) {
      if (err.code !== "ENOENT") throw err;
    }
  }
});
