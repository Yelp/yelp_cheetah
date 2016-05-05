from Cheetah.compile import compile_to_class
from constants import WRITE_SRC


tmpl = compile_to_class(WRITE_SRC.format('"hello world"'))()
run = tmpl.respond
