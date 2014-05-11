import contextlib
import subprocess
import sys

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


def run_python(path, env={}):
    proc = subprocess.Popen(
        [sys.executable, path], env=env, stdout=subprocess.PIPE,
    )
    return proc.communicate()[0].decode('utf-8')
