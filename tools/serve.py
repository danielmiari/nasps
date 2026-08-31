"""Lokal förhandsvisning med samma URL:er som i produktion.

`python3 -m http.server` hittar inte `about.html` när webbläsaren ber om
`/about` utan svarar med sin felsida. Den här servern gör samma sak som
Vercels `cleanUrls`: provar `about.html` och `about/index.html`, och faller
tillbaka på `404.html` med rätt statuskod.

    python3 tools/serve.py          # http://127.0.0.1:8000
    python3 tools/serve.py 3000     # annan port

Är porten upptagen tas nästa lediga, och den faktiska adressen skrivs ut.
"""
import http.server
import os
import posixpath
import socket
import socketserver
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def translate_path(self, path):
        """Löser rena URL:er mot filerna på disk."""
        clean = urllib.parse.urlparse(path).path
        rel = urllib.parse.unquote(clean.lstrip('/'))
        # posixpath.normpath stoppar ../ utanför projektet
        rel = posixpath.normpath(rel).lstrip('./')
        base = os.path.join(ROOT, rel.replace('/', os.sep)) if rel else ROOT

        for candidate in (base, base + '.html', os.path.join(base, 'index.html')):
            if os.path.isfile(candidate):
                return candidate
        return base

    def send_error(self, code, message=None, explain=None):
        """Visar sajtens egen 404-sida i stället för serverns."""
        page = os.path.join(ROOT, '404.html')
        if code == 404 and os.path.isfile(page):
            body = open(page, 'rb').read()
            self.send_response(404)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def taken(port):
    """Sant om något redan svarar på porten, oavsett IPv4 eller IPv6.

    Utan den här kollen kan servern binda IPv4 medan en annan process håller
    IPv6 på samma port - och webbläsaren hamnar hos fel server.
    """
    for family, addr in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.3)
                if probe.connect_ex((addr, port)) == 0:
                    return True
        except OSError:
            continue
    return False


if __name__ == '__main__':
    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    port = wanted
    while taken(port) and port < wanted + 20:
        print(f'port {port} är upptagen av något annat, provar {port + 1}')
        port += 1

    with Server(('127.0.0.1', port), Handler) as httpd:
        # 127.0.0.1 och inte localhost: localhost kan slå upp till ::1 och
        # då hamna hos en annan server på samma portnummer.
        print(f'nasps.se → http://127.0.0.1:{port}  (ctrl+c avslutar)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\navslutad')
