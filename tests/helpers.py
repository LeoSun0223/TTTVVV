from pathlib import Path

from iptv_clean.models import Rejected, Response

FIXTURES = Path(__file__).parent / "fixtures"


class Clock:
    def __init__(self):
        self.now = 0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class StreamClient:
    def __init__(self, samples, frozen=False, low=False, master=False, broken=None, repeated=False, broken_after_first=False):
        self.samples, self.frozen, self.low = samples, frozen, low
        self.master, self.broken, self.repeated = master, broken, repeated
        self.broken_after_first = broken_after_first
        self.polls, self.downloads, self.requests = 0, 0, []

    def get(self, url, max_bytes, byte_range=None):
        self.requests.append(url)
        if self.master and url.endswith('/1080p.m3u8'):
            body = b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\nmedia.m3u8\n'
        elif url.endswith('.m3u8'):
            base = (FIXTURES / 'frozen_24s.m3u8').read_text()
            shift = 0 if self.frozen else self.polls
            for number in range(359977912, 359977909, -1):
                base = base.replace(str(number), 's' + str(number + shift))
            body = base.replace('s359', '359').encode()
            self.polls += 1
        else:
            self.downloads += 1
            if self.broken and (not self.broken_after_first or self.downloads > 1):
                raise Rejected(self.broken)
            body = self.samples['sd'] if self.low else self.samples['hd_a' if self.downloads == 1 or self.repeated else 'hd_b']
        return Response(url, body, ips=['93.184.215.14'], elapsed=0.02, ttfb=0.01)
