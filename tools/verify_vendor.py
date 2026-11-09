#!/usr/bin/env python3
"""Fail-closed local validation of imported upstream source and release attestations.

This is not a substitute for disconnected build/run tests or legal review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from vendor_sources import ROOT, LOCK, MANIFEST, files_inventory


def errors() -> list[str]:
    failures: list[str] = []
    lock = json.loads(LOCK.read_text())
    if not MANIFEST.exists():
        return ["missing vendor/manifest.json: source vendoring is incomplete"]
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("schema_version") != 1:
        failures.append("unsupported vendor manifest schema")
    sources = {entry["id"]: entry for entry in manifest.get("sources", [])}
    if len(sources) != len(manifest.get("sources", [])):
        failures.append("duplicate vendor IDs in manifest")
    if set(sources) != {item["id"] for item in lock["sources"]}:
        failures.append("vendor source list does not match pinned lock")
    for entry in lock["sources"]:
        ident = entry["id"]
        record = sources.get(ident)
        if record is None:
            continue
        for key in ("repository", "commit", "path"):
            if record.get(key) != entry[key]:
                failures.append(f"{ident}: {key} differs from lock")
        dst = (ROOT / entry["path"]).resolve()
        if not dst.is_relative_to(ROOT) or not dst.is_dir():
            failures.append(f"{ident}: missing/unsafe vendor tree")
            continue
        if not (dst / entry["license_file"]).is_file():
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
