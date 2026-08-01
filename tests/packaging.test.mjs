/**
 * GVM PKP packaging tests — verifies deterministic builds and archive integrity.
 */
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { execFileSync } from "node:child_process";

const root = process.cwd();
const dist = path.join(root, "dist");

test("build archives are deterministic ZIP files", async () => {
  try {
    await fs.access(dist);
  } catch {
    return;
  }

  const assets = (await fs.readdir(dist))
    .filter((name) => name.endsWith(".pkp"))
    .sort();

  if (assets.length === 0) return;

  const inspect = (archivePath) =>
    JSON.parse(
      execFileSync(
        "python",
        [
          "-c",
          [
            "import json,stat,sys,zipfile",
            "z=zipfile.ZipFile(sys.argv[1])",
            "out=[{'name':i.filename,'size':i.file_size,'date':list(i.date_time),'symlink':stat.S_ISLNK(i.external_attr>>16)} for i in z.infolist()]",
            "print(json.dumps({'files':out,'manifest':json.loads(z.read('manifest.json'))}))",
          ].join("\n"),
          archivePath,
        ],
        { encoding: "utf8" }
      )
    );

  const forbidden = /\.(pdf|dat|exe|dll|so|dylib|js|mjs|cjs|py|ps1|sh|bat|cmd|html|apk|jar|dex|bin|fw)$/i;

  for (const asset of assets) {
    const archivePath = path.join(dist, asset);
    const result = inspect(archivePath);
    assert.equal(result.manifest.dataOnly, true, `${asset}: must be data-only`);
    assert.equal(result.manifest.signatureStatus, "UNVERIFIED");
    assert.ok(result.files.length <= 100, `${asset}: too many files`);

    for (const file of result.files) {
      assert.deepEqual(file.date, [1980, 1, 1, 0, 0, 0], `${asset}: wrong timestamp on ${file.name}`);
      assert.equal(file.symlink, false, `${asset}: symlink detected`);
      assert.equal(path.posix.isAbsolute(file.name), false);
      assert.equal(file.name.includes("\\"), false);
      assert.equal(file.name.split("/").includes(".."), false);
      assert.equal(forbidden.test(file.name), false, `${asset}: forbidden file ${file.name}`);
    }
  }
});

test("checksums file matches archives", async () => {
  try {
    await fs.access(path.join(dist, "checksums.txt"));
  } catch {
    return;
  }

  const text = await fs.readFile(path.join(dist, "checksums.txt"), "utf8");
  const sha256sums = await fs.readFile(path.join(dist, "SHA256SUMS"), "utf8");
  assert.equal(text, sha256sums, "checksums.txt and SHA256SUMS must be identical");

  const lines = text.trim().split(/\r?\n/);
  assert.ok(lines.length >= 1, "Must have at least one checksum entry");

  for (const line of lines) {
    const match = /^([a-f0-9]{64})  (.+)$/.exec(line);
    assert.ok(match, `Invalid checksum line: ${line}`);
    const data = await fs.readFile(path.join(dist, match[2]));
    assert.equal(
      crypto.createHash("sha256").update(data).digest("hex"),
      match[1],
      `Checksum mismatch for ${match[2]}`
    );
  }
});
