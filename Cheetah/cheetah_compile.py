# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import os.path
import sys

from Cheetah import five
from Cheetah.compile import compile_file


def compile_template(filename, **kwargs):
    if not isinstance(filename, five.text):
        filename = filename.decode('UTF-8')
    return compile_file(filename, **kwargs)


def compile_all(filenames):
    for filename in filenames:
        compile_template(filename)


def _compile_files_in_directory(
        directory,
        filenames,
        extension='.tmpl',
        **kwargs
):
    """Compiles files in a directory, returns whether there were any."""
    for filename in filenames:
        if filename.endswith(extension):
            filename = os.path.join(directory, filename)
            print('Compiling {0}'.format(filename))
            compile_template(filename, **kwargs)

    return any(filename.endswith(extension) for filename in filenames)


def _touch_init_if_not_exists(directory):
    init_py_file = os.path.join(directory, '__init__.py')
    if not os.path.exists(init_py_file):
        print('Creating {0}'.format(init_py_file))
        open(init_py_file, 'a').close()


def compile_directories(directories, extension='.tmpl', **kwargs):
    """Compiles all templates in the given directories.  Touches __init__.py
    for each sub-package inside the directories to make the outputs importable.

    :param tuple directories: Iterable of directories to iterate.
    :param kwargs: additional arguments to pass to compiler.
    """
    for directory in directories:
        for dirpath, _, filenames in os.walk(directory):
            # Compile all the files
            has_templates = _compile_files_in_directory(
                dirpath,
                filenames,
                extension=extension,
                **kwargs
            )

            # Don't add __init__.py if we're not a template directory
            if not has_templates:
                continue

            _touch_init_if_not_exists(dirpath)


def main():  # pragma: no cover (called by commandline only)
    compile_all(sys.argv[1:])


if __name__ == '__main__':
    exit(main())
