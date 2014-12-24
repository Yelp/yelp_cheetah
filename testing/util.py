import contextlib
import subprocess
import sys

import six


@contextlib.contextmanager
def assert_raises_exactly(cls, text):
    try:
        yield
    except Exception as e:
        assert type(e) is cls
        assert six.text_type(e) == text
    else:
        raise AssertionError('expected to raise')


def run_python(path, env={}):
    proc = subprocess.Popen(
        [sys.executable, path], env=env, stdout=subprocess.PIPE,
    )
    return proc.communicate()[0].decode('UTF-8')
