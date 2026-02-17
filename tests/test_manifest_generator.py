"""
test_manifest_generator.py — Coverage for manifest_generator.py

Targets the three uncovered regions:
  - iter_backpack_files: symlink handling (safe + unsafe)
  - check_required_files: missing and present required files
  - main(): CLI entry point via argv patching
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from provara.manifest_generator import (
    build_manifest,
    check_required_files,
    iter_backpack_files,
    main,
    manifest_leaves,
)
from provara.backpack_integrity import MANIFEST_EXCLUDE


class TestIterBackpackFiles(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_regular_files_included(self) -> None:
        (self.root / "a.txt").write_text("hello")
        (self.root / "b.txt").write_text("world")
        files = iter_backpack_files(self.root, set())
        paths = [f["path"] for f in files]
        self.assertIn("a.txt", paths)
        self.assertIn("b.txt", paths)

    def test_excluded_files_skipped(self) -> None:
        (self.root / "manifest.json").write_text("{}")
        (self.root / "data.txt").write_text("data")
        files = iter_backpack_files(self.root, {"manifest.json"})
        paths = [f["path"] for f in files]
        self.assertNotIn("manifest.json", paths)
        self.assertIn("data.txt", paths)

    def test_safe_symlink_within_root_included(self) -> None:
        target = self.root / "real.txt"
        target.write_text("real content")
        link = self.root / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported on this platform")
        # safe symlink (resolves inside root) should appear with a NOTE warning
        import io
        with patch("sys.stderr", new_callable=io.StringIO):
            files = iter_backpack_files(self.root, set())
        paths = [f["path"] for f in files]
        self.assertIn("link.txt", paths)

    def test_unsafe_symlink_outside_root_skipped(self) -> None:
        # Create an external target outside the backpack root
        with tempfile.TemporaryDirectory() as external:
            external_file = Path(external) / "secret.txt"
            external_file.write_text("secret")
            link = self.root / "escape.txt"
            try:
                link.symlink_to(external_file)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not supported on this platform")
            import io
            stderr_buf = io.StringIO()
            with patch("sys.stderr", new=stderr_buf):
                files = iter_backpack_files(self.root, set())
            paths = [f["path"] for f in files]
            self.assertNotIn("escape.txt", paths)
            self.assertIn("SKIPPED", stderr_buf.getvalue())

    def test_directories_not_included(self) -> None:
        subdir = self.root / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")
        files = iter_backpack_files(self.root, set())
        paths = [f["path"] for f in files]
        self.assertIn("subdir/nested.txt", paths)
        # The directory itself should not appear
        self.assertNotIn("subdir", paths)

    def test_sorted_deterministically(self) -> None:
        for name in ["z.txt", "a.txt", "m.txt"]:
            (self.root / name).write_text(name)
        files = iter_backpack_files(self.root, set())
        paths = [f["path"] for f in files]
        self.assertEqual(paths, sorted(paths))

    def test_file_metadata_correct(self) -> None:
        content = b"hello world"
        (self.root / "test.bin").write_bytes(content)
        files = iter_backpack_files(self.root, set())
        self.assertEqual(len(files), 1)
        f = files[0]
        self.assertEqual(f["path"], "test.bin")
        self.assertEqual(f["size"], len(content))
        import hashlib
        self.assertEqual(f["sha256"], hashlib.sha256(content).hexdigest())


class TestCheckRequiredFiles(unittest.TestCase):

    def _manifest(self, paths: list) -> dict:
        return {"files": [{"path": p, "sha256": "x", "size": 1} for p in paths]}

    def test_all_required_present(self) -> None:
        from provara.backpack_integrity import SPEC_REQUIRED_FILES
        # manifest.json is excluded from the check by design
        paths = [f for f in SPEC_REQUIRED_FILES if f != "manifest.json"]
        manifest = self._manifest(paths)
        missing = check_required_files(manifest)
        self.assertEqual(missing, [])

    def test_missing_required_file_detected(self) -> None:
        # Provide nothing — all required files should be reported missing
        manifest = self._manifest([])
        missing = check_required_files(manifest)
        # At least one required file should be missing
        self.assertGreater(len(missing), 0)
        # identity/genesis.json is always required
        self.assertIn("identity/genesis.json", missing)

    def test_manifest_json_not_checked(self) -> None:
        # manifest.json is excluded from the manifest itself — should never appear
        manifest = self._manifest([])
        missing = check_required_files(manifest)
        self.assertNotIn("manifest.json", missing)


class TestManifestGeneratorMain(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # Minimal files so it doesn't crash on empty directory
        (self.root / "events").mkdir()
        (self.root / "events" / "events.ndjson").write_text("")
        (self.root / "keys.json").write_text("{}")
        (self.root / "merkle_root.txt").write_text("")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_main_prints_merkle_root(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("sys.argv", ["manifest_generator", str(self.root)]):
            with redirect_stdout(buf):
                main()
        output = buf.getvalue()
        self.assertIn("merkle_root:", output)
        self.assertIn("manifest_file_count:", output)

    def test_main_write_flag_creates_files(self) -> None:
        manifest_file = self.root / "manifest.json"
        if manifest_file.exists():
            manifest_file.unlink()
        with patch("sys.argv", ["manifest_generator", str(self.root), "--write"]):
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()):
                main()
        self.assertTrue(manifest_file.exists())
        self.assertTrue((self.root / "merkle_root.txt").exists())

    def test_main_check_required_flag(self) -> None:
        import io
        stderr_buf = io.StringIO()
        with patch("sys.argv", ["manifest_generator", str(self.root), "--check-required"]):
            with patch("sys.stderr", new=stderr_buf):
                import io as _io
                from contextlib import redirect_stdout
                with redirect_stdout(_io.StringIO()):
                    main()
        # keys.json exists so some required files should be present
        # Just verify it ran without error

    def test_main_nonexistent_dir_exits(self) -> None:
        with patch("sys.argv", ["manifest_generator", "/no/such/path/xyz"]):
            with self.assertRaises(SystemExit):
                main()

    def test_main_custom_exclude(self) -> None:
        (self.root / "skip_me.txt").write_text("excluded")
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("sys.argv", [
            "manifest_generator", str(self.root), "--exclude", "skip_me.txt"
        ]):
            with redirect_stdout(buf):
                main()
        self.assertIn("merkle_root:", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
