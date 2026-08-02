/**
 * GVM PKP validator — validates all module data against JSON Schema.
 */
import fs from "node:fs/promises";
import path from "node:path";
import Ajv from "ajv";
import addFormats from "ajv-formats";

const root = process.cwd();
const errors = [];
const warnings = [];
const stats = {
  jsonFiles: 0,
  jsonlFiles: 0,
  jsonlRecords: 0,
  products: 0,
  modules: 0,
  facts: 0,
  rules: 0,
  menuPaths: 0,
  firmwareEvents: 0,
  chunks: 0,
  relations: 0,
  sources: 0,
  evidence: 0,
};

const readJson = async (file) => {
  try {
    const data = await fs.readFile(file, "utf8");
    return JSON.parse(data);
  } catch (err) {
    if (err.code === "ENOENT") {
      if (file.endsWith("products.json")) return { products: [] };
      if (file.endsWith("aliases.json")) return { aliases: [] };
      if (file.endsWith("sources.json")) return { sources: [], evidence: [] };
      return {};
    }
    throw err;
  }
};
const readJsonl = async (file) => {
  try {
    const data = await fs.readFile(file, "utf8");
    return data.split(/\r?\n/).filter(Boolean).map((line, index) => {
      try { return JSON.parse(line); } catch (error) {
        errors.push(`${path.relative(root, file)}:${index + 1}: invalid JSON: ${error.message}`);
        return null;
      }
    }).filter(Boolean);
  } catch (err) {
    if (err.code === "ENOENT") return [];
    throw err;
  }
};
async function* walk(directory) {
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    if ([".git", "node_modules", "work", "dist"].includes(entry.name)) continue;
    const fullPath = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) {
      errors.push(`Symbolic link is forbidden: ${path.relative(root, fullPath)}`);
    } else if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else {
      yield fullPath;
    }
  }
}

for await (const file of walk(root)) {
  if (file.endsWith(".json")) {
    stats.jsonFiles += 1;
    try { JSON.parse(await fs.readFile(file, "utf8")); }
    catch (error) { errors.push(`${path.relative(root, file)}: invalid JSON: ${error.message}`); }
  } else if (file.endsWith(".jsonl")) {
    stats.jsonlFiles += 1;
    const records = await readJsonl(file);
    stats.jsonlRecords += records.length;
  }
}

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);
const schemaNames = [
  "product", "fact", "operational-rule", "menu-path",
  "firmware-history", "chunk", "compatibility",
  "source", "evidence", "module", "manifest",
];
const validators = {};
for (const name of schemaNames) {
  validators[name] = ajv.compile(await readJson(path.join(root, "schemas", `${name}.schema.json`)));
}

const validate = (schemaName, value, location) => {
  if (validators[schemaName](value)) return;
  for (const issue of validators[schemaName].errors ?? []) {
    errors.push(`${location}${issue.instancePath || "/"} ${issue.message}`);
  }
};

// Validate catalog
const catalog = await readJson(path.join(root, "modules", "catalog", "products.json"));
const products = catalog.products;
const productIds = new Set();
for (const [index, product] of products.entries()) {
  validate("product", product, `modules/catalog/products.json#/products/${index}`);
  if (productIds.has(product.productId)) errors.push(`Duplicate productId: ${product.productId}`);
  productIds.add(product.productId);
}
stats.products = productIds.size;

// Validate .photopack/manifest.json against the manifest schema (when present)
const manifestPath = path.join(root, ".photopack", "manifest.json");
if (await fs.access(manifestPath).then(() => true).catch(() => false)) {
  const manifest = await readJson(manifestPath);
  validate("manifest", manifest, ".photopack/manifest.json");
  for (const [index, mod] of (manifest.modules ?? []).entries()) {
    for (const [pidIndex, pid] of (mod.productIds ?? []).entries()) {
      if (!productIds.has(pid)) {
        errors.push(`.photopack/manifest.json#/modules/${index}/productIds/${pidIndex}: references missing catalog product: ${pid}`);
      }
    }
  }
} else {
  warnings.push(".photopack/manifest.json not found; manifest schema validation skipped (run tools/build.py first)");
}

// Validate sources
const globalSources = await readJson(path.join(root, "sources", "sources.json"));
const sourceIds = new Set();
for (const [index, source] of globalSources.sources.entries()) {
  validate("source", source, `sources/sources.json#/sources/${index}`);
  if (sourceIds.has(source.sourceId)) errors.push(`Duplicate sourceId: ${source.sourceId}`);
  sourceIds.add(source.sourceId);
}
stats.sources = sourceIds.size;

const evidenceIds = new Set();
for (const [index, ev] of globalSources.evidence.entries()) {
  validate("evidence", ev, `sources/sources.json#/evidence/${index}`);
  if (evidenceIds.has(ev.evidenceId)) errors.push(`Duplicate evidenceId: ${ev.evidenceId}`);
  if (!sourceIds.has(ev.sourceId)) errors.push(`Evidence references missing source: ${ev.sourceId}`);
  evidenceIds.add(ev.evidenceId);
}
stats.evidence = evidenceIds.size;

