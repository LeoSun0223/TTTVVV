import re
from collections import Counter

from .models import Candidate, Rejected
from .security import canonical_url, has_credentials

ATTR = re.compile(r'([\w-]+)\s*=\s*"([^"\r\n]*)"')


def split_extinf(line):
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            return dict(ATTR.findall(line[:i])), line[i + 1:].strip()
    raise Rejected("invalid_extinf")


def parse_m3u(text, source, channels):
    text = text.lstrip("\ufeff").strip()
    if not text or text.splitlines()[0].split()[0] != "#EXTM3U":
        raise Rejected("not_m3u")
    found, rejected, pending, dependent = [], Counter(), None, False
    for raw in text.splitlines()[1:]:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            if pending:
                rejected["missing_url"] += 1
            try:
                pending = split_extinf(line)
            except Rejected as e:
                rejected[e.code] += 1
                pending = None
            dependent = False
        elif line.startswith(("#EXTVLCOPT:", "#KODIPROP:", "#EXTHTTP:")):
            dependent = True
        elif not line.startswith("#"):
            if not pending:
                rejected["orphan_url"] += 1
                continue
            attrs, name = pending
            pending = None
            # A matching tvg-id must not turn an unknown or 4K channel into CCTV1.
            channel = channels.normalize(name)
            if not channel:
                rejected["out_of_scope"] += 1
                continue
            try:
                url = canonical_url(line)
                if re.search(r"\.(mp4|swf|flv|html?)(?:[?#]|$)", url, re.I):
                    raise Rejected("unsupported_url")
                if dependent or has_credentials(url):
                    raise Rejected("credentialed_or_header_dependent")
                found.append(Candidate(channel, url, [source], attrs))
            except Rejected as e:
                rejected[e.code] += 1
    if pending:
        rejected["missing_url"] += 1
    return found, dict(rejected)


def deduplicate(candidates):
    unique = {}
    for candidate in candidates:
        key = (candidate.channel, candidate.url)
        if key in unique:
            unique[key].sources = list(dict.fromkeys(unique[key].sources + candidate.sources))
        else:
            unique[key] = candidate
    return list(unique.values())
