import socket

import pytest

from iptv_clean.dns import Resolver
from iptv_clean.http_client import SafeHTTP
from iptv_clean.models import Rejected
from iptv_clean.security import canonical_url, public_ip, redact_url, resolve_public


@pytest.mark.parametrize('ip', ['127.0.0.1','10.0.0.1','172.16.0.1','192.168.1.1','169.254.169.254','100.100.100.200','198.18.0.81','0.0.0.0','::1','fc00::1','fe80::1','::ffff:127.0.0.1','224.0.0.1','2002:7f00:1::','64:ff9b::7f00:1'])
def test_private_literal(ip):
    assert not public_ip(ip)
    with pytest.raises(Rejected, match='unsafe_destination'):
        Resolver().resolve(ip,80)


def test_mixed_dns_is_rejected():
    def resolver(*args, **kwargs):
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,80)) for ip in ['93.184.215.14','10.0.0.1']]
    with pytest.raises(Rejected, match='unsafe_destination'):
        resolve_public('example.org',80,resolver)


def test_redirect_revalidated_before_connect(monkeypatch,settings):
    import iptv_clean.http_client as http
    opened = []
    class Reply:
        status = 302
        def getheader(self,key):
            return 'http://169.254.169.254/latest/meta-data/' if key == 'Location' else None
    class Connection:
        def __init__(self,host,port,ips,*args):
            opened.append((host,ips))
        def request(self,*args,**kwargs): pass
        def getresponse(self): return Reply()
        def close(self): pass
    client = SafeHTTP(settings)
    original = client.resolver.resolve
    client.resolver.resolve = lambda host,port: ['93.184.215.14'] if host == 'example.org' else original(host,port)
    monkeypatch.setattr(http,'_PinnedHTTP',Connection)
    with pytest.raises(Rejected, match='unsafe_destination'):
        client.get('https://example.org/a',100)
    assert opened == [('example.org',['93.184.215.14'])]


@pytest.mark.parametrize('url', ['http://user:pass@example.org/a', 'http://example.org/a\nX:b', 'http://example.org/a\\b', 'http://example.org/a%xy', 'http://example.org:99999/a'])
def test_invalid_url(url):
    with pytest.raises(Rejected): canonical_url(url)


def test_redaction():
    result = redact_url('https://user:pass@example.org/a?token=very-secret&odd=also-secret')
    assert 'very-secret' not in result and 'also-secret' not in result and 'pass' not in result


def test_redaction_keeps_ipv6_and_port():
    assert redact_url('http://[2606:4700::1111]:8080/a?v=x') == 'http://[2606:4700::1111]:8080/a?v=REDACTED'
