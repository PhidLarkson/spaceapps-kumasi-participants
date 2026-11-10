"""Live-reload static server for the participant card maker.

    python3 tools/serve.py [port]

Serves the project root and reloads the browser whenever a file changes.
Nothing is written into index.html: the reload stub is injected on the way out.
"""
import functools
import http.server
import os
import pathlib
import socketserver
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
STUB = b"""
<script>
(() => {
  const es = new EventSource('/__reload');
  es.onmessage = e => { if (e.data === 'reload') location.reload(); };
  es.onerror = () => {};
})();
</script>
"""


def snapshot():
    seen = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {'.git', 'node_modules', '__pycache__'}]
        for f in filenames:
            p = os.path.join(dirpath, f)
            try:
                seen[p] = os.stat(p).st_mtime_ns
            except OSError:
                pass
    return seen


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def do_GET(self):
        if self.path.startswith('/__reload'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            last = snapshot()
            try:
                while True:
                    time.sleep(0.45)
                    now = snapshot()
                    if now != last:
                        last = now
                        self.wfile.write(b'data: reload\n\n')
                        self.wfile.flush()
                    else:
                        self.wfile.write(b': ping\n\n')
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            return

        # serve files, injecting the reload stub into HTML
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, 'index.html')
        if path.endswith('.html') and os.path.isfile(path):
            body = pathlib.Path(path).read_bytes()
            if b'</body>' in body:
                body = body.replace(b'</body>', STUB + b'</body>', 1)
            else:
                body += STUB
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_header  # noqa
        super().do_GET()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    handler = functools.partial(Handler, directory=str(ROOT))
    with Server(('127.0.0.1', port), handler) as httpd:
        print(f"serving {ROOT} at http://127.0.0.1:{port}/  (live reload on)")
        httpd.serve_forever()


if __name__ == '__main__':
    main()
