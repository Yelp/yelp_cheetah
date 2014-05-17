from __future__ import unicode_literals

import io
import os
import os.path
import subprocess
import sys

from Cheetah.cheetah_compile import compile_template


def test_templates_runnable_using_env(tmpdir):
    tmpl_filename = os.path.join(tmpdir.strpath, 'my_template.tmpl')
    tmpl_py_filename = os.path.join(tmpdir.strpath, 'my_template.py')

    with io.open(tmpl_filename, 'w') as template:
        template.write(
            '$foo\n'
            '$bar\n'
        )

    compile_template(tmpl_filename)

    ret = subprocess.Popen(
        [sys.executable, tmpl_py_filename],
        env={'foo': 'herp', 'bar': 'derp'},
        stdout=subprocess.PIPE,
    ).communicate()[0]

    assert ret.strip() == 'herp\nderp'
