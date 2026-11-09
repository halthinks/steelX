"""Hermetic fail-closed vendor import tests; local Git repositories only."""

import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import vendor_sources, verify_vendor
from tools.vendor_sources import files_inventory


def local_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.PIPE).strip()


class VendorFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(prefix="steelx-vendor-test-")
        self.addCleanup(self.tempdir.cleanup)
        self.root = pathlib.Path(self.tempdir.name) / "steelX"
        self.root.mkdir()
        self.vendor = self.root / "vendor"
        self.vendor.mkdir()
        self.lock = self.vendor / "upstreams.lock.json"
        self.manifest = self.vendor / "manifest.json"
        self.patches = [
            mock.patch.object(vendor_sources, "ROOT", self.root),
            mock.patch.object(vendor_sources, "LOCK", self.lock),
            mock.patch.object(vendor_sources, "MANIFEST", self.manifest),
            mock.patch.object(verify_vendor, "ROOT", self.root),
            mock.patch.object(verify_vendor, "MANIFEST", self.manifest),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_checkout(self, ident: str, *, licensed=True) -> tuple[pathlib.Path, str]:
        repo = pathlib.Path(self.tempdir.name) / ("upstream-" + ident)
        local_git("init", "-q", str(repo))
        (repo / "source.py").write_text(f"source = '{ident}'\n", encoding="utf-8")
        if licensed:
            (repo / "LICENSE.md").write_text("Apache-2.0 test fixture\n", encoding="utf-8")
        local_git("-C", str(repo), "add", ".")
        local_git("-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                  "commit", "-qm", "Pinned fixture")
        return repo, local_git("-C", str(repo), "rev-parse", "HEAD")

    def write_lock(self, sources: dict[str, tuple[pathlib.Path, str]]) -> None:
        self.lock.write_text(json.dumps({"schema_version": 1, "sources": [
            {"id": ident, "repository": "https://github.com/example/" + ident,
             "commit": sha, "path": "vendor/sources/" + ident,
             "license_file": "LICENSE.md"}
            for ident, (_, sha) in sources.items()
        ]}), encoding="utf-8")


class VendorInventoryTests(unittest.TestCase):
    def test_hashes_and_detects_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "a.txt").write_text("first")
            old = files_inventory(root)
            (root / "a.txt").write_text("second")
            self.assertNotEqual(old, files_inventory(root))

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "escape").symlink_to("/etc/hosts")
            with self.assertRaises(ValueError):
                files_inventory(root)


