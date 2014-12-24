from __future__ import unicode_literals

import imp
import io
import os.path

import six

from Cheetah.legacy_compiler import CLASS_NAME
from Cheetah.legacy_compiler import LegacyCompiler


def compile_source(
        source,
        settings=None,
        compiler_cls=LegacyCompiler,
):
    """The general case for compiling from source.

    :param text source: Text representing the cheetah source.
    :param dict settings: Compile settings
    :param type compiler_cls: Class to use for the compiler.
    :return: The compiled output.
    :rtype: text
    :raises TypeError: if source is not text.
    """
    if not isinstance(source, six.text_type):
        raise TypeError(
            '`source` must be `text` but got {0!r}'.format(type(source))
        )

    compiler = compiler_cls(source, settings=settings)
    return compiler.getModuleCode()


def compile_file(filename, target=None, **kwargs):
    """Compiles a file.

    :param text filename: Filename of the file to open
    :param kwargs: Keyword args passed to `compile`
    """
    if not isinstance(filename, six.text_type):
        raise TypeError(
            '`filename` must be `text` but got {0!r}'.format(type(filename))
        )

    contents = io.open(filename, encoding='UTF-8').read()

    py_file = os.path.basename(filename).split('.', 1)[0] + '.py'
    compiled_source = compile_source(contents, **kwargs)

    if target is None:
        dirname = os.path.dirname(filename)
        target = os.path.join(dirname, py_file)

    with io.open(target, 'w', encoding='UTF-8') as target_file:
        target_file.write('# -*- coding: UTF-8 -*-\n')
        target_file.write(compiled_source)

    return target


def _create_module_from_source(source, filename='<generated cheetah module>'):
    """Creates a module from the given source.

    :param text source: Sourcecode to put into new module.
    :return: A Module object.
    """
    assert type(source) is six.text_type

    module = imp.new_module('created_module')
    module.__file__ = filename
    code = compile(source, filename, 'exec', dont_inherit=True)
    exec(code, module.__dict__)  # pylint:disable=exec-used
    return module


def compile_to_class(source, **kwargs):
    """Compile source directly to a `type` object.  Mainly used by tests.

    :param text source: Text representing the cheetah source
    :param kwargs: Keyword args passed to `compile`
    :return: A `Template` class
    :rtype: type
    """
    compiled_source = compile_source(source, **kwargs)
    module = _create_module_from_source(compiled_source)
    cls = getattr(module, CLASS_NAME)
    # To prevent our module from getting gc'd
    cls.__module_obj__ = module
    return cls
