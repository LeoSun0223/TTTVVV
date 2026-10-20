from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import time

import pytest

import iptv_clean.http_client as http
from iptv_clean.models import Rejected


@pytest.fixture(scope='module')
def server():
    class Handler(BaseHTTPRequestHandler):
        active, peak = 0, 0
        lock = threading.Lock()

        def log_message(self,*args): pass

        def do_GET(self):
            if self.path == '/loop':
                self.send_response(302)
                self.send_header('Location','/loop')
                self.end_headers()
                return
            if self.path == '/big':
                self.send_response(200)
                self.send_header('Content-Length','999999')
                self.end_headers()
                return
            if self.path == '/truncated':
                self.send_response(200)
                self.send_header('Content-Length','10')
                self.end_headers()
                self.wfile.write(b'abc')
                return
            if self.path == '/range':
                assert self.headers['Range'] == 'bytes=2-5'
                self.send_response(206)
                self.send_header('Content-Range','bytes 2-5/10')
                self.send_header('Content-Length','4')
                self.end_headers()
                self.wfile.write(b'2345')
                return
            if self.path == '/unbounded':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'x'*120)
                return
            if self.path == '/concurrency':
                with self.lock:
                    type(self).active += 1
                    type(self).peak = max(type(self).peak,type(self).active)
                time.sleep(0.04)
                with self.lock:
                    type(self).active -= 1
            self.send_response(200)
            self.send_header('Content-Length','2')
            self.end_headers()
            self.wfile.write(b'OK')
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield server,Handler
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def client(monkeypatch,settings,server):
    server,_ = server
    def local_connect(self):
        self.sock = socket.create_connection(server.server_address, timeout=self.timeout)
    # This test-only transport substitution is not a production bypass option.
    monkeypatch.setattr(http._PinnedHTTP,'connect',local_connect)
    client = http.SafeHTTP(settings)
    client.resolver.resolve = lambda host,port:['93.184.215.14']
    return client


@pytest.mark.parametrize('path,reason', [('/loop','redirect_loop'),('/big','response_too_large'),('/truncated','truncated_response'),('/unbounded','response_too_large')])
def test_http_limits(client,path,reason):
    with pytest.raises(Rejected,match=reason):
        client.get('http://example.org'+path,100)


def test_byte_range_download(client):
    response = client.get('http://example.org/range',100,byte_range=(2,4))
    assert response.body == b'2345' and response.status == 206


def test_global_download_budget(client):
    client.settings = dict(client.settings, max_run_bytes=3)
    assert client.get('http://example.org/ok',100).body == b'OK'
    with pytest.raises(Rejected,match='run_download_budget_exceeded'):
        client.get('http://example.org/ok',100)


def test_per_host_concurrency(client,server):
    _,handler = server
    handler.peak = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _:client.get('http://example.org/concurrency',100),range(6)))
    assert all(r.body == b'OK' for r in results)
    assert 1 <= handler.peak <= 2


def test_connect_uses_pinned_ip_without_second_dns(monkeypatch):
    peers = []
    class Socket:
        def settimeout(self,t): pass
        def connect(self,peer): peers.append(peer)
        def close(self): pass
    monkeypatch.setattr(socket,'socket',lambda *a,**k:Socket())
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:pytest.fail('Unexpected second DNS lookup'))
    conn = http._PinnedHTTP('example.org',80,['93.184.215.14'],8)
    conn.connect()
    assert peers == [('93.184.215.14',80)]
