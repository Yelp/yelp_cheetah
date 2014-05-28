from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os.path
import pytest

from Cheetah.cheetah_compile import compile_template
from Cheetah.cheetah_compile import compile_all
from testing.util import run_python


@pytest.yield_fixture
def template_writer(tmpdir):
    class TemplateWriter(object):
        def __init__(self):
            self.tmpl_number = 0

        def write(self, src):
            self.tmpl_number += 1
            tmpl_path = os.path.join(
                tmpdir.strpath, 'a{0}.tmpl'.format(self.tmpl_number)
            )
            with io.open(tmpl_path, 'w') as tmpl_file:
                tmpl_file.write(src)

            return tmpl_path
    yield TemplateWriter()


def _test_compile_template(tmpl_file):
    tmpl_py = compile_template(tmpl_file)
    assert os.path.exists(tmpl_py)
    ret = run_python(tmpl_py)
    assert ret == 'Hello world\n'


def test_compile_template(template_writer):
    tmpl_file = template_writer.write('Hello world')
    _test_compile_template(tmpl_file)


def test_compile_template_with_bytes(template_writer):
    """argv passes bytes in py2"""
    tmpl_file = template_writer.write('Hello world')
    filename = tmpl_file.encode('utf-8')
    assert isinstance(filename, bytes)
    _test_compile_template(filename)


def test_compile_multiple_files(template_writer):
    tmpl1 = template_writer.write('foo')
    tmpl2 = template_writer.write('bar')
    compile_all([tmpl1, tmpl2])
    assert run_python(tmpl1.replace('.tmpl', '.py')) == 'foo\n'
    assert run_python(tmpl2.replace('.tmpl', '.py')) == 'bar\n'
