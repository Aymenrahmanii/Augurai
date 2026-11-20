from augurai.models import RawItem


def test_make_id_normalizes():
    a = RawItem.make_id("https://GitHub.com/a/b/?utm_source=x")
    b = RawItem.make_id("https://github.com/a/b")
    assert a == b and len(a) == 16
