import pathlib, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import local_patches


class LocalPatchTests(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.dir, ignore_errors=True))

    def _write(self, name, text):
        p = self.dir / name
        p.write_text(text)
        return p

    def test_resolve_file_picks_largest(self):
        self._write('control-ui-share-stub.mjs', 'export {}')
        big = self._write('control-ui-share-real.mjs', 'x' * 5000)
        self.assertEqual(local_patches.resolve_file(self.dir, 'control-ui-share-*.mjs'), big)

    def test_resolve_file_none(self):
        self.assertIsNone(local_patches.resolve_file(self.dir, 'nope-*.mjs'))

    def test_status_already_applied(self):
        p = self._write('f.mjs', 'if (pathname.startsWith("/plugins/")) return { kind: "not-control-ui" };')
        self.assertEqual(local_patches.patch_status(p, local_patches.PLUGINS_ROUTE_PATCH[1]), 'ALREADY_APPLIED')

    def test_status_applyable(self):
        p = self._write('f.mjs', 'if (pathname === "/plugins" || pathname.startsWith("/plugins/")) return { kind: "not-control-ui" };')
        self.assertEqual(local_patches.patch_status(p, local_patches.PLUGINS_ROUTE_PATCH[1]), 'APPLYABLE')

    def test_status_upstream_changed(self):
        p = self._write('f.mjs', 'if (somethingElse) return { kind: "not-control-ui" };')
        self.assertEqual(local_patches.patch_status(p, local_patches.PLUGINS_ROUTE_PATCH[1]), 'UPSTREAM_CHANGED')

    def test_apply_writes_and_backs_up(self):
        p = self._write('f.mjs', 'if (pathname === "/plugins" || pathname.startsWith("/plugins/")) return { kind: "not-control-ui" };')
        bk = self.dir / 'bk'
        status = local_patches.apply_patch(p, local_patches.PLUGINS_ROUTE_PATCH[1], bk)
        self.assertEqual(status, 'APPLIED')
        self.assertIn('pathname.startsWith("/plugins/")', p.read_text())
        self.assertNotIn('pathname === "/plugins"', p.read_text())
        self.assertTrue((bk / 'f.mjs.before').is_file())
        self.assertTrue((bk / 'f.mjs.sha256').is_file())

    def test_apply_refuses_upstream_changed(self):
        p = self._write('f.mjs', 'unrelated code')
        status = local_patches.apply_patch(p, local_patches.PLUGINS_ROUTE_PATCH[1], self.dir / 'bk')
        self.assertEqual(status, 'UPSTREAM_CHANGED')
        self.assertEqual(p.read_text(), 'unrelated code')

    def test_apply_idempotent(self):
        p = self._write('f.mjs', 'if (pathname.startsWith("/plugins/")) return { kind: "not-control-ui" };')
        status = local_patches.apply_patch(p, local_patches.PLUGINS_ROUTE_PATCH[1], self.dir / 'bk')
        self.assertEqual(status, 'ALREADY_APPLIED')


if __name__ == '__main__':
    unittest.main()
