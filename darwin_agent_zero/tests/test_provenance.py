import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from dgm_zero.provenance import ProvenanceRecorder, fingerprint


@dataclass(frozen=True)
class FakeConfig:
    generations: int = 2
    population: int = 4
    seed: int = 11


class ProvenanceTests(unittest.TestCase):
    def test_fingerprint_records_hash_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.txt"
            path.write_text("abc", encoding="utf-8")
            fp = fingerprint(path, "sample.txt")
            self.assertIsNotNone(fp)
            self.assertEqual(fp.path, "sample.txt")
            self.assertEqual(fp.bytes, 3)
            self.assertEqual(fp.sha256, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_fingerprint_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(fingerprint(Path(tmp) / "missing.txt"))

    def test_manifest_includes_config_and_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            workspace = Path(tmp) / "workspace"
            source = root / "src" / "dgm_zero"
            source.mkdir(parents=True)
            workspace.mkdir()
            (source / "evolver.py").write_text("print('source')\n", encoding="utf-8")
            (workspace / "champion.py").write_text("def solve(a, b): return a + b\n", encoding="utf-8")

            manifest = ProvenanceRecorder(root, workspace).build(FakeConfig())

            self.assertEqual(manifest.config["generations"], 2)
            self.assertTrue(any(item.path == "src/dgm_zero/evolver.py" for item in manifest.source_files))
            self.assertTrue(any(item.path == "champion.py" for item in manifest.artifacts))

    def test_write_outputs_json_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            workspace = Path(tmp) / "workspace"
            root.mkdir()
            workspace.mkdir()
            path = workspace / "provenance.json"
            recorder = ProvenanceRecorder(root, workspace)
            recorder.write(path, recorder.build(FakeConfig()))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["config"]["seed"], 11)
            self.assertIn("python", data)
            self.assertIn("platform", data)


if __name__ == "__main__":
    unittest.main()
