import gzip
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import create_app

class FrontendAssetsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.raw = b'console.log("asset content");' * 200
        self.assets = ['umi.01234567.js', 'p__Login__index.89abcdef.async.js', 'umi.01234567.chunk.css', 'umi.js']
        (self.root / 'index.html').write_text('<html>OA shell</html>')
        (self.root / 'version.json').write_text('{"version":"0123456789abcdef0123456789abcdef"}')
        for name in self.assets:
            (self.root / name).write_bytes(self.raw)
            (self.root / (name + '.gz')).write_bytes(gzip.compress(self.raw))
        with patch.dict(os.environ, FRONTEND_DIST_DIR=self.directory.name):
            app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://'})
        self.client = app.test_client()
    def tearDown(self):
        self.directory.cleanup()
    def test_gzip_negotiation_and_immutable_cache(self):
        for name in self.assets[:3]:
            response = self.client.get('/' + name, headers={'Accept-Encoding': 'br, gzip'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get('Content-Encoding'), 'gzip')
            self.assertEqual(gzip.decompress(response.data), self.raw)
            self.assertIn('Accept-Encoding', response.headers['Vary'])
            self.assertIn('max-age=31536000', response.headers['Cache-Control'])
            self.assertIn('immutable', response.headers['Cache-Control'])
            self.assertIn('text/css' if name.endswith('.css') else 'javascript', response.headers['Content-Type'])
    def test_identity_fallback_and_conditional_requests(self):
        for accept in ['', 'gzip;q=0, identity', 'br']:
            response = self.client.get('/umi.01234567.js', headers={'Accept-Encoding': accept})
            self.assertEqual(response.data, self.raw)
            self.assertNotIn('Content-Encoding', response.headers)
        response = self.client.get('/umi.01234567.js', headers={'Accept-Encoding': 'gzip'})
        cached = self.client.get('/umi.01234567.js', headers={'Accept-Encoding': 'gzip', 'If-None-Match': response.headers['ETag']})
        self.assertEqual(cached.status_code, 304)
        self.assertEqual(cached.data, b'')
        identity = self.client.get('/umi.01234567.js', headers={'If-None-Match': response.headers['ETag']})
        self.assertEqual(identity.status_code, 200)
        (self.root / 'umi.01234567.js.gz').unlink()
        fallback = self.client.get('/umi.01234567.js', headers={'Accept-Encoding': 'gzip'})
        self.assertEqual(fallback.data, self.raw)
        self.assertNotIn('Content-Encoding', fallback.headers)
    def test_html_revalidates_and_assets_do_not_fall_back_to_html(self):
        for path in ['/', '/play-pricing', '/orders', '/index.html']:
            response = self.client.get(path)
            self.assertIn(b'OA shell', response.data)
            self.assertIn('no-cache', response.headers['Cache-Control'])
            self.assertNotIn('immutable', response.headers['Cache-Control'])
        legacy = self.client.get('/umi.js')
        self.assertIn('no-cache', legacy.headers['Cache-Control'])
        for path in ['/missing.async.js', '/static/missing.png', '/admin_api/missing', '/..%2Fsecret.js']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(b'OA shell', response.data)

    def test_release_manifest_is_public_uncached_and_never_spa_html(self):
        response = self.client.get('/version.json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'version': '0123456789abcdef0123456789abcdef'})
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('no-cache', response.headers['Cache-Control'])
        response = self.client.get('/version.json', headers={'If-None-Match': response.headers['ETag']})
        self.assertEqual(response.status_code, 200)
        (self.root / 'version.json').unlink()
        response = self.client.get('/version.json')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b'OA shell', response.data)
