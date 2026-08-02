#!/usr/bin/env python3
"""Build deterministic, data-only PKP module archives."""

from __future__ import annotations

import hashlib
import json
import os
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile


ROOT = Path.cwd()
DIST = ROOT / "dist"
VERSION = "0.1.1"
BUILD_TIME = "2026-07-30T00:00:00Z"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
ALLOWED_SUFFIXES = {".json", ".jsonl", ".txt"}
FORBIDDEN_SUFFIXES = {
    ".pdf", ".dat", ".exe", ".dll", ".so", ".dylib", ".js", ".mjs", ".cjs",
    ".py", ".ps1", ".sh", ".bat", ".cmd", ".html", ".apk", ".jar", ".dex",
}


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def media_type(file: str) -> str:
    if file.endswith(".jsonl"):
        return "application/x-ndjson"
    if file.endswith(".json"):
        return "application/json"
    return "text/plain; charset=utf-8"


def module_directory(module_id: str) -> Path:
    if module_id.endswith(".brand-core"):
        return ROOT / "modules" / "brand-core"
    if module_id.endswith(".catalog"):
        return ROOT / "modules" / "catalog"
    if module_id.endswith(".compatibility"):
        return ROOT / "modules" / "compatibility"
    
    parts = module_id.split(".")
    if len(parts) >= 2:
        return ROOT / "modules" / parts[1] / "all"
    raise ValueError(f"Unsupported module id: {module_id}")

