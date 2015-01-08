from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os.path

from Cheetah.cheetah_compile import compile_template
from Cheetah.compile import _create_module_from_source
from Cheetah.compile import compile_source
from Cheetah.compile import compile_to_class
from Cheetah.Template import Template
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
    # Instead of _v = VFFSL("int"...
    assert ' _v = int("9001") #' in src


def test_optimized_attributes_of_builtins():
    src = compile_source('$ValueError.__name__')
    assert ' _v = ValueError.__name__ #' in src


def test_optimized_attributes_of_builtins_function_args():
    cls = compile_to_class('$float.fromhex($bar)')
    assert cls({'bar': '0x5'}).respond().strip() == '5.0'


def test_non_optimized_searchlist():
    src = compile_source('$int($foo)')
    assert ' _v = int(VFFSL("foo"' in src


def test_optimization_still_prefers_locals():
    cls = compile_to_class(
        '#def foo(int)\n'
        '$int\n'
        '#end def\n'
    )
    assert cls().foo(5).strip() == '5'


def test_optimization_globals():
    src = compile_source(
        '#import os\n'
        '$os.path.join("foo", "bar")\n'
    )
    assert ' _v = os.path.join(' in src


def test_optimization_parameters():
    src = compile_source(
        '#def foo(bar)\n'
        '$bar\n'
        '#end def\n'
    )
    assert ' _v = bar #' in src


def test_optimization_import_dotted_name():
    src = compile_source(
        '#import os.path\n'
        '$os.path.join("foo", "bar")\n'
    )
    assert ' _v = os.path.join(' in src


def test_optimization_import_as_name():
    src = compile_source(
        '#import os.path as herp\n'
        '$herp.join("foo", "bar")\n'
    )
    assert ' _v = herp.join(' in src


def test_optimization_from_imports():
    src = compile_source(
        '#from os import path\n'
        '$path.join("foo", "bar")\n'
    )
    assert ' _v = path.join(' in src


def test_optimization_assign():
    src = compile_source(
        '#py foo = "bar"\n'
        '$foo\n'
    )
    assert ' _v = foo #' in src


def test_optimization_with():
    src = compile_source(
        '#with foo() as bar:\n'
        '    $bar\n'
        '#end with\n'
    )
    assert ' _v = bar #' in src


def test_optimization_for():
    src = compile_source(
        '#for foo in bar:\n'
        '    $foo\n'
        '#end for\n'
    )
    assert ' _v = foo #' in src


def test_optimization_except():
    src = compile_source(
        '#try\n'
        '    #pass\n'
        '#except Exception as e\n'
        '    $e\n'
        '#end try\n'
    )
    assert ' _v = e #' in src


def test_optimization_multiple_assign():
    src = compile_source(
        '#py x = y = z = 0\n'
        '$x\n'
        '$y\n'
        '$z\n'
    )
    assert ' _v = x #' in src
    assert ' _v = y #' in src
    assert ' _v = z #' in src


def test_optimization_tuple_assign():
    src = compile_source(
        '#py x, (y, z) = (1, (2, 3))\n'
        '$x\n'
        '$y\n'
        '$z\n'
    )
    assert ' _v = x #' in src
    assert ' _v = y #' in src
    assert ' _v = z #' in src


VFN_opt_src = '$foo.barvar[0].upper()'


class fooobj(object):
    barvar = 'womp'


def test_optimization_removes_VFN():
    src = compile_source(VFN_opt_src)
    assert 'VFN(' not in src
    assert ' _v = VFFSL("foo", locals(), globals(), self, NS).barvar[0].upper() #' in src
    cls = compile_to_class(VFN_opt_src)
    assert cls({'foo': fooobj}).respond() == 'W'


def test_optimization_oneline_class():
    cheetah_src = (
        '#py class notlocal(object): pass\n'
        '$notlocal.__name__\n'
    )
    assert compile_to_class(cheetah_src)().respond() == 'notlocal\n'
    src = compile_source(cheetah_src)
    assert ' _v = notlocal.__name__ #' in src


def test_optimization_oneline_function():
    cheetah_src = (
        '#py def foo(x): return x * x\n'
        '$foo(2)\n'
    )
    assert compile_to_class(cheetah_src)().respond() == '4\n'
    src = compile_source(cheetah_src)
    assert ' _v = foo(2) #' in src


def test_optimization_args():
    src = compile_source(
        '#def foo(*args)\n'
        '$args\n'
        '#end def\n'
    )
    assert ' _v = args #' in src


def test_optimization_kwargs():
    src = compile_source(
        '#def foo(**kwargs)\n'
        '$kwargs\n'
        '#end def\n'
    )
    assert ' _v = kwargs #' in src


def test_optimization_partial_template_functions():
    from testing.templates.src.optimize_name import foo
    assert foo(Template()).strip() == '25'
    src = io.open('testing/templates/src/optimize_name.py').read()
    assert ' _v = bar(5) #' in src
