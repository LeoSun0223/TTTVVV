"""Conservative HLS subset: MPEG-TS/fMP4, masters, relative URIs and byte ranges.

Encrypted/DRM, LL-HLS-only and delta playlists fail closed. No key is fetched.
"""
from dataclasses import dataclass, field
import math
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from .models import Rejected
from .security import canonical_url


def attributes(value):
    return {m.group(1): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in re.finditer(r'([A-Z0-9-]+)=(?:"([^"\r\n]*)"|([^,\r\n]*))', value)}


@dataclass
class Segment:
    url: str
    duration: float
    sequence: int
    byte_range: object = None
    init: object = None

    def identity(self):
        p = urlsplit(self.url)
        # Rotating query values alone are not evidence of live progress.
        return (urlunsplit((p.scheme, p.netloc, p.path, "", "")), self.byte_range)


@dataclass
class Playlist:
    url: str
    sequence: int = 0
    target: float = 0
    segments: list = field(default_factory=list)
    variants: list = field(default_factory=list)


def parse_hls(body, base):
    try:
        text = body.decode("utf-8-sig").strip()
    except UnicodeError:
        raise Rejected("not_hls") from None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "#EXTM3U":
        raise Rejected("not_hls")
    if "#EXT-X-ENDLIST" in lines or "#EXT-X-PLAYLIST-TYPE:VOD" in lines:
        raise Rejected("vod_endlist")
    result = Playlist(base)
    pending_variant, duration, pending_range, init = None, None, None, None
    previous_range = None
    try:
        for line in lines[1:]:
            tag, _, value = line.partition(":")
            if tag in ("#EXT-X-KEY", "#EXT-X-SESSION-KEY"):
                if attributes(value).get("METHOD") != "NONE":
                    raise Rejected("unsupported_encryption")
            elif tag in ("#EXT-X-SKIP", "#EXT-X-DEFINE", "#EXT-X-I-FRAMES-ONLY", "#EXT-X-GAP"):
                raise Rejected("unsupported_hls")
            elif tag == "#EXT-X-MEDIA-SEQUENCE":
                result.sequence = int(value)
                if result.sequence < 0 or result.segments:
                    raise ValueError()
            elif tag == "#EXT-X-TARGETDURATION":
                result.target = float(value)
                if not math.isfinite(result.target) or not 0 < result.target <= 120:
                    raise ValueError()
            elif tag == "#EXT-X-STREAM-INF":
                pending_variant = attributes(value)
            elif tag == "#EXTINF":
                duration = float(value.split(",")[0])
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError()
            elif tag == "#EXT-X-BYTERANGE":
                pending_range = value
            elif tag == "#EXT-X-MAP":
                attrs = attributes(value)
                if "URI" not in attrs:
                    raise ValueError()
                init_range = parse_range(attrs["BYTERANGE"], None) if "BYTERANGE" in attrs else None
                init = (canonical_url(urljoin(base, attrs["URI"])), init_range)
            elif not line.startswith("#"):
                url = canonical_url(urljoin(base, line))
                if pending_variant is not None:
                    result.variants.append((url, pending_variant))
                    pending_variant = None
                elif duration is not None:
                    byte_range = parse_range(pending_range, previous_range[1] if previous_range and previous_range[0] == url else None) if pending_range else None
                    result.segments.append(Segment(url, duration, result.sequence + len(result.segments), byte_range, init))
                    previous_range = (url, sum(byte_range)) if byte_range else None
                    duration, pending_range = None, None
                else:
                    raise ValueError()
        if pending_variant or duration is not None or (result.segments and result.variants):
            raise ValueError()
        if not result.variants and (not result.segments or not result.target):
            raise Rejected("unsupported_hls")
    except (ValueError, TypeError, OverflowError):
        raise Rejected("invalid_hls") from None
    return result


def parse_range(value, previous_end):
    length, sep, offset = value.partition("@")
    start = int(offset) if sep else previous_end
    length = int(length)
    if start is None or start < 0 or length <= 0:
        raise ValueError()
    return (start, length)


def variant_order(variant):
    attrs = variant[1]
    try:
        height = int(attrs.get("RESOLUTION", "0x0").split("x")[1])
        # Prefer Full HD over unnecessarily heavy 4K; hints never certify quality.
        return (height >= 720, 720 <= height <= 1080, height, int(attrs.get("BANDWIDTH", 0)))
    except (ValueError, IndexError):
        return (False, False, 0, 0)


def get_media(client, url, settings, depth=0):
    if depth > 3:
        raise Rejected("master_recursion")
    response = client.get(url, settings["max_playlist_bytes"])
    playlist = parse_hls(response.body, response.url)
    if not playlist.variants:
        return playlist, response
    errors = []
    for variant, _ in sorted(playlist.variants, key=variant_order, reverse=True)[:4]:
        try:
            return get_media(client, variant, settings, depth + 1)
        except Rejected as e:
            errors.append(e.code)
    raise Rejected(errors[-1] if errors else "no_media_variant")