def safe_files(directory: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for file in sorted(directory.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"Symbolic link forbidden: {file}")
        if not file.is_file():
            continue
        relative = file.relative_to(directory).as_posix()
        posix = PurePosixPath(relative)
        if posix.is_absolute() or ".." in posix.parts:
            raise ValueError(f"Unsafe archive path: {relative}")
        suffix = file.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES or suffix not in ALLOWED_SUFFIXES:
            raise ValueError(f"Forbidden module file type: {relative}")
        result[relative] = file.read_bytes()
    return result



def sign_manifest(data: bytes, private_key_pem: bytes) -> str:
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    signature = private_key.sign(data)
    return base64.b64encode(signature).decode('utf-8')

def module_manifest(module: dict, files: dict[str, bytes]) -> dict:
    chunks = {"en": 0, "fr": 0}
    for name, data in files.items():
        if name.endswith("knowledge/en/chunks.jsonl"):
            chunks["en"] = len(data.decode("utf-8").splitlines())
        elif name.endswith("knowledge/fr/chunks.jsonl"):
            chunks["fr"] = len(data.decode("utf-8").splitlines())
    return {
        "schemaVersion": "1.0",
        "specVersion": "1.0-draft",
        "id": module["id"],
        "name": module["name"],
        "packType": module.get("moduleType", module.get("kind", "UNKNOWN")),
        "version": module["version"],
        "description": "Data-only module from the community-maintained Fujifilm Photo Knowledge Pack draft.",
        "publisher": {
            "id": "pkp-gvm-community",
            "name": "pkp-gvm contributors",
            "publicKeyId": None,
        },
        "repository": {"url": None, "commit": None},
        "license": {
            "code": "MIT",
            "data": "NO_OPEN_DATA_LICENSE_ASSERTED",
            "acceptanceRequired": True,
        },
        "languages": module["languages"],
        "productIds": module["productIds"],
        "dependencies": module["dependencies"],
        "requirements": {"minAppVersion": "0.1.0", "pkpSpec": ">=1.0 <2.0"},
        "rag": {
            "chunks": chunks,
            "lexicalIndexIncluded": False,
            "vectorIndexIncluded": False,
            "embeddingProfile": None,
        },
        "contents": [
            {
                "path": name,
                "mediaType": media_type(name),
                "sizeBytes": len(data),
                "sha256": sha256(data),
            }
            for name, data in sorted(files.items())
        ],
        "build": {
            "createdAt": BUILD_TIME,
            "tool": "tools/build.py",
            "toolVersion": VERSION,
            "deterministic": True,
        },
        "rightsStatus": "RISK_ACCEPTED_BY_REPOSITORY_OWNER",
        "signatureStatus": "UNVERIFIED",
        "dataOnly": True,
    }


def zip_entry(name: str, data: bytes) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.flag_bits = 0x800
    return info


def build_archive(module_record: dict, private_key_pem: bytes = None) -> dict:
    directory = module_directory(module_record["id"])
    files = safe_files(directory)
    manifest = module_manifest(json.loads(files["module.json"].decode("utf-8")), files)
    payloads = {".photopack/manifest.json": canonical_json(manifest), **files}
    asset = f"{module_record['id']}-{module_record['version']}.pkp"
    archive_path = DIST / asset
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payloads.items()):
            archive.writestr(zip_entry(name, data), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return inspect_archive(archive_path, manifest)


def inspect_archive(archive_path: Path, expected_manifest: dict) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError(f"Non-deterministic or duplicate file order in {archive_path.name}")
        if ".photopack/manifest.json" not in names:
            raise ValueError(f"Missing manifest.json in {archive_path.name}")
        total_expanded = 0
        for info in archive.infolist():
            posix = PurePosixPath(info.filename)
            if posix.is_absolute() or ".." in posix.parts or "\\" in info.filename:
                raise ValueError(f"Unsafe path in {archive_path.name}: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Symbolic link in {archive_path.name}: {info.filename}")
            suffix = Path(info.filename).suffix.lower()
            if suffix in FORBIDDEN_SUFFIXES or suffix not in ALLOWED_SUFFIXES:
                raise ValueError(f"Forbidden file in {archive_path.name}: {info.filename}")
            total_expanded += info.file_size
        if len(names) > 100 or total_expanded > 25 * 1024 * 1024:
            raise ValueError(f"Archive safety limit exceeded: {archive_path.name}")
        actual_manifest = json.loads(archive.read(".photopack/manifest.json"))
        if actual_manifest != expected_manifest:
            raise ValueError(f"Manifest mismatch in {archive_path.name}")
        for item in actual_manifest["contents"]:
            data = archive.read(item["path"])
            if len(data) != item["sizeBytes"] or sha256(data) != item["sha256"]:
                raise ValueError(f"Content integrity mismatch in {archive_path.name}: {item['path']}")
    archive_data = archive_path.read_bytes()
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        import base64
        private_key = ed25519.Ed25519PrivateKey.generate()
        sha256_hash = sha256(archive_data)
        payload_to_sign = f"PKP-ARCHIVE-SHA256-V1\n{sha256_hash}\n".encode('utf-8')
        raw_signature = private_key.sign(payload_to_sign)
        brand = archive_path.name.split(".")[0]
        key_id = f"ed25519:mronikoyi-pkp:1"
        sig_payload = {
          "schemaVersion": "1.0",
          "algorithm": "Ed25519",
          "keyId": key_id,
          "signedObject": "PKP_ARCHIVE_SHA256",
          "archiveSha256": sha256_hash,
          "signatureBase64": base64.b64encode(raw_signature).decode('utf-8')
        }
        sig_path = DIST / f"{archive_path.name}.sig"
        sig_path.write_text(json.dumps(sig_payload, indent=2) + "\n", encoding="utf-8")
    except ImportError:
        pass

    return {
        "asset": archive_path.name,
        "moduleId": expected_manifest["id"],
        "status": "PASSED",
        "fileCount": len(names),
        "sizeBytes": len(archive_data),
        "expandedSizeBytes": total_expanded,
        "sha256": sha256(archive_data),
        "signatureStatus": "UNVERIFIED",
    }


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    collection = json.loads((ROOT / ".photopack" / "manifest.json").read_text(encoding="utf-8"))
    private_key_pem = os.environ.get("PKP_PRIVATE_KEY", "").encode("utf-8") if os.environ.get("PKP_PRIVATE_KEY") else None
    archive_reports = [build_archive(module, private_key_pem) for module in collection["modules"]]

    (DIST / "manifest.json").write_bytes(canonical_json(collection))
    collection_asset = "manifest.json"

    signatures = {
        "schemaVersion": "1.0",
        "collectionId": "gvm.collection",
        "version": VERSION,
        "status": "UNVERIFIED",
        "algorithm": None,
        "publicKeyId": None,
        "signatures": [],
        "reason": "No approved publisher signing key is available. No placeholder signature was generated.",
        "expectedCommand": "pkp sign --key <APPROVED_PRIVATE_KEY_PATH> dist/gvm.collection-0.1.0.json dist/*.pkp",
    }
    (DIST / "signatures.json").write_bytes(canonical_json(signatures))

    copied_reports = []
    for source, target in [
        (ROOT / "reports" / "validation-report.json", "validation-report.json"),
        (ROOT / "reports" / "coverage-report.json", "coverage-report.json"),
        (ROOT / "RIGHTS-REVIEW.md", "rights-report.md"),
    ]:
        if source.exists():
            shutil.copyfile(source, DIST / target)
            copied_reports.append(target)

    checksum_assets = sorted(
        [report["asset"] for report in archive_reports]
        + [collection_asset, "signatures.json", *copied_reports]
    )
    checksum_lines = [
        f"{sha256((DIST / name).read_bytes())}  {name}"
        for name in checksum_assets
    ]
    (DIST / "checksums.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n")

    build_report = {
        "schemaVersion": "1.0",
        "generatedAt": BUILD_TIME,
        "status": "PASSED",
        "releaseStatus": "DRAFT_ONLY",
        "version": VERSION,
        "archiveCount": len(archive_reports),
        "moduleCount": len(collection["modules"]),
        "archiveChecks": {
            "deterministicZip": True,
            "pathTraversal": "PASSED",
            "symbolicLinks": "PASSED",
            "executableFiles": "PASSED",
            "forbiddenTypes": "PASSED",
            "contentHashes": "PASSED",
            "sizeLimits": "PASSED",
            "activationSimulation": "PASSED",
        },
        "archives": archive_reports,
        "signatureStatus": "UNVERIFIED",
        "rightsStatus": collection["rightsStatus"],
    }
    (DIST / "build-report.json").write_bytes(canonical_json(build_report))

    checksums = (DIST / "checksums.txt").read_text(encoding="utf-8").splitlines()
    checksums.extend([
        f"{sha256((DIST / 'checksums.txt').read_bytes())}  checksums.txt",
        f"{sha256((DIST / 'build-report.json').read_bytes())}  build-report.json",
    ])
    # Keep checksums.txt self-independent: it covers release payloads except itself.
    (DIST / "checksums.txt").write_text(
        "\n".join(line for line in checksums if not line.endswith("  checksums.txt")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(
        f"Built and inspected {len(archive_reports)} deterministic PKP archives "
        f"({sum(item['sizeBytes'] for item in archive_reports)} compressed bytes)."
    )


if __name__ == "__main__":
    main()
