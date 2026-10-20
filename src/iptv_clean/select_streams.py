from collections import defaultdict, deque
from urllib.parse import urlsplit


def fair_candidates(candidates):
    """Round-robin sources, then hosts. No provider/port quality score."""
    by_source = defaultdict(deque)
    for c in candidates:
        by_source[c.sources[0] if c.sources else "previous"].append(c)
    interleaved = []
    while any(by_source.values()):
        for queue in by_source.values():
            if queue:
                interleaved.append(queue.popleft())
    by_host = defaultdict(deque)
    for c in interleaved:
        by_host[urlsplit(c.url).hostname].append(c)
    result = []
    while any(by_host.values()):
        for queue in by_host.values():
            if queue:
                result.append(queue.popleft())
    return result


def independent(a, b):
    def hosts(row):
        return {row.get('resolved_host')} | {urlsplit(s['url']).hostname for s in row.get('segments',[]) if s.get('url')}
    def ips(row):
        return set(row.get('resolved_ips',[])) | {ip for s in row.get('segments',[]) for ip in s.get('ips',[])}
    if (hosts(a) - {None}) & (hosts(b) - {None}):
        return False
    return not (ips(a) & ips(b))


def score(result):
    return (result['height'] >= 1080, result['height'],
            -sum(s['elapsed_seconds'] for s in result['segments']),
            -result.get('elapsed_seconds',0))


def select_streams(results):
    grouped = defaultdict(list)
    for result in results:
        if result.get('final_status') == 'passed' and all(result.get(k) for k in ('reachable','live_progress_ok','segment_ok','resolution_verified')):
            grouped[result['channel']].append(result)
    selected = {}
    for channel, candidates in grouped.items():
        ordered = sorted(candidates, key=score, reverse=True)
        primary = ordered[0]
        primary_endpoint = primary.get('resolved_url', primary['url'])
        backups = [c for c in ordered[1:] if c.get('resolved_url', c['url']) != primary_endpoint]
        backup = next((c for c in backups if independent(primary,c)), backups[0] if backups else None)
        selected[channel] = [primary] + ([backup] if backup else [])
    return selected
