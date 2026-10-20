"""Offline artifact integrity check: every emitted URL maps to this run's proof."""
from collections import Counter
import json
from pathlib import Path
import sys

from iptv_clean.models import Candidate
from iptv_clean.parse_m3u import split_extinf
from iptv_clean.pipeline import candidate_id
from iptv_clean.security import canonical_url, has_credentials


def check(directory):
    root = Path(directory)
    report = json.loads((root/'report.json').read_text())
    assert report['publish_gate']['allowed'], 'publication gate denied'
    proofs = {r['candidate_id']:r for r in report['candidates']}
    for filename,limit in [('live.m3u',1),('backup.m3u',2)]:
        lines = (root/filename).read_text(encoding='utf-8').splitlines()
        assert lines[0] == '#EXTM3U' and (len(lines)-1) % 2 == 0
        counts = Counter()
        emitted = {}
        for index in range(1,len(lines),2):
            assert lines[index].startswith('#EXTINF:')
            attrs,title = split_extinf(lines[index])
            channel = title.removesuffix(' (备用)')
            url = canonical_url(lines[index+1])
            assert not has_credentials(url)
            key = candidate_id(Candidate(channel,url))
            proof = proofs[key]
            assert key in report['selected'][channel]
            assert proof['final_status'] == 'passed' and proof['height'] >= 720
            assert all(proof[k] for k in ['reachable','live_progress_ok','segment_ok','resolution_verified'])
            assert len(proof['segments']) >= 2 and proof['observation_seconds'] >= 24
            assert attrs['tvg-id'] == channel
            counts[channel] += 1
            emitted.setdefault(channel,[]).append(key)
        assert counts and max(counts.values()) <= limit
        assert len(counts) == report['qualified_channels']
        for channel,ids in report['selected'].items():
            assert emitted[channel] == ids[:limit]
        print(filename+': '+str(sum(counts.values()))+' 条，'+str(len(counts))+' 台，所有 URL 均对应本轮连续性/分片/720P+ 通过记录')


if __name__ == '__main__':
    check(sys.argv[1])
