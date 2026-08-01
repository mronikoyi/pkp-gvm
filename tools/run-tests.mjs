/**
 * PKP GVM test runner — runs all .test.mjs files.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";

const root = process.cwd();
const testsDir = path.join(root, "tests");

let testFiles = [];
try {
  testFiles = (await fs.readdir(testsDir))
    .filter((f) => f.endsWith(".test.mjs"))
    .sort();
} catch (e) {
  testFiles = [];
}

let passed = 0;
let failed = 0;
const results = [];

for (const tf of testFiles) {
  const filePath = path.join(testsDir, tf);
  try {
    const output = execFileSync("node", ["--test", filePath], {
      encoding: "utf8",
      cwd: root,
      timeout: 30000,
    });
    results.push({ file: tf, status: "PASSED" });
    passed += 1;
    console.log(`✓ ${tf}`);
  } catch (error) {
    results.push({ file: tf, status: "FAILED", error: error.stderr?.slice(0, 500) || error.message });
    failed += 1;
    console.error(`✗ ${tf}`);
    console.error(error.stderr?.slice(0, 500) || error.message);
  }
}

const report = {
  schemaVersion: "1.0",
  generatedAt: new Date().toISOString(),
  status: failed === 0 ? "PASSED" : "FAILED",
  total: testFiles.length,
  passed,
  failed,
  results,
};

await fs.mkdir(path.join(root, "reports"), { recursive: true });
await fs.writeFile(
  path.join(root, "reports", "test-report.json"),
  `${JSON.stringify(report, null, 2)}\n`
);

console.log(`\n${passed} passed, ${failed} failed`);
process.exitCode = failed > 0 ? 1 : 0;