class VendorImportTests(VendorFixture):
    def test_complete_local_import_is_byte_verified(self):
        sources = {ident: self.make_checkout(ident) for ident in ("newton", "warp", "steel-webgpu")}
        self.write_lock(sources)
        records = vendor_sources.import_sources({ident: repo for ident, (repo, _) in sources.items()})
        self.assertEqual({item["id"] for item in records}, set(sources))
        self.assertEqual(verify_vendor.errors(), [])
        self.assertTrue((self.root / "vendor/sources/newton/source.py").is_file())
        (self.root / "vendor/sources/warp/source.py").write_text("tampered", encoding="utf-8")
        self.assertTrue(any("modified vendored files" in issue for issue in verify_vendor.errors()))

    def test_missing_later_license_keeps_all_destinations_unpublished(self):
        sources = {"newton": self.make_checkout("newton"), "warp": self.make_checkout("warp", licensed=False)}
        self.write_lock(sources)
        with self.assertRaisesRegex(ValueError, "required upstream license missing"):
            vendor_sources.import_sources({ident: repo for ident, (repo, _) in sources.items()})
        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.root / "vendor/sources/newton").exists())
        self.assertFalse((self.root / "vendor/sources/warp").exists())

    def test_publish_failure_rolls_back_our_own_new_vendor_tree(self):
        sources = {ident: self.make_checkout(ident) for ident in ("newton", "warp")}
        self.write_lock(sources)
        original_rename = pathlib.Path.rename

        def fail_second_publish(path, target):
            if path.name == "warp" and target == self.root / "vendor/sources/warp":
                raise OSError("injected publish failure")
            return original_rename(path, target)

        with mock.patch.object(pathlib.Path, "rename", autospec=True, side_effect=fail_second_publish):
            with self.assertRaisesRegex(OSError, "injected publish failure"):
                vendor_sources.import_sources({ident: repo for ident, (repo, _) in sources.items()})
        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.root / "vendor/sources/newton").exists())
        self.assertFalse((self.root / "vendor/sources/warp").exists())

    def test_git_lfs_pointer_does_not_count_as_vendored_content(self):
        source = self.make_checkout("newton")
        pointer = "version https://git-lfs.github.com/spec/v1\noid sha256:" + "a" * 64 + "\nsize 12345\n"
        (source[0] / "source.py").write_text(pointer, encoding="utf-8")
        local_git("-C", str(source[0]), "add", "source.py")
        local_git("-C", str(source[0]), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                  "commit", "-qm", "LFS pointer fixture")
        pinned = local_git("-C", str(source[0]), "rev-parse", "HEAD")
        self.write_lock({"newton": (source[0], pinned)})
        with self.assertRaisesRegex(ValueError, "unresolved Git LFS pointer"):
            vendor_sources.import_sources({"newton": source[0]})
        self.assertFalse(self.manifest.exists())

    def test_git_submodule_source_is_not_silently_omitted(self):
        outer = self.make_checkout("newton")
        nested = self.make_checkout("nested")
        local_git("-c", "protocol.file.allow=always", "-C", str(outer[0]), "submodule", "add",
                  str(nested[0]), "modules/nested")
        local_git("-C", str(outer[0]), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                  "commit", "-qam", "Add gitlink fixture")
        pinned = local_git("-C", str(outer[0]), "rev-parse", "HEAD")
        self.write_lock({"newton": (outer[0], pinned)})
        with self.assertRaisesRegex(ValueError, "submodules require separately pinned vendoring"):
            vendor_sources.import_sources({"newton": outer[0]})
        self.assertFalse(self.manifest.exists())

    def test_dirty_checkout_rejected_before_any_import(self):
        source = self.make_checkout("newton")
        self.write_lock({"newton": source})
        (source[0] / "source.py").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "working tree is dirty"):
            vendor_sources.import_sources({"newton": source[0]})
        self.assertFalse((self.root / "vendor/sources").exists())

    def test_wrong_commit_cannot_silently_import_newer_source(self):
        source = self.make_checkout("newton")
        self.write_lock({"newton": (source[0], "f" * 40)})
        with self.assertRaisesRegex(ValueError, "source HEAD is not the pinned commit"):
            vendor_sources.import_sources({"newton": source[0]})
        self.assertFalse(self.manifest.exists())

    def test_existing_vendor_tree_never_overwritten(self):
        source = self.make_checkout("newton")
        self.write_lock({"newton": source})
        existing = self.root / "vendor/sources/newton"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("user data", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            vendor_sources.import_sources({"newton": source[0]})
        self.assertEqual((existing / "keep.txt").read_text(), "user data")

    def test_lock_path_escape_and_duplicate_ids_rejected(self):
        source = self.make_checkout("newton")
        self.write_lock({"newton": source})
        row = json.loads(self.lock.read_text())
        row["sources"][0]["path"] = "../../unsafe"
        self.lock.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "destination"):
            vendor_sources.import_sources({"newton": source[0]})
        row["sources"][0]["path"] = "vendor/sources/newton"
        row["sources"].append(dict(row["sources"][0]))
        self.lock.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "duplicate vendor source ID"):
            vendor_sources.import_sources({"newton": source[0]})

    def test_escaping_license_path_and_vendor_symlink_rejected(self):
        source = self.make_checkout("newton")
        self.write_lock({"newton": source})
        row = json.loads(self.lock.read_text())
        row["sources"][0]["license_file"] = "../../LICENSE.md"
        self.lock.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "unsafe license_file"):
            vendor_sources.import_sources({"newton": source[0]})
        self.write_lock({"newton": source})
        outside = pathlib.Path(self.tempdir.name) / "unsafe-import-target"
        outside.mkdir()
        (self.vendor / "sources").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsafe symlinked vendor root"):
            vendor_sources.import_sources({"newton": source[0]})
        self.assertEqual(list(outside.iterdir()), [])

    def test_malformed_manifest_and_lock_fail_as_errors(self):
        source = self.make_checkout("newton")
        self.write_lock({"newton": source})
        self.manifest.write_text("not JSON", encoding="utf-8")
        self.assertIn("invalid vendor manifest JSON", verify_vendor.errors())
        self.manifest.write_text('{"schema_version": 1, "sources": [null]}', encoding="utf-8")
        self.assertIn("invalid vendor manifest sources", verify_vendor.errors())
        self.lock.write_text("broken JSON", encoding="utf-8")
        self.assertTrue(any("invalid pinned source lock" in issue for issue in verify_vendor.errors()))


if __name__ == "__main__":
    unittest.main()
