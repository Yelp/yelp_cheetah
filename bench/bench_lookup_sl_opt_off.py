from Cheetah.compile import compile_to_class

from constants import SL_SRC


tmpl = compile_to_class(SL_SRC, settings={'optimize_lookup': False})([{
    'foo': 'bar',
}])
run = tmpl.respond
