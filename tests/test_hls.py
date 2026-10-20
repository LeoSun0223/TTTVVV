import pytest

from iptv_clean.hls import parse_hls
from iptv_clean.models import Rejected


@pytest.mark.parametrize('extra,reason', [('#EXT-X-ENDLIST','vod_endlist'),('#EXT-X-PLAYLIST-TYPE:VOD','vod_endlist'),('#EXT-X-KEY:METHOD=AES-128,URI="key"','unsupported_encryption'),('#EXT-X-KEY:METHOD=SAMPLE-AES,URI="key"','unsupported_encryption'),('#EXT-X-SKIP:SKIPPED-SEGMENTS=2','unsupported_hls')])
def test_unsupported(extra,reason):
    with pytest.raises(Rejected, match=reason):
        parse_hls(('#EXTM3U\n#EXT-X-TARGETDURATION:8\n'+extra+'\n#EXTINF:8,\na.ts').encode(), 'https://example.org/a.m3u8')


@pytest.mark.parametrize('body', [b'<html>200 OK</html>', b'', b'#EXTM3U\n#EXT-X-PART:DURATION=1,URI="a.m4s"'])
def test_non_hls_or_partial_only(body):
    with pytest.raises(Rejected):
        parse_hls(body, 'https://example.org/a')


def test_relative_query_and_byte_ranges():
    body = b'#EXTM3U\n#EXT-X-TARGETDURATION:8\n#EXT-X-MAP:URI="init.mp4",BYTERANGE="50@0"\n#EXT-X-BYTERANGE:100@50\n#EXTINF:8,\n../stream.mp4?v=1\n#EXT-X-BYTERANGE:200\n#EXTINF:8,\n../stream.mp4?v=1'
    p = parse_hls(body, 'https://example.org/live/a.m3u8')
    assert p.segments[0].url == 'https://example.org/stream.mp4?v=1'
    assert p.segments[1].byte_range == (150,200)
    assert p.segments[0].init == ('https://example.org/live/init.mp4',(0,50))
