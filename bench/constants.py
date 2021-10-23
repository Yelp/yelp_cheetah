ITERATIONS = 10

LOCAL_SRC = (
    '#from constants import ITERATIONS\n'
    '#def foo(x)\n'
    '#for _ in range(ITERATIONS)\n'
    '#py $x\n'
    '#end for\n'
    '#end def\n'
    '$self.foo(9001)\n'
)

GLOBAL_SRC = (
    '#from constants import ITERATIONS\n'
    '#py [$ITERATIONS for _ in range(ITERATIONS)]\n'
)

BUILTIN_SRC = (
    '#from constants import ITERATIONS\n'
    '#py [$int for _ in range(ITERATIONS)]\n'
)

SL_SRC = (
    '#from constants import ITERATIONS\n'
    '#py [$foo for _ in range(ITERATIONS)]\n'
)

DOTTED_SL_SRC = (
    '#from constants import ITERATIONS\n'
    '#py [$foo.bar[0].upper() for _ in range(ITERATIONS)]\n'
)


WRITE_SRC = (
    '#from markupsafe import Markup\n'
    '#from constants import ITERATIONS\n'
    '#py x = {}\n'
    '#for _ in range(ITERATIONS)\n'
    '$x\n'
    '#end for\n'
)
