from Cheetah.compile import compile_to_class

from constants import BUILTIN_SRC


tmpl = compile_to_class(BUILTIN_SRC, settings={'optimize_lookup': False})()
run = tmpl.respond
