from Cheetah.compile import compile_to_class

from constants import BUILTIN_SRC


tmpl = compile_to_class(BUILTIN_SRC)()
run = tmpl.respond
