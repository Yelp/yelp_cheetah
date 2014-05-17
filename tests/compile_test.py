from __future__ import unicode_literals

import io
import os.path
import pytest
import subprocess
import textwrap

from Cheetah import five
from Cheetah.compile import compile_file
from Cheetah.compile import compile_source
from Cheetah.compile import compile_to_class
from Cheetah.compile import create_module_from_source
from Cheetah.compile import detect_encoding
from Cheetah.NameMapper import NotFound
from Cheetah.Template import Template


def test_compile_source_requires_text():
    with pytest.raises(TypeError):
        compile_source(b'not text')


def test_compile_source_cls_name_requires_text():
    with pytest.raises(TypeError):
        compile_source('text', cls_name=b'not text')


def test_compile_source_returns_text():
    ret = compile_source('Hello World')
    assert type(ret) is five.text
    assert 'Hello World' in ret


def test_compile_source_with_encoding_returns_text():
    ret = compile_source('#encoding utf-8\n\nHello World \u2603')
    assert type(ret) is five.text


def test_compile_cls_name_in_output():
    ret = compile_source('Hello World', cls_name='my_cls_name')
    assert 'class my_cls_name(' in ret


def test_compile_source_follows_settings():
    ret = compile_to_class(
        textwrap.dedent(
            '''
            #def baz()
                #set foo = {'a': 1234}
                $foo.a
            #end def

            $baz()
            '''
        ),
        settings={'useDottedNotation': False},
    )

    with pytest.raises(NotFound):
        ret(searchList=[]).respond()


def test_compile_file_filename_requires_text():
    with pytest.raises(TypeError):
        compile_file(b'not_text.tmpl')


def test_compile_file_complains_when_cls_name_is_specified():
    with pytest.raises(ValueError):
        compile_file('temp.tmpl', cls_name='foo')


@pytest.yield_fixture
def tmpfile(tmpdir):
    tmpfile_path = os.path.join(tmpdir.strpath, 'temp.tmpl')
    with io.open(tmpfile_path, 'w') as tmpfile:
        tmpfile.write('Hello World')

    yield tmpfile_path


def test_compile_file(tmpfile):
    compiled_python_file = compile_file(tmpfile)

    assert os.path.exists(compiled_python_file)
    python_file_contents = io.open(compiled_python_file).read()
    assert python_file_contents.splitlines()[0] == '# -*- coding: utf-8 -*-'
    assert 'class temp(' in python_file_contents


def test_compile_file_returns_target(tmpfile):
    ret = compile_file(tmpfile)
    assert ret == os.path.splitext(tmpfile)[0] + '.py'


def test_compile_file_destination(tmpfile, tmpdir):
    output_file = os.path.join(tmpdir.strpath, 'out.py')
    compile_file(tmpfile, target=output_file)
    assert os.path.exists(output_file)
    python_file_contents = io.open(output_file).read()
    assert 'class temp(' in python_file_contents


def test_compile_file_as_script(tmpfile):
    subprocess.check_call(['cheetah-compile', tmpfile])


def test_detect_encoding_empty_file(tmpfile):
    io.open(tmpfile, 'w').close()
    assert detect_encoding(tmpfile) == 'utf-8'


def test_detect_encoding_encoding_specified(tmpfile):
    with io.open(tmpfile, 'w') as file:
        file.write('#encoding latin-1\n')

    assert detect_encoding(tmpfile) == 'latin-1'


def test_non_utf8_in_first_line_raises_TypeError(tmpfile):
    non_utf8_string = b'\x97\n'

    # Try and decode it
    with pytest.raises(UnicodeDecodeError):
        non_utf8_string.decode('utf-8')

    with io.open(tmpfile, 'wb') as file:
        file.write(b'\x97\n')

    with pytest.raises(TypeError):
        detect_encoding(tmpfile)


def test_create_module_from_source():
    my_module_source = textwrap.dedent(
        '''
        MODULE_CONSTANT = 9001


        def snowman_pls():
            return u'\u2603'


        def multiple_snowmans(i):
            return i * snowman_pls()
        '''
    )

    module = create_module_from_source(my_module_source)
    assert module.MODULE_CONSTANT == 9001
    assert module.snowman_pls() == '\u2603'
    assert module.multiple_snowmans(3) == '\u2603\u2603\u2603'


def test_compile_to_class_default_class_name():
    ret = compile_to_class('Hello World')
    assert ret.__name__ == 'DynamicallyCompiledTemplate'
    assert issubclass(ret, Template)


def test_compile_to_class_non_default_class_name():
    ret = compile_to_class('Hello World', cls_name='foo')
    assert ret.__name__ == 'foo'
    assert issubclass(ret, Template)
