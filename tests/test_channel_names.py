import pytest


@pytest.mark.parametrize('label,expected', [('CCTV-1综合','CCTV1'),('CCTV10','CCTV10'),('CCTV-10科教 HD','CCTV10'),('CCTV5','CCTV5'),('CCTV5+','CCTV5+'),('CCTV5+体育赛事','CCTV5+'),('央视一套','CCTV1'),('浙江卫视高清','浙江卫视'),('上海东方卫视','东方卫视'),('CCTV4K',None),('CCTV8K',None),('CCTV体育赛事',None),('CCTV1电影轮播',None)])
def test_names(channels,label,expected):
    assert channels.normalize(label) == expected
