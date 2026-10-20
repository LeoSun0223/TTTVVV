import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from iptv_clean.models import Candidate, Rejected
from iptv_clean.pipeline import run
from iptv_clean.publish_gate import load_previous, publish_gate
from iptv_clean.render_outputs import write_site
from iptv_clean.select_streams import select_streams


def passing(channel, index=1, host='example.org', ip='93.184.215.14', height=1080):
    return {'channel':channel,'candidate_id':channel+str(index),'url':'https://'+host+'/'+str(index)+'.m3u8',
            'resolved_url':'https://'+host+'/'+str(index)+'.m3u8','resolved_host':host,'resolved_ips':[ip],
            'final_status':'passed','reachable':True,'live_progress_ok':True,'segment_ok':True,'resolution_verified':True,
            'height':height,'segments':[{'elapsed_seconds':0.1}],'elapsed_seconds':30}


def test_large_failure_keeps_previous_bytes(tmp_path,settings,channels):
    old = tmp_path/'published'
    old.mkdir()
    (old/'live.m3u').write_text('#EXTM3U\nOLD')
    (old/'backup.m3u').write_text('#EXTM3U\nOLD')
    (old/'report.json').write_text(json.dumps({'qualified_channels':45,'generated_at':'2026-10-19T00:00:00Z','published_at':'2026-10-19T00:05:00Z'}))
    before = {p.name:p.read_bytes() for p in old.iterdir()}
    selected = {c:[passing(c)] for c in list(channels.rows)[:8]}
    gate = publish_gate(selected,channels,settings,load_previous(old))
    assert not gate['allowed']
    with pytest.raises(Rejected,match='publish_gate_denied'):
        write_site(old,selected,channels,{}, {'publish_gate':gate})
    assert before == {p.name:p.read_bytes() for p in old.iterdir()}


def test_ratio_and_categories(settings,channels):
    names = list(channels.rows)
    selected = {c:[passing(c)] for c in names[:18]+names[18:30]}
    previous = {'qualified_channels':45,'generated_at':'yesterday'}
    assert publish_gate(selected,channels,settings,previous)['reason'] == 'channel_count_regression'
    selected[names[30]] = [passing(names[30])]
    selected[names[31]] = [passing(names[31])]
    assert publish_gate(selected,channels,settings,previous)['allowed']
    assert publish_gate({c:[passing(c)] for c in names[:12]},channels,settings)['reason'] == 'missing_required_category'


def test_all_fail_cold_start_no_fake_playlist(tmp_path,settings,channels):
    args = SimpleNamespace(channels=None,previous_dir=str(tmp_path/'previous'),report_dir=str(tmp_path/'report'),output_dir=str(tmp_path/'site'),dns='system',publish_local=True)
    assert run(args,[],[{'status':'failed'}],channels,settings,None) == 2
    assert not (tmp_path/'site').exists()
    report = json.loads((tmp_path/'report/report.json').read_text())
    assert report['qualified_channels'] == 0 and not report['publish_gate']['allowed']
    assert not list(tmp_path.rglob('*.m3u'))


def test_frozen_result_never_selected():
    bad = passing('浙江卫视')
    bad.update(final_status='rejected',reason='frozen_playlist',live_progress_ok=False)
    assert select_streams([bad]) == {}


def test_backup_max_two_and_independence():
    rows = [passing('CCTV1',1),passing('CCTV1',2),passing('CCTV1',3,'independent.org','8.8.8.8',720)]
    choices = select_streams(rows)['CCTV1']
    assert len(choices) == 2 and choices[1]['resolved_host'] == 'independent.org'
    rows[1]['resolved_url'] = rows[0]['resolved_url']
    assert len(select_streams(rows[:2])['CCTV1']) == 1


def test_corrupt_baseline_not_a_cold_start(tmp_path):
    (tmp_path/'report.json').write_text('{broken')
    with pytest.raises(Rejected,match='baseline_invalid'):
        load_previous(tmp_path)


def test_history_cannot_bypass_fresh_validation(tmp_path,settings,channels):
    from iptv_clean.pipeline import candidate_id
    candidate = Candidate('CCTV1','https://example.org/live.m3u8',['fixture'])
    history = tmp_path/'history.json'
    history.write_text(json.dumps({'selected':{'CCTV1':[candidate_id(candidate)]}}))
    class Offline:
        def get(self,*args,**kwargs):
            raise Rejected('http_404')
    args = SimpleNamespace(channels=None,previous_dir=str(tmp_path/'previous'),report_dir=str(tmp_path/'report'),output_dir=str(tmp_path/'site'),dns='system',publish_local=True,history_report=str(history))
    assert run(args,[candidate],[],channels,settings,Offline()) == 2
    report = json.loads((tmp_path/'report/report.json').read_text())
    assert report['qualified_channels'] == 0
    assert report['candidates'][0]['reason'] == 'http_404'
    assert not (tmp_path/'site').exists()
