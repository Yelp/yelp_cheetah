from Cheetah.compile import compile_to_class
from constants import DOTTED_SL_SRC
from constants import NO_AUTO_SELF


class fooobj:
    bar = 'baz'


tmpl = compile_to_class(NO_AUTO_SELF + DOTTED_SL_SRC)({'foo': fooobj})
run = tmpl.respond
