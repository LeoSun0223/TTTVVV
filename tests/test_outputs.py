import json

from iptv_clean.models import Candidate
from iptv_clean.parse_m3u import parse_m3u
from iptv_clean.render_outputs import write_site
from iptv_clean.select_streams import select_streams

from .test_publish_gate import passing


def test_utf8_extinf_url_pairs_and_two_routes(tmp_path,channels):
    results = [passing('CCTV1'),passing('浙江卫视'),passing('浙江卫视',2,'backup.org','8.8.8.8',720)]
    candidates = {r['candidate_id']:Candidate(r['channel'],r['url'],['fixture'],{'tvg-logo':'https://example.org/logo.png'}) for r in results}
    selected = select_streams(results)
    report = {'publish_gate':{'allowed':True},'generated_at':'2026-10-20T00:00:00Z','environment':{'location':'test'}}
    target = tmp_path/'site'
    write_site(target,selected,channels,candidates,report)
    for name,count in [('live.m3u',2),('backup.m3u',3)]:
        text = (target/name).read_text()
        lines = text.splitlines()
        assert lines[0] == '#EXTM3U'
        assert len(lines) == 1 + count*2
        assert all(lines[i].startswith('#EXTINF:') and lines[i+1].startswith('https://') for i in range(1,len(lines),2))
        assert '浙江卫视' in text
    assert '卫视-备用' in (target/'backup.m3u').read_text()
    assert '浙江卫视 (备用)' in (target/'backup.m3u').read_text()
    rows,errors = parse_m3u((target/'live.m3u').read_text(),'test',channels)
    assert len(rows) == 2 and not errors
    assert json.loads((target/'report.json').read_text()) == report


def test_failed_directory_swap_rolls_back(tmp_path,channels,monkeypatch):
    import iptv_clean.render_outputs as render
    target = tmp_path/'site'
    target.mkdir()
    (target/'live.m3u').write_text('OLD')
    real_replace = render.os.replace
    def replacement(a,b):
        if a.name.startswith('.iptv-stage-'):
            raise OSError('simulated disk failure')
        real_replace(a,b)
    monkeypatch.setattr(render.os,'replace',replacement)
    report = {'publish_gate':{'allowed':True},'generated_at':'today','environment':{'location':'test'}}
    import pytest
    with pytest.raises(OSError):
        write_site(target,{},channels,{},report)
    assert (target/'live.m3u').read_text() == 'OLD'
