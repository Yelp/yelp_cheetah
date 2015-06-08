from Cheetah.compile import compile_to_class

from constants import SL_SRC


tmpl = compile_to_class(SL_SRC)({'foo': 'bar'})
run = tmpl.respond
