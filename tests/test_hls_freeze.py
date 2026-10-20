from iptv_clean.models import Candidate
from iptv_clean.validate_hls import Validator

from .helpers import Clock, StreamClient


def check(client, settings):
    clock = Clock()
    result = Validator(client, settings, clock.sleep, clock.clock).validate(Candidate('浙江卫视', 'https://example.org/1080p.m3u8', ['fixture']))
    return result, clock


def test_historical_24_seconds_freeze(settings, media_samples):
    client = StreamClient(media_samples, frozen=True)
    result, clock = check(client, settings)
    assert result['reason'] == 'frozen_playlist'
    assert result['final_status'] == 'rejected'
    assert not result['live_progress_ok']
    assert clock.now >= 30
    assert len(result['snapshots']) >= 4
    assert {s['media_sequence'] for s in result['snapshots']} == {359977910}
    assert client.downloads == 1


def test_progress_real_segments_and_real_1080_probe(settings, media_samples):
    result, clock = check(StreamClient(media_samples), settings)
    assert result['final_status'] == 'passed'
    assert all(result[key] for key in ['reachable','live_progress_ok','segment_ok','resolution_verified'])
    assert result['width'] == 1920 and result['height'] == 1080
    assert len(result['segments']) == 2 and clock.now >= 30


def test_dynamic_counter_repeated_video_rejected(settings, media_samples):
    result, _ = check(StreamClient(media_samples, repeated=True), settings)
    assert result['reason'] == 'repeated_segment'


def test_dynamic_playlist_broken_segments(settings, media_samples):
    for status in ['http_404','http_403']:
        result, _ = check(StreamClient(media_samples, broken=status), settings)
        assert result['reason'] == status and result['final_status'] == 'rejected'


def test_only_first_segment_works_is_not_enough(settings,media_samples):
    result, clock = check(StreamClient(media_samples,broken='http_404',broken_after_first=True),settings)
    assert clock.now >= 30 and result['live_progress_ok']
    assert result['reason'] == 'http_404' and not result['segment_ok']
