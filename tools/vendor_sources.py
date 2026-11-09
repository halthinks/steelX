#!/usr/bin/env python3
"""Import source-only upstream trees from local, exact-commit Git checkouts.

Maintenance command only. No network access or package installation is performed.
Existing vendor trees are never overwritten. Test with verify_vendor.py afterward.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "vendor" / "upstreams.lock.json"
MANIFEST = ROOT / "vendor" / "manifest.json"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def checked_checkout(repo: Path, expected: str) -> None:
    if git(repo, "rev-parse", "HEAD").lower() != expected.lower():
        raise ValueError(f"{repo}: source HEAD is not the pinned commit {expected}")
    # Include ignored/untracked state in the clean-check; git archive exports tracked content only.
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(f"{repo}: working tree is dirty")


def files_inventory(root: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for current, dirs, filenames in os.walk(root, followlinks=False):
        here = Path(current)
        for name in sorted(dirs + filenames):
            p = here / name
            relative = p.relative_to(root).as_posix()
            if p.is_symlink():
                resolved = p.resolve(strict=True)
                if not resolved.is_relative_to(root.resolve()):
                    raise ValueError(f"unsafe symlink: {relative}")
                result.append({"path": relative, "type": "symlink", "target": os.readlink(p)})
            elif p.is_file():
                result.append({"path": relative, "type": "file", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    return sorted(result, key=lambda entry: entry["path"])


def import_tree(src: Path, dst: Path, commit: str) -> None:
    checked_checkout(src, commit)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(f"preserving existing vendor tree: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="steelx-vendor-") as scratch:
        archive = Path(scratch) / "source.tar"
        extracted = Path(scratch) / "tree"
        extracted.mkdir()
        with archive.open("wb") as stream:
            subprocess.run(["git", "-C", str(src), "archive", "--format=tar", commit], stdout=stream, check=True)
        # Python's data filter rejects absolute paths and escaping links in archives.
        with tarfile.open(archive) as tar:
            tar.extractall(extracted, filter="data")
        extracted.rename(dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="ID=LOCAL_GIT_CHECKOUT")
    args = parser.parse_args()
    sources = dict(item.split("=", 1) for item in args.source)
    lock = json.loads(LOCK.read_text())
    expected_ids = {entry["id"] for entry in lock["sources"]}
    if set(sources) != expected_ids or len(args.source) != len(expected_ids):
        parser.error(f"exactly one --source required for each of: {', '.join(sorted(expected_ids))}")
    # Preflight every input before making any repo changes.
    for entry in lock["sources"]:
        checked_checkout(Path(sources[entry["id"]]).resolve(), entry["commit"])
        dest = ROOT / entry["path"]
        if dest.exists() or dest.is_symlink():
            parser.error(f"will not overwrite {dest}")

    records = []
    for entry in lock["sources"]:
        dst = ROOT / entry["path"]
        import_tree(Path(sources[entry["id"]]).resolve(), dst, entry["commit"])
        if not (dst / entry["license_file"]).is_file():
            raise ValueError(f"missing upstream license {dst / entry['license_file']}")
        records.append({
            "id": entry["id"],
            "repository": entry["repository"],
            "commit": entry["commit"],
            "path": entry["path"],
            "files": files_inventory(dst),
        })
        print(f"imported {entry['id']} at {entry['commit']}")
    MANIFEST.write_text(json.dumps({"schema_version": 1, "sources": records}, indent=2) + "\n")
    print("Source import complete; run python tools/verify_vendor.py")
    print("This does NOT mean dependencies, licenses, or offline runtime are release-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
