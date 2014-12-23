from Cheetah.compile import compile_to_class

from constants import GLOBAL_SRC


tmpl = compile_to_class(GLOBAL_SRC)()
run = tmpl.respond
