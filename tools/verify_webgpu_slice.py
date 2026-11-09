#!/usr/bin/env python3
"""Fail-closed source hash and license audit for the pinned WebGPU core slice.

Runs with Python stdlib, no network, package manager, Git installation, or GPU.
It does not qualify the full engine for offline release or verify a signature.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path("vendor/browser/steel-webgpu")
SOURCE_FILES = {f"src/{name}.js" for name in ("artwgsl", "builder", "device", "loaders", "sim", "wgsl")}
PINNED_FILES = SOURCE_FILES | {"LICENSE.md", "UPSTREAM_ROOT_LICENSE.md"}
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


def _safe_relative(path: object) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and not path.startswith("/")
        and "\\" not in path
        and all(segment not in ("", ".", "..") for segment in path.split("/"))
    )


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def audit(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    slice_root = root / RELATIVE
    manifest_file = slice_root / "PROVENANCE.json"
    lock_file = root / "vendor/upstreams.lock.json"
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return ["missing or symlinked WebGPU slice provenance manifest"]
    try:
        manifest = _json(manifest_file)
        lock = _json(lock_file)
    except (OSError, UnicodeError, ValueError) as error:
        return [f"invalid WebGPU provenance or source lock: {error}"]
    entries = lock.get("sources")
    if not isinstance(entries, list):
        return ["invalid upstream source list"]
    matched = [x for x in entries if isinstance(x, dict) and x.get("id") == "steel-webgpu"]
    if len(matched) != 1 or manifest.get("schema_version") != 1:
        return ["missing pinned WebGPU source or invalid provenance schema"]
    pinned = matched[0]
    if manifest.get("repository") != pinned.get("repository") or manifest.get("commit") != pinned.get("commit"):
        errors.append("WebGPU provenance does not match pinned upstream source")
    if manifest.get("license") != "Apache-2.0":
        errors.append("WebGPU license designation differs from approved source")
    if slice_root.is_symlink() or not slice_root.resolve().is_relative_to(root.resolve()):
        return errors + ["WebGPU source root escapes repository"]
    if (slice_root / "src").is_symlink():
        return errors + ["symlinked WebGPU source directory"]
    files = manifest.get("sources")
    if not isinstance(files, list):
        return errors + ["invalid WebGPU file inventory"]
    paths: set[str] = set()
    for record in files:
        if not isinstance(record, dict) or not _safe_relative(record.get("path")):
            errors.append("invalid provenance file path")
            continue
        path = record["path"]
        if path in paths:
            errors.append(f"duplicate WebGPU source file: {path}")
            continue
        paths.add(path)
        if path not in PINNED_FILES:
            errors.append(f"unapproved WebGPU source file: {path}")
            continue
        upstream = record.get("upstream_path")
        expected_upstream = (
            "LICENSE.md" if path == "UPSTREAM_ROOT_LICENSE.md"
            else "packages/steel-webgpu/LICENSE.md" if path == "LICENSE.md"
            else "packages/steel-webgpu/" + path
        )
        if upstream != expected_upstream:
            errors.append(f"incorrect upstream attribution: {path}")
        sha1 = record.get("git_blob_sha1")
        sha256 = record.get("sha256")
        if not isinstance(sha1, str) or not HEX40.fullmatch(sha1) or not isinstance(sha256, str) or not HEX64.fullmatch(sha256):
            errors.append(f"invalid hashes: {path}")
            continue
        file = slice_root / path
        if not file.is_file() or file.is_symlink():
            errors.append(f"missing or symlinked WebGPU source: {path}")
            continue
        data = file.read_bytes()
        blob_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob_hash != sha1 or hashlib.sha256(data).hexdigest() != sha256:
            errors.append(f"WebGPU source hash mismatch: {path}")
    if paths != PINNED_FILES:
        errors.append(f"incomplete WebGPU source inventory: {', '.join(sorted(PINNED_FILES - paths))}")
    actual = {p.relative_to(slice_root).as_posix() for p in (slice_root / "src").rglob("*") if p.is_file() or p.is_symlink()}
    if actual != SOURCE_FILES:
        errors.append("unexpected or missing files inside vendored WebGPU source tree")
    return errors


if __name__ == "__main__":
    failures = audit()
    for failure in failures:
        print("FAIL:", failure)
    if failures:
        raise SystemExit(1)
    print("PASS: pinned WebGPU core source and license bytes match provenance; offline release is not qualified")
