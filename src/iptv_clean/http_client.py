import http.client
import socket
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit

from .models import Rejected, Response
from .security import canonical_url, has_credentials
from .dns import Resolver


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ips, timeout, tls=False):
        super().__init__(host, port=port, timeout=timeout)
        self.ips, self.tls = ips, tls

    def connect(self):
        # No second hostname resolution; DNS rebinding cannot change the peer.
        last = None
        deadline = time.monotonic() + self.timeout
        for ip in self.ips:
            sock = None
            try:
                family = socket.AF_INET6 if ":" in ip else socket.AF_INET
                sock = socket.socket(family, socket.SOCK_STREAM)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout()
                sock.settimeout(remaining)
                sock.connect((ip, self.port))
                self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host) if self.tls else sock
                return
            except OSError as e:
                last = e
                if sock:
                    sock.close()
        raise last or OSError("connect failed")


class SafeHTTP:
    def __init__(self, settings, dns_mode="system"):
        self.settings = settings
        self.resolver = Resolver(dns_mode, settings["http_timeout"])
        self._hosts, self._lock = {}, threading.Lock()
        self.deadline = None
        self.total_bytes = 0
        self.budget_exhausted = False

    def _charge(self, count):
        with self._lock:
            if self.total_bytes + count > self.settings['max_run_bytes']:
                self.budget_exhausted = True
                raise Rejected('run_download_budget_exceeded')
            self.total_bytes += count

    def _semaphore(self, host):
        with self._lock:
            return self._hosts.setdefault(host, threading.BoundedSemaphore(self.settings["per_host_concurrency"]))

    def get(self, url, max_bytes, byte_range=None):
        started = time.monotonic()
        seen = set()
        for _ in range(self.settings["max_redirects"] + 1):
            if self.budget_exhausted:
                raise Rejected('run_download_budget_exceeded')
            if self.deadline and time.monotonic() >= self.deadline:
                raise Rejected("run_budget_exhausted")
            url = canonical_url(url)
            if has_credentials(url):
                raise Rejected("credentialed_url")
            if url in seen:
                raise Rejected("redirect_loop")
            seen.add(url)
            p = urlsplit(url)
            port = p.port or (443 if p.scheme == "https" else 80)
            ips = self.resolver.resolve(p.hostname, port)
            with self._semaphore(p.hostname):
                timeout = min(self.settings["http_timeout"], max(0.1, self.deadline - time.monotonic())) if self.deadline else self.settings["http_timeout"]
                conn = _PinnedHTTP(p.hostname, port, ips, timeout, p.scheme == "https")
                try:
                    headers = {"User-Agent": "iptv-clean/0.1 (+HLS validation)", "Accept-Encoding": "identity", "Cache-Control": "no-cache"}
                    if byte_range:
                        start, length = byte_range
                        if length <= 0 or length > max_bytes or start < 0:
                            raise Rejected("invalid_byte_range")
                        headers["Range"] = "bytes={}-{}".format(start, start + length - 1)
                    request_started = time.monotonic()
                    conn.request("GET", p.path + ("?" + p.query if p.query else ""), headers=headers)
                    resp = conn.getresponse()
                    ttfb = time.monotonic() - request_started
                    if resp.status in (301, 302, 303, 307, 308):
                        location = resp.getheader("Location")
                        if not location:
                            raise Rejected("invalid_redirect")
                        url = urljoin(url, location)
                        continue
                    if resp.status not in (200, 206):
                        raise Rejected("http_{}".format(resp.status))
                    if byte_range:
                        start, length = byte_range
                        expected = "bytes {}-{}/".format(start, start + length - 1)
                        if resp.status != 206 or not (resp.getheader("Content-Range") or "").startswith(expected):
                            raise Rejected("invalid_byte_range")
                    elif resp.status != 200:
                        raise Rejected("unexpected_partial_response")
                    if resp.getheader("Content-Encoding", "identity").lower() != "identity":
                        raise Rejected("unsupported_encoding")
                    size = resp.getheader("Content-Length")
                    if size and int(size) > max_bytes:
                        raise Rejected("response_too_large")
                    parts, count = [], 0
                    while True:
                        remaining = self.settings["http_timeout"] - (time.monotonic() - request_started)
                        if remaining <= 0:
                            raise Rejected("http_timeout")
                        if conn.sock:
                            conn.sock.settimeout(remaining)
                        chunk = resp.read1(min(65536, max_bytes + 1 - count))
                        if not chunk:
                            break
                        self._charge(len(chunk))
                        parts.append(chunk)
                        count += len(chunk)
                        if count > max_bytes:
                            raise Rejected("response_too_large")
                    body = b"".join(parts)
                    if not body:
                        raise Rejected("empty_response")
                    if size and count != int(size):
                        raise Rejected("truncated_response")
                    if byte_range and len(body) != byte_range[1]:
                        raise Rejected("invalid_byte_range")
                    return Response(url, body, resp.status, dict(resp.getheaders()), ips,
                                    time.monotonic() - started, ttfb)
                except (TimeoutError, socket.timeout):
                    raise Rejected("http_timeout") from None
                except (OSError, ValueError, http.client.HTTPException):
                    raise Rejected("connection_failed") from None
                finally:
                    conn.close()
        raise Rejected("too_many_redirects")
