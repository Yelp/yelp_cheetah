from __future__ import unicode_literals


ITERATIONS = 10

LOCAL_SRC = (
    '#from constants import ITERATIONS\n'
    '#def foo(x)\n'
    '#for _ in range(ITERATIONS)\n'
    '#silent $x\n'
    '#end for\n'
    '#end def\n'
    '$self.foo(9001)\n'
)

GLOBAL_SRC = (
    '#from constants import ITERATIONS\n'
    '#silent [$ITERATIONS for _ in range(ITERATIONS)]\n'
)

BUILTIN_SRC = (
    '#from constants import ITERATIONS\n'
    '#silent [$int for _ in range(ITERATIONS)]\n'
)

SL_SRC = (
    '#from constants import ITERATIONS\n'
    '#silent [$foo for _ in range(ITERATIONS)]\n'
)

DOTTED_SL_SRC = (
    '#from constants import ITERATIONS\n'
    '#silent [$foo.bar[0].upper() for _ in range(ITERATIONS)]\n'
)
