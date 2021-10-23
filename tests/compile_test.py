import os.path
import subprocess
import sys
import textwrap

import pytest

from Cheetah.compile import _create_module_from_source
from Cheetah.compile import compile_file
from Cheetah.compile import compile_source
from Cheetah.compile import compile_to_class
from Cheetah.legacy_parser import directiveNamesAndParsers
from Cheetah.Template import Template


def test_compile_source_requires_text():
    with pytest.raises(TypeError):
        compile_source(b'not text')


def test_compile_source_returns_text():
    ret = compile_source('Hello, world!')
    assert type(ret) is str
    assert "write('''Hello, world!''')" in ret


def test_compile_source_with_encoding_returns_text():
    ret = compile_source('Hello, world! ☃')
    assert type(ret) is str
    assert "write('''Hello, world! ☃''')" in ret


def test_compile_source_follows_settings():
    tmpl = textwrap.dedent(
        '''
        #try
            #import foo
        #except ImportError
            importerror
        #end try
        ''',
    )

    ret = compile_to_class(tmpl, settings={'useLegacyImportMode': False})
    assert '\n    importerror\n' == ret().respond()

    with pytest.raises(SyntaxError):
        compile_to_class(tmpl, settings={'useLegacyImportMode': True})


def test_compile_file_filename_requires_text():
    with pytest.raises(TypeError):
        compile_file(b'not_text.tmpl')


@pytest.fixture
def tmpfile(tmpdir):
    tmpfile_path = os.path.join(tmpdir.strpath, 'temp.tmpl')
    with open(tmpfile_path, 'w') as tmpfile:
        tmpfile.write('Hello, world!')

    yield tmpfile_path


def test_compile_file(tmpfile):
    compiled_python_file = compile_file(tmpfile)

    assert os.path.exists(compiled_python_file)
    with open(compiled_python_file) as f:
        python_file_contents = f.read()
    assert 'class YelpCheetahTemplate(' in python_file_contents


def test_compile_file_returns_target(tmpfile):
    ret = compile_file(tmpfile)
    assert ret == os.path.splitext(tmpfile)[0] + '.py'


def test_compile_file_destination(tmpfile, tmpdir):
    output_file = os.path.join(tmpdir.strpath, 'out.py')
    compile_file(tmpfile, target=output_file)
    assert os.path.exists(output_file)
    python_file_contents = open(output_file).read()
    assert 'class YelpCheetahTemplate(' in python_file_contents
    assert "write('''Hello, world!''')" in python_file_contents


def test_compile_file_as_script(tmpfile):
    subprocess.check_call(['cheetah-compile', tmpfile])
    pyfile = tmpfile.replace('.tmpl', '.py')
    module = _create_module_from_source(
        '\n'.join(open(pyfile).read().splitlines()[1:]),
    )
    result = module.YelpCheetahTemplate().respond()
    assert 'Hello, world!' == result


def test_non_utf8_raises_error(tmpfile):
    non_utf8_string = b'\x97\n'

    # Try and decode it
    with pytest.raises(UnicodeDecodeError):
        non_utf8_string.decode()

    with open(tmpfile, 'wb') as file_obj:
        file_obj.write(non_utf8_string)

    with pytest.raises(UnicodeDecodeError):
        compile_file(tmpfile)


def test_create_module_from_source():
    my_module_source = textwrap.dedent(
        '''
        MODULE_CONSTANT = 9001


        def snowman_pls():
            return u'☃'


        def multiple_snowmans(i):
            return i * snowman_pls()
        ''',
    )

    module = _create_module_from_source(my_module_source)
    assert module.MODULE_CONSTANT == 9001
    assert module.snowman_pls() == '☃'
    assert module.multiple_snowmans(3) == '☃☃☃'


def test_compile_to_class_default_class_name():
    ret = compile_to_class('Hello, world!')
    assert ret.__name__ == 'YelpCheetahTemplate'
    assert ret.__module__ == 'created_module'
    assert ret.__module_obj__
    assert issubclass(ret, Template)

    assert type(ret.__module_obj__) is type(sys)
    assert ret.__module_obj__.__name__ == 'created_module'
    assert ret.__module_obj__.__file__ == '<generated cheetah module>'

    assert 'Hello, world!' == ret().respond()
    assert 'created_module' not in sys.modules


def test_compile_to_class_traceback():
    ret = compile_to_class('${1/0}')

    try:
        ret().respond()
    except ZeroDivisionError:
        from traceback import format_exc
        traceback = format_exc()
    else:
        raise AssertionError("Should raise ZeroDivision")

    # The current implementation doesn't show the line of code which caused the exception:
    import re
    assert re.match(
        r'''Traceback \(most recent call last\):
  File ".+/tests/compile_test\.py", line \d*, in test_compile_to_class_traceback
    ret\(\).respond\(\)
  File "<generated cheetah module>", line \d*, in respond
ZeroDivisionError: (integer )?division( or modulo)? by zero''', traceback,
    )


def test_compile_is_deterministic():
    # This crazy template uses all of the currently supported directives
    MEGA_TEMPLATE = """
#compiler-settings
useLegacyImportMode = False
#end compiler-settings
#extends testing.templates.extends_test_template
#implements respond

#import contextlib
#import sys
#from tests.SyntaxAndOutput_test import dummydecorator


#attr attribute = "bar"


#@dummydecorator
#def returning_function()
    #return 5
#end def


#def try_raise_finally_func()
    #try
        #raise AssertionError("foo")
    #except AssertionError
        Caught AssertionError
    #except ValueError
        #pass
    #finally
        Finally
    #end try
#end def


#def spacer()
   #super()
   after
#end def


#def gen()
    #yield 1
    #yield 2
    #yield 3
#end def

#@contextlib.contextmanager
#def ctx()
    before
    #yield
    after
#end def


#py foo = {"a": 1}
#del foo['a']
$foo


#assert True


$self.returning_function()
$self.spacer()

#if 15
   15!
#elif 16
   16!
#else
   not 15 or 16
#end if

#py arr = [1, 2, 3]
#py arr.append(5)
$arr

#block infinite_loop_meybs
    #while True
        infinite loop?
        #break ## nope lol
    #end while
#end block

#for i in self.gen()
    #if $i == 2
        #continue
    #end if
    $i#slurp
#end for

#with self.ctx()
    inside ctx
#end with
    """
    compiled_templates = [compile_source(MEGA_TEMPLATE) for _ in range(5)]
    assert len(set(compiled_templates)) == 1

    # Make sure we got all of the directives
    for directive_name in directiveNamesAndParsers:
        assert f'#{directive_name}' in MEGA_TEMPLATE

    # also make sure MEGA_TEMPLATE renders
    assert compile_to_class(MEGA_TEMPLATE)().respond()
