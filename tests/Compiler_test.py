from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os.path

from Cheetah.compile import compile_source
from Cheetah.compile import _create_module_from_source
from Cheetah.cheetah_compile import compile_template
from testing.util import run_python


def test_templates_runnable_using_env(tmpdir):
    tmpl_filename = os.path.join(tmpdir.strpath, 'my_template.tmpl')
    tmpl_py_filename = os.path.join(tmpdir.strpath, 'my_template.py')

    with io.open(tmpl_filename, 'w') as template:
        template.write(
            '$foo\n'
            '$bar\n'
        )

    compile_template(tmpl_filename)

    ret = run_python(tmpl_py_filename, env={'foo': 'herp', 'bar': 'derp'})
    assert ret.strip() == 'herp\nderp'


def test_template_exposes_global():
    src = compile_source('Hello World')
    module = _create_module_from_source(src)
    assert module.__YELP_CHEETAH__ is True


def test_unicode_literals_on():
    tmpl_source = compile_source(
        'Hello World',
        settings={'future_unicode_literals': True},
    )
    assert 'from __future__ import unicode_literals\n' in tmpl_source
    # No u because we're unicode literals
    assert "write('''Hello World''')" in tmpl_source


def test_unicode_literals_off():
    tmpl_source = compile_source(
        'Hello World',
        settings={'future_unicode_literals': False},
    )
    assert 'from __future__ import unicode_literals\n' not in tmpl_source
    # u because we're not unicode literals
    assert "write(u'''Hello World''')" in tmpl_source
