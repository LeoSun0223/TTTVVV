import pytest

from iptv_clean.models import Rejected
from iptv_clean.parse_m3u import deduplicate, parse_m3u


def test_bom_crlf_metadata_and_duplicate(channels):
    text = '\ufeff#EXTM3U\r\n#EXTINF:-1 tvg-id="cctv1" tvg-name="综合" tvg-logo="https://example.org/a,b.png" group-title="央视",CCTV-1综合\r\nhttps://EXAMPLE.org:443/live/%E4%B8%AD.m3u8  \r\n'
    rows, errors = parse_m3u(text, "a", channels)
    assert not errors
    assert rows[0].channel == "CCTV1"
    assert rows[0].attrs['tvg-logo'].endswith('a,b.png')
    assert rows[0].url == 'https://example.org/live/%E4%B8%AD.m3u8'
    other, _ = parse_m3u(text, "b", channels)
    result = deduplicate(rows + other)
    assert len(result) == 1 and result[0].sources == ['a','b']


@pytest.mark.parametrize("url", ['udp://example.org/1', 'rtsp://example.org/1', 'http://example.org/a.swf', 'http://example.org/a.mp4', 'http://example.org/a#http://evil.org/b', 'http://example.org/a|User-Agent=x', 'http://example.org/a?token=secret'])
def test_bad_urls(url, channels):
    rows, errors = parse_m3u('#EXTM3U\n#EXTINF:-1,CCTV1\n'+url, 'a', channels)
    assert rows == [] and errors


@pytest.mark.parametrize('text',['<html>hello</html>','#EXTM3UFAKE\n'])
def test_html(text,channels):
    with pytest.raises(Rejected, match='not_m3u'):
        parse_m3u(text, 'a', channels)


def test_no_conflicting_id_or_required_headers(channels):
    text = '#EXTM3U\n#EXTINF:-1 tvg-id="CCTV1",CCTV4K\nhttps://example.org/1\n#EXTINF:-1,CCTV1\n#EXTVLCOPT:http-referrer=https://example.org\nhttps://example.org/2'
    rows, errors = parse_m3u(text, 'a', channels)
    assert not rows and sum(errors.values()) == 2
