"""Fail closed on private destinations; pin the validated IP at connect time."""
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .models import Rejected

SENSITIVE = re.compile(r"token|auth|sign|secret|pass|cookie|session|credential|api.?key|expires|expire|^key$|^user$|^uid$|^ws(time|secret)$|^tx(time|secret)$", re.I)


def canonical_url(raw):
    raw = raw.strip()
    if (not raw or len(raw) > 8192 or re.search(r"[\x00-\x20\x7f\\|]", raw)
            or len(re.findall(r"https?://", raw, re.I)) != 1
            or re.search(r"%(?![0-9a-fA-F]{2})", raw)):
        raise Rejected("invalid_url")
    try:
        p = urlsplit(raw)
        if p.scheme.lower() not in ("http", "https") or not p.hostname:
            raise ValueError()
        if p.username is not None or p.password is not None:
            raise Rejected("credentials_in_url")
        host = p.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = p.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
        authority = "[{}]".format(host) if ":" in host else host
        if port and port != (443 if p.scheme.lower() == "https" else 80):
            authority += ":{}".format(port)
        return urlunsplit((p.scheme.lower(), authority, quote(p.path or "/", safe="/%:@!$&'()*+,;=-._~"), p.query, ""))
    except (ValueError, UnicodeError):
        raise Rejected("invalid_url") from None


def has_credentials(url):
    return any(SENSITIVE.search(k) for k, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True))


def redact_url(url):
    try:
        p = urlsplit(url)
        # All query values are hidden, including unrecognised token names.
        host = p.hostname or ""
        authority = "[{}]".format(host) if ":" in host else host
        if p.port:
            authority += ":{}".format(p.port)
        return urlunsplit((p.scheme, authority, p.path,
                           urlencode([(k, "REDACTED") for k, _ in parse_qsl(p.query, keep_blank_values=True)]), ""))
    except ValueError:
        return "[invalid URL]"


def public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if getattr(ip, 'sixtofour', None) and not public_ip(str(ip.sixtofour)):
            return False
        if getattr(ip, 'teredo', None) and not all(public_ip(str(v)) for v in ip.teredo):
            return False
        if isinstance(ip, ipaddress.IPv6Address) and ip in ipaddress.ip_network('64:ff9b::/96'):
            return public_ip(str(ipaddress.IPv4Address(int(ip) & 0xffffffff)))
        return ip.is_global and not (ip.is_multicast or ip.is_unspecified or ip.is_reserved)
    except ValueError:
        return False


def resolve_public(host, port, resolver=socket.getaddrinfo):
    try:
        records = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise Rejected("dns_failed") from None
    ips = list(dict.fromkeys(r[4][0] for r in records))
    if not ips or any(not public_ip(ip) for ip in ips):
        raise Rejected("unsafe_destination")
    return ips
