import contextlib

from Cheetah import five


@contextlib.contextmanager
def assert_raises_exactly(cls, text):
    try:
        yield
    except Exception as e:
        assert type(e) is cls
        assert five.text(e) == text
    else:
        raise AssertionError('expected to raise')
