import io
import json
import pathlib
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import extensions
from stacklib import StackError


class ReviewedAliasTests(unittest.TestCase):
    def archive(self, destination):
        blob = io.BytesIO()
        with tarfile.open(fileobj=blob, mode="w") as archive:
            script = tarfile.TarInfo("open-gstack-browser/setup")
            script.mode = 0o755
            script.size = 4
            archive.addfile(script, io.BytesIO(b"true"))
            alias = tarfile.TarInfo("connect-chrome")
            alias.type = tarfile.SYMTYPE
            alias.linkname = destination
            archive.addfile(alias)
        return blob.getvalue()

    def test_reviewed_alias_becomes_regular_files_with_executable_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory)
            extensions.safe_extract(self.archive("open-gstack-browser"), target,
                                    {"connect-chrome": "open-gstack-browser"})
            self.assertFalse((target / "connect-chrome").is_symlink())
            self.assertEqual((target / "connect-chrome/setup").read_bytes(), b"true")
            self.assertEqual((target / "connect-chrome/setup").stat().st_mode & 0o111, 0o111)

    def test_changed_alias_target_cannot_escape_the_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StackError):
                extensions.safe_extract(self.archive("../outside"), pathlib.Path(directory),
                                        {"connect-chrome": "open-gstack-browser"})

    def test_links_remain_rejected_without_explicit_reviewed_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StackError):
                extensions.safe_extract(self.archive("open-gstack-browser"), pathlib.Path(directory))


class LicenseEvidenceTests(unittest.TestCase):
    def test_explicit_license_document_is_recorded_in_source_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"sources": [{
                "id": "diagram", "repo": "example/diagram", "ref": "main",
                "license_evidence": ["README.md"], "skills": [],
            }]}))
            def snapshot(repo, ref, target, links=None):
                target.mkdir(parents=True)
                (target / "README.md").write_text("## License\n\nMIT\n")
                return "a" * 40
            with patch.object(extensions, "snapshot", side_effect=snapshot):
                extensions.stage(manifest, root / "stage")
            source = json.loads((root / "stage/sources.lock.json").read_text())["sources"][0]
        self.assertEqual(source["licenses"], ["README.md"])
