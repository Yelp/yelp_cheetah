from Cheetah.compile import compile_to_class

from constants import DOTTED_SL_SRC


class fooobj:
    bar = 'baz'


tmpl = compile_to_class(DOTTED_SL_SRC)([{'foo': fooobj}])
run = tmpl.respond
