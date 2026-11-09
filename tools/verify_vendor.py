#!/usr/bin/env python3
"""Fail-closed local validation of imported upstream source and release attestations.

This is not a substitute for disconnected build/run tests or legal review.
"""

from __future__ import annotations

import argparse
import json
import sys

if __package__:
    from .vendor_sources import ROOT, MANIFEST, files_inventory, load_lock
else:
    from vendor_sources import ROOT, MANIFEST, files_inventory, load_lock


def errors() -> list[str]:
    failures: list[str] = []
    try:
        entries = load_lock()
    except (ValueError, OSError) as error:
        return [f"invalid pinned source lock: {error}"]
    if not MANIFEST.exists():
        return ["missing vendor/manifest.json: source vendoring is incomplete"]
    if MANIFEST.is_symlink():
        return ["unsafe symlinked vendor manifest"]
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["invalid vendor manifest JSON"]
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["unsupported vendor manifest schema"]
    records = manifest.get("sources")
    if not isinstance(records, list) or any(not isinstance(item, dict) or
                                            not isinstance(item.get("id"), str) for item in records):
        return ["invalid vendor manifest sources"]
    sources = {entry["id"]: entry for entry in records}
    if len(sources) != len(records):
        failures.append("duplicate vendor IDs in manifest")
    if set(sources) != {item["id"] for item in entries}:
        failures.append("vendor source list does not match pinned lock")
    for entry in entries:
        ident = entry["id"]
        record = sources.get(ident)
        if record is None:
            continue
        for key in ("repository", "commit", "path"):
            if record.get(key) != entry[key]:
                failures.append(f"{ident}: {key} differs from lock")
        dst_raw = ROOT / entry["path"]
        dst = dst_raw.resolve()
        if dst_raw.is_symlink() or not dst.is_relative_to(ROOT.resolve()) or not dst.is_dir():
            failures.append(f"{ident}: missing/unsafe vendor tree")
            continue
        license_path = dst / entry["license_file"]
        if not license_path.is_file() or not license_path.resolve().is_relative_to(dst):
            failures.append(f"{ident}: missing upstream license")
        try:
            if record.get("files") != files_inventory(dst):
                failures.append(f"{ident}: added, deleted, or modified vendored files")
        except (ValueError, OSError) as ex:
            failures.append(f"{ident}: unsafe/corrupt file tree: {ex}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="also require full offline release evidence")
    args = parser.parse_args()
    failures = errors()
    if args.release:
        # Only an explicitly structured release attestation can lift this gate.
        # A detailed release attestation validator is still a roadmap item.
        failures.append("offline release gate not implemented: disconnected build/run and license evidence required")
    if failures:
        for issue in failures:
            print(f"FAIL: {issue}", file=sys.stderr)
        return 1
    print("PASS: pinned vendored source byte inventory")
    print("NOT VERIFIED: offline transitive dependencies, runtime, tests, or redistribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
