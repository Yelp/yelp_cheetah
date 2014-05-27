from __future__ import unicode_literals

import io
import os.path
import subprocess
import sys

from Cheetah import five
from Cheetah.cheetah_compile import compile_template
from Cheetah.Parser import ParseError


def get_cheetah_template_output(py_path):
    proc = subprocess.Popen([sys.executable, py_path], stdout=subprocess.PIPE)
    ret = proc.communicate()[0]
    return ret


def write_template(tmpdir_path, src):
    tmpl_path = os.path.join(tmpdir_path, 'a.tmpl')
    with io.open(tmpl_path, 'w') as tmpl_file:
        tmpl_file.write(src)
    return tmpl_path


def test_acceptable_directive_name(tmpdir):
    tmpl_path = write_template(tmpdir.strpath, '#if True\nHai\n#end if\n')
    py_path = compile_template(tmpl_path)
    output = get_cheetah_template_output(py_path)
    assert output.strip() == 'Hai'


def test_unknown_macro_name(tmpdir):
    tmpl_path = write_template(tmpdir.strpath, '#foo\n')
    try:
        compile_template(tmpl_path)
    except ParseError as e:
        ret = five.text(e)
        assert ret == (
            '\n\n'
            'Bad macro name: "foo". You may want to escape that # sign?\n'
            'Line 1, column 1\n'
            '\n'
            'Line|Cheetah Code\n'
            '----|-------------------------------------------------------------\n'
            '1   |#foo\n'
            '     ^\n'
        )
        return
    raise AssertionError('Expected to raise')
