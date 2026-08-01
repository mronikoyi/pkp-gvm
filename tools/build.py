#!/usr/bin/env python3
"""GVM PKP deterministic ZIP builder."""

import hashlib
import json
import os
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"
DIST = ROOT / "dist"
PHOTOPACK = ROOT / ".photopack"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def canonical_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"


def media_type(file):
    if file.endswith(".json"):
        return "application/json"
    if file.endswith(".jsonl"):
        return "application/jsonl+json"
    return "application/octet-stream"


def module_directory(module_id):
    """Map module ID to directory path."""
    return MODULES / module_id.replace("gvm.", "").replace(".", "/")


def module_product_ids(module_id):
    """Read the productIds declared by a module.json (used for the pack manifest)."""
    module_json = MODULES / module_id.replace("gvm.", "").replace(".", "/") / "module.json"
    if not module_json.exists():
        return []
    mod = json.loads(module_json.read_text(encoding="utf-8"))
    return mod.get("productIds", [])


def safe_files(directory):
    """Collect safe data-only files from a directory, rejecting scripts and binaries."""
    files = {}
    forbidden = {".pdf", ".dat", ".exe", ".dll", ".so", ".dylib",
                 ".js", ".mjs", ".cjs", ".py", ".ps1", ".sh", ".bat",
                 ".cmd", ".html", ".apk", ".jar", ".dex", ".bin", ".fw"}
    if not directory.exists():
        return files
    for entry in sorted(directory.rglob("*")):
        if entry.is_symlink():
            continue
        if entry.is_dir():
            if entry.name in (".git", "node_modules", "__pycache__", "dist", "work"):
                continue
            continue
        if entry.suffix.lower() in forbidden:
            continue
        rel = entry.relative_to(directory).as_posix()
        data = entry.read_bytes()
        if len(data) > 25 * 1024 * 1024:
            continue
        files[rel] = data
    return files


def module_manifest(module, files):
    contents = []
    for name, data in sorted(files.items()):
        contents.append({
            "path": name,
            "size": len(data),
            "mediaType": media_type(name),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return {
        "moduleId": module["id"],
        "version": module["version"],
        "dataOnly": True,
        "signatureStatus": "UNVERIFIED",
        "contents": contents,
    }


def zip_entry(name, data):
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    return info, data


def build_archive(module_record):
    module_id = module_record["id"]
    directory = module_directory(module_id)
    files = safe_files(directory)
    manifest = module_manifest(module_record, files)
    manifest_data = canonical_json(manifest)
    files["manifest.json"] = manifest_data

    archive_name = f"{module_id}-{module_record['version']}.pkp"
    archive_path = DIST / archive_name
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(files):
            info, data = zip_entry(name, files[name])
            zf.writestr(info, data)

    sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    return {
        "moduleId": module_id,
        "archiveName": archive_name,
        "archivePath": str(archive_path),
        "sha256": sha256,
        "size": archive_path.stat().st_size,
        "files": len(files),
    }


def inspect_archive(archive_path, expected_manifest):
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
        manifest_raw = zf.read("manifest.json")
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if manifest != expected_manifest:
            raise ValueError(f"Manifest mismatch in {archive_path}")
        for item in manifest["contents"]:
            path = item["path"]
            if path == "manifest.json":
                continue
            data = zf.read(path)
            digest = hashlib.sha256(data).hexdigest()
            if digest != item["sha256"]:
                raise ValueError(f"Digest mismatch for {path} in {archive_path}")


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    PHOTOPACK.mkdir(parents=True, exist_ok=True)

    records = []
    archive_records = []

    for entry in sorted(MODULES.rglob("module.json")):
        mod = json.loads(entry.read_text(encoding="utf-8"))
        arch = build_archive(mod)

        directory = module_directory(mod["id"])
        files = safe_files(directory)
        manifest = module_manifest(mod, files)
        inspect_archive(arch["archivePath"], manifest)

        rec = {
            "id": mod["id"],
            "name": mod["name"],
            "version": mod["version"],
            "kind": mod["kind"],
            "archive": arch["archiveName"],
            "sha256": arch["sha256"],
            "size": arch["size"],
            "dependencies": mod.get("dependencies", []),
            "languages": mod.get("languages", ["en", "fr"]),
        }
        records.append(rec)
        archive_records.append(arch)

    records_sorted = sorted(records, key=lambda r: r["id"])
    module_refs = [
        {
            "id": r["id"],
            "version": r["version"],
            "dependencies": r["dependencies"],
            "productIds": module_product_ids(r["id"]),
        }
        for r in records_sorted
    ]

    pkg_manifest = {
        "schemaVersion": "1.0",
        "packId": "gvm.lighting",
        "name": "GVM Lighting — PKP Photo Knowledge Pack",
        "version": "0.1.0",
        "description": "Canonical technical data for GVM continuous lights, LED panels, modifiers, and accessories",
        "publisher": {
            "name": "PKP Community"
        },
        "repository": {
            "type": "git",
            "url": None
        },
        "license": {
            "code": "MIT",
            "data": "CC-BY-NC-4.0"
        },
        "languages": ["en", "fr"],
        "requirements": {
            "pkpSpecVersion": "1.0",
            "minAppVersion": "1.0.0"
        },
        "modules": module_refs,
        "installProfiles": {
            "CATALOG_ONLY": ["gvm.brand-core", "gvm.catalog"],
            "OWNED_GEAR": ["CATALOG_ONLY", "MATCH_USER_GEAR"],
            "FULL_OFFLINE": ["ALL_MODULES"],
            "CUSTOM": []
        },
        "rightsStatus": "RISK_ACCEPTED_BY_REPOSITORY_OWNER",
        "signatureStatus": "UNSIGNED_DRAFT",
    }

    (PHOTOPACK / "manifest.json").write_text(
        canonical_json(pkg_manifest).decode("utf-8"),
        encoding="utf-8",
        newline="\n"
    )

    print(f"Built {len(records)} deterministic PKP archives in {DIST}")


if __name__ == "__main__":
    main()
