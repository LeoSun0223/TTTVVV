from iptv_clean.probe_video import probe_video

from .helpers import StreamClient
from .test_hls_freeze import check


def test_actual_ffprobe(media_samples):
    assert probe_video(media_samples['sd'])['height'] == 360
    assert probe_video(media_samples['hd_a'])['height'] == 1080


def test_1080_url_is_actually_360(settings, media_samples):
    result, _ = check(StreamClient(media_samples, low=True), settings)
    assert result['reason'] == 'resolution_below_minimum'
    assert not result['resolution_verified']


def test_1080_master_is_actually_360(settings, media_samples):
    result, _ = check(StreamClient(media_samples, low=True, master=True), settings)
    assert result['reason'] == 'resolution_below_minimum'
    assert result['segments'][0]['height'] == 360
