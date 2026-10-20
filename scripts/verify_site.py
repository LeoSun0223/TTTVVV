"""Read-only public Pages verification; also usable after an authorised deploy."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urljoin, urlsplit

from iptv_clean.http_client import SafeHTTP
from iptv_clean.__main__ import load_config


def main():
    p = argparse.ArgumentParser()
    p.add_argument('base_url')
    p.add_argument('--expected-dir', required=True)
    p.add_argument('--dns', choices=['system','alidns'], default='system')
    args = p.parse_args()
    if urlsplit(args.base_url).scheme != 'https':
        raise SystemExit('Pages 必须使用 HTTPS')
    _,_,settings = load_config('config')
    client = SafeHTTP(settings,args.dns)
    for attempt in range(6):
        try:
            for name in ['live.m3u','backup.m3u','report.json']:
                response = client.get(urljoin(args.base_url.rstrip('/')+'/',name), settings['max_source_bytes'])
                expected = (Path(args.expected_dir)/name).read_bytes()
                if response.body != expected:
                    raise ValueError('Pages 仍是旧版或内容不一致')
                if name.endswith('.m3u') and not response.body.startswith(b'#EXTM3U\n'):
                    raise ValueError('invalid_m3u')
                print(name+' HTTP '+str(response.status)+' sha256='+hashlib.sha256(expected).hexdigest())
            return 0
        except Exception as e:
            if attempt == 5:
                raise SystemExit('Pages 访问校验失败：'+type(e).__name__)
            time.sleep(10)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
