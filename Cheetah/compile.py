from __future__ import unicode_literals

import imp
import io
import os.path

from Cheetah import five
from Cheetah.Compiler import Compiler


def compile_source(
    source,
    cls_name='DynamicallyCompiledTemplate',
    settings=None,
    compiler_cls=Compiler,
):
    """The general case for compiling from source.

    :param text source: Text representing the cheetah source.
    :param text cls_name: Classname for the generated module.
    :param dict settings: Compiler settings
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

    if settings is None:
        settings = {}

    compiler = compiler_cls(
        source,
        moduleName=cls_name,
        mainClassName=cls_name,
        settings=settings,
    )
    compiler.compile()
    return compiler.getModuleCode()


def detect_encoding(filename):
    """Detects the #encoding directive and returns the encoding.  If none is
    found, the default is utf-8

    The #encoding directive must appear on the first line of the file and
    specify a valid encoding.

    :param text filename: Filename to open
    :return: The detected encoding of the file or utf-8.
    :rtype: text
    :raises TypeError: If the first line of the file is not valid utf-8.
    """
    # Read the file as binary.  We assume the first line is utf-8
    with io.open(filename, 'rb') as file_obj:
        first_line = file_obj.readline()

    # Attempt to look at the first line as utf-8
    try:
        first_line = first_line.decode('utf-8')
    except UnicodeDecodeError:
        raise TypeError(
            'File does not start with an #encoding directive '
            'but has non utf-8 bytes.'
        )

    if first_line.startswith('#encoding'):
        return first_line.split()[1].lower()

    return 'utf-8'


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

    contents = io.open(filename, encoding=detect_encoding(filename)).read()

    cls_name = os.path.basename(filename).split('.', 1)[0]
    compiled_source = compile_source(contents, cls_name=cls_name, **kwargs)

    if target is None:
        # Write out to the file {cls_name}.py
        dirname = os.path.dirname(filename)
        target = os.path.join(dirname, '{0}.py'.format(cls_name))

    with io.open(target, 'w', encoding='utf-8') as target_file:
        target_file.write('# -*- coding: utf-8 -*-\n\n')
        target_file.write(compiled_source)

    return target


def create_module_from_source(source):
    """Creates a module from the given source.

    :param text source: Sourcecode to put into new module.
    :return: A Module object.
    """
    module = imp.new_module('created_module')
    code = compile(source, '<generated cheetah module>', 'exec', dont_inherit=True)
    exec(code, module.__dict__)
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
    module = create_module_from_source(compiled_source)
    cls = getattr(module, cls_name)
    # To prevent our module from getting gc'd
    cls.__module_obj__ = module
    return cls
