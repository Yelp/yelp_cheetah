# -*- coding: UTF-8 -*-

import sys

import Cheetah.compile
from Cheetah import five


def compile_template(filename):
    if not isinstance(filename, five.text):
        filename = filename.decode('UTF-8')

    return Cheetah.compile.compile_file(filename)


def compile_all(filenames):
    for filename in filenames:
        compile_template(filename)


def main():  # pragma: no cover (called by commandline only)
    compile_all(sys.argv[1:])


if __name__ == '__main__':
    exit(main())
