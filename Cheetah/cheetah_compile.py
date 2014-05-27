# -*- coding: UTF-8 -*-

import sys

import Cheetah.compile
from Cheetah import five


CHEETAH_OPTS = dict(
    allowNestedDefScopes=False,
    # This strange fellow makes template functions write to the current buffer,
    # rather than returning a flattened string (and losing the Markup blessing)
    autoAssignDummyTransactionToSelf=True,
    # These are the cretins responsible for magically resolving $foo.bar as
    # foo['bar'] and $self.foo as self.foo().
    useAutocalling=False,
    useDottedNotation=False,
)


def compile_template(filename):
    if not isinstance(filename, five.text):
        filename = filename.decode('UTF-8')

    return Cheetah.compile.compile_file(filename, settings=CHEETAH_OPTS)


def compile_all(filenames):
    for filename in filenames:
        compile_template(filename)


def main():
    compile_all(sys.argv[1:])


if __name__ == '__main__':
    exit(main())