// Validate modules
for await (const file of walk(path.join(root, "modules"))) {
  if (path.basename(file) === "module.json") {
    stats.modules += 1;
    const mod = await readJson(file);
    validate("module", mod, path.relative(root, file));
  } else if (path.basename(file) === "facts.jsonl") {
    const records = await readJsonl(file);
    stats.facts += records.length;
    for (const [index, fact] of records.entries()) {
      validate("fact", fact, `${path.relative(root, file)}#/${index}`);
    }
  } else if (path.basename(file) === "operational-rules.jsonl") {
    const records = await readJsonl(file);
    stats.rules += records.length;
    for (const [index, rule] of records.entries()) {
      validate("operational-rule", rule, `${path.relative(root, file)}#/${index}`);
    }
  } else if (path.basename(file) === "menu-paths.jsonl") {
    const records = await readJsonl(file);
    stats.menuPaths += records.length;
    for (const [index, mp] of records.entries()) {
      validate("menu-path", mp, `${path.relative(root, file)}#/${index}`);
    }
  } else if (path.basename(file) === "firmware-history.jsonl") {
    const records = await readJsonl(file);
    stats.firmwareEvents += records.length;
    for (const [index, fw] of records.entries()) {
      validate("firmware-history", fw, `${path.relative(root, file)}#/${index}`);
    }
  } else if (path.basename(file) === "chunks.jsonl") {
    const records = await readJsonl(file);
    stats.chunks += records.length;
    for (const [index, chk] of records.entries()) {
      validate("chunk", chk, `${path.relative(root, file)}#/${index}`);
    }
  } else if (path.basename(file) === "relations.jsonl") {
    const records = await readJsonl(file);
    stats.relations += records.length;
    for (const [index, rel] of records.entries()) {
      validate("compatibility", rel, `${path.relative(root, file)}#/${index}`);
      const location = `${path.relative(root, file)}#/${index}`;
      if (rel.subjectId && !productIds.has(rel.subjectId)) {
        errors.push(`${location}: relation subjectId references missing catalog product: ${rel.subjectId}`);
      }
      if (rel.objectId && rel.objectId.startsWith("gvm.") && !productIds.has(rel.objectId)) {
        errors.push(`${location}: relation objectId references missing catalog product: ${rel.objectId}`);
      }
    }
  }
}

const status = errors.length === 0 ? "PASS" : "FAIL";

const distDir = path.join(root, "dist");
try {
  const distFiles = await fs.readdir(distDir);
  const sigFiles = distFiles.filter(f => f.endsWith(".pkp.sig"));
  const pkpFiles = distFiles.filter(f => f.endsWith(".pkp"));
  const manifests = distFiles.filter(f => f.endsWith(".manifest.json") || f === "manifest.json");

  if (manifests.length !== 1 || manifests[0] !== "manifest.json") {
    errors.push("Release must contain exactly one manifest.json, and no .manifest.json or default.manifest.json");
  }

  if (manifests.includes("manifest.json")) {
      const manifestStr = await fs.readFile(path.join(distDir, "manifest.json"), "utf8");
      const extManifest = JSON.parse(manifestStr);
      validate("manifest", extManifest, "dist/manifest.json");
      
      if (!extManifest.packType) errors.push("packType absent");
      if (extManifest.repository.url === null) errors.push("repository.url is null");
      if (extManifest.repository.commit === null) errors.push("repository.commit is null");
      if (extManifest.version !== "0.1.1") errors.push("Manifest version must match release tag 0.1.1");
    
      for (const pkp of pkpFiles) {
        if (!distFiles.includes(pkp + ".sig")) {
          errors.push(`Archive without signature: ${pkp}`);
        }
      }
      
      if (extManifest.installProfiles.FULL_OFFLINE && extManifest.installProfiles.FULL_OFFLINE.length > 128) {
          if (extManifest.installProfiles.FULL_OFFLINE.includes("ALL_MODULES")) {
              if (extManifest.modules.length > 128) {
                  errors.push("FULL_OFFLINE exceeds 128 archives");
              }
          }
      }
      
      for (const mod of extManifest.modules) {
          if (!distFiles.includes(mod.asset)) {
              errors.push(`Manifest references missing module archive ${mod.asset}`);
          }
      }
  }

} catch (e) {
  if (e.code !== 'ENOENT') {
    errors.push(`Error checking dist folder: ${e.message}`);
  }
}

const report = {
  schemaVersion: "1.0",
  generatedAt: new Date().toISOString(),
  status,
  errors,
  warnings,
  stats,
};

await fs.mkdir(path.join(root, "reports"), { recursive: true });
await fs.writeFile(
  path.join(root, "reports", "validation-report.json"),
  JSON.stringify(report, null, 2) + "\n",
  "utf8"
);

console.log(`Validation finished: ${status} (${errors.length} errors, ${warnings.length} warnings)`);
if (errors.length > 0) {
  console.error("Errors:", errors.slice(0, 10));
  process.exitCode = 1;
}
