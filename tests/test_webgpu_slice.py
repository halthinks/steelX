"""Hermetic tests for the byte-identical, source-pinned WebGPU core import."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.verify_webgpu_slice import RELATIVE, audit


HERE = Path(__file__).resolve().parents[1]


class TestWebgpuSlice(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="steelx-webgpu-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        dest = self.root / RELATIVE
        dest.parent.mkdir(parents=True)
        shutil.copytree(HERE / RELATIVE, dest)
        lock = self.root / "vendor/upstreams.lock.json"
        lock.write_bytes((HERE / "vendor/upstreams.lock.json").read_bytes())
        self.slice = dest

    def test_exact_upstream_core_and_licenses_pass(self):
        self.assertEqual(audit(self.root), [])

    def test_tampered_js_fails_closed(self):
        source = self.slice / "src/sim.js"
        source.write_bytes(source.read_bytes().replace(b"export class Sim", b"export class Evil", 1))
        self.assertTrue(any("hash mismatch: src/sim.js" in item for item in audit(self.root)))

    def test_tampered_license_fails_closed(self):
        license_file = self.slice / "LICENSE.md"
        license_file.write_bytes(license_file.read_bytes() + b"unauthorized change\n")
        self.assertTrue(any("hash mismatch: LICENSE.md" in item for item in audit(self.root)))

    def test_unlisted_extra_javascript_is_rejected(self):
        (self.slice / "src/unreviewed.js").write_text("export default 1\n", encoding="utf-8")
        self.assertTrue(any("unexpected or missing" in item for item in audit(self.root)))

    def test_provenance_commit_must_match_source_lock(self):
        path = self.slice / "PROVENANCE.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["commit"] = "0" * 40
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertTrue(any("does not match pinned" in item for item in audit(self.root)))

    def test_unsafe_source_path_and_missing_entry_are_rejected(self):
        path = self.slice / "PROVENANCE.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["sources"][0]["path"] = "../../escaped.js"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        failures = audit(self.root)
        self.assertTrue(any("invalid provenance file path" in item for item in failures))
        self.assertTrue(any("incomplete WebGPU" in item for item in failures))

    def test_symlinked_source_is_rejected(self):
        file = self.slice / "src/device.js"
        data = file.read_bytes()
        file.unlink()
        other = self.root / "external-device.js"
        other.write_bytes(data)
        file.symlink_to(other)
        self.assertTrue(any("symlinked WebGPU source" in item for item in audit(self.root)))


if __name__ == "__main__":
    unittest.main()
