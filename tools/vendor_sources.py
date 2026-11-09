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
import re
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "vendor" / "upstreams.lock.json"
MANIFEST = ROOT / "vendor" / "manifest.json"
_SOURCE_ID = re.compile(r"[a-z][a-z0-9-]*\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z", re.IGNORECASE)


def load_lock(path: Path | None = None) -> list[dict[str, str]]:
    """Validate the untrusted source map before touching any filesystem paths."""
    path = LOCK if path is None else path
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("vendor lock is missing or invalid JSON") from error
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        raise ValueError("unsupported vendor lock schema")
    entries = lock.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValueError("vendor lock requires a nonempty sources list")
    identities: set[str] = set()
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("vendor source entry must be an object")
        ident = entry.get("id")
        commit = entry.get("commit")
        source_path = entry.get("path")
        license_path = entry.get("license_file")
        repository = entry.get("repository")
        if not isinstance(ident, str) or not _SOURCE_ID.fullmatch(ident):
            raise ValueError("invalid vendor source ID")
        if ident in identities:
            raise ValueError(f"duplicate vendor source ID: {ident}")
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise ValueError(f"{ident}: commit must be a full Git SHA-1")
        if not isinstance(source_path, str) or source_path != f"vendor/sources/{ident}":
            raise ValueError(f"{ident}: vendor destination must be vendor/sources/{ident}")
        if source_path in paths:
            raise ValueError("duplicate vendor destination")
        if not isinstance(license_path, str) or not license_path:
            raise ValueError(f"{ident}: license_file is required")
        segments = license_path.split("/")
        if any(segment in ("", ".", "..") or "\\" in segment for segment in segments):
            raise ValueError(f"{ident}: unsafe license_file")
        if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
            raise ValueError(f"{ident}: pinned upstream repository URL required")
        identities.add(ident)
        paths.add(source_path)
    return entries


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
    # git archive does not recurse into gitlinks. Never publish a source tree
    # that appears complete while silently omitting a nested repository.
    if any(line.startswith("160000 ") for line in git(repo, "ls-files", "--stage").splitlines()):
        raise ValueError(f"{repo}: submodules require separately pinned vendoring")


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
                # Git LFS exports often contain text pointers rather than the
                # declared bytes. A pointer is not an offline asset or source.
                if p.stat().st_size < 512 and p.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
                    raise ValueError(f"unresolved Git LFS pointer: {relative}")
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


def import_sources(sources: dict[str, Path]) -> list[dict]:
    """Stage and validate *all* sources before publishing any vendor tree.

    Each destination is newly created, never overwritten. In a failed commit,
    move our own newly published trees back into the temporary staging area.
    A failed import cannot advertise a partial vendor manifest.
    """
    entries = load_lock()
    expected_ids = {entry["id"] for entry in entries}
    if set(sources) != expected_ids:
        raise ValueError(f"exactly one local checkout required for: {', '.join(sorted(expected_ids))}")
    if MANIFEST.exists() or MANIFEST.is_symlink():
        raise FileExistsError(f"preserving existing vendor manifest: {MANIFEST}")
    if (ROOT / "vendor").is_symlink() or (ROOT / "vendor" / "sources").is_symlink():
        raise ValueError("unsafe symlinked vendor root")
    for entry in entries:
        src = Path(sources[entry["id"]]).resolve(strict=True)
        checked_checkout(src, entry["commit"])
        dest = ROOT / entry["path"]
        if dest.exists() or dest.is_symlink():
            raise FileExistsError(f"preserving existing vendor tree: {dest}")
        # All paths are now validated by load_lock; still forbid a symlinked
        # parent managed by another process/operator.
        if dest.parent.exists() and not dest.parent.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f"unsafe vendor parent: {dest.parent}")

    vendor_parent = ROOT / "vendor" / "sources"
    vendor_parent.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    with tempfile.TemporaryDirectory(prefix=".steelx-stage-", dir=vendor_parent) as staging:
        stage_root = Path(staging)
        for entry in entries:
            staged = stage_root / entry["id"]
            import_tree(Path(sources[entry["id"]]).resolve(), staged, entry["commit"])
            if not (staged / entry["license_file"]).is_file():
                raise ValueError(f"{entry['id']}: required upstream license missing")
            records.append({
                "id": entry["id"],
                "repository": entry["repository"],
                "commit": entry["commit"],
                "path": entry["path"],
                "files": files_inventory(staged),
            })

        manifest_bytes = (json.dumps({"schema_version": 1, "sources": records}, indent=2) + "\n").encode("utf-8")
        temporary_manifest = stage_root / "manifest.json"
        temporary_manifest.write_bytes(manifest_bytes)
        published: list[tuple[Path, Path]] = []
        try:
            for entry in entries:
                staged = stage_root / entry["id"]
                dest = ROOT / entry["path"]
                if dest.exists() or dest.is_symlink():
                    raise FileExistsError(f"preserving existing vendor tree: {dest}")
                staged.rename(dest)
                published.append((dest, staged))
            if MANIFEST.exists() or MANIFEST.is_symlink():
                raise FileExistsError(f"preserving existing vendor manifest: {MANIFEST}")
            temporary_manifest.rename(MANIFEST)
        except Exception:
            for dest, staged in reversed(published):
                dest.rename(staged)
            raise
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="ID=LOCAL_GIT_CHECKOUT")
    args = parser.parse_args()
    if any("=" not in item or not item.split("=", 1)[0] for item in args.source):
        parser.error("each --source must be ID=LOCAL_GIT_CHECKOUT")
    sources = dict(item.split("=", 1) for item in args.source)
    if len(sources) != len(args.source):
        parser.error("duplicate --source identifier")
    records = import_sources({ident: Path(path) for ident, path in sources.items()})
    for entry in records:
        print(f"imported {entry['id']} at {entry['commit']}")
    print("Source import complete; run python tools/verify_vendor.py")
    print("This does NOT mean dependencies, licenses, or offline runtime are release-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
