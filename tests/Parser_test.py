from __future__ import unicode_literals

import io
import pytest
import os.path
import subprocess
import sys

from Cheetah import five
from Cheetah.Parser import ArgList
from Cheetah.cheetah_compile import compile_template
from Cheetah.Parser import UnknownDirectiveError


@pytest.yield_fixture
def arglist():
    yield ArgList()


def test_ArgList_merge1(arglist):
    """Testing the ArgList case results from
    Template.Preprocessors.test_complexUsage
    """
    arglist.add_argument('arg')
    assert arglist.merge() == [('arg', None)]


def test_ArgList_merge2(arglist):
    """Testing the ArgList case results from
    SyntaxAndOutput.BlockDirective.test4
    """
    arglist.add_argument('a')
    arglist.add_default('999')
    arglist.next()
    arglist.add_argument('b')
    arglist.add_default('444')

    assert arglist.merge() == [('a', '999'), ('b', '444')]


def test_merge3(arglist):
    """Testing the ArgList case results
    from SyntaxAndOutput.BlockDirective.test13
    """
    arglist.add_argument('arg')
    arglist.add_default("'This is my block'")
    assert arglist.merge() == [('arg', "'This is my block'")]


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
    except UnknownDirectiveError as e:
        ret = five.text(e)
        assert ret == (
            '\n\n'
            'Bad macro name: "foo". You may want to escape that # sign?\n'
            'Line 1, column 2\n'
            '\n'
            'Line|Cheetah Code\n'
            '----|-------------------------------------------------------------\n'
            '1   |#foo\n'
            '      ^\n'
        )
        return
    raise AssertionError('Expected to raise')
