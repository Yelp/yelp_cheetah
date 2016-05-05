# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os
import os.path
import sys

import six

from Cheetah.compile import compile_file


def compile_template(filename, **kwargs):
    if not isinstance(filename, six.text_type):
        filename = filename.decode('UTF-8')
    print('Compiling {}'.format(filename))
    return compile_file(filename, **kwargs)


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
            compile_template(filename, **kwargs)

    return any(filename.endswith(extension) for filename in filenames)


def _touch_init_if_not_exists(directory):
    if '__pycache__' in directory:
        return
    init_py_file = os.path.join(directory, '__init__.py')
    if not os.path.exists(init_py_file):
        print('Creating {}'.format(init_py_file))
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
            _compile_files_in_directory(
                dirpath,
                filenames,
                extension=extension,
                **kwargs
            )

            _touch_init_if_not_exists(dirpath)


def compile_all(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filenames', nargs='*',
        help='Filenames / directories to cheetah compile templates in',
    )
    parser.add_argument(
        '--extension', default='.tmpl',
        help='File extension to use for compiling directories',
    )
    args = parser.parse_args(argv)

    directories = [
        filename for filename in args.filenames if os.path.isdir(filename)
    ]
    files = [
        filename for filename in args.filenames if not os.path.isdir(filename)
    ]
    compile_directories(directories, extension=args.extension)
    for filename in files:
        compile_template(filename)


def main():  # pragma: no cover (called by commandline only)
    compile_all(sys.argv[1:])


if __name__ == '__main__':
    exit(main())
