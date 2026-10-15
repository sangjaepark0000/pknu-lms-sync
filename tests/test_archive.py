import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import pknu_lms_sync.archive as archive_module
from pknu_lms_sync.archive import Archive


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.state = self.base / "state"
        self.state.mkdir()
        self.patcher = patch.object(archive_module, "STATE_DIR", self.state)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temporary.cleanup()

    def test_versions_and_manual_edits_survive(self):
        root = self.base / "root"
        root.mkdir()
        archive = Archive(root)
        source = self.base / "source"
        target = root / "course" / "file.pdf"
        source.write_bytes(b"original")
        archive.commit("id", source, target, {})
        source.write_bytes(b"professor revision")
        archive.commit("id", source, target, {})
        self.assertEqual(target.read_bytes(), b"professor revision")
        self.assertEqual(next((target.parent / ".versions").iterdir()).read_bytes(), b"original")
        target.write_bytes(b"my notes")
        source.write_bytes(b"next revision")
        incoming = archive.commit("id", source, target, {})
        self.assertEqual(target.read_bytes(), b"my notes")
        self.assertNotEqual(incoming, target)
        self.assertEqual(incoming.read_bytes(), b"next revision")

    def test_archive_refuses_destination_outside_root(self):
        root = self.base / "root"
        root.mkdir()
        source = self.base / "source"
        source.write_bytes(b"data")
        with self.assertRaises(ValueError):
            Archive(root).commit("id", source, self.base / "outside", {})


if __name__ == "__main__":
    unittest.main()
