"""Actual Gunicorn transport regression, only a disposable loopback WSGI process."""
import contextlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.request import Request, urlopen


@unittest.skipUnless(shutil.which('gunicorn'), 'requires the image Gunicorn runtime')
class IdleConnectionTest(unittest.TestCase):
    @contextlib.contextmanager
    def server(self, baseline=False):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'probe.py').write_text('''def application(environ, start_response):
    length=int(environ.get('CONTENT_LENGTH') or 0)
    if length: environ['wsgi.input'].read(length)
    start_response('200 OK', [('Content-Type','application/json')])
    return [b'{"status":"healthy"}']
''')
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            config = Path(__file__).resolve().parents[1] / 'gunicorn.conf.py'
            command = ['gunicorn', '-c', str(config), '-w', '4', '--graceful-timeout', '1',
                       '-b', '127.0.0.1:'+str(port), '--chdir', directory, 'probe:application']
            if baseline:
                command += ['--worker-class', 'sync', '--threads', '1']
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    try:
                        with urlopen('http://127.0.0.1:'+str(port)+'/health', timeout=.2) as response:
                            self.assertEqual(response.status, 200)
                        break
                    except Exception:
                        if process.poll() is not None: self.fail('Gunicorn did not start')
                        time.sleep(.05)
                else: self.fail('Gunicorn readiness timed out')
                yield port
            finally:
                process.terminate()
                try: process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=2)

    @contextlib.contextmanager
    def stalled_clients(self, port, partial=False):
        connections = []
        try:
            for _ in range(4):
                connection = socket.create_connection(('127.0.0.1', port), timeout=1)
                if partial: connection.sendall(b'POST /probe HTTP/1.1\r\nHost: localhost\r\nContent-Length: 20\r\n\r\nx')
                connections.append(connection)
            yield
        finally:
            for connection in connections: connection.close()

    def test_sync_baseline_is_exhausted_by_four_idle_connections(self):
        with self.server(baseline=True) as port, self.stalled_clients(port):
            with self.assertRaises(TimeoutError):
                urlopen('http://127.0.0.1:'+str(port)+'/health', timeout=.5)

    def test_health_static_and_normal_post_survive_idle_and_partial_clients(self):
        with self.server() as port, self.stalled_clients(port), self.stalled_clients(port, partial=True):
            for path, body in [('/health', None), ('/version.json', None), ('/probe', b'{"probe":true}')]:
                request = Request('http://127.0.0.1:'+str(port)+path, data=body)
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response)['status'], 'healthy')
