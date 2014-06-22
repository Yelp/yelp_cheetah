from __future__ import unicode_literals

import imp
import io
import os.path

from Cheetah import five
from Cheetah.legacy_compiler import LegacyCompiler


def compile_source(
        source,
        cls_name='DynamicallyCompiledTemplate',
        settings=None,
        compiler_cls=LegacyCompiler,
):
    """The general case for compiling from source.

    :param text source: Text representing the cheetah source.
    :param text cls_name: Classname for the generated module.
    :param dict settings: Compile settings
    :param type compiler_cls: Class to use for the compiler.
    :return: The compiled output.
    :rtype: text
    :raises TypeError: if source or cls_name are not text.
    """
    if not isinstance(source, five.text):
        raise TypeError(
            '`source` must be `text` but got {0!r}'.format(type(source))
        )

    if not isinstance(cls_name, five.text):
        raise TypeError(
            '`cls_name` must be `text` but got {0!r}'.format(type(cls_name))
        )

    compiler = compiler_cls(source, cls_name, settings=settings)
    return compiler.getModuleCode()


def compile_file(filename, target=None, **kwargs):
    """Compiles a file.

    :param text filename: Filename of the file to open
    :param kwargs: Keyword args passed to `compile`
    """
    if not isinstance(filename, five.text):
        raise TypeError(
            '`filename` must be `text` but got {0!r}'.format(type(filename))
        )

    if 'cls_name' in kwargs:
        raise ValueError('`cls_name` when compiling a file is invalid')

    contents = io.open(filename, encoding='UTF-8').read()

    cls_name = os.path.basename(filename).split('.', 1)[0]
    compiled_source = compile_source(contents, cls_name=cls_name, **kwargs)

    if target is None:
        # Write out to the file {cls_name}.py
        dirname = os.path.dirname(filename)
        target = os.path.join(dirname, '{0}.py'.format(cls_name))

    with io.open(target, 'w', encoding='UTF-8') as target_file:
        target_file.write('# -*- coding: UTF-8 -*-\n')
        target_file.write(compiled_source)

    return target


def _create_module_from_source(source, filename='<generated cheetah module>'):
    """Creates a module from the given source.

    :param text source: Sourcecode to put into new module.
    :return: A Module object.
    """
    assert type(source) is five.text

    module = imp.new_module('created_module')
    module.__file__ = filename
    code = compile(source, filename, 'exec', dont_inherit=True)
    exec(code, module.__dict__)  # pylint:disable=exec-used
    return module


def compile_to_class(source, cls_name='DynamicallyCompiledTemplate', **kwargs):
    """Compile source directly to a `type` object.  Mainly used by tests.

    :param text source: Text representing the cheetah source
    :param text cls_name: Classname for generated module.
    :param kwargs: Keyword args passed to `compile`
    :return: A `Template` class
    :rtype: type
    """
    compiled_source = compile_source(source, cls_name=cls_name, **kwargs)
    module = _create_module_from_source(compiled_source)
    cls = getattr(module, cls_name)
    # To prevent our module from getting gc'd
    cls.__module_obj__ = module
    return cls
