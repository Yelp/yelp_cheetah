from Cheetah.compile import compile_to_class
from constants import NO_AUTO_SELF
from constants import SL_SRC


tmpl = compile_to_class(NO_AUTO_SELF + SL_SRC)({'foo': 'bar'})
run = tmpl.respond
