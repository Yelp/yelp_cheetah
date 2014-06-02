# -*- coding: UTF-8 -*-
from __future__ import unicode_literals

import sys

from Cheetah import five
from Cheetah.compile import compile_file


def compile_template(filename):
    if not isinstance(filename, five.text):
        filename = filename.decode('UTF-8')
    return compile_file(filename)


def compile_all(filenames):
    for filename in filenames:
        compile_template(filename)


def main():  # pragma: no cover (called by commandline only)
    compile_all(sys.argv[1:])


if __name__ == '__main__':
    exit(main())
