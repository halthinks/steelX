"""Minimal fail-closed tests that run without vendored content or a network."""

import pathlib
import tempfile
import unittest

from tools.vendor_sources import files_inventory


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


if __name__ == "__main__":
    unittest.main()
