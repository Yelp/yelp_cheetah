from Cheetah.compile import compile_to_class
from constants import LOCAL_SRC
from constants import NO_AUTO_SELF


tmpl = compile_to_class(NO_AUTO_SELF + LOCAL_SRC)()
run = tmpl.respond
