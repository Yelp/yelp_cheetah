from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os.path

from Cheetah.compile import compile_source
from Cheetah.compile import compile_to_class
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


def test_comments():
    tmpl_source = compile_source('## foo')
    assert '# foo' in tmpl_source


def test_optimized_builtins():
    src = compile_source('$int("9001")')
    # Instead of _v = VFFSL(SL, "int"...
    assert '_v = int("9001")' in src


def test_optimized_attributes_of_builtins():
    src = compile_source('$ValueError.__name__')
    assert '_v = ValueError.__name__' in src


def test_optimized_attributes_of_builtins_function_args():
    cls = compile_to_class('$float.fromhex($bar)')
    assert cls([{'bar': '0x5'}]).respond().strip() == '5.0'


def test_non_optimized_searchlist():
    src = compile_source('$int($foo)')
    assert '_v = int(VFFSL(SL, "foo"' in src


def test_optimization_still_prefers_locals():
    cls = compile_to_class(
        '#def foo(int)\n'
        '$int\n'
        '#end def\n'
    )
    assert cls().foo(5).strip() == '5'


def test_no_optimization_with_autocall():
    cls = compile_to_class(
        '#compiler-settings\n'
        'useAutocalling = True\n'
        '#end compiler-settings\n'
        '#def foo(int)\n'
        '$int\n'
        '#end def\n'
    )
    # With optimizations this outputs:
    # &lt;function &lt;lambda&gt; at 0x7f7a640f60c8&gt;
    assert cls().foo(lambda: 5).strip() == '5'


def test_no_optimization_with_autokey():
    cls = compile_to_class(
        '#compiler-settings \n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '#def foo(int)\n'
        '$int.bar\n'
        '#end def\n'
    )
    # With optimizations this errors:
    # AttributeError: 'dict' object has no attribute 'bar'
    assert cls().foo({'bar': 5}).strip() == '5'
