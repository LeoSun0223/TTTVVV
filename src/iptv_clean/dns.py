"""Optional app-only DoH. Does not change OS DNS, router or proxy settings."""
import ipaddress
import json
import threading
import time
from urllib.parse import urlencode

from .models import Rejected
from .security import public_ip, resolve_public


class Resolver:
    def __init__(self, mode="system", timeout=8):
        self.mode, self.timeout = mode, timeout
        self.cache, self.lock = {}, threading.Lock()

    def resolve(self, host, port):
        try:
            ip = str(ipaddress.ip_address(host))
        except ValueError:
            ip = None
        if ip:
            if not public_ip(ip):
                raise Rejected("unsafe_destination")
            return [ip]
        if self.mode == "system":
            return resolve_public(host, port)
        from .http_client import _PinnedHTTP
        with self.lock:
            cached = self.cache.get(host)
            if cached and cached[0] > time.monotonic():
                return cached[1]
        ips = []
        for record_type in ("A", "AAAA"):
            conn = _PinnedHTTP("dns.alidns.com", 443, ["223.5.5.5"], self.timeout, True)
            try:
                conn.request("GET", "/resolve?" + urlencode({"name": host, "type": record_type}),
                             headers={"Accept": "application/dns-json"})
                response = conn.getresponse()
                body = response.read(65537)
                if response.status != 200 or len(body) > 65536:
                    raise Rejected("dns_failed")
                data = json.loads(body)
                if data.get("Status") != 0:
                    raise Rejected("dns_failed")
                ips.extend(row["data"] for row in data.get("Answer", []) if row.get("type") in (1, 28))
            except (OSError, ValueError, KeyError):
                raise Rejected("dns_failed") from None
            finally:
                conn.close()
        if not ips or any(not public_ip(ip) for ip in ips):
            raise Rejected("unsafe_destination" if ips else "dns_failed")
        with self.lock:
            self.cache[host] = (time.monotonic() + 60, ips)
        return ips
